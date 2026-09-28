import pandas as pd
import numpy as np
import logging

def analyze_split_times(txt_path, start_frame, fps, d15m_x0, d25m_x0, d50m_x0, laps_data=None):
    """
    傳入追蹤txt路徑與起始frame、fps與距離線位置，
    回傳各距離達成的frame dict，以及總時間。
    
    Update: 優先使用 laps_data (從 Hip X 趨勢分析得來) 來決定 25m/50m 的觸壁時間 (使用 Lap End Frame)。
    15m 仍然使用座標穿越偵測。
    
    Update (Thesis Logic): 使用膝角 (Knee Flexion Angle) 來偵測真實的 Push-off 作為計時起點。
    """

    from scipy.signal import find_peaks
    def get_first_true_local_min_backwards(df_sub):
        vals = df_sub['angle_smooth'].values
        peaks, _ = find_peaks(-vals, prominence=5)
        if len(peaks) > 0:
            return int(df_sub.iloc[peaks[-1]]['frame_id'])
        else:
            return int(df_sub.loc[df_sub['angle_smooth'].idxmin(), 'frame_id'])

    # --- DEBUG 輸出 1：輸入參數與數據狀態 ---
    logging.info("--- Timing Analysis Debug Start ---")
    logging.info(f"Input: Start Frame={start_frame}, FPS={fps:.2f}")
    logging.info(
        f"Line Positions (X): 15m={d15m_x0:.2f}, 25m={d25m_x0:.2f}, 50m={d50m_x0:.2f}"
    )

    # === NEW LOGIC: Dynamic Calibration ===
    if d15m_x0 is None or d25m_x0 is None:
        try:
            from BD.calibration import get_pixel_for_distance
            d15m_x0 = get_pixel_for_distance(15.0)
            d25m_x0 = get_pixel_for_distance(25.0)
            d0m_x0 = get_pixel_for_distance(0.0)
            logging.info(f"Dynamically calibrated pixels: 0m={d0m_x0:.2f}, 15m={d15m_x0:.2f}, 25m={d25m_x0:.2f}")
        except Exception as e:
            logging.warning(f"Dynamic calibration failed, using fallback pixels: {e}")
            # fallback
            d0m_x0 = 3748.0
            d15m_x0 = 1551.0
            d25m_x0 = 136.0

    try:
        # 讀取數據
        df = pd.read_csv(txt_path, sep=r"\s+", header=None)
        # 0=frame, 2=bbox_x, 4=bbox_w
        if df.shape[1] > 4:
            # 計算 bbox_left (xmin) 與 bbox_right (xmax)
            # 因為 bbox_x 是中心點，所以 left = x - w/2, right = x + w/2
            df["bbox_left"] = df[2] - df[4] / 2.0
            df["bbox_right"] = df[2] + df[4] / 2.0
            
            # 簡單平滑處理，避免因為 width 瞬間變動導致的判定誤觸
            for col in ["bbox_left", "bbox_right"]:
                df.loc[df[col].diff().abs() > 50, col] = np.nan
                df.loc[df[col].diff(periods=-1).abs() > 50, col] = np.nan
                df[col] = df[col].interpolate(method="linear", limit_direction="both")
                df[col] = df[col].rolling(window=7, min_periods=1, center=True).mean()
        else:
            logging.error(f"❌ TXT file format unexpected. Columns: {df.shape[1]}")
            return {"15m": None, "25m": None, "50m": None}, None, {}, {}, start_frame

        # 這裡不提早過濾 start_frame，因為我們將重新計算精準的 Kick-off
        # df = df[df[0] >= start_frame].reset_index(drop=True)
        
        df.rename(columns={0: "frame"}, inplace=True)
        
        # --- NEW LOGIC: Load and Smooth Knee Angles ---
        try:
            from BD.diving_analyzer_track_angles import calculate_kick_angles_from_txt
            df_angles = calculate_kick_angles_from_txt(txt_path)
            df_angles["angle_smooth"] = df_angles["angle"].rolling(window=7, min_periods=1, center=True).mean()
            logging.info("✅ Knee angles loaded for Push-off detection.")
        except Exception as e:
            logging.warning(f"⚠️ Could not calculate knee angles: {e}")
            df_angles = None

        if df.empty:
            logging.error(f"❌ DataFrame is empty after filtering by start_frame {start_frame}.")
            return {"15m": None, "25m": None, "50m": None}, None, {}, {}, start_frame

        logging.info(
            f"Data Loaded. Frames to process: {df['frame'].min()} to {df['frame'].max()}"
        )

    except Exception as e:
        logging.error(f"❌ Data loading or cleaning failed: {e}")
        return {"15m": None, "25m": None, "50m": None}, None, {}, {}, start_frame

    passed = {"15m": None, "25m": None, "50m": None}

    # === NEW LOGIC: Use laps_data if available ===
    if laps_data:
        logging.info(f"✅ Using Laps Data for Split Timing: {len(laps_data)} raw laps.")
        
        # 1. Filter out static laps and sort by time
        valid_laps = [L for L in laps_data if L.get("trend") != "static"]
        valid_laps.sort(key=lambda x: x.get("lap_range", (0, 0))[0])
        
        logging.info(f"   Valid Swimming Laps found: {len(valid_laps)}")
        for i, vl in enumerate(valid_laps):
             logging.info(f"     -> [{i}] Index {vl.get('lap_index')}: {vl.get('trend')} ({vl.get('lap_range')})")
             # Log detailed phases if available
             div_seg = vl.get('diving_segment')
             if div_seg: logging.info(f"        Detailed: Diving Phase: {div_seg[0]}-{div_seg[1]}")
             
             swim_seg = vl.get('swimming_segment')
             if swim_seg: logging.info(f"        Detailed: Swimming Phase: {swim_seg[0]}-{swim_seg[1]}")
             elif div_seg:
                  # If diving segment exists but swimming doesn't explicit frame, assume rest is swimming
                  logging.info(f"        Detailed: Swimming Phase: {div_seg[1]}-{vl.get('lap_range')[1]}")

        # 2. Identify Outbound (Decreasing) -> Handles Kickoff, 15m, 25m
        outbound_lap = next((L for L in valid_laps if "decreasing" in L.get("trend", "")), None)
        
        if outbound_lap:
            l1_start, l1_end = outbound_lap["lap_range"]
            logging.info(f"   identified Outbound Lap: {outbound_lap.get('lap_index')} ({l1_start}-{l1_end})")
            
            df_outbound = df[(df["frame"] >= l1_start) & (df["frame"] <= l1_end)]
            
            # --- Kick-off (0m) Split Logic ---
            # 尋找去程初期的最大 BBox 右側 (選手發力前、身體往後延伸的極限點)
            df_kickoff_search = df_outbound.head(int(len(df_outbound) * 0.3)) # 只找前 30% 作為發力準備期
            if not df_kickoff_search.empty:
                max_windup_idx = df_kickoff_search["bbox_right"].idxmax()
                max_windup_val = df_kickoff_search.loc[max_windup_idx, "bbox_right"]
                
                # 從這個極值點往後找，只要掉超過 10 pixel，就視為腳正式離開出發台/牆壁！
                df_after_windup = df_outbound.loc[max_windup_idx:]
                cross_0 = df_after_windup[df_after_windup["bbox_right"] < max_windup_val - 10]
                
                if not cross_0.empty:
                    kick_off_0m = int(cross_0.iloc[0]["frame"])
                    logging.info(f"   ✅ Kick-off Detected at Frame {kick_off_0m} (Dropped from peak {max_windup_val:.1f})")
                else:
                    kick_off_0m = l1_start
                    logging.warning(f"   ⚠️ Kick-off fallback to lap start: {kick_off_0m}")
            else:
                kick_off_0m = l1_start
                logging.warning(f"   ⚠️ Kick-off fallback (empty search window): {kick_off_0m}")
            
            # --- TRUE PUSH-OFF (0m) LOGIC ---
            push_off_0m = kick_off_0m
            if df_angles is not None and not df_angles.empty:
                search_start = max(df_angles['frame_id'].min(), kick_off_0m - 90)
                df_search = df_angles[(df_angles['frame_id'] >= search_start) & (df_angles['frame_id'] <= kick_off_0m)]
                if not df_search.empty:
                    push_off_0m = get_first_true_local_min_backwards(df_search)
                    logging.info(f"   ✅ True 0m Push-off detected via knee angle at Frame {push_off_0m}")
            
            passed["0m_push_off"] = push_off_0m
            # 將舊的 start_frame 賦值為 push_off_0m，以利後續 fallback 使用
            start_frame = push_off_0m
            
            # 只取 kickoff 之後的資料來找 15m 和 25m
            df_outbound = df_outbound[df_outbound["frame"] >= kick_off_0m]

            # --- 15m Split Logic ---
            # 15m: BBox 左側 (Leading Edge) 到達 <= 15m
            cross_15 = df_outbound[df_outbound["bbox_left"] <= d15m_x0]
            if not cross_15.empty:
                passed["15m"] = int(cross_15.iloc[0]["frame"])
                logging.info(f"   ✅ 15m Detected at Frame {passed['15m']}")
            
            # --- 25m Split Logic ---
            # 25m: BBox 左側 (Leading Edge) 到達 <= 25m
            cross_25 = df_outbound[df_outbound["bbox_left"] <= d25m_x0]
            if not cross_25.empty:
                passed["25m"] = int(cross_25.iloc[0]["frame"])
                logging.info(f"   ✅ 25m Detected at Frame {passed['25m']}")
            else:
                passed["25m"] = l1_end
                logging.warning(f"   ⚠️ 25m fallback to lap end: {passed['25m']}")
                
        else:
             logging.warning("   ⚠️ No 'decreasing' (Outbound) lap found. 15m/25m splits skipped.")

        # 3. Identify Inbound (Increasing) -> Handles 50m
        start_search_frame = passed.get("25m") if passed.get("25m") else (outbound_lap["lap_range"][1] if outbound_lap else 0)
        
        inbound_lap = next((L for L in valid_laps 
                            if "increasing" in L.get("trend", "") 
                            and L.get("lap_range", (0,0))[0] >= start_search_frame), None)
                            
        if inbound_lap:
            l2_start, l2_end = inbound_lap["lap_range"]
            logging.info(f"   Identified Inbound Lap: {inbound_lap.get('lap_index')} ({l2_start}-{l2_end})")
            
            df_inbound = df[(df["frame"] >= l2_start) & (df["frame"] <= l2_end)]
            
            # --- 25m Kick-off & Push-off Logic ---
            push_off_25m = l2_start # Default fallback
            if passed.get("25m"):
                df_after_touch = df[(df["frame"] > passed["25m"]) & (df["frame"] <= l2_end)]
                # Trailing edge for inbound is bbox_left, leaving the 25m wall
                cross_out = df_after_touch[df_after_touch["bbox_left"] > d25m_x0]
                if not cross_out.empty:
                    kick_off_25m = int(cross_out.iloc[0]["frame"])
                else:
                    kick_off_25m = passed["25m"]
                    
                if df_angles is not None and not df_angles.empty:
                    search_angle_start = max(df_angles['frame_id'].min(), max(passed["25m"], kick_off_25m - 120))
                    df_angle_search = df_angles[(df_angles['frame_id'] >= search_angle_start) & (df_angles['frame_id'] <= kick_off_25m)]
                    if not df_angle_search.empty:
                        push_off_25m = get_first_true_local_min_backwards(df_angle_search)
                        logging.info(f"   ✅ True 25m Push-off detected via knee angle at Frame {push_off_25m}")
                    else:
                        push_off_25m = kick_off_25m
            passed["25m_push_off"] = push_off_25m
            
            # --- 50m Split Logic ---
            # 50m: 回程時，BBox 右側 (Leading Edge in this direction) 只要一大於 3748(0m) 就算到了
            # 為了避免 hip_x 的 lap 提早結束導致漏抓，我們直接從回程起點 (l2_start) 搜尋到影片最後一格
            df_after_turn = df[df["frame"] >= l2_start]
            cross_50 = df_after_turn[df_after_turn["bbox_right"] >= d50m_x0]
            
            if not cross_50.empty:
                passed["50m"] = int(cross_50.iloc[0]["frame"])
                logging.info(f"   ✅ 50m Detected at Frame {passed['50m']}")
            else:
                # 找不到大於 3748 的幀 (可能沒摸到物理牆壁、角度問題等)
                # 改為抓取回程區間中「BBox 右側到達最遠(最大值)」的那一幀，代表手伸到最極限觸牆的瞬間
                df_inbound_only = df[(df["frame"] >= l2_start) & (df["frame"] <= l2_end)]
                if not df_inbound_only.empty:
                    max_right_frame = int(df_inbound_only.loc[df_inbound_only["bbox_right"].idxmax(), "frame"])
                    passed["50m"] = max_right_frame
                    logging.warning(f"   ⚠️ 50m fallback to MAX BBox Right: {passed['50m']}")
                else:
                    passed["50m"] = l2_end
                    logging.warning(f"   ⚠️ 50m fallback to lap end: {passed['50m']}")
        else:
             logging.warning("   ⚠️ No proper 'increasing' (Inbound) lap found. 50m split skipped.")

    # === FALLBACK LOGIC: Raw Coordinate Iteration (Only if laps_data missing) ===
    else:
        logging.info("⚠️ laps_data not provided. Using raw coordinate iteration (Legacy Mode).")
        has_turned_back = False
        min_observed_xmin = float('inf')
        min_observed_wrist_x = float('inf')

        for index, row in df.iterrows():
            frame = int(row["frame"])
            xmin = row["bbox_x"]
            width_val = row["bbox_w"]
            xmax = xmin + width_val
            x_wrist = row["wrist_x"]

            # Update Debug Mins
            if xmin < min_observed_xmin: min_observed_xmin = xmin
            if x_wrist < min_observed_wrist_x: min_observed_wrist_x = x_wrist

            # 1. 15m
            if passed["15m"] is None and xmin <= d15m_x0:
                passed["15m"] = frame
                logging.info(f"✅ 15m Passed at Frame {frame}")

            # 2. 25m
            if passed["25m"] is None:
                if xmin <= d25m_x0:
                    passed["25m"] = frame
                    logging.info(f"✅ 25m Passed at Frame {frame}")
                elif x_wrist <= d25m_x0:
                     passed["25m"] = frame
                     logging.info(f"✅ 25m Passed (by Wrist) at Frame {frame}")

            # 3. Turn Check
            if passed["25m"] is not None and xmax >= d50m_x0 * 0.95:
                has_turned_back = True

            # 4. 50m
            if has_turned_back and passed["50m"] is None and xmax >= d50m_x0:
                passed["50m"] = frame
                logging.info(f"🎯 50m Touch Detected at Frame {frame}")
                break
        
        if passed["50m"] is None:
             logging.warning(f"Final Passed: {passed}. Min BBox X: {min_observed_xmin:.2f}, Min Wrist X: {min_observed_wrist_x:.2f}")

    # === RESULT AGGREGATION ===
    total_time = None
    split_breakdown = {}
    lap_durations = {}  # New: Store duration of each lap for SPM calc

    # helper for safe calc
    def get_duration(start_f, end_f):
        if start_f is not None and end_f is not None and end_f > start_f:
            return (end_f - start_f) / fps
        return None

    # Calculate Lap Durations from Laps Data (if available) - DYNAMIC VERSION
    if laps_data:
        valid_laps = [L for L in laps_data if L.get("trend") != "static"]
        # Sort by start frame just in case
        valid_laps.sort(key=lambda x: x.get("lap_range", (0, 0))[0])
        
        for L in valid_laps:
            idx = L.get("lap_index")
            
            # Priority: Swimming Segment (for accurate SPM) > Lap Range
            # SPM should be calculated based on the time spent swimming strokes, excluding pushoff/glide.
            seg = L.get("swimming_segment")
            # Validate segment
            if not seg or seg[0] is None or seg[1] is None or seg[1] <= seg[0]:
                seg = L.get("lap_range")
            
            if idx is not None and seg and seg[0] is not None and seg[1] is not None:
                dur = get_duration(seg[0], seg[1])
                if dur and dur > 0:
                    lap_durations[f"lap{idx}"] = dur
        
        logging.info(f"Dynamic Lap Durations Calculated: {lap_durations.keys()}")

    # === Legacy Fallback for Lap Durations ===
    if not lap_durations:
         d25 = passed.get("25m")
         d50 = passed.get("50m")
         
         # Lap 1: Start -> 25m
         if d25:
             dur1 = get_duration(start_frame, d25)
             if dur1: lap_durations["lap1"] = dur1
             
         # Lap 2: 25m -> 50m
         if d25 and d50:
             dur2 = get_duration(d25, d50)
             if dur2: lap_durations["lap2"] = dur2

    # 1. Total Time (Legacy/Overall)
    if passed["50m"] is not None:
        total_time = get_duration(start_frame, passed["50m"])
        logging.info(f"✅ Final 50m Time Calculated: {total_time:.2f}s")
    elif passed["25m"] is not None:
        total_time = get_duration(start_frame, passed["25m"])
        logging.info(f"✅ Final 25m Time Calculated: {total_time:.2f}s")
    else:
        logging.warning("❌ No 25m/50m end point detected.")

    # 2. Segment Split Times (Updated for Thesis Logic)
    
    # 0-15m: 15m - 0m Push-off
    if passed.get("0m_push_off") and passed.get("15m"):
        t0_15 = get_duration(passed["0m_push_off"], passed["15m"])
        if t0_15: split_breakdown["0-15m"] = f"{t0_15:.2f}s"
    
    # 15-25m: 25m Wall-touch - 15m
    if passed.get("15m") and passed.get("25m"):
        t15_25 = get_duration(passed["15m"], passed["25m"])
        if t15_25: split_breakdown["15-25m"] = f"{t15_25:.2f}s"
        
    # 0-25m (Lap 1 Total): 25m Wall-touch - 0m Push-off
    if passed.get("0m_push_off") and passed.get("25m"):
        t_lap1 = get_duration(passed["0m_push_off"], passed["25m"])
        if t_lap1: split_breakdown["0-25m"] = f"{t_lap1:.2f}s"
    
    # 25-50m (Lap 2 Total): 50m Wall-touch - 25m Push-off
    if passed.get("25m_push_off") and passed.get("50m"):
        t25_50 = get_duration(passed["25m_push_off"], passed["50m"])
        if t25_50: split_breakdown["25-50m"] = f"{t25_50:.2f}s"

    logging.info(f"Split Breakdown (using Push-off base): {split_breakdown}")
    logging.info(f"Lap Durations (for SPM): {lap_durations}")

    logging.info("--- Timing Analysis Debug End ---")
    
    # Return 0m_push_off as start_frame if available
    final_start = passed.get("0m_push_off", start_frame)
    return passed, total_time, split_breakdown, lap_durations, final_start
