# # BD/diving_analyzer_track_angles.py
# import numpy as np
# import pandas as pd
# import cv2
# from scipy.signal import argrelextrema

# def read_and_clean_txt(path, expected_cols=4):
#     """
#     讀取 keypoints txt ，只擷取 frame_id、bbox_x、bbox_y、頭部 y座標(col8)
#     """
#     data = []
#     with open(path, 'r') as f:
#         for line in f:
#             parts = line.strip().split()
#             if len(parts) >= expected_cols:
#                 try:
#                     frame_id = int(parts[0])
#                     bbox_x = float(parts[2])  
#                     bbox_y = float(parts[3])
#                     col8 = float(parts[8])
#                     hip_x = float(parts[19])  # 髖關節 x
#                     hip_y = float(parts[20])  # 髖關節 y
#                     data.append((frame_id, bbox_x, bbox_y, col8, hip_x, hip_y))
#                 except:
#                     continue
#     return pd.DataFrame(data, columns=['frame_id', 'bbox_x', 'bbox_y', 'col8', 'hip_x' , 'hip_y'])

# def calculate_angle(A, B, C):
#     """
#     計算三點 A-B-C 中點 B 的夾角 (度數)
#     """
#     BA = np.array(A) - np.array(B)
#     BC = np.array(C) - np.array(B)

#     cosine_theta = np.dot(BA, BC) / (np.linalg.norm(BA) * np.linalg.norm(BC))
#     angle = np.arccos(np.clip(cosine_theta, -1.0, 1.0)) * 180 / np.pi
#     return angle

# def detect_waterline_y(frame, lower_blue=(80, 50, 50), upper_blue=(140, 255, 255), morph_kernel_size=5):
#     """
#     根據影片第一幀，利用 HSV 色彩空間的藍色範圍偵測水面水平線 y 座標。
#     傳入彩色 BGR frame，回傳水面 y 座標 (int)。
#     """
#     hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
#     lower = np.array(lower_blue)
#     upper = np.array(upper_blue)
#     mask = cv2.inRange(hsv, lower, upper)

#     kernel = np.ones((morph_kernel_size, morph_kernel_size), np.uint8)
#     mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

#     contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

#     if contours:
#         largest_contour = max(contours, key=cv2.contourArea)
#         waterline_y = np.min(largest_contour[:, :, 1])
#         return waterline_y
#     else:
#         return None

# def find_largest_submerged_segments(df, waterline_y, top_n=2):
#     """
#     找出頭部 y 座標 >= 水面 y，且連續的最大 n 段區間。
#     回傳格式為 list，元素為 (start_frame, end_frame) tuple。
#     """
#     segments = []
#     current_segment = []
#     in_segment = False

#     for i, row in df.iterrows():
#         frameid = row['frame_id']
#         value = row['col8']

#         if value >= waterline_y:
#             if not in_segment:
#                 in_segment = True
#                 current_segment = [(frameid, value)]
#             else:
#                 current_segment.append((frameid, value))
#         else:
#             if in_segment:
#                 segments.append(current_segment)
#                 in_segment = False
#                 current_segment = []
#     if in_segment and current_segment:
#         segments.append(current_segment)

#     segment_lengths = [(segment, len(segment)) for segment in segments]
#     segment_lengths.sort(key=lambda x: x[1], reverse=True)
#     largest_segments = segment_lengths[:top_n]

#     result = []
#     for segment, length in largest_segments:
#         start_frame = segment[0][0]
#         end_frame = segment[-1][0]
#         result.append((start_frame, end_frame))

#     # 保證區段按開始時間排序
#     result.sort(key=lambda x: x[0])
#     return result

# def calculate_kick_angles(file_path, output_angle_path):
#     """
#     讀取骨架關鍵點 txt，計算踢腿膝蓋角度並輸出新檔案。
#     """
#     with open(file_path, "r", encoding="utf-8") as f:
#         lines = f.readlines()

#     output_lines = []

#     for line in lines:
#         values = line.split()

#         if len(values) > 0 and values[0].isdigit():
#             frame_id = int(values[0])
#         else:
#             frame_id = -1

#         if "no" in values or len(values) < 21:
#             output_lines.append(f"{frame_id} \n")
#             continue

#         values = list(map(float, values))

#         A = (values[19], values[20])   # 髖座標 (index=4)
#         B = (values[22], values[23])   # 膝座標 (index=5)
#         C = (values[25], values[26])   # 腳踝座標 (index=6)

#         angle_1 = calculate_angle(A, B, C)
#         angle_2 = calculate_angle(C, B, A)
#         min_angle = min(angle_1, angle_2)

