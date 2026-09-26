"""
=============================================================================
迷幻風格 (Trippy) + 物理發光粒子特效 MediaPipe 手部追蹤系統
Psychedelic Trippy Hand Tracker with Physics Glowing Particle System
=============================================================================
功能特性：
1. 核心手部追蹤：跨版本支援 MediaPipe Tasks API 及 Legacy Solutions API，即時捕捉 21 個手部特徵點。
2. 迷幻霓虹視覺 (Trippy Visuals)：
   - HSV 霓虹彩虹色相隨時間動態循環 (Hue Cycling)
   - 節點多層同心光環 (Concentric Pulsating Orbs)
   - 正弦波碎形動態連線 (Sine Wave Harmonic Fractal Connections)
   - 空間殘影回饋緩衝區 (Feedback Decay Buffer & Warp Trail)
3. 物理發光粒子系統 (Glowing Particle System)：
   - 食指尖端 (Landmark 8) 發射器
   - 支援手指揮動慣性加速度注入 (Velocity Injection) + 向下重力 (Gravity) + 空氣阻力 (Drag) + 混沌擾動 (Turbulence)
   - 多層次光暈漸層渲染 (Additive Glow Blending)
4. 互動控制與 HUD 顯示：
   - 快捷鍵切換背景模式、殘影長度、爆炸特效、截圖存檔等。
=============================================================================
"""

import os
import sys
import time
import math
import random
import urllib.request
import cv2
import numpy as np

# 設定 Windows 控制台 UTF-8 編碼
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 嘗試載入 MediaPipe 模組（相容 Tasks API 與 Solutions API）
try:
    import mediapipe as mp
except ImportError:
    print("[錯誤] 未檢測到 mediapipe 套件，請先執行: pip install mediapipe opencv-python numpy")
    sys.exit(1)


# =============================================================================
# 1. 顏色與數學輔助工具 (Color & Math Utilities)
# =============================================================================

def hsv_to_bgr(h: float, s: float = 255.0, v: float = 255.0) -> tuple:
    """
    將 HSV 色彩 (H: 0~179, S: 0~255, V: 0~255) 轉換為 OpenCV BGR (B, G, R) 整數元組
    """
    h_clamped = int(h % 180)
    s_clamped = int(max(0, min(255, s)))
    v_clamped = int(max(0, min(255, v)))
    hsv_pixel = np.uint8([[[h_clamped, s_clamped, v_clamped]]])
    bgr_pixel = cv2.cvtColor(hsv_pixel, cv2.COLOR_HSV2BGR)[0][0]
    return int(bgr_pixel[0]), int(bgr_pixel[1]), int(bgr_pixel[2])


# 手部 21 節點的標準連線骨架定義 (MediaPipe Hand Connections)
HAND_CONNECTIONS = [
    # 拇指
    (0, 1), (1, 2), (2, 3), (3, 4),
    # 食指
    (0, 5), (5, 6), (6, 7), (7, 8),
    # 中指
    (0, 9), (9, 10), (10, 11), (11, 12),
    # 無名指
    (0, 13), (13, 14), (14, 15), (15, 16),
    # 小指
    (0, 17), (17, 18), (18, 19), (19, 20),
    # 掌心橫向連線
    (5, 9), (9, 13), (13, 17)
]


# =============================================================================
# 2. 物理發光粒子系統 (Glowing Particle System)
# =============================================================================

class Particle:
    """單一物理發光粒子"""
    def __init__(self, x: float, y: float, vx: float, vy: float, hue: float, size: float = 6.0, life: float = 1.0, decay: float = 0.025):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.ax = 0.0
        self.ay = 0.28  # 向下重力加速度 (Gravity)
        self.hue = float(hue)
        self.initial_size = float(size)
        self.size = float(size)
        self.life = float(life)         # 1.0 -> 0.0
        self.max_life = float(life)
        self.decay = float(decay)       # 每幀生命衰減率
        self.drag = 0.965               # 空氣阻力係數 (Damping)
        self.spin = random.uniform(-0.15, 0.15)
        self.phase = random.uniform(0, math.pi * 2)

    def update(self):
        """更新粒子物理狀態"""
        # 加入微小的混沌正弦擾動 (Turbulence)
        turbulence_x = math.sin(self.life * 10.0 + self.phase) * 0.35
        turbulence_y = math.cos(self.life * 8.0 + self.phase) * 0.2

        self.vx = (self.vx + self.ax + turbulence_x) * self.drag
        self.vy = (self.vy + self.ay + turbulence_y) * self.drag

        self.x += self.vx
        self.y += self.vy

        # 隨生命週期衰減大小與色相漂移
        self.life -= self.decay
        life_ratio = max(0.0, self.life / self.max_life)
        self.size = self.initial_size * (0.2 + 0.8 * life_ratio)
        self.hue = (self.hue + 1.2) % 180  # 霓虹色相旋轉

    def is_alive(self) -> bool:
        return self.life > 0.0 and self.size > 0.5


