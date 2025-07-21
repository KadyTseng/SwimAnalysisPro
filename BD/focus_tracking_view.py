# BD/focus_tracking_view.py
import cv2
"""
先讀整個影片的最大範圍的bbox
中心點用髖關節
最後在resize成固定大小
產出追焦畫面再呼叫
"""
def get_max_bbox_size(txt_path, padding1=80, padding2=80):
    max_w = 0
    max_h = 0

    with open(txt_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            w = float(parts[4])
            h = float(parts[5])
            max_w = max(max_w, w)
            max_h = max(max_h, h)

    return int(max_w + padding1), int(max_h + padding2)

def crop_focus_frame(frame, hip_x, hip_y, box_w, box_h):
    h, w, _ = frame.shape
    cx, cy = int(hip_x), int(hip_y)

    x1 = max(cx - box_w // 2, 0)
    y1 = max(cy - box_h // 2, 0)
    x2 = min(cx + box_w // 2, w)
    y2 = min(cy + box_h // 2, h)

    return frame[y1:y2, x1:x2]

def export_focus_only_video(video_path, txt_path, output_focus_path, padding1=80, padding2=80, focus_size=(600, 300)):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_focus_path, fourcc, fps, focus_size)

    max_w, max_h = get_max_bbox_size(txt_path, padding1, padding2)

    with open(txt_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        ret, frame = cap.read()
        if not ret:
            break

        parts = line.strip().split()
        hip_x, hip_y = float(parts[19]), float(parts[20])

        focus_frame = crop_focus_frame(frame, hip_x, hip_y, max_w, max_h)
        focus_resized = cv2.resize(focus_frame, focus_size)

        out.write(focus_resized)

    cap.release()
    out.release()
    print(f"追焦影片輸出完成: {output_focus_path}")
