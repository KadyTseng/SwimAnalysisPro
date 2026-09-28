import os
import sys
import json
import logging
import matplotlib.pyplot as plt

# 設定與導入 BD 模組
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from BD.orchestrator import run_full_analysis

# ================== 參數設定區 ==================
# 請在此填入您要處理的兩部（或多部）原始影片路徑
VIDEO_PATHS = [
    r"E:\swimmer coco(validation)\kick_data(validation)\260624_IMU\IMU\real_time_picture (422).mp4",
    r"E:\swimmer coco(validation)\kick_data(validation)\260624_IMU\IMU\real_time_picture (423).mp4"
]

# 自動偵測模型路徑
POSE_MODEL_PATH = os.path.join(current_dir, "data", "models", "best_1.pt")
STYLE_MODEL_PATH = os.path.join(current_dir, "data", "models", "svm_model_new_3.pkl")
if not os.path.exists(STYLE_MODEL_PATH):
    STYLE_MODEL_PATH = os.path.join(current_dir, "data", "models", "svm_model_v2.pkl")

# 設定 FFMPEG 路徑
FFMPEG_PATH = "ffmpeg"
# 基礎輸出路徑 (Orchestrator 預設的 processed_videos 目錄)
OUTPUT_BASE_DIR = os.path.join(current_dir, "data", "processed_videos")
# ================================================

def generate_stroke_plots(keypoints_txt, phase_json_txt, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. 讀取骨架資料 (col10,11: 肩膀, col16,17: 手腕)
    frame_data = {}
    if not os.path.exists(keypoints_txt):
         logging.error(f"找不到骨架檔案: {keypoints_txt}")
         return
         
    with open(keypoints_txt, "r") as f:
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
    if not os.path.exists(phase_json_txt):
         logging.error(f"找不到相位記錄檔案: {phase_json_txt}")
         return
         
    with open(phase_json_txt, "r") as f:
        try:
             regions_data = json.load(f)
        except Exception as e:
             logging.error(f"解析 JSON 失敗 {phase_json_txt}: {e}")
             return

    # 找出所有的 Pull 起點
    pull_starts_info = []
    for lap_key, lap_data in regions_data.items():
        if isinstance(lap_data, dict):
            pulls = lap_data.get("Pull regions", [])
            for p in pulls:
                lap_name = lap_key.split('_')[0].capitalize() 
                pull_starts_info.append((p[0], lap_name))

    pull_starts_info.sort(key=lambda x: x[0])

    if len(pull_starts_info) > 0:
        max_frame = max(frame_data.keys()) if frame_data else 0
        
        for i in range(len(pull_starts_info)):
            start_f, lap_str = pull_starts_info[i]
            if i < len(pull_starts_info) - 1:
                end_f = pull_starts_info[i+1][0] - 1 
            else:
                end_f = max_frame
            
            frames, vals_x, vals_y = [], [], []
            for f in range(start_f, end_f + 1):
                if f in frame_data:
                    frames.append(f)
                    vals_x.append(frame_data[f][0])
                    vals_y.append(frame_data[f][1])
                    
            if len(frames) > 0:
                plt.figure(figsize=(8, 8))
                plt.plot(vals_x, vals_y, marker='o', markersize=3, color='b', linewidth=1.5, alpha=0.7)
                
                plt.scatter([vals_x[0]], [vals_y[0]], color='green', marker='o', s=100, label="Start (Pull)", zorder=6)
                plt.text(vals_x[0], vals_y[0], "  Start", color='green', fontsize=12, fontweight='bold', zorder=7)
                
                plt.scatter([vals_x[-1]], [vals_y[-1]], color='purple', marker='s', s=100, label="End", zorder=6)
                plt.text(vals_x[-1], vals_y[-1], "  End", color='purple', fontsize=12, fontweight='bold', zorder=7)
                
                plt.scatter([0], [0], color='r', marker='X', s=150, label="Shoulder (Origin)", zorder=5)
                
                plt.title(f"Stroke {i+1} 2D Trajectory | {lap_str} | (Frames {start_f} - {end_f})")
                plt.xlabel("Wrist X relative to Shoulder (Pixels)")
                plt.ylabel("Wrist Y relative to Shoulder (Pixels)")
                
                plt.gca().invert_yaxis()
                plt.axis('equal')
                
                plt.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
                plt.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
                
                plt.grid(True, alpha=0.3)
                plt.legend()
                
                out_file = os.path.join(out_dir, f"stroke_{i+1}.png")
                plt.savefig(out_file, dpi=150)
                plt.close()
                logging.info(f"✅ 已輸出: {out_file}")
                
        logging.info(f"🎉 總共匯出了 {len(pull_starts_info)} 下的軌跡圖片！\n放置在: {out_dir}")
    else:
        logging.warning("找不到任何 Pull 階段標記。")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    
    for video_path in VIDEO_PATHS:
        if not os.path.exists(video_path):
             logging.warning(f"影片不存在，略過: {video_path}")
             continue
             
        logging.info(f"========== 開始處理影片: {video_path} ==========")
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        
        # 建立輸出的資料夾結構
        os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
        data_dir = os.path.dirname(OUTPUT_BASE_DIR) # 會是 data/
        
        # 1. 執行完整的 Orchestrator 分析 (這會產生骨架與 Phase JSON)
        try:
             run_full_analysis(
                 pose_model_path=POSE_MODEL_PATH,
                 style_model_path=STYLE_MODEL_PATH,
                 video_path=video_path,
                 output_dir=OUTPUT_BASE_DIR,
                 ffmpeg_path=FFMPEG_PATH
             )
        except Exception as e:
             logging.error(f"分析影片 {base_name} 失敗: {e}")
             continue
             
        # 取得分析產出的路徑
        keypoints_txt = os.path.join(data_dir, "keypoints", f"{base_name}.txt")
        phase_json_txt = os.path.join(data_dir, "Stroke_Phase_Frames", f"{base_name}_a.txt")
        
        # 圖片輸出的資料夾
        plots_out_dir = os.path.join(current_dir, "test_outputs", "stroke_plots_auto", base_name)
        
        # 2. 產出切分好的划手軌跡圖片
        logging.info(f"開始繪製 {base_name} 的划手軌跡圖...")
        generate_stroke_plots(keypoints_txt, phase_json_txt, plots_out_dir)
        logging.info(f"========== 影片 {base_name} 處理完成 ==========\n")
