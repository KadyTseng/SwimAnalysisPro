import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class LiveStreamTuningApp:
    def __init__(self, window, video_path):
        self.window = window
        self.window.title("游泳特徵即時分析工作站 (RGB 通道獨立觀測版)")
        self.video_path = video_path
        
        # 1. 影像讀取與基礎資訊
        self.cap = cv2.VideoCapture(video_path)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 60.0
        
        # 2. ROI 範圍與邏輯設定
        self.roi_x = (3600, 3650)
        self.roi_y = (580, 700)
        self.threshold = 40.0
        
        # 3. 數據暫存器 (用於繪圖)
        self.frame_data = []
        self.total_diff_data = []
        self.b_raw_data, self.g_raw_data, self.r_raw_data = [], [], []
        
        # 4. 背景參考值 (REF) 初始化設定 (前 60 幀平均)
        self.bg_b, self.bg_g, self.bg_r = 0, 0, 0
        self.bg_init_frames = []
        self.bg_needed_frames = 60  
        self.is_bg_ready = False
        self.global_frame_count = 0
        
        # 5. UI 與 繪圖物件建立
        self._create_widgets()
        self._create_video_window()
        
        # 6. 啟動迴圈
        self.update_loop()

    def _create_widgets(self):
        # 左側控制台
        self.left_panel = ttk.Frame(self.window, padding=12)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        # 右側大圖表區 (獲得極大化水平寬度)
        self.right_panel = ttk.Frame(self.window, padding=10)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 門檻控制區
        ttk.Label(self.left_panel, text="【門檻 Threshold】", font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(5,0))
        t_frame = ttk.Frame(self.left_panel); t_frame.pack(anchor=tk.W, pady=5)
        ttk.Button(t_frame, text="-5", width=4, command=lambda: self.adj_t(-5)).pack(side=tk.LEFT)
        self.t_var = tk.StringVar(value=str(int(self.threshold)))
        self.entry_t = ttk.Entry(t_frame, textvariable=self.t_var, width=6, justify='center', font=('Arial', 11))
        self.entry_t.pack(side=tk.LEFT, padx=5)
        self.entry_t.bind("<Return>", lambda e: self.adj_t(0))
        ttk.Button(t_frame, text="+5", width=4, command=lambda: self.adj_t(5)).pack(side=tk.LEFT)

        ttk.Separator(self.left_panel, orient='horizontal').pack(fill=tk.X, pady=10)

        # 各顏色通道計算模式切換
        for color in ['Blue', 'Green', 'Red']:
            ttk.Label(self.left_panel, text=f"【{color} Channel 設定】", font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(5, 0))
            var = tk.IntVar(value=0) 
            setattr(self, f"{color.lower()}_var", var)
            
            f = ttk.Frame(self.left_panel)
            f.pack(anchor=tk.W, pady=(2, 5))
            
            c_let = color[0] 
            ttk.Radiobutton(f, text=f"{c_let} - {c_let}ref (正)", variable=var, value=0, command=self._update_composite_formula).pack(side=tk.LEFT, padx=5)
            ttk.Radiobutton(f, text=f"{c_let}ref - {c_let} (負)", variable=var, value=1, command=self._update_composite_formula).pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.left_panel, orient='horizontal').pack(fill=tk.X, pady=10)

        # 公式文字區
        ttk.Label(self.left_panel, text="【當前決策公式】", font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(5, 2))
        self.lbl_composite_formula = tk.Label(
            self.left_panel, 
            text="", 
            font=('Consolas', 13, 'bold'),
            fg='#1b2a4a', 
            bg='#e3f2fd', 
            justify=tk.LEFT,
            anchor=tk.W,
            padx=10, 
            pady=12, 
            wraplength=250
        )
        self.lbl_composite_formula.pack(anchor=tk.W, fill=tk.X, pady=5)
        
        self._update_composite_formula()

        # Matplotlib 結構改版 (4行1列佈局，基礎尺寸放大為 9x8)
        self.fig, (self.ax_r, self.ax_g, self.ax_b, self.ax_total) = plt.subplots(4, 1, figsize=(9, 8), sharex=True) 
        self.fig.tight_layout(pad=2.0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_video_window(self):
        self.video_win = tk.Toplevel(self.window)
        self.video_win.title("大螢幕影像即時觀測窗")
        self.video_win.protocol("WM_DELETE_WINDOW", self.window.destroy)
        
        self.video_label = ttk.Label(self.video_win)
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _update_composite_formula(self):
        b_pos = self.blue_var.get() == 0
        g_pos = self.green_var.get() == 0
        r_pos = self.red_var.get() == 0
        
        b_txt = "(B - Bref)" if b_pos else "(Bref - B)"
        g_txt = "(G - Gref)" if g_pos else "(Gref - G)"
        r_txt = "(R - Rref)" if r_pos else "(Rref - R)"
        
        formula_str = f"{b_txt} + {g_txt} + {r_txt}"
        self.lbl_composite_formula.config(text=formula_str)

    def adj_t(self, amt):
        try:
            self.threshold = max(0.0, float(self.t_var.get()) + amt)
            self.t_var.set(str(int(self.threshold)))
        except ValueError:
            pass

    def _calc_diff(self, cur, ref, mode_idx):
        if mode_idx == 0: return cur - ref
        return ref - cur

    def update_loop(self):
        ret, frame = self.cap.read()
        if not ret:
            print("影片播放結束")
            self.cap.release()
            return

        roi = frame[self.roi_y[0]:self.roi_y[1], self.roi_x[0]:self.roi_x[1]]
        if roi.size > 0:
            avg_color = np.mean(roi, axis=(0, 1))
            self.global_frame_count += 1
            
            # 紀錄原始 RGB 絕對值
            self.frame_data.append(self.global_frame_count)
            self.b_raw_data.append(avg_color[0])
            self.g_raw_data.append(avg_color[1])
            self.r_raw_data.append(avg_color[2])
            
            # 背景初始化邏輯
            if not self.is_bg_ready:
                self.bg_init_frames.append(avg_color)
                if len(self.bg_init_frames) == self.bg_needed_frames:
                    bg_avg = np.mean(self.bg_init_frames, axis=0)
                    self.bg_b, self.bg_g, self.bg_r = bg_avg
                    self.is_bg_ready = True
                
                self.total_diff_data.append(0.0)
                status_txt = f"Initializing REF... ({len(self.bg_init_frames)}/{self.bg_needed_frames})"
            else:
                db = self._calc_diff(avg_color[0], self.bg_b, self.blue_var.get())
                dg = self._calc_diff(avg_color[1], self.bg_g, self.green_var.get())
                dr = self._calc_diff(avg_color[2], self.bg_r, self.red_var.get())
                total = db + dg + dr
                self.total_diff_data.append(total)
                
                status_txt = f"Total Diff: {total:.1f} | Thresh: {int(self.threshold)}"

            # 滾動控制 (維持最近 300 幀長度)
            if len(self.frame_data) > 300:
                self.frame_data.pop(0)
                self.b_raw_data.pop(0); self.g_raw_data.pop(0); self.r_raw_data.pop(0)
                self.total_diff_data.pop(0)

            # 影像渲染
            draw_frame = frame.copy()
            if self.is_bg_ready and len(self.total_diff_data) > 0 and self.total_diff_data[-1] > self.threshold:
                box_color = (0, 0, 255)
            else:
                box_color = (0, 255, 0)

            cv2.rectangle(draw_frame, (self.roi_x[0], self.roi_y[0]), (self.roi_x[1], self.roi_y[1]), box_color, 3)
            cv2.putText(draw_frame, status_txt, (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, box_color, 3)
            self._display_video(draw_frame)

        if len(self.frame_data) > 0:
            self._update_charts()

        self.window.after(1, self.update_loop)

    def _update_charts(self):
        self.ax_r.clear(); self.ax_g.clear(); self.ax_b.clear(); self.ax_total.clear()
        
        # 1. 獨立紅通道 (Red Raw)
        self.ax_r.plot(self.frame_data, self.r_raw_data, color='red', label='Red Raw (0-255)', linewidth=1.5)
        if self.is_bg_ready:
            self.ax_r.axhline(y=self.bg_r, color='darkred', linestyle=':', label=f'R_REF ({int(self.bg_r)})')
        self.ax_r.set_ylabel("Red")
        self.ax_r.set_ylim(0, 255)
        self.ax_r.legend(loc='upper left', fontsize='7')
        self.ax_r.grid(True, alpha=0.2)

        # 2. 獨立綠通道 (Green Raw)
        self.ax_g.plot(self.frame_data, self.g_raw_data, color='green', label='Green Raw (0-255)', linewidth=1.5)
        if self.is_bg_ready:
            self.ax_g.axhline(y=self.bg_g, color='darkgreen', linestyle=':', label=f'G_REF ({int(self.bg_g)})')
        self.ax_g.set_ylabel("Green")
        self.ax_g.set_ylim(0, 255)
        self.ax_g.legend(loc='upper left', fontsize='7')
        self.ax_g.grid(True, alpha=0.2)

        # 3. 獨立藍通道 (Blue Raw)
        self.ax_b.plot(self.frame_data, self.b_raw_data, color='blue', label='Blue Raw (0-255)', linewidth=1.5)
        if self.is_bg_ready:
            self.ax_b.axhline(y=self.bg_b, color='darkblue', linestyle=':', label=f'B_REF ({int(self.bg_b)})')
        self.ax_b.set_ylabel("Blue")
        self.ax_b.set_ylim(0, 255)
        self.ax_b.legend(loc='upper left', fontsize='7')
        self.ax_b.grid(True, alpha=0.2)

        # 4. 最底層：決策總分與門檻對照圖 (與前三圖時間軸完全對齊)
        self.ax_total.plot(self.frame_data, self.total_diff_data, color='purple', linewidth=2, label='Total Fused Diff')
        self.ax_total.axhline(y=self.threshold, color='crimson', linestyle='--', linewidth=2, label=f'Threshold ({int(self.threshold)})')
        
        total_np = np.array(self.total_diff_data)
        self.ax_total.fill_between(self.frame_data, total_np, self.threshold, where=(total_np > self.threshold), color='red', alpha=0.2)
        
        self.ax_total.set_title("Decision Dashboard: Total Score vs Threshold", fontsize=10, pad=2)
        self.ax_total.set_xlabel("Frame Count")
        self.ax_total.set_ylabel("Score")
        
        current_max = max(self.total_diff_data) if len(self.total_diff_data) > 0 else 100
        current_min = min(self.total_diff_data) if len(self.total_diff_data) > 0 else -50
        self.ax_total.set_ylim(min(-50, current_min * 1.2), max(120, current_max * 1.3))
        self.ax_total.legend(loc='upper left', fontsize='7')
        self.ax_total.grid(True, alpha=0.3)

        self.canvas.draw()

    def _display_video(self, frame):
        h, w = frame.shape[:2]
        new_w = 1020
        new_h = int(h * (new_w / w))
        img = cv2.resize(frame, (new_w, new_h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img)
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

if __name__ == "__main__":
    # 🌟 已成功更換至最新的 WEICHIEH 子目錄路徑
    video_path = r"C:\Users\user\Desktop\WEICHIEH\SwimtimingUI\demo\real_time_picture (353)_200.mp4"
    
    root = tk.Tk()
    app = LiveStreamTuningApp(root, video_path)
    root.mainloop()