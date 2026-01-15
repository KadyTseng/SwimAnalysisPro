# # BD/orchestrator.py (Fully Translated)

# import os
# import cv2
# import logging

# logging.basicConfig(
#     level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
# )

# from BD.pose_estimator import run_pose_estimation
# from BD.txt_base import process_keypoints_txt
# from BD.diving_analyzer_track_angles import analyze_diving_phase
# from BD.stroke_style_recognizer import analyze_stroke

# from BD.stroke_analysis import breaststroke_stroke_stage as stroke_stage_bs
# from BD.stroke_analysis import breaststroke_stroke_phase_plot as stroke_plot_bs

# from BD.stroke_analysis import (
#     backstroke_butterfly_freestyle_stroke_stage as stroke_stage_bbfs,
# )
# from BD.stroke_analysis.backstroke_butterfly_freestyle_stroke_phase_plot import (
#     plot_phase_on_col11_col17 as plot_phase_bbfs,
# )
# from BD.stroke_analysis.backstroke_butterfly_freestyle_stroke_stage import (
#     extract_columns_in_range,
# )


# from BD.split_speed_analyzer import analyze_split_times
# from BD.video_postprocessor import overlay_results_on_video
# from BD.focus_tracking_view import export_focus_only_video

# import subprocess
# import logging

# # --- 🎯 FFMPEG 執行檔的精確路徑 ---
# # 使用 r"" 來處理反斜線，確保路徑正確
# FFMPEG_EXECUTABLE_PATH = r"C:\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe"
# # ------------------------------------


# def transcode_to_h264(input_avi_path, output_mp4_path, ffmpeg_path):
#     """
#     使用 FFMPEG 執行檔將 MJPG/AVI 檔案轉碼為 H.264/MP4 格式。
#     """
#     logging.info(f"▶️ 開始轉碼：從 {os.path.basename(input_avi_path)} 轉為 MP4/H.264...")

#     try:
#         # FFMPEG 轉碼指令：第一個元素使用完整路徑
#         command = [
#             ffmpeg_path,  # <--- 這裡是關鍵修正點！
#             "-i",
#             input_avi_path,
#             "-c:v",
#             "libx264",
#             "-pix_fmt",
#             "yuv420p",
#             "-preset",
#             "veryfast",
#             "-crf",
#             "23",
#             "-y",
#             output_mp4_path,
#         ]

#         # 執行指令
#         # ... (後續的 subprocess.run 邏輯不變)
#         subprocess.run(command, check=True, capture_output=True, text=True)

#         # 轉碼成功後，可以刪除中間的 AVI 檔案以節省空間
#         if os.path.exists(output_mp4_path):
#             os.remove(input_avi_path)
#             logging.info(f"✅ 轉碼成功，並刪除中間檔案: {output_mp4_path}")
#             return output_mp4_path
#         else:
#             # 如果轉碼成功但沒有輸出檔案，可能是 FFMPEG 內部錯誤
#             raise Exception("FFMPEG 轉碼成功但未生成檔案。")

#     except subprocess.CalledProcessError as e:
#         logging.error(f"❌ FFMPEG 轉碼失敗！錯誤訊息: {e.stderr}")
#         return None
#     except FileNotFoundError:
#         # 捕捉 FFMPEG 執行檔路徑錯誤
#         logging.error(f"❌ 轉碼失敗！無法找到 FFMPEG 執行檔: {FFMPEG_EXECUTABLE_PATH}")
#         return None
#     except Exception as e:
#         logging.error(f"❌ 轉碼流程失敗: {e}")
#         return None


# def run_full_analysis(
#     pose_model_path,
#     style_model_path,
#     video_path,
#     output_dir,
#     ffmpeg_path,
#     status_callback=None,
# ):
#     logging.info("--- Starting Full Analysis Process ---")
#     logging.info(f"Input Video: {os.path.basename(video_path)}")
#     logging.info(f"Output Directory: {output_dir}")

#     if not os.path.exists(output_dir):
#         os.makedirs(output_dir)

#     # Step 1: Pose Estimation
#     logging.info("Step 1/7: Executing Pose Estimation (YOLOv11)...")
#     video_out, txt_out = run_pose_estimation(pose_model_path, video_path, output_dir)
#     logging.info(f"Raw Keypoints TXT generated at: {txt_out}")

#     # Step 2: Keypoints Interpolation and Saving
#     logging.info("Step 2/7: Interpolating and smoothing keypoint data...")

