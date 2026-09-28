import os
import csv
import glob
import argparse
from pathlib import Path

# 從你原本的專案中引入核心分析功能
from BD.orchestrator import run_full_analysis

# 預設使用的模型路徑 (與 main.py 一致)
POSE_MODEL_PATH = os.path.abspath("data/models/best_1.pt")
STYLE_MODEL_PATH = os.path.abspath("data/models/svm_model_v2.pkl")
# 我們另外將 batch 的輸出隔離，避免混淆原有的 /data/processed_videos
OUTPUT_DIR_BASE = os.path.abspath("data/batch_processed_videos")
# FFMPEG 預設路徑
FFMPEG_EXECUTABLE_PATH = "ffmpeg"


def process_folder(folder_path, csv_writer):
    # 對該資料夾找出所有常見影片格式
    extensions = ['*.mp4', '*.avi', '*.mov']
    video_files = []
    for ext in extensions:
        video_files.extend(glob.glob(os.path.join(folder_path, ext)))
        # 考慮大寫副檔名
        video_files.extend(glob.glob(os.path.join(folder_path, ext.upper())))
    
    video_files = list(set(video_files))  # 移除重複項目
    
    print(f"\n=== 📂 正在掃描資料夾：{folder_path} ===")
    print(f"找到 {len(video_files)} 個影片。")

    for video_path in video_files:
        video_name = os.path.basename(video_path)
        print(f"\n▶️ 正在分析：{video_name}")
        
        # 針對每支影片獨立建立一個結果輸出資料夾
        video_id = os.path.splitext(video_name)[0]
        output_dir = os.path.join(OUTPUT_DIR_BASE, video_id)
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # orchestrator 會要求一個 status_callback 來顯示進度，這裡用 dummy pass 掉即可
            def dummy_callback(*args, **kwargs):
                pass
            
            # 使用絕對路徑確保不因為執行點不同而出錯
            abs_video_path = os.path.abspath(video_path)
            
            # 執行完整分析 (途中會自動在 data/Stroke_Phase_Frames 產出相位文字檔)
            # 我們傳入 save_postprocessed_video=False 來略過冗長的生成後製影片步驟，大幅提升速度！
            result = run_full_analysis(
                pose_model_path=POSE_MODEL_PATH,
                style_model_path=STYLE_MODEL_PATH,
                video_path=abs_video_path,
                output_dir=output_dir,
                ffmpeg_path=FFMPEG_EXECUTABLE_PATH,
                status_callback=dummy_callback,
                save_postprocessed_video=False
            )
            
            stroke_style = result.get("stroke_style", "Unknown")
            print(f"✅ 分析完成！{video_name} 的泳姿為：{stroke_style}")
            
            # 將結果寫入 CSV (包含資料夾來源、影片名稱、辨識出的泳姿)
            csv_writer.writerow([folder_path, video_name, stroke_style])
            
        except Exception as e:
            print(f"❌ 發生錯誤 {video_name}：{e}")
            csv_writer.writerow([folder_path, video_name, f"Error: {e}"])

def main():
    parser = argparse.ArgumentParser(description="批次分析多個資料夾中的游泳影片並輸出泳姿 CSV")
    
    # nargs='+' 允許使用者輸入多個資料夾路徑，以空白分隔
    parser.add_argument(
        '--folders', 
        nargs='+', 
        required=True, 
        help='請輸入要分析的資料夾路徑 (支援多個，以空白分隔)'
    )
    
    parser.add_argument(             
        '--output_csv',                          
        type=str, 
        default='stroke_results.csv', 
        help='輸出的 CSV 檔名 (預設為 stroke_results.csv)'
    )
    
    args = parser.parse_args()
    
    print(f"🚀 開始批處理分析，共指定 {len(args.folders)} 個資料夾。")
    print(f"📝 最終結果將會被存擋至：{args.output_csv}\n")
    
    # 建立/開啟 CSV 檔案並寫入標題列
    with open(args.output_csv, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        # 第一列：標題
        writer.writerow(['來源資料夾', '影片名稱', '模型辨識出之泳姿'])
        
        for folder in args.folders:
            if os.path.isdir(folder):
                process_folder(folder, writer)
            else:
                print(f"⚠️ 警告：找不到指定的資料夾 -> {folder}")
    
    print(f"\n🎉 批次處理全部結束！請查看 {args.output_csv} 以確認結果。")

if __name__ == "__main__":
    main()
