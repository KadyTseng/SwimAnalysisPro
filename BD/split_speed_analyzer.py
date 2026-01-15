import pandas as pd
import logging


def analyze_split_times(txt_path, start_frame, fps, d15m_x0, d25m_x0, d50m_x0):
    """
    傳入追蹤txt路徑與起始frame、fps與距離線位置，
    回傳各距離達成的frame dict，以及總時間。
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
        df = df[[0, 2, 4, 16]]
        df.columns = ["frame", "bbox_x", "bbox_w", "wrist_x"]

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
    has_turned_back = False

    for index, row in df.iterrows():  # 將 _ 改為 index, 方便追蹤哪一列在處理
        frame = int(row["frame"])
        xmin = row["bbox_x"]  # BBox 中心 X 座標 (根據您的數據，這可能是中心點)
        xmax = xmin + row["bbox_w"]  # 估計 BBox 右邊緣 (xmin + width)
        x = row["wrist_x"]  # 手腕 X 座標

        # 1. 15m 通過檢查 (使用手腕 X 座標)
        # 假設游向是 X 座標減小 (從右到左，常見的單邊鏡頭)
        if passed["15m"] is None and x <= d15m_x0:
            passed["15m"] = frame
            logging.info(
                f"✅ 15m Passed at Frame {frame} (Wrist X: {x:.2f} <= {d15m_x0:.2f})"
            )

        # 2. 25m 通過檢查 (使用 BBox Xmin 座標)
        # 注意：這裡使用 BBox xmin，如果 txt 欄位 2 存的是中心點，那麼 xmin 應為 center - width/2
        # 我們沿用您原有的邏輯 (欄位 2 是 BBox 中心點 X)
        if passed["25m"] is None and xmin <= d25m_x0:
            passed["25m"] = frame
            logging.info(
                f"✅ 25m Passed at Frame {frame} (BBox X_center: {xmin:.2f} <= {d25m_x0:.2f})"
            )

        # 3. 轉身/折返檢查 (進入 50m 區域前 5% 的預警)
        if passed["25m"] is not None and xmax >= d50m_x0 * 0.95:
            if not has_turned_back:
                logging.info(
                    f"⚠️ Near 50m Turn/Wall Detected at Frame {frame} (Xmax: {xmax:.2f})"
                )
            has_turned_back = True

        # 4. 50m 觸壁檢查 (必須在轉身標誌後且 BBox 右邊緣通過 50m 線)
        if has_turned_back and passed["50m"] is None and xmax >= d50m_x0:
            passed["50m"] = frame
            logging.info(
                f"🎯 50m Touch Detected at Frame {frame} (Xmax: {xmax:.2f} >= {d50m_x0:.2f})"
            )
            break

    # --- DEBUG 輸出 3：結果總結 ---
    total_time = None
    if passed["50m"] is not None:
        total_time = (passed["50m"] - start_frame) / fps
        logging.info(f"✅ Final 50m Time Calculated: {total_time:.2f}s")
    else:
        logging.warning("❌ 50m Split Point NOT detected.")
        logging.warning(f"Final Passed Dictionary: {passed}")  # 輸出當前找到的 15m/25m

    logging.info("--- Timing Analysis Debug End ---")
    return passed, total_time
