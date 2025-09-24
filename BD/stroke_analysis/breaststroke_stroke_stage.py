import numpy as np
import cv2
from scipy.ndimage import uniform_filter1d
from .breaststroke_stroke_phase_plot import load_data_dict_from_txt, plot_phase_on_col11_col17

def read_txt(path):
    data = []
    with open(path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) > 20:
                try:
                    frame_id = int(parts[0])
                    x_center = float(parts[2])
                    width = float(parts[4])
                    head_y = float(parts[8])
                    data.append((frame_id, x_center, width, head_y))
                except:
                    continue
    import pandas as pd
    return pd.DataFrame(data, columns=['frame_id', 'x_center', 'width', 'head_y'])

def detect_waterline_y(video_path, lower_blue=(80, 50, 50), upper_blue=(140, 255, 255)):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("無法讀取影片")

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower_blue), np.array(upper_blue))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        waterline_y = np.min(max(contours, key=cv2.contourArea)[:, :, 1])

    else:
        raise RuntimeError("無法偵測水面線")
    print(waterline_y)
    return waterline_y

def find_submerged_segments(df, waterline_y, top_n=2):
    segments = []
    current = []
    for _, row in df.iterrows():
        if row['head_y'] >= waterline_y:
            current.append(row['frame_id'])
        else:
            if current:
                segments.append(current)
                current = []
    if current:
        segments.append(current)
    segments.sort(key=len, reverse=True)
    top_segments = segments[:top_n]
    top_segments.sort(key=lambda seg: seg[0])
    return [(seg[0], seg[-1]) for seg in top_segments]

# def find_touch_frame(df, threshold=3800):
#     max_frame = df['frame_id'].max()
#     half_frame = max_frame // 2
#     for _, row in df.iterrows():
#         if row['frame_id'] >= half_frame:
#             if row['x_center'] + row['width'] / 2 > threshold:
#                 return int(row['frame_id'])
#     return None
def find_touch_frame(df, video_width):
    """
    找觸牆幀：當 x_center + width/2 > video_width - 40
    """
    threshold = video_width - 40
    max_frame = df['frame_id'].max()
    half_frame = max_frame // 2
    for _, row in df.iterrows():
        if row['frame_id'] >= half_frame:
            if row['x_center'] + row['width'] / 2 > threshold:
                return int(row['frame_id'])
    return None
def calculate_angle(A, B, C):
    BA = np.array(A) - np.array(B)
    BC = np.array(C) - np.array(B)
    cosine_theta = np.dot(BA, BC) / (np.linalg.norm(BA) * np.linalg.norm(BC))
    angle = np.arccos(np.clip(cosine_theta, -1.0, 1.0)) * 180 / np.pi
    return angle

