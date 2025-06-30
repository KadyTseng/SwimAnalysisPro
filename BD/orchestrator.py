# BD/orchestrator.py

import os

from BD.pose_estimator import run_pose_estimation
from BD.txt_base import process_keypoint_txt
from BD.diving_analyzer_track_angles import analyze_diving_and_kicking
from BD.stroke_style_recognizer import recognize_stroke_style

from BD.stroke_counter.freestyle_counter import count_freestyle_strokes
from BD.stroke_counter.breaststroke_counter import count_breaststroke_strokes
from BD.stroke_counter.butterfly_counter import count_butterfly_strokes
from BD.stroke_counter.backstroke_counter import (
    generate_smoothed_txt,
    find_touch_frame,
    count_backstroke_strokes
)


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
    stroke_style = recognize_stroke_style(final_output_path)

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

    return {
        "stroke_style": stroke_style,
        "final_output": final_output_path,
        "smoothed_txt": smoothed_txt_path,
        "touch_frame": touch_frame,
        "diving_segments": {"s1": s1, "e1": e1, "s2": s2, "e2": e2},
        "waterline_y": waterline_y,
        "stroke_result": stroke_result,
    }


if __name__ == "__main__":
    model_path = "path/to/your_model.pt"
    video_path = "path/to/your_video.mp4"
    output_dir = "path/to/output_folder"

    result = run_full_analysis(model_path, video_path, output_dir)
    print(result)
