import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os  # 用於強制退出、釋放背景程序

class LiveStreamTuningApp:
    def __init__(self, window, video_path):
        self.window = window
        self.window.title("游泳特徵即時分析工作站 (每幀動態正極大值尋優版)")
        self.video_path = video_path
        
        # 🌟 修正：設定主主控台視窗的大小與彈出位置 (寬1200, 高900, 畫面左上角 X=50, Y=50 處)
        self.window.geometry("1200x900+50+50")
        
        # 🌟 綁定視窗關閉事件：點擊 ❌ 時強制釋放所有資源，防範第二次執行卡死
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 1. 影像讀取與基礎資訊
        self.cap = cv2.VideoCapture(video_path)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 60.0
        
        # 2. ROI 範圍與邏輯設定
        self.roi_x = (3600, 3650)
        self.roi_y = (580, 700)
        self.threshold = 40.0
        
        # 🌟 公式參數鎖定狀態與容器
        self.is_locked = False
        self.locked_combo = (0, 0, 0)  # 儲存鎖定那一刻的 (B, G, R) 公式密碼
        
        # 3. 數據暫存器 (用於繪圖)
        self.frame_data = []
        self.total_diff_data = []
        self.b_raw_data, self.g_raw_data, self.r_raw_data = [], [], []
        ㄙ
        # 4. 背景參考值 (REF) 初始化設定
        self.bg_b, self.bg_g, self.bg_r = 0, 0, 0
        self.bg_init_frames = []
        self.bg_needed_frames = 60  
        self.is_bg_ready = False
        self.global_frame_count = 0
        
        # 定義 8 種公式組合清單 (0 代表 cur-ref 正向, 1 代表 ref-cur 負向)
        self.formula_combinations = [
            (b, g, r) for b in [0, 1] for g in [0, 1] for r in [0, 1]
        ]
        
        # 5. UI 與 繪圖物件建立
        self._create_widgets()
        self._create_video_window()
        
        # 6. 啟動迴圈
        self.update_loop()

    def _create_widgets(self):
        # 左側控制台
        self.left_panel = ttk.Frame(self.window, padding=12)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        # 右側大圖表區
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

        ttk.Separator(self.left_panel, orient='horizontal').pack(fill=tk.X, pady=15)

        # 實時動態公式文字區
        ttk.Label(self.left_panel, text="【當前畫面最佳公式(動態追蹤中)】", font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(5, 2))
        self.lbl_composite_formula = tk.Label(
            self.left_panel, 
            text="正在等待背景初始化...", 
            font=('Consolas', 12, 'bold'),
            fg='#1b2a4a', 
            bg='#e3f2fd', 
            justify=tk.LEFT,
            anchor=tk.W,
            padx=10, 
            pady=12, 
            wraplength=250
        )
        self.lbl_composite_formula.pack(anchor=tk.W, fill=tk.X, pady=5)

        # 🌟 鎖定參數按鈕
        self.lock_btn = tk.Button(
            self.left_panel,
            text="確定鎖定當前公式",
            command=self.toggle_lock,
            bg="#2e7d32",  # 深綠色
            fg="white",
            font=('Arial', 11, 'bold'),
            relief=tk.RAISED,
            padx=10,
            pady=5
        )
        self.lock_btn.pack(anchor=tk.W, fill=tk.X, pady=15)

        # Matplotlib 結構佈局
        self.fig, (self.ax_r, self.ax_g, self.ax_b, self.ax_total) = plt.subplots(4, 1, figsize=(9, 8), sharex=True) 
        self.fig.tight_layout(pad=2.0)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _create_video_window(self):
        self.video_win = tk.Toplevel(self.window)
        self.video_win.title("大螢幕影像即時觀測窗")
        
        # 🌟 修正：設定影像觀測視窗的大小與彈出位置 (寬1050, 高650, 彈在右側 X=1300, Y=50 的位置，與主視窗分離)
        self.video_win.geometry("1050x650+1250+50")
        
        # 子視窗關閉時也連帶觸發主退場機制，確保乾淨釋放
        self.video_win.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.video_label = ttk.Label(self.video_win)
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _get_formula_text(self, combo):
        """根據傳入的組合代碼，轉換成可讀的公式字串"""
        b_pos, g_pos, r_pos = [mode == 0 for mode in combo]
        b_txt = "(B - Bref)" if b_pos else "(Bref - B)"
        g_txt = "(G - Gref)" if g_pos else "(Gref - G)"
        r_txt = "(R - Rref)" if r_pos else "(Rref - R)"
        return f"{b_txt}\n+ {g_txt}\n+ {r_txt}"

    def adj_t(self, amt):
        try:
            self.threshold = max(0.0, float(self.t_var.get()) + amt)
            self.t_var.set(str(int(self.threshold)))
        except ValueError:
            pass

    def _calc_diff(self, cur, ref, mode_idx):
        if mode_idx == 0: return cur - ref
        return ref - cur

    def toggle_lock(self):
        """控制鎖定/解鎖狀態"""
        if not self.is_bg_ready:
            print("⚠️ 背景尚未初始化完成，無法鎖定公式。")
            return

        if not self.is_locked:
            # 執行鎖定
            self.is_locked = True
            self.lock_btn.config(text="🔒 已鎖定公式 (點擊解鎖)", bg="#c62828") # 變紅色提示
            print(f"🎯 公式已鎖定！後續全部計算將固定採用組合: {self.locked_combo}")
        else:
            # 解鎖
            self.is_locked = False
            self.lock_btn.config(text="確定鎖定當前公式", bg="#2e7d32") # 回復綠色
            print("🔓 公式已解鎖，回復每幀動態最佳化尋優。")

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
                if self.is_locked:
                    # 【鎖定模式】：固定使用被鎖定時的那組 combo 進行後續計算
                    combo = self.locked_combo
                    db = self._calc_diff(avg_color[0], self.bg_b, combo[0])
                    dg = self._calc_diff(avg_color[1], self.bg_g, combo[1])
                    dr = self._calc_diff(avg_color[2], self.bg_r, combo[2])
                    final_score = db + dg + dr
                    
                    formula_str = self._get_formula_text(combo)
                    self.lbl_composite_formula.config(text=f"🔒 [已鎖定]\n{formula_str}", fg='#7f0000', bg='#ffebee')
                else:
                    # 【動態尋優模式】：每幀重新尋找「真正的正值最大值」
                    max_positive_score = -99999.0
                    current_best_combo = (0, 0, 0)
                    
                    for combo in self.formula_combinations:
                        db = self._calc_diff(avg_color[0], self.bg_b, combo[0])
                        dg = self._calc_diff(avg_color[1], self.bg_g, combo[1])
                        dr = self._calc_diff(avg_color[2], self.bg_r, combo[2])
                        total_score = db + dg + dr
                        
                        if total_score > max_positive_score:
                            max_positive_score = total_score
                            current_best_combo = combo
                    
                    final_score = max_positive_score
                    self.locked_combo = current_best_combo # 隨時更新最佳解，供按鈕隨時鎖定
                    
                    formula_str = self._get_formula_text(current_best_combo)
                    self.lbl_composite_formula.config(text=formula_str, fg='#e65100', bg='#fff3e0')
                
                self.total_diff_data.append(final_score)
                status_txt = f"Score: {final_score:.1f} | Thresh: {int(self.threshold)}"

            # 滾動控制 (維持最近 300 幀長度)
            if len(self.frame_data) > 300:
                self.frame_data.pop(0)
                self.b_raw_data.pop(0); self.g_raw_data.pop(0); self.r_raw_data.pop(0)
                self.total_diff_data.pop(0)

            # 影像渲染與觸發門檻
            draw_frame = frame.copy()
            if self.is_bg_ready and len(self.total_diff_data) > 0 and self.total_diff_data[-1] > self.threshold:
                box_color = (0, 0, 255) # 超過門檻亮紅燈
            else:
                box_color = (0, 255, 0) # 安全綠燈

            cv2.rectangle(draw_frame, (self.roi_x[0], self.roi_y[0]), (self.roi_x[1], self.roi_y[1]), box_color, 3)
            cv2.putText(draw_frame, status_txt, (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, box_color, 3)
            self._display_video(draw_frame)

        if len(self.frame_data) > 0:
            self._update_charts()

        self.window.after(1, self.update_loop)

    def _update_charts(self):
        self.ax_r.clear(); self.ax_g.clear(); self.ax_b.clear(); self.ax_total.clear()
        
        # --- 通用處理函數：維持保底範圍，超出則自動撐開 ---
        def get_dynamic_ylim(data, ref_val, padding_down=30, padding_up=50, absolute_limit=(0, 255)):
            if not self.is_bg_ready or len(data) == 0:
                return absolute_limit
            
            # 1. 設定你想要的「固定保底範圍」
            base_min = ref_val - padding_down
            base_max = ref_val + padding_up
            
            # 2. 取得當前數據的實際極值
            actual_min = min(data)
            actual_max = max(data)
            
            # 3. 邏輯：取兩者之最（讓範圍只會變大，不會縮到比保底還小）
            final_min = min(base_min, actual_min - 5) # 多給 5 的緩衝
            final_max = max(base_max, actual_max + 5)
            
            # 4. 限制在物理極限 (如 0~255)
            return (max(absolute_limit[0], final_min), min(absolute_limit[1], final_max))

        # 1. 紅通道
        self.ax_r.plot(self.frame_data, self.r_raw_data, color='red', label='Red Raw', linewidth=1.5)
        if self.is_bg_ready:
            self.ax_r.axhline(y=self.bg_r, color='darkred', linestyle=':', label=f'R_REF ({int(self.bg_r)})')
            # 🌟 維持設定的 -30~+50，但超出則自動放大的邏輯
            self.ax_r.set_ylim(get_dynamic_ylim(self.r_raw_data, self.bg_r, 40, 40))
        else:
            self.ax_r.set_ylim(0, 255)
        self.ax_r.set_ylabel("Red")
        self.ax_r.legend(loc='upper left', fontsize='7').set_zorder(5)
        self.ax_r.grid(True, alpha=0.2)

        # 2. 綠通道
        self.ax_g.plot(self.frame_data, self.g_raw_data, color='green', label='Green Raw', linewidth=1.5)
        if self.is_bg_ready:
            self.ax_g.axhline(y=self.bg_g, color='darkgreen', linestyle=':', label=f'G_REF ({int(self.bg_g)})')
            self.ax_g.set_ylim(get_dynamic_ylim(self.g_raw_data, self.bg_g, 40, 40))
        else:
            self.ax_g.set_ylim(0, 255)
        self.ax_g.set_ylabel("Green")
        self.ax_g.legend(loc='upper left', fontsize='7').set_zorder(5)
        self.ax_g.grid(True, alpha=0.2)

        # 3. 藍通道
        self.ax_b.plot(self.frame_data, self.b_raw_data, color='blue', label='Blue Raw', linewidth=1.5)
        if self.is_bg_ready:
            self.ax_b.axhline(y=self.bg_b, color='darkblue', linestyle=':', label=f'B_REF ({int(self.bg_b)})')
            self.ax_b.set_ylim(get_dynamic_ylim(self.b_raw_data, self.bg_b, 25, 25))
        else:
            self.ax_b.set_ylim(0, 255)
        self.ax_b.set_ylabel("Blue")
        self.ax_b.legend(loc='upper left', fontsize='7').set_zorder(5)
        self.ax_b.grid(True, alpha=0.2)

        # 4. 最底層：實時正極大值 (保底 -10~80)
        total_np = np.array(self.total_diff_data)
        self.ax_total.plot(self.frame_data, total_np, color='purple', linewidth=2, label='Frame Max Pos Diff')
        self.ax_total.axhline(y=self.threshold, color='crimson', linestyle='--', linewidth=2, label=f'Threshold ({int(self.threshold)})')
        self.ax_total.fill_between(self.frame_data, total_np, self.threshold, where=(total_np > self.threshold), color='red', alpha=0.2)
        
        # 🌟 設定總表的保底範圍：常態看 -10~80，數值噴掉時自動放大
        if len(self.total_diff_data) > 0:
            t_min = min(-10, min(self.total_diff_data) - 10)
            t_max = max(80, max(self.total_diff_data) + 20)
            self.ax_total.set_ylim(t_min, t_max)
        else:
            self.ax_total.set_ylim(-10, 80)

        self.ax_total.set_title("Dynamic Max Positive Dashboard", fontsize=10, pad=2)
        self.ax_total.set_xlabel("Frame Count")
        self.ax_total.set_ylabel("Score")
        self.ax_total.legend(loc='upper left', fontsize='7').set_zorder(5)
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

    def on_closing(self):
        """安全退場機制：徹底銷毀程序防卡死"""
        print("👉 正在安全關閉分析工作站並完整釋放記憶體...")
        try:
            if self.cap.isOpened():
                self.cap.release()
        except:
            pass
        try:
            plt.close('all')
        except:
            pass
        self.window.destroy()
        os._exit(0)  # ⚡ 直接秒殺 Windows 後台程序

if __name__ == "__main__":
    video_path = "D:/WEICHIEH/SwimtimingUI/demo/real_time_picture (353)_200.mp4"
    
    root = tk.Tk()
    app = LiveStreamTuningApp(root, video_path)
    root.mainloop()