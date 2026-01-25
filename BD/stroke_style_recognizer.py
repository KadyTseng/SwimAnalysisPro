# BD/stroke_style_recognizer.py
import pandas as pd
import numpy as np
import math
from sklearn.preprocessing import StandardScaler
from .diving_analyzer_track_angles import get_diving_swimming_segments
import joblib
from collections import Counter


def read_full_keypoints_txt(path, expected_cols=28):
    """
    讀取完整骨架 txt，回傳 DataFrame
    """
    data = []
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= expected_cols:
                try:
                    values = list(map(float, parts))
                    frame_id = int(values[0])
                    data.append([frame_id] + values[1:])
                except:
                    continue
    col_names = ["frame_id"] + [f"col{i}" for i in range(1, expected_cols)]
    return pd.DataFrame(data, columns=col_names)


def calculate_signed_angle(A, B, C):
    """
    計算三點 A-B-C 中點 B 的帶方向夾角 (0~360°)
    """
    BA = (A[0] - B[0], A[1] - B[1])
    BC = (C[0] - B[0], C[1] - B[1])
    dot = BA[0] * BC[0] + BA[1] * BC[1]
    det = BA[0] * BC[1] - BA[1] * BC[0]
    angle_rad = math.atan2(det, dot)
    angle_deg = math.degrees(angle_rad)
    if angle_deg < 0:
        angle_deg += 360
    return angle_deg


def calculate_diving_kick_angles(df_diving):
    """
    計算潛泳段的髖–膝–踝角度 (frame by frame)，回傳 (角度序列, 平均角度)
    """
    angle_list = []

    for _, row in df_diving.iterrows():
        # 確保關鍵點存在
        if pd.isna(row["col19"]) or pd.isna(row["col20"]):
            continue
        if pd.isna(row["col22"]) or pd.isna(row["col23"]):
            continue
        if pd.isna(row["col25"]) or pd.isna(row["col26"]):
            continue

        A = (row["col19"], row["col20"])  # 髖
        B = (row["col22"], row["col23"])  # 膝
        C = (row["col25"], row["col26"])  # 踝

        signed_angle = calculate_signed_angle(A, B, C)
        angle_list.append(signed_angle)

    mean_angle = np.mean(angle_list) if angle_list else None
    return angle_list, mean_angle


def split_segments(video_path, keypoints_txt_path, laps_data=None):
    """
    1. 讀完整骨架 txt
    2. 根據 laps_data 提取所有潛泳段與游泳段數據
    3. 計算潛泳段髖–膝–踝平均角度
    4. 游泳段再取出 7 個 y 座標並做標準化
    """
    # 讀完整骨架 (需包含 col5 height)
    df_full = read_full_keypoints_txt(keypoints_txt_path)
    
    # 準備容器
    df_diving_list = []
    df_swimming_list = []
    
    if laps_data:
        print(f"[DEBUG] Using provided laps_data with {len(laps_data)} laps.")
        for lap in laps_data:
            # 1. Diving Segment
            div_seg = lap.get("diving_segment")
            if div_seg and div_seg[0] is not None:
                s, e = div_seg
                # 篩選並複製數據
                d_part = df_full[(df_full["frame_id"] >= s) & (df_full["frame_id"] <= e)].copy()
                df_diving_list.append(d_part)
                
            # 2. Swimming Segment
            swim_seg = lap.get("swimming_segment")
            if swim_seg and swim_seg[0] is not None:
                s, e = swim_seg
                s_part = df_full[(df_full["frame_id"] >= s) & (df_full["frame_id"] <= e)].copy()
                df_swimming_list.append(s_part)
    else:
        # Fallback: 使用舊邏輯 (只取第一趟)
        # 建立精簡版 df
        df_clean = df_full[["frame_id", "col2", "col3", "col5", "col8", "col19", "col20"]].copy()
        df_clean.columns = ["frame_id", "bbox_x", "bbox_y", "height", "col8", "hip_x", "hip_y"]

        waterline_y, segments = get_diving_swimming_segments(video_path, df_clean)
        
        # Unpack segments safely
        s1, e1 = segments[0] if len(segments) > 0 else (0, 0)
        s2, e2 = segments[1] if len(segments) > 1 else (0, 0)
        
        # 潛泳段 (s1~e1)
        if s1 < e1:
            df_diving_list.append(df_full[(df_full["frame_id"] >= s1) & (df_full["frame_id"] <= e1)])
            
        # 游泳段 (e1~s2)
        if e1 < s2:
             df_swimming_list.append(df_full[(df_full["frame_id"] >= e1) & (df_full["frame_id"] <= s2)])

    # 合併數據
    if df_diving_list:
        df_diving = pd.concat(df_diving_list, ignore_index=True)
    else:
        df_diving = pd.DataFrame()
        
    if df_swimming_list:
        df_swimming = pd.concat(df_swimming_list, ignore_index=True)
    else:
        df_swimming = pd.DataFrame()

    print(f"[DEBUG] Total Diving Frames: {len(df_diving)}, Total Swimming Frames: {len(df_swimming)}")

    # === 計算潛泳段踢腿角度 ===
    angle_list, mean_angle = calculate_diving_kick_angles(df_diving)

    # 游泳段標準化
    # 游泳段取出 7 個 y 座標
    selected_cols = [
        "frame_id",
        "col8",
        "col11",
        "col14",
        "col17",
        "col20",
        "col23",
        "col26",
    ]
    
    # 檢查欄位是否存在 (避免空 df 報錯)
    if df_swimming.empty:
         return None, df_diving, pd.DataFrame(), angle_list, mean_angle

    df_swimming_selected = df_swimming[selected_cols].copy()

    # 標準化
    scaler = StandardScaler()
    coords = df_swimming_selected.drop(columns=["frame_id"])
    
    if coords.shape[0] == 0:
        print("!! WARNING: Coords are empty. Skipping scaling.")
        return None, df_diving, pd.DataFrame(), angle_list, mean_angle

    coords_scaled = scaler.fit_transform(coords)

    df_swimming_normalized = pd.DataFrame(coords_scaled, columns=coords.columns)
    df_swimming_normalized.insert(
        0, "frame_id", df_swimming_selected["frame_id"].values
    )

    return None, df_diving, df_swimming_normalized, angle_list, mean_angle


