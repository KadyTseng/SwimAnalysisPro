import os
import subprocess

def cut_video(input_path, output_dir, time_segments, ffmpeg_path="ffmpeg"):
    """
    使用 ffmpeg 進行無損影片裁切 (c:v copy, c:a copy)
    
    :param input_path: 輸入影片路徑
    :param output_dir: 輸出資料夾路徑
    :param time_segments: 裁切時間區段列表，格式為 [(開始時間, 結束時間), ...]
                         時間可以使用 "HH:MM:SS", "MM:SS" 或秒數 (例如 55)
    :param ffmpeg_path: ffmpeg 執行檔路徑，若已加入環境變數可直接用 "ffmpeg"
    """
    if not os.path.exists(input_path):
        print(f"❌ 找不到輸入影片: {input_path}")
        return

    os.makedirs(output_dir, exist_ok=True)
    
    # 取得影片副檔名
    _, ext = os.path.splitext(input_path)
    
    print(f"🎬 開始裁切影片: {os.path.basename(input_path)}")
    print(f"📂 輸出目錄: {output_dir}")
    print("-" * 50)

    for i, (start, end) in enumerate(time_segments, start=1):
        output_filename = f"segment_{i}_{start.replace(':', '_')}_to_{end.replace(':', '_')}{ext}"
        output_path = os.path.join(output_dir, output_filename)
        
        # 建立 ffmpeg 指令
        # 使用 -c copy 可以實現無損秒切，不需重新編碼，速度極快
        cmd = [
            ffmpeg_path,
            "-ss", str(start),
            "-to", str(end),
            "-i", input_path,
            "-c", "copy",
            "-y",  # 若檔案已存在則直接覆蓋
            output_path
        ]
        
        print(f"⚡ 正在裁切第 {i} 個區段: {start} ~ {end} -> {output_filename}")
        
        try:
            # 執行指令並隱藏 ffmpeg 的詳細輸出，只在錯誤時顯示
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            if result.returncode == 0:
                print(f"✅ 成功儲存: {output_path}")
            else:
                print(f"❌ 裁切失敗，錯誤訊息:\n{result.stderr}")
        except Exception as e:
            print(f"❌ 執行發生異常: {e}")
            
    print("-" * 50)
    print("🎉 所有區段裁切完成！")

if __name__ == "__main__":
    # ==================== 設定區 ====================
    # 1. 請填入您的來源影片路徑 (支援 mp4, avi, mkv 等)
    INPUT_VIDEO = r"E:\2025_CATS\泳池demo\網頁測試_即時錄影分析_即時分段計時.mp4" 
    
    # 2. 裁切後的影片儲存資料夾
    OUTPUT_FOLDER = r"E:\2025_CATS\泳池demo\cut_segments"
    
    # 3. 設定您的 ffmpeg 執行檔路徑 (若環境變數已有，保持 "ffmpeg" 即可)
    # Windows 範例: r"C:\ffmpeg\bin\ffmpeg.exe"
    FFMPEG_PATH = "ffmpeg" 
    
    # 4. 裁切的時間點列表 (可填寫 "MM:SS" 或 "HH:MM:SS" 或純秒數)
    # 您提到了 6 個區段，但只列出了 5 個，這裡我先幫您設定這 5 個，並留下一行註解供您彈性增加第 6 個！
    TIME_SEGMENTS = [
        ("00:00", "00:55"),      # 1. 0 ~ 55sec
        ("00:55", "02:40"),      # 2. 55s ~ 2:40
        ("02:40", "08:10"),      # 3. 2:40 ~ 8:10
        ("08:10", "12:37"),      # 4. 8:10 ~ 12:37
        ("12:40", "16:15"),      # 5. 12:40 ~ 16:15
        ("16:15", "17:00"),      # 6. 16:15 ~ 17:00
        ("17:00", "40:18"),    # 7. (備用) 第 6 個區段，例如裁切剩餘部分
    ]
    # ===============================================
    
    cut_video(INPUT_VIDEO, OUTPUT_FOLDER, TIME_SEGMENTS, ffmpeg_path=FFMPEG_PATH)
