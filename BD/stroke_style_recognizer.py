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


def split_segments(video_path, keypoints_txt_path):
    """
    1. 讀完整骨架 txt
    2. 用精簡版 df 丟給 get_diving_swimming_segments
    3. 切出潛泳段 (s1, e1) 和游泳段 (e1, s2)
    4. 計算潛泳段髖–膝–踝平均角度
    5. 游泳段再取出 7 個 y 座標並做標準化
    """
    # 讀完整骨架
    df_full = read_full_keypoints_txt(keypoints_txt_path)

    # 建立精簡版 df，符合 diving_analyzer_track_angles 需求
    df_clean = df_full[["frame_id", "col2", "col3", "col8", "col19", "col20"]].copy()
    df_clean.columns = ["frame_id", "bbox_x", "bbox_y", "col8", "hip_x", "hip_y"]

    # 從 diving_analyzer_track_angles 取得水面與區段
    waterline_y, (s1, e1), (s2, e2) = get_diving_swimming_segments(video_path, df_clean)
    
    print(f"\n[DEBUG] Segments Identified -> Diving: {s1}-{e1}, Swimming: {e1}-{s2}")

    # 潛泳段 (s1~e1)
    df_diving = df_full[
        (df_full["frame_id"] >= s1) & (df_full["frame_id"] <= e1)
    ].reset_index(drop=True)

    # === 計算潛泳段踢腿角度 ===
    angle_list, mean_angle = calculate_diving_kick_angles(df_diving)

    # 游泳段 (e1~s2)
    df_swimming = df_full[
        (df_full["frame_id"] >= e1) & (df_full["frame_id"] <= s2)
    ].reset_index(drop=True)
    
    print(f"[DEBUG] Swimming Segment: {len(df_swimming)} frames found in range {e1}-{s2}.")

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
    df_swimming_selected = df_swimming[selected_cols].copy()

    # 標準化
    scaler = StandardScaler()
    coords = df_swimming_selected.drop(columns=["frame_id"])
    
    print(f"[DEBUG] Coords for scaling shape: {coords.shape}")
    
    if coords.shape[0] == 0:
        print("!! WARNING: Coords are empty. Skipping scaling.")
        return waterline_y, df_diving, pd.DataFrame(), angle_list, mean_angle

    coords_scaled = scaler.fit_transform(coords)

    df_swimming_normalized = pd.DataFrame(coords_scaled, columns=coords.columns)
    df_swimming_normalized.insert(
        0, "frame_id", df_swimming_selected["frame_id"].values
    )

    return waterline_y, df_diving, df_swimming_normalized, angle_list, mean_angle


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


def analyze_stroke(video_path, keypoints_txt_path, model_path):
    """
    完整流程：
    1. 切分潛泳段與游泳段
    2. 計算潛泳踢腿角度
    3. 辨識游泳段泳姿 (SVM + 平均踢腿角度)
    回傳最終泳姿類別 (0~3)
    """
    # 切段 + 潛泳踢腿角度 + 游泳段標準化
    waterline_y, df_diving, df_swimming_normalized, angle_list, mean_angle = (
        split_segments(video_path, keypoints_txt_path)
    )

    # 辨識泳姿
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
