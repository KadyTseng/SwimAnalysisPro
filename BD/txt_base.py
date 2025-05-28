import numpy as np
import pandas as pd

input_txt = r"C:\Users\USER\Desktop\predict\Excellent_20230414_freestyle_M_3 (4).txt"            #讀keypoints最一開始預測的txt
first_output = input_txt.replace(".txt", "_1.txt")                                               #補值內插

# 讀取資料
with open(input_txt, 'r') as f:
    lines = f.readlines()

# 根據第一筆有資料的列決定欄位數量
for line in lines:
    if "no detection" not in line:
        num_columns = len(line.strip().split())
        break

data = []

# 處理每一行資料
for line in lines:
    parts = line.strip().split()
    if "no" in parts:
        frame_id = int(parts[0])
        row = [frame_id, 0] + [np.nan] * (num_columns - 2)
    else:
        row = []
        for v in parts:
            try:
                row.append(float(v))
            except:
                row.append(v)
    data.append(row)

df = pd.DataFrame(data)

# 建立欄位名稱
cols = ['frame_id', 'class', 'x_center', 'y_center', 'width', 'height', 'conf']
for i in range(1, 8):
    cols += [f'kp{i}_x', f'kp{i}_y', f'kp{i}_conf']
df.columns = cols

#  === 儲存第一階段清理後的 TXT（處理 "no detection"）===
# with open(step1_output, 'w') as f:
#     for _, row in df.iterrows():
#         row_str = ' '.join(
#             str(int(v)) if df.columns[i] in ['frame_id', 'class'] else f"{v:.6f}"
#             for i, v in enumerate(row)
#         )
#         f.write(row_str + '\n')
# print(f"第一步清理完成，儲存為: {step1_output}")
#  ======================================================

# ===處理關鍵點xy欄位===
columns_to_check = [7, 8, 10, 11, 13, 14, 16, 17, 19, 20, 22, 23, 25, 26]  # 0-indexed
for col_idx in columns_to_check:
    col_name = df.columns[col_idx]
    
    # 1. 小於10的設為 nan (假設那些是被填0的)
    df.loc[df[col_name] < 10, col_name] = np.nan

    # 2. 與前一筆差值 > 50 的設為 nan (2-3步是跳掉的)
    diff_prev = df[col_name].diff().abs()
    df.loc[diff_prev > 50, col_name] = np.nan

    # 3. 與後一筆差值 > 50 的設為 nan
    diff_next = df[col_name].diff(periods=-1).abs()
    df.loc[diff_next > 50, col_name] = np.nan
    
# === 中繼檔案儲存：過濾小於10 & 跳動過大之後 ===
# filtered_output = input_txt.replace('.txt', '_filtered.txt')
# with open(filtered_output, 'w') as f:
#     for _, row in df.iterrows():
#         row_str = ' '.join(
#             str(int(v)) if df.columns[i] in ['frame_id', 'class'] else f"{v:.6f}"
#             for i, v in enumerate(row)
#         )
#         f.write(row_str + '\n')
# print(f"中繼檔儲存完成（過濾異常值後）: {filtered_output}")
#  ======================================================

# 內插所有 nan 
df = df.interpolate(method='linear', limit_direction='both')

# === 儲存第二階段補齊後的 TXT ===
with open(first_output, 'w') as f:
    for _, row in df.iterrows():
        row_str = ' '.join(
            str(int(v)) if df.columns[i] in ['frame_id', 'class'] else f"{v:.6f}"
            for i, v in enumerate(row)
        )
        f.write(row_str + '\n')

final_output = first_output.replace(".txt", "_smoothed.txt")                                # 平滑

df = pd.read_csv(first_output, sep='\s+', header=None)

# 要平滑的BBOX.7SK
smooth_columns = [2, 3, 4, 5, 7, 8, 10, 11, 13, 14, 16, 17, 19, 20, 22, 23, 25, 26]

# 對每一個指定欄位做平滑處理
for col in smooth_columns:
    df[col] = df[col].rolling(window=7, min_periods=1, center=True).mean()

with open(final_output, 'w') as f:
    for _, row in df.iterrows():
        row_str = ' '.join(
            str(int(val)) if i in [0, 1] else f"{val:.6f}" for i, val in enumerate(row)
        )
        f.write(row_str + '\n')

