import numpy as np
import matplotlib.pyplot as plt

# 原始檔案路徑
file_path = r"D:\Kady\swimmer coco\stroke_data\predict_train8\backstroke\Excellent_20230414_backstroke_M_3 (3)\Excellent_20230414_backstroke_M_3 (3)_1_col11_smoothed.txt"

# 讀檔 + 處理成 list of list（這樣可以保留格式）
with open(file_path, 'r') as f:
    lines = [line.strip().split() for line in f if line.strip()]

# 轉成 numpy array 做濾波
data = np.array(lines, dtype=float)

# X 軸
x_values = np.arange(len(data))

# Y 軸：第 12 欄（index=11）
y_values = data[:, 11]

# Hampel 濾波
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

filtered_y = hampel_filter(y_values, window_size=50, n_sigmas=3)

# 畫圖
plt.figure(figsize=(18, 4))
plt.plot(x_values, y_values, label='Original', linewidth=2, color='green', alpha = 0.6)  # 原始線條顏色設為紅色
plt.plot(x_values, filtered_y, label='Hampel Filtered', linewidth=1, color='red', alpha =1)  # 濾波後線條顏色設為藍色
plt.title('Hampel Filter - col11')
plt.xlabel('Frame Index')
plt.ylabel('Value')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()


# 把第11欄改成 Hampel結果，但其他欄保持原格式
for i in range(len(lines)):
    lines[i][11] = f'{filtered_y[i]:.6f}'  # 第11欄用小數6位

# 儲存新的TXT檔（每個欄位用一個空格隔開）
new_file_path = file_path.replace('.txt', '_hampel_filtered.txt')

with open(new_file_path, 'w') as f:
    for row in lines:
        f.write(' '.join(row) + '\n')

print(f"已儲存新的檔案到：{new_file_path}")

import numpy as np
from scipy.ndimage import uniform_filter1d

# 檔案路徑
input_path = r"D:\Kady\swimmer coco\stroke_data\predict_train8\backstroke\Excellent_20230414_backstroke_M_3 (3)\Excellent_20230414_backstroke_M_3 (3)_1_col11_smoothed_hampel_filtered.txt"
output_path = r"D:\Kady\swimmer coco\stroke_data\predict_train8\backstroke\Excellent_20230414_backstroke_M_3 (3)\Excellent_20230414_backstroke_M_3 (3)_1_col11_smoothed_hampel_filtered_uniform.txt"

# 讀取整份檔案內容
all_data = []
col11_data = []

with open(input_path, 'r') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) > 11:
            try:
                col11_val = float(parts[11])
                col11_data.append(col11_val)
                all_data.append(parts)
            except:
                continue  # 轉換失敗就跳過

# 平滑第 11 欄 (index 11)
col11_smooth = uniform_filter1d(col11_data, size=40)

# 替換原始資料的第 11 欄
for i in range(len(all_data)):
    all_data[i][11] = f"{col11_smooth[i]:.6f}"

# 寫入新檔案
with open(output_path, 'w') as f:
    for row in all_data:
        f.write(' '.join(row) + '\n')
plt.figure(figsize=(18, 4))
plt.plot(col11_data, label="Original Signal", color='blue',alpha = 0.7)
plt.plot(col11_smooth, label="uniform_filter1d", color='red', linestyle='--')
# plt.axvline(x=1778, color='black', linestyle=':', label="x=1778")  
# plt.axvline(x=1850, color='black', linestyle=':', label="x=1850")  
# plt.axvline(x=2004, color='black', linestyle=':', label="x=2004")  
# plt.axvline(x=2088, color='black', linestyle=':', label="x=2088")
plt.title("Smoothed of Column 11")
plt.xlabel("Frame Index")
plt.ylabel("Y Value")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

import cv2
import numpy as np
import matplotlib.pyplot as plt

# === 1. 讀取影片 ===
video_path = r"D:\Kady\swimmer coco\Swimming stroke recognition\SVM\Excellent_20240619_freestyle_M_3_1.mp4"  
cap = cv2.VideoCapture(video_path)

ret, frame = cap.read()
if not ret:
    print("Can not read.")
    cap.release()
    exit()

