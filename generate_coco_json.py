import os
import glob
import json
import cv2
from ultralytics import YOLO

# ==========================================
# 參數與對應關係 (等待你後續提供來填補)
# ==========================================

MODEL_PATH = "data/models/best_1.pt"
BASE_DIR = r"D:\coco\coco-annotator\datasets" # e.g. "D:/Kady/datasets"

# 想跑的 7 個子資料夾名稱
TARGET_FOLDERS = [
     "Excellent_20260120_freestyle_M_3(4)",
     "Excellent_20260120_freestyle_M_3(5)",
     "Excellent_20260120_butterfly_F_3 (2)",
     "Excellent_20260120_breaststroke_M_3(1)",
     "Excellent_20260120_backstroke_M_3",
     "Excellent_20260120_backstroke_F_3"
]

# 資料夾名稱與 Dataset ID 的對應
FOLDER_TO_DATASET_ID = {
    "Excellent_20260120_backstroke_F_3": 92,
    "Excellent_20260120_backstroke_M_3": 93,
    "Excellent_20260120_breaststroke_M_3(1)": 94,
    "Excellent_20260120_butterfly_F_3 (2)": 95,
    "Excellent_20260120_freestyle_M_3(4)": 96,
    "Excellent_20260120_freestyle_M_3(5)": 97,
}

# 每個資料夾中第一張圖片的起始 ID
START_IMAGE_ID_PER_FOLDER = {
    "Excellent_20260120_backstroke_F_3": 95211,
    "Excellent_20260120_backstroke_M_3": 96756,
    "Excellent_20260120_breaststroke_M_3(1)": 98573,
    "Excellent_20260120_butterfly_F_3 (2)": 104493,
    "Excellent_20260120_freestyle_M_3(4)": 107927,
    "Excellent_20260120_freestyle_M_3(5)": 105573,
}

# 標註 (Annotation) 的起始全域 ID
START_ANNOTATION_ID = 15175

# ==========================================

def get_base_coco():
    """回傳使用者指定格式的 COCO 基本骨架"""
    return {
        "images": [],
        "categories": [
            {
                "id": 1,
                "name": "swimmer",
                "supercategory": "",
                "color": "#c6b9b9",
                "metadata": {},
                "keypoint_colors": ["#bf5c4d", "#d99100", "#4d8068", "#bf5c4d", "#d99100", "#4d8068", "#0d2b80"],
                "keypoints": ["head", "shoulder", "elbow", "wrist", "hip", "knee", "ankle"],
                "skeleton": [[2, 3], [2, 5], [3, 4], [5, 6], [6, 7]]
            }
        ],
        "annotations": []
    }

