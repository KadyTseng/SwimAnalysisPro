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
    print(f"\n[ORCHESTRATOR] 🚀 STARTING ANALYSIS: {os.path.basename(video_path)}", flush=True)
    logging.info("--- Starting Full Analysis Process ---")
    logging.info(f"Input Video: {os.path.basename(video_path)}")
    logging.info(f"Output Directory: {output_dir}")

    # Step 1: Directory Setup
    # output_dir passed in is typically ".../data/processed_videos"
    # We need to resolve sibling directories based on the parent "data" folder logic or just assume structure.
    # Safe bet: output_dir is ".../data/processed_videos".
    base_data_dir = os.path.dirname(output_dir) # .../data
    
    keypoints_dir = os.path.join(base_data_dir, "keypoints")
    phase_frames_dir = os.path.join(base_data_dir, "Stroke_Phase_Frames")
    processed_dir = output_dir # Keep as is

    for d in [keypoints_dir, phase_frames_dir, processed_dir]:
        if not os.path.exists(d):
            os.makedirs(d)

    base_name = os.path.splitext(os.path.basename(video_path))[0]

    # Step 1: Pose Estimation
    print("[ORCHESTRATOR] 🔹 Step 1/7: Running Pose Estimation (YOLO)...", flush=True)
    if status_callback: status_callback(10, "Step 1: Pose Estimation (YOLO)")
    logging.info("Step 1/7: Executing Pose Estimation (YOLOv11)...")
    
    # run_pose_estimation saves to output_dir with filename {base_name}_raw.txt
    # We direct it to keypoints_dir.
    # User requested NO intermediate video for pose estimation step.
    video_out_pose, txt_out = run_pose_estimation(
        pose_model_path, video_path, keypoints_dir, save_video=False
    )
    logging.info(f"Raw Keypoints TXT generated at: {txt_out}")

    # Step 2: Keypoints Interpolation and Saving
    print("[ORCHESTRATOR] 🔹 Step 2/7: Smoothing Keypoints...", flush=True)
    if status_callback: status_callback(30, "Step 2: Smoothing Keypoints")
    logging.info("Step 2/7: Interpolating and smoothing keypoint data...")

    # --- Path Definition ---
    # 1. Smoothed Keypoints (Coordinate Data) -> data/keypoints/{base_name}.txt
    smoothed_txt_filename = f"{base_name}.txt"
    smoothed_txt_path = os.path.join(keypoints_dir, smoothed_txt_filename)
    
    # 2. Phase Analysis Data (Stroke Stages) -> data/Stroke_Phase_Frames/{base_name}_a.txt
    phase_output_filename = f"{base_name}_a.txt"
    phase_output_path = os.path.join(phase_frames_dir, phase_output_filename)
    # -----------------------

    # Execute smoothing -> Save to smoothed_txt_path (keypoints dir)
    df = process_keypoints_txt(
        txt_out, save_final_output=True, final_output=smoothed_txt_path
    )
    logging.info(f"Final smoothed data saved at: {smoothed_txt_path}")

    # Cleanup Raw Output if needed (User requseted "不需要存" for the raw output)
    if txt_out and os.path.exists(txt_out):
        try:
            os.remove(txt_out)
            logging.info(f"Removed temp raw file: {txt_out}")
        except OSError as e:
            logging.warning(f"Could not remove raw file {txt_out}: {e}")

    # Update variable for downstream steps:
    # Most subsequent steps (Diving, Stroke Recog, Split Times) need the smoothed COORDINATES.
    # So we use `smoothed_txt_path`.
    final_output_path = smoothed_txt_path 

    # Step 3: Underwater Dive and Kick Analysis (Get all results dict)
    print("[ORCHESTRATOR] 🔹 Step 3/7: Analyzing Diving Phase & Turns...", flush=True)

    if status_callback: status_callback(45, "Step 3: Diving & Kick Analysis")
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
    print("[ORCHESTRATOR] 🔹 Step 4/7: Recognizing Stroke Style...", flush=True)
    if status_callback: status_callback(60, "Step 4: Stroke Style Recognition")
    logging.info("Step 4/7: Executing stroke style recognition...")
    try:
        stroke_label_int = analyze_stroke(video_path, final_output_path, style_model_path)
    except Exception as e:
        print(f"[ORCHESTRATOR] ⚠️ Stroke Recognition Failed: {e}", flush=True)
        # Default to Freestyle to prevent pipeline halt if strictly needed, or just let error bubble up?
        # Given previous fixes, it handles '0 size' by returning default.
        # Here we just log.
        raise e

    # Map integer label to English stroke name
    label_dict = {0: "backstroke", 1: "breaststroke", 2: "freestyle", 3: "butterfly"}
    stroke_style = label_dict.get(stroke_label_int, "freestyle")
    logging.info(f"Stroke Recognition Result: {stroke_style}")
    print(f"[ORCHESTRATOR] 💡 Identified Style: {stroke_style.upper()}", flush=True)

    # Step 5: Stroke Phase Segmentation, Counting, and Waveform Generation
    print("[ORCHESTRATOR] 🔹 Step 5/7: Phase Analysis & Waveform Generation...", flush=True)
    if status_callback: status_callback(75, "Step 5: Stroke Analysis & Graphs")
    logging.info(
        "Step 5/7: Executing stroke phase segmentation and waveform generation..."
    )
    stroke_plot_figs = {}
    range1 = (e1, s2)
    range2 = (e2, touch_frame)

    if stroke_style == "breaststroke":
        laps_data = diving_analysis_result.get("laps_data")
        
        phase_frames_dict = {}
        data_dict = {}
        
        # Pre-read file for data dictionary construction (efficiency)
        raw_lines = []
        try:
            with open(final_output_path, 'r') as f:
                raw_lines = f.readlines()
        except FileNotFoundError:
            logging.error(f"Cannot read {final_output_path}")

        def parse_bs_line(line):
             parts = line.strip().split()
             if len(parts) > 20:
                 try:
                     frame = int(parts[0])
                     # Format: (frame, col10, col11, col13, col14, col16, col17, hip_x)
                     return (frame, float(parts[10]), float(parts[11]), float(parts[13]), 
                             float(parts[14]), float(parts[16]), float(parts[17]), float(parts[19]))
                 except: return None
             return None

        parsed_data_map = {}
        for line in raw_lines:
             d = parse_bs_line(line)
             if d: parsed_data_map[d[0]] = d

        if laps_data:
            # Flexible Analysis using laps_data
            for lap in laps_data:
                idx = lap.get('lap_index', 0)
                trend = lap.get('trend', 'unknown')
                swim_seg = lap.get('swimming_segment')
                
                if not swim_seg or swim_seg[0] is None:
                    continue
                
                # Check segment duration (skip if too short, e.g. < 10 frames)
                if swim_seg[1] - swim_seg[0] < 10:
                    continue

                key = f"lap{idx}_{trend}"
                
                # Determine slope change: Outbound (decreasing) -> neg2pos, Inbound -> pos2neg
                slope_change = "neg2pos" if "decreasing" in trend else "pos2neg"
                # Fallback if trend unknown: use index (Odd=Out=neg2pos)
                if trend == "unknown":
                    slope_change = "neg2pos" if idx % 2 != 0 else "pos2neg"

                # Run Process Range from Stage file
                (frames, _, _, _, _, _, _, p_starts, p_ends, r_ends) = \
                    stroke_stage_bs.process_range(final_output_path, swim_seg, slope_change)
                
                phase_frames_dict[key] = {
                    "propulsion_starts": p_starts,
                    "propulsion_ends": p_ends,
                    "recovery_ends": r_ends
                }
                
                # Build data list for plotting
                seg_list = []
                for f_id in range(swim_seg[0], swim_seg[1] + 1):
                    if f_id in parsed_data_map:
                        seg_list.append(parsed_data_map[f_id])
                data_dict[key] = seg_list
                
        else:
            # Fallback: Original Logic
            range1 = (e1, s2)
            range2 = (e2, touch_frame)
            
            # Analyze Range 1 (Outbound -> neg2pos)
            if range1[0] is not None and range1[1] is not None and range1[1] > range1[0]:
                (frames1, *_, p_starts1, p_ends1, r_ends1) = \
                    stroke_stage_bs.process_range(final_output_path, range1, "neg2pos")
                phase_frames_dict["range1"] = {
                    "propulsion_starts": p_starts1, "propulsion_ends": p_ends1, "recovery_ends": r_ends1
                }
                # Data
                seg_list1 = []
                for f_id in range(range1[0], range1[1] + 1):
                    if f_id in parsed_data_map: seg_list1.append(parsed_data_map[f_id])
                data_dict["range1"] = seg_list1

            # Analyze Range 2 (Inbound -> pos2neg)
            if range2[0] is not None and range2[1] is not None and range2[1] > range2[0]:
                (frames2, *_, p_starts2, p_ends2, r_ends2) = \
                    stroke_stage_bs.process_range(final_output_path, range2, "pos2neg")
                phase_frames_dict["range2"] = {
                    "propulsion_starts": p_starts2, "propulsion_ends": p_ends2, "recovery_ends": r_ends2
                }
                # Data
                seg_list2 = []
                for f_id in range(range2[0], range2[1] + 1):
                    if f_id in parsed_data_map: seg_list2.append(parsed_data_map[f_id])
                data_dict["range2"] = seg_list2

        # 2. Call Plotting Function (Generate Regions and Metrics)
        # Note: data_dict keys match phase_frames_dict keys
        phase_results = stroke_plot_bs.plot_phase_on_col11_col17(
            data_dict, phase_frames_dict, waterline_y, output_txt=phase_output_path
        )
        
        # 3. Aggregate Counts and Build Frontend Result (stroke_plot_figs)
        import re
        lap_counts = {}
        total_cnt = 0
        all_stroke_frames = []
        stroke_plot_figs = {}

        for key, res in phase_results.items():
            # Recovery Count
            rec_regs = res.get("recovery", [])
            cnt = len(rec_regs)
            total_cnt += cnt
            
            # key classification
            lap_idx = -1
            match = re.search(r"lap(\d+)", key)
            if match:
                lap_idx = int(match.group(1))
            elif "range1" in key: lap_idx = 1
            elif "range2" in key: lap_idx = 2
            
            if lap_idx > 0:
                lap_counts[lap_idx] = lap_counts.get(lap_idx, 0) + cnt
            else:
                # Default assume outbound (1) or inbound (2) based on trend if no lap index?
                if "decreasing" in key: lap_counts[1] = lap_counts.get(1, 0) + cnt
                elif "increasing" in key: lap_counts[2] = lap_counts.get(2, 0) + cnt

            # Collect frame markers
            for r in rec_regs:
                all_stroke_frames.append(r[1]) # End of recovery
            
            # Build Plot Data for Frontend
            logging.info(f"DEBUG: Breaststroke Key={key}, Res Keys={list(res.keys())}")
            # Build Plot Data for Frontend - Split Shoulder/Wrist to match other styles
            if "values_shoulder" in res and "values_wrist" in res:
                 res_shoulder = res.copy()
                 res_shoulder["values"] = res["values_shoulder"]
                 stroke_plot_figs[f"{key}_shoulder"] = res_shoulder
                 
                 res_wrist = res.copy()
                 res_wrist["values"] = res["values_wrist"]
                 stroke_plot_figs[f"{key}_wrist"] = res_wrist
            else:
                 stroke_plot_figs[key] = res

        stroke_frames_list = sorted(all_stroke_frames)
        stroke_result = {
            "total_count": total_cnt,
            "stroke_frames": stroke_frames_list,
        }
        for idx, c in lap_counts.items():
            stroke_result[f"range{idx}_recovery_count"] = c
        
        # Legacy Fallback
        if "range1_recovery_count" not in stroke_result: stroke_result["range1_recovery_count"] = lap_counts.get(1, 0)
        if "range2_recovery_count" not in stroke_result: stroke_result["range2_recovery_count"] = lap_counts.get(2, 0)

        logging.info(
            f"Breaststroke count complete. Total: {stroke_result['total_count']}"
        )    
    elif stroke_style in ["backstroke", "butterfly", "freestyle"]:

        # Execute run_analysis function from the Stage file
        # Pass laps_data for flexible segment analysis
        laps_data = diving_analysis_result.get("laps_data")
        analysis_output = stroke_stage_bbfs.run_backstroke_butterfly_analysis(
            txt_path=final_output_path,
            video_path=video_path,
            waterline_y=waterline_y,
            laps_data=laps_data,
            output_txt_path=phase_output_path # <--- Pass the Phase Frames output path
        )

        if analysis_output["status"] == "success":
            # stroke_plot_figs = analysis_output.get("full_phase_regions", {}) # Not used directly?
            analysis_end_frame = analysis_output.get("analysis_end_frame", touch_frame)

            # 修正點：獲取分析階段數據 (這是字典，但裡面的 keys 現在是 lap{i}_{trend})
            full_phase_regions = analysis_output.get("full_phase_regions", {})
            phase_data_plot = analysis_output.get("phase_data", {}) # intersection_dict
            
            # 1. 統計 Strokes per Lap
            import re
            lap_counts = {}
            total_cnt = 0
            all_recovery_regions = []
            
            for key, regions_dict in full_phase_regions.items():
                rec_regs = regions_dict.get("Recovery regions", [])
                cnt = len(rec_regs)
                total_cnt += cnt
                all_recovery_regions.extend(rec_regs)
                
                # key format: "lap{i}_{trend}" (e.g. lap1_decreasing)
                lap_idx = -1
                match = re.search(r"lap(\d+)", key)
                if match:
                    lap_idx = int(match.group(1))
                elif "range1" in key: lap_idx = 1
                elif "range2" in key: lap_idx = 2
                
                if lap_idx > 0:
                    lap_counts[lap_idx] = lap_counts.get(lap_idx, 0) + cnt

            # 3. 建立 stroke_result 字典
            stroke_frames_list = [r[0] for r in all_recovery_regions if r]
            stroke_frames_list.sort() # Ensure sorted order

            stroke_result = {
                "total_count": total_cnt,
                "stroke_frames": stroke_frames_list,
            }
            # Inject per-lap counts (rangeX_recovery_count)
            # Ensure at least range1/range2 exist for legacy safety if data is missing? 
            # Or just rely on dynamic.
            for idx, c in lap_counts.items():
                stroke_result[f"range{idx}_recovery_count"] = c
            
            # Legacy Fallback: If range1/range2 missing but we have lap1/lap2
            if "range1_recovery_count" not in stroke_result: stroke_result["range1_recovery_count"] = lap_counts.get(1, 0)
            if "range2_recovery_count" not in stroke_result: stroke_result["range2_recovery_count"] = lap_counts.get(2, 0)
            
            # *** Plotting Steps for BFFS ***
            # Need to extract columns for ALL processed segments.
            # `extract_columns_in_range` uses old logic. We should rely on `run_backstroke...` 
            # effectively having done this, but we need the raw data for plotting waveforms in orchestrator.
            # However! `run_backstroke_butterfly_analysis` calculated intersections but didn't return the raw column data 
            # in a way we can easily use here without re-extraction.
            # But wait, `run_backstroke_...` calls `extract_columns_for_segment` internally.
            # We should probably duplicate that extraction here or modify `run_...` to return data.
            # Given we can't easily change `run_...` return signature safely without breaking other things maybe?
            # Actually, we can just loop through `laps_data` again here to get the data for plotting.
            
            stroke_plot_figs = {}
            if laps_data:
                from BD.stroke_analysis.backstroke_butterfly_freestyle_stroke_stage import extract_columns_for_segment
                
                for lap in laps_data:
                    trend = lap.get('trend', 'unknown')
                    idx = lap.get('lap_index', 0)
                    swim_seg = lap.get('swimming_segment')
                    if swim_seg and swim_seg[0] is not None:
                         s, e = swim_seg
                         key = f"lap{idx}_{trend}"
                         
                         # Check if this key exists in results (it should)
                         if key in full_phase_regions:
                             seg_data = extract_columns_for_segment(final_output_path, s, e)
                             # regions is actually the full dict returned by plot_phase_on_col11_col17
                             full_res_dict = full_phase_regions[key]
                             
                             # Extract keys needed
                             seg_metrics = full_res_dict.get("segment_metrics", [])
                             
                             if seg_data:
                                 frames = [d[0] for d in seg_data]
                                 shoulder_y = [d[2] for d in seg_data]
                                 wrist_y = [d[4] for d in seg_data]
                                 
                                 stroke_plot_figs[f"{key}_shoulder"] = {
                                     "values": shoulder_y, 
                                     "frames": frames,
                                     "regions": full_res_dict, # Pass full dict safely
                                     "segment_metrics": seg_metrics # <--- PASS METRICS HERE TOO
                                 }
                                 stroke_plot_figs[f"{key}_wrist"] = {
                                     "values": wrist_y, 
                                     "frames": frames,
                                     "regions": full_res_dict,
                                     "segment_metrics": seg_metrics # <--- PASS METRICS HERE
                                 }
            else:
                 # Fallback old logic if laps_data missing
                 range1 = (e1, s2)
                 range2 = (e2, analysis_end_frame)
                 data_bbfs = extract_columns_in_range(final_output_path, range1, range2)
                 for r_key in ["range1", "range2"]:
                    dataset = data_bbfs.get(r_key, [])
                    regions = full_phase_regions.get(r_key, {})
                    seg_metrics = regions.get("segment_metrics", [])
                    
                    if dataset:
                        frames = [d[0] for d in dataset]
                        shoulder_y = [d[2] for d in dataset]
                        wrist_y = [d[4] for d in dataset]
                        
                        stroke_plot_figs[f"{r_key}_shoulder"] = {
                            "values": shoulder_y, 
                            "frames": frames,
                            "regions": regions,
                            "segment_metrics": seg_metrics # <--- PASS METRICS HERE TOO
                        }
                        stroke_plot_figs[f"{r_key}_wrist"] = {
                            "values": wrist_y, 
                            "frames": frames,
                            "regions": regions,
                            "segment_metrics": seg_metrics
                        }

            logging.info(f"Waveform data extraction complete for {stroke_style}")

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

    passed, total_time, split_breakdown, lap_durations = analyze_split_times(
        final_output_path, start_frame, fps, d15m_x0, d25m_x0, d50m_x0, laps_data=laps_data
    )
    
    avg_speed = 0.0
    spm = 0.0
    spm_breakdown_str = None
    
    # --- 修正點: Speed/Time Calculation Logic ---
    # User Request: Use (Last Lap End - First Lap Start) for total time
    valid_laps_for_timing = []
    if laps_data:
        for lap in laps_data:
            # 確保有 swimming_segment
            if lap.get('swimming_segment') and lap['swimming_segment'][0] is not None:
                valid_laps_for_timing.append(lap)
        valid_laps_for_timing.sort(key=lambda x: x.get('lap_index', 0))

    if valid_laps_for_timing:
        # Calculate Time from Laps
        first_lap = valid_laps_for_timing[0]
        last_lap = valid_laps_for_timing[-1]
        
        # Start Frame: Prefer diving start, else swimming start
        lf_start = first_lap.get('diving_segment', [None])[0]
        if lf_start is None: 
            lf_start = first_lap['swimming_segment'][0]
            
        # End Frame: Swimming end
        ll_end = last_lap['swimming_segment'][1]
        
        if lf_start is not None and ll_end is not None and ll_end > lf_start:
            total_time_frames = ll_end - lf_start
            total_time = total_time_frames / fps
            logging.info(f"Updated Total Time based on Laps ({len(valid_laps_for_timing)}): Frames {lf_start} to {ll_end} ({total_time:.2f}s)")
            
            # Recalculate Dist
            num_laps = len(valid_laps_for_timing)
            total_dist = num_laps * 25.0
            
            # Recalculate Speed
            avg_speed = total_dist / total_time if total_time > 0 else 0
            
            total_time_display = f"{total_time:.2f}"
            
            # Ensure passed dict has something relevant if empty (optional)
        else:
             logging.warning("Could not determine start/end frames from laps_data, keeping original timing.")
             
    else:
         # Fallback to original analyze_split_times result if no laps_data logic available
         # Calculate Avg Speed (Original)
         if total_time is not None:
             num_laps = 0
             if passed.get("50m"): num_laps = 2
             elif passed.get("25m"): num_laps = 1
             
             total_dist = num_laps * 25.0
             if total_time > 0:
                 avg_speed = total_dist / total_time
    
    # Safety ensure total_time is set
    if total_time is None:
        logging.warning("Timing analysis failed: Total time set to N/A.")
        total_time_display = "N/A"
        total_time = 0.0 # for SPM calc safety
    else:
        total_time = float(total_time)
        try:
             total_time_display = f"{total_time:.2f}"
        except: pass
        
    # Calculate SPM (Overall) using the (possibly updated) total_time
    total_strokes = stroke_result.get("total_count", 0)
    if total_time > 0:
        spm = total_strokes / (total_time / 60.0)
           
        # Calculate SPM & Strokes Breakdown (Dynamic Laps)
        spm_parts = []
        stroke_parts = []
        
        if laps_data:
             # Use Laps Data for Precise Swimming Segment SPM
             sorted_laps = sorted(laps_data, key=lambda x: x.get('lap_index', 0))
             total_swim_time_acc = 0.0
             valid_laps_found = False

             for lap in sorted_laps:
                 idx = lap.get('lap_index')
                 swim_seg = lap.get('swimming_segment')
                 
                 if not idx: continue

                 # Stroke Count
                 range_key = f"range{idx}_recovery_count"
                 cnt = stroke_result.get(range_key, 0)
                 stroke_parts.append(str(cnt))
                 
                 # Lap SPM (Swimming Time)
                 if swim_seg and swim_seg[0] is not None and swim_seg[1] > swim_seg[0]:
                     valid_laps_found = True
                     dur_frames = swim_seg[1] - swim_seg[0]
                     dur_sec = dur_frames / fps
                     total_swim_time_acc += dur_sec
                     
                     if dur_sec > 0:
                         curr_spm = cnt / (dur_sec / 60.0)
                         spm_parts.append(f"{curr_spm:.1f}")
                     else:
                         spm_parts.append("0.0")
                 else:
                     spm_parts.append("-")
             
             # Recalculate Overall SPM based on Total Swimming Time (User Request)
             if valid_laps_found and total_swim_time_acc > 0:
                 spm = total_strokes / (total_swim_time_acc / 60.0)
                 logging.info(f"Recalculated Overall SPM using Swim Time ({total_swim_time_acc:.2f}s): {spm:.1f}")

        else:
            # Fallback Legacy Logic
            lap_keys = [k for k in lap_durations.keys() if k.startswith("lap") and k[3:].isdigit()]
            lap_keys.sort(key=lambda x: int(x[3:])) 
            
            if not lap_keys and "range1_recovery_count" in stroke_result:
                 lap_keys = ["lap1"]
                 if "range2_recovery_count" in stroke_result: lap_keys.append("lap2")
    
            for lap_key in lap_keys:
                 lap_idx_str = lap_key.replace("lap", "")
                 range_key = f"range{lap_idx_str}_recovery_count"
                 
                 dur = lap_durations.get(lap_key)
                 cnt = stroke_result.get(range_key, 0)
                 
                 stroke_parts.append(str(cnt))
                 
                 if dur and dur > 0:
                     current_spm = cnt / (dur / 60.0)
                     spm_parts.append(f"{current_spm:.1f}")
        
        # Build Strings
        if spm_parts:
            spm_breakdown_str = " / ".join(spm_parts)
            
        strokes_breakdown_str = None
        if stroke_parts:
             strokes_breakdown_str = " / ".join(stroke_parts)
            
        logging.info(f"Performance Metrics: Laps={num_laps}, Dist={total_dist}m, Time={total_time:.2f}s, AvgSpeed={avg_speed:.2f}m/s, SPM={spm:.1f}, Breakdown={spm_breakdown_str}, Strokes={strokes_breakdown_str}")

    logging.info(f"Split timing complete. Total time: {total_time_display}s")


    # Step 7: Generate Tracking Video and Final Post-processing Overlay
    logging.info(
        "Step 7/7: Generating focus video and final post-processing overlay..."
    )
    # --- Naming: {base_name}_focus.mp4 in processed_dir ---
    focus_video_path = os.path.join(processed_dir, f"{base_name}_focus.mp4")
    # -----------------------------------------------------

    export_focus_only_video(video_path, final_output_path, focus_video_path)
    logging.info(f"Focus video generated at: {focus_video_path}")

    # Output processed video path
    # --- Naming: {base_name}_trajectory.avi in processed_dir (interim) ---
    processed_avi_path = os.path.join(processed_dir, f"{base_name}_trajectory.avi")
    # ---------------------------------------------------------------------------------

    # 2. MP4 最終輸出路徑 (用於 Streamlit 播放)
    # --- Naming: {base_name}_trajectory.mp4 in processed_dir ---
    final_mp4_path = os.path.join(processed_dir, f"{base_name}_trajectory.mp4")
    # ------------------------------------------------------------

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
    
    # 轉碼 Focus Video (確保瀏覽器可播放) - 覆蓋原檔案或新建
    # Currently focus video is already mp4 from opencv writer likely, but verify encoding.
    # We will transcode to ensure H.264 web compatibility
    final_focus_path = None
    if os.path.exists(focus_video_path):
        # Temp intermediate for focus
        focus_temp = focus_video_path.replace(".mp4", "_temp.mp4")
        os.rename(focus_video_path, focus_temp)
        final_focus_path = transcode_to_h264(focus_temp, focus_video_path, ffmpeg_path=ffmpeg_path)
        if os.path.exists(focus_temp):
             os.remove(focus_temp)
    
    if not final_focus_path:
        final_focus_path = focus_video_path

    if final_processed_video_path is None:
        # 如果轉碼失敗，我們仍然傳遞 AVI 路徑用於除錯或下載
        final_processed_video_path = processed_avi_path
        logging.error("FFMPEG Transcoding FAILED! Using raw AVI output for fallback.")

    logging.info(
        f"--- Process Complete! Processed video output at: {final_processed_video_path} ---"
    )
    print(f"\n[ORCHESTRATOR] ✅ ANALYSIS COMPLETE! Video saved to: {final_processed_video_path}\n", flush=True)

    # --- Resource Cleanup ---
    try:
        import gc
        import glob

        gc.collect()
        logging.info("Forcing Garbage Collection to release file locks.")
        
        # Cleanup unwanted PNGs (Kick Angle plots etc matching pattern)
        # Assuming they might be generated in processed_dir or keypoints_dir depending on implementation
        # User requested: "png圖片不需要存"
        for d in [keypoints_dir, processed_dir]:
            pngs = glob.glob(os.path.join(d, "*.png"))
            for p in pngs:
                try:
                    os.remove(p)
                    logging.info(f"Cleaned up PNG: {p}")
                except Exception as e:
                    logging.warning(f"Failed to delete PNG {p}: {e}")

    except Exception as e:
        logging.warning(f"Cleanup failed: {e}")
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
        "focus_video_path": final_focus_path,
        "processed_video_path": final_processed_video_path,
        "stroke_plot_figs": stroke_plot_figs,
        "kick_angle_fig_1": kick_angle_fig_1,
        "kick_angle_fig_2": kick_angle_fig_2,
        "diving_analysis": diving_analysis_result,
        "avg_speed": avg_speed,
        "spm": spm,
        "spm_breakdown": spm_breakdown_str,
        "strokes_breakdown": strokes_breakdown_str,
        "split_breakdown": split_breakdown,
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
