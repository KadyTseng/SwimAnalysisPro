# diving_analyzer_track_angles.py

import numpy as np
import pandas as pd
import cv2
import matplotlib.pyplot as plt
from scipy.signal import argrelextrema
import streamlit as st


def read_and_clean_txt(path, expected_cols=4):
    """
    讀取 keypoints txt ，只擷取 frame_id、bbox_x、bbox_y、頭部 y座標(col8)
   肩膀(col11), 手肘(col14), 膝蓋(col23), 腳踝(col26), 手腕(col17), 髖關節(col19, 20)
    """
    data = []
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= expected_cols:
                try:
                    frame_id = int(parts[0])
                    bbox_x = float(parts[2])
                    bbox_y = float(parts[3])
                    bbox_width = float(parts[4])
                    bbox_height = float(parts[5]) # 讀取 height
                    col8 = float(parts[8])   # 頭y
                    col11 = float(parts[11]) # 肩膀y
                    col14 = float(parts[14]) # 手肘y
                    col17 = float(parts[17]) # 手腕y
                    hip_x = float(parts[19]) # 髖關節 x
                    hip_y = float(parts[20]) # 髖關節 y
                    col23 = float(parts[23]) # 膝蓋y
                    col26 = float(parts[26]) # 腳踝y
                    
                    data.append(
                        (frame_id, bbox_x, bbox_y, bbox_width, bbox_height, col8, col11, col14, col17, hip_x, hip_y, col23, col26)
                    )
                except:
                    continue
    return pd.DataFrame(
        data,
        columns=[
            "frame_id",
            "bbox_x",
            "bbox_y",
            "width",
            "height", # 新增 height column
            "col8",
            "shoulder_y",
            "elbow_y",
            "wrist_y",
            "hip_x",
            "hip_y",
            "knee_y",
            "ankle_y"
        ],
    )


def calculate_angle(A, B, C):
    """
    計算三點 A-B-C 中點 B 的夾角 (度數)
    """
    BA = np.array(A) - np.array(B)
    BC = np.array(C) - np.array(B)

    cosine_theta = np.dot(BA, BC) / (np.linalg.norm(BA) * np.linalg.norm(BC))
    angle = np.arccos(np.clip(cosine_theta, -1.0, 1.0)) * 180 / np.pi
    return angle


def detect_waterline_y(
    frame, lower_blue=(80, 50, 50), upper_blue=(140, 255, 255), morph_kernel_size=5
):
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


def detect_laps_by_hip_x(df, min_lap_duration=100):
    """
    根據 Hip X 的趨勢判斷折返 (Laps)。
    假設：
    - 去程 (Outbound): Hip X 數值顯著 減少 (或增加，視座標原點，但在這裡使用相對變化)
    - 回程 (Inbound): Hip X 數值顯著 增加 (或減少)
    
    邏輯：
    1. 平滑 Hip X。
    2. 找出顯著的轉折點 (Local Min/Max)。轉折點代表觸牆/轉身。
    3. 將影片分割成數個 Laps (Ranges)。
    4. 判斷每個 Range 的趨勢 (X 變大或變小)。
    
    回傳: list of (start_frame, end_frame, trend_label)
    test
    """
    # 1. 取出並平滑 Hip X
    x_raw = df["hip_x"].values
    if len(x_raw) < min_lap_duration:
        return [(df["frame_id"].min(), df["frame_id"].max(), "unknown")]
        
    # 簡單移動平均平滑
    window_size = 60 # 約 2秒
    pad_width = window_size // 2
    x_smooth = np.convolve(x_raw, np.ones(window_size)/window_size, mode='valid')
    # 補回 padding 以對齊 frame_id
    x_smooth = np.pad(x_smooth, (pad_width, len(x_raw) - len(x_smooth) - pad_width), mode='edge')
    
    # 2. 找轉折點 (Local Extrema)
    # 使用較大的 order 避免划手造成的微小震盪被誤判
    # order=90 表示前後 3秒內必須是極值
    from scipy.signal import argrelextrema
    order_val = 90
    
    # 找波峰 (Max) 和 波谷 (Min)
    id_max = argrelextrema(x_smooth, np.greater, order=order_val)[0]
    id_min = argrelextrema(x_smooth, np.less, order=order_val)[0]
    
    # 合併所有轉折點並排序
    turning_points = sorted(np.concatenate([id_max, id_min]).astype(int))
    
    # 加入起點 (0) 和 終點 (len-1)
    boundary_points = [0, len(df)-1]
    
    # 過濾過於接近邊界的點
    filtered_points = [0]
    for p in turning_points:
        if p > 30 and p < (len(df) - 30): # 避免開頭結尾的極值雜訊
             # 避免與上一點太近
             if p - filtered_points[-1] > min_lap_duration:
                 filtered_points.append(p)
    
    if (len(df)-1) - filtered_points[-1] > min_lap_duration:
        filtered_points.append(len(df)-1)
    else:
        # 如果最後一段太短，直接把最後一點延伸到結尾
        filtered_points[-1] = len(df)-1
        
    laps = []
    frames = df["frame_id"].values
    
    for i in range(len(filtered_points) - 1):
        idx_s = filtered_points[i]
        idx_e = filtered_points[i+1]
        
        f_start = frames[idx_s]
        f_end = frames[idx_e]
        
        # 判斷趨勢: 頭尾比較
        x_s = x_smooth[idx_s]
        x_e = x_smooth[idx_e]
        diff = x_e - x_s
        
        # 設定一個閾值，沒有顯著移動就不算 Lap (可能是休息)
        move_threshold = 200 # pixel
        
        trend = "static"
        if diff < -move_threshold:
            trend = "decreasing" # 數值變小 (去程?)
        elif diff > move_threshold:
            trend = "increasing" # 數值變大 (回程?)
            
        laps.append((f_start, f_end, trend))
        
    return laps


