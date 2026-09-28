import os
import glob
import pandas as pd
import numpy as np
import joblib
from collections import Counter

def read_full_keypoints_txt(path, expected_cols=28):
    data = []
    with open(path, "r", encoding="utf-8") as f:
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

def process_keypoints(txt_folder, model_path, output_csv):
    print(f"Loading model: {model_path}")
    model = joblib.load(model_path)
    
    txt_files = glob.glob(os.path.join(txt_folder, "*.txt"))
    print(f"Found {len(txt_files)} txt files in {txt_folder}")
    
    label_map = {0: "Backstroke(0)", 1: "Breaststroke(1)", 2: "Freestyle(2)", 3: "Butterfly(3)"}
    
    results = []
    from sklearn.preprocessing import StandardScaler
    
    for txt_path in txt_files:
        fname = os.path.basename(txt_path)
        try:
            df = read_full_keypoints_txt(txt_path)
            if df.empty:
                results.append({"Video Name": fname, "Raw Label Int": -1, "Predicted Style": "Error: Empty Data"})
                continue
                
            selected_cols = ["frame_id", "col8", "col11", "col14", "col17", "col20", "col23", "col26"]
            # 確保欄位存在
            missing_cols = [c for c in selected_cols if c not in df.columns]
            if missing_cols:
                results.append({"Video Name": fname, "Raw Label Int": -1, "Predicted Style": f"Error: Missing {missing_cols}"})
                continue
                
            df_selected = df[selected_cols].copy()
            coords = df_selected.drop(columns=["frame_id"])
            
            # 標準化
            scaler = StandardScaler()
            coords_scaled = scaler.fit_transform(coords)
            
            # 推論
            y_pred = model.predict(coords_scaled)
            counter = Counter(y_pred)
            majority_label = int(counter.most_common(1)[0][0])
            
            results.append({
                "Video Name": fname,
                "Raw Label Int": majority_label,
                "Predicted Style": label_map.get(majority_label, f"Unknown_raw({majority_label})")
            })
            
        except Exception as e:
            print(f"Failed processing {fname}: {e}")
            results.append({"Video Name": fname, "Raw Label Int": -1, "Predicted Style": f"Error: {e}"})
            
    df_results = pd.DataFrame(results)
    df_results.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"✅ 完成！已儲存至 {output_csv}")

if __name__ == "__main__":
    txt_folder = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\batch_processed_videos(validation)\keypoints"
    model_path = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\svm_model_new_3.pkl"
    output_csv = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\stroke_results_svm_model_new_3.csv"
    
    process_keypoints(txt_folder, model_path, output_csv)
