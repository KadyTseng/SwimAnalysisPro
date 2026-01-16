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
                    col8 = float(parts[8])  # 頭y
                    hip_x = float(parts[19])  # 髖關節 x
                    hip_y = float(parts[20])  # 髖關節 y
                    data.append(
                        (frame_id, bbox_x, bbox_y, bbox_width, col8, hip_x, hip_y)
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
            "col8",
            "hip_x",
            "hip_y",
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


def find_largest_submerged_segments(df, waterline_y, top_n=2):
    """
    修正後的版本：確保排序時使用的是數字相減
    """

    segments = []
    current_segment = []
    in_segment = False

    # 🎯 2. 設定最小長度門檻 (過濾雜訊)
    MIN_DIVE_LEN = 40

    for i, row in df.iterrows():
        frameid = row["frame_id"]
        value = row["col8"]

        if value >= waterline_y:
            if not in_segment:
                in_segment = True
                # 這裡只存入 frameid 即可，不用存整個 tuple
                current_segment = [frameid]
            else:
                current_segment.append(frameid)
        else:
            if in_segment:
                # 🎯 3. 只有長度夠長的區段才存入
                if len(current_segment) >= MIN_DIVE_LEN:
                    # 存入起始幀與結束幀的 tuple
                    segments.append((current_segment[0], current_segment[-1]))
                in_segment = False
                current_segment = []

    # 處理結尾
    if in_segment and len(current_segment) >= MIN_DIVE_LEN:
        segments.append((current_segment[0], current_segment[-1]))

    if not segments:
        return []

    # 🎯 4. 依照「幀數長度」排序，取最長的 top_n 段
    # 現在 x[1] 和 x[0] 都是整數(幀號)，可以相減了
    segments.sort(key=lambda x: x[1] - x[0], reverse=True)
    largest_segments = segments[:top_n]

    # 🎯 5. 最後按時間先後排序返回 (s1, e1) -> (s2, e2)
    largest_segments.sort(key=lambda x: x[0])

    return largest_segments


def get_diving_swimming_segments(video_path, df, top_n=2):  # 之後top_n可以彈性
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
    largest_segments = find_largest_submerged_segments(df_clean, waterline_y)
    # 檢查 segments 是否有效，避免索引錯誤
    if not largest_segments:
        # 如果 segments 為空，給出合理的預設值並返回
        return {
            "segments": [],
            "waterline_y": waterline_y,
            "min_angle_data_1": (None, None),
            "min_angle_data_2": (None, None),
            "df_hip_data": df_clean,
            "track_start_frame": None,
            "track_end_frame": None,
            "touch_frame": None,
            "kick_angle_fig_1": None,
            "kick_angle_fig_2": None,
        }
    # 3. 計算踢腿角度 dataframe
    df_angles = calculate_kick_angles_from_txt(keypoints_txt_path)

    # 4. 找局部最小值
    s1, e1 = largest_segments[0]
    s2, e2 = largest_segments[1] if len(largest_segments) > 1 else (None, None)
    # === 新增：檢查 s1 腳踝 X 是否 < 3790，否則往後找 ===
    keypoints = np.loadtxt(keypoints_txt_path)
    frames_all = keypoints[:, 0].astype(int)
    ankle_x_all = keypoints[:, 25]  # 腳踝 X

    # 過濾出在 [s1, e1] 區段的幀
    mask = (frames_all >= s1) & (frames_all <= e1)
    frames_in_seg = frames_all[mask]
    ankle_x_in_seg = ankle_x_all[mask]

    # 找第一個 ankle_x < 3790 的幀
    valid_idx = np.where(ankle_x_in_seg < 3790)[0]
    if len(valid_idx) > 0:
        s1 = frames_in_seg[valid_idx[0]]  # 更新 s1

    local_min_frames1, local_min_values1 = find_local_min_angles_df(df_angles, s1, e1)
    if s2 is not None:
        local_min_frames2, local_min_values2 = find_local_min_angles_df(
            df_angles, s2, e2
        )
    else:
        local_min_frames2, local_min_values2 = None, None

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
        "segments": largest_segments,
        "waterline_y": waterline_y,
        "min_angle_data_1": (local_min_frames1, local_min_values1),
        "min_angle_data_2": (local_min_frames2, local_min_values2),
        "df_hip_data": df_clean,
        "track_start_frame": s1,
        "track_end_frame": e1,  # 只畫第一段潛泳
        "touch_frame": touch_frame,
        "kick_angle_fig_1": fig1_path,
        "kick_angle_fig_2": kick_angle_fig_2_path,  # Now returns path string or None
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
