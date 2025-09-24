# BD/orchestrator.py

import os, cv2

from BD.pose_estimator import run_pose_estimation
from BD.txt_base import process_keypoint_txt
from BD.diving_analyzer_track_angles import analyze_diving_and_kicking
from BD.stroke_style_recognizer import analyze_stroke

from BD.stroke_counter.freestyle_counter import count_freestyle_strokes
from BD.stroke_counter.breaststroke_counter import count_breaststroke_strokes
from BD.stroke_counter.butterfly_counter import count_butterfly_strokes
from BD.stroke_counter.backstroke_counter import (
    generate_smoothed_txt,
    find_touch_frame,
    count_backstroke_strokes
)

from BD.split_speed_analyzer import analyze_split_times  
from BD.video_postprocessor import overlay_results_on_video
from BD.focus_tracking_view import export_focus_only_video

def run_full_analysis(model_path, video_path, output_dir):
    # Step 1: 姿態估計
    video_out, txt_out = run_pose_estimation(model_path, video_path, output_dir)

    # Step 2: 關節點TXT內插與儲存
    final_output_path = os.path.join(output_dir, "final_output.txt")
    df = process_keypoint_txt(txt_out, save_final_output=True, final_output=final_output_path)

    # Step 3: 平滑 shoulder Y
    smoothed_txt_path = generate_smoothed_txt(final_output_path)

    # Step 4: 潛泳與踢腿分析（取得 s1, e1, s2, e2, waterline_y）
    s1, e1, s2, e2, waterline_y = analyze_diving_and_kicking(final_output_path)

    # Step 5: 偵測觸牆幀
    touch_frame = find_touch_frame(final_output_path)

    # Step 6: 判斷泳姿
    # 需要提供影片、骨架 txt、SVM 模型
    stroke_label_int = analyze_stroke(video_path, final_output_path, "path/to/svm_model.pkl")

    # 對應英文泳姿名稱
    label_dict = {0: "backstroke", 1: "breaststroke", 2: "freestyle", 3: "butterfly"}
    stroke_style = label_dict[stroke_label_int]

    print("辨識泳姿:", stroke_style)

    # Step 7: 根據泳姿呼叫對應划手次數分析器
    if stroke_style == 'backstroke':
        stroke_result = count_backstroke_strokes(
            smoothed_txt_path, waterline_y, s1, e1, s2, e2, touch_frame)
    elif stroke_style == 'freestyle':
        stroke_result = count_freestyle_strokes(
            smoothed_txt_path, waterline_y, s1, e1, s2, e2, touch_frame)
    elif stroke_style == 'breaststroke':
        stroke_result = count_breaststroke_strokes(
            smoothed_txt_path, waterline_y, s1, e1, s2, e2, touch_frame)
    elif stroke_style == 'butterfly':
        stroke_result = count_butterfly_strokes(
            smoothed_txt_path, waterline_y, s1, e1, s2, e2, touch_frame)
    else:
        raise ValueError(f"無法辨識泳姿: {stroke_style}")

    # Step 8: 取得影片fps與寬度，計算距離線位置
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()
    
    d15m_x0 = width * 2 / 5
    d25m_x0 = 150
    d50m_x0 = width
    start_frame = s1  
    
    passed, total_time = analyze_split_times(
        final_output_path, start_frame, fps, d15m_x0, d25m_x0, d50m_x0)
    
    
    # Step 9: 產生追焦影片
    focus_video_path = os.path.join(output_dir, "focus_only.mp4")
    export_focus_only_video(video_path, smoothed_txt_path, focus_video_path)
    
    
    
    
    # 輸出後製影片路徑
    processed_video_path = os.path.join(output_dir, "processed_" + os.path.basename(video_path))
    
    overlay_results_on_video(
        video_path,
        analysis_results={"stroke_frames": stroke_result.get("stroke_frames", [])},
        output_path=processed_video_path,
        split_times={
            "passed": passed,
            "start_frame": start_frame,
            "fps": fps,
            "line_positions": {"15m": d15m_x0, "25m": d25m_x0, "50m": d50m_x0}
        },
        focus_video_path=focus_video_path
    )
    return {
        "stroke_style": stroke_style,
        "final_output": final_output_path,
        "smoothed_txt": smoothed_txt_path,
        "touch_frame": touch_frame,
        "diving_segments": {"s1": s1, "e1": e1, "s2": s2, "e2": e2},
        "waterline_y": waterline_y,
        "stroke_result": stroke_result,
        "passed": passed,
        "total_time": total_time,
        "focus_video_path": focus_video_path,
        "processed_video_path": processed_video_path
    }


if __name__ == "__main__":
    model_path = "path/to/your_model.pt"
    video_path = "path/to/your_video.mp4"
    output_dir = "path/to/output_folder"

    result = run_full_analysis(model_path, video_path, output_dir)
    print(result)