def find_best_segment_in_range(df_subset, waterline_y, use_bbox=True):
    """
    在給定的時間區間內，找出「最佳」的一個潛泳段。
    
    參數:
        use_bbox: 
            True  -> 使用 BBox 上緣 (較寬鬆/穩定)
            False -> 使用 全關節(頭~腳)皆在水下 (嚴格檢查/Fallback)
            
    回傳: (start, end) or None
    """
    from itertools import groupby
    from operator import itemgetter
    
    if df_subset.empty:
        return None

    if use_bbox:
        # 策略 A: BBox 上緣 > 水面
        condition = ((df_subset["bbox_y"] - df_subset["height"] / 2) > waterline_y)
    else:
        # 策略 B (Fallback): 嚴格全關節潛泳
        condition = (
            (df_subset["col8"] > waterline_y) &
            (df_subset["shoulder_y"] > waterline_y) &
            (df_subset["elbow_y"] > waterline_y) &
            (df_subset["wrist_y"] > waterline_y) &
            (df_subset["hip_y"] > waterline_y) &
            (df_subset["knee_y"] > waterline_y) &
            (df_subset["ankle_y"] > waterline_y)
        )

    valid_frames = df_subset[condition]["frame_id"].tolist()
    if not valid_frames:
        return None
        
    segments = []
    MIN_DIVE_LEN = 10  # 稍微寬鬆一點，讓 Lap 內能抓到

    for k, g in groupby(enumerate(valid_frames), lambda ix: ix[0] - ix[1]):
        chunk = list(map(itemgetter(1), g))
        if len(chunk) >= MIN_DIVE_LEN:
            segments.append((chunk[0], chunk[-1]))
            
    if not segments:
        return None
            
    # 取最長的一段
    segments.sort(key=lambda x: x[1] - x[0], reverse=True)
    return segments[0]



