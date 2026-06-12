import os
import cv2
import numpy as np
import time
import tkinter as tk
from tkinter import messagebox, ttk

# --- 1. 背景偵測類別 (改用灰階辨識以解決色偏問題) ---
class ScanningAreaDetector:
    def __init__(self, alpha=0.8, threshold=1.2, consecutive_frames=1, reset_delay=1.2):
        self.avg_background = None
        self.alpha = alpha 
        self.threshold = threshold 
        self.consecutive_frames = consecutive_frames 
        self.counter = 0 
        self.reset_delay = reset_delay 
        self.triggered_time = None 
        self.is_locked = False 

    def update_and_detect(self, roi):
        if roi is None or roi.size == 0: return False, 0
        current_time = time.time()
        if self.is_locked:
            if current_time - self.triggered_time >= self.reset_delay:
                self.reset_state()
                return False, 0
            else:
                return True, 0

        # --- 修改處：使用灰階亮度，避免 ROI 4 因為藍紫色偏導致 Score 歸零 ---
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype("float32")
        
        if self.avg_background is None:
            self.avg_background = gray_roi.copy()
            return False, 0

        # 背景累積與差異計算
        cv2.accumulateWeighted(gray_roi, self.avg_background, self.alpha)
        diff = cv2.absdiff(gray_roi.astype("uint8"), self.avg_background.astype("uint8"))
        
        mean_val, _ = cv2.meanStdDev(diff)
        score = mean_val[0][0]
        
        if score > self.threshold: self.counter += 1
        else: self.counter = max(0, self.counter - 30) 
        
        if self.counter >= self.consecutive_frames:
            self.is_locked = True
            self.triggered_time = current_time
            return True, score
        return False, score

    def reset_state(self):
        self.counter = 0
        self.is_locked = False
        self.triggered_time = None
        self.avg_background = None

# --- 2. 輸入 UI ---
def get_parameters_from_ui():
    params = {}
    root = tk.Tk()
    root.title("SwimTiming System - Setup")
    root.geometry("350x450")
    main_frame = tk.Frame(root, padx=20, pady=20)
    main_frame.pack(expand=True, fill="both")

    tk.Label(main_frame, text="Race Distance (Meters):", font=("Arial", 9, "bold")).pack(anchor="w")
    ent_dist = tk.Entry(main_frame)
    ent_dist.pack(fill="x", pady=(0, 15)); ent_dist.insert(0, "200")

    tk.Label(main_frame, text="Number of Swimmers:", font=("Arial", 9, "bold")).pack(anchor="w")
    swimmer_count = tk.StringVar(value="2")
    cbo_swimmers = ttk.Combobox(main_frame, textvariable=swimmer_count, values=["1", "2", "3", "4"], state="readonly")
    cbo_swimmers.pack(fill="x", pady=(0, 15))

    tk.Label(main_frame, text="Target Time (Min/Sec):", font=("Arial", 9, "bold")).pack(anchor="w")
    time_frame = tk.Frame(main_frame); time_frame.pack(fill="x", pady=(0, 15))
    ent_min = tk.Entry(time_frame, width=5); ent_min.pack(side="left"); ent_min.insert(0, "3")
    tk.Label(time_frame, text=" min ").pack(side="left")
    ent_sec = tk.Entry(time_frame, width=5); ent_sec.pack(side="left"); ent_sec.insert(0, "0")
    tk.Label(time_frame, text=" sec").pack(side="left")

    tk.Label(main_frame, text="Total Laps (趟數):", font=("Arial", 9, "bold")).pack(anchor="w")
    ent_laps = tk.Entry(main_frame)
    ent_laps.pack(fill="x", pady=(0, 20)); ent_laps.insert(0, "1")

    def on_confirm():
        try:
            params['distance'] = int(ent_dist.get())
            params['swimmers'] = int(swimmer_count.get())
            params['total_seconds'] = int(ent_min.get()) * 60 + int(ent_sec.get())
            params['laps'] = int(ent_laps.get())
            root.destroy()
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers.")

    tk.Button(main_frame, text="Confirm & Start", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), command=on_confirm, pady=10).pack(fill="x")
    root.mainloop()
    return params if 'distance' in params else None

