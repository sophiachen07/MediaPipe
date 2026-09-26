# 🔮 Trippy Hand Tracker - 迷幻風格手部追蹤與物理發光粒子系統

一個基於 **OpenCV** 與 **MediaPipe Hands** 開發的即時迷幻風格 (Trippy Visuals) 手部追蹤與 2D 物理發光粒子特效系統。

---

## ✨ 核心特色 (Features)

1. **即時手部追蹤 (Real-time Hand Tracking)**
   - 跨版本相容 MediaPipe Tasks API (Python 3.12 / 3.13+) 與經典 Solutions API。
   - 21 個手部關節點精準定位，支援雙手同時追蹤。
   - 水平鏡像翻轉，操作手感自然直覺。

2. **迷幻霓虹視覺 (Psychedelic Trippy Visuals)**
   - **HSV 色彩動態循環**：節點與連線的顏色隨時間（幀數）進行霓虹色調輪轉。
   - **多層同心光環 (Concentric Pulsating Orbs)**：關節點呈現多層發光同心圓與白熾發光核心，具備呼吸縮放效果。
   - **正弦波碎形動態連線 (Sine Wave Harmonic Fractal Connections)**：捨棄傳統直線骨架，透過多重諧波正弦函數計算垂直振幅，呈現動態有機碎形感。
   - **空間殘影回饋緩衝區 (Feedback Decay Buffer & Space Drift)**：利用微量空間旋轉放大與加權透明度衰減，產生視覺殘影與空間扭曲感。

3. **物理發光粒子系統 (Physics-based Glowing Particle System)**
   - **食指尖端發射器 (Landmark 8)**：以食指尖為發射源。
   - **真實物理模擬**：
     - 手指移動慣性加速度注入 (Velocity Injection)。
     - 向下重力加速度 (Gravity)。
     - 空氣阻力衰減 (Drag/Damping) 與混沌正弦擾動 (Turbulence)。
   - **多層次 Neon Glow 發光漸層**：利用加權混色（`cv2.add`）模擬璀璨星塵光暈。

4. **豐富的即時互動控制 (Interactive HUD & Hotkeys)**
   - 包含即時 FPS、偵測手部數、粒子數與模式狀態顯示。

---

## 🛠️ 安裝方式 (Installation)

### 1. 複製專案
```bash
git clone https://github.com/sophiachen07/MediaPipe.git
cd MediaPipe
```

### 2. 安裝相依套件
建議在 Python 3.10+ 環境下執行：
```bash
pip install -r requirements.txt
```

---

## 🚀 執行程式 (Run)

```bash
python trippy_hand_tracker.py
```
> **提示**：程式首次執行時會自動從 Google 官方下載 `hand_landmarker.task` 模型檔案（約 7.8 MB）。

---

## 🎮 鍵盤快捷鍵 (Hotkeys)

| 按鍵 | 功能說明 |
| :---: | :--- |
| **`Q`** / **`ESC`** | 退出程式 |
| **`B`** | 切換 **純黑霓虹模式 (Dark Neon)** 與 **相機實景疊加模式 (Camera Blend)** |
| **`T`** | 切換殘影強度（**Short** 輕度 / **Medium** 標準 / **Dreamy Long** 夢幻長光軌） |
| **`P`** | 在食指尖端觸發 **超新星粒子爆發 (Supernova Burst)** |
| **`C`** | 清除殘影緩衝區與所有在場粒子 |
| **`S`** | 即時儲存當前畫面截圖至目錄 |

---

## 📄 授權條款 (License)

本專案採用 [MIT License](LICENSE) 開源授權。