def main():
    model = YOLO(MODEL_PATH)
    
    # 臨時的備用流水號 (萬一沒給字典，程式也能產生唯一 ID 代替)
    fallback_image_id = 900000
    current_ann_id = START_ANNOTATION_ID
    
    for folder_name in TARGET_FOLDERS:
        # 每個資料夾獨立一份 COCO json 骨架
        coco_data = get_base_coco()
        folder_path = os.path.join(BASE_DIR, folder_name)
        if not os.path.exists(folder_path):
            print(f"⚠️ 找不到資料夾: {folder_path}，已略過...")
            continue
            
        dataset_id = FOLDER_TO_DATASET_ID.get(folder_name, 0)
        
        # 搜尋所有圖檔
        extensions = ['*.png', '*.jpg', '*.jpeg']
        image_files = []
        for ext in extensions:
            image_files.extend(glob.glob(os.path.join(folder_path, ext)))
            image_files.extend(glob.glob(os.path.join(folder_path, ext.upper())))
            
        print(f"\n📂 開始處理資料夾: {folder_name} (共 {len(image_files)} 張)")
        
        # 決定該資料夾圖片 ID 的起點
        current_image_id = START_IMAGE_ID_PER_FOLDER.get(folder_name, fallback_image_id)
        
        for img_path in sorted(image_files):
            file_name = os.path.basename(img_path)
            # COCO JSON 中要求的相對路徑格式
            coco_path = f"/datasets/{folder_name}/{file_name}"
            
            # 取得圖片對應的 ID 並遞增
            image_id = current_image_id
            current_image_id += 1
            if current_image_id > fallback_image_id:
                fallback_image_id = current_image_id
                
            # 取得圖片尺寸
            img_bgr = cv2.imread(img_path)
            if img_bgr is None:
                continue
            h, w, _ = img_bgr.shape
            
            # --- 建立 Image 區塊 ---
            image_obj = {
                "id": image_id,
                "dataset_id": dataset_id,
                "category_ids": [],
                "path": coco_path,
                "width": w,
                "height": h,
                "file_name": file_name,
                "annotated": False,
                "annotating": [],
                "num_annotations": 0,
                "metadata": {},
                "deleted": False,
                "milliseconds": 0,
                "events": [],
                "regenerate_thumbnail": False
            }
            
            # --- 進行 YOLO 推論 ---
            results = model(img_path, verbose=False)
            
            annotation_count = 0
            for result in results:
                if result.boxes is None or result.keypoints is None:
                    continue
                    
                # 若有多人則迭代 (如果是游泳池畫面通常為1人)
                for i in range(len(result.boxes)):
                    # 取出 Bounding Box
                    x1, y1, x2, y2 = result.boxes.xyxy[i].cpu().numpy()
                    bbox_w = x2 - x1
                    bbox_h = y2 - y1
                    # COCO bbox 格式: [top_left_x, top_left_y, w, h]
                    bbox = [round(float(x1), 1), round(float(y1), 1), round(float(bbox_w), 1), round(float(bbox_h), 1)]
                    
                    # 將 Bounding box 轉為矩形的 Segmentation Polygon
                    segmentation = [[
                        round(float(x2), 1), round(float(y1), 1),
                        round(float(x2), 1), round(float(y2), 1),
                        round(float(x1), 1), round(float(y2), 1),
                        round(float(x1), 1), round(float(y1), 1)
                    ]]
                    area = round(float(bbox_w * bbox_h), 1)
                    
                    # 取出 Keypoints
                    kpts = result.keypoints.data[i].cpu().numpy() # Shape: (7, 3), 也就是 [x, y, confidence]
                    coco_kpts = []
                    
                    for k in range(len(kpts)):
                        kx, ky, kconf = kpts[k]
                        # 依照需求，將所有輸出的關鍵點可見度強制標記為 2
                        visibility = 2
                        coco_kpts.extend([int(kx), int(ky), visibility])
                        
                    # 取得 Annotation ID
                    ann_id = current_ann_id
                    current_ann_id += 1
                        
                    # --- 建立 Annotation 區塊 ---
                    annotation_obj = {
                        "id": ann_id,
                        "image_id": image_id,
                        "category_id": 1,
                        "segmentation": segmentation,
                        "area": area,
                        "bbox": bbox,
                        "iscrowd": False,
                        "isbbox": True,
                        "color": "#bd291d",
                        "keypoints": coco_kpts,
                        "metadata": {},
                        "num_keypoints": len(kpts) # 等於 7
                    }
                    
                    coco_data["annotations"].append(annotation_obj)
                    annotation_count += 1
            
            # 更新 image 狀態
            image_obj["num_annotations"] = annotation_count
            if annotation_count > 0:
                image_obj["annotated"] = True
                image_obj["category_ids"] = [1]
            coco_data["images"].append(image_obj)
            
            # 印出目前進度
            print(f"  └ [進度] 處理完成 {file_name}，共偵測到 {annotation_count} 位游泳者")

        # 每個資料夾獨立存一份 JSON
        output_json_path = os.path.join(folder_path, 'coco_pose_results.json')
        with open(output_json_path, 'w', encoding='utf-8') as f:
            # 使用 json.dump 匯出，若希望美化版面可加上 indent=2 參數
            json.dump(coco_data, f, ensure_ascii=False)
            
        print(f"✅ {folder_name} 的 JSON 已經儲存到：{output_json_path}")

    print("\n🎉 所有資料夾的標註檔案皆已獨立儲存完畢！")

if __name__ == "__main__":
    main()
