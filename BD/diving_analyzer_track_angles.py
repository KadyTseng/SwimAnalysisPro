import numpy as np
import matplotlib.pyplot as plt
import cv2
import pandas as pd

# === 1. 讀影片 定義水平面 ===
video_path = r"D:\Kady\swimmer coco\Swimming stroke recognition\test_all\Excellent\backstroke\Excellent_20230414_backstroke_F_3 (1).mp4" 
cap = cv2.VideoCapture(video_path)

ret, frame = cap.read()
if not ret:
    print("Can not read.")
    cap.release()
    exit()

hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
lower_blue = np.array([80, 50, 50])
upper_blue = np.array([140, 255, 255])       # 藍色範圍
mask = cv2.inRange(hsv, lower_blue, upper_blue)

kernel = np.ones((5,5), np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
frame_with_line = frame.copy()

if contours:
    largest_contour = max(contours, key=cv2.contourArea)
    
    x, y, w, h = cv2.boundingRect(largest_contour)
    cv2.rectangle(frame_with_line, (x, y), (x+w, y+h), (0, 0, 255), 5)
    
    waterline_y = np.min(largest_contour[:, :, 1])
    
    cv2.line(frame_with_line, (0, waterline_y), (frame.shape[1], waterline_y), (255, 0, 0), 5)
    # print(f"water level y = {waterline_y}")
else:
    print("can not find water level.")

# === 2. 讀出frame和頭部y和BBOX ===
file_path = r"D:\Kady\swimmer coco\Swimming stroke recognition\test_all\Excellent\backstroke\Excellent_20230414_backstroke_F_3 (1).txt"  # 讀data資料夾的_1_smoothed.txt

def read_and_clean_txt(path, expected_cols= 12):
    data = []
    with open(path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 12: 
                try:
                    frame_id = int(parts[0])
                    bbox_x = float(parts[2])  
                    bbox_y = float(parts[3])
                    col8 = float(parts[8])  # index=8 頭部y
                    data.append((frame_id, bbox_x, bbox_y, col8))
                except:
                    continue
    return pd.DataFrame(data, columns=['frame_id','bbox_x', 'bbox_y','col8'])

df = read_and_clean_txt(file_path)          

# === 3. 找出頭在水下的最大兩個區段  ===
segments = []
current_segment = []

in_segment = False

for i, row in df.iterrows():
    frameid = row['frame_id']
    value = row['col8']

    if value >= waterline_y:  
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

if current_segment:
    segments.append(current_segment)

segment_lengths = [(segment, len(segment)) for segment in segments]
segment_lengths.sort(key=lambda x: x[1], reverse=True)
largest_segments = segment_lengths[:2]

s1 = int(largest_segments[0][0][0][0])       
e1 = int(largest_segments[0][0][-1][0])
s2 = int(largest_segments[1][0][0][0])
e2 = int(largest_segments[1][0][-1][0])                 # 取得區段的頭尾 frame_id：潛泳第一區段記為 (s1, e1)，第二區段記為 (s2, e2)

if s1 > s2:                                           # 先demo去程就好
    s1, e1, s2, e2 = s2, e2, s1, e1
    
# === 4. 潛泳區段的踢腿角度  ===

output_angle = r"D:\Kady\swimmer coco\Swimming stroke recognition\test_all\Excellent\backstroke\Excellent_20230414_backstroke_F_3 (1)_angle.txt"      # data資料夾 存_angle.txt

def calculate_angle(A, B, C):
    """計算 B 點的夾角 """
    BA = np.array(A) - np.array(B)
    BC = np.array(C) - np.array(B)
    
    cosine_theta = np.dot(BA, BC) / (np.linalg.norm(BA) * np.linalg.norm(BC))
    angle = np.arccos(np.clip(cosine_theta, -1.0, 1.0)) * 180 / np.pi
    return angle

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

output_lines = []

for line in lines:
    values = line.split()
    
    if len(values) > 0 and values[0].isdigit():
        frame_id = int(values[0])
    else:
        frame_id = -1  

    if "no" in values or len(values) < 21:
        output_lines.append(f"{frame_id} \n")  
        continue

    values = list(map(float, values))

    A = (values[19], values[20])   # 髖座標 (index= 4)
    B = (values[22], values[23])   # 膝座標 (index= 5)
    C = (values[25], values[26])   # 腳踝座標 (index= 6)

    angle_1 = calculate_angle(A, B, C)
    angle_2 = calculate_angle(C, B, A)
    min_angle = min(angle_1, angle_2)

    # 新的 txt 格式：frame_id angle A B C
    new_line = f"{frame_id} {min_angle:.2f} {A[0]:.2f} {A[1]:.2f} {B[0]:.2f} {B[1]:.2f} {C[0]:.2f} {C[1]:.2f}\n"
    output_lines.append(new_line)

with open(output_angle, "w", encoding="utf-8") as f:
    f.writelines(output_lines)

""" 從角度txt找潛泳段最小的 """
from scipy.signal import argrelextrema

frame_ids = []
angles = []

with open(output_angle, "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    values = line.split()
    
    if len(values) >= 2:  
        frameid = int(values[0])
        angle = float(values[1])
        
        frame_ids.append(frameid)
        angles.append(angle)
        
start_frame = s1
end_frame = e1

start_idx = frame_ids.index(start_frame)
end_idx = frame_ids.index(end_frame)

sub_angles = np.array(angles[start_idx:end_idx+1])                 # 區段
sub_frames = frame_ids[start_idx:end_idx+1]  

local_min_indices = argrelextrema(sub_angles, np.less, order=30)[0]  # 找出所有波谷：比較方式是小於相鄰的值(30個值去比)

'''要把這些角度顯示在後製的影片內'''
if len(local_min_indices) > 0:
    local_min_frames = [sub_frames[i] for i in local_min_indices]
    local_min_values = [sub_angles[i] for i in local_min_indices]              # 這兩個變數是最小角度的時間跟角度

# === 5. 潛泳區段的軌跡(後製的部分 可能可以放到其他py)  ===
''' 這邊要整合到後製那邊去 '''
output_path = r'D:\Kady\swimmer coco\Swimming stroke recognition\test_all\Excellent\backstroke\Excellent_20230414_backstroke_F_3 (1)_output_with_trajectory.mp4'

df = read_and_clean_txt(file_path)

cap = cv2.VideoCapture(video_path)
fps = cap.get(cv2.CAP_PROP_FPS)
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  
out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

track_points = []
frame_id = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    row = df[df['frame_id'] == frame_id]
    if not row.empty:
        x = int(row['bbox_x'].values[0])
        y = int(row['bbox_y'].values[0])

        if s1 <= frame_id <= e1:       # 畫第一段潛泳
            track_points.append((x, y))

    for i in range(len(track_points) - 1):
        cv2.line(frame, track_points[i], track_points[i + 1], (0, 0, 255), 3)

    out.write(frame)
    frame_id += 1

cap.release()
out.release()