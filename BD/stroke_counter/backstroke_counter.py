import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import argrelextrema
import os

def generate_smoothed_txt(final_output_path):
    """
    從 txt_base.py 產出的 final_output.txt 讀取，
    對第11欄(shoulder Y)做 Hampel 濾波與 uniform filter，
    並輸出同目錄下 final_output_hampel_uniform.txt，
    回傳新檔案路徑。
    """
    def hampel_filter(signal, window_size=50, n_sigmas=3):
        filtered = signal.copy()
        L = 1
        for i in range(window_size, len(signal) - window_size):
            window = signal[i - window_size:i + window_size + 1]
            median = np.median(window)
            std = L * np.median(np.abs(window - median))
            if np.abs(signal[i] - median) > n_sigmas * std:
                filtered[i] = median
        return filtered

    # 讀檔 + 轉為 list of list
    with open(final_output_path, 'r') as f:
        lines = [line.strip().split() for line in f if line.strip()]

    col11 = np.array([float(row[11]) for row in lines])

    # Hampel 濾波
    col11_hampel = hampel_filter(col11, window_size=50, n_sigmas=3)
    # uniform_filter1d 平滑
    col11_smooth = uniform_filter1d(col11_hampel, size=40)

    # 將平滑後結果寫回 lines，保留原格式
    for i in range(len(lines)):
        lines[i][11] = f"{col11_smooth[i]:.6f}"

    # 輸出路徑
    dir_path = os.path.dirname(final_output_path)
    base_name = os.path.basename(final_output_path).replace('.txt', '_hampel_uniform.txt')
    smoothed_txt_path = os.path.join(dir_path, base_name)

    with open(smoothed_txt_path, 'w') as f:
        for row in lines:
            f.write(' '.join(row) + '\n')

    return smoothed_txt_path


def find_touch_frame(file_path, threshold=2540):
    """
    從 bbox txt 檔中找出右游過半後，x_center + width/2 > threshold 的第一個 frame，視為觸牆
    """
    max_frame = 0
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            frame_id = int(parts[0])
            x_center = float(parts[2])
            width = float(parts[4])
            data.append((frame_id, x_center, width))
            max_frame = max(max_frame, frame_id)

    half_frame = max_frame // 2
    for frame_id, x_center, width in data:
        if frame_id >= half_frame:
            x_right = x_center + width / 2
            if x_right > threshold:
                return frame_id
    return None


def filter_local_peaks(raw_indices, signal, waterline_y, min_gap=40, peak_type='max'):
    """
    篩選局部極大值或極小值，
    peak_type 可為 'max' 或 'min'，
    條件為峰值大於(或小於)水面水準線，
    且峰值間距大於 min_gap。
    """
    if peak_type == 'max':
        condition = lambda v: v > waterline_y
    else:
        condition = lambda v: v < waterline_y

    filtered = [idx for idx in raw_indices if condition(signal[idx])]
    final_result = []
    prev = -np.inf
    for idx in filtered:
        if idx - prev > min_gap:
            final_result.append(idx)
            prev = idx
    return np.array(final_result)


def count_backstroke_strokes(smoothed_txt_path, waterline_y, s1, e1, s2, e2, touch_frame):
    """
    計算仰式划手次數與時間點，回傳格式：
    {
        'middle': {'frames': [...], 'count': N},
        'last': {'frames': [...], 'count': M}
    }
    """
    # 預設接縫範圍，可視實際需求修改
    seam_ranges = [(570, 700), (1210, 1340), (1850, 1980)]

    # 讀入 txt
    with open(smoothed_txt_path, 'r') as f:
        lines = [line.strip().split() for line in f if line.strip()]

    col11 = np.array([float(parts[11]) for parts in lines])
    col10 = np.array([float(parts[10]) for parts in lines])
    frame_ids = np.array([int(parts[0]) for parts in lines])

    # 分段資料
    middle_col11 = col11[e1:s2]
    last_col11 = col11[e2:touch_frame]

    # 偵測局部極大值（峰值）
    middle_peaks = argrelextrema(middle_col11, np.greater, order=40)[0] + e1
    last_peaks = argrelextrema(last_col11, np.greater, order=40)[0] + e2

    # 篩選符合水下划手條件
    middle_peaks = filter_local_peaks(middle_peaks, col11, waterline_y, peak_type='max')
    last_peaks = filter_local_peaks(last_peaks, col11, waterline_y, peak_type='max')

    # 過濾最後段不合理划手：在最後一次肩膀浮出水面後的峰值需去除
    last_min = argrelextrema(last_col11, np.less, order=40)[0] + e2
    if len(last_min) > 0:
        max_valid = np.max(last_min)
        last_peaks = last_peaks[last_peaks <= max_valid]

    # 處理接縫重複峰值：保留該區最小 frame 的峰值
    seam_margin = 0
    used = set()
    filtered_last_peaks = []
    for start, end in seam_ranges:
        in_seam = [idx for idx in last_peaks if start <= col10[idx] <= end and idx not in used]
        if in_seam:
            keep = min(in_seam)
            filtered_last_peaks.append(keep)
            used.update(in_seam)
    for idx in last_peaks:
        if idx not in used:
            filtered_last_peaks.append(idx)

    last_peaks = sorted(filtered_last_peaks)

    return {
        'middle': {
            'frames': middle_peaks.tolist(),
            'count': len(middle_peaks)
        },
        'last': {
            'frames': last_peaks,
            'count': len(last_peaks)
        }
    }


# if __name__ == "__main__":
#     # 示範用，請自行替換路徑與參數
#     final_output_path = r"path\to\final_output.txt"  # txt_base.py 產出路徑
#     bbox_txt_path = r"path\to\bbox_file.txt"        # 用於找 touch_frame 的 bbox txt 檔

#     # 先從 final_output.txt 產生濾波後的 smoothed_txt_path
#     smoothed_txt_path = generate_smoothed_txt(final_output_path)

#     # 找 touch_frame
#     touch_frame = find_touch_frame(bbox_txt_path)
#     print(f"touch_frame: {touch_frame}")

#     # 這裡示範水面水平線 waterline_y 與兩段潛泳段 (s1,e1), (s2,e2)
#     # 這些參數請從 diving_analyzer_track_angles.py 或其他地方取得
#     waterline_y = 360  # 範例值，請用偵測到的實際值
#     s1, e1 = 100, 400  # 潛泳第一段範圍 範例
#     s2, e2 = 450, 800  # 潛泳第二段範圍 範例

#     # 計算划手次數
#     result = count_backstroke_strokes(smoothed_txt_path, waterline_y, s1, e1, s2, e2, touch_frame)
#     print("划手時間點與次數：")
#     print(result)
