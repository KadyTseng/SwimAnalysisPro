import cv2
import os
import pandas as pd  # 確保導入 pandas 以處理 hip data dataframe
import logging


def overlay_results_on_video(
    video_path, analysis_results, output_path, split_times=None, focus_video_path=None
):
    """根據分析結果將資訊畫在影片上。
    analysis_results 必須包含 (用於軌跡):
    'df_hip_trajectory': DataFrame (包含 frame_id, hip_x, hip_y)
    'track_segment_start': int (軌跡繪製起始幀)
    'track_segment_end': int (軌跡繪製結束幀)
    """

    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    try:
        fourcc = cv2.VideoWriter_fourcc(*"H264")
        if fourcc == 0:
            fourcc = cv2.VideoWriter_fourcc(*"AVC1")
    except Exception:
        # 如果 OpenCV 在設定 H.264/AVC1 時遇到罕見錯誤，最終備用 XVID
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")

    try:
        # 優先使用傳入的 output_path (假設是 .mp4 或 .mov)
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not out.isOpened():
            raise IOError("Initial VideoWriter failed. Forcing MJPG/AVI.")

    # 優先使用傳入的 output_path (假設是 .mp4 或 .mov)
    except Exception as e:
        # 如果 H.264 初始化失敗（如日誌所示的 OpenH264 DLL 錯誤），則執行此區塊
        print(f"[警告] H.264 初始化失敗 ({e})。正在強制使用 MJPG/AVI 編碼器。")

        # 1. 設置 MJPG 標籤
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")

        # 2. 更改輸出路徑為 .avi
        output_path = os.path.splitext(output_path)[0] + ".avi"

        # 3. 重新初始化 VideoWriter
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not out.isOpened():
            print("[嚴重錯誤] MJPG/AVI 最終嘗試仍然失敗。")
            raise IOError("VideoWriter initialization failed. Cannot proceed.")

    focus_cap = None
    if focus_video_path is not None:
        focus_cap = cv2.VideoCapture(focus_video_path)

    frame_id = 0
    active_labels = []

    # --- 軌跡繪製初始化 ---
    df_hip_data = analysis_results.get("df_hip_trajectory", pd.DataFrame())
    track_start_frame = analysis_results.get("track_segment_start", 0)
    track_end_frame = analysis_results.get("track_segment_end", 0)

    # 建立 Hip 座標查詢映射 (frame_id -> (x, y))
    frame_to_hip = {
        int(row["frame_id"]): (int(row["hip_x"]), int(row["hip_y"]))
        for _, row in df_hip_data.iterrows()
        if "hip_x" in row and "hip_y" in row
    }

    track_points = []  # 儲存歷史軌跡點
    line_color = (0, 0, 255)  # 軌跡線顏色 (BGR: 紅色, 遵循原代碼)
    line_thickness = 3
    # --- 軌跡繪製初始化結束 ---

    # 🎯 設置偏移量
    OFFSET_25M = 100  # 25m 虛線的額外左移偏移
    TEXT_OFFSET_LEFT = 350  # 文字在左側時的偏移量 (確保在線左邊)
    TEXT_OFFSET_RIGHT = 10  # 文字在右側時的偏移量 (確保在線右邊)

    # 如果有傳入分段時間資料，準備標籤資料
    time_labels_all = []
    if split_times:
        passed = split_times.get("passed", {})
        start_frame = split_times.get("start_frame", 0)
        line_positions = split_times.get("line_positions", {})
        BASE_Y_OFFSET = height - 150

        for k in ["15m", "25m", "50m"]:
            if passed.get(k) is not None:
                sec = (passed[k] - start_frame) / fps

                # 🎯 恢復方向判斷，並統一將 15m/25m 設為 'right'，50m 設為 'left'
                direction = "left" if k == "50m" else "right"

                # 獲取 X 座標
                x_pos = int(line_positions.get(k, 0))

                # 🎯 關鍵修正 1：在初始化時對 25m 施加額外向左偏移 (虛線與文字一起移動)
                if k == "25m":
                    x_pos -= OFFSET_25M

                time_labels_all.append(
                    {
                        "frame": passed[k],
                        "label": f"{k}: {sec:.2f} sec",
                        "x": x_pos,  # 使用調整後的 X 座標
                        "y": BASE_Y_OFFSET,
                        "direction": direction,
                    }
                )

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 1. 軌跡點更新與繪製 (整合 draw_trajectory_on_video 的核心邏輯)
        if frame_id in frame_to_hip:
            x, y = frame_to_hip[frame_id]

            # A. 判斷是否在潛泳繪製範圍內，並更新歷史點
            if track_start_frame <= frame_id <= track_end_frame:
                track_points.append((x, y))

            # B. 繪製軌跡線 (使用您指定的 cv2.line 逐點連接邏輯)
            for i in range(len(track_points) - 1):
                cv2.line(
                    frame,
                    track_points[i],
                    track_points[i + 1],
                    line_color,
                    line_thickness,
                )

        # 2. 畫虛線、時間文字、Stroke! 標記 (原有的疊加邏輯)

        if split_times:
            pass
            # 1. 計算限制的 Y 座標範圍
            # height = frame.shape[0]  # 取得影片幀的實際高度 (例如 1080)

            # # 25% 的高度 (起始點)
            # start_y = int(height * 0.25)

            # # 75% 的高度 (結束點)
            # end_y = int(height * 0.80)

            # # 虛線的間隔設定
            # line_segment_length = 10  # 虛線段長度
            # line_gap = 10  # 虛線間隔長度 (總步長 20)
            # line_step = line_segment_length + line_gap  # 總步長 (20)

            # for label_key, color in zip(["15m", "25m", "50m"], [(0, 255, 0)] * 3):

            #     # 尋找已在 time_labels_all 中調整過的 X 座標
            #     current_label = next(
            #         (l for l in time_labels_all if l["label"].startswith(label_key)),
            #         None,
            #     )
            #     if current_label is None:
            #         continue

            #     x_pos = current_label["x"]  # 使用已經調整好的 X 座標 (25m 有額外偏移)

            #     # 3. 調整 range 函式，讓它從 start_y 開始，到 end_y 結束，步長為 line_step
            #     for y_line in range(start_y, end_y, line_step):

            #         # 計算線段的終點
            #         y_end = y_line + line_segment_length

            #         # 確保線段不會畫超出 end_y 範圍
            #         if y_end > end_y:
            #             y_end = end_y

            #         # 4. 繪製虛線段
            #         cv2.line(
            #             frame,
            #             (int(x_pos), y_line),  # 起點 (x_pos, y_line)
            #             (int(x_pos), y_end),  # 終點 (x_pos, y_end)
            #             color,
            #             2,
            #         )

        # 更新標籤顯示 (暫時取消文字顯示)
        # for label in time_labels_all:
        #     if label not in active_labels and frame_id >= label["frame"]:
        #         active_labels.append(label)

        # 畫時間文字 (暫時取消文字顯示)
        # for label in active_labels:
        #     # 🎯 關鍵修正 2：根據 direction 判斷文字位置
        #     # text_x = label["x"] - TEXT_OFFSET_LEFT if label["direction"] == "left" else label["x"] + TEXT_OFFSET_RIGHT
        #
        #     if label["direction"] == "left":
        #         # 50m (在右側，文字向左偏移)
        #         text_x = label["x"] - TEXT_OFFSET_LEFT
        #     else:
        #         # 15m 和 25m (在左側或中間，文字向左偏移)
        #         # 這裡使用負偏移量確保文字在虛線左側
        #         text_x = label["x"] - TEXT_OFFSET_LEFT
        #
        #     # 確保文字不會超出畫面左邊
        #     text_x = max(20, text_x)
        #
        #     cv2.putText(
        #         frame,
        #         label["label"],
        #         (text_x, label["y"]),
        #         cv2.FONT_HERSHEY_SIMPLEX,
        #         1.5,
        #         (0, 255, 0),
        #         2,
        #     )

        # 3. 疊加追焦小影片 (自動適應尺寸並置於右上角)
        # if focus_cap is not None:
        #     ret_f, focus_frame = focus_cap.read()
        #     if ret_f:
        #         # 🎯 自動讀取追焦畫面的高度與寬度
        #         # (這會是你設定的 height * 0.25 與 height * 0.5)
        #         fh, fw, _ = focus_frame.shape

        #         # 🎯 計算右上角位置
        #         # x_offset: 總寬度 - 追焦寬度 - 邊距
        #         # y_offset: 邊距
        #         margin = 20
        #         x_offset = width - fw - margin
        #         y_offset = margin

        #         # 💡 安全檢查：確保疊加區域不會超出主畫面邊界
        #         if x_offset >= 0 and y_offset + fh <= height:
        #             frame[y_offset : y_offset + fh, x_offset : x_offset + fw] = (
        #                 focus_frame
        #             )
        #         else:
        #             # 如果追焦畫面太大(這在 0.25 比例下通常不會發生)，可以縮小它
        #             logging.warning(
        #                 "Focus frame exceeds main video boundaries. Check scale."
        #             )

        out.write(frame)
        frame_id += 1

    cap.release()
    out.release()
    if focus_cap is not None:
        focus_cap.release()

    print(f"影片後製完成：{output_path}")