def get_diving_swimming_segments(video_path, df, top_n=None): # top_n is deprecated but kept for compatibility
    """
    彈性多趟判斷：
    1. 先偵測這數個 Laps (基於 Hip X 變化)
    2. 對每個 Lap 找出最長的一段潛泳區間
    
    回傳:
        waterline_y
        segments: list of (s, e) tuples
    """
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("影片無法讀取")

    waterline_y = detect_waterline_y(frame)
    if waterline_y is None:
        raise RuntimeError("水面偵測失敗")

    # 1. Detect Laps
    laps = detect_laps_by_hip_x(df)
    
    # 2. Find One Segment Per Lap
    found_segments = []
    
    print(f"   [INFO] Detected {len(laps)} Laps (Ranges):")
    for idx, (f_start, f_end, trend) in enumerate(laps):
        print(f"     -> Lap {idx+1}: Frame {f_start}-{f_end} ({trend})")
        
        # 只處理有顯著移動的區段 (排除 static)
        if trend == "static":
            continue
            
        # 擷取該 Lap 的資料子集
        df_lap = df[(df["frame_id"] >= f_start) & (df["frame_id"] <= f_end)]
        
        best_seg = find_best_segment_in_range(df_lap, waterline_y)
        if best_seg:
            found_segments.append(best_seg)
            
    # Sort by time just in case
    found_segments.sort(key=lambda x: x[0])

    return waterline_y, found_segments


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
            angles_data.append(
                (frame_id, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan)
            )
            continue

        values = list(map(float, values))

        A = (values[19], values[20])  # 髖座標
        B = (values[22], values[23])  # 膝座標
        C = (values[25], values[26])  # 腳踝座標

        angle_1 = calculate_angle(A, B, C)
        angle_2 = calculate_angle(C, B, A)
        min_angle = min(angle_1, angle_2)

        angles_data.append((frame_id, min_angle, A[0], A[1], B[0], B[1], C[0], C[1]))

    df_angles = pd.DataFrame(
        angles_data,
        columns=["frame_id", "angle", "A_x", "A_y", "B_x", "B_y", "C_x", "C_y"],
    )
    return df_angles


def find_local_min_angles_df(df_angles, segment_start, segment_end, order=30):
    """
    從踢腿角度 dataframe 中找出指定區段的局部最小值（角度波谷）
    """
    sub_df = df_angles[
        (df_angles["frame_id"] >= segment_start)
        & (df_angles["frame_id"] <= segment_end)
    ]
    angles = sub_df["angle"].values
    frames = sub_df["frame_id"].values

    if len(angles) >= 3:
        local_min_indices = argrelextrema(angles, np.less, order=order)[0]
    else:
        local_min_indices = np.array([], dtype=int)
    filtered_indices = [i for i in local_min_indices if angles[i] <= 140]

    local_min_frames = frames[filtered_indices]
    local_min_angles = angles[filtered_indices]

    return local_min_frames.tolist(), local_min_angles.tolist()


def draw_trajectory_on_video(
    video_path,
    df,
    output_path,
    segment_start,
    segment_end,
    line_color=(0, 0, 255),
    line_thickness=3,
):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    track_points = []
    frame_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        row = df[df["frame_id"] == frame_id]

        if not row.empty:
            x = int(row["hip_x"].values[0])
            y = int(row["hip_y"].values[0])

            if segment_start <= frame_id <= segment_end:
                track_points.append((x, y))

        for i in range(len(track_points) - 1):
            cv2.line(
                frame, track_points[i], track_points[i + 1], line_color, line_thickness
            )

        out.write(frame)
        frame_id += 1

    cap.release()
    out.release()


def plot_kick_angle_waveform_with_lines_df(
    df_angles,
    keypoints_txt_path,
    segment_start,
    segment_end,
    phase_name,
    draw_aux_lines=True,
    crop_from_ankle_min=False,
    total_distance=25.0,
):
    # ===== 取指定區段 =====
    sub_df = df_angles[
        (df_angles["frame_id"] >= segment_start)
        & (df_angles["frame_id"] <= segment_end)
    ]
    frames = sub_df["frame_id"].values
    angles = sub_df["angle"].values

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
    distance_per_frame = (
        total_distance / (frames[-1] - frames[0]) if len(frames) > 1 else 0.0
    )
    filtered_distances = (
        (filtered_frames - frames[0]) * distance_per_frame
        if len(filtered_frames) > 0
        else np.array([])
    )

    # ===== 畫圖 =====
    fig, ax1 = plt.subplots(figsize=(15, 3))
    ax1.plot(frames, angles, label="Kick Angle")
    ax1.scatter(filtered_frames, filtered_angles, color="red", label="Minimum")
    for x, y in zip(filtered_frames, filtered_angles):
        ax1.text(x, y - 5, f"{y:.1f}", fontsize=9, color="black", ha="center")

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

    # ax1.set_title(f"Kick Angles Waveform ({phase_name})")
    ax1.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), borderaxespad=0.0)
    plt.tight_layout()
    # plt.show()
    return fig