#     # --- Dynamic Filename Generation (using video_path) ---
#     base_name = os.path.splitext(os.path.basename(video_path))[0]
#     final_output_filename = f"{base_name}_1.txt"
#     final_output_path = os.path.join(output_dir, final_output_filename)
#     # ----------------------------------------------------

#     # Execute smoothing
#     df = process_keypoints_txt(
#         txt_out, save_final_output=True, final_output=final_output_path
#     )
#     logging.info(f"Final smoothed data saved at: {final_output_path}")

#     # Step 3: Underwater Dive and Kick Analysis (Get all results dict)
#     logging.info(
#         "Step 3/7: Executing dive analysis, trajectory extraction, and wall touch detection..."
#     )

#     # 1. Receive full output dictionary from analyze_diving_phase
#     diving_analysis_result = analyze_diving_phase(
#         video_path, final_output_path  # keypoints_txt_path
#     )
#     kick_angle_fig_1 = diving_analysis_result.get("kick_angle_fig_1")
#     kick_angle_fig_2 = diving_analysis_result.get("kick_angle_fig_2")

#     # 2. Extract top-level variables needed for Step 7/9
#     # --- Core Data Unpacking ---
#     segments = diving_analysis_result["segments"]

#     # Extract s1, e1, s2, e2
#     s1, e1 = segments[0] if len(segments) > 0 else (None, None)
#     s2, e2 = segments[1] if len(segments) > 1 else (None, None)
#     touch_frame = diving_analysis_result["touch_frame"]

#     # Extract data needed for Step 9 plotting
#     waterline_y = diving_analysis_result["waterline_y"]
#     touch_frame = diving_analysis_result["touch_frame"]
#     hip_data_for_overlay = diving_analysis_result["df_hip_data"]
#     track_start = s1  # Trajectory start frame
#     track_end = e1  # Trajectory end frame
#     # --- Variable Unpacking End ---
#     logging.info(
#         f"Dive segment frames: s1={s1}, e1={e1}, s2={s2}, e2={e2}. Touch frame: {touch_frame}. waterline:{waterline_y}"
#     )

#     # Step 4: Stroke Style Recognition
#     logging.info("Step 4/7: Executing stroke style recognition...")
#     stroke_label_int = analyze_stroke(video_path, final_output_path, style_model_path)

#     # Map integer label to English stroke name
#     label_dict = {0: "backstroke", 1: "breaststroke", 2: "freestyle", 3: "butterfly"}
#     stroke_style = label_dict[stroke_label_int]
#     logging.info(f"Stroke Recognition Result: {stroke_style}")

#     # Step 5: Stroke Phase Segmentation, Counting, and Waveform Generation
#     logging.info(
#         "Step 5/7: Executing stroke phase segmentation and waveform generation..."
#     )
#     stroke_plot_figs = {}
#     range1 = (e1, s2)
#     range2 = (e2, touch_frame)

#     if stroke_style == "breaststroke":

#         # Execute process_range to get all phase frames
#         (frames1, *_, propulsion_starts1, propulsion_ends1, recovery_ends1) = (
#             stroke_stage_bs.process_range(final_output_path, range1, "neg2pos")
#         )
#         (frames2, *_, propulsion_starts2, propulsion_ends2, recovery_ends2) = (
#             stroke_stage_bs.process_range(final_output_path, range2, "pos2neg")
#         )

#         phase_frames_dict = {
#             "range1": {
#                 "propulsion_starts": propulsion_starts1,
#                 "propulsion_ends": propulsion_ends1,
#                 "recovery_ends": recovery_ends1,
#             },
#             "range2": {
#                 "propulsion_starts": propulsion_starts2,
#                 "propulsion_ends": propulsion_ends2,
#                 "recovery_ends": recovery_ends2,
#             },
#         }

#         # 2. Execute counting
#         total_recovery_count_r1 = len(recovery_ends1)
#         total_recovery_count_r2 = len(recovery_ends2)

#         stroke_result = {
#             "total_count": total_recovery_count_r1 + total_recovery_count_r2,
#             "range1_recovery_count": total_recovery_count_r1,
#             "range2_recovery_count": total_recovery_count_r2,
#             "stroke_frames": recovery_ends1 + recovery_ends2,  # 用作影片標記
#         }
#         logging.info(
#             f"Breaststroke count complete. Total strokes: {stroke_result.get('total_count')}"
#         )

