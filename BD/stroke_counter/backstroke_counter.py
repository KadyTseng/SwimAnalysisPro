import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import argrelextrema

# ---------------- Part 1: 從第一個 txt 取得兩個最大區段 ----------------

EXPECTED_COLS = 12

def read_and_clean_txt(path, expected_cols=EXPECTED_COLS):
    """
    讀取 txt 檔案，假設每一行至少有 expected_cols 欄，
    並取出 frame_id 和第 9 欄（index=8）的數值（例如 col8）。
    """
    data = []
    with open(path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= expected_cols:
                try:
                    frame_id = int(parts[0])
                    col8 = float(parts[8])
                    data.append((frame_id, col8))
                except:
                    continue
    return pd.DataFrame(data, columns=['frame_id', 'col8'])

# 設定第一個 txt 的路徑（col8 smoothed）
col8_path = r"D:\Kady\swimmer coco\stroke_data\predict_train8\backstroke\Excellent_20230414_backstroke_M_3 (3)\Excellent_20230414_backstroke_M_3 (3)_1_col8_smoothed.txt"
df = read_and_clean_txt(col8_path)

# 找出所有大於等於 360 的連續區段
segments = []
current_segment = []
in_segment = False

for idx, row in df.iterrows():
    frameid = row['frame_id']
    value = row['col8']
    if value >= 358:
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
# 若最後一行仍屬於區段，也加入
if current_segment:
    segments.append(current_segment)

# 根據連續點數（長度）排序，選出最大的兩個區段
segment_lengths = [(segment, len(segment)) for segment in segments]
segment_lengths.sort(key=lambda x: x[1], reverse=True)
largest_segments = segment_lengths[:2]

# 假設每個區段的資料為 list of tuple，如 [(frame_id, value), ...]
# 取得區段的頭尾 frame_id：第一區段記為 (s1, e1)，第二區段記為 (s2, e2)
s1 = int(largest_segments[0][0][0][0])
e1 = int(largest_segments[0][0][-1][0])
s2 = int(largest_segments[1][0][0][0])
e2 = int(largest_segments[1][0][-1][0])

# 若順序錯誤（例如 s1 大於 s2），則交換兩區段
if s1 > s2:
    s1, e1, s2, e2 = s2, e2, s1, e1

print("第一區段：Start = {}, End = {}".format(s1, e1))
print("第二區段：Start = {}, End = {}".format(s2, e2))

# --------------------- 設定已知的區段邊界 ---------------------
# 從第一個 txt 得到的區段邊界
# --------------------- Part 2: 讀取第二個 txt 的第一行 ---------------------
# 設定第二個 txt 的路徑，該檔第一行所有數字依序代表各 frame 的 col11 值
col11_path = r"D:\Kady\swimmer coco\stroke_data\predict_train8\backstroke\Excellent_20230414_backstroke_M_3 (3)\Excellent_20230414_backstroke_M_3 (3)_1_col11_smoothed_uniform.txt"

col11 = []
with open(col11_path, 'r') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) >= 13:
            col11.append(float(parts[11]))  # index 12 是你要的數值
        else:
            col11.append(None)  # 補 None 避免錯位
col11 = np.array(col11) 
middle_col11 = col11[e1:s2]
last_col11 = col11[e2:]

middle_col11 = np.array(middle_col11)
last_col11 = np.array(last_col11)

# 找極大值索引並偏移回原始索引位置
middle_max_idx = np.asarray(argrelextrema(middle_col11, np.greater,order=40)[0]) + e1
last_max_idx = np.asarray(argrelextrema(last_col11, np.greater,order=40)[0]) + e2
last_min_idx = np.asarray(argrelextrema(last_col11, np.less,order=40)[0]) + e2