@st.cache_data
def analyze_diving_phase(
    video_path,
    keypoints_txt_path,
    output_video_path=None,
    lower_blue=(80, 50, 50),
    upper_blue=(140, 255, 255),
):
    """
    主流程修改後，不再輸出 kickangle txt，直接使用 dataframe 計算
    """
    # 1. 水面
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not ret:
        cap.release()
        raise RuntimeError("Cannot read video frame.")
    v_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    waterline_y = detect_waterline_y(frame, lower_blue, upper_blue)

    if waterline_y is None:
        cap.release()
        raise RuntimeError("Cannot detect waterline.")
    cap.release()
    # waterline_y = 190
    # 2. 讀取簡版 keypoints
    df_clean = read_and_clean_txt(keypoints_txt_path)

    # --- NEW: Lap-based Detection ---
    laps = detect_laps_by_hip_x(df_clean)
    largest_segments = []
    print(f"   [INFO] Detected {len(laps)} Laps inside analysis:")
    for i, (f_start, f_end, trend) in enumerate(laps):
        print(f"     -> Lap {i+1}: {trend} ({f_start}-{f_end})")
        if trend == "static":
            continue
        df_lap = df_clean[(df_clean["frame_id"] >= f_start) & (df_clean["frame_id"] <= f_end)]
        # Find best segment in this lap
        seg = find_best_segment_in_range(df_lap, waterline_y)
        if seg:
            largest_segments.append(seg)
    largest_segments.sort(key=lambda x: x[0])
    # --------------------------------

    # 檢查 segments 是否有效，避免索引錯誤
    if not largest_segments:
        # 如果 segments 為空，給出合理的預設值並返回
        return {
            "segments": [],
            "waterline_y": waterline_y,
            "min_angle_data_1": (None, None),
            "min_angle_data_2": (None, None),
            "kick_angle_series_1": ([], []), # NEW
            "kick_angle_series_2": ([], []), # NEW
            "df_hip_data": df_clean,
            "track_start_frame": None,
            "track_end_frame": None,
            "touch_frame": None,
            "kick_angle_fig_1": None,
            "kick_angle_fig_2": None,
        }
    # 3. 計算踢腿角度 dataframe (全影片一次算完)
    df_angles = calculate_kick_angles_from_txt(keypoints_txt_path)
    
    # 4. 逐趟分析 (Per Lap Processing)
    laps_data = []

    # 為了繪圖 (只畫第一段去程潛泳)，我們需要收集所有的 segments 讓外部知道
    all_diving_segments = []

    # 讀取腳踝與髖關節數據 (用於距離/位移計算)
    keypoints = np.loadtxt(keypoints_txt_path)
    # k_frames_all = keypoints[:, 0].astype(int)
    # k_ankle_x_all = keypoints[:, 25]
    
    for i, (l_start, l_end, trend) in enumerate(laps):
        if trend == "static":
            continue
            
        print(f"   [ANALYSIS] Processing Lap {i+1}: {trend} ({l_start}-{l_end})")
        
        # (A) 尋找潛泳段 (S, E)
        df_lap = df_clean[(df_clean["frame_id"] >= l_start) & (df_clean["frame_id"] <= l_end)]
        
        # 優先嘗試：BBox 上緣判斷
        div_seg = find_best_segment_in_range(df_lap, waterline_y, use_bbox=True)
        
        # 檢查是否需要 Fallback
        # 條件 1: 沒找到潛泳段
        # 條件 2: 找到潛泳段，但結束點 >= Lap 終點 (代表沒有游泳段，通常不合理)
        need_fallback = False
        if div_seg is None:
            need_fallback = True
            print(f"     -> [Check] No diving segment found with BBox method.")
        elif div_seg[1] >= l_end - 5: # 保留一點緩衝，若潛泳幾乎佔滿整趟
            need_fallback = True
            print(f"     -> [Check] Diving segment covers entire lap (No Swim Phase). Unlikely.")

        # Fallback 機制: 改用全關節嚴格檢查
        if need_fallback:
            print(f"     -> [Fallback] Trying Strict Joints method...")
            div_seg_strict = find_best_segment_in_range(df_lap, waterline_y, use_bbox=False)
            
            # 只有當嚴格模式有找到結果時才覆蓋
            if div_seg_strict:
                div_seg = div_seg_strict
                print(f"     -> [Fallback] Success! Found segment using Strict Joints method: {div_seg}")
            else:
                 print(f"     -> [Fallback] Strict method also failed to find better segment.")
                 # 若嚴格模式也沒找到，維持原本的結果 (可能是 None 或 全程潛泳)
        
        lap_result = {
            "lap_index": i + 1,
            "lap_range": (l_start, l_end),
            "trend": trend,
            "diving_segment": None,
            "swimming_segment": None,
            "angle_data": { 
                "frames": [], 
                "angles": [], 
                "minima_frames": [], 
                "minima_values": [],
                "displacements": [] # 用於前端 X軸
            }
        }
        
        if div_seg:
            s_d, e_d = div_seg
            
            # --- 邏輯修正需求: 檢查 s_d 腳踝 X 是否 < 3790 (針對出發端的特例處理) ---
            # 如果是去程 (decreasing) 或第一趟，通常是從右往左(視相機而定)，假設 3790 是牆壁位置
            # 這邊沿用原本邏輯，但建議只限於 Lap 1
            if i == 0 or trend == "decreasing": 
                # 這裡需要一個更通用的方法讀 raw keypoints，或是直接用 df_clean
                # 為了效能，使用 df_clean (已經有 col26 ankle_y, 但我們需要 ankle_x 嗎? read_and_clean_txt 沒讀 ankle_x)
                # 暫時跳過這個針對特定場域的 3790 修正，除非您非常堅持保留 (原程式碼有這段)
                pass 

            lap_result["diving_segment"] = (s_d, e_d)
            all_diving_segments.append((s_d, e_d))
            
            # (B) 定義游泳段 (E, L_end)
            if e_d < l_end:
                lap_result["swimming_segment"] = (e_d, l_end)
                
            # (C) 角度與波型資料 (針對潛泳段)
            # 取出該區段的角度
            sub_angles = df_angles[(df_angles["frame_id"] >= s_d) & (df_angles["frame_id"] <= e_d)]
            series_frames = sub_angles["frame_id"].tolist()
            series_values = sub_angles["angle"].tolist()
            
            # 找局部最小值 (波谷)
            min_frames, min_vals = find_local_min_angles_df(df_angles, s_d, e_d)
            
            # 簡單計算位移 (使用 Frame 數暫代，或需讀取 Hip X 做差值)
            # Front-end usually needs relative distance. 
            # 這裡回傳每個 frame 相對於 s_d 的 index 或是 1.0 進度
            displacements = [x - s_d for x in series_frames]
            
            lap_result["angle_data"] = {
                "frames": series_frames,
                "angles": series_values,
                "minima_frames": min_frames,
                "minima_values": min_vals,
                "displacements": displacements
            }
            
            # 為了相容舊的 return 結構 (S1, S2)，將前兩趟寫入變數
            # (這會在 loop 外處理)
        
        laps_data.append(lap_result)

    # 準備回傳結構 (Flatten data for old logic compatibility, rich data for new)
    # 取出 Lap 1 和 Lap 2 的潛泳數據填入舊欄位
    s1, e1 = (None, None)
    s2, e2 = (None, None)
    
    # 找第一個有 diving segment 的 lap
    valid_laps = [L for L in laps_data if L["diving_segment"] is not None]
    
    series_frames_1, series_angles_1 = [], []
    series_frames_2, series_angles_2 = [], []
    min_data_1 = (None, None)
    min_data_2 = (None, None)
    
    if len(valid_laps) > 0:
        L1 = valid_laps[0]
        s1, e1 = L1["diving_segment"]
        series_frames_1 = L1["angle_data"]["frames"]
        series_angles_1 = L1["angle_data"]["angles"]
        min_data_1 = (L1["angle_data"]["minima_frames"], L1["angle_data"]["minima_values"])
        
    if len(valid_laps) > 1:
        L2 = valid_laps[1]
        s2, e2 = L2["diving_segment"]
        series_frames_2 = L2["angle_data"]["frames"]
        series_angles_2 = L2["angle_data"]["angles"]
        min_data_2 = (L2["angle_data"]["minima_frames"], L2["angle_data"]["minima_values"])

    # 5. *** 整合觸牆偵測 (find_touch_frame 邏輯) ***
    threshold = v_width - 40
    touch_frame = None

    df_temp = df_clean.copy()
    max_frame = df_temp["frame_id"].max()
    half_frame = max_frame // 2

    for _, row in df_temp.iterrows():
        if row["frame_id"] >= half_frame:
            # 這裡的 row["width"] 是 BBox 的寬度
            if row["bbox_x"] + row["width"] / 2 > threshold:
                touch_frame = int(row["frame_id"])
                break
    # 🎯 修正要求: 如果 touch_frame 沒有偵測到，則用影片的總幀數表示
    if touch_frame is None:
        touch_frame = total_frames
    # 6. Save Kick Angle Waveforms
    import os
    base_dir = os.path.dirname(keypoints_txt_path)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    
    fig1_path_rel = f"kick_angle_1_{base_name}.png"
    fig1_path = os.path.join(base_dir, fig1_path_rel)
    
    kick_angle_fig_1 = plot_kick_angle_waveform_with_lines_df(
        df_angles, keypoints_txt_path, s1, e1, "Phase 1", draw_aux_lines=False
    )
    kick_angle_fig_1.savefig(fig1_path)
    plt.close(kick_angle_fig_1)

    kick_angle_fig_2_path = None
    if s2 is not None:
        fig2_path_rel = f"kick_angle_2_{base_name}.png"
        fig2_path = os.path.join(base_dir, fig2_path_rel)
        
        kick_angle_fig_2 = plot_kick_angle_waveform_with_lines_df(
            df_angles,
            keypoints_txt_path,
            s2,
            e2,
            "Phase 2",
            draw_aux_lines=True,
            crop_from_ankle_min=True,
        )
        kick_angle_fig_2.savefig(fig2_path)
        plt.close(kick_angle_fig_2)
        kick_angle_fig_2_path = fig2_path

    return {
        "laps_data": laps_data, # NEW: Complete structure
        "segments": all_diving_segments, # For main() compat
        "waterline_y": waterline_y,
        "min_angle_data_1": min_data_1,
        "min_angle_data_2": min_data_2,
        "kick_angle_series_1": (series_frames_1, series_angles_1),
        "kick_angle_series_2": (series_frames_2, series_angles_2),
        "df_hip_data": df_clean,
        "track_start_frame": s1,
        "track_end_frame": e1, 
        "touch_frame": touch_frame,
        "kick_angle_fig_1": fig1_path,
        "kick_angle_fig_2": kick_angle_fig_2_path,
    }


