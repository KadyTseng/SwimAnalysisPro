# SwimAnalysisPro/BD/stroke_analysis/backstroke_butterfly_stroke_waveform.py

import cv2
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter1d

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

def find_touch_frame(df, threshold=3800):
    max_frame = df['frame_id'].max()
    half_frame = max_frame // 2
    for _, row in df.iterrows():
        if row['frame_id'] >= half_frame:
            if row['x_center'] + row['width'] / 2 > threshold:
                return int(row['frame_id'])
    return None

def extract_stroke_segments(txt_path, video_path):
    df = read_txt(txt_path)
    waterline_y = detect_waterline_y(video_path)
    (s1, e1), (s2, e2) = find_submerged_segments(df, waterline_y)
    touch_frame = find_touch_frame(df)
    return e1, s2, e2, touch_frame, waterline_y

def extract_columns_in_range(txt_path, range1, range2):
    def parse_line(line):
        parts = line.strip().split()
        if len(parts) > 17:
            frame_id = int(parts[0])
            col10 = float(parts[10])
            col11 = float(parts[11])
            col16 = float(parts[16])
            col17 = float(parts[17])
            col19 = float(parts[19])
            return frame_id, col10, col11, col16, col17, col19
        return None

    range1_data = []
    range2_data = []
    with open(txt_path, 'r') as f:
        for line in f:
            parsed = parse_line(line)
            if parsed:
                frame_id, col10, col11, col16, col17, col19 = parsed
                if range1[0] <= frame_id <= range1[1]:
                    range1_data.append((frame_id, col10, col11, col16, col17, col19))
                elif range2[0] <= frame_id <= range2[1]:
                    range2_data.append((frame_id, col10, col11, col16, col17, col19))
    return {
        'range1': range1_data,
        'range2': range2_data
    }

def plot_intersection_from_smoothed(data_dict, smooth_size=10):
    intersection_result = {}
    for key, values in data_dict.items():
        frames = np.array([v[0] for v in values])
        col10s = np.array([v[1] for v in values])
        col16s = np.array([v[3] for v in values])
        col10s_smooth = uniform_filter1d(col10s, size=smooth_size)
        col16s_smooth = uniform_filter1d(col16s, size=smooth_size)
        diff = col10s_smooth - col16s_smooth
        sign_change = np.where(np.diff(np.sign(diff)) != 0)[0]
        intersection_frames = frames[sign_change]
        intersection_result[key] = intersection_frames.tolist()
    return intersection_result

from .backstroke_butterfly_stroke_phase_plot import plot_phase_on_col11_col17  # 分開管理 plot 實作

def run_backstroke_butterfly_analysis(txt_path: str, video_path: str):
    e1, s2, e2, touch_frame, waterline_y = extract_stroke_segments(txt_path, video_path)
    range1 = (e1, s2)
    range2 = (e2, touch_frame)
    data = extract_columns_in_range(txt_path, range1, range2)
    intersection_dict = plot_intersection_from_smoothed(data)
    plot_phase_on_col11_col17(data, intersection_dict, waterline_y)

# ====demo ====

def main():

    txt_path = r"D:\Kady\swimmer coco\anvanced stroke analysis\demo\Excellent_20230414_butterfly_M_3 (1)_1_smoothed.txt"
    video_path = r"D:\Kady\swimmer coco\anvanced stroke analysis\demo\Excellent_20230414_butterfly_M_3 (1).mp4"

    # 1. 自動偵測水面線
    waterline_y = detect_waterline_y(video_path)

    # 2. 讀取資料 + 找出潛泳區間 + 觸牆時間點
    df = read_txt(txt_path)
    (s1, e1), (s2, e2) = find_submerged_segments(df, waterline_y)
    touch_frame = find_touch_frame(df)

    # 3. 擷取有效分析段落
    range1 = (e1, s2)
    range2 = (e2, touch_frame)
    data = extract_columns_in_range(txt_path, range1, range2)

    # 4. 找交會點
    intersection_dict = plot_intersection_from_smoothed(data)

    # 5. 畫圖並標記推進/拉水/復原區段
    plot_phase_on_col11_col17(data, intersection_dict, waterline_y)


if __name__ == "__main__":
    main()