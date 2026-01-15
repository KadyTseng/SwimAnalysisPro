# SwimAnalysisPro/BD/stroke_analysis/backstroke_butterfly_freestyle_stroke_stage.py
import cv2
import pandas as pd
import numpy as np
from scipy.ndimage import uniform_filter1d


def read_txt(path):
    data = []
    with open(path, "r") as f:
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
    return pd.DataFrame(data, columns=["frame_id", "x_center", "width", "head_y"])


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
        if row["head_y"] >= waterline_y:
            current.append(row["frame_id"])
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
    max_frame = df["frame_id"].max()
    half_frame = max_frame // 2
    for _, row in df.iterrows():
        if row["frame_id"] >= half_frame:
            if row["x_center"] + row["width"] / 2 > threshold:
                return int(row["frame_id"])
    return None


def extract_stroke_segments(txt_path, video_path, waterline_y):
    df = read_txt(txt_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"無法開啟影片: {video_path}")

    v_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()

    (s1, e1), (s2, e2) = find_submerged_segments(df, waterline_y)
    touch_frame = find_touch_frame(df, v_width)

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
    with open(txt_path, "r") as f:
        for line in f:
            parsed = parse_line(line)
            if parsed:
                frame_id, col10, col11, col16, col17, col19 = parsed
                if range1[0] <= frame_id <= range1[1]:
                    range1_data.append((frame_id, col10, col11, col16, col17, col19))
                elif range2[0] <= frame_id <= range2[1]:
                    range2_data.append((frame_id, col10, col11, col16, col17, col19))
    return {"range1": range1_data, "range2": range2_data}


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


# BD/stroke_analysis/backstroke_butterfly_freestyle_stroke_stage.py


def count_strokes_from_phases(phase_results):
    """
    計算划手次數：統計 range1 和 range2 中包含的幀數列表長度。
    (注意：此函數假設 phase_results['rangeX'] 的值本身就是一個幀數列表。)
    """
    # print("--- DEBUG: Phase Results Type Check ---")
    # print(f"Type of phase_results: {type(phase_results)}")
    # print(f"Content (First 500 chars): {str(phase_results)[:500]}")
    # print("--------------------------------------")
    # *** 修正點 1: 確保輸入是字典 ***
    if not isinstance(phase_results, dict):
        # 這裡應該拋出錯誤或返回 0，以防輸入類型錯誤
        return {"total_count": 0, "stroke_frames": []}

    # *** 修正點 2: 直接獲取 range1, range2 的列表長度 ***
    # 這裡假設 phase_results['range1'] 的值就是我們想要計算長度的列表。

    # 確保 range1/range2 的值是列表，如果不存在則返回空列表 []
    recovery_list_r1 = phase_results.get("range1", [])
    recovery_list_r2 = phase_results.get("range2", [])

    # 由於我們沒有子鍵，直接計算列表長度
    strokes_range1 = len(recovery_list_r1)
    strokes_range2 = len(recovery_list_r2)
    total_strokes = strokes_range1 + strokes_range2

    # 合併所有幀數 (假設這是划水點)
    all_stroke_frames = recovery_list_r1 + recovery_list_r2

    return {
        "total_count": total_strokes,
        "range1_recovery_count": strokes_range1,
        "range2_recovery_count": strokes_range2,
        "stroke_frames": all_stroke_frames,
        "phase_regions_detail": phase_results,
    }


import os
from .backstroke_butterfly_freestyle_stroke_phase_plot import (
    plot_phase_on_col11_col17,
)  # 分開管理 plot 實作


