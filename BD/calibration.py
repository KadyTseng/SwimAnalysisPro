import os
import glob
import re
import numpy as np

def get_pixel_for_distance(target_m, calibration_dir=r"E:\2025_CATS\碩論\pixel_to_distance\resize"):
    """
    動態讀取校正資料夾內的檔案，計算對應距離的 pixel X 座標。
    檔名格式例如：距離測量_15_1551.png
    若 target_m == 50.0，視為回程游回 0m 處。
    """
    # 50m 相當於游回 0m 處
    if target_m == 50.0:
        target_m = 0.0
        
    # 0m 的特別處理 (使用者提供：3748)
    if target_m == 0.0:
        return 3748.0
        
    mapping = []
    
    # 掃描資料夾
    if os.path.exists(calibration_dir):
        files = glob.glob(os.path.join(calibration_dir, "*.png"))
        for f in files:
            name = os.path.basename(f)
            # 匹配 距離測量_距離_pixel.png
            match = re.match(r'距離測量_([0-9\.]+)_([0-9]+)\.png', name)
            if match:
                dist = float(match.group(1))
                px = int(match.group(2))
                mapping.append((dist, px))
                
    if not mapping:
        # Fallback to hardcoded values extracted previously if folder not found/empty
        mapping = [
            (1.0, 3587), (2.0, 3451), (3.0, 3317), (3.125, 3307), (4.0, 3189),
            (5.0, 3045), (6.0, 2897), (6.25, 2841), (7.0, 2725), (8.0, 2583),
            (9.0, 2429), (9.375, 2373), (10.0, 2295), (11.0, 2153), (12.0, 2017),
            (12.5, 1915), (13.0, 1829), (14.0, 1697), (15.0, 1551), (15.625, 1457),
            (16.0, 1413), (17.0, 1271), (18.0, 1131), (18.75, 1007), (19.0, 973),
            (20.0, 825), (21.0, 687), (21.875, 557), (22.0, 549), (23.0, 413),
            (24.0, 287), (25.0, 136)
        ]
        
    # 加入 0m = 3748
    mapping.append((0.0, 3748))
    
    # 確保資料中沒有重複的 x (距離) 值以免 np.interp 混淆，並依距離排序
    # 若有重複的距離，以第一筆為主
    unique_mapping = {}
    for d, p in mapping:
        if d not in unique_mapping:
            unique_mapping[d] = p
            
    sorted_mapping = sorted(unique_mapping.items(), key=lambda x: x[0])
    
    distances = np.array([m[0] for m in sorted_mapping])
    pixels = np.array([m[1] for m in sorted_mapping])
    
    # 使用 numpy.interp 進行線性插值 (np.interp 預期 x 是遞增的)
    target_px = np.interp(target_m, distances, pixels)
    
    # 如果傳入的是單一數值則回傳 float，否則回傳 array
    return float(target_px) if isinstance(target_m, (int, float)) else target_px

def get_distance_for_pixel(target_px, calibration_dir=r"E:\2025_CATS\碩論\pixel_to_distance\resize"):
    """
    動態讀取校正資料夾內的檔案，計算對應 pixel 的實際距離 (m)。
    支援傳入單一數值或 numpy array。
    """
    mapping = []
    
    if os.path.exists(calibration_dir):
        files = glob.glob(os.path.join(calibration_dir, "*.png"))
        for f in files:
            name = os.path.basename(f)
            match = re.match(r'距離測量_([0-9\.]+)_([0-9]+)\.png', name)
            if match:
                dist = float(match.group(1))
                px = float(match.group(2))
                mapping.append((dist, px))
                
    if not mapping:
        mapping = [
            (1.0, 3587), (2.0, 3451), (3.0, 3317), (3.125, 3307), (4.0, 3189),
            (5.0, 3045), (6.0, 2897), (6.25, 2841), (7.0, 2725), (8.0, 2583),
            (9.0, 2429), (9.375, 2373), (10.0, 2295), (11.0, 2153), (12.0, 2017),
            (12.5, 1915), (13.0, 1829), (14.0, 1697), (15.0, 1551), (15.625, 1457),
            (16.0, 1413), (17.0, 1271), (18.0, 1131), (18.75, 1007), (19.0, 973),
            (20.0, 825), (21.0, 687), (21.875, 557), (22.0, 549), (23.0, 413),
            (24.0, 287), (25.0, 136)
        ]
        
    mapping.append((0.0, 3748.0))
    
    unique_mapping = {}
    for d, p in mapping:
        if p not in unique_mapping:
            unique_mapping[p] = d
            
    # 對 pixel 進行升冪排序 (因為 np.interp 需要 xp 嚴格遞增)
    sorted_mapping = sorted(unique_mapping.items(), key=lambda x: x[0])
    
    pixels = np.array([m[0] for m in sorted_mapping])
    distances = np.array([m[1] for m in sorted_mapping])
    
    target_dist = np.interp(target_px, pixels, distances)
    
    return float(target_dist) if isinstance(target_px, (int, float)) else target_dist

def get_distance_between_pixels(px1, px2, calibration_dir=r"E:\2025_CATS\碩論\pixel_to_distance\resize"):
    """
    計算兩個 Pixel 之間的實際距離 (絕對值)
    """
    dist1 = get_distance_for_pixel(px1, calibration_dir)
    dist2 = get_distance_for_pixel(px2, calibration_dir)
    return abs(dist1 - dist2)

if __name__ == "__main__":
    # Test script
    print("0m pixel:", get_pixel_for_distance(0.0))
    print("15m pixel:", get_pixel_for_distance(15.0))
    print("25m pixel:", get_pixel_for_distance(25.0))
    print("Distance for 3587 px:", get_distance_for_pixel(3587))
    print("Distance between 3748 and 136:", get_distance_between_pixels(3748, 136))