#         # 3. Execute plotting (Waveform)
#         data_dict = stroke_plot_bs.load_data_dict_from_txt(
#             final_output_path, range1, range2
#         )
#         # stroke_plot_bs.plot_phase_on_col11_col17(data_dict, phase_frames_dict, waterline_y) # Removed redundant call
#         stroke_plot_figs = stroke_plot_bs.plot_phase_on_col11_col17(
#             data_dict, phase_frames_dict, waterline_y
#         )
#     elif stroke_style in ["backstroke", "butterfly", "freestyle"]:

#         # Execute run_analysis function from the Stage file
#         analysis_output = stroke_stage_bbfs.run_backstroke_butterfly_analysis(
#             txt_path=final_output_path,
#             video_path=video_path,
#             waterline_y=waterline_y,
#         )

#         if analysis_output["status"] == "success":
#             analysis_end_frame = analysis_output.get("analysis_end_frame", touch_frame)

#             # 修正點：獲取分析階段數據 (這是字典，但裡面的 'range1'/'range2' 是列表)
#             full_phase_regions = analysis_output.get("full_phase_regions", {})

#             # 1. 計算 Range 1 (去程) 的 Recovery Regions 數量
#             # range1_phases 結構為 { 'Pull regions': [...], 'Recovery regions': [...] }
#             range1_phases = full_phase_regions.get("range1", {})
#             recovery_r1 = range1_phases.get("Recovery regions", [])
#             count_r1 = len(recovery_r1)

#             # 2. 計算 Range 2 (回程) 的 Recovery Regions 數量
#             range2_phases = full_phase_regions.get("range2", {})
#             recovery_r2 = range2_phases.get("Recovery regions", [])
#             count_r2 = len(recovery_r2)
#             # 3. 建立 stroke_result 字典
#             # stroke_frames_list 使用 Recovery region 的起始幀作為標記點
#             stroke_frames_list = [
#                 region[0] for region in recovery_r1 + recovery_r2 if region
#             ]

#             stroke_result = {
#                 "total_count": count_r1 + count_r2,
#                 "range1_recovery_count": count_r1,
#                 "range2_recovery_count": count_r2,
#                 "stroke_frames": stroke_frames_list,
#             }
#             # *** Plotting Steps for BFFS *** (以下繪圖邏輯不需要大幅度修改)

#             # 獲取分析區間 (用於繪圖)
#             range1 = (e1, s2)
#             range2 = (e2, analysis_end_frame)
#             data_bbfs = extract_columns_in_range(final_output_path, range1, range2)

#             # 這裡的 phase_data 是 Plotting 步驟所需的數據
#             # intersection_dict 是我們在步驟二中回傳的 phase_data 鍵
#             phase_data_plot = analysis_output["phase_data"]  # intersection_dict

#             # 4. Execute plotting
#             # 由於我們在步驟二中修改了 plot_phase_bbfs 的前置函式，這裡的調用保持不變
#             stroke_plot_figs = plot_phase_bbfs(
#                 # ❗️ 注意: 這裡的 plot_phase_bbfs 應使用 intersection_dict (即 analysis_output["phase_data"])
#                 # 作為其第二個參數，而不是 full_phase_regions
#                 data_bbfs,
#                 phase_data_plot,
#                 waterline_y,
#             )

#             logging.info(
#                 f"{stroke_style.capitalize()} count complete. Total strokes (Recovery-based): {stroke_result.get('total_count')}"
#             )
#         else:
#             logging.warning(
#                 f"Analysis failed/skipped for {stroke_style}: {analysis_output['reason']}"
#             )
#             stroke_result = {"total_count": 0}
#     logging.info("Step 5/7 Phase analysis process finished.")

#     # Step 6: Get FPS/Width and Calculate Split Times
#     logging.info("Step 6/7: Calculating split times and speed metrics...")

#     cap = cv2.VideoCapture(video_path)
#     fps = cap.get(cv2.CAP_PROP_FPS)
#     width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     cap.release()

#     # Calibration definitions (assumed values)
#     d15m_x0 = width * 0.4
#     d25m_x0 = width * 0.05
#     d50m_x0 = width - 60
#     start_frame = s1  # Usually the start of the first dive segment

#     passed, total_time = analyze_split_times(
#         final_output_path, start_frame, fps, d15m_x0, d25m_x0, d50m_x0
#     )
#     if total_time is None:
#         logging.warning("Timing analysis failed: Total time set to N/A.")
#         total_time_display = "N/A"
#         passed = {}  # Ensure passed is a safe dictionary
#     else:
#         # Ensure total_time is numeric and formatted
#         total_time_display = f"{total_time:.2f}"

#     logging.info(f"Split timing complete. Total time: {total_time_display}s")

