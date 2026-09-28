import os
import json
import numpy as np
import pandas as pd
from scipy.interpolate import splprep, splev
from scipy.signal import find_peaks

def resample_curve(pts, n_points=100):
    dist = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    keep = np.insert(dist > 1e-5, 0, True)
    pts = pts[keep]
    if len(pts) < 4:
        return pts.tolist()
    try:
        tck, u = splprep([pts[:, 0], pts[:, 1]], s=0, k=min(3, len(pts)-1))
        u_new = np.linspace(0, 1, n_points)
        x_new, y_new = splev(u_new, tck)
        return np.column_stack((x_new, y_new)).tolist()
    except Exception as e:
        # Fallback to linear interpolation
        t_old = np.linspace(0, 1, len(pts))
        t_new = np.linspace(0, 1, n_points)
        x_new = np.interp(t_new, t_old, pts[:, 0])
        y_new = np.interp(t_new, t_old, pts[:, 1])
        return np.column_stack((x_new, y_new)).tolist()

def generate_demo():
    kp_file = r"E:\swimmer coco(validation)\kick_data(validation)\260527\real_time_picture (349)_50_keypoints.txt"
    dive_file = r"E:\swimmer coco(validation)\kick_data(validation)\260527\real_time_picture (349)_50_dive_info_angles.json"

    fps = 60.0
    total_frames = 3577

    # 1. Load dive angles
    with open(dive_file, "r") as f:
        dive_data = json.load(f)

    # 2. Load keypoints
    frames, col10, col11, col16, col17 = [], [], [], [], []
    with open(kp_file, "r") as f:
        for line in f:
            p = line.strip().split()
            if len(p) > 17:
                frames.append(int(p[0]))
                col10.append(float(p[10])) # sh_x
                col11.append(float(p[11])) # sh_y
                col16.append(float(p[16])) # wr_x
                col17.append(float(p[17])) # wr_y

    df = pd.DataFrame({
        "frame": frames,
        "sh_x": col10,
        "sh_y": col11,
        "wr_x": col16,
        "wr_y": col17
    })

    # Segment definitions from dive info
    # Lap 1: Dive 1036..1499, Swim 1500..2202 (decreasing, R->L)
    # Lap 2: Dive 2203..2507, Swim 2508..3480 (increasing, L->R)

    # Stroke entry peaks detection
    # Lap 1:
    sub1 = df[(df["frame"] >= 1500) & (df["frame"] <= 2202)].copy()
    sub1["rel_x"] = sub1["wr_x"] - sub1["sh_x"]
    sub1["rel_y"] = -(sub1["wr_y"] - sub1["sh_y"])
    sub1["smooth_x"] = sub1["rel_x"].rolling(15, center=True, min_periods=1).mean()
    peaks1, _ = find_peaks(-sub1["smooth_x"], distance=40, prominence=15)
    stroke_starts_1 = sub1.iloc[peaks1]["frame"].tolist()
    if stroke_starts_1[0] > 1520:
        stroke_starts_1.insert(0, 1505)
    stroke_starts_1.append(2200)

    # Lap 2:
    sub2 = df[(df["frame"] >= 2508) & (df["frame"] <= 3480)].copy()
    sub2["rel_x"] = sub2["wr_x"] - sub2["sh_x"]
    sub2["rel_y"] = -(sub2["wr_y"] - sub2["sh_y"])
    sub2["smooth_x"] = sub2["rel_x"].rolling(15, center=True, min_periods=1).mean()
    peaks2, _ = find_peaks(sub2["smooth_x"], distance=40, prominence=15)
    stroke_starts_2 = sub2.iloc[peaks2]["frame"].tolist()
    if stroke_starts_2[0] > 2520:
        stroke_starts_2.insert(0, 2510)
    stroke_starts_2.append(3475)

    def process_strokes(stroke_starts, lap_idx, is_decreasing):
        strokes = []
        for i in range(len(stroke_starts) - 1):
            s_f = stroke_starts[i]
            e_f = stroke_starts[i+1] - 1
            if e_f - s_f < 10:
                continue

            stroke_df = df[(df["frame"] >= s_f) & (df["frame"] <= e_f)]
            if len(stroke_df) < 5:
                continue

            # Swimming coordinate normalization:
            # Origin is Shoulder (0, 0)
            # Upward (toward water surface) is positive Y
            # Forward reach is positive X
            if is_decreasing:
                x_rel = -(stroke_df["wr_x"].values - stroke_df["sh_x"].values)
            else:
                x_rel = (stroke_df["wr_x"].values - stroke_df["sh_x"].values)
            y_rel = -(stroke_df["wr_y"].values - stroke_df["sh_y"].values)

            raw_pts = np.column_stack((x_rel, y_rel))
            smooth_100 = resample_curve(raw_pts, 100)

            raw_list = [
                {"x": round(float(x), 2), "y": round(float(y), 2), "frame": int(f)}
                for x, y, f in zip(x_rel, y_rel, stroke_df["frame"].values)
            ]

            strokes.append({
                "stroke_index": len(strokes) + 1,
                "stroke_name": f"Stroke {len(strokes) + 1}",
                "lap_index": lap_idx,
                "start_frame": int(s_f),
                "end_frame": int(e_f),
                "duration_frames": int(e_f - s_f + 1),
                "start_time_s": round(s_f / fps, 2),
                "end_time_s": round(e_f / fps, 2),
                "duration_s": round((e_f - s_f + 1) / fps, 2),
                "raw_points": raw_list,
                "smooth_points": [
                    {"x": round(float(pt[0]), 2), "y": round(float(pt[1]), 2)}
                    for pt in smooth_100
                ],
                "start_point": {"x": round(float(x_rel[0]), 2), "y": round(float(y_rel[0]), 2)},
                "end_point": {"x": round(float(x_rel[-1]), 2), "y": round(float(y_rel[-1]), 2)},
                "shoulder_point": {"x": 0.0, "y": 0.0}
            })
        return strokes

    strokes_lap1 = process_strokes(stroke_starts_1, 1, is_decreasing=True)
    strokes_lap2 = process_strokes(stroke_starts_2, 2, is_decreasing=False)

    print(f"Generated {len(strokes_lap1)} strokes for Lap 1, {len(strokes_lap2)} strokes for Lap 2.")

    # Build Waveform DataPoints for standard charts (Speed, Kick Angle, Wrist Y, Shoulder Y)
    def make_wrist_pts(sub, is_decreasing):
        pts = []
        for _, row in sub.iterrows():
            f = int(row["frame"])
            y_val = round(600.0 - row["wr_y"], 2) # waterline Y=600 normalization
            phase = "Pull"
            pts.append({
                "frame": f,
                "timestamp_ms": round((f / fps) * 1000, 1),
                "value": y_val,
                "phase": phase
            })
        return pts

    wrist_pts_lap1 = make_wrist_pts(sub1, True)
    wrist_pts_lap2 = make_wrist_pts(sub2, False)

    # Kick angle points
    def make_kick_pts(lap_data):
        kicks = lap_data.get("kicks", [])
        pts = []
        for k in kicks:
            f = k["frame"]
            ang = round(k["angle_deg"], 1)
            pts.append({
                "frame": f,
                "timestamp_ms": round((f / fps) * 1000, 1),
                "value": ang,
                "phase": "Kick"
            })
        pts.sort(key=lambda x: x["frame"])
        return pts

    kick_pts_lap1 = make_kick_pts(dive_data["laps"][0])
    kick_pts_lap2 = make_kick_pts(dive_data["laps"][1])

    # Assemble stroke_plot_figs
    stroke_plot_figs = {
        "lap1_decreasing_wrist": {
            "plot_type": "phase",
            "time_series": {
                "title": "Lap 1 Wrist Y",
                "data_points": wrist_pts_lap1,
                "metadata": {"reverse_axis": True}
            },
            "title": "Lap 1 Wrist Y"
        },
        "lap2_increasing_wrist": {
            "plot_type": "phase",
            "time_series": {
                "title": "Lap 2 Wrist Y",
                "data_points": wrist_pts_lap2,
                "metadata": {"reverse_axis": False}
            },
            "title": "Lap 2 Wrist Y"
        },
        # === 🎯 NEW: WRIST TRAJECTORY PLOTS ===
        "lap1_wrist_trajectory": {
            "plot_type": "trajectory",
            "time_series": {
                "title": "Lap 1 Wrist Trajectory",
                "data_points": [],
                "metadata": {
                    "lap_index": 1,
                    "strokes": strokes_lap1,
                    "total_strokes": len(strokes_lap1),
                    "fixed_origin": [0.0, 0.0]
                }
            },
            "title": "Lap 1 Wrist Trajectory"
        },
        "lap2_wrist_trajectory": {
            "plot_type": "trajectory",
            "time_series": {
                "title": "Lap 2 Wrist Trajectory",
                "data_points": [],
                "metadata": {
                    "lap_index": 2,
                    "strokes": strokes_lap2,
                    "total_strokes": len(strokes_lap2),
                    "fixed_origin": [0.0, 0.0]
                }
            },
            "title": "Lap 2 Wrist Trajectory"
        }
    }

    # Diving plot figs
    diving_plot_figs = {
        "lap1_kick_angle": {
            "plot_type": "angle",
            "time_series": {
                "title": "Lap 1 Kick Angle",
                "data_points": kick_pts_lap1,
                "metadata": {"reverse_axis": True}
            },
            "title": "Lap 1 Kick Angle"
        },
        "lap2_kick_angle": {
            "plot_type": "angle",
            "time_series": {
                "title": "Lap 2 Kick Angle",
                "data_points": kick_pts_lap2,
                "metadata": {"reverse_axis": False}
            },
            "title": "Lap 2 Kick Angle"
        }
    }

    # Full Result Object
    full_result = {
        "video_id": "real_time_picture_349",
        "processed_video_path": "data/processed_videos/real_time_picture(349).mp4",
        "stroke_style": "butterfly",
        "stroke_result": {
            "total_count": len(strokes_lap1) + len(strokes_lap2),
            "stroke_style": "butterfly",
            "range1_recovery_count": len(strokes_lap1),
            "range2_recovery_count": len(strokes_lap2),
            "stroke_frames": stroke_starts_1[:-1] + stroke_starts_2[:-1],
            "strokes_per_minute": round(((len(strokes_lap1) + len(strokes_lap2)) / (59.6 / 60)), 1),
            "average_stroke_duration_ms": 1350.0
        },
        "diving_analysis": {
            "segments": [[1036, 1499], [2203, 2507]],
            "touch_frame": 2202,
            "waterline_y": 600,
            "total_kick_count": len(kick_pts_lap1) + len(kick_pts_lap2),
            "kick_frequency": 2.2,
            "kick_angle_analysis": {
                "range1": {
                    "avg_angle": 126.5,
                    "max_angle": 158.9,
                    "min_angle": 79.0
                },
                "range2": {
                    "avg_angle": 113.8,
                    "max_angle": 158.6,
                    "min_angle": 2.6
                }
            }
        },
        "split_timing": {
            "splits": [18.4, 21.2],
            "average_speed": 1.28,
            "max_speed": 1.45,
            "min_speed": 1.10,
            "segments": [
                {"segment_id": 1, "start_frame": 1036, "end_frame": 2202, "duration_sec": 18.4, "avg_speed_m_per_sec": 1.36},
                {"segment_id": 2, "start_frame": 2203, "end_frame": 3480, "duration_sec": 21.2, "avg_speed_m_per_sec": 1.18}
            ]
        },
        "stroke_plot_figs": stroke_plot_figs,
        "diving_plot_figs": diving_plot_figs,
        "focus_crop_video_path": None,
        "timestamp": "2026-09-28T21:00:00",
        "analysis_duration_seconds": 45.2,
        "fps": 60.0
    }

    # Wrap in analysis_db schema
    demo_db_entry = {
        "real_time_picture_349": {
            "filename": "real_time_picture(349).mp4",
            "file_path": "data/processed_videos/real_time_picture(349).mp4",
            "status": "completed",
            "progress": 100,
            "error_message": None,
            "result": full_result,
            "current_step": "分析完成",
            "created_at": "2026-09-28T21:00:00",
            "completed_at": "2026-09-28T21:01:00"
        }
    }

    out_json = r"data\real_time_picture_349_analysis_result.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(demo_db_entry, f, indent=2, ensure_ascii=False)

    print(f"Saved demo analysis result to {out_json} successfully!")

if __name__ == "__main__":
    generate_demo()