class ParticleSystem:
    """食指發光粒子系統管理器"""
    def __init__(self, max_particles: int = 500):
        self.particles: list[Particle] = []
        self.max_particles = max_particles
        self.prev_emitter_pos = None
        self.emitter_velocity = np.array([0.0, 0.0])

    def emit(self, x: float, y: float, base_hue: float, count: int = 4, burst_mode: bool = False):
        """
        根據食指位置與移動加速度發射粒子
        """
        current_pos = np.array([x, y], dtype=float)

        if self.prev_emitter_pos is not None:
            # 計算前後幀位移產生的手指速度向量
            raw_vel = current_pos - self.prev_emitter_pos
            # 平滑手指速度
            self.emitter_velocity = self.emitter_velocity * 0.6 + raw_vel * 0.4
        else:
            self.emitter_velocity = np.array([0.0, 0.0])

        self.prev_emitter_pos = current_pos

        speed = float(np.linalg.norm(self.emitter_velocity))

        # 根據手指移動速度動態增加發射數量
        dynamic_count = count
        if burst_mode:
            dynamic_count = count * 6
        elif speed > 15:
            dynamic_count = min(count + int(speed * 0.3), 12)

        for _ in range(dynamic_count):
            if len(self.particles) >= self.max_particles:
                # 移除最老的一顆
                self.particles.pop(0)

            # 粒子噴發速度包含：手指慣性速度 + 隨機擴散速度
            spread_angle = random.uniform(0, 2 * math.pi)
            if burst_mode:
                spread_speed = random.uniform(4.0, 14.0)
                vx = math.cos(spread_angle) * spread_speed
                vy = math.sin(spread_angle) * spread_speed
            else:
                spread_speed = random.uniform(0.8, 3.8)
                # 結合手指慣性 (向後拖曳或揮舞噴濺)
                inertia_factor = 0.45
                vx = -self.emitter_velocity[0] * inertia_factor + math.cos(spread_angle) * spread_speed
                vy = -self.emitter_velocity[1] * inertia_factor + math.sin(spread_angle) * spread_speed

            # 粒子色相在基準色相周圍隨機抖動
            p_hue = (base_hue + random.uniform(-25, 25)) % 180
            p_size = random.uniform(3.5, 8.5) if not burst_mode else random.uniform(5.0, 12.0)
            p_decay = random.uniform(0.015, 0.038) if not burst_mode else random.uniform(0.02, 0.045)

            # 在手指周圍加入微小微量偏差
            px = x + random.uniform(-3, 3)
            py = y + random.uniform(-3, 3)

            self.particles.append(Particle(px, py, vx, vy, p_hue, p_size, life=1.0, decay=p_decay))

    def update(self):
        """更新所有粒子狀態並清理死亡粒子"""
        alive_particles = []
        for p in self.particles:
            p.update()
            if p.is_alive():
                alive_particles.append(p)
        self.particles = alive_particles

    def draw(self, glow_canvas: np.ndarray):
        """
        在發光畫布上渲染多層發光粒子 (多層同心圓模擬 Neon Glow)
        """
        h, w = glow_canvas.shape[:2]

        for p in self.particles:
            ix, iy = int(round(p.x)), int(round(p.y))
            if not (0 <= ix < w and 0 <= iy < h):
                continue

            life_ratio = max(0.0, min(1.0, p.life / p.max_life))
            base_color = hsv_to_bgr(p.hue, 230, 255)
            core_color = (255, 255, 255)  # 白熾核心

            # 發光光暈半徑
            radius = int(max(1, round(p.size)))
            glow_radius_outer = int(radius * 2.8)
            glow_radius_inner = int(radius * 1.5)

            # 外層大光暈 (柔和低亮度)
            outer_color = (int(base_color[0] * 0.35 * life_ratio),
                           int(base_color[1] * 0.35 * life_ratio),
                           int(base_color[2] * 0.35 * life_ratio))
            cv2.circle(glow_canvas, (ix, iy), glow_radius_outer, outer_color, -1, cv2.LINE_AA)

            # 中層霓虹光暈 (鮮豔飽和)
            mid_color = (int(base_color[0] * 0.85 * life_ratio),
                         int(base_color[1] * 0.85 * life_ratio),
                         int(base_color[2] * 0.85 * life_ratio))
            cv2.circle(glow_canvas, (ix, iy), glow_radius_inner, mid_color, -1, cv2.LINE_AA)

            # 核心光點 (高亮白色微縮)
            core_val = int(255 * life_ratio)
            cv2.circle(glow_canvas, (ix, iy), max(1, int(radius * 0.6)), (core_val, core_val, core_val), -1, cv2.LINE_AA)

    def clear(self):
        """清除所有粒子"""
        self.particles.clear()
        self.prev_emitter_pos = None