#     # Step 7: Generate Tracking Video and Final Post-processing Overlay
#     logging.info(
#         "Step 7/7: Generating focus video and final post-processing overlay..."
#     )
#     focus_video_path = os.path.join(output_dir, "focus_only.mp4")
#     export_focus_only_video(video_path, final_output_path, focus_video_path)
#     logging.info(f"Focus video generated at: {focus_video_path}")

#     # Output processed video path
#     # processed_video_path = os.path.join(
#     #     output_dir,
#     #     "processed_" + os.path.splitext(os.path.basename(video_path))[0] + ".avi",
#     # )
#     base_name = os.path.splitext(os.path.basename(video_path))[0]
#     processed_avi_path = os.path.join(
#         output_dir,
#         "processed_" + base_name + ".avi",
#     )
#     # 2. MP4 最終輸出路徑 (用於 Streamlit 播放)
#     final_mp4_path = os.path.join(
#         output_dir,
#         "processed_" + base_name + ".mp4",
#     )

#     overlay_results_on_video(
#         video_path,
#         analysis_results={
#             "stroke_frames": stroke_result.get("stroke_frames", []),
#             "df_hip_trajectory": hip_data_for_overlay,
#             "track_segment_start": track_start,
#             "track_segment_end": track_end,
#         },
#         output_path=processed_avi_path,
#         split_times={
#             "passed": passed,
#             "start_frame": s1,
#             "fps": fps,
#             "line_positions": {"15m": d15m_x0, "25m": d25m_x0, "50m": d50m_x0},
#         },
#         focus_video_path=focus_video_path,
#     )
#     # --- 🎯 修正點 B: 執行 FFMPEG 轉碼 ---

#     # 轉碼 AVI 成 MP4 (帶 H.264 編碼，保證瀏覽器兼容)
#     # final_processed_video_path 將會是 .mp4 路徑或 None
#     final_processed_video_path = transcode_to_h264(
#         processed_avi_path, final_mp4_path, ffmpeg_path=ffmpeg_path
#     )

#     if final_processed_video_path is None:
#         # 如果轉碼失敗，我們仍然傳遞 AVI 路徑用於除錯或下載
#         final_processed_video_path = processed_avi_path
#         logging.error("FFMPEG Transcoding FAILED! Using raw AVI output for fallback.")

#     logging.info(
#         f"--- Process Complete! Processed video output at: {final_processed_video_path} ---"
#     )

#     # --- Resource Cleanup ---
#     try:
#         import gc

#         gc.collect()
#         logging.info("Forcing Garbage Collection to release file locks.")
#     except Exception as e:
#         logging.warning(f"GC failed: {e}")
#     # ------------------------

#     return {
#         "fps": fps,
#         "stroke_style": stroke_style,
#         "final_output": final_output_path,
#         "touch_frame": touch_frame,
#         "diving_segments": {"s1": s1, "e1": e1, "s2": s2, "e2": e2},
#         "waterline_y": waterline_y,
#         "stroke_result": stroke_result,
#         "passed": passed,
#         "total_time": total_time,
#         "focus_video_path": focus_video_path,
#         "processed_video_path": final_processed_video_path,
#         "stroke_plot_figs": stroke_plot_figs,
#         "kick_angle_fig_1": kick_angle_fig_1,
#         "kick_angle_fig_2": kick_angle_fig_2,
#     }


# if __name__ == "__main__":

#     # --- TEST PATHS (Replace with your actual D drive paths) ---
#     POSE_MODEL_PATH = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\best_1.pt"
#     STYLE_MODEL_PATH = (
#         r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\svm_model_new_3.pkl"
#     )
#     VIDEO_PATH = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\videos\Excellent_20230414_backstroke_M_3 (6).mp4"
#     OUTPUT_DIR = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\processed_videos"
#     # ------------------------------------------------------------

#     # Ensure output_dir exists
#     if not os.path.exists(OUTPUT_DIR):
#         os.makedirs(OUTPUT_DIR)

#     # Execute analysis
#     result = run_full_analysis(
#         POSE_MODEL_PATH, STYLE_MODEL_PATH, VIDEO_PATH, OUTPUT_DIR
#     )

#     if result:
#         # --- Console Output Summary ---
#         fps_val = result["fps"]
#         start_frame_val = result["diving_segments"]["s1"]

#         stroke_count_r1 = result["stroke_result"].get("range1_recovery_count", 0)
#         stroke_count_r2 = result["stroke_result"].get("range2_recovery_count", 0)
#         total_strokes = result["stroke_result"].get("total_count", 0)

