import os
import json
import argparse
import glob

def format_compact_phase_file(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 整理各類別，只保留需要的階段(regions)資訊
    new_data = {}
    for lap_key, lap_data in data.items():
        clean_data = lap_data.copy()
        # 直接刪除不需要的鍵，保留原汁原味的最外層分類 (propulsion, recovery, glide 或 Pull, Push, Recovery)
        unwanted_keys = ['values', 'frames', 'segment_metrics', 'regions', 'values_shoulder', 'values_wrist']
        for unwanted in unwanted_keys:
            if unwanted in clean_data:
                del clean_data[unwanted]
        
        new_data[lap_key] = clean_data
            
    # 自訂 JSON 序列化，讓外層維持結構，內層陣列拿掉空白與換行
    lines = ["{"]
    for i, (lap_key, lap_data) in enumerate(new_data.items()):
        lines.append(f'    "{lap_key}": {{')
        
        keys = list(lap_data.keys())
        for j, key in enumerate(keys):
            val = lap_data[key]
            # 將 list 壓縮在一行內並加上逗號
            compact_list = json.dumps(val, separators=(', ', ': '))
            comma = "," if j < len(keys) - 1 else ""
            lines.append(f'        "{key}": {compact_list}{comma}')
            
        lap_comma = "," if i < len(new_data) - 1 else ""
        lines.append("    }" + lap_comma)
    lines.append("}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
    
    print(f"✅ 成功產出精簡格式檔案: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="將 _a.txt 格式化為沒有 values 且壓縮陣列的精簡版")
    parser.add_argument("input_path", help="要處理的 _a.txt 路徑，或是包含 txt 的資料夾")
    args = parser.parse_args()

    if os.path.isdir(args.input_path):
        txt_files = glob.glob(os.path.join(args.input_path, "*_a.txt"))
        for txt_file in txt_files:
            if not txt_file.endswith("_compact.txt"):
                out_name = txt_file.replace("_a.txt", "_a_compact.txt")
                format_compact_phase_file(txt_file, out_name)
    else:
        out_name = args.input_path.replace("_a.txt", "_a_compact.txt")
        # 即使副檔名不完全是 _a.txt 也能處理
        if out_name == args.input_path:
             out_name = args.input_path.replace(".txt", "_compact.txt")
             
        format_compact_phase_file(args.input_path, out_name)
