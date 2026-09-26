"""
=============================================================================
🔮 迷幻風格 (Trippy) + 物理發光粒子 + 三大特色模式 MediaPipe 手部追蹤系統
Psychedelic Trippy Hand Tracker with Multi-Mode Interactive VFX
=============================================================================
三大特色模式：
  1. 🌌 模式一【時空扭曲蟲洞 (Space Warp & Liquid Distortion)】
     - 手部關節作為引力透鏡與液態漩渦中心，產生即時空間扭曲與 RGB 色散分光。
  2. 🚀 模式二【手勢控制宇宙發散 (Gesture Cosmic Expansion)】
     - 神聖幾何與超空間粒子發散：張開手全速爆發、握緊減速慢動作、握拳時間凍結。
  3. ⚡ 模式三【奇異博士 / 鋼鐵人 掌心旋轉全息魔法陣 (Holo Arc Mandala)】
     - 追蹤掌心中心點 (節點 0, 5, 17)，張開手即展開多層順逆雙向旋轉魔法陣與能量電弧。

特色視覺：
  - 捨棄抖動曲線，全面採用極致平滑的【霓虹雷射光束 (Smooth Laser Glow)】與呼吸節點。
  - 食指尖端具備真實重力、加速度慣性與發光光暈之物理粒子系統。
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

# 載入 MediaPipe
try:
    import mediapipe as mp
except ImportError:
    print("[錯誤] 未檢測到 mediapipe 套件，請先執行: pip install mediapipe opencv-python numpy")
    sys.exit(1)


# =============================================================================
# 1. 顏色與數學工具函式 (Color & Math Utilities)
# =============================================================================

def hsv_to_bgr(h: float, s: float = 255.0, v: float = 255.0) -> tuple[int, int, int]:
    """將 HSV (H:0~179, S:0~255, V:0~255) 轉換為 OpenCV BGR (B, G, R)"""
    h_c = int(h % 180)
    s_c = int(max(0, min(255, s)))
    v_c = int(max(0, min(255, v)))
    pixel = cv2.cvtColor(np.uint8([[[h_c, s_c, v_c]]]), cv2.COLOR_HSV2BGR)[0][0]
    return int(pixel[0]), int(pixel[1]), int(pixel[2])


# 手部 21 骨架標準連線
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
    # 掌部橫向骨幹
    (5, 9), (9, 13), (13, 17)
]


# =============================================================================
# 2. 手勢與姿態分析引擎 (Hand Gesture & Pose Engine)
# =============================================================================

class HandPose:
    """單一手部的姿態、幾何中心與手勢分析資料結構"""
    def __init__(self, landmarks_px: list[tuple[int, int]]):
        self.landmarks = landmarks_px
        self.wrist = np.array(landmarks_px[0], dtype=float)
        self.index_mcp = np.array(landmarks_px[5], dtype=float)
        self.middle_mcp = np.array(landmarks_px[9], dtype=float)
        self.pinky_mcp = np.array(landmarks_px[17], dtype=float)

        # 掌心中心點 (基於 0, 5, 17 節點的幾何質心)
        self.palm_center = (self.wrist + self.index_mcp + self.pinky_mcp) / 3.0
        self.palm_center_pt = (int(round(self.palm_center[0])), int(round(self.palm_center[1])))

        # 掌心尺度 (以手腕到中指指根距離為基準)
        self.palm_size = max(15.0, float(np.linalg.norm(self.middle_mcp - self.wrist)))

        # 手掌指向角度 (手腕朝向中指根部)
        direction = self.middle_mcp - self.wrist
        self.palm_angle = math.atan2(direction[1], direction[0])

        # 計算 5 根手指開合度 (Fingertip to Palm Center Ratio)
        tip_indices = [4, 8, 12, 16, 20]
        distances = []
        for idx in tip_indices:
            tip = np.array(landmarks_px[idx], dtype=float)
            dist = np.linalg.norm(tip - self.palm_center)
            distances.append(dist)

        avg_tip_dist = np.mean(distances)
        # 正規化開合度 (0.0 緊閉拳頭 ~ 1.0 完全張開)
        # 拳頭時 avg_tip_dist 約為 0.55 * palm_size；張開時約 1.45 * palm_size
        raw_openness = (avg_tip_dist / self.palm_size - 0.55) / 0.90
        self.openness = float(np.clip(raw_openness, 0.0, 1.0))

        # 手勢分類
        if self.openness < 0.28:
            self.gesture_state = "FIST"          # 握拳 (停住)
        elif self.openness > 0.65:
            self.gesture_state = "OPEN"          # 張開 (全速發散)
        else:
            self.gesture_state = "CLOSING"       # 半握/握緊中 (減速)


# =============================================================================
# 3. 物理發光粒子系統 (Physics-based Glowing Particle System)
# =============================================================================

class Particle:
    """單一物理發光粒子"""
    def __init__(self, x: float, y: float, vx: float, vy: float, hue: float, size: float = 6.0, life: float = 1.0, decay: float = 0.028):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.ax = 0.0
        self.ay = 0.28           # 重力加速度 (Gravity)
        self.hue = float(hue)
        self.initial_size = float(size)
        self.size = float(size)
        self.life = float(life)
        self.max_life = float(life)
        self.decay = float(decay)
        self.drag = 0.965        # 空氣阻力係數 (Damping)
        self.phase = random.uniform(0, math.pi * 2)

    def update(self, speed_mult: float = 1.0):
        if speed_mult <= 1e-4:
            return  # 凍結時間

        turb_x = math.sin(self.life * 8.0 + self.phase) * 0.35 * speed_mult
        turb_y = math.cos(self.life * 6.0 + self.phase) * 0.20 * speed_mult

        self.vx = (self.vx + self.ax + turb_x) * (self.drag ** speed_mult)
        self.vy = (self.vy + self.ay * speed_mult + turb_y) * (self.drag ** speed_mult)

        self.x += self.vx * speed_mult
        self.y += self.vy * speed_mult

        self.life -= self.decay * speed_mult
        ratio = max(0.0, self.life / self.max_life)
        self.size = self.initial_size * (0.2 + 0.8 * ratio)
        self.hue = (self.hue + 1.2 * speed_mult) % 180

    def is_alive(self) -> bool:
        return self.life > 0.0 and self.size > 0.5


class ParticleSystem:
    """食指尖發光粒子系統"""
    def __init__(self, max_particles: int = 600):
        self.particles: list[Particle] = []
        self.max_particles = max_particles
        self.prev_emitter_pos = None
        self.emitter_velocity = np.array([0.0, 0.0])

    def emit(self, x: float, y: float, base_hue: float, count: int = 4, burst_mode: bool = False, speed_mult: float = 1.0):
        curr_pos = np.array([x, y], dtype=float)
        if self.prev_emitter_pos is not None:
            raw_vel = curr_pos - self.prev_emitter_pos
            self.emitter_velocity = self.emitter_velocity * 0.6 + raw_vel * 0.4
        else:
            self.emitter_velocity = np.array([0.0, 0.0])
        self.prev_emitter_pos = curr_pos

        speed = float(np.linalg.norm(self.emitter_velocity))
        dynamic_count = count
        if burst_mode:
            dynamic_count = count * 7
        elif speed > 15:
            dynamic_count = min(count + int(speed * 0.3), 12)

        # 握拳凍結時降低發射數量
        if speed_mult < 0.1 and not burst_mode:
            dynamic_count = 1

        for _ in range(dynamic_count):
            if len(self.particles) >= self.max_particles:
                self.particles.pop(0)

            angle = random.uniform(0, 2 * math.pi)
            if burst_mode:
                sp = random.uniform(4.0, 14.0)
                vx = math.cos(angle) * sp
                vy = math.sin(angle) * sp
            else:
                sp = random.uniform(0.8, 3.5)
                vx = -self.emitter_velocity[0] * 0.4 + math.cos(angle) * sp
                vy = -self.emitter_velocity[1] * 0.4 + math.sin(angle) * sp

            p_hue = (base_hue + random.uniform(-25, 25)) % 180
            p_size = random.uniform(4.0, 8.5) if not burst_mode else random.uniform(6.0, 13.0)
            p_decay = random.uniform(0.018, 0.038)
            px = x + random.uniform(-3, 3)
            py = y + random.uniform(-3, 3)

            self.particles.append(Particle(px, py, vx, vy, p_hue, p_size, life=1.0, decay=p_decay))

    def update(self, speed_mult: float = 1.0):
        alive = []
        for p in self.particles:
            p.update(speed_mult)
            if p.is_alive():
                alive.append(p)
        self.particles = alive

    def draw(self, canvas: np.ndarray):
        h, w = canvas.shape[:2]
        for p in self.particles:
            ix, iy = int(round(p.x)), int(round(p.y))
            if not (0 <= ix < w and 0 <= iy < h):
                continue

            ratio = max(0.0, min(1.0, p.life / p.max_life))
            base_col = hsv_to_bgr(p.hue, 240, 255)
            r = int(max(1, round(p.size)))

            # 外層光暈
            out_col = (int(base_col[0] * 0.35 * ratio), int(base_col[1] * 0.35 * ratio), int(base_col[2] * 0.35 * ratio))
            cv2.circle(canvas, (ix, iy), int(r * 2.8), out_col, -1, cv2.LINE_AA)

            # 中層霓虹
            mid_col = (int(base_col[0] * 0.85 * ratio), int(base_col[1] * 0.85 * ratio), int(base_col[2] * 0.85 * ratio))
            cv2.circle(canvas, (ix, iy), int(r * 1.5), mid_col, -1, cv2.LINE_AA)

            # 白熾核心
            core_val = int(255 * ratio)
            cv2.circle(canvas, (ix, iy), max(1, int(r * 0.6)), (core_val, core_val, core_val), -1, cv2.LINE_AA)

    def clear(self):
        self.particles.clear()
        self.prev_emitter_pos = None


# =============================================================================
# 4. 平滑霓虹雷射手部骨架渲染器 (Smooth Laser Glow Skeleton)
# =============================================================================

class SmoothLaserHandRenderer:
    """平滑高質感霓虹雷射骨架（無抖動正弦曲線）"""
    @staticmethod
    def draw(canvas: np.ndarray, landmarks_px: list[tuple[int, int]], base_hue: float, time_sec: float):
        # 1. 繪製骨架雷射光束連線 (平滑多層光暈)
        for p1_idx, p2_idx in HAND_CONNECTIONS:
            pt1 = landmarks_px[p1_idx]
            pt2 = landmarks_px[p2_idx]

            bone_hue = (base_hue + (p1_idx + p2_idx) * 4.0) % 180
            glow_color = hsv_to_bgr(bone_hue, 240, 255)
            core_color = hsv_to_bgr((bone_hue + 15) % 180, 80, 255)

            # 層次 1: 寬光暈
            cv2.line(canvas, pt1, pt2, (int(glow_color[0]*0.25), int(glow_color[1]*0.25), int(glow_color[2]*0.25)), 8, cv2.LINE_AA)
            # 層次 2: 霓虹主光束
            cv2.line(canvas, pt1, pt2, glow_color, 3, cv2.LINE_AA)
            # 層次 3: 白熾雷射核心
            cv2.line(canvas, pt1, pt2, core_color, 1, cv2.LINE_AA)

        # 2. 繪製多層同心光環節點 (Concentric Pulsating Orbs)
        for i, (x, y) in enumerate(landmarks_px):
            node_hue = (base_hue + i * 8.0) % 180
            node_color = hsv_to_bgr(node_hue, 255, 255)
            comp_color = hsv_to_bgr((node_hue + 90) % 180, 240, 255)

            pulse = math.sin(time_sec * 4.0 + i * 0.6)
            is_tip = i in (4, 8, 12, 16, 20)
            base_r = 8.5 if is_tip else 5.0
            r = max(2, int(base_r + pulse * 2.0))

            # 外層光暈
            cv2.circle(canvas, (x, y), int(r * 2.4), (int(node_color[0]*0.3), int(node_color[1]*0.3), int(node_color[2]*0.3)), -1, cv2.LINE_AA)
            # 外層裝飾環
            cv2.circle(canvas, (x, y), int(r * 1.6), comp_color, 1, cv2.LINE_AA)
            # 節點本體
            cv2.circle(canvas, (x, y), r, node_color, -1, cv2.LINE_AA)
            # 白熾核心
            cv2.circle(canvas, (x, y), max(1, int(r * 0.45)), (255, 255, 255), -1, cv2.LINE_AA)


# =============================================================================
# 5. 模式一：時空扭曲蟲洞風 (Mode 1: Space Warp & Liquid Distortion)
# =============================================================================

class SpaceWarpDistortionEffect:
    """手部節點產生液態空間扭曲與 RGB 色散分光"""
    def __init__(self):
        self.grid_x = None
        self.grid_y = None
        self.prev_shape = None

    def _init_grids(self, h: int, w: int):
        if self.prev_shape != (h, w):
            self.grid_x, self.grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
            self.prev_shape = (h, w)

    def apply_warp(self, frame: np.ndarray, hands_pose: list[HandPose], time_sec: float) -> np.ndarray:
        h, w = frame.shape[:2]
        self._init_grids(h, w)

        if not hands_pose:
            return frame

        map_x = self.grid_x.copy()
        map_y = self.grid_y.copy()

        # 針對手部關鍵節點施加局部空間扭曲場 (Swirl + Radial Lens)
        for hand in hands_pose:
            # 使用掌心與指尖共 6 個焦點產生漩渦
            focal_points = [hand.palm_center] + [np.array(hand.landmarks[idx], dtype=float) for idx in [4, 8, 12, 16, 20]]
            for f_idx, pt in enumerate(focal_points):
                cx, cy = pt[0], pt[1]
                radius = hand.palm_size * (1.1 if f_idx == 0 else 0.7)
                r_sq = radius * radius

                min_x = max(0, int(cx - radius))
                max_x = min(w, int(cx + radius + 1))
                min_y = max(0, int(cy - radius))
                max_y = min(h, int(cy + radius + 1))

                if min_x >= max_x or min_y >= max_y:
                    continue

                dx = map_x[min_y:max_y, min_x:max_x] - cx
                dy = map_y[min_y:max_y, min_x:max_x] - cy
                dist_sq = dx * dx + dy * dy

                mask = dist_sq < r_sq
                if not np.any(mask):
                    continue

                dist = np.sqrt(dist_sq) + 1e-5
                norm_r = dist / radius
                # 扭曲強度係數 (含波動)
                warp_strength = (1.0 - norm_r) ** 2
                swirl_angle = (1.2 + 0.3 * math.sin(time_sec * 3.0 + f_idx)) * warp_strength

                # 旋轉矩陣變換
                cos_a = np.cos(swirl_angle)
                sin_a = np.sin(swirl_angle)

                # 徑向縮放透鏡
                radial_push = 1.0 - 0.28 * np.sin(norm_r * math.pi) * warp_strength

                new_dx = (dx * cos_a - dy * sin_a) * radial_push
                new_dy = (dx * sin_a + dy * cos_a) * radial_push

                map_x[min_y:max_y, min_x:max_x] = np.where(mask, cx + new_dx, map_x[min_y:max_y, min_x:max_x])
                map_y[min_y:max_y, min_x:max_x] = np.where(mask, cy + new_dy, map_y[min_y:max_y, min_x:max_x])

        # 色散分光效果 (Chromatic Aberration)：RGB 通道輕微位移重構
        # Blue channel
        b_warped = cv2.remap(frame[:, :, 0], map_x + 1.5, map_y + 1.5, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # Green channel (基準)
        g_warped = cv2.remap(frame[:, :, 1], map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # Red channel
        r_warped = cv2.remap(frame[:, :, 2], map_x - 1.5, map_y - 1.5, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

        warped_frame = cv2.merge([b_warped, g_warped, r_warped])
        return warped_frame


# =============================================================================
# 6. 模式二：手勢控制宇宙發散 (Mode 2: Gesture Cosmic Expansion)
# =============================================================================

class CosmicExpansionTunnel:
    """動態神聖幾何與超光速通道：張開全速發散、握緊減速、握拳時間凍結"""
    def __init__(self, num_rings: int = 14):
        self.num_rings = num_rings
        self.ring_depths = [i / float(num_rings) for i in range(num_rings)]
        self.speed_smooth = 1.0
        self.rotation = 0.0

    def update_and_draw(self, canvas: np.ndarray, hands_pose: list[HandPose], time_sec: float, base_hue: float) -> tuple[float, str]:
        h, w = canvas.shape[:2]
        center_x, center_y = w // 2, h // 2

        # 根據手勢計算目標速度
        if hands_pose:
            # 取第一隻手做主控，若有兩隻手取平均
            avg_openness = float(np.mean([h_p.openness for h_p in hands_pose]))
            gesture_label = hands_pose[0].gesture_state

            if avg_openness < 0.28:
                target_speed = 0.0      # 握拳：時間凍結
                state_text = "FIST [TIME FREEZE]"
            elif avg_openness > 0.65:
                # 張開手：高速發散 (1.6 ~ 2.6x)
                target_speed = 1.6 + (avg_openness - 0.65) / 0.35 * 1.0
                state_text = "OPEN [HYPER EXPAND]"
            else:
                # 握緊中：減速慢動作 (0.15 ~ 0.6x)
                target_speed = 0.15 + (avg_openness - 0.28) / 0.37 * 0.45
                state_text = "CLOSING [SLOW MOTION]"

            # 焦點可移向掌心
            center_x = int(round(hands_pose[0].palm_center[0]))
            center_y = int(round(hands_pose[0].palm_center[1]))
        else:
            target_speed = 0.8
            state_text = "IDLE [STANDBY]"

        # 平滑過渡速度 (Lerp)
        self.speed_smooth = self.speed_smooth * 0.85 + target_speed * 0.15
        self.rotation += 0.025 * self.speed_smooth

        # 更新並繪製神聖幾何通道層次
        max_dim = math.hypot(w, h)
        for i in range(self.num_rings):
            # 推進深度
            self.ring_depths[i] += 0.014 * self.speed_smooth
            if self.ring_depths[i] > 1.0:
                self.ring_depths[i] -= 1.0

            z = self.ring_depths[i]
            # 深度映射到指數擴散半徑
            radius = (z ** 2.2) * (max_dim * 0.65)
            if radius < 3.0:
                continue

            ring_hue = (base_hue + i * 12.0 + z * 60.0) % 180
            color = hsv_to_bgr(ring_hue, 230, 255)
            alpha_ratio = math.sin(z * math.pi)

            glow_col = (int(color[0] * alpha_ratio * 0.7), int(color[1] * alpha_ratio * 0.7), int(color[2] * alpha_ratio * 0.7))
            line_col = (int(color[0] * alpha_ratio), int(color[1] * alpha_ratio), int(color[2] * alpha_ratio))

            # 繪製幾何同心多邊形（六角星與神聖幾何外框）
            sides = 6 if i % 2 == 0 else 8
            poly_pts = []
            rot_offset = self.rotation * (1.0 if i % 2 == 0 else -1.2) + i * 0.3
            for s in range(sides):
                angle = rot_offset + s * (2 * math.pi / sides)
                px = int(center_x + math.cos(angle) * radius)
                py = int(center_y + math.sin(angle) * radius)
                poly_pts.append([px, py])

            poly_arr = np.array(poly_pts, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(canvas, [poly_arr], True, glow_col, 4, cv2.LINE_AA)
            cv2.polylines(canvas, [poly_arr], True, line_col, 1, cv2.LINE_AA)

            # 同心圓環
            cv2.circle(canvas, (center_x, center_y), int(radius), glow_col, 1, cv2.LINE_AA)

        # 若握拳凍結，在手心繪製凝聚晶體核心
        if hands_pose and self.speed_smooth < 0.2:
            freeze_glow = hsv_to_bgr((base_hue + 90) % 180, 255, 255)
            cv2.circle(canvas, (center_x, center_y), int(hands_pose[0].palm_size * 0.45), freeze_glow, 2, cv2.LINE_AA)
            cv2.circle(canvas, (center_x, center_y), int(hands_pose[0].palm_size * 0.25), (255, 255, 255), -1, cv2.LINE_AA)

        return self.speed_smooth, state_text


# =============================================================================
# 7. 模式三：奇異博士 / 鋼鐵人 掌心旋轉全息魔法陣 (Mode 3: Holo Arc Mandala)
# =============================================================================

class HoloArcMandalaRenderer:
    """追蹤掌心中心點 (0, 5, 17)，張開手合成旋轉魔法陣與全息能量光環"""
    def __init__(self):
        self.rot_clockwise = 0.0
        self.rot_counter = 0.0

    def draw_mandala(self, canvas: np.ndarray, hand: HandPose, time_sec: float, base_hue: float):
        # 僅在手掌張開度 > 0.35 時展開魔法陣
        if hand.openness < 0.35:
            # 握拳時僅顯示掌心凝聚微光
            cx, cy = hand.palm_center_pt
            r = int(hand.palm_size * 0.2)
            cv2.circle(canvas, (cx, cy), r * 2, (100, 100, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, (cx, cy), r, (255, 255, 255), -1, cv2.LINE_AA)
            return

        # 展開係數 (0.0 ~ 1.0)
        expand_ratio = (hand.openness - 0.35) / 0.65
        cx, cy = hand.palm_center_pt
        base_r = hand.palm_size * 1.5 * expand_ratio

        self.rot_clockwise += 0.035
        self.rot_counter -= 0.05

        # 魔法陣色彩 (奇異博士金橙色 / 鋼鐵人全息青藍色混合)
        mandala_hue = (base_hue + 30) % 180
        col_primary = hsv_to_bgr(mandala_hue, 240, 255)
        col_secondary = hsv_to_bgr((mandala_hue + 40) % 180, 200, 255)
        col_arc = (255, 240, 150)  # 高光能量色

        # ---------------------------------------------------------------------
        # 1. 外層符文齒輪環 (Outer Runic Gear Ring)
        # ---------------------------------------------------------------------
        r_outer = int(base_r)
        cv2.circle(canvas, (cx, cy), r_outer, col_primary, 2, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), int(r_outer * 1.06), (int(col_primary[0]*0.4), int(col_primary[1]*0.4), int(col_primary[2]*0.4)), 4, cv2.LINE_AA)

        # 外環刻度齒牙 (12 個刻度)
        for i in range(12):
            ang = self.rot_clockwise + i * (2 * math.pi / 12)
            p_in = (int(cx + math.cos(ang) * (r_outer * 0.94)), int(cy + math.sin(ang) * (r_outer * 0.94)))
            p_out = (int(cx + math.cos(ang) * (r_outer * 1.06)), int(cy + math.sin(ang) * (r_outer * 1.06)))
            cv2.line(canvas, p_in, p_out, col_secondary, 2, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # 2. 中層幾何八芒星法陣 (Interlocking Octagram Mandala)
        # ---------------------------------------------------------------------
        r_mid = int(base_r * 0.72)
        cv2.circle(canvas, (cx, cy), r_mid, col_secondary, 1, cv2.LINE_AA)

        # 兩個交錯旋轉正方形 (八芒星)
        for sq in range(2):
            sq_pts = []
            offset = self.rot_counter + sq * (math.pi / 4)
            for s in range(4):
                ang = offset + s * (math.pi / 2)
                px = int(cx + math.cos(ang) * r_mid)
                py = int(cy + math.sin(ang) * r_mid)
                sq_pts.append([px, py])
                # 在頂點繪製發光法力節點
                cv2.circle(canvas, (px, py), 4, col_arc, -1, cv2.LINE_AA)
            sq_arr = np.array(sq_pts, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(canvas, [sq_arr], True, col_primary, 2, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # 3. 內層鋼鐵人全息刻度環 (Iron Man Tech HUD Rings)
        # ---------------------------------------------------------------------
        r_inner = int(base_r * 0.42)
        cv2.circle(canvas, (cx, cy), r_inner, col_arc, 1, cv2.LINE_AA)

        # 4 象限 HUD 弧形儀表
        for quad in range(4):
            start_deg = int(math.degrees(self.rot_clockwise * 1.5) + quad * 90 + 10) % 360
            end_deg = (start_deg + 60) % 360
            cv2.ellipse(canvas, (cx, cy), (int(r_inner * 0.8), int(r_inner * 0.8)), 0, start_deg, end_deg, col_secondary, 2, cv2.LINE_AA)

        # 十字鎖定準星
        cross_len = int(r_inner * 0.5)
        cv2.line(canvas, (cx - cross_len, cy), (cx + cross_len, cy), (255, 255, 255), 1, cv2.LINE_AA)
        cv2.line(canvas, (cx, cy - cross_len), (cx, cy + cross_len), (255, 255, 255), 1, cv2.LINE_AA)

        # ---------------------------------------------------------------------
        # 4. 掌心超新星能量源與閃爍電弧 (Core Reactor & Arc Lightning)
        # ---------------------------------------------------------------------
        core_r = max(4, int(base_r * 0.16))
        # 掌心發光光暈
        cv2.circle(canvas, (cx, cy), core_r * 3, (int(col_primary[0]*0.5), int(col_primary[1]*0.5), int(col_primary[2]*0.5)), -1, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), core_r * 2, col_secondary, -1, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), core_r, (255, 255, 255), -1, cv2.LINE_AA)

        # 隨機射出的電弧火花 (Arc Lightning)
        for _ in range(3):
            arc_ang = random.uniform(0, 2 * math.pi)
            arc_len = random.uniform(r_inner, r_outer)
            mid_ang = arc_ang + random.uniform(-0.2, 0.2)
            mid_len = arc_len * 0.5

            p0 = (cx, cy)
            p1 = (int(cx + math.cos(mid_ang) * mid_len), int(cy + math.sin(mid_ang) * mid_len))
            p2 = (int(cx + math.cos(arc_ang) * arc_len), int(cy + math.sin(arc_ang) * arc_len))

            cv2.line(canvas, p0, p1, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.line(canvas, p1, p2, col_arc, 1, cv2.LINE_AA)


# =============================================================================
# 8. 手部追蹤核心封裝 (MediaPipe Universal Hands Wrapper)
# =============================================================================

class UniversalHandTracker:
    """自動相容最新 MediaPipe Tasks API (Python 3.12/3.13) 與 Legacy Solutions API"""
    def __init__(self, max_num_hands: int = 2):
        self.max_num_hands = max_num_hands
        self.mode = None
        self.detector = None
        self._init_tracker()

    def _init_tracker(self):
        # 1. 嘗試 Legacy Solutions API
        if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'hands'):
            try:
                self.detector = mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=self.max_num_hands,
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.6
                )
                self.mode = 'solutions'
                print("[系統] 載入 MediaPipe Solutions API 模式。")
                return
            except Exception:
                pass

        # 2. 嘗試現代 Tasks API
        try:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_landmarker.task")
            if not os.path.exists(model_path):
                print("[下載] 正在從 Google 下載 hand_landmarker.task 模型...")
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
            print("[系統] 載入 MediaPipe Tasks API 模式 (hand_landmarker.task)。")
        except Exception as e:
            print(f"[錯誤] 無法初始化 MediaPipe: {e}")
            raise RuntimeError("MediaPipe 初始化失敗")

    def process(self, frame_bgr: np.ndarray) -> list[HandPose]:
        h, w = frame_bgr.shape[:2]
        poses = []

        if self.mode == 'solutions':
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            res = self.detector.process(rgb)
            if res.multi_hand_landmarks:
                for hl in res.multi_hand_landmarks:
                    pts = [(int(lm.x * w), int(lm.y * h)) for lm in hl.landmark]
                    poses.append(HandPose(pts))
        elif self.mode == 'tasks':
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = self.detector.detect(mp_img)
            if res.hand_landmarks:
                for hl in res.hand_landmarks:
                    pts = [(int(lm.x * w), int(lm.y * h)) for lm in hl]
                    poses.append(HandPose(pts))

        return poses


# =============================================================================
# 9. 主應用程式主迴圈 (Main Application Execution)
# =============================================================================

MODES = [
    ("1. 空間扭曲蟲洞 (Space Warp)", "Space Warp"),
    ("2. 宇宙手勢發散 (Cosmic Expand)", "Cosmic Expand"),
    ("3. 奇異博士/鋼鐵人 魔法陣 (Holo Arc)", "Holo Mandala")
]

def draw_hud(frame: np.ndarray, fps: float, current_mode_idx: int, gesture_info: str, speed_val: float, particle_count: int, dark_mode: bool):
    """繪製賽博龐克風格的 HUD 介面"""
    overlay = frame.copy()
    cv2.rectangle(overlay, (15, 15), (420, 160), (12, 12, 28), -1)
    cv2.rectangle(overlay, (15, 15), (420, 160), (180, 50, 240), 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, "TRIPPY HAND TRACKER 2.0", (26, 40), font, 0.62, (0, 240, 255), 2, cv2.LINE_AA)

    mode_str = MODES[current_mode_idx][0]
    cv2.putText(frame, f"MODE: {mode_str}", (26, 68), font, 0.48, (255, 200, 50), 1, cv2.LINE_AA)

    cv2.putText(frame, f"Gesture: {gesture_info}", (26, 92), font, 0.46, (100, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(frame, f"FPS: {fps:.1f} | Spd: {speed_val:.2f}x | Pts: {particle_count}", (26, 114), font, 0.44, (200, 220, 255), 1, cv2.LINE_AA)

    cv2.putText(frame, "[1/2/3/TAB]Mode  [B]Bg  [P]Burst  [C]Clear  [S]Shot  [Q]Quit", (26, 142), font, 0.36, (160, 160, 200), 1, cv2.LINE_AA)


def main():
    print("=" * 68)
    print(" 🔮 啟動 TRIPPY HAND TRACKER 2.0 (迷幻手部追蹤與三大特色模式)")
    print("=" * 68)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[錯誤] 無法開啟前置鏡頭 (ID 0)，請確認鏡頭連線或權限。")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    tracker = UniversalHandTracker(max_num_hands=2)
    particle_system = ParticleSystem(max_particles=700)
    warp_effect = SpaceWarpDistortionEffect()
    cosmic_tunnel = CosmicExpansionTunnel()
    holo_renderer = HoloArcMandalaRenderer()

    # 模式與狀態
    current_mode = 0             # 0: 空間扭曲, 1: 宇宙發散, 2: 奇異博士魔法陣
    dark_mode = False            # True: 純黑霓虹背景, False: 鏡頭實景背景
    feedback_buffer = None
    burst_trigger = False

    fps_smooth = 30.0
    prev_time = time.time()
    frame_idx = 0

    print("\n[操作指南]")
    print("  - 數字鍵 1: 切換至【模式一：時空扭曲蟲洞風】")
    print("  - 數字鍵 2: 切換至【模式二：手勢控制宇宙發散 (張開全速/握緊慢/握拳停)】")
    print("  - 數字鍵 3: 切換至【模式三：奇異博士/鋼鐵人 掌心旋轉魔法陣】")
    print("  - TAB 鍵: 循環切換三大模式")
    print("  - B: 切換 純黑霓虹宇宙 / 鏡頭實景背景")
    print("  - P: 在食指觸發超新星粒子爆發")
    print("  - C: 清除殘影與粒子緩衝區")
    print("  - S: 截圖儲存當前畫面")
    print("  - Q 或 ESC: 退出程式\n")

    win_name = "Trippy Hand Tracker 2.0"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.02)
            continue

        # 鏡像翻轉
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        if feedback_buffer is None or feedback_buffer.shape != frame.shape:
            feedback_buffer = np.zeros_like(frame, dtype=np.float32)

        curr_time = time.time()
        dt = max(1e-4, curr_time - prev_time)
        prev_time = curr_time
        fps_smooth = fps_smooth * 0.9 + (1.0 / dt) * 0.1
        frame_idx += 1

        # 全域霓虹色相循環
        base_hue = (frame_idx * 1.5) % 180

        # 追蹤手部姿態
        hands_pose = tracker.process(frame)

        # 速度倍率與手勢文字
        effective_speed = 1.0
        gesture_status_str = "No Hands"
        if hands_pose:
            openness = hands_pose[0].openness
            gesture_status_str = f"{hands_pose[0].gesture_state} ({openness*100:.0f}%)"

        # 建立繪圖圖層
        art_layer = np.zeros_like(frame)
        glow_particle_layer = np.zeros_like(frame)

        # ---------------------------------------------------------------------
        # 依當前模式進行渲染處理
        # ---------------------------------------------------------------------
        if current_mode == 0:
            # === 模式一：時空扭曲蟲洞 ===
            # 對底層視訊執行局部空間扭曲與色差
            base_background = warp_effect.apply_warp(frame if not dark_mode else (frame * 0.12).astype(np.uint8), hands_pose, curr_time)

            # 繪製平滑雷射骨架
            for h_p in hands_pose:
                SmoothLaserHandRenderer.draw(art_layer, h_p.landmarks, base_hue, curr_time)

        elif current_mode == 1:
            # === 模式二：手勢控制宇宙發散 ===
            base_background = frame if not dark_mode else (frame * 0.10).astype(np.uint8)
            effective_speed, gesture_status_str = cosmic_tunnel.update_and_draw(art_layer, hands_pose, curr_time, base_hue)

            # 繪製平滑雷射骨架
            for h_p in hands_pose:
                SmoothLaserHandRenderer.draw(art_layer, h_p.landmarks, base_hue, curr_time)

        elif current_mode == 2:
            # === 模式三：奇異博士 / 鋼鐵人 掌心旋轉全息魔法陣 ===
            base_background = frame if not dark_mode else (frame * 0.12).astype(np.uint8)

            # 繪製平滑雷射骨架
            for h_p in hands_pose:
                SmoothLaserHandRenderer.draw(art_layer, h_p.landmarks, base_hue, curr_time)
                # 繪製掌心旋轉全息法陣
                holo_renderer.draw_mandala(art_layer, h_p, curr_time, base_hue)

        # ---------------------------------------------------------------------
        # 物理發光粒子系統 (食指尖端)
        # ---------------------------------------------------------------------
        if hands_pose:
            for h_p in hands_pose:
                # 節點 8 為食指尖端
                tip_x, tip_y = h_p.landmarks[8]
                particle_system.emit(tip_x, tip_y, base_hue, count=4, burst_mode=burst_trigger, speed_mult=effective_speed)
        else:
            particle_system.prev_emitter_pos = None

        if burst_trigger:
            burst_trigger = False

        particle_system.update(speed_mult=effective_speed)
        particle_system.draw(glow_particle_layer)

        # 合併當前幀迷幻藝術與粒子
        current_combined_art = cv2.add(art_layer, glow_particle_layer)

        # ---------------------------------------------------------------------
        # 殘影緩衝區處理 (Feedback Buffer)
        # ---------------------------------------------------------------------
        decay_factor = 0.82 if current_mode != 1 else (0.75 if effective_speed > 0.5 else 0.92)
        # 微量向外擴散漂移
        M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), 0.12 * effective_speed, 1.004)
        feedback_buffer = cv2.warpAffine(feedback_buffer, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        feedback_buffer = feedback_buffer * decay_factor + current_combined_art.astype(np.float32)
        feedback_buffer = np.clip(feedback_buffer, 0, 255)
        feedback_display = feedback_buffer.astype(np.uint8)

        # ---------------------------------------------------------------------
        # 最終合成輸出
        # ---------------------------------------------------------------------
        if dark_mode:
            final_frame = cv2.add((base_background * 0.35).astype(np.uint8), feedback_display)
        else:
            final_frame = cv2.add((base_background * 0.72).astype(np.uint8), feedback_display)

        # 繪製 HUD
        draw_hud(final_frame, fps_smooth, current_mode, gesture_status_str, effective_speed, len(particle_system.particles), dark_mode)

        cv2.imshow(win_name, final_frame)

        # ---------------------------------------------------------------------
        # 鍵盤互動事件
        # ---------------------------------------------------------------------
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            print("[退出] 使用者終止程式。")
            break
        elif key == ord('1'):
            current_mode = 0
            print(f"[切換模式] -> {MODES[0][0]}")
        elif key == ord('2'):
            current_mode = 1
            print(f"[切換模式] -> {MODES[1][0]}")
        elif key == ord('3'):
            current_mode = 2
            print(f"[切換模式] -> {MODES[2][0]}")
        elif key == 9:  # TAB 鍵
            current_mode = (current_mode + 1) % len(MODES)
            print(f"[切換模式] -> {MODES[current_mode][0]}")
        elif key == ord('b') or key == ord('B'):
            dark_mode = not dark_mode
            print(f"[背景切換] {'純黑霓虹宇宙' if dark_mode else '鏡頭實景'}")
        elif key == ord('p') or key == ord('P'):
            burst_trigger = True
            print("[特效] 觸發超新星粒子爆發 (Burst)！")
        elif key == ord('c') or key == ord('C'):
            particle_system.clear()
            feedback_buffer = np.zeros_like(frame, dtype=np.float32)
            print("[重置] 殘影緩衝區與粒子已清空。")
        elif key == ord('s') or key == ord('S'):
            shot_name = f"trippy_capture_mode{current_mode+1}_{int(time.time())}.png"
            cv2.imwrite(shot_name, final_frame)
            print(f"[截圖] 畫面已儲存至: {shot_name}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
