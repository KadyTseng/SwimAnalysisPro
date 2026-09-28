import os
import sys
import json
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from scipy.interpolate import splprep, splev, CubicSpline
from scipy.signal import savgol_filter, butter, filtfilt, medfilt
from scipy.ndimage import gaussian_filter1d
from scipy import optimize
from sklearn.decomposition import PCA

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# ================== 參數設定區 ==================
VIDEO_PATH = r"E:\swimmer coco(validation)\stroke_trajectory\real_time_picture (422)\real_time_picture (422).mp4"
base_name = "real_time_picture (422)"

OUTPUT_BASE_DIR = os.path.join(current_dir, "data", "processed_videos")
data_dir = os.path.join(current_dir, "data")
keypoints_txt = os.path.join(data_dir, "keypoints", f"{base_name}.txt")
phase_json_txt = os.path.join(data_dir, "Stroke_Phase_Frames", f"{base_name}_a.txt")
out_dir = os.path.dirname(VIDEO_PATH)

POSE_MODEL_PATH = os.path.join(current_dir, "data", "models", "best_1.pt")
STYLE_MODEL_PATH = os.path.join(current_dir, "data", "models", "svm_model_new_3.pkl")
if not os.path.exists(STYLE_MODEL_PATH):
    STYLE_MODEL_PATH = os.path.join(current_dir, "data", "models", "svm_model_v2.pkl")
FFMPEG_PATH = "ffmpeg"
# ================================================

# --- 11 Smoothing Methods ---

def smooth_fourier(x, y, keep_fraction=0.15):
    z = x + 1j * y
    Z = np.fft.fft(z)
    n = len(Z)
    keep_n = max(1, int(n * keep_fraction))
    Z_filtered = np.zeros_like(Z)
    Z_filtered[:keep_n] = Z[:keep_n]
    if keep_n > 1:
        Z_filtered[-keep_n+1:] = Z[-keep_n+1:]
    z_smooth = np.fft.ifft(Z_filtered)
    return z_smooth.real, z_smooth.imag

def smooth_pca(x, y, window=5):
    if len(x) < window: return x, y
    points = np.column_stack([x, y])
    pca = PCA(n_components=2)
    try:
        points_pca = pca.fit_transform(points)
        points_pca[:, 0] = pd.Series(points_pca[:, 0]).rolling(window, min_periods=1, center=True).mean().values
        points_pca[:, 1] = pd.Series(points_pca[:, 1]).rolling(window*2, min_periods=1, center=True).mean().values
        points_smooth = pca.inverse_transform(points_pca)
        return points_smooth[:, 0], points_smooth[:, 1]
    except:
        return x, y

def smooth_bspline(x, y, s=500.0):
    try:
        tck, u = splprep([x, y], s=s)
        unew = np.linspace(0, 1.0, len(x)*3)
        out = splev(unew, tck)
        return out[0], out[1]
    except:
        return x, y

def smooth_bezier(x, y):
    # 使用 CubicSpline 加上重度平滑模擬 Bezier
    try:
        t = np.linspace(0, 1, len(x))
        cs_x = CubicSpline(t, x)
        cs_y = CubicSpline(t, y)
        t_new = np.linspace(0, 1, len(x)*3)
        return gaussian_filter1d(cs_x(t_new), sigma=5), gaussian_filter1d(cs_y(t_new), sigma=5)
    except:
        return x, y

def smooth_spline_filter(x, y):
    try:
        t = np.linspace(0, 1, len(x))
        cs_x = CubicSpline(t, x)
        cs_y = CubicSpline(t, y)
        t_new = np.linspace(0, 1, len(x)*3)
        x_new = cs_x(t_new)
        y_new = cs_y(t_new)
        x_smooth = savgol_filter(x_new, min(15, len(x_new)), 3)
        y_smooth = savgol_filter(y_new, min(15, len(y_new)), 3)
        return x_smooth, y_smooth
    except:
        return x, y

def smooth_savgol(x, y, window=11, poly=3):
    window = min(window, len(x)-1 if len(x)%2==0 else len(x))
    if window < poly + 1: window = poly + 1
    if window % 2 == 0: window += 1
    if window < poly + 1: return x, y
    return savgol_filter(x, window, poly), savgol_filter(y, window, poly)

def smooth_gaussian(x, y, sigma=3):
    return gaussian_filter1d(x, sigma), gaussian_filter1d(y, sigma)

def smooth_butterworth(x, y, cutoff=0.15, order=2):
    b, a = butter(order, cutoff, btype='low', analog=False)
    try:
        if len(x) > 15:
            x_s = filtfilt(b, a, x)
            y_s = filtfilt(b, a, y)
            return x_s, y_s
        else:
            return x, y
    except:
        return x, y

def smooth_med_ma(x, y, med_k=3, ma_k=5):
    if len(x) < max(med_k, ma_k): return x, y
    x_m = medfilt(x, kernel_size=med_k)
    y_m = medfilt(y, kernel_size=med_k)
    x_s = pd.Series(x_m).rolling(ma_k, center=True, min_periods=1).mean().values
    y_s = pd.Series(y_m).rolling(ma_k, center=True, min_periods=1).mean().values
    return x_s, y_s

def smooth_kalman(x, y):
    dt = 1.0
    F = np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]])
    H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
    R = np.eye(2) * 5.0
    Q = np.eye(4) * 0.5
    
    n = len(x)
    state = np.zeros((4, 1))
    state[0, 0] = x[0]
    state[1, 0] = y[0]
    P = np.eye(4) * 100
    
    sx, sy = [], []
    for i in range(n):
        state = F @ state
        P = F @ P @ F.T + Q
        z = np.array([[x[i]], [y[i]]])
        y_res = z - H @ state
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        state = state + K @ y_res
        P = (np.eye(4) - K @ H) @ P
        sx.append(state[0, 0])
        sy.append(state[1, 0])
        
    # Backward pass for zero-phase smoothing
    state = np.zeros((4, 1))
    state[0, 0] = x[-1]
    state[1, 0] = y[-1]
    P = np.eye(4) * 100
    sx_b, sy_b = [], []
    for i in range(n-1, -1, -1):
        state = F @ state
        P = F @ P @ F.T + Q
        z = np.array([[x[i]], [y[i]]])
        y_res = z - H @ state
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        state = state + K @ y_res
        P = (np.eye(4) - K @ H) @ P
        sx_b.append(state[0, 0])
        sy_b.append(state[1, 0])
    sx_b.reverse()
    sy_b.reverse()
    
    # Average forward and backward
    return (np.array(sx) + np.array(sx_b))/2, (np.array(sy) + np.array(sy_b))/2

def smooth_ema(x, y, alpha=0.3):
    x_s = pd.Series(x).ewm(alpha=alpha, adjust=False).mean().values
    y_s = pd.Series(y).ewm(alpha=alpha, adjust=False).mean().values
    x_s = pd.Series(x_s[::-1]).ewm(alpha=alpha, adjust=False).mean().values[::-1]
    y_s = pd.Series(y_s[::-1]).ewm(alpha=alpha, adjust=False).mean().values[::-1]
    return x_s, y_s

def smooth_circle_fit(x, y):
    def calc_R(xc, yc):
        return np.sqrt((x-xc)**2 + (y-yc)**2)
    def f_2(c):
        Ri = calc_R(*c)
        return Ri - Ri.mean()
    
    try:
        center_estimate = np.mean(x), np.mean(y)
        xc, yc = optimize.leastsq(f_2, center_estimate)[0]
        R = calc_R(xc, yc).mean()
        
        angles = np.unwrap(np.arctan2(y - yc, x - xc))
        t = np.linspace(0, 1, len(angles))
        cs_angles = CubicSpline(t, angles)
        angles_new = cs_angles(np.linspace(0, 1, len(x)*3))
        
        return xc + R*np.cos(angles_new), yc + R*np.sin(angles_new)
    except:
        return x, y

def smooth_ellipse_fit(x, y):
    def residual(params):
        x0, y0, a, b, angle = params
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        xc = x - x0
        yc = y - y0
        x_rot = xc * cos_a + yc * sin_a
        y_rot = -xc * sin_a + yc * cos_a
        return (x_rot/a)**2 + (y_rot/b)**2 - 1.0

    try:
        x0_est = np.mean(x)
        y0_est = np.mean(y)
        a_est = np.max([np.std(x), 1.0])
        b_est = np.max([np.std(y), 1.0])
        angle_est = 0.0
        
        res = optimize.least_squares(residual, [x0_est, y0_est, a_est, b_est, angle_est])
        x0, y0, a, b, angle = res.x
        a, b = abs(a), abs(b)
        
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        xc = x - x0
        yc = y - y0
        x_rot = xc * cos_a + yc * sin_a
        y_rot = -xc * sin_a + yc * cos_a
        
        angles = np.unwrap(np.arctan2(y_rot * a, x_rot * b))
        t = np.linspace(0, 1, len(angles))
        cs_angles = CubicSpline(t, angles)
        angles_new = cs_angles(np.linspace(0, 1, len(x)*3))
        
        x_ell = a * np.cos(angles_new)
        y_ell = b * np.sin(angles_new)
        
        x_fit = x0 + x_ell * cos_a - y_ell * sin_a
        y_fit = y0 + x_ell * sin_a + y_ell * cos_a
        return x_fit, y_fit
    except:
        return x, y

METHODS = {
    "Fourier": smooth_fourier,
    "PCA": smooth_pca,
    "B-Spline": smooth_bspline,
    "Bezier": smooth_bezier,
    "Spline_Filter": smooth_spline_filter,
    "Savitzky-Golay": smooth_savgol,
    "Gaussian": smooth_gaussian,
    "Butterworth": smooth_butterworth,
    "Med_MA": smooth_med_ma,
    "Kalman": smooth_kalman,
    "EMA": smooth_ema,
    "Circle_Fit": smooth_circle_fit,
    "Ellipse_Fit": smooth_ellipse_fit
}

# --- Main Logic ---

def process_and_plot():
    os.makedirs(out_dir, exist_ok=True)
    
    if not os.path.exists(keypoints_txt) or not os.path.exists(phase_json_txt):
        logging.error("找不到骨架或相位資料，請先執行分析取得 txt 檔！")
        return
            
    # Read Keypoints
    frame_data = {}
    with open(keypoints_txt, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) > 17:
                try:
                    f_idx = int(parts[0])
                    col10, col11 = float(parts[10]), float(parts[11]) # Shoulder
                    col16, col17 = float(parts[16]), float(parts[17]) # Wrist
                    rel_x = col16 - col10
                    rel_y = col17 - col11
                    frame_data[f_idx] = (rel_x, rel_y)
                except: pass

    # Read Phase
    with open(phase_json_txt, "r") as f:
        regions_data = json.load(f)

    pull_starts_info = []
    for lap_key, lap_data in regions_data.items():
        if isinstance(lap_data, dict):
            pulls = lap_data.get("Pull regions", [])
            for p in pulls:
                pull_starts_info.append(p[0])
    pull_starts_info.sort()

    if len(pull_starts_info) == 0:
        logging.warning("No Pull regions found.")
        return

    max_frame = max(frame_data.keys()) if frame_data else 0
    
    for i in range(len(pull_starts_info)):
        start_f = pull_starts_info[i]
        end_f = pull_starts_info[i+1]-1 if i < len(pull_starts_info)-1 else max_frame
        
        frames, vals_x, vals_y = [], [], []
        for f_idx in range(start_f, end_f + 1):
            if f_idx in frame_data:
                frames.append(f_idx)
                vals_x.append(frame_data[f_idx][0])
                vals_y.append(frame_data[f_idx][1])
                
        if len(frames) < 10: continue
        
        vals_x = np.array(vals_x)
        vals_y = np.array(vals_y)
        
        # 儲存原始資料
        raw_csv_file = os.path.join(out_dir, f"stroke_{i+1}_Raw.csv")
        pd.DataFrame({"Frame": frames, "X_Raw": vals_x, "Y_Raw": vals_y}).to_csv(raw_csv_file, index=False)
        
        for method_name, method_func in METHODS.items():
            sx, sy = method_func(vals_x.copy(), vals_y.copy())
            
            plt.figure(figsize=(8, 8))
            # 原始軌跡 (淺色)
            plt.plot(vals_x, vals_y, marker='o', markersize=3, color='gray', linewidth=1, alpha=0.3, label="Raw")
            # 平滑軌跡
            plt.plot(sx, sy, marker='none', color='b', linewidth=2.5, label=f"Smoothed ({method_name})")
            
            # 起點終點
            plt.scatter([sx[0]], [sy[0]], color='green', marker='o', s=100, label="Start", zorder=6)
            plt.scatter([sx[-1]], [sy[-1]], color='purple', marker='s', s=100, label="End", zorder=6)
            plt.scatter([0], [0], color='r', marker='X', s=150, label="Shoulder", zorder=5)
            
            plt.title(f"Stroke {i+1} | {method_name}")
            plt.xlabel("Wrist X (Pixels)")
            plt.ylabel("Wrist Y (Pixels)")
            plt.gca().invert_yaxis()
            plt.axis('equal')
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            out_file = os.path.join(out_dir, f"stroke_{i+1}_{method_name}.png")
            plt.savefig(out_file, dpi=150)
            plt.close()
            
            # 儲存平滑後的軌跡資料
            csv_file = os.path.join(out_dir, f"stroke_{i+1}_{method_name}.csv")
            pd.DataFrame({"X_Smoothed": sx, "Y_Smoothed": sy}).to_csv(csv_file, index=False)
            
    logging.info(f"🎉 測試完畢，圖片與 CSV 資料已儲存至: {out_dir}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
    process_and_plot()