# =============================================================================
# 3. 迷幻視覺彩繪渲染器 (Trippy Visuals Renderer)
# =============================================================================

class TrippyHandRenderer:
    """負責繪製迷幻霓虹關節、正弦波碎形連線與殘影特效"""
    def __init__(self):
        self.frame_count = 0

    def draw_trippy_hand(self, canvas: np.ndarray, landmarks_px: list[tuple[int, int]], base_hue: float):
        """
        繪製單一手部的迷幻視覺特效
        """
        t = self.frame_count * 0.06

        # ---------------------------------------------------------------------
        # 1. 繪製正弦波動態碎形連線 (Sine-wave Harmonic Connections)
        # ---------------------------------------------------------------------
        for p1_idx, p2_idx in HAND_CONNECTIONS:
            pt1 = np.array(landmarks_px[p1_idx], dtype=float)
            pt2 = np.array(landmarks_px[p2_idx], dtype=float)

            diff = pt2 - pt1
            dist = np.linalg.norm(diff)
            if dist < 1e-4:
                continue

            # 計算垂直於骨架連線的法向量
            normal = np.array([-diff[1], diff[0]]) / dist

            # 連線的動態漸層色彩
            conn_hue = (base_hue + (p1_idx + p2_idx) * 4.5 + math.sin(t) * 15.0) % 180
            conn_color = hsv_to_bgr(conn_hue, 240, 255)
            harmonic_color = hsv_to_bgr((conn_hue + 45) % 180, 200, 240)

            # 正弦碎形採樣點
            segments = max(8, int(dist / 4.0))
            pts_main = []
            pts_harmonic = []

            # 根據時間與距離動態計算振幅
            amplitude = math.sin(t * 1.5 + p1_idx * 0.6) * (dist * 0.14)
            harmonic_amp = math.cos(t * 2.2 + p2_idx * 0.8) * (dist * 0.08)

            for s in range(segments + 1):
                ratio = s / float(segments)
                base_pt = pt1 * (1.0 - ratio) + pt2 * ratio

                # 主波型 (兩端收斂為 0，中間波動最大)
                envelope = math.sin(ratio * math.pi)
                offset1 = normal * (math.sin(ratio * math.pi * 3.0 + t * 2.0) * amplitude * envelope)
                offset2 = normal * (math.sin(ratio * math.pi * 5.0 - t * 3.0) * harmonic_amp * envelope)

                curve_pt1 = base_pt + offset1
                curve_pt2 = base_pt - offset2

                pts_main.append([int(curve_pt1[0]), int(curve_pt1[1])])
                pts_harmonic.append([int(curve_pt2[0]), int(curve_pt2[1])])

            pts_main_np = np.array(pts_main, dtype=np.int32).reshape((-1, 1, 2))
            pts_harmonic_np = np.array(pts_harmonic, dtype=np.int32).reshape((-1, 1, 2))

            # 繪製多層次光暈與諧波細線
            cv2.polylines(canvas, [pts_main_np], False, (int(conn_color[0]*0.4), int(conn_color[1]*0.4), int(conn_color[2]*0.4)), 5, cv2.LINE_AA)
            cv2.polylines(canvas, [pts_main_np], False, conn_color, 2, cv2.LINE_AA)
            cv2.polylines(canvas, [pts_harmonic_np], False, harmonic_color, 1, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # 2. 繪製多層次同心圓霓虹節點 (Concentric Pulsating Joint Orbs)
        # ---------------------------------------------------------------------
        for i, (x, y) in enumerate(landmarks_px):
            node_hue = (base_hue + i * 8.0 + math.cos(t + i) * 20.0) % 180
            node_color = hsv_to_bgr(node_hue, 255, 255)
            comp_color = hsv_to_bgr((node_hue + 90) % 180, 240, 255)

            # 節點脈衝半徑
            pulse = math.sin(t * 3.0 + i * 0.7)
            # 指尖 (4, 8, 12, 16, 20) 加大尺寸
            is_tip = i in (4, 8, 12, 16, 20)
            base_r = 10.0 if is_tip else 6.0
            r = max(3, int(base_r + pulse * 2.5))

            # 層級 1：外圍光暈
            cv2.circle(canvas, (x, y), int(r * 2.2), (int(node_color[0]*0.3), int(node_color[1]*0.3), int(node_color[2]*0.3)), -1, cv2.LINE_AA)

            # 層級 2：次級霓虹環
            cv2.circle(canvas, (x, y), int(r * 1.5), comp_color, 1, cv2.LINE_AA)

            # 層級 3：主飽和圓形
            cv2.circle(canvas, (x, y), r, node_color, -1, cv2.LINE_AA)

            # 層級 4：內部白熾核心
            cv2.circle(canvas, (x, y), max(1, int(r * 0.45)), (255, 255, 255), -1, cv2.LINE_AA)


# =============================================================================
# 4. 手部追蹤包裝器 (MediaPipe Universal Hands Wrapper)
# =============================================================================

class UniversalHandTracker:
    """
    自適應包裝器：相容最新 MediaPipe Tasks API (Python 3.12/3.13) 與 Legacy Solutions API
    """
    def __init__(self, max_num_hands: int = 2):
        self.max_num_hands = max_num_hands
        self.mode = None
        self.detector = None
        self._init_tracker()

    def _init_tracker(self):
        # 1. 嘗試使用經典 Solutions API
        if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands'):
            try:
                self.detector = mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=self.max_num_hands,
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.6
                )
                self.mode = 'solutions'
                print("[系統] 成功載入 MediaPipe Solutions API 模式。")
                return
            except Exception as e:
                print(f"[提示] 初始化 Solutions 失敗，切換至 Tasks API: {e}")

        # 2. 嘗試使用現代 Tasks API
        try:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
            if not os.path.exists(model_path):
                print("[下載] 正在從 Google 官方下載手部追蹤模型 hand_landmarker.task ...")
                url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
                urllib.request.urlretrieve(url, model_path)
                print("[下載] 模型下載完成！")

            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                num_hands=self.max_num_hands,
                min_hand_detection_confidence=0.6,
                min_hand_presence_confidence=0.6,
                min_tracking_confidence=0.6
            )
            self.detector = vision.HandLandmarker.create_from_options(options)
            self.mode = 'tasks'
            print("[系統] 成功載入 MediaPipe Tasks API 模式 (hand_landmarker.task)。")
        except Exception as e:
            print(f"[錯誤] 無法初始化 MediaPipe 追蹤器: {e}")
            raise RuntimeError("MediaPipe 初始化失敗，請檢查環境設定。")

    def process(self, frame_bgr: np.ndarray) -> list[list[tuple[int, int]]]:
        """
        傳入 BGR 畫面，返回所有偵測到手部的 21 節點像素座標串列 [[(x0, y0), ...(x20, y20)], ...]
        """
        h, w = frame_bgr.shape[:2]
        all_hands = []

        if self.mode == 'solutions':
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            results = self.detector.process(frame_rgb)
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    pts = []
                    for lm in hand_landmarks.landmark:
                        px = int(lm.x * w)
                        py = int(lm.y * h)
                        pts.append((px, py))
                    all_hands.append(pts)

        elif self.mode == 'tasks':
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            results = self.detector.detect(mp_image)
            if results.hand_landmarks:
                for hand_lms in results.hand_landmarks:
                    pts = []
                    for lm in hand_lms:
                        px = int(lm.x * w)
                        py = int(lm.y * h)
                        pts.append((px, py))
                    all_hands.append(pts)

        return all_hands


