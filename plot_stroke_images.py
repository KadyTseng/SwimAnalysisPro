import os
import json
import matplotlib.pyplot as plt

base_dir = r"d:\Kady\Pool_UI_processed\SwimAnalysisPro"
# RAW 骨架檔案
raw_txt = os.path.join(base_dir, r"data\batch_processed_videos(validation)\keypoints\Excellent_20260120_freestyle_M_3(3).txt")
# JSON 相位記錄檔案
json_txt = os.path.join(base_dir, r"data\batch_processed_videos(validation)\Stroke_Phase_Frames\Excellent_20260120_freestyle_M_3(3)_a.txt")
# 圖片輸出資料夾
out_dir = os.path.join(base_dir, r"test_outputs\batch_arm_trajectory\Excellent_20260120_freestyle_M_3(3)\stroke_plots")
os.makedirs(out_dir, exist_ok=True)

# 1. 讀取原始骨架資料 (抽取 col10,11: 肩膀, col16,17: 手腕)
frame_data = {}
with open(raw_txt, "r") as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) > 17:
            try:
                frame = int(parts[0])
                col10 = float(parts[10]) # 肩膀X
                col11 = float(parts[11]) # 肩膀Y
                col16 = float(parts[16]) # 手腕X
                col17 = float(parts[17]) # 手腕Y
                
                # 相對位移 (以肩膀為原點)
                rel_x = col16 - col10
                rel_y = col17 - col11
                frame_data[frame] = (rel_x, rel_y)
            except:
                pass

# 2. 讀取分析好的相位區段
with open(json_txt, "r") as f:
    regions_data = json.load(f)

# 找出所有的 Pull 起點 (抓水起點，視為每一「下」的開始) 並記錄所屬 Lap
pull_starts_info = []
for lap_key, lap_data in regions_data.items():
    pulls = lap_data.get("Pull regions", [])
    for p in pulls:
        # lap_key 格式大約是 "lap1_decreasing"
        # 簡單清理一下字串只取前段例如 "Lap 1"
        lap_name = lap_key.split('_')[0].capitalize() 
        pull_starts_info.append((p[0], lap_name))

# 照著 start frame 排序
pull_starts_info.sort(key=lambda x: x[0])

# 3. 根據每一下 (Stroke) 進行切分與繪圖
if len(pull_starts_info) > 0:
    max_frame = max(frame_data.keys())
    
    for i in range(len(pull_starts_info)):
        start_f, lap_str = pull_starts_info[i]
        # 到下一個週期的前一幀為止，若是最後一下則畫到最後
        if i < len(pull_starts_info) - 1:
            end_f = pull_starts_info[i+1][0] - 1 
        else:
            end_f = max_frame
        
        frames = []
        vals_x = []
        vals_y = []
        for f in range(start_f, end_f + 1):
            if f in frame_data:
                frames.append(f)
                vals_x.append(frame_data[f][0])
                vals_y.append(frame_data[f][1])
                
        if len(frames) > 0:
            plt.figure(figsize=(8, 8))
            
            # 畫出 2D 軌跡線與點
            plt.plot(vals_x, vals_y, marker='o', markersize=3, color='b', linewidth=1.5, alpha=0.7)
            
            # 標示起點與終點
            plt.scatter([vals_x[0]], [vals_y[0]], color='green', marker='o', s=100, label="Start (Pull)", zorder=6)
            plt.text(vals_x[0], vals_y[0], "  Start", color='green', fontsize=12, fontweight='bold', zorder=7)
            
            plt.scatter([vals_x[-1]], [vals_y[-1]], color='purple', marker='s', s=100, label="End", zorder=6)
            plt.text(vals_x[-1], vals_y[-1], "  End", color='purple', fontsize=12, fontweight='bold', zorder=7)
            
            # 在原點 (0,0) 標示出肩膀的位置
            plt.scatter([0], [0], color='r', marker='X', s=150, label="Shoulder (Origin)", zorder=5)
            
            # 設定圖表資訊 (加上是哪一個 Lap)
            plt.title(f"Stroke {i+1} 2D Trajectory | {lap_str} | (Frames {start_f} - {end_f})")
            plt.xlabel("Wrist X relative to Shoulder (Pixels)")
            plt.ylabel("Wrist Y relative to Shoulder (Pixels)")
            
            # 反轉 Y 軸，因為影片坐標系 Y 是往下遞增的，這樣視覺上水面會在上方
            plt.gca().invert_yaxis()
            # 讓 X Y 軸比例1:1，避免軌跡被壓扁或拉長
            plt.axis('equal')
            
            # 加入十字準線明確定義原點位置
            plt.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            plt.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
            
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            # 存檔
            out_file = os.path.join(out_dir, f"stroke_{i+1}.png")
            plt.savefig(out_file, dpi=150)
            plt.close()
            print(f"✅ 已輸出: stroke_{i+1}.png")
            
    print(f"\n🎉 總共匯出了 {len(pull_starts_info)} 下的軌跡圖片！")
    print(f"檔案放置在: {out_dir}")
else:
    print("找不到任何 Pull 階段標記。")