def process_range(txt_path, frame_range, slope_change, smooth_size=5, min_frame_gap=30):
    data = []
    with open(txt_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) > 19:
                frame_id = int(parts[0])
                if frame_range[0] <= frame_id <= frame_range[1]:
                    col7 = float(parts[7])
                    col8 = float(parts[8])
                    col10 = float(parts[10])
                    col11 = float(parts[11])
                    col13 = float(parts[13])
                    col14 = float(parts[14])
                    col16 = float(parts[16])
                    col17 = float(parts[17])
                    data.append((frame_id, col7, col8, col10, col11, col13, col14, col16, col17))

    frames = np.array([d[0] for d in data])
    shoulder_xy = [(d[3], d[4]) for d in data]
    elbow_xy = [(d[5], d[6]) for d in data]
    wrist_xy = [(d[7], d[8]) for d in data]
    head_y = np.array([d[2] for d in data])

    wrist_x = np.array([d[7] for d in data])
    wrist_y = np.array([d[8] for d in data])
    elbow_y = np.array([d[6] for d in data])
    shoulder_y = np.array([d[4] for d in data])

    wrist_x_smooth = uniform_filter1d(wrist_x, size=smooth_size)
    wrist_y_smooth = uniform_filter1d(wrist_y, size=smooth_size)
    elbow_y_smooth = uniform_filter1d(elbow_y, size=smooth_size)
    shoulder_y_smooth = uniform_filter1d(shoulder_y, size=smooth_size)

    stroke_angles = np.array([
        calculate_angle(shoulder_xy[i], elbow_xy[i], wrist_xy[i])
        for i in range(len(frames))
    ])
    stroke_angles_smooth = uniform_filter1d(stroke_angles, size=smooth_size)

    diff = np.diff(wrist_x_smooth)
    raw_start_frames = []

    if len(diff) > 0:
        if slope_change == 'neg2pos' and diff[0] > 0:
            raw_start_frames.append(frames[1])
        elif slope_change == 'pos2neg' and diff[0] < 0:
            raw_start_frames.append(frames[1])

    for i in range(1, len(diff)):
        if slope_change == 'neg2pos' and diff[i - 1] < 0 and diff[i] > 0:
            raw_start_frames.append(frames[i + 1])
        elif slope_change == 'pos2neg' and diff[i - 1] > 0 and diff[i] < 0:
            raw_start_frames.append(frames[i + 1])

    filtered_start_frames = []
    for f in raw_start_frames:
        if not filtered_start_frames or f - filtered_start_frames[-1] >= min_frame_gap:
            filtered_start_frames.append(f)

    end_frames = []
    for i in range(len(filtered_start_frames) - 1):
        start = filtered_start_frames[i]
        end = filtered_start_frames[i + 1]
        idx_range = np.where((frames >= start) & (frames <= end))[0]
        if len(idx_range) == 0:
            continue
        min_idx = idx_range[np.argmin(head_y[idx_range])]
        end_frames.append(frames[min_idx])

    recovery_end_frames = []
    for end_f in end_frames:
        idx_after_end = np.where(frames > end_f)[0]
        if len(idx_after_end) == 0:
            continue
        search_range = idx_after_end[:smooth_size * 3]
        if len(search_range) == 0:
            continue
        max_idx = search_range[np.argmax(stroke_angles_smooth[search_range])]
        recovery_end_frames.append(frames[max_idx])

    return frames, wrist_x_smooth, wrist_y_smooth, elbow_y_smooth, shoulder_y_smooth, head_y, stroke_angles_smooth, filtered_start_frames, end_frames, recovery_end_frames

import pandas as pd

def extract_stroke_segments(txt_path, video_path):
    df = read_txt(txt_path)
    waterline_y = detect_waterline_y(video_path)
    
    cap = cv2.VideoCapture(video_path)
    v_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()
    
    (s1, e1), (s2, e2) = find_submerged_segments(df, waterline_y)
    touch_frame = find_touch_frame(df,v_width)
    return e1, s2, e2, touch_frame, waterline_y

# if __name__ == "__main__":
#     import sys

#     # 預設路徑
#     default_txt_path = r"D:\Kady\swimmer coco\anvanced stroke analysis\demo\Excellent_20230414_breaststroke_F_3_1_smoothed.txt"
#     default_video_path = r"D:\Kady\swimmer coco\anvanced stroke analysis\demo\Excellent_20230414_breaststroke_F_3.mp4"

#     if len(sys.argv) >= 3:
#         txt_path = sys.argv[1]
#         video_path = sys.argv[2]
#     else:
#         print("未提供參數，使用預設路徑")
#         txt_path = default_txt_path
#         video_path = default_video_path

#     # 自動偵測水面線 y 座標
#     waterline_y = detect_waterline_y(video_path)

#     e1, s2, e2, touch_frame = extract_stroke_segments(txt_path, waterline_y)
    
#     range1 = (e1, s2)
#     range2 = (e2, touch_frame)
    
#     frames1, wrist_x1, wrist_y1, elbow_y1, shoulder_y1, head_y1, stroke_angle1, propulsion_starts1, propulsion_ends1, recovery_ends1 = process_range(txt_path, range1, 'neg2pos')
#     frames2, wrist_x2, wrist_y2, elbow_y2, shoulder_y2, head_y2, stroke_angle2, propulsion_starts2, propulsion_ends2, recovery_ends2 = process_range(txt_path, range2, 'pos2neg')

