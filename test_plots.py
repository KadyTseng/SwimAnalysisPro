import sys
import os
import cv2
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# add paths
current_dir = '/home/kady6582/SwimAnalysisPro'
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from BD.diving_analyzer_track_angles import read_and_clean_txt, detect_waterline_y, analyze_diving_phase, calculate_kick_angles_from_txt, plot_kick_angle_waveform_with_lines_df
from BD.arm_trajectory_analyzer import extract_arm_trajectories

def get_depth_scale(video_path, txt_path):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    waterline_y, pool_bottom_y = detect_waterline_y(frame) if ret else (200, video_height)
    if not waterline_y: 
        waterline_y = int(video_height/4)
        pool_bottom_y = int(video_height * 3/4)
    
    # 深度轉換比例 (像素到cm)，以偵測出的藍色區域高度作為160cm的基準
    water_pixel_depth = pool_bottom_y - waterline_y
    cm_per_pixel = 160.0 / water_pixel_depth if water_pixel_depth > 0 else 1.0
    
    m_per_pixel_x = 25.0 / video_width if video_width > 0 else 1.0

    return video_width, video_height, waterline_y, pool_bottom_y, cm_per_pixel, m_per_pixel_x


def main():
    video_path = "/home/kady6582/SwimAnalysisPro/uploaded_videos/real_time_picture (116).mp4"
    txt_path = "/home/kady6582/SwimAnalysisPro/data/keypoints/real_time_picture (116).txt"
    output_dir = "/home/kady6582/SwimAnalysisPro/test_outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Running analyze_diving_phase...")
    try:
        from BD.diving_analyzer_track_angles import analyze_diving_phase
        res = analyze_diving_phase(video_path, txt_path)
    except Exception as e:
        print(f"Failed to run analysis: {e}")
        import traceback
        traceback.print_exc()
        return

    print("Retrieving depth scales...")
    v_w, v_h, waterline_y, pool_bottom_y, cm_per_pixel, m_per_pixel_x = get_depth_scale(video_path, txt_path)
    
    # 1. 畫上半身角度和踢腿角度畫在同一張圖上 (這部分其實 analyze_diving_phase 已經輸出，只要複製到 test_outputs 即可)
    if res.get("kick_angle_fig_1"):
        import shutil
        shutil.copy(res["kick_angle_fig_1"], f"{output_dir}/1_upper_and_kick_angle.png")
        print(f"Generated plot 1: {output_dir}/1_upper_and_kick_angle.png")
        
    df_clean = res["df_hip_data"]
    laps_data = res["laps_data"]
    
    def pixel_to_cm_h(y_pixel):
        # 水平為0, 水下為負
        return (waterline_y - y_pixel) * cm_per_pixel
    def pixel_to_m_w(x_pixel):
        return x_pixel * m_per_pixel_x

    # 2. 潛泳頭部與髖關節軌跡圖
    for lap in laps_data:
        if lap["diving_segment"]:
            s_d, e_d = lap["diving_segment"]
            df_dive = df_clean[(df_clean["frame_id"] >= s_d) & (df_clean["frame_id"] <= e_d)]
            
            x_hip = [pixel_to_m_w(x) for x in df_dive["hip_x"]]
            y_hip = [pixel_to_cm_h(y) for y in df_dive["hip_y"]]
            x_head = [pixel_to_m_w(x) for x in df_dive["head_x"]]
            y_head = [pixel_to_cm_h(y) for y in df_dive["col8"]]
            
            fig = plt.figure(figsize=(10, 5))
            plt.plot(x_hip, y_hip, label="Hip Trajectory", color='red')
            plt.plot(x_head, y_head, label="Head Trajectory", color='y')
            plt.axhline(y=0, color='blue', linestyle='--', label="Waterline (0 cm)")
            plt.axhline(y=-50, color='red', linestyle='--', label="50 cm Depth")
            plt.title(f"Diving Trajectory Lap {lap['lap_index']}")
            plt.xlabel("Distance (m)")
            plt.ylabel("Depth (cm)")
            
            # y軸範圍只要顯示水下160cm到水上160cm
            plt.ylim(-160, 160)
            plt.xlim(0, 25)
            plt.legend()
            
            plt.savefig(f"{output_dir}/2_diving_trajectory_lap{lap['lap_index']}.png")
            plt.close()
            print(f"Generated plot 2: {output_dir}/2_diving_trajectory_lap{lap['lap_index']}.png")
            break # only one lap needed for test
            
    # 3. 游泳段的三個手部軌跡
    arm_data = extract_arm_trajectories(df_clean, laps_data, waterline_y)
    if arm_data:
        # take the first available
        ad = arm_data[0]
        traj = ad["trajectory"]
        
        # normalize x and y
        x_wrist = [pixel_to_m_w(x) for x in traj["wrist"]["x"]]
        y_wrist = [y * cm_per_pixel for y in traj["wrist"]["y"]] # traj y is already waterline_y - y, just mult by scale. Note: arm_trajectory_analyzer normalizes Y = waterline_y - y_raw.
        
        x_elbow = [pixel_to_m_w(x) for x in traj["elbow"]["x"]]
        y_elbow = [y * cm_per_pixel for y in traj["elbow"]["y"]]
        
        x_shoulder = [pixel_to_m_w(x) for x in traj["shoulder"]["x"]]
        y_shoulder = [y * cm_per_pixel for y in traj["shoulder"]["y"]]

        fig = plt.figure(figsize=(10, 5))
        plt.plot(x_wrist, y_wrist, label="Wrist", color='blue')
        plt.plot(x_elbow, y_elbow, label="Elbow", color='green')
        plt.plot(x_shoulder, y_shoulder, label="Shoulder", color='red')
        plt.axhline(y=0, color='cyan', linestyle='--', label="Waterline (0 cm)")
        
        plt.title(f"Swimming Arm Trajectories Lap {ad['lap_index']}")
        plt.xlabel("Distance (m)")
        plt.ylabel("Depth (cm)")
        plt.ylim(-160, 160)
        plt.xlim(0, 25)
        plt.legend()
        
        plt.savefig(f"{output_dir}/3_swimming_arm_trajectory_lap{ad['lap_index']}.png")
        plt.close()
        print(f"Generated plot 3: {output_dir}/3_swimming_arm_trajectory_lap{ad['lap_index']}.png")

if __name__ == "__main__":
    main()