#         print("\n--- ANALYSIS SUMMARY ---")
#         print(f"Recognized Stroke Style: {result['stroke_style']}")

#         print("\n--- SPLIT TIMING RESULTS ---")
#         passed_frames = result["passed"]
#         if passed_frames:
#             for k, frame in passed_frames.items():
#                 if frame is not None:
#                     time_sec = (frame - start_frame_val) / fps_val
#                     print(f"  {k} Time: {time_sec:.2f} seconds")
#         else:
#             print("  No valid split timing data.")

#         print("\n--- STROKE COUNT RESULTS ---")
#         print(f"  Outbound (R1) Strokes: {stroke_count_r1} cycles")
#         print(f"  Inbound (R2) Strokes: {stroke_count_r2} cycles")
#         print(f"  Total Strokes: {total_strokes} cycles")

#         print(f"Total Analysis Time: {result['total_time']}s")
#         print(f"Processed Video: {result['processed_video_path']}")

# BD/orchestrator.py (Fully Translated)

import os
import cv2
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

from BD.pose_estimator import run_pose_estimation
from BD.txt_base import process_keypoints_txt
from BD.diving_analyzer_track_angles import analyze_diving_phase
from BD.stroke_style_recognizer import analyze_stroke

from BD.stroke_analysis import breaststroke_stroke_stage as stroke_stage_bs
from BD.stroke_analysis import breaststroke_stroke_phase_plot as stroke_plot_bs

from BD.stroke_analysis import (
    backstroke_butterfly_freestyle_stroke_stage as stroke_stage_bbfs,
)
from BD.stroke_analysis.backstroke_butterfly_freestyle_stroke_stage import (
    extract_columns_in_range,
)


from BD.split_speed_analyzer import analyze_split_times
from BD.video_postprocessor import overlay_results_on_video
from BD.focus_tracking_view import export_focus_only_video

import subprocess
import logging

# --- 🎯 FFMPEG 執行檔的精確路徑 ---
# 使用 r"" 來處理反斜線，確保路徑正確
FFMPEG_EXECUTABLE_PATH = r"C:\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe"
# ------------------------------------


def transcode_to_h264(input_avi_path, output_mp4_path, ffmpeg_path):
    """
    使用 FFMPEG 執行檔將 MJPG/AVI 檔案轉碼為 H.264/MP4 格式。
    """
    logging.info(f"▶️ 開始轉碼：從 {os.path.basename(input_avi_path)} 轉為 MP4/H.264...")

    try:
        # FFMPEG 轉碼指令：第一個元素使用完整路徑
        command = [
            ffmpeg_path,  # <--- 這裡是關鍵修正點！
            "-i",
            input_avi_path,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-y",
            output_mp4_path,
        ]

        # 執行指令
        # ... (後續的 subprocess.run 邏輯不變)
        subprocess.run(command, check=True, capture_output=True, text=True)

        # 轉碼成功後，可以刪除中間的 AVI 檔案以節省空間
        if os.path.exists(output_mp4_path):
            os.remove(input_avi_path)
            logging.info(f"✅ 轉碼成功，並刪除中間檔案: {output_mp4_path}")
            return output_mp4_path
        else:
            # 如果轉碼成功但沒有輸出檔案，可能是 FFMPEG 內部錯誤
            raise Exception("FFMPEG 轉碼成功但未生成檔案。")

    except subprocess.CalledProcessError as e:
        logging.error(f"❌ FFMPEG 轉碼失敗！錯誤訊息: {e.stderr}")
        return None
    except FileNotFoundError:
        # 捕捉 FFMPEG 執行檔路徑錯誤
        logging.error(f"❌ 轉碼失敗！無法找到 FFMPEG 執行檔: {FFMPEG_EXECUTABLE_PATH}")
        return None
    except Exception as e:
        logging.error(f"❌ 轉碼流程失敗: {e}")
        return None


