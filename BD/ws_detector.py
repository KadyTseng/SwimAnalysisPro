import cv2
import numpy as np
import time

class ScanningAreaDetector:
    def __init__(self, alpha=0.8, threshold=1.2, consecutive_frames=1, reset_delay=1.2):
        self.avg_background = None
        self.alpha = alpha 
        self.threshold = threshold 
        self.consecutive_frames = consecutive_frames 
        self.counter = 0 
        self.reset_delay = reset_delay 
        self.triggered_time = None 
        self.is_locked = False 

    def update_and_detect(self, roi):
        if roi is None or roi.size == 0: return False, 0
        current_time = time.time()
        if self.is_locked:
            if current_time - self.triggered_time >= self.reset_delay:
                self.reset_state()
                return False, 0
            else:
                return True, 0

        # --- 使用灰階亮度，避免色偏問題 ---
        if len(roi.shape) == 3:
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype("float32")
        else:
            gray_roi = roi.astype("float32")
            
        if self.avg_background is None:
            self.avg_background = gray_roi.copy()
            return False, 0

        # 背景累積與差異計算
        cv2.accumulateWeighted(gray_roi, self.avg_background, self.alpha)
        diff = cv2.absdiff(gray_roi.astype("uint8"), self.avg_background.astype("uint8"))
        
        mean_val, _ = cv2.meanStdDev(diff)
        score = mean_val[0][0]
        
        if score > self.threshold: self.counter += 1
        else: self.counter = max(0, self.counter - 30) 
        
        if self.counter >= self.consecutive_frames:
            self.is_locked = True
            self.triggered_time = current_time
            return True, score
        return False, score

    def reset_state(self):
        self.counter = 0
        self.is_locked = False
        self.triggered_time = None
        self.avg_background = None
