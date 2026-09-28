import os
import sys
import glob
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Ensure BD modules can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from BD.pose_estimator import run_pose_estimation
    from BD.freestyle_pose_estimator.txt_base import process_keypoints_txt
    from BD.diving_analyzer_track_angles import analyze_diving_phase
except ImportError as e:
    print(f"Error importing BD modules: {e}")
    sys.exit(1)

# Configuration
# 請在此替換為您要處理的特定三個資料夾路徑
TARGET_DIRS = [
    r"E:\swimmer coco(validation)\kick_data(validation)\260617",
    r"E:\swimmer coco(validation)\kick_data(validation)\260622",
    r"E:\swimmer coco(validation)\kick_data(validation)\260624_IMU"
]
MODEL_PATH = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\best_1.pt"

def process_video(video_path):
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    dir_name = os.path.dirname(video_path)
    
    # Define target output paths
    smoothed_txt_path = os.path.join(dir_name, f"{base_name}_keypoints.txt")
    output_txt_path = os.path.join(dir_name, f"{base_name}_dive_info_angles.txt")
    output_json_path = os.path.join(dir_name, f"{base_name}_dive_info_angles.json")
    
    logging.info(f"[{base_name}] 開始處理影片...")
    
    # 1. 骨架預測 (Pose Estimation)
    try:
        # run_pose_estimation 會產生一個包含 _raw 後綴的 txt
        _, raw_txt = run_pose_estimation(MODEL_PATH, video_path, dir_name, save_video=False)
    except Exception as e:
        logging.error(f"[{base_name}] Pose estimation failed: {e}")
        return
        
    # 2. 骨架平滑化處理 (txt_base.py)
    try:
        process_keypoints_txt(raw_txt, save_final_output=True, final_output=smoothed_txt_path)
        logging.info(f"[{base_name}] 骨架平滑化完成: {smoothed_txt_path}")
    except Exception as e:
        logging.error(f"[{base_name}] Smoothing failed: {e}")
        return
        
    # 刪除暫存的 raw.txt，保持資料夾乾淨
    if os.path.exists(raw_txt):
        try:
            os.remove(raw_txt)
        except OSError:
            pass
            
    # 3. 潛泳與踢水角度分析
    try:
        res = analyze_diving_phase(video_path, smoothed_txt_path)
    except Exception as e:
        logging.error(f"[{base_name}] Diving analysis failed: {e}")
        return
        
    # 4. 產出 JSON 與美化後的 TXT
    json_data = {
        "video_name": base_name,
        "laps": []
    }
    
    txt_content = []
    txt_content.append("="*50)
    txt_content.append(f"影片分析報告: {base_name}")
    txt_content.append("="*50 + "\n")
    
    if "laps_data" in res:
        for idx, lap in enumerate(res["laps_data"]):
            lap_idx = idx + 1  # 重新編號：只算真正有游動的趟數，永遠從 1 開始
            trend = lap.get("trend", "unknown")
            s, e = lap.get("diving_segment") or (None, None)
            
            # 中文化方向
            direction_str = "去程" if trend == "decreasing" else "回程" if trend == "increasing" else trend
            
            lap_info = {
                "lap_index": lap_idx,
                "direction": trend,
                "diving_segment": {"start_frame": s, "end_frame": e},
                "kicks": []
            }
            
            txt_content.append(f"▶ 第 {lap_idx} 趟 ({direction_str})")
            
            if s is not None:
                txt_content.append(f"   [潛泳區間] Frame: {s} ~ {e}")
                
                frames = lap.get("angle_data", {}).get("minima_frames", [])
                angles = lap.get("angle_data", {}).get("minima_values", [])
                
                if frames and len(frames) > 0:
                    txt_content.append("   [踢水最小角度紀錄] (包含所有波谷)")
                    for fr, ang in zip(frames, angles):
                        lap_info["kicks"].append({"frame": int(fr), "angle_deg": float(ang)})
                        txt_content.append(f"      - Frame {int(fr):>4d} : 角度 {ang:.2f}°")
                else:
                    txt_content.append("   [踢水最小角度紀錄] 無有效踢水數據")
            else:
                txt_content.append(f"   [潛泳區間] 未偵測到有效的潛泳片段")
                
            txt_content.append("-" * 30)
            json_data["laps"].append(lap_info)
    else:
        txt_content.append("未偵測到完整的分析數據。")
        
    # 寫入 JSON
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
        
    # 寫入 TXT
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(txt_content))
        
    logging.info(f"[{base_name}] 分析報告產出完成: JSON & TXT\n")

if __name__ == "__main__":
    all_videos = []
    
    # 針對指定的每個資料夾進行搜尋
    for d in TARGET_DIRS:
        if not os.path.exists(d):
            logging.warning(f"資料夾不存在，略過: {d}")
            continue
            
        videos_in_dir = glob.glob(os.path.join(d, "**", "*.mp4"), recursive=True)
        videos_in_dir += glob.glob(os.path.join(d, "**", "*.avi"), recursive=True)
        all_videos.extend(videos_in_dir)
        
    if not all_videos:
        logging.warning("在所有指定的資料夾內皆找不到任何影片。")
        sys.exit(0)
        
    logging.info(f"總共找到 {len(all_videos)} 部影片準備處理...")
    for v in all_videos:
        process_video(v)