def run_full_analysis(
    pose_model_path,
    style_model_path,
    video_path,
    output_dir,
    ffmpeg_path,
    status_callback=None,
):
    logging.info("--- Starting Full Analysis Process ---")
    logging.info(f"Input Video: {os.path.basename(video_path)}")
    logging.info(f"Output Directory: {output_dir}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Step 1: Pose Estimation
    logging.info("Step 1/7: Executing Pose Estimation (YOLOv11)...")
    video_out, txt_out = run_pose_estimation(pose_model_path, video_path, output_dir)
    logging.info(f"Raw Keypoints TXT generated at: {txt_out}")

    # Step 2: Keypoints Interpolation and Saving
    logging.info("Step 2/7: Interpolating and smoothing keypoint data...")

    # --- Dynamic Filename Generation (using video_path) ---
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    final_output_filename = f"{base_name}_1.txt"
    final_output_path = os.path.join(output_dir, final_output_filename)
    # ----------------------------------------------------

    # Execute smoothing
    df = process_keypoints_txt(
        txt_out, save_final_output=True, final_output=final_output_path
    )
    logging.info(f"Final smoothed data saved at: {final_output_path}")

    # Step 3: Underwater Dive and Kick Analysis (Get all results dict)
    logging.info(
        "Step 3/7: Executing dive analysis, trajectory extraction, and wall touch detection..."
    )

    # 1. Receive full output dictionary from analyze_diving_phase
    # waterline_y = 190
    diving_analysis_result = analyze_diving_phase(
        video_path, final_output_path  # keypoints_txt_path
    )
    kick_angle_fig_1 = diving_analysis_result.get("kick_angle_fig_1")
    kick_angle_fig_2 = diving_analysis_result.get("kick_angle_fig_2")

    # 2. Extract top-level variables needed for Step 7/9
    # --- Core Data Unpacking ---

    segments = diving_analysis_result.get("segments", [])

    # Extract s1, e1, s2, e2
    s1, e1 = segments[0] if len(segments) > 0 else (None, None)
    s2, e2 = segments[1] if len(segments) > 1 else (None, None)

    # Extract data needed for Step 9 plotting
    waterline_y = diving_analysis_result["waterline_y"]
    # waterline_y = 190
    touch_frame = diving_analysis_result["touch_frame"]
    hip_data_for_overlay = diving_analysis_result["df_hip_data"]
    track_start = s1  # Trajectory start frame
    track_end = e1  # Trajectory end frame
    # --- Variable Unpacking End ---
    logging.info(
        f"Dive segment frames: s1={s1}, e1={e1}, s2={s2}, e2={e2}. Touch frame: {touch_frame}. waterline:{waterline_y}"
    )

    # Step 4: Stroke Style Recognition
    logging.info("Step 4/7: Executing stroke style recognition...")
    stroke_label_int = analyze_stroke(video_path, final_output_path, style_model_path)

    # Map integer label to English stroke name
    label_dict = {0: "backstroke", 1: "breaststroke", 2: "freestyle", 3: "butterfly"}
    stroke_style = label_dict[stroke_label_int]
    logging.info(f"Stroke Recognition Result: {stroke_style}")

    # Step 5: Stroke Phase Segmentation, Counting, and Waveform Generation
    logging.info(
        "Step 5/7: Executing stroke phase segmentation and waveform generation..."
    )
    stroke_plot_figs = {}
    range1 = (e1, s2)
    range2 = (e2, touch_frame)

    if stroke_style == "breaststroke":

        # Execute process_range to get all phase frames
        (frames1, *_, propulsion_starts1, propulsion_ends1, recovery_ends1) = (
            stroke_stage_bs.process_range(final_output_path, range1, "neg2pos")
        )
        (frames2, *_, propulsion_starts2, propulsion_ends2, recovery_ends2) = (
            stroke_stage_bs.process_range(final_output_path, range2, "pos2neg")
        )

        phase_frames_dict = {
            "range1": {
                "propulsion_starts": propulsion_starts1,
                "propulsion_ends": propulsion_ends1,
                "recovery_ends": recovery_ends1,
            },
            "range2": {
                "propulsion_starts": propulsion_starts2,
                "propulsion_ends": propulsion_ends2,
                "recovery_ends": recovery_ends2,
            },
        }

        # 2. Execute counting
        total_recovery_count_r1 = len(recovery_ends1)
        total_recovery_count_r2 = len(recovery_ends2)

        stroke_result = {
            "total_count": total_recovery_count_r1 + total_recovery_count_r2,
            "range1_recovery_count": total_recovery_count_r1,
            "range2_recovery_count": total_recovery_count_r2,
            "stroke_frames": recovery_ends1 + recovery_ends2,  # 用作影片標記
        }
        logging.info(
            f"Breaststroke count complete. Total strokes: {stroke_result.get('total_count')}"
        )

        # 3. Execute plotting (Waveform)
        data_dict = stroke_plot_bs.load_data_dict_from_txt(
            final_output_path, range1, range2
        )
        # stroke_plot_bs.plot_phase_on_col11_col17(data_dict, phase_frames_dict, waterline_y) # Removed redundant call
        stroke_plot_figs = stroke_plot_bs.plot_phase_on_col11_col17(
            data_dict, phase_frames_dict, waterline_y
        )
    elif stroke_style in ["backstroke", "butterfly", "freestyle"]:

        # Execute run_analysis function from the Stage file
        analysis_output = stroke_stage_bbfs.run_backstroke_butterfly_analysis(
            txt_path=final_output_path,
            video_path=video_path,
            waterline_y=waterline_y,
        )

        if analysis_output["status"] == "success":
            stroke_plot_figs = analysis_output.get("full_phase_regions", {})
            analysis_end_frame = analysis_output.get("analysis_end_frame", touch_frame)

            # 修正點：獲取分析階段數據 (這是字典，但裡面的 'range1'/'range2' 是列表)
            full_phase_regions = analysis_output.get("full_phase_regions", {})

            # 1. 計算 Range 1 (去程) 的 Recovery Regions 數量
            # range1_phases 結構為 { 'Pull regions': [...], 'Recovery regions': [...] }
            range1_phases = full_phase_regions.get("range1", {})
            recovery_r1 = range1_phases.get("Recovery regions", [])
            count_r1 = len(recovery_r1)

            # 2. 計算 Range 2 (回程) 的 Recovery Regions 數量
            range2_phases = full_phase_regions.get("range2", {})
            recovery_r2 = range2_phases.get("Recovery regions", [])
            count_r2 = len(recovery_r2)
            # 3. 建立 stroke_result 字典
            # stroke_frames_list 使用 Recovery region 的起始幀作為標記點
            stroke_frames_list = [
                region[0] for region in recovery_r1 + recovery_r2 if region
            ]

            stroke_result = {
                "total_count": count_r1 + count_r2,
                "range1_recovery_count": count_r1,
                "range2_recovery_count": count_r2,
                "stroke_frames": stroke_frames_list,
            }
            # *** Plotting Steps for BFFS *** (以下繪圖邏輯不需要大幅度修改)

            # 獲取分析區間 (用於繪圖)
            range1 = (e1, s2)
            range2 = (e2, analysis_end_frame)
            data_bbfs = extract_columns_in_range(final_output_path, range1, range2)

            # 這裡的 phase_data 是 Plotting 步驟所需的數據
            # intersection_dict 是我們在步驟二中回傳的 phase_data 鍵
            phase_data_plot = analysis_output["phase_data"]  # intersection_dict

            # 4. Execute plotting
            # 由於我們在步驟二中修改了 plot_phase_bbfs 的前置函式，這裡的調用保持不變
            # stroke_plot_figs = plot_phase_bbfs(
            #     # ❗️ 注意: 這裡的 plot_phase_bbfs 應使用 intersection_dict (即 analysis_output["phase_data"])
            #     # 作為其第二個參數，而不是 full_phase_regions
            #     data_bbfs,
            #     phase_data_plot,
            #     waterline_y,
            # )

            logging.info(
                f"{stroke_style.capitalize()} count complete. Total strokes (Recovery-based): {stroke_result.get('total_count')}"
            )
        else:
            logging.warning(
                f"Analysis failed/skipped for {stroke_style}: {analysis_output['reason']}"
            )
            stroke_result = {"total_count": 0}
    logging.info("Step 5/7 Phase analysis process finished.")

    # Step 6: Get FPS/Width and Calculate Split Times
    logging.info("Step 6/7: Calculating split times and speed metrics...")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()

    # Calibration definitions (assumed values)
    d15m_x0 = width * 0.4
    d25m_x0 = width * 0.05
    d50m_x0 = width - 60
    start_frame = s1  # Usually the start of the first dive segment

    passed, total_time = analyze_split_times(
        final_output_path, start_frame, fps, d15m_x0, d25m_x0, d50m_x0
    )
    if total_time is None:
        logging.warning("Timing analysis failed: Total time set to N/A.")
        total_time_display = "N/A"
        passed = {}  # Ensure passed is a safe dictionary
    else:
        # Ensure total_time is numeric and formatted
        total_time_display = f"{total_time:.2f}"

    logging.info(f"Split timing complete. Total time: {total_time_display}s")

    # Step 7: Generate Tracking Video and Final Post-processing Overlay
    logging.info(
        "Step 7/7: Generating focus video and final post-processing overlay..."
    )
    focus_video_path = os.path.join(output_dir, "focus_only.mp4")
    export_focus_only_video(video_path, final_output_path, focus_video_path)
    logging.info(f"Focus video generated at: {focus_video_path}")

    # Output processed video path
    # processed_video_path = os.path.join(
    #     output_dir,
    #     "processed_" + os.path.splitext(os.path.basename(video_path))[0] + ".avi",
    # )
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    processed_avi_path = os.path.join(
        output_dir,
        "processed_" + base_name + ".avi",
    )
    # 2. MP4 最終輸出路徑 (用於 Streamlit 播放)
    final_mp4_path = os.path.join(
        output_dir,
        "processed_" + base_name + ".mp4",
    )

    overlay_results_on_video(
        video_path,
        analysis_results={
            "stroke_frames": stroke_result.get("stroke_frames", []),
            "df_hip_trajectory": hip_data_for_overlay,
            "track_segment_start": track_start,
            "track_segment_end": track_end,
        },
        output_path=processed_avi_path,
        split_times={
            "passed": passed,
            "start_frame": s1,
            "fps": fps,
            "line_positions": {"15m": d15m_x0, "25m": d25m_x0, "50m": d50m_x0},
        },
        focus_video_path=focus_video_path,
    )
    # --- 🎯 修正點 B: 執行 FFMPEG 轉碼 ---

    # 轉碼 AVI 成 MP4 (帶 H.264 編碼，保證瀏覽器兼容)
    # final_processed_video_path 將會是 .mp4 路徑或 None
    final_processed_video_path = transcode_to_h264(
        processed_avi_path, final_mp4_path, ffmpeg_path=ffmpeg_path
    )

    if final_processed_video_path is None:
        # 如果轉碼失敗，我們仍然傳遞 AVI 路徑用於除錯或下載
        final_processed_video_path = processed_avi_path
        logging.error("FFMPEG Transcoding FAILED! Using raw AVI output for fallback.")

    logging.info(
        f"--- Process Complete! Processed video output at: {final_processed_video_path} ---"
    )

    # --- Resource Cleanup ---
    try:
        import gc

        gc.collect()
        logging.info("Forcing Garbage Collection to release file locks.")
    except Exception as e:
        logging.warning(f"GC failed: {e}")
    # ------------------------

    return {
        "fps": fps,
        "stroke_style": stroke_style,
        "final_output": final_output_path,
        "touch_frame": touch_frame,
        "diving_segments": {"s1": s1, "e1": e1, "s2": s2, "e2": e2},
        "waterline_y": waterline_y,
        "stroke_result": stroke_result,
        "passed": passed,
        "total_time": total_time,
        "focus_video_path": focus_video_path,
        "processed_video_path": final_processed_video_path,
        "stroke_plot_figs": stroke_plot_figs,
        "kick_angle_fig_1": kick_angle_fig_1,
        "kick_angle_fig_2": kick_angle_fig_2,
    }


if __name__ == "__main__":

    # --- TEST PATHS (Replace with your actual D drive paths) ---
    POSE_MODEL_PATH = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\best_1.pt"
    STYLE_MODEL_PATH = (
        r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\svm_model_new_3.pkl"
    )
    VIDEO_PATH = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\videos\Excellent_20230414_backstroke_M_3 (6).mp4"
    OUTPUT_DIR = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\processed_videos"
    # ------------------------------------------------------------

    # Ensure output_dir exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Execute analysis
    result = run_full_analysis(
        POSE_MODEL_PATH, STYLE_MODEL_PATH, VIDEO_PATH, OUTPUT_DIR
    )

    if result:
        # --- Console Output Summary ---
        fps_val = result["fps"]
        start_frame_val = result["diving_segments"]["s1"]

        stroke_count_r1 = result["stroke_result"].get("range1_recovery_count", 0)
        stroke_count_r2 = result["stroke_result"].get("range2_recovery_count", 0)
        total_strokes = result["stroke_result"].get("total_count", 0)

        print("\n--- ANALYSIS SUMMARY ---")
        print(f"Recognized Stroke Style: {result['stroke_style']}")

        print("\n--- SPLIT TIMING RESULTS ---")
        passed_frames = result["passed"]
        if passed_frames:
            for k, frame in passed_frames.items():
                if frame is not None:
                    time_sec = (frame - start_frame_val) / fps_val
                    print(f"  {k} Time: {time_sec:.2f} seconds")
        else:
            print("  No valid split timing data.")

        print("\n--- STROKE COUNT RESULTS ---")
        print(f"  Outbound (R1) Strokes: {stroke_count_r1} cycles")
        print(f"  Inbound (R2) Strokes: {stroke_count_r2} cycles")
        print(f"  Total Strokes: {total_strokes} cycles")

        print(f"Total Analysis Time: {result['total_time']}s")
        print(f"Processed Video: {result['processed_video_path']}")
