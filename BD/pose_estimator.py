import torch
from ultralytics import YOLO
import cv2
import os
import numpy as np

def run_pose_estimation(
    model_path: str,
    video_path: str,
    output_dir: str,
    save_video: bool = True,
    save_txt: bool = True
):
    """
    對影片進行姿態估計，輸出帶骨架的影片與預測結果 txt。

    Args:
        model_path: YOLO 模型權重檔路徑
        video_path: 輸入影片路徑
        output_dir: 輸出資料夾（會自動建立）
        save_video: 是否輸出帶骨架的影片
        save_txt: 是否輸出預測結果 txt

    Returns:
        output_video_path: 輸出影片路徑或 None
        output_txt_path: 輸出 txt 路徑或 None
    """

    os.makedirs(output_dir, exist_ok=True)
    model = YOLO(model_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video file: {video_path}")

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    output_video_path = None
    if save_video:
        output_video_name = os.path.basename(video_path)
        output_video_path = os.path.join(output_dir, output_video_name)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))
    else:
        out = None

    output_txt_path = None
    if save_txt:
        output_txt_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(video_path))[0]}.txt")
        f_txt = open(output_txt_path, 'w', encoding='utf-8')
    else:
        f_txt = None

    skeleton_pairs = [
        (1, 2), (2, 3), (1, 4),
        (4, 5), (5, 6)
    ]

    colors = [
        (255, 0, 0),   (0, 255, 0),   (0, 0, 255),   (255, 255, 0), 
        (255, 0, 255), (0, 255, 255), (128, 128, 128) 
    ]

    frame_id = 0
    no_detection_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame)
        result = results[0]

        if result.keypoints is not None:
            keypoints = result.keypoints.xy.cpu().numpy() if torch.cuda.is_available() else result.keypoints.xy.numpy()

            keypoints_conf = result.keypoints.conf
            if keypoints_conf is not None:
                keypoints_conf = keypoints_conf.cpu().numpy() if torch.cuda.is_available() else keypoints_conf.numpy()
            else:
                keypoints_conf = np.zeros_like(keypoints[..., 0])

            # 畫關鍵點與骨架
            for keypoint, keypoint_conf in zip(keypoints, keypoints_conf):
                for i, (x, y, conf) in enumerate(zip(keypoint[:, 0], keypoint[:, 1], keypoint_conf)):
                    if x > 0 and y > 0:
                        color = colors[i % len(colors)]
                        cv2.circle(frame, (int(x), int(y)), 4, color, -1)

                for (i, j) in skeleton_pairs:
                    if 0 <= i < len(keypoint) and 0 <= j < len(keypoint):
                        x1, y1 = keypoint[i]
                        x2, y2 = keypoint[j]
                        if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:
                            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)

        if save_video:
            out.write(frame)

        if save_txt:
            if result.boxes is None or len(result.boxes) == 0:
                f_txt.write(f"{frame_id} no detection\n")
                no_detection_count += 1
            else:
                xywh = result.boxes.xywh.cpu().numpy() if torch.cuda.is_available() else result.boxes.xywh.numpy()
                confs = result.boxes.conf.cpu().numpy() if torch.cuda.is_available() else result.boxes.conf.numpy()
                classes = result.boxes.cls.cpu().numpy() if torch.cuda.is_available() else result.boxes.cls.numpy()

                keypoints = None
                keypoints_conf = None
                if result.keypoints is not None:
                    keypoints = result.keypoints.xy.cpu().numpy() if torch.cuda.is_available() else result.keypoints.xy.numpy()
                    keypoints_conf = result.keypoints.conf.cpu().numpy() if torch.cuda.is_available() else result.keypoints.conf.numpy()

                for i, (box_xywh, conf, cls) in enumerate(zip(xywh, confs, classes)):
                    x_center, y_center, width, height = box_xywh
                    keypoints_line = ""

                    if keypoints is not None and keypoints_conf is not None and i < len(keypoints):
                        keypoint_data = keypoints[i]
                        keypoint_conf_data = keypoints_conf[i]

                        for (kpt_x, kpt_y), kpt_conf in zip(keypoint_data, keypoint_conf_data):
                            keypoints_line += f" {kpt_x:.6f} {kpt_y:.6f} {kpt_conf:.6f}"

                    f_txt.write(f"{frame_id} {int(cls)} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f} {conf:.6f}{keypoints_line}\n")

        frame_id += 1

    cap.release()
    if save_video:
        out.release()
    if save_txt:
        f_txt.close()

    print(f"Prediction coordinates saved to: {output_txt_path}" if save_txt else "No txt saved.")
    print(f"Processed video saved to: {output_video_path}" if save_video else "No video saved.")

    return output_video_path if save_video else None, output_txt_path if save_txt else None


if __name__ == "__main__":
    # 範例測試
    model_path = r"D:\Kady\swimmer coco\runs\pose\train8\weights\best.pt"
    video_path = r"D:\Kady\swimmer coco\predict_test\test\Excellent_20230414_breaststroke_M_3 (12).mp4"
    output_dir = r"D:\Kady\swimmer coco\predict_test\test"

    run_pose_estimation(model_path, video_path, output_dir)
