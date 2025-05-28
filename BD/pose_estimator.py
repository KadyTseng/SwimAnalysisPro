import torch
from ultralytics import YOLO
import cv2
import os
import numpy as np

# 骨架模型
model = YOLO(r"D:\Kady\swimmer coco\runs\pose\train8\weights\best.pt")

# 設定影片路徑與輸出目錄
video_path = r"D:\Kady\swimmer coco\predict_test\test\Excellent_20230414_breaststroke_M_3 (12).mp4"     # 目前是手動
output_dir = r"D:\Kady\swimmer coco\predict_test\test"                                                   # 放產出的影片及預測骨架的txt
os.makedirs(output_dir, exist_ok=True)

# 開啟影片
cap = cv2.VideoCapture(video_path)
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# 設定影片輸出
output_video_name = os.path.basename(video_path)
output_video_path = os.path.join(output_dir, output_video_name)
fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # 設定 MP4 格式
out = cv2.VideoWriter(output_video_path, fourcc, fps, (frame_width, frame_height))

skeleton_pairs = [
    (1, 2), (2, 3), (1, 4),
    (4, 5), (5, 6)
]

# 設定不同顏色給 7 個關鍵點
colors = [
    (255, 0, 0),   (0, 255, 0),   (0, 0, 255),   (255, 255, 0), 
    (255, 0, 255), (0, 255, 255), (128, 128, 128) 
]

output_txt_path = os.path.join(output_dir, f"{os.path.splitext(output_video_name)[0]}.txt")
no_detection_count = 0  

frame_id = 0
with open(output_txt_path, 'w') as f:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break  


        results = model(frame)

        result = results[0]
        if result.keypoints is not None: 
            keypoints = result.keypoints.xy.cpu().numpy() if torch.cuda.is_available() else result.keypoints.xy.numpy()

            # 確保 keypoints.conf 存在
            keypoints_conf = result.keypoints.conf
            if keypoints_conf is not None:
                keypoints_conf = keypoints_conf.cpu().numpy() if torch.cuda.is_available() else keypoints_conf.numpy()
            else:
                keypoints_conf = np.zeros_like(keypoints[..., 0])  # 若無信心值，設為 0

            for keypoint, keypoint_conf in zip(keypoints, keypoints_conf):
                # 畫出關鍵點（使用不同顏色）
                for i, (x, y, conf) in enumerate(zip(keypoint[:, 0], keypoint[:, 1], keypoint_conf)):
                    if x > 0 and y > 0:  
                        color = colors[i % len(colors)]  
                        cv2.circle(frame, (int(x), int(y)), 4, color, -1) 
                        #cv2.putText(frame, f"{conf:.2f}", (int(x), int(y) - 5),
                                    #cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                for (i, j) in skeleton_pairs:
                    if all(0 <= idx < len(keypoint) for idx in (i, j)):
                        x1, y1 = keypoint[i]
                        x2, y2 = keypoint[j]
                        if x1 > 0 and y1 > 0 and x2 > 0 and y2 > 0:  
                            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2) 


        out.write(frame)
        frame_id += 1

        if results[0].boxes is None or len(results[0].boxes) == 0:
            f.write(f"{frame_id} no detection\n")
            no_detection_count += 1
        else:
            for i, box in enumerate(results[0].boxes):
                xywh = box.xywh.cpu().numpy() if torch.cuda.is_available() else box.xywh.numpy()
                conf = box.conf.cpu().numpy() if torch.cuda.is_available() else box.conf.numpy()
                cls = box.cls.cpu().numpy() if torch.cuda.is_available() else box.cls.numpy()

                for xywh_item, conf_item, cls_item in zip(xywh, conf, cls):
                    x_center, y_center, width, height = xywh_item
                    keypoints_line = ""

                    if result.keypoints is not None:
                        keypoints = result.keypoints.xy.cpu().numpy() if torch.cuda.is_available() else result.keypoints.xy.numpy()
                        keypoints_conf = result.keypoints.conf.cpu().numpy() if torch.cuda.is_available() else result.keypoints.conf.numpy()

                        keypoint_data = keypoints[i]  
                        keypoint_conf_data = keypoints_conf[i]

                        for (kpt_x, kpt_y), kpt_conf in zip(keypoint_data, keypoint_conf_data):
                            keypoints_line += f" {kpt_x:.6f} {kpt_y:.6f} {kpt_conf:.6f}"

                    line = f"{frame_id} {int(cls_item)} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f} {conf_item:.6f}{keypoints_line}\n"
                    f.write(line)

# # 紀錄影片總幀數與未偵測幀數
# with open(output_txt_path, 'a') as f:
#     f.write(f"\nTotal frames: {total_frames}\n")
#     f.write(f"Frames without detection: {no_detection_count}\n")

# 釋放資源
cap.release()
out.release()
cv2.destroyAllWindows()

# 印出結果
print(f"Prediction coordinates saved to: {output_txt_path}")
print(f"Processed video saved to: {output_video_path}")