#     print("\n[Range1 - Slope Neg → Pos]")
#     print("Propulsion Starts (black dashed lines):", propulsion_starts1)
#     print("Propulsion Ends   (blue dashed lines):", propulsion_ends1)

#     print("\n[Range2 - Slope Pos → Neg]")
#     print("Propulsion Starts (black dotted lines):", propulsion_starts2)
#     print("Propulsion Ends   (blue dotted lines):", propulsion_ends2)
    
#     phase_frames_dict = {
#         'range1': {
#             "propulsion_starts": propulsion_starts1,
#             "propulsion_ends": propulsion_ends1,
#             "recovery_ends": recovery_ends1
#         },
#         'range2': {
#             "propulsion_starts": propulsion_starts2,
#             "propulsion_ends": propulsion_ends2,
#             "recovery_ends": recovery_ends2
#         }
#     }

#     data_dict = load_data_dict_from_txt(txt_path, range1, range2)
#     plot_phase_on_col11_col17(data_dict, phase_frames_dict, waterline_y)


import os
def run_analysis_for_folder(folder):
    txt_files = [f for f in os.listdir(folder) if f.endswith("_1.txt")]

    for txt_file in txt_files:
        txt_path = os.path.join(folder, txt_file)
        base_name = os.path.splitext(txt_file)[0].replace("_1", "")
        video_path = os.path.join(folder, base_name + ".mp4")
        output_txt = os.path.join(folder, base_name + ".a.txt")

        if not os.path.exists(video_path):
            print(f"⚠ 找不到影片 {video_path}, 跳過 {txt_file}")
            continue

        print(f"處理 {txt_file} 對應 {video_path}")

        # --- 讀取影片和標註 ---
        df = read_txt(txt_path)
        waterline_y = detect_waterline_y(video_path)
        cap = cv2.VideoCapture(video_path)
        v_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cap.release()

        segments = find_submerged_segments(df, waterline_y)
        if len(segments) < 2:
            print(f"⚠ {txt_file} 潛泳段不足兩段，跳過")
            continue
        (s1, e1), (s2, e2) = segments

        touch_frame = find_touch_frame(df, v_width)
        if None in (e1, s2, e2, touch_frame):
            print(f"⚠ {txt_file} 找不到完整階段，跳過")
            continue

        range1 = (e1, s2)
        range2 = (e2, touch_frame)
        if e1 >= s2 or e2 >= touch_frame:
            print(f"⚠ {txt_file} 範圍不正確，跳過")
            continue

        frames1, wrist_x1, wrist_y1, elbow_y1, shoulder_y1, head_y1, stroke_angle1, propulsion_starts1, propulsion_ends1, recovery_ends1 = process_range(txt_path, range1, 'neg2pos')
        frames2, wrist_x2, wrist_y2, elbow_y2, shoulder_y2, head_y2, stroke_angle2, propulsion_starts2, propulsion_ends2, recovery_ends2 = process_range(txt_path, range2, 'pos2neg')

        phase_frames_dict = {
            'range1': {"propulsion_starts": propulsion_starts1, "propulsion_ends": propulsion_ends1, "recovery_ends": recovery_ends1},
            'range2': {"propulsion_starts": propulsion_starts2, "propulsion_ends": propulsion_ends2, "recovery_ends": recovery_ends2}
        }

        data_dict = load_data_dict_from_txt(txt_path, range1, range2)
        phase_results = plot_phase_on_col11_col17(data_dict, phase_frames_dict, waterline_y)

        # 輸出
        with open(output_txt, "w", encoding="utf-8") as f:
            for key, regions in phase_results.items():
                f.write(f"\n{key} Phase Frames:\n")
                f.write(f"Propulsion regions: {regions['propulsion']}\n")
                f.write(f"Recovery regions:   {regions['recovery']}\n")
                f.write(f"Glide regions:      {regions['glide']}\n")

        print(f"✅ 已輸出結果到 {output_txt}")



# 假設這支是主程式
if __name__ == "__main__":
    folder = r"D:\Kady\swimmer coco\anvanced stroke analysis\stroke_stage\breaststroke"
    run_analysis_for_folder(folder)
