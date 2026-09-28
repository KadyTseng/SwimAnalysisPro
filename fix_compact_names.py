import glob
import os
import json

def fix_compact_names(folder_path):
    files = glob.glob(os.path.join(folder_path, "*_a_compact.txt"))
    count = 0  
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            # 簡易檢查是否包含這三種 key
            if '"Pull regions":' in content and '"Recovery regions":' in content and '"Glide regions":' in content:
                new_content = content.replace('"Pull regions":', '"Propulsion":')
                new_content = new_content.replace('"Recovery regions":', '"Recovery":')
                new_content = new_content.replace('"Glide regions":', '"Glide":')
                
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"✅ 已修正: {os.path.basename(path)}")
                count += 1
        except Exception as e:
            print(f"❌ 錯誤 {os.path.basename(path)}: {e}")
            
    print(f"\n🎉 完成！共修正了 {count} 個檔案。")

if __name__ == "__main__":
    target_folder = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\batch_processed_videos(validation)\Stroke_Phase_Frames"
    print(f"正在掃描資料夾: {target_folder}")
    fix_compact_names(target_folder)
