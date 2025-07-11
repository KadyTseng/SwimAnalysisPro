# BD/video_postprocessor.py

def overlay_results_on_video(video_path, analysis_results, output_path, split_times=None):
    """
    根據分析結果將資訊畫在影片上。
    split_times: dict，格式例子：
        {
            "passed": {"15m": frame_num1, "25m": frame_num2, "50m": frame_num3},
            "start_frame": int,
            "fps": float,
            "line_positions": {"15m": x1, "25m": x2, "50m": x3}
        }
    """

    import cv2

    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_id = 0
    active_labels = []

    # 如果有傳入分段時間資料，準備標籤資料
    time_labels_all = []
    if split_times:
        passed = split_times.get("passed", {})
        start_frame = split_times.get("start_frame", 0)
        line_positions = split_times.get("line_positions", {})
        for k in ["15m", "25m", "50m"]:
            if passed.get(k) is not None:
                sec = (passed[k] - start_frame) / fps
                direction = "left" if k == "50m" else "right"
                time_labels_all.append({
                    "frame": passed[k],
                    "label": f"{k} - {sec:.2f} sec",
                    "x": int(line_positions.get(k, 0)),
                    "y": 50 + len(time_labels_all) * 30,
                    "direction": direction
                })

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # 畫虛線（如果有）
        if split_times:
            for label, color in zip(["15m", "25m", "50m"], [(255, 0, 0)] * 3):
                x_pos = line_positions.get(label, 0)
                for y in range(0, height, 20):
                    cv2.line(frame, (int(x_pos), y), (int(x_pos), y + 10), color, 2)

        # 更新標籤顯示
        for label in time_labels_all:
            if label not in active_labels and frame_id >= label["frame"]:
                active_labels.append(label)

        # 畫時間文字
        for label in active_labels:
            text_x = label["x"] - 300 if label["direction"] == "left" else label["x"] + 10
            cv2.putText(
                frame,
                label["label"],
                (text_x, label["y"]),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2
            )

        # 保留你原本 stroke_frames 標記
        if 'stroke_frames' in analysis_results:
            if frame_id in analysis_results['stroke_frames']:
                cv2.putText(frame, 'Stroke!', (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)

        out.write(frame)
        frame_id += 1

    cap.release()
    out.release()
    print(f"影片後製完成：{output_path}")
