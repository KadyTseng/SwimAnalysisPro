import pandas as pd
import logging

def analyze_split_times(txt_path, start_frame, fps, d15m_x0, d25m_x0, d50m_x0, laps_data=None):
    """
    傳入追蹤txt路徑與起始frame、fps與距離線位置，
    回傳各距離達成的frame dict，以及總時間。
    
    Update: 優先使用 laps_data (從 Hip X 趨勢分析得來) 來決定 25m/50m 的觸壁時間 (使用 Lap End Frame)。
    15m 仍然使用座標穿越偵測。
    """

    # --- DEBUG 輸出 1：輸入參數與數據狀態 ---
    logging.info("--- Timing Analysis Debug Start ---")
    logging.info(f"Input: Start Frame={start_frame}, FPS={fps:.2f}")
    logging.info(
        f"Line Positions (X): 15m={d15m_x0:.2f}, 25m={d25m_x0:.2f}, 50m={d50m_x0:.2f}"
    )

    try:
        # 讀取數據
        df = pd.read_csv(txt_path, sep=r"\s+", header=None)
        # 選擇所需欄位: 0=frame, 2=bbox_x, 4=bbox_w, 16=wrist_x
        if df.shape[1] > 16:
            df = df[[0, 2, 4, 16]]
            df.columns = ["frame", "bbox_x", "bbox_w", "wrist_x"]
        else:
            logging.error(f"❌ TXT file format unexpected. Columns: {df.shape[1]}")
            return {"15m": None, "25m": None, "50m": None}, None

        # 過濾起始幀
        df = df[df["frame"] >= start_frame].reset_index(drop=True)

        if df.empty:
            logging.warning(
                f"❌ DataFrame is empty after filtering by start_frame {start_frame}."
            )
            return {"15m": None, "25m": None, "50m": None}, None

        logging.info(
            f"Data Loaded. Frames to process: {df['frame'].min()} to {df['frame'].max()}"
        )

    except Exception as e:
        logging.error(f"❌ Data loading or cleaning failed: {e}")
        return {"15m": None, "25m": None, "50m": None}, None

    passed = {"15m": None, "25m": None, "50m": None}

    # === NEW LOGIC: Use laps_data if available ===
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

        # 2. Identify Outbound (Decreasing) -> Handles 0-25m
        outbound_lap = next((L for L in valid_laps if "decreasing" in L.get("trend", "")), None)
        
        if outbound_lap:
            l1_start, l1_end = outbound_lap["lap_range"]
            logging.info(f"   identified Outbound Lap: {outbound_lap.get('lap_index')} ({l1_start}-{l1_end})")
            
            # --- 25m Split Logic ---
            # 假設去程結束就是碰到對面牆壁 (25m)
            passed["25m"] = l1_end
            logging.info(f"   Note: Outbound Lap End ({l1_end}) set as 25m split.")
            
            # --- 15m Split Logic ---
            try:
                df_lap1 = df[(df["frame"] >= l1_start) & (df["frame"] <= l1_end)]
                # 假設去程 X 減少，尋找首次 wrist_x <= d15m_x0
                cross_15 = df_lap1[df_lap1["wrist_x"] <= d15m_x0]
                if not cross_15.empty:
                    passed["15m"] = int(cross_15.iloc[0]["frame"])
                    logging.info(f"   ✅ 15m Detected at Frame {passed['15m']} (WristX <= {d15m_x0:.1f})")
                else:
                    logging.warning(f"   ⚠️ 15m cross not detected via coordinates in Outbound Lap.")
            except Exception as e:
                logging.warning(f"Error calculating 15m split: {e}")
        else:
             logging.warning("   ⚠️ No 'decreasing' (Outbound) lap found. 15m/25m splits skipped.")

        # 3. Identify Inbound (Increasing) -> Handles 25-50m
        # We look for an increasing lap that starts AFTER the outbound lap (if outbound exists)
        # Or just the first increasing lap if no outbound exists (e.g. start video from other side?)
        start_search_frame = outbound_lap["lap_range"][1] if outbound_lap else 0
        
        inbound_lap = next((L for L in valid_laps 
                            if "increasing" in L.get("trend", "") 
                            and L.get("lap_range", (0,0))[0] >= start_search_frame), None)
                            
        if inbound_lap:
            l2_start, l2_end = inbound_lap["lap_range"]
            logging.info(f"   Identified Inbound Lap: {inbound_lap.get('lap_index')} ({l2_start}-{l2_end})")
            
            # --- 50m Split Logic ---
            # 回程結束就是回到起點 (50m)
            passed["50m"] = l2_end
            logging.info(f"   Note: Inbound Lap End ({l2_end}) set as 50m split.")
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
            if passed["15m"] is None and x_wrist <= d15m_x0:
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

    # 2. Segment Split Times
    # 0-15m
    t0_15 = get_duration(start_frame, passed["15m"])
    if t0_15: split_breakdown["0-15m"] = f"{t0_15:.2f}s"
    
    # 15-25m
    t15_25 = get_duration(passed["15m"], passed["25m"])
    if t15_25: split_breakdown["15-25m"] = f"{t15_25:.2f}s"
    
    # 25-50m
    t25_50 = get_duration(passed["25m"], passed["50m"])
    if t25_50: split_breakdown["25-50m"] = f"{t25_50:.2f}s"

    logging.info(f"Split Breakdown: {split_breakdown}")
    logging.info(f"Lap Durations (for SPM): {lap_durations}")

    logging.info("--- Timing Analysis Debug End ---")
    return passed, total_time, split_breakdown, lap_durations