#         new_line = f"{frame_id} {min_angle:.2f} {A[0]:.2f} {A[1]:.2f} {B[0]:.2f} {B[1]:.2f} {C[0]:.2f} {C[1]:.2f}\n"
#         output_lines.append(new_line)

#     with open(output_angle_path, "w", encoding="utf-8") as f:
#         f.writelines(output_lines)

# def find_local_min_angles(angle_txt_path, segment_start, segment_end, order=30):
#     """
#     從踢腿角度 txt 中找出指定區段的局部最小值（角度波谷）
#     回傳當中局部最小的幀與角度列表 (frame_list, angle_list)
#     """
#     frame_ids = []
#     angles = []

#     with open(angle_txt_path, "r", encoding="utf-8") as f:
#         lines = f.readlines()

#     for line in lines:
#         values = line.split()

#         if len(values) >= 2:
#             frameid = int(values[0])
#             angle = float(values[1])
#             frame_ids.append(frameid)
#             angles.append(angle)

#     start_idx = frame_ids.index(segment_start)
#     end_idx = frame_ids.index(segment_end)

#     sub_angles = np.array(angles[start_idx:end_idx+1])
#     sub_frames = frame_ids[start_idx:end_idx+1]

#     local_min_indices = argrelextrema(sub_angles, np.less, order=order)[0]

#     local_min_frames = [sub_frames[i] for i in local_min_indices]
#     local_min_values = [sub_angles[i] for i in local_min_indices]

#     return local_min_frames, local_min_values

# def draw_trajectory_on_video(
#     video_path,
#     df,
#     output_path,
#     segment_start,
#     segment_end,
#     line_color=(0,0,255),
#     line_thickness=3
# ):
#     """
#     讀取影片與關節點資料，繪製指定潛泳區段 BBOX 軌跡，輸出新影片
#     """
#     cap = cv2.VideoCapture(video_path)
#     fps = cap.get(cv2.CAP_PROP_FPS)
#     width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#     fourcc = cv2.VideoWriter_fourcc(*'mp4v')  
#     out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

#     track_points = []
#     frame_id = 0


#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             break

#         row = df[df['frame_id'] == frame_id]

#         if not row.empty:
#             x = int(row['hip_x'].values[0])
#             y = int(row['hip_y'].values[0])
            
#             if segment_start <= frame_id <= segment_end:
#                 track_points.append((x, y))

#         for i in range(len(track_points) - 1):
#             cv2.line(frame, track_points[i], track_points[i + 1], line_color, line_thickness)

#         out.write(frame)
#         frame_id += 1

#     cap.release()
#     out.release()

# def analyze_diving_phase(
#     video_path,
#     keypoints_txt_path,
#     output_angle_path,
#     output_video_path,
#     lower_blue=(80, 50, 50),
#     upper_blue=(140, 255, 255)
# ):
#     """
#     結合整體流程：
#     1. 讀影片首幀判斷水面水平線
#     2. 讀取關節點資料，找出潛泳最大兩區段
#     3. 計算踢腿角度，儲存角度 txt
#     4. 找出潛泳區段局部最小角度(膝蓋踢腿波谷)
#     5. 繪製潛泳軌跡並輸出影片
    
#     回傳： 
#     - largest_segments: [(s1,e1), (s2,e2)] 潛泳兩段
#     - local_min_frames: 潛泳第一段局部最小角度幀列表
#     - local_min_values: 潛泳第一段局部最小角度值列表
#     """
#     # 1. 抓影片第一幀判斷水面
#     cap = cv2.VideoCapture(video_path)
#     ret, frame = cap.read()
#     if not ret:
#         cap.release()
#         raise RuntimeError("Cannot read video frame.")

#     waterline_y = detect_waterline_y(frame, lower_blue, upper_blue)
#     if waterline_y is None:
#         cap.release()
#         raise RuntimeError("Cannot detect waterline.")
    
#     # 2. 讀關節點資料（簡版用於找潛泳）
#     df_clean = read_and_clean_txt(keypoints_txt_path)
    
#     # 3. 找出兩段潛泳區段
#     largest_segments = find_largest_submerged_segments(df_clean, waterline_y)

#     # 4. 計算踢腿角度並輸出
#     calculate_kick_angles(keypoints_txt_path, output_angle_path)
    
#     # 5. 針對第一段找踢腿最小角度幀
#     s1, e1 = largest_segments[0]

#     local_min_frames, local_min_values = find_local_min_angles(output_angle_path, s1, e1)
    
#     # 6. 用完整骨架資料畫髖關節軌跡
#     df_full =read_and_clean_txt(keypoints_txt_path)
#     draw_trajectory_on_video(video_path, df_full, output_video_path, s1, e1)

#     cap.release()

#     return largest_segments, local_min_frames, local_min_values


# 要試試看行不行
# BD/diving_analyzer_track_angles.py

import os
import numpy as np
import pandas as pd
import cv2
import matplotlib.pyplot as plt
from scipy.signal import argrelextrema

def read_and_clean_txt(path, expected_cols=4):
    """
    讀取 keypoints txt ，只擷取 frame_id、bbox_x、bbox_y、頭部 y座標(col8)
    """
    data = []
    with open(path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= expected_cols:
                try:
                    frame_id = int(parts[0])
                    bbox_x = float(parts[2])  
                    bbox_y = float(parts[3])
                    col8 = float(parts[8])
                    hip_x = float(parts[19])  # 髖關節 x
                    hip_y = float(parts[20])  # 髖關節 y
                    data.append((frame_id, bbox_x, bbox_y, col8, hip_x, hip_y))
                except:
                    continue
    return pd.DataFrame(data, columns=['frame_id', 'bbox_x', 'bbox_y', 'col8', 'hip_x' , 'hip_y'])

def calculate_angle(A, B, C):
    """
    計算三點 A-B-C 中點 B 的夾角 (度數)
    """
    BA = np.array(A) - np.array(B)
    BC = np.array(C) - np.array(B)

    cosine_theta = np.dot(BA, BC) / (np.linalg.norm(BA) * np.linalg.norm(BC))
    angle = np.arccos(np.clip(cosine_theta, -1.0, 1.0)) * 180 / np.pi
    return angle

def detect_waterline_y(frame, lower_blue=(80, 50, 50), upper_blue=(140, 255, 255), morph_kernel_size=5):
    """
    根據影片第一幀，利用 HSV 色彩空間的藍色範圍偵測水面水平線 y 座標。
    傳入彩色 BGR frame，回傳水面 y 座標 (int)。
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array(lower_blue)
    upper = np.array(upper_blue)
    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((morph_kernel_size, morph_kernel_size), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        waterline_y = np.min(largest_contour[:, :, 1])
        return waterline_y
    else:
        return None

def find_largest_submerged_segments(df, waterline_y, top_n=2):
    """
    找出頭部 y 座標 >= 水面 y，且連續的最大 n 段區間。
    回傳格式為 list，元素為 (start_frame, end_frame) tuple。
    """
    segments = []
    current_segment = []
    in_segment = False

    for i, row in df.iterrows():
        frameid = row['frame_id']
        value = row['col8']

        if value >= waterline_y:
            if not in_segment:
                in_segment = True
                current_segment = [(frameid, value)]
            else:
                current_segment.append((frameid, value))
        else:
            if in_segment:
                segments.append(current_segment)
                in_segment = False
                current_segment = []
    if in_segment and current_segment:
        segments.append(current_segment)

    segment_lengths = [(segment, len(segment)) for segment in segments]
    segment_lengths.sort(key=lambda x: x[1], reverse=True)
    largest_segments = segment_lengths[:top_n]

    result = []
    for segment, length in largest_segments:
        start_frame = segment[0][0]
        end_frame = segment[-1][0]
        result.append((start_frame, end_frame))

    result.sort(key=lambda x: x[0])
    return result

def get_diving_swimming_segments(video_path, df, top_n=2):   #之後top_n可以彈性 
    """
    從影片抓水面，並用骨架 df 找出潛泳/游泳區間。
    
    參數:
        video_path: 影片路徑
        df: 已整理好的骨架 DataFrame (frame_id, bbox_x, bbox_y, col8, hip_x, hip_y)
        top_n: 取前 n 段潛泳連續區段
    
    回傳:
        waterline_y: 水面水平線 y 座標
        (s1, e1): 潛泳段第一段 (起始 frame, 結束 frame)
        (s2, e2): 潛泳段第二段或游泳段 (起始 frame, 結束 frame)，若不存在回傳 None
    """
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("影片無法讀取")

    waterline_y = detect_waterline_y(frame)
    if waterline_y is None:
        raise RuntimeError("水面偵測失敗")

    segments = find_largest_submerged_segments(df, waterline_y, top_n=top_n)

    if len(segments) >= 2:
        (s1, e1), (s2, e2) = segments
    elif len(segments) == 1:
        (s1, e1) = segments[0]
        s2, e2 = None, None
    else:
        s1, e1, s2, e2 = None, None, None, None

    return waterline_y, (s1, e1), (s2, e2)

def calculate_kick_angles_from_txt(file_path):
    """
    讀取骨架關鍵點 txt，計算踢腿膝蓋角度，直接回傳 dataframe
    不輸出檔案
    """
    angles_data = []

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        values = line.split()
        if len(values) > 0 and values[0].isdigit():
            frame_id = int(values[0])
        else:
            frame_id = -1

        if "no" in values or len(values) < 21:
            angles_data.append((frame_id, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan))
            continue

        values = list(map(float, values))

        A = (values[19], values[20])   # 髖座標
        B = (values[22], values[23])   # 膝座標
        C = (values[25], values[26])   # 腳踝座標

        angle_1 = calculate_angle(A, B, C)
        angle_2 = calculate_angle(C, B, A)
        min_angle = min(angle_1, angle_2)

        angles_data.append((frame_id, min_angle, A[0], A[1], B[0], B[1], C[0], C[1]))

    df_angles = pd.DataFrame(
        angles_data,
        columns=['frame_id', 'angle', 'A_x', 'A_y', 'B_x', 'B_y', 'C_x', 'C_y']
    )
    return df_angles

def find_local_min_angles_df(df_angles, segment_start, segment_end, order=30):
    """
    從踢腿角度 dataframe 中找出指定區段的局部最小值（角度波谷）
    """
    sub_df = df_angles[(df_angles['frame_id'] >= segment_start) & (df_angles['frame_id'] <= segment_end)]
    angles = sub_df['angle'].values
    frames = sub_df['frame_id'].values

    if len(angles) >= 3:
        local_min_indices = argrelextrema(angles, np.less, order=order)[0]
    else:
        local_min_indices = np.array([], dtype=int)
    filtered_indices = [i for i in local_min_indices if angles[i] <= 140]

    local_min_frames = frames[filtered_indices]
    local_min_angles = angles[filtered_indices]

    return local_min_frames.tolist(), local_min_angles.tolist()

def draw_trajectory_on_video(video_path, df, output_path, segment_start, segment_end, line_color=(0,0,255), line_thickness=3):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    track_points = []
    frame_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        row = df[df['frame_id'] == frame_id]

        if not row.empty:
            x = int(row['hip_x'].values[0])
            y = int(row['hip_y'].values[0])
            
            if segment_start <= frame_id <= segment_end:
                track_points.append((x, y))

        for i in range(len(track_points) - 1):
            cv2.line(frame, track_points[i], track_points[i + 1], line_color, line_thickness)

        out.write(frame)
        frame_id += 1

    cap.release()
    out.release()

def plot_kick_angle_waveform_with_lines_df(df_angles, keypoints_txt_path,
                                        segment_start, segment_end, phase_name,
                                        draw_aux_lines=True, crop_from_ankle_min=False,
                                        total_distance=25.0):
    # ===== 取指定區段 =====
    sub_df = df_angles[(df_angles['frame_id'] >= segment_start) & (df_angles['frame_id'] <= segment_end)]
    frames = sub_df['frame_id'].values
    angles = sub_df['angle'].values

    # ===== 讀 keypoints =====
    keypoints = np.loadtxt(keypoints_txt_path)
    k_frames_all = keypoints[:, 0].astype(int)
    ankle_x_all = keypoints[:, 25]

    k_mask = (k_frames_all >= segment_start) & (k_frames_all <= segment_end)
    k_frames = k_frames_all[k_mask]
    ankle_x = ankle_x_all[k_mask]

    # ===== 找 ankle 最小值幀 =====
    ankle_min_frame = int(k_frames[np.argmin(ankle_x)]) if len(k_frames) > 0 else None

    # ===== 從 ankle 最小值開始裁切 =====
    if crop_from_ankle_min and (ankle_min_frame is not None):
        mask = frames >= ankle_min_frame
        frames = frames[mask]
        angles = angles[mask]

    # ===== 找局部最小值 & 過濾 ≤140° =====
    if len(angles) >= 3:
        local_min_indices = argrelextrema(angles, np.less)[0]
    else:
        local_min_indices = np.array([], dtype=int)
    filtered_indices = [i for i in local_min_indices if angles[i] <= 140]
    filtered_frames = frames[filtered_indices]
    filtered_angles = angles[filtered_indices]

    # ===== 計算距離比例 (frame → m) =====
    distance_per_frame = total_distance / (frames[-1] - frames[0]) if len(frames) > 1 else 0.0
    filtered_distances = (filtered_frames - frames[0]) * distance_per_frame if len(filtered_frames) > 0 else np.array([])

    # ===== 畫圖 =====
    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(frames, angles, label="Kick Angle")
    ax1.scatter(filtered_frames, filtered_angles, color='red', label='Minimum')
    for x, y in zip(filtered_frames, filtered_angles):
        ax1.text(x, y - 5, f"{y:.1f}", fontsize=9, color='black', ha='center')

    ax1.set_xlabel("Frame")
    ax1.set_ylabel("Angle (degrees)")
    ax1.grid(True)

    ax2 = ax1.twiny()
    ax2.set_xlim(ax1.get_xlim())
    ax2.set_xticks([])
    ax2.set_xlabel("Distance (m)")

    if len(filtered_frames) >= 2 and distance_per_frame > 0:
        tick_positions = []
        tick_labels = []
        for i in range(len(filtered_frames) - 1):
            f1 = filtered_frames[i]
            f2 = filtered_frames[i + 1]
            dist_m = (f2 - f1) * distance_per_frame
            mid_frame = (f1 + f2) / 2.0
            tick_positions.append(mid_frame)
            tick_labels.append(f"{dist_m:.2f}")
        ax2.set_xticks(tick_positions)
        ax2.set_xticklabels(tick_labels, color="black")

    #if draw_aux_lines and (ankle_min_frame is not None):
       # ax1.axvline(x=ankle_min_frame, color='green', linestyle='--', label=f"Ankle min @ {ankle_min_frame}")

    filename = "unknown"
    ax1.set_title(f"{filename} Kick Angle Waveform ({phase_name})")
    ax1.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), borderaxespad=0.)
    plt.tight_layout()
    plt.show()


def analyze_diving_phase(video_path, keypoints_txt_path, output_video_path=None, lower_blue=(80,50,50), upper_blue=(140,255,255)):
    """
    主流程修改後，不再輸出 kickangle txt，直接使用 dataframe 計算
    """
    # 1. 水面
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError("Cannot read video frame.")
    waterline_y = detect_waterline_y(frame, lower_blue, upper_blue)
    if waterline_y is None:
        cap.release()
        raise RuntimeError("Cannot detect waterline.")
    cap.release()

    # 2. 讀取簡版 keypoints
    df_clean = read_and_clean_txt(keypoints_txt_path)
    largest_segments = find_largest_submerged_segments(df_clean, waterline_y)

    # 3. 計算踢腿角度 dataframe
    df_angles = calculate_kick_angles_from_txt(keypoints_txt_path)

    # 4. 找局部最小值
    s1, e1 = largest_segments[0]
    s2, e2 = largest_segments[1] if len(largest_segments) > 1 else (None, None)
    # === 新增：檢查 s1 腳踝 X 是否 < 3790，否則往後找 ===
    keypoints = np.loadtxt(keypoints_txt_path)
    frames_all = keypoints[:, 0].astype(int)
    ankle_x_all = keypoints[:, 25]   # 腳踝 X

    # 過濾出在 [s1, e1] 區段的幀
    mask = (frames_all >= s1) & (frames_all <= e1)
    frames_in_seg = frames_all[mask]
    ankle_x_in_seg = ankle_x_all[mask]

    # 找第一個 ankle_x < 3790 的幀
    valid_idx = np.where(ankle_x_in_seg < 3790)[0]
    if len(valid_idx) > 0:
        s1 = frames_in_seg[valid_idx[0]]   # 更新 s1
        
    local_min_frames1, local_min_values1 = find_local_min_angles_df(df_angles, s1, e1)
    if s2 is not None:
        local_min_frames2, local_min_values2 = find_local_min_angles_df(df_angles, s2, e2)
    else:
        local_min_frames2, local_min_values2 = None, None

    # # 5. 畫軌跡影片
    # if output_video_path is not None:
    #     df_full = read_and_clean_txt(keypoints_txt_path)
    #     draw_trajectory_on_video(video_path, df_full, output_video_path, s1, e1)

    # 6. 畫踢腿角度波型
    plot_kick_angle_waveform_with_lines_df(df_angles, keypoints_txt_path, s1, e1, "Phase 1", draw_aux_lines=False)
    if s2 is not None:
        plot_kick_angle_waveform_with_lines_df(df_angles, keypoints_txt_path, s2, e2, "Phase 2", draw_aux_lines=True, crop_from_ankle_min=True)

    return largest_segments, (local_min_frames1, local_min_values1), (local_min_frames2, local_min_values2)


# DEMO
analyze_diving_phase(
    video_path=r"D:\Kady\swimmer coco\kick_data\new\champ\real_time_picture_19.mp4",
    keypoints_txt_path=r"D:\Kady\swimmer coco\kick_data\new\champ\real_time_picture_19_1.txt",
    output_video_path=None
)