def run_backstroke_butterfly_analysis(
    txt_path: str, video_path: str, waterline_y: float
):
    """
    執行仰式/蝶式的分析流程：
    1. 找出有效分析區間 (e1, s2, e2, touch_frame)。
    2. 計算肩關節與手腕的交會點 (作為劃分階段的依據)。
    3. 呼叫繪圖函數輸出波形圖和結果 TXT。
    """
    # 確保 extract_stroke_segments 已經被定義在上面或導入
    # 假設 extract_stroke_segments 返回 5 個值
    e1, s2, e2, touch_frame, waterline_y = extract_stroke_segments(
        txt_path, video_path, waterline_y
    )

    if None in (e1, s2, e2):  # 這裡我們只需要檢查 e1, s2, e2 是否有效
        print(f"⚠️ 區間資訊缺失，跳過影片: {video_path} (核心分段不足)")
        return {"status": "skipped", "reason": "core segments missing"}

        # --- 修正點：定義分析終點 ---
    if touch_frame is None:
        # 如果沒有偵測到觸牆，獲取影片的總幀數作為分析終點
        cap = cv2.VideoCapture(video_path)
        last_frame = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        analysis_end_frame = last_frame - 5  # 使用影片最後5幀
        print("偵測不到觸牆幀，使用影片最後一幀作為分析終點。")
    else:
        analysis_end_frame = touch_frame

    range1 = (e1, s2)
    range2 = (e2, analysis_end_frame)

    # 擷取所需欄位數據
    data = extract_columns_in_range(txt_path, range1, range2)

    # 找出划手階段交會點
    intersection_dict = plot_intersection_from_smoothed(data)

    base, _ = os.path.splitext(video_path)
    output_txt = base + ".a.txt"

    # 執行繪圖和結果輸出
    full_phase_regions = plot_phase_on_col11_col17(
        data,
        intersection_dict,
        waterline_y,
        output_txt=output_txt,
    )

    # 返回劃分結果，供 orchestrator 進行計數 (Step 7)
    return {
        "status": "success",
        "phase_data": intersection_dict,
        "full_phase_regions": full_phase_regions,  # 🎯 修正點 B: 新增這個鍵，回傳完整的階段區域
        "output_txt": output_txt,
        "analysis_end_frame": analysis_end_frame,
    }


# ====demo ====


# def main():

#     txt_path = r"D:\Kady\swimmer coco\anvanced stroke analysis\stroke_stage\butterfly\Excellent_20230414_butterfly_M_3 (1)_1.txt"
#     video_path = r"D:\Kady\swimmer coco\anvanced stroke analysis\stroke_stage\butterfly\Excellent_20230414_butterfly_M_3 (1).mp4"

#     # 1. 自動偵測水面線
#     waterline_y = detect_waterline_y(video_path)

#     # 2. 讀取資料 + 找出潛泳區間 + 觸牆時間點
#     df = read_txt(txt_path)
#     (s1, e1), (s2, e2) = find_submerged_segments(df, waterline_y)
#     touch_frame = find_touch_frame(df)

#     # 3. 擷取有效分析段落
#     range1 = (e1, s2)
#     range2 = (e2, touch_frame)
#     data = extract_columns_in_range(txt_path, range1, range2)

#     # 4. 找交會點
#     intersection_dict = plot_intersection_from_smoothed(data)

#     # 5. 畫圖並標記推進/拉水/復原區段
#     plot_phase_on_col11_col17(data, intersection_dict, waterline_y)


# if __name__ == "__main__":
#     main()

# ==== demo ====

# def main():
#     folder = r"D:\Kady\swimmer coco\anvanced stroke analysis\stroke_stage\backstroke"

#     for fname in os.listdir(folder):
#         if fname.endswith(".mp4") and not fname.endswith("_1.mp4"):
#             video_path = os.path.join(folder, fname)
#             txt_name = os.path.splitext(fname)[0] + "_1.txt"
#             txt_path = os.path.join(folder, txt_name)

#             if not os.path.exists(txt_path):
#                 print(f"⚠️ 找不到對應的 txt：{txt_path}")
#                 continue

#             print(f"\n🚀 處理影片：{video_path}")
#             run_backstroke_butterfly_analysis(txt_path, video_path)


# if __name__ == "__main__":
#     main()