# === 2. 轉換到 HSV 空間找藍色 ===
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
lower_blue = np.array([80, 50, 50])
upper_blue = np.array([140, 255, 255])
mask = cv2.inRange(hsv, lower_blue, upper_blue)

# 去除小雜點
kernel = np.ones((5,5), np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

# === 3. 找輪廓並框出最大藍色區域 ===
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
frame_with_line = frame.copy()

if contours:
    largest_contour = max(contours, key=cv2.contourArea)
    
    # 畫紅框（方便觀察）
    x, y, w, h = cv2.boundingRect(largest_contour)
    cv2.rectangle(frame_with_line, (x, y), (x+w, y+h), (0, 0, 255), 5)
    
    # 找藍色區域最頂端 y 值
    waterline_y = np.min(largest_contour[:, :, 1])
    
    # 畫藍線（代表水面）
    cv2.line(frame_with_line, (0, waterline_y), (frame.shape[1], waterline_y), (255, 0, 0), 5)
    print(f"水面線 y = {waterline_y}")
else:
    print("找不到藍色區域")


# === 4. 顯示於 Jupyter ===
frame_rgb = cv2.cvtColor(frame_with_line, cv2.COLOR_BGR2RGB)
plt.figure(figsize=(12, 6))
# plt.imshow(mask, cmap='gray')
plt.imshow(frame_rgb)
# plt.title("Blue Mask")
plt.title("Waterline (Top of Blue Region)")
plt.axis('off')
plt.show()

cap.release()

def read_and_process_txt(file_path):
    with open(file_path, 'r') as file:
        data = [line.strip().split() for line in file.readlines()]  
    
    segments = []
    current_segment = []

    for line in data:
        frameid = int(line[0]) 
        value = float(line[8])    

        if value < 360:
            current_segment.append((frameid, value))  # 將 frameid 和數值一起記錄
        else:
            # 如果遇到大於等於360的數值，並且目前已有區段，則保存當前區段
            if current_segment:
                segments.append(current_segment)
                current_segment = []

    # 如果最後一個區段還有數據，將其加進區段列表
    if current_segment:
        segments.append(current_segment)
    
    for i, segment in enumerate(segments):
        first_frameid, first_value = segment[0]
        last_frameid, last_value = segment[-1]
        print(f"Segment {i+1}: Head = (FrameID: {first_frameid}, Value: {first_value}), "
              f"Tail = (FrameID: {last_frameid}, Value: {last_value})")

file_path = r"D:\Kady\swimmer coco\Swimming stroke recognition\SVM\FFT\Excellent_20230414_freestyle_M_3 (3)_1_smoothed.txt"
read_and_process_txt(file_path)

import pandas as pd
import matplotlib.pyplot as plt

# 定義預期的列數
EXPECTED_COLS = 12

def read_and_clean_txt(path, expected_cols=EXPECTED_COLS):
    data = []
    with open(path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 12:  # 至少要有 frame_id + 第12欄
                try:
                    frame_id = int(parts[0])
                    col8 = float(parts[8])  # index=8 仰式頭部
                    data.append((frame_id, col8))
                except:
                    continue
    return pd.DataFrame(data, columns=['frame_id', 'col8'])

# 讀取 txt 文件並處理數據
file_path = r"D:\Kady\swimmer coco\Swimming stroke recognition\SVM\FFT\Excellent_20230414_freestyle_M_3 (3)_1_smoothed.txt"
df = read_and_clean_txt(file_path)

# 生成區段（每次遇到大於等於360的值，直到下一次大於等於360的值，則是一個區段）
segments = []
current_segment = []

# 標記是否正在處理區段
in_segment = False

for i, row in df.iterrows():
    frameid = row['frame_id']
    value = row['col8']

    if value >= 358:  # 當數值大於等於360時
        if not in_segment:  # 如果目前還沒進入區段
            in_segment = True  # 開始新的區段
            current_segment = [(frameid, value)]  # 記錄此區段的第一個數值
        else:
            current_segment.append((frameid, value))  # 繼續加入當前區段
    else:
        if in_segment:  # 如果當前值小於360，並且已經進入過區段
            segments.append(current_segment)  # 結束當前區段
            in_segment = False  # 結束區段
            current_segment = []  # 清空當前區段

# 確保最後的區段也會被處理
if current_segment:
    segments.append(current_segment)

# 計算每個區段的長度（區段的大小）
segment_lengths = [(segment, len(segment)) for segment in segments]

# 排序並選擇出最大的兩個區段
segment_lengths.sort(key=lambda x: x[1], reverse=True)
largest_segments = segment_lengths[:2]

# 繪製波形圖
fig, ax = plt.subplots(figsize=(18, 4))

# 畫出整體的 Col 8 值（橙色線）
ax.plot(df['frame_id'], df['col8'], color='orange')

# 標註大於等於360的區段（用紅色線條畫出）
for segment in segments:
    segment_frameids = [s[0] for s in segment]
    segment_values = [s[1] for s in segment]

    # 在圖中畫紅色區段線條
    ax.plot(segment_frameids, segment_values, color='red')

# 標註最大的兩個區段的頭尾 Frame ID
for i, (segment, length) in enumerate(largest_segments):
    start_frameid, start_value = segment[0]
    end_frameid, end_value = segment[-1]

    # 在最大兩個區段的頭尾位置畫垂直線
    ax.axvline(x=start_frameid, color='green', linestyle='--', linewidth=1)
    ax.axvline(x=end_frameid, color='green', linestyle='--', linewidth=1)

    # 在垂直線旁邊標註 frameid
    ax.text(start_frameid, df['col8'].min(), f'{start_frameid}', color='black', ha='center', va='top')
    ax.text(end_frameid, df['col8'].min(), f'{end_frameid}', color='black', ha='center', va='top')

# 設定標題和座標軸標籤
ax.set_title('Underwater Segment')
ax.set_xlabel('Frame ID')
ax.set_ylabel('Value')
ax.grid(True)

# 顯示圖表
plt.tight_layout()
plt.show()
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.signal import argrelextrema
# 讀取輸出的 TXT 文件
input_file = r"D:\Kady\swimmer coco\kick_data\predict_train8_video\49\real_time_picture_49_1_angle.txt"
frame_ids = []
angles = []

# 讀取文件並提取 frame_id 和 angle
with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    values = line.split()
    
    if len(values) >= 2:  # 確保有 frame_id 和角度
        frame_id = int(values[0])
        angle = float(values[1])
        
        frame_ids.append(frame_id)
        angles.append(angle)
        
# --- 1. 手動設定區間 ---
start_frame = 417
end_frame = 552

# --- 2. 取得該區間的索引 ---
start_idx = frame_ids.index(start_frame)
end_idx = frame_ids.index(end_frame)

# --- 3. 找出該區段內的波谷（局部最小值） ---
sub_angles = np.array(angles[start_idx:end_idx+1])
sub_frames = frame_ids[start_idx:end_idx+1]

# 找出所有波谷：比較方式是小於相鄰的值
local_min_indices = argrelextrema(sub_angles, np.less, order=30)[0]  # 表示相鄰30個值比較

# --- 畫圖 ---
plt.figure(figsize=(18, 6))
plt.plot(frame_ids, angles, label='kick angle', color='b', linestyle='-')

if len(local_min_indices) > 0:
    local_min_frames = [sub_frames[i] for i in local_min_indices]
    local_min_values = [sub_angles[i] for i in local_min_indices]
    plt.scatter(local_min_frames, local_min_values, color='red', marker='o', label='Minima angle', zorder=6)
    # 標註數值
    for i in range(len(local_min_indices)):
        plt.text(local_min_frames[i], local_min_values[i] - 3, f'{local_min_values[i]:.1f}', 
                 color='red', ha='center', va='top', fontsize=9)
        
# 印出所有 local minima 的角度與對應 frame_id
print("找到的波谷點（local minima）：")
for i in range(len(local_min_indices)):
    print(f"Frame {local_min_frames[i]} - Angle {local_min_values[i]:.2f}")
# 標題、圖例等
plt.title('kick angle (Video 52)')
plt.xlabel('Frames')
plt.ylabel('Angle (°)')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig(output_image_file)
plt.show()