# 2. 定義篩選函數：水平面 > 360 且 划手最短時間 > 40
def filter_local_maxima(raw_indices, signal, value_thresh=358, min_gap=40):    
    # 只保留 signal 值大於門檻的 maxima
    filtered = [idx for idx in raw_indices if signal[idx] > value_thresh]
    
    # 篩選相鄰 maxima 的距離
    final_result = []
    prev = -np.inf
    for idx in filtered:
        if idx - prev > min_gap:
            final_result.append(idx)
            prev = idx
    return np.array(final_result)
def filter_local_minimum(raw_indices, signal, value_thresh=358, min_gap=40):    
    # 只保留 signal 值大於門檻的 maxima
    filtered = [idx for idx in raw_indices if signal[idx] < value_thresh]
    
    # 篩選相鄰 maxima 的距離
    final_result = []
    prev = -np.inf
    for idx in filtered:
        if idx - prev > min_gap:
            final_result.append(idx)
            prev = idx
    return np.array(final_result)

# 3. 套用篩選條件
middle_max_idx = filter_local_maxima(middle_max_idx, col11)
last_max_idx = filter_local_maxima(last_max_idx, col11)
last_min_idx = filter_local_minimum(last_min_idx, col11)

# 只保留 <= touch_frame 的 local maxima   (刪除到牆邊的點)
if touch_frame is not None:
    last_max_idx = last_max_idx[last_max_idx <= touch_frame]
# print(touch_frame)
last_max_idx = last_max_idx[last_max_idx <= max(last_min_idx)]   # 最後一次划手到水面上有個最後的明顯低點，在那之後找到的高點刪掉
    
# 4. 接縫處附近(範圍)只算一次

plt.figure(figsize=(18, 4))
plt.plot(col11, label="shoulder")

# 畫虛線區段
plt.axvline(x=e1, color='gray', linestyle='--', label='Start of middle section')
plt.axvline(x=s2, color='gray', linestyle='--', label='End of middle section')
plt.axvline(x=e2, color='gray', linestyle='--', label='Start of last section')
plt.axvline(x=2473, color='green', linestyle='--', label='wall')

plt.axvline(x=1046, color='red', linestyle='--')
plt.axvline(x=1075, color='red', linestyle='--', alpha =0.3)
plt.axvline(x=1140, color='red', linestyle='--')
plt.axvline(x=1203, color='red', linestyle='--', alpha =0.3)
plt.axvline(x=1272, color='red', linestyle='--')
plt.axvline(x=1956, color='red', linestyle='--')
plt.axvline(x=2088, color='red', linestyle='--')
plt.axvline(x=2232, color='red', linestyle='--')
plt.axvline(x=2352, color='red', linestyle='--')
# 在虛線底下標上 frame 數字
ymin, ymax = plt.ylim()  # 取得 Y 軸範圍，方便定位文字
offset = (ymax - ymin) * 0.001  # 往下偏移一點，避免重疊

plt.text(e1, ymin - offset, f'{e1}', ha='center', va='top', fontsize=9, color='gray')
plt.text(s2, ymin - offset, f'{s2}', ha='center', va='top', fontsize=9, color='gray')
plt.text(e2, ymin - offset, f'{e2}', ha='center', va='top', fontsize=9, color='gray')

# 畫出 local maxima
plt.plot(middle_max_idx, col11[middle_max_idx], 'ro', label='shoulder under water')
plt.plot(last_max_idx, col11[last_max_idx], 'ro', label='shoulder under water')
# plt.plot(last_min_idx, col11[last_min_idx], 'bo', label='shoulder above water')

plt.legend()
plt.title("Local Maxima in Specified Sections")
plt.xlabel("Frame Index")
plt.ylabel("col11 Value")
plt.grid(True)
plt.tight_layout()
plt.show()

# 顯示 middle_max_idx 的 (x, y)
print("Middle Section Local Maxima (Frame, Value):")
for idx in middle_max_idx:
    print(f"({idx}, {col11[idx]:.3f})")

# 顯示 last_max_idx 的 (x, y)
print("\nLast Section Local Maxima (Frame, Value):")
for idx in last_max_idx:
    print(f"({idx}, {col11[idx]:.3f})")

