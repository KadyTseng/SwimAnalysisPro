import pandas as pd
import json

def extract_arm_trajectories(df_clean, laps_data, waterline_y):
    """
    從已經分析好的 laps_data 和 df_clean 中，提取各趟「游泳段」(swimming segment)的手腕、手肘、肩膀軌跡。
    水面 (waterline) 正規化為 Y=0。
    正規化 Y = Waterline_Y - Raw_Y (如此一來，水面上的點 Y > 0，水面下的點 Y < 0)。
    """
    arm_data = []

    for lap in laps_data:
        # 只取出游泳段 (Swimming Phase)
        if lap.get("swimming_segment") is None:
            continue
            
        s_swim, e_swim = lap["swimming_segment"]
        trend = lap["trend"]
        
        # 取出該游泳區段的資料
        df_swim = df_clean[(df_clean["frame_id"] >= s_swim) & (df_clean["frame_id"] <= e_swim)]
        
        if df_swim.empty:
            continue

        frames = df_swim["frame_id"].tolist()
        
        # X 座標維持相對畫面位置，或之後由前端依照泳道長度 (例如25m) 做 Mapping
        # Y 座標進行正規化: 水面為 0
        wrist_x = df_swim["wrist_x"].tolist()
        wrist_y = [float(waterline_y - y) for y in df_swim["wrist_y"].tolist()]
        
        elbow_x = df_swim["elbow_x"].tolist()
        elbow_y = [float(waterline_y - y) for y in df_swim["elbow_y"].tolist()]
        
        shoulder_x = df_swim["shoulder_x"].tolist()
        shoulder_y = [float(waterline_y - y) for y in df_swim["shoulder_y"].tolist()]
        
        arm_data.append({
            "lap_index": lap["lap_index"],
            "trend": trend,
            "start_frame": s_swim,
            "end_frame": e_swim,
            "trajectory": {
                "frames": frames,
                "wrist": {"x": wrist_x, "y": wrist_y},
                "elbow": {"x": elbow_x, "y": elbow_y},
                "shoulder": {"x": shoulder_x, "y": shoulder_y}
            }
        })
        
    return arm_data

def save_arm_trajectories_to_json(df_clean, laps_data, waterline_y, output_path):
    """
    計算手部軌跡並儲存為 JSON 檔案，讓前端可以直接抓取波型圖數據。
    """
    arm_data = extract_arm_trajectories(df_clean, laps_data, waterline_y)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(arm_data, f, ensure_ascii=False, indent=4)
        
    return arm_data