# --- 3. 結算 UI ---
def show_final_results_ui(goal, lap_records, target_time):
    result_img = np.zeros((650, 950, 3), dtype=np.uint8)
    while True:
        display = result_img.copy()
        cv2.putText(display, f"=== FINAL RESULTS ({goal}M) Target: {target_time}s ===", (150, 50), cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 255, 255), 2)
        y = 110
        for lap, records in lap_records.items():
            cv2.putText(display, f"LAP {lap}:", (40, y), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 0), 2)
            y += 40
            for s_dist in sorted(records['p1'].keys()):
                p1_val, p2_val = records['p1'][s_dist], records['p2'][s_dist]
                p1_str = f"{p1_val:.2f}s" if isinstance(p1_val, float) else "NA"
                p2_str = f"{p2_val:.2f}s" if isinstance(p2_val, float) else "NA"
                line_text = f"  {s_dist}M - P1: {p1_str:<11} | P2: {p2_str}"
                cv2.putText(display, line_text, (60, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                y += 30
        cv2.putText(display, "Press 'Q' to Exit", (380, 620), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow("SwimTiming System - Report", display)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    cv2.destroyAllWindows()

# --- 4. 單鏡頭計時主程式 ---
def test_single_video_timing(video_path, roi_list, params):
    distance_goal = params['distance']
    total_laps = params['laps']
    target_time = params['total_seconds']
    all_lap_results = {}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open {video_path}")
        return

    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    for lap_idx in range(1, total_laps + 1):
        trigger_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        last_global_trigger = 0.0
        timers = {"p1": None, "p2": None}        
        ui_messages = [] 
        all_milestones = list(range(25, distance_goal + 25, 25))
        records = {"p1": {s: "NA" for s in all_milestones}, "p2": {s: "NA" for s in all_milestones}}
        detectors = [ScanningAreaDetector() for _ in roi_list]
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        def add_message(text, pos=(50, 150), color=(0, 255, 255), duration=5.0):
            ui_messages.append({"text": text, "expire": time.time() + duration, "pos": pos, "color": color})

        while True:
            ret, frame = cap.read()
            if not ret: break
            
            now_ts = time.time()
            for idx, roi_coords in enumerate(roi_list):
                y1, y2, x1, x2 = roi_coords
                y1, y2 = max(0, min(y1, orig_h)), max(0, min(y2, orig_h))
                x1, x2 = max(0, min(x1, orig_w)), max(0, min(x2, orig_w))
                
                roi_img = frame[y1:y2, x1:x2]
                if roi_img.size == 0: continue

                was_locked = detectors[idx].is_locked
                found, score = detectors[idx].update_and_detect(roi_img)
                
                # 這裡對應你的 single_cam_rois 列表順序
                curr_id = 1 if idx == 0 else 4 
                
                if found and not was_locked:
                    if now_ts - last_global_trigger < 0.8:
                        detectors[idx].reset_state()
                    else:
                        last_global_trigger = now_ts
                        trigger_counts[curr_id] += 1
                        cnt = trigger_counts[curr_id]
                        
                        # 計時邏輯 (ROI 1 同時作為起點與終點端)
                        if curr_id == 1:
                            if cnt == 1: timers["p1"] = now_ts; add_message("P1 START!", (100, 100), (0, 255, 0))
                            elif cnt == 2: timers["p2"] = now_ts; add_message("P2 START!", (100, 150), (0, 255, 0))
                            elif cnt >= 3:
                                adj = cnt - 2
                                p = "p1" if adj % 2 != 0 else "p2"
                                d = 50 + ((adj - 1) // 2) * 50
                                if timers[p] and d <= distance_goal:
                                    records[p][d] = now_ts - timers[p]
                                    add_message(f"{p.upper()} {d}M: {records[p][d]:.2f}s", (700, 100 if p=="p1" else 150), (255, 128, 0))
                        
                        # 轉身端邏輯 (ROI 4)
                        elif curr_id == 4:
                            p = "p1" if cnt % 2 != 0 else "p2"
                            d = 25 + ((cnt - 1) // 2) * 50
                            if timers[p] and d <= distance_goal:
                                records[p][d] = now_ts - timers[p]
                                add_message(f"{p.upper()} {d}M: {records[p][d]:.2f}s", (400, 100 if p=="p1" else 150))

                # 顯示方框與 Score
                clr = (0, 0, 255) if detectors[idx].is_locked else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), clr, 3)
                cv2.putText(frame, f"ROI {curr_id} Score:{score:.2f}", (x1, y1-15), cv2.FONT_HERSHEY_SIMPLEX, 1.2, clr, 3)

            # 畫面縮放顯示
            display_w = 1280
            scale = display_w / orig_w
            display_h = int(orig_h * scale)
            display_frame = cv2.resize(frame, (display_w, display_h))

            ui_messages = [m for m in ui_messages if now_ts < m["expire"]]
            for m in ui_messages:
                scaled_pos = (int(m["pos"][0] * scale), int(m["pos"][1] * scale))
                cv2.putText(display_frame, m["text"], scaled_pos, cv2.FONT_HERSHEY_DUPLEX, 1.0, m["color"], 2)
            
            for i, p in enumerate(["p1", "p2"]):
                if timers[p]:
                    cv2.putText(display_frame, f"{p.upper()}: {now_ts-timers[p]:.1f}s", 
                                (30, 50+i*50), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255,255,255), 2)

            info = f"LAP: {lap_idx}/{total_laps} | 200M Mode | Target: {target_time}s"
            cv2.putText(display_frame, info, (30, display_h - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

            cv2.imshow("SwimTiming System - Single Cam", display_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'): 
                lap_idx = total_laps
                break
            if records["p1"][distance_goal] != "NA" and records["p2"][distance_goal] != "NA":
                time.sleep(2); break
        
        all_lap_results[lap_idx] = records

    cap.release()
    cv2.destroyAllWindows()
    show_final_results_ui(distance_goal, all_lap_results, target_time)

if __name__ == "__main__":
    params = get_parameters_from_ui()
    if params:
        video_path = r"C:\Users\user\Desktop\real_time_picture (223).mp4"
        single_cam_rois = [
            [620, 800, 400, 450],   # ROI 1
            [620, 800, 3200, 3250]  # ROI 4
        ]
        test_single_video_timing(video_path, single_cam_rois, params)