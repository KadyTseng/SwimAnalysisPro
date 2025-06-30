# BD/diving_analyzer_track_angles.py
import numpy as np
import pandas as pd
import cv2
from scipy.signal import argrelextrema

def read_and_clean_txt(path, expected_cols=12):
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
                    col8 = float(parts[8])  # 頭部 y 座標
                    data.append((frame_id, bbox_x, bbox_y, col8))
                except:
                    continue
    return pd.DataFrame(data, columns=['frame_id', 'bbox_x', 'bbox_y', 'col8'])

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

    # 保證區段按開始時間排序
    result.sort(key=lambda x: x[0])
    return result

def calculate_kick_angles(file_path, output_angle_path):
    """
    讀取骨架關鍵點 txt，計算踢腿膝蓋角度並輸出新檔案。
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    output_lines = []

    for line in lines:
        values = line.split()

        if len(values) > 0 and values[0].isdigit():
            frame_id = int(values[0])
        else:
            frame_id = -1

        if "no" in values or len(values) < 21:
            output_lines.append(f"{frame_id} \n")
            continue

        values = list(map(float, values))

        A = (values[19], values[20])   # 髖座標 (index=4)
        B = (values[22], values[23])   # 膝座標 (index=5)
        C = (values[25], values[26])   # 腳踝座標 (index=6)

        angle_1 = calculate_angle(A, B, C)
        angle_2 = calculate_angle(C, B, A)
        min_angle = min(angle_1, angle_2)

        new_line = f"{frame_id} {min_angle:.2f} {A[0]:.2f} {A[1]:.2f} {B[0]:.2f} {B[1]:.2f} {C[0]:.2f} {C[1]:.2f}\n"
        output_lines.append(new_line)

    with open(output_angle_path, "w", encoding="utf-8") as f:
        f.writelines(output_lines)

def find_local_min_angles(angle_txt_path, segment_start, segment_end, order=30):
    """
    從踢腿角度 txt 中找出指定區段的局部最小值（角度波谷）
    回傳當中局部最小的幀與角度列表 (frame_list, angle_list)
    """
    frame_ids = []
    angles = []

    with open(angle_txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        values = line.split()

        if len(values) >= 2:
            frameid = int(values[0])
            angle = float(values[1])
            frame_ids.append(frameid)
            angles.append(angle)

    start_idx = frame_ids.index(segment_start)
    end_idx = frame_ids.index(segment_end)

    sub_angles = np.array(angles[start_idx:end_idx+1])
    sub_frames = frame_ids[start_idx:end_idx+1]

    local_min_indices = argrelextrema(sub_angles, np.less, order=order)[0]

    local_min_frames = [sub_frames[i] for i in local_min_indices]
    local_min_values = [sub_angles[i] for i in local_min_indices]

    return local_min_frames, local_min_values

def draw_trajectory_on_video(
    video_path,
    df,
    output_path,
    segment_start,
    segment_end,
    line_color=(0,0,255),
    line_thickness=3
):
    """
    讀取影片與關節點資料，繪製指定潛泳區段 BBOX 軌跡，輸出新影片
    """
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
            x = int(row['bbox_x'].values[0])
            y = int(row['bbox_y'].values[0])

            if segment_start <= frame_id <= segment_end:
                track_points.append((x, y))

        for i in range(len(track_points) - 1):
            cv2.line(frame, track_points[i], track_points[i + 1], line_color, line_thickness)

        out.write(frame)
        frame_id += 1

    cap.release()
    out.release()

def analyze_diving_phase(
    video_path,
    keypoints_txt_path,
    output_angle_path,
    output_video_path,
    lower_blue=(80, 50, 50),
    upper_blue=(140, 255, 255)
):
    """
    結合整體流程：
    1. 讀影片首幀判斷水面水平線
    2. 讀取關節點資料，找出潛泳最大兩區段
    3. 計算踢腿角度，儲存角度 txt
    4. 找出潛泳區段局部最小角度(膝蓋踢腿波谷)
    5. 繪製潛泳軌跡並輸出影片
    
    回傳： 
    - largest_segments: [(s1,e1), (s2,e2)] 潛泳兩段
    - local_min_frames: 潛泳第一段局部最小角度幀列表
    - local_min_values: 潛泳第一段局部最小角度值列表
    """

    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError("Cannot read video frame.")

    waterline_y = detect_waterline_y(frame, lower_blue, upper_blue)
    if waterline_y is None:
        cap.release()
        raise RuntimeError("Cannot detect waterline.")

    df = read_and_clean_txt(keypoints_txt_path)

    largest_segments = find_largest_submerged_segments(df, waterline_y)

    calculate_kick_angles(keypoints_txt_path, output_angle_path)

    s1, e1 = largest_segments[0]

    local_min_frames, local_min_values = find_local_min_angles(output_angle_path, s1, e1)

    draw_trajectory_on_video(video_path, df, output_video_path, s1, e1)

    cap.release()

    return largest_segments, local_min_frames, local_min_values