def recognize_stroke_style(df_swimming_normalized, mean_kick_angle, model_path: str):
    """
    使用 SVM + 潛泳踢腿角度判斷泳姿
    """
    # 載入 SVM 模型
    model = joblib.load(model_path)

    # 取特徵 (去掉 frame_id)
    X = df_swimming_normalized.drop(columns=["frame_id"])

    # 預測每一幀
    y_pred = model.predict(X)

    # 多數決決定初步類別
    counter = Counter(y_pred)
    majority_label = counter.most_common(1)[0][0]

    # 根據邏輯判斷最終泳姿
    if majority_label == 1:
        final_label = 1  # 蛙式
    elif majority_label == 3:
        final_label = 3  # 蝶式
    else:
        # 初步類別是 0 或 2 → 用潛泳平均踢腿角度判斷
        if mean_kick_angle is not None and mean_kick_angle > 180:
            final_label = 0  # 仰式
        else:
            final_label = 2  # 自由式

    return final_label


def analyze_stroke(video_path, keypoints_txt_path, model_path, laps_data=None):
    """
    完整流程：
    1. 根據 laps_data (若有) 提取潛泳段與游泳段
    2. 計算潛泳踢腿角度
    3. 辨識游泳段泳姿 (SVM + 平均踢腿角度)
    回傳最終泳姿類別 (0~3)
    """
    # 切段 + 潛泳踢腿角度 + 游泳段標準化
    _, df_diving, df_swimming_normalized, angle_list, mean_angle = (
        split_segments(video_path, keypoints_txt_path, laps_data)
    )

    # 辨識泳姿
    if df_swimming_normalized.empty:
        print("[WARNING] No swimming data found for stroke recognition. Defaulting to Freestyle.")
        return 2 # Default Freestyle
        
    stroke_label = recognize_stroke_style(
        df_swimming_normalized, mean_angle, model_path
    )

    return stroke_label


# if __name__ == "__main__":
#     # 這裡的程式碼只會在您直接運行此文件時執行，不會在 orchestrator 導入時執行。

#     # 測試參數 (請替換為您實際可用的路徑)
#     demo_video_path = "demo_video.mp4"
#     demo_txt_path = "skeleton.txt"
#     demo_model_path = "svm_model.pkl"

#     # 數字到字串的轉換字典 (僅用於此測試)
#     label_dict = {0: "backstroke", 1: "breaststroke", 2: "freestyle", 3: "butterfly"}

#     try:
#         label = analyze_stroke(demo_video_path, demo_txt_path, demo_model_path)
#         # 輸出結果
#         print("\n--- 泳姿辨識測試結果 ---")
#         print("最終辨識泳姿:", label_dict[label])
#         print("返回標籤 (數字):", label)

#     except Exception as e:
#         print(
#             f"\n泳姿辨識測試失敗，請檢查 demo 檔案是否存在或 SVM 模型路徑是否正確。錯誤: {e}"
#         )
