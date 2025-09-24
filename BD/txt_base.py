# BD/txt_base.py
import numpy as np
import pandas as pd

def process_keypoints_txt(
    input_txt: str,
    first_output: str = None,
    filtered_output: str = None,
    final_output: str = None,
    save_filtered: bool = False,
    save_first_output: bool = False,
    save_final_output: bool = True
):
    """
    讀取 keypoints txt，清理異常點，補值內插並平滑。
    可選擇輸出各階段結果。

    參數:
    - input_txt: 原始 keypoints txt 路徑
    - first_output: 補值內插後輸出路徑
    - filtered_output: 過濾異常值後中繼檔案輸出路徑
    - final_output: 平滑後輸出路徑
    - save_filtered: 是否儲存過濾異常值後的中繼檔案
    - save_first_output: 是否儲存補值內插後檔案
    - save_final_output: 是否儲存平滑後檔案

    回傳:
    - 平滑後的 DataFrame
    """

    # 讀取資料
    with open(input_txt, 'r') as f:
        lines = f.readlines()

    # 根據第一筆有資料的列決定欄位數量
    num_columns = None
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

    # === 儲存過濾異常值後的中繼檔案（可選）===
    if save_filtered and filtered_output is not None:
        with open(filtered_output, 'w') as f:
            for _, row in df.iterrows():
                row_str = ' '.join(
                    str(int(v)) if df.columns[i] in ['frame_id', 'class'] else f"{v:.6f}"
                    for i, v in enumerate(row)
                )
                f.write(row_str + '\n')
        print(f"中繼檔儲存完成（過濾異常值後）: {filtered_output}")

    # === 處理關鍵點xy欄位異常值 ===
    columns_to_check = [7, 8, 10, 11, 13, 14, 16, 17, 19, 20, 22, 23, 25, 26]  # 0-indexed
    for col_idx in columns_to_check:
        col_name = df.columns[col_idx]

        # 1. 小於10設為 nan (假設是被填0的)
        df.loc[df[col_name] < 10, col_name] = np.nan

        # 2. 與前一筆差值 > 50 設為 nan
        diff_prev = df[col_name].diff().abs()
        df.loc[diff_prev > 50, col_name] = np.nan

        # 3. 與後一筆差值 > 50 設為 nan
        diff_next = df[col_name].diff(periods=-1).abs()
        df.loc[diff_next > 50, col_name] = np.nan

    # === 補值內插 ===
    df = df.interpolate(method='linear', limit_direction='both')

    # === 儲存第一階段補值內插後的 TXT（可選）===
    if save_first_output and first_output is not None:
        with open(first_output, 'w') as f:
            for _, row in df.iterrows():
                row_str = ' '.join(
                    str(int(v)) if df.columns[i] in ['frame_id', 'class'] else f"{v:.6f}"
                    for i, v in enumerate(row)
                )
                f.write(row_str + '\n')
        print(f"第一步清理完成，儲存為: {first_output}")

    # === 讀取補值內插後檔案，進行平滑 ===
    if first_output is not None:
        df = pd.read_csv(first_output, sep='\s+', header=None)
        df.columns = list(range(df.shape[1]))
    else:
        # 若沒指定檔案，使用目前df
        df.columns = list(range(df.shape[1]))

    # 平滑欄位（BBOX與7關鍵點）
    smooth_columns = [2, 3, 4, 5, 7, 8, 10, 11, 13, 14, 16, 17, 19, 20, 22, 23, 25, 26]
    for col in smooth_columns:
        df[col] = df[col].rolling(window=7, min_periods=1, center=True).mean()

    # === 儲存第二階段平滑後的 TXT（可選）===
    if save_final_output and final_output is not None:
        with open(final_output, 'w') as f:
            for _, row in df.iterrows():
                row_str = ' '.join(
                    str(int(val)) if i in [0, 1] else f"{val:.6f}" for i, val in enumerate(row)
                )
                f.write(row_str + '\n')
        print(f"第二步平滑完成，儲存為: {final_output}")
    else:
        final_output = None  # 防呆

    return final_output  # <<< 回傳檔案路徑給 orchestrator 或其他模組使用
# DEMO
# input_txt =r"D:\Kady\swimmer coco\anvanced stroke analysis\stroke_stage\butterfly\Excellent_20230414_butterfly_M_3 (1).txt"
# final_output = r"D:\Kady\swimmer coco\anvanced stroke analysis\stroke_stage\butterfly\Excellent_20230414_butterfly_M_3 (1)_1.txt"

# final_path = process_keypoints_txt(
#     input_txt=input_txt,
#     final_output=final_output,
#     save_final_output=True
# )
# DEMO
import os

def main():
    folder = r"D:\Kady\swimmer coco\kick_data\new\women"

    for fname in os.listdir(folder):
        if fname.endswith(".txt") and not fname.endswith(".n.txt"):
            input_txt = os.path.join(folder, fname)

            # 輸出命名：在原本檔名加上 "_1"
            base, ext = os.path.splitext(fname)
            final_output = os.path.join(folder, base + "_1.txt")

            print(f"🚀 處理檔案: {input_txt}")
            final_path = process_keypoints_txt(
                input_txt=input_txt,
                final_output=final_output,
                save_final_output=True
            )
            print(f"✅ 輸出完成: {final_path}")

if __name__ == "__main__":
    main()
