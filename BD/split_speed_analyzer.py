import pandas as pd

def analyze_split_times(txt_path, start_frame, fps, d15m_x0, d25m_x0, d50m_x0):
    """
    傳入追蹤txt路徑與起始frame、fps與距離線位置，
    回傳各距離達成的frame dict，以及總時間。
    """
    df = pd.read_csv(txt_path, sep=r"\s+", header=None)
    df = df[[0, 2, 4, 16]]
    df.columns = ["frame", "bbox_x", "bbox_w", "wrist_x"]
    df = df[df["frame"] >= start_frame].reset_index(drop=True)

    passed = {"15m": None, "25m": None, "50m": None}
    has_turned_back = False

    for _, row in df.iterrows():
        frame = int(row["frame"])
        xmin = row["bbox_x"]
        xmax = xmin + row["bbox_w"]
        x = row["wrist_x"]

        if passed["15m"] is None and x <= d15m_x0:
            passed["15m"] = frame

        if passed["25m"] is None and xmin <= d25m_x0:
            passed["25m"] = frame

        if passed["25m"] is not None and xmax >= d50m_x0 * 0.95:
            has_turned_back = True

        if has_turned_back and xmax >= d50m_x0:
            passed["50m"] = frame
            break

    total_time = None
    if passed["50m"] is not None:
        total_time = (passed["50m"] - start_frame) / fps

    return passed, total_time
