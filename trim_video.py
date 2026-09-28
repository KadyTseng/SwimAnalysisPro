import subprocess
import sys
import os

def trim_video(input_path, output_path, start_time="00:00:16"):
    """
    裁切影片，跳過前面的秒數。
    預設為跳過前 16 秒 (start_time="00:00:16")。
    """
    if not os.path.exists(input_path):
        print(f"錯誤：找不到輸入檔案 '{input_path}'")
        return

    # 建立 ffmpeg 指令
    # -ss : 指定開始時間
    # -i : 輸入檔案
    # -c copy : 複製影像與聲音串流，不重新編碼（處理速度極快，且不失真）
    command = [
        "ffmpeg",
        "-ss", str(start_time),
        "-i", input_path,
        "-c", "copy",
        output_path
    ]

    try:
        print(f"執行指令: {' '.join(command)}")
        # 執行指令並等待完成
        subprocess.run(command, check=True)
        print(f"\n[成功] 裁切影片完成！已儲存至 '{output_path}'")
    except subprocess.CalledProcessError as e:
        print(f"裁切影片時發生錯誤: {e}")
    except FileNotFoundError:
        print("錯誤：找不到 ffmpeg 執行檔。")
        print("請確認您已經安裝了 FFmpeg，並將其加入了系統的 PATH 環境變數中。")
        print("下載連結：https://ffmpeg.org/download.html")

if __name__ == "__main__":
    # 檢查命令列參數
    if len(sys.argv) < 3:
        print("使用方式: python trim_video.py <輸入影片路徑> <輸出影片路徑>")
        print("範例: python trim_video.py input.mp4 output.mp4")
        sys.exit(1)
        
    input_video = sys.argv[1]
    output_video = sys.argv[2]
    
    # 執行裁切 (設定跳過前 16 秒)
    trim_video(input_video, output_video, start_time="00:00:16")