# =============================================================================
# 5. 主應用程式主迴圈 (Main Application Execution)
# =============================================================================

def draw_hud(frame: np.ndarray, fps: float, particle_count: int, hand_count: int, dark_mode: bool, trail_level: str):
    """繪製 Cyberpunk / Neon 風格的 HUD 資訊介面"""
    h, w = frame.shape[:2]

    # 半透明 HUD 背景飾條
    overlay = frame.copy()
    cv2.rectangle(overlay, (15, 15), (320, 165), (10, 10, 25), -1)
    cv2.rectangle(overlay, (15, 15), (320, 165), (180, 50, 240), 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    # 標題與資訊
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, "TRIPPY HAND TRACKER", (28, 42), font, 0.62, (0, 240, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, f"FPS: {fps:.1f}", (28, 70), font, 0.5, (0, 255, 150), 1, cv2.LINE_AA)
    cv2.putText(frame, f"Hands: {hand_count} | Particles: {particle_count}", (28, 92), font, 0.48, (220, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(frame, f"Mode: {'Dark Neon' if dark_mode else 'Camera Blend'} | Trail: {trail_level}", (28, 114), font, 0.46, (255, 180, 50), 1, cv2.LINE_AA)

    # 快捷鍵提示
    cv2.putText(frame, "[B]Bg  [T]Trail  [P]Burst  [C]Clear  [S]Shot  [Q]Quit", (28, 146), font, 0.38, (160, 160, 200), 1, cv2.LINE_AA)


def main():
    print("=" * 65)
    print(" 啟動 迷幻風格 (Trippy) + 物理發光粒子 MediaPipe 手部追蹤系統")
    print("=" * 65)

    # 開啟攝影機
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[錯誤] 無法開啟預設鏡頭 (ID 0)，請確認攝影機權限或連線。")
        return

    # 設定鏡頭解析度
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    tracker = UniversalHandTracker(max_num_hands=2)
    particle_system = ParticleSystem(max_particles=700)
    trippy_renderer = TrippyHandRenderer()

    # 殘影緩衝區 (Feedback Buffer)
    feedback_buffer = None

    # 控制參數
    dark_mode = False             # 是否使用全黑極致迷幻背景
    trail_modes = [
        ("Short", 0.72),
        ("Medium", 0.85),
        ("Dreamy Long", 0.93)
    ]
    trail_idx = 1
    burst_trigger = False

    fps_smooth = 30.0
    prev_time = time.time()
    frame_idx = 0

    print("\n[操作提示]")
    print("  - Q 或 ESC: 退出程式")
    print("  - B: 切換 純黑霓虹背景 / 鏡頭實景背景")
    print("  - T: 切換 殘影長度 (Short / Medium / Dreamy Long)")
    print("  - P: 在食指觸發超新星粒子爆破 (Supernova Burst)")
    print("  - C: 清除所有粒子與殘影")
    print("  - S: 儲存當前畫面截圖\n")

    window_name = "Trippy Hands - Psychedelic Particle Experience"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[警告] 影像讀取失敗，正在重試...")
            time.sleep(0.05)
            continue

        # 鏡像翻轉，符合人體直覺操作
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        # 初始化殘影緩衝區
        if feedback_buffer is None or feedback_buffer.shape != frame.shape:
            feedback_buffer = np.zeros_like(frame, dtype=np.float32)

        curr_time = time.time()
        dt = max(1e-4, curr_time - prev_time)
        prev_time = curr_time
        fps_smooth = fps_smooth * 0.9 + (1.0 / dt) * 0.1
        frame_idx += 1
        trippy_renderer.frame_count = frame_idx

        # 基礎全域動態色彩色相循環 (0 ~ 179)
        global_base_hue = (frame_idx * 1.6) % 180

        # 手部追蹤偵測
        detected_hands = tracker.process(frame)

        # 建立當前幀迷幻繪圖專用圖層
        trippy_layer = np.zeros_like(frame)
        glow_particle_layer = np.zeros_like(frame)

        # 處理各隻手部
        index_tip_positions = []
        for hand_i, landmarks in enumerate(detected_hands):
            # 每隻手有些微色相偏移
            hand_hue = (global_base_hue + hand_i * 60) % 180
            trippy_renderer.draw_trippy_hand(trippy_layer, landmarks, hand_hue)

            # 抓取食指尖端節點 8 (Landmark 8: INDEX_FINGER_TIP)
            if len(landmarks) > 8:
                tip_x, tip_y = landmarks[8]
                index_tip_positions.append((tip_x, tip_y, hand_hue))

        # 粒子發射與更新
        if index_tip_positions:
            for tip_x, tip_y, tip_hue in index_tip_positions:
                particle_system.emit(tip_x, tip_y, tip_hue, count=4, burst_mode=burst_trigger)
        else:
            particle_system.prev_emitter_pos = None

        if burst_trigger:
            burst_trigger = False  # 觸發一次後重置

        # 更新與繪製粒子
        particle_system.update()
        particle_system.draw(glow_particle_layer)

        # 合併當前幀的動態圖層 (手部迷幻骨架 + 發光粒子)
        current_trippy_art = cv2.add(trippy_layer, glow_particle_layer)

        # ---------------------------------------------------------------------
        # 殘影緩衝區處理 (Feedback Buffer with Decay & Space Drift)
        # ---------------------------------------------------------------------
        decay_factor = trail_modes[trail_idx][1]

        # 空間輕微縮放漂移感 (Feedback Warp / Zoom Distortion)
        # 將 feedback 緩衝區微微放大並衰減，產生向外擴散的視覺穿梭感
        M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), 0.15, 1.006)
        feedback_buffer = cv2.warpAffine(feedback_buffer, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

        # 衰減殘影並疊加當前幀迷幻藝術
        feedback_buffer = feedback_buffer * decay_factor + current_trippy_art.astype(np.float32)
        feedback_buffer = np.clip(feedback_buffer, 0, 255)
        feedback_display = feedback_buffer.astype(np.uint8)

        # ---------------------------------------------------------------------
        # 主畫面合成 (Background Blending)
        # ---------------------------------------------------------------------
        if dark_mode:
            # 純黑背景模式：極致突顯霓虹發光與殘影
            dark_bg = (frame * 0.08).astype(np.uint8)  # 微暗底色保留輪廓
            final_frame = cv2.add(dark_bg, feedback_display)
        else:
            # 鏡頭實景模式：將殘影與發光特效透過加權混合融入實景
            # 使用 cv2.addWeighted 疊加實景與迷幻特效
            dimmed_cam = (frame * 0.75).astype(np.uint8)
            final_frame = cv2.add(dimmed_cam, feedback_display)

        # 繪製 HUD
        draw_hud(final_frame, fps_smooth, len(particle_system.particles), len(detected_hands), dark_mode, trail_modes[trail_idx][0])

        cv2.imshow(window_name, final_frame)

        # ---------------------------------------------------------------------
        # 鍵盤互動事件處理 (Keyboard Events)
        # ---------------------------------------------------------------------
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # Q or ESC
            print("[退出] 使用者終止程式。")
            break
        elif key == ord('b') or key == ord('B'):  # 切換背景模式
            dark_mode = not dark_mode
            print(f"[模式切換] 背景模式: {'純黑霓虹 (Dark Neon)' if dark_mode else '相機疊加 (Camera Blend)'}")
        elif key == ord('t') or key == ord('T'):  # 切換殘影等級
            trail_idx = (trail_idx + 1) % len(trail_modes)
            print(f"[模式切換] 殘影強度: {trail_modes[trail_idx][0]}")
        elif key == ord('p') or key == ord('P'):  # 粒子大爆發
            burst_trigger = True
            print("[特效] 觸發粒子爆發 (Burst)！")
        elif key == ord('c') or key == ord('C'):  # 清除殘影與粒子
            particle_system.clear()
            feedback_buffer = np.zeros_like(frame, dtype=np.float32)
            print("[清除] 殘影緩衝區與粒子已重置。")
        elif key == ord('s') or key == ord('S'):  # 螢幕截圖
            screenshot_name = f"trippy_hand_capture_{int(time.time())}.png"
            cv2.imwrite(screenshot_name, final_frame)
            print(f"[截圖] 已儲存截圖至: {screenshot_name}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
