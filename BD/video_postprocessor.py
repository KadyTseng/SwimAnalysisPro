# BD/video_postprocessor.py

def overlay_results_on_video(video_path, analysis_results, output_path):
    """
    根據分析結果將資訊畫在影片上。這是一個簡化範例。
    """
    import cv2
    cap = cv2.VideoCapture(video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    frame_id = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if 'stroke_frames' in analysis_results:
            if frame_id in analysis_results['stroke_frames']:
                cv2.putText(frame, 'Stroke!', (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)

        out.write(frame)
        frame_id += 1

    cap.release()
    out.release()
    print(f"影片後製完成：{output_path}")