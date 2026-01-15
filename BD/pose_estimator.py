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
    save_txt: bool = True,
):
    """
    對影片進行姿態估計，輸出帶骨架的影片與預測結果 txt。
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
    print(f"🎬 影片 {os.path.basename(video_path)} 總幀數: {total_frames}")

    # --- 確保輸出影片名稱是 _1.mp4 ---

    base_name, ext = os.path.splitext(os.path.basename(video_path))
    output_video_name = base_name + "_1" + ext
    output_video_path = os.path.join(output_dir, output_video_name)
    # output_video_path = None

    if save_video:
        output_video_name = base_name + "_1" + ext
        output_video_path = os.path.join(output_dir, output_video_name)
        # fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        try:
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
        except:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(
            output_video_path, fourcc, fps, (frame_width, frame_height)
        )
        if not out.isOpened():
            print("[警告] run_pose_estimation 影片寫入器初始化失敗，將跳過輸出影片。")
            # 如果初始化失敗，將 out 設為 None，避免後續的 out.write(frame) 出錯
            out = None
            save_video = False
    else:
        out = None

    output_txt_path = None

    if save_txt:
        output_txt_path = os.path.join(output_dir, f"{base_name}.txt")
        f_txt = open(output_txt_path, "w", encoding="utf-8")
    else:
        f_txt = None

    skeleton_pairs = [(1, 2), (2, 3), (1, 4), (4, 5), (5, 6)]
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
    ]

    frame_id = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame)
        result = results[0]

        if result.keypoints is not None:

            # 先取 keypoints（此時為 numpy）
            keypoints = (
                result.keypoints.xy.cpu().numpy()
                if torch.cuda.is_available()
                else result.keypoints.xy.numpy()
            )

            # 先取 keypoints_conf（此時為 Tensor）
            keypoints_conf = result.keypoints.conf

            # 如果有多個 BBOX，先挑最佳的 best_idx
            if result.boxes is not None:
                confs = (
                    result.boxes.conf.cpu().numpy()
                    if torch.cuda.is_available()
                    else result.boxes.conf.numpy()
                )

                if len(confs) > 1:
                    best_idx = np.argmax(confs)
                    keypoints = keypoints[best_idx : best_idx + 1]
                    keypoints_conf = keypoints_conf[
                        best_idx : best_idx + 1
                    ]  # <--還是 Tensor，不急著 numpy

            # 這裡才做 numpy 轉換（安全，不會出錯）
            if keypoints_conf is not None:
                keypoints_conf = (
                    keypoints_conf.cpu().numpy()
                    if torch.cuda.is_available()
                    else keypoints_conf.numpy()
                )
            else:
                keypoints_conf = np.zeros_like(keypoints[..., 0])

            # 畫關鍵點與骨架
            for keypoint, keypoint_conf in zip(keypoints, keypoints_conf):

                for i, (x, y, conf) in enumerate(
                    zip(keypoint[:, 0], keypoint[:, 1], keypoint_conf)
                ):

                    if x > 0 and y > 0:
                        color = colors[i % len(colors)]
                        cv2.circle(frame, (int(x), int(y)), 4, color, -1)

                for i, j in skeleton_pairs:

                    if 0 <= i < len(keypoint) and 0 <= j < len(keypoint):
                        x1, y1 = keypoint[i]
                        x2, y2 = keypoint[j]
                        if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:

                            cv2.line(
                                frame,
                                (int(x1), int(y1)),
                                (int(x2), int(y2)),
                                (255, 0, 0),
                                2,
                            )

        if save_video:
            out.write(frame)

        if save_txt:
            if result.boxes is None or len(result.boxes) == 0:
                f_txt.write(f"{frame_id} no detection\n")
            else:

                xywh = (
                    result.boxes.xywh.cpu().numpy()
                    if torch.cuda.is_available()
                    else result.boxes.xywh.numpy()
                )

                confs = (
                    result.boxes.conf.cpu().numpy()
                    if torch.cuda.is_available()
                    else result.boxes.conf.numpy()
                )

                classes = (
                    result.boxes.cls.cpu().numpy()
                    if torch.cuda.is_available()
                    else result.boxes.cls.numpy()
                )

                keypoints = None
                keypoints_conf = None
                if result.keypoints is not None:

                    keypoints = (
                        result.keypoints.xy.cpu().numpy()
                        if torch.cuda.is_available()
                        else result.keypoints.xy.numpy()
                    )

                    keypoints_conf = (
                        result.keypoints.conf.cpu().numpy()
                        if torch.cuda.is_available()
                        else result.keypoints.conf.numpy()
                    )
                if len(confs) > 1:
                    best_idx = np.argmax(confs)
                    xywh = xywh[best_idx : best_idx + 1]
                    confs = confs[best_idx : best_idx + 1]
                    classes = classes[best_idx : best_idx + 1]

                    if keypoints is not None:
                        keypoints = keypoints[best_idx : best_idx + 1]
                        keypoints_conf = keypoints_conf[best_idx : best_idx + 1]

                for i, (box_xywh, conf, cls) in enumerate(zip(xywh, confs, classes)):
                    x_center, y_center, width, height = box_xywh
                    keypoints_line = ""

                    if (
                        keypoints is not None
                        and keypoints_conf is not None
                        and i < len(keypoints)
                    ):

                        keypoint_data = keypoints[i]
                        keypoint_conf_data = keypoints_conf[i]

                        for (kpt_x, kpt_y), kpt_conf in zip(
                            keypoint_data, keypoint_conf_data
                        ):

                            keypoints_line += f" {kpt_x:.6f} {kpt_y:.6f} {kpt_conf:.6f}"

                    f_txt.write(
                        f"{frame_id} {int(cls)} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f} {conf:.6f}{keypoints_line}\n"
                    )

        if frame_id % 50 == 0:
            print(f"➡️ 已處理 {frame_id}/{total_frames} 幀")

        frame_id += 1

    cap.release()
    if save_video:
        out.release()
    if save_txt:
        f_txt.close()

    print(f"📄 Prediction saved to: {output_txt_path}" if save_txt else "No txt saved.")

    print(
        f"🎞 Processed video saved to: {output_video_path}"
        if save_video
        else "No video saved."
    )

    return output_video_path if save_video else None, (
        output_txt_path if save_txt else None
    )


if __name__ == "__main__":
    model_path = r"D:\Kady\swimmer coco\runs\pose\train8\weights\best.pt"
    input_dir = r"D:\Kady\swimmer coco\new pool\old_data"
    output_dir = input_dir  # 同資料夾輸出
    video_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".mp4")]

    for fname in video_files:
        video_path = os.path.join(input_dir, fname)

        print(f"\n🚀 開始處理影片: {fname}")
        run_pose_estimation(
            model_path, video_path, output_dir, save_video=True, save_txt=True
        )
