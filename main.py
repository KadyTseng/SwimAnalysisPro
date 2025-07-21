import sys
from PyQt5.QtWidgets import QApplication
from UI.main_window import MainWindow
from BD.orchestrator import run_full_analysis
import threading

def main():
    app = QApplication(sys.argv)
    window = MainWindow()

    window.controls.video_selected.connect(window.video_player.load_video)
    
    # 當使用者按「Video processing」按鈕時，跑後端分析與後製
    def on_video_processing():
        video_path = window.video_player.current_video_path 
        if not video_path:
            print("請先選擇影片")
            return
        
        output_dir = "data/processed_videos"  # 後製影片輸出資料夾
        model_path = "path/to/your_model.pt"  # 模型路徑，視情況改成參數或設定檔
    
    
        def worker():
            print("開始影片分析與後製...")
            result = run_full_analysis(model_path, video_path, output_dir)
            print("分析完成:", result)
            # 在 UI 執行緒載入後製影片
            window.video_player.load_video(result["processed_video_path"])

        threading.Thread(target=worker, daemon=True).start()

    window.controls.video_processing.connect(on_video_processing)

    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
