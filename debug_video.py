import os
import sys
import traceback
from pathlib import Path

# Add project root to path
sys.path.append("/home/kady6582/SwimAnalysisPro")

from BD.orchestrator import run_full_analysis

def status_callback(progress, message=""):
    print(f"[STATUS] Progress: {progress}%, Message: {message}")

def debug_video(video_path_str):
    print(f"\n--- Starting Debug for {video_path_str} ---")
    video_path = Path(video_path_str)
    
    if not video_path.exists():
        print(f"File not found: {video_path}")
        return
        
    output_dir = Path("/home/kady6582/SwimAnalysisPro/test_outputs") / video_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    
    pose_model_path = "/home/kady6582/SwimAnalysisPro/data/models/best_1.pt"
    style_model_path = "/home/kady6582/SwimAnalysisPro/data/models/svm_model_new_3.pkl"
    ffmpeg_path = "/usr/bin/ffmpeg"
    
    try:
        results = run_full_analysis(
            pose_model_path,
            style_model_path,
            str(video_path),
            str(output_dir),
            ffmpeg_path,
            status_callback
        )
        print("\n--- Analysis Completed ---")
        
        # 將結果輸出成 JSON (處理 Numpy 陣列轉譯問題)
        if results:
            import json
            import numpy as np
            
            def default_converter(o):
                if isinstance(o, np.ndarray): return o.tolist()
                if isinstance(o, np.integer): return int(o)
                if isinstance(o, np.floating): return float(o)
                return str(o)
                
            json_path = output_dir / f"{video_path.stem}_analysis_result.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=4, default=default_converter)
                
            print(f"✅ 整體分析數值已儲存為 JSON: {json_path}")
        else:
            print("  run_full_analysis returned None")
    except Exception as e:
        print(f"\n--- Analysis FAILED ---")
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Message: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    demo_dir = Path("/home/kady6582/SwimAnalysisPro/demo_debug_videos")
    videos = list(demo_dir.glob("*.mp4"))
    
    if not videos:
        print(f"No videos found in {demo_dir}")
    else:
        target_names = ["real_time_picture (432)", "real_time_picture (434)", "real_time_picture (435)"]
        for v in videos:
            if v.stem in target_names:
                debug_video(str(v))