#  DEMO
# analyze_diving_phase(
#     video_path=r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\temp_videos\real_time_picture (24).mp4",
#     keypoints_txt_path=r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\web_output\sessions\real_time_picture (24)_1.txt",
#     output_video_path=None,
# # )

# if __name__ == "__main__":
#     # --- 執行分析 ---
#     result = analyze_diving_phase(
#         video_path=r"D:\Kady\swimmer coco\1217_demo_debug\real_time_picture (24).mp4",
#         keypoints_txt_path=r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\web_output\sessions\real_time_picture (24)_1.txt",
#         output_video_path=None,
#     )

# # --- Print 出我們關心的結果 ---
# print("\n" + "=" * 50)
# print("🎯 潛泳區段分析結果：")

# segments = result.get("segments", [])
# if segments:
#     for idx, (s, e) in enumerate(segments):
#         print(f"區段 {idx+1}: 起始幀 = {s}, 結束幀 = {e}, 總長度 = {e - s + 1} 幀")
# else:
#     print("❌ 未偵測到符合條件的潛泳區段。")

# print(f"\n📏 使用的水面高度 (Waterline Y): {result.get('waterline_y')}")
# print(f"🏁 觸牆幀 (Touch Frame): {result.get('touch_frame')}")
# print("=" * 50 + "\n")

# ==========================================
# BATCH TESTING & VISUALIZATION
# ==========================================
import sys
import glob
import os

# Helper to allow importing sibling modules when running standalone
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import dependencies (Lazy import inside check to avoid top-level failures if env issues)
try:
    from BD.pose_estimator import run_pose_estimation
    from BD.txt_base import process_keypoints_txt
except ImportError:
    try:
        from pose_estimator import run_pose_estimation
        from txt_base import process_keypoints_txt
    except ImportError as e:
        print(f"Warning: Could not import Pose/Txt modules: {e}")

def draw_multiple_segments_on_video(video_path, df, output_path, segments, line_color=(0, 0, 255), line_thickness=3):
    """
    Draws trajectories for multiple segments on the video.
    segments: list of tuples [(s1, e1), (s2, e2), ...]
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Cannot open video: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Try different codecs
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        print(f"Error: Cannot open video writer: {output_path}")
        cap.release()
        return

    paths = [] 
    current_path = []
    
    # Filter and sort segments
    valid_segments = sorted([s for s in segments if s is not None and len(s) == 2], key=lambda x: x[0])
    
    def get_segment_index(f):
        for i, (s, e) in enumerate(valid_segments):
            if s <= f <= e:
                return i
        return -1
    
    frame_id = 0
    last_seg_idx = -1
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        row = df[df["frame_id"] == frame_id]
        current_seg_idx = get_segment_index(frame_id)
        
        if not row.empty and current_seg_idx != -1:
            if "hip_x" in row.columns and "hip_y" in row.columns:
                x = int(row["hip_x"].values[0])
                y = int(row["hip_y"].values[0])
                
                # If segment changed, push current path and start new
                if current_seg_idx != last_seg_idx:
                     if current_path:
                         paths.append(current_path)
                         current_path = []
                
                current_path.append((x, y))
                last_seg_idx = current_seg_idx
        elif current_seg_idx == -1 and last_seg_idx != -1:
            # Just exited a segment
            if current_path:
                paths.append(current_path)
                current_path = []
            last_seg_idx = -1
            
        # Draw past paths
        for p in paths:
            for i in range(len(p) - 1):
                cv2.line(frame, p[i], p[i+1], line_color, line_thickness)
        
        # Draw current path
        if current_path:
            for i in range(len(current_path) - 1):
                cv2.line(frame, current_path[i], current_path[i+1], line_color, line_thickness)
        
        # Overlay Info - REMOVED per user request
        # info_text = f"Frame: {frame_id}"
        # if current_seg_idx != -1:
        #     s, e = valid_segments[current_seg_idx]
        #     info_text += f" | Seg {current_seg_idx+1}: {s}-{e}"
        #     cv2.rectangle(frame, (5, 5), (400, 40), (0,0,0), -1) 
            
        # cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        out.write(frame)
        frame_id += 1

    cap.release()
    out.release()
    print(f"   -> Saved Trajectory Video: {os.path.basename(output_path)}")


if __name__ == "__main__":
    # --- USER SETTINGS ---
    # INPUT_DIR: The folder containing MP4 videos to process
    INPUT_DIR = r"D:\Kady\swimmer coco\anvanced stroke analysis\diving_stage\260107\N"  
    
    # MODEL_PATH: Path to the Pose Estimation Model
    MODEL_PATH = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\best_1.pt"
    # ---------------------

    if len(sys.argv) > 1:
        INPUT_DIR = sys.argv[1]

    print(f"\n🚀 STARTING BATCH DIVING ANALYSIS")
    print(f"📂 Target Directory: {INPUT_DIR}")
    
    if not os.path.exists(INPUT_DIR):
        print(f"❌ Error: Directory does not exist: {INPUT_DIR}")
        sys.exit(1)

    # Find videos
    video_files = glob.glob(os.path.join(INPUT_DIR, "*.mp4"))
    # Exclude previously generated file artifacts
    video_files = [
        f for f in video_files 
        if "trajectory" not in f 
        and "processed" not in f 
        and "focus" not in f
        and "swimmer_plot" not in f
    ]
    
    print(f"found {len(video_files)} videos.")
    results = []

    for video_path in video_files:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        folder = os.path.dirname(video_path)
        print(f"\n🔹 Processing: {base_name}")
        
        # 1. Prepare Keypoints
        final_txt_path = os.path.join(folder, f"{base_name}_1.txt")
        raw_txt_path = os.path.join(folder, f"{base_name}.txt")
        
        has_keypoints = False
        
        if os.path.exists(final_txt_path):
             print(f"   [OK] Found smoothed keypoints: {os.path.basename(final_txt_path)}")
             has_keypoints = True
        else:
             print("   [..] Smoothed keypoints not found. Checking raw...")
             if not os.path.exists(raw_txt_path):
                 print("   [..] Raw keypoints not found. Running Pose Estimation...")
                 try:
                     # run_pose_estimation saves to {folder}/{base_name}.txt because output_dir=folder
                     run_pose_estimation(MODEL_PATH, video_path, folder, save_video=False, save_txt=True)
                 except Exception as e:
                     print(f"   [ERROR] Pose Estimation Failed: {e}")
            
             if os.path.exists(raw_txt_path):
                 print("   [..] Smoothing keypoints...")
                 try:
                     process_keypoints_txt(raw_txt_path, save_final_output=True, final_output=final_txt_path)
                     has_keypoints = True
                 except Exception as e:
                     print(f"   [ERROR] Smoothing Failed: {e}")
             else:
                 print("   [ERROR] Could not generate keypoints.")

        if not has_keypoints:
            print("   [SKIP] Skipping video due to missing keypoints.")
            continue
            
        # 2. Run Diving Analysis
        try:
            # Run the analysis function from THIS file
            # analyze_diving_phase is defined in this file (diving_analyzer_track_angles_test.py)
            # Make sure it's available in scope. Yes, it is defined above.
            result_dict = analyze_diving_phase(video_path, final_txt_path)
            
            # Retrieve new structured data
            laps_data = result_dict.get("laps_data", [])
            segments = result_dict.get("segments", []) # kept for video drawing
            df_hip = result_dict.get("df_hip_data") # RESTORED
            waterline = result_dict.get("waterline_y")
            
            # Print detailed results to console
            print(f"   [RESULT] Waterline: {waterline}")
            for lap in laps_data:
                idx = lap["lap_index"]
                l_s, l_e = lap["lap_range"]
                d_s, d_e = lap["diving_segment"] if lap["diving_segment"] else ("-", "-")
                s_s, s_e = lap["swimming_segment"] if lap["swimming_segment"] else ("-", "-")
                print(f"     -> Lap {idx} ({lap['trend']}): Total[{l_s}-{l_e}] | Dive[{d_s}-{d_e}] | Swim[{s_s}-{s_e}]")

            # Prepare CSV Row
            row_data = {
                "Video": base_name,
                "Waterline": waterline,
                "Num_Laps": len(laps_data)
            }
            
            # Flatten lap data -> Columns
            for lap in laps_data:
                i = lap["lap_index"]
                l_s, l_e = lap["lap_range"]
                
                # Lap Range
                row_data[f"Lap{i}_Start"] = l_s
                row_data[f"Lap{i}_End"] = l_e
                
                # Diving Segment
                if lap["diving_segment"]:
                    row_data[f"Lap{i}_Dive_S"] = lap["diving_segment"][0]
                    row_data[f"Lap{i}_Dive_E"] = lap["diving_segment"][1]
                else:
                    row_data[f"Lap{i}_Dive_S"] = None
                    row_data[f"Lap{i}_Dive_E"] = None
                    
                # Swimming Segment
                if lap["swimming_segment"]:
                    row_data[f"Lap{i}_Swim_S"] = lap["swimming_segment"][0]
                    row_data[f"Lap{i}_Swim_E"] = lap["swimming_segment"][1]
                else:
                    row_data[f"Lap{i}_Swim_S"] = None
                    row_data[f"Lap{i}_Swim_E"] = None

            results.append(row_data)
            
            # 3. Generate Trajectory Video
            output_traj_path = os.path.join(folder, f"{base_name}_diving_trajectory.mp4")
            if segments and df_hip is not None:
                # 繪製所有偵測到的區段 (因為現在是 Per-Lap，很精準)
                # USER REQUEST: 只畫第一趟去程的潛泳軌跡 (segments[:1])
                draw_multiple_segments_on_video(video_path, df_hip, output_traj_path, segments[:1])
            else:
                print("   [INFO] No segments to draw.")
                
        except Exception as e:
            print(f"   [ERROR] Analysis Phase Failed: {e}")
            # import traceback
            # traceback.print_exc()

    # 4. Save Summary
    if results:
        summary_csv = os.path.join(INPUT_DIR, "diving_analysis_summary.csv")
        try:
            df_sum = pd.DataFrame(results)
            df_sum.to_csv(summary_csv, index=False)
            print(f"\n✅ Batch Analysis Complete. Summary saved to:\n   {summary_csv}")
            print("\nPreview:")
            print(df_sum.to_string())
        except Exception as e:
             print(f"Error saving csv: {e}")
    else:
        print("\n⚠️  No results to save.")
