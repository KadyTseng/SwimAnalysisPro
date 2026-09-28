"""
Enhanced Arm Trajectory Plotter with:
- Wrist-only visualization (no elbow/shoulder)
- Dual-axis display (distance + time)
- Recovery phase indicators for lap2
- Segmented stroke phase visualization
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import os
from typing import Dict, List, Tuple, Optional


def extract_recovery_regions_from_phase_dict(phase_dict: Dict) -> List[Tuple[int, int]]:
    """
    Extract recovery regions from phase analysis results.
    Phase dict typically contains keys like 'lap1_down', 'lap2_up' with recovery_regions lists.
    """
    recovery_regions = []
    for key, phase_data in phase_dict.items():
        if isinstance(phase_data, dict) and "recovery_regions" in phase_data:
            recovery_regions.extend(phase_data["recovery_regions"])
    return sorted(recovery_regions)


def plot_wrist_trajectory_with_dual_axis(
    df_clean,
    laps_data,
    waterline_y,
    output_dir: str,
    fps: float = 30.0,
    pool_length: float = 25.0,
    phase_frames_dict: Optional[Dict] = None,
    cm_per_pixel: float = 1.0,
):
    """
    Plot wrist trajectory with:
    - Distance (m) and Time (s) on x-axis (dual axis)
    - Remove elbow/shoulder traces
    - Add recovery phase dashed lines for lap2

    Parameters:
    -----------
    df_clean : DataFrame
        Cleaned keypoint data with frame_id, wrist_x, wrist_y, etc.
    laps_data : List[Dict]
        Lap information with swimming_segment data
    waterline_y : float
        Waterline y-coordinate in pixel space
    output_dir : str
        Directory to save plots
    fps : float
        Frames per second (default 30)
    pool_length : float
        Pool length in meters (default 25m)
    phase_frames_dict : Dict, optional
        Phase analysis results containing recovery information
    cm_per_pixel : float
        Conversion factor for depth scaling
    m_per_pixel_x : float
        Conversion factor for horizontal distance
    """

    os.makedirs(output_dir, exist_ok=True)
    extract_recovery_regions = phase_frames_dict or {}

    # Process each lap's swimming segment
    for lap in laps_data:
        if lap.get("swimming_segment") is None:
            continue

        lap_index = lap.get("lap_index", 0)
        s_swim, e_swim = lap["swimming_segment"]
        trend = lap.get("trend", "unknown")

        # Extract swimming segment data
        df_swim = df_clean[
            (df_clean["frame_id"] >= s_swim) & (df_clean["frame_id"] <= e_swim)
        ]

        if df_swim.empty:
            continue

        # Prepare wrist trajectory data
        frames = df_swim["frame_id"].tolist()
        frame_times = [(f - frames[0]) / fps for f in frames]  # Time in seconds

        # Wrist coordinates (already height-normalized in arm_trajectory_analyzer)
        wrist_x_pixels = df_swim["wrist_x"].tolist()
        wrist_y_normalized = [
            (waterline_y - y) * cm_per_pixel for y in df_swim["wrist_y"].tolist()
        ]

        # Distance in meters (actual horizontal position relative to first frame)
        wrist_x_start = wrist_x_pixels[0]
        
        from BD.calibration import get_distance_between_pixels
        raw_dist_m = [get_distance_between_pixels(x, wrist_x_start) for x in wrist_x_pixels]

        # Normalize orientation: always show increasing progress from 0
        # If swimmer moves right-to-left, invert axis so it still increases
        if raw_dist_m[-1] < raw_dist_m[0]:
            distances_m = [raw_dist_m[0] - d for d in raw_dist_m]
        else:
            distances_m = [d - raw_dist_m[0] for d in raw_dist_m]

        # Make distance monotonic (forward movement) using cumulative sum of absolute differences
        cum_dist_m = [0.0]
        for i in range(1, len(distances_m)):
            cum_dist_m.append(cum_dist_m[-1] + abs(distances_m[i] - distances_m[i - 1]))

        distances_m = cum_dist_m
        x_min, x_max = 0.0, max(distances_m) if distances_m else pool_length

        # Create figure with twin axes
        fig, ax1 = plt.subplots(figsize=(14, 6))

        # Plot wrist trajectory
        ax1.plot(
            distances_m,
            wrist_y_normalized,
            "b-",
            linewidth=2.5,
            label="Wrist Trajectory",
        )
        ax1.axhline(
            y=0,
            color="cyan",
            linestyle="--",
            linewidth=1.5,
            label="Waterline (0 cm)",
        )
        ax1.set_xlabel("Distance (m)", fontsize=12, fontweight="bold")
        ax1.set_ylabel("Depth (cm)", fontsize=12, fontweight="bold")
        ax1.set_ylim(-160, 160)
        ax1.set_xlim(x_min, x_max)
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis="x", labelsize=10)
        ax1.tick_params(axis="y", labelsize=10)

        # Create twin axis for time
        ax1_time = ax1.twiny()

        # CORRECT MAPPING: Create time-to-distance mapping based on actual frame data
        # Build a lookup: for each frame, what distance corresponds to it?
        frame_to_distance = {fr: dist for fr, dist in zip(frames, distances_m)}

        # Create evenly-spaced time ticks, then find their corresponding distances
        time_ticks_frames = np.linspace(0, len(frames) - 1, 7)  # 7 ticks
        time_values_sec = [
            frames[int(fr)] / fps if int(fr) < len(frames) else frames[-1] / fps
            for fr in time_ticks_frames
        ]

        # Get corresponding distances for these time points
        distance_positions = [
            (
                frame_to_distance[frames[int(fr)]]
                if int(fr) < len(frames)
                else distances_m[-1]
            )
            for fr in time_ticks_frames
        ]

        # Set the time axis to match the same xlim as distance axis
        ax1_time.set_xlim(ax1.get_xlim())

        # Place time ticks at their correct distance positions
        ax1_time.set_xticks(distance_positions)
        time_labels = [
            (
                f"{frames[int(fr)] / fps:.1f}s"
                if int(fr) < len(frames)
                else f"{frames[-1] / fps:.1f}s"
            )
            for fr in time_ticks_frames
        ]
        ax1_time.set_xticklabels(time_labels, fontsize=10)
        ax1_time.set_xlabel("Time (s)", fontsize=12, fontweight="bold", color="red")
        ax1_time.tick_params(axis="x", labelcolor="red")

        # Add recovery phase visualization for lap2
        if lap_index == 2 and phase_frames_dict:
            recovery_key = f"lap{lap_index}_{trend}"
            recovery_drawn = False

            if recovery_key in phase_frames_dict:
                phase_data = phase_frames_dict[recovery_key]
                if isinstance(phase_data, dict) and "recovery_regions" in phase_data:
                    for rec_start, rec_end in phase_data["recovery_regions"]:
                        # Convert frame numbers to distances
                        try:
                            rec_start_idx = frames.index(rec_start)
                            rec_end_idx = frames.index(rec_end)
                            rec_start_dist = distances_m[rec_start_idx]
                            rec_end_dist = distances_m[rec_end_idx]

                            # Draw recovery phase as dashed vertical lines
                            ax1.axvline(
                                x=rec_start_dist,
                                color="red",
                                linestyle="--",
                                linewidth=2,
                                alpha=0.7,
                                label="Recovery (start)" if not recovery_drawn else "",
                            )
                            ax1.axvline(
                                x=rec_end_dist,
                                color="red",
                                linestyle="--",
                                linewidth=2,
                                alpha=0.7,
                                label="Recovery (end)" if not recovery_drawn else "",
                            )
                            recovery_drawn = True
                        except ValueError:
                            # Frame not in this segment, skip
                            continue

        # Add title and legend
        title = f"Wrist Trajectory - Lap {lap_index} ({trend.capitalize()})"
        ax1.set_title(title, fontsize=14, fontweight="bold", pad=20)

        # Custom legend (avoid duplicate labels)
        handles, labels = ax1.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax1.legend(by_label.values(), by_label.keys(), loc="upper left", fontsize=10)

        plt.tight_layout()

        # Save figure
        output_path = os.path.join(
            output_dir, f"3_swimming_arm_trajectory_lap{lap_index}_enhanced.png"
        )
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()

        # Save time-aligned data and recovery mapping
        recovery_list = []
        if lap_index == 2 and phase_frames_dict:
            recovery_key = f"lap{lap_index}_{trend}"
            if recovery_key in phase_frames_dict:
                phase_data = phase_frames_dict[recovery_key]
                if isinstance(phase_data, dict) and "recovery_regions" in phase_data:
                    for rec_start, rec_end in phase_data["recovery_regions"]:
                        try:
                            rec_start_idx = frames.index(rec_start)
                            rec_end_idx = frames.index(rec_end)
                        except ValueError:
                            continue
                        recovery_list.append(
                            {
                                "frame_start": rec_start,
                                "frame_end": rec_end,
                                "time_start_s": (rec_start - frames[0]) / fps,
                                "time_end_s": (rec_end - frames[0]) / fps,
                                "distance_start_m": distances_m[rec_start_idx],
                                "distance_end_m": distances_m[rec_end_idx],
                            }
                        )

        json_output = {
            "lap_index": lap_index,
            "trend": trend,
            "start_frame": frames[0],
            "end_frame": frames[-1],
            "frames": frames,
            "times_s": frame_times,
            "distances_m": distances_m,
            "wrist_y_cm": wrist_y_normalized,
            "recovery_regions": recovery_list,
        }

        json_path = os.path.join(
            output_dir, f"3_swimming_arm_trajectory_lap{lap_index}_enhanced.json"
        )
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(json_output, jf, ensure_ascii=False, indent=2)

        print(f"✅ Generated enhanced plot: {output_path}")
        print(f"✅ Saved plot data: {json_path}")


def plot_wrist_relative_to_shoulder(
    df_clean,
    laps_data,
    waterline_y,
    output_dir: str,
    fps: float = 30.0,
    phase_frames_dict: Optional[Dict] = None,
    cm_per_pixel: float = 1.0,
):
    """
    Plot wrist trajectory RELATIVE TO SHOULDER (shoulder as origin).
    Shows arm motion relative to shoulder position.

    Parameters:
    -----------
    df_clean : DataFrame
        Cleaned keypoint data with frame_id, wrist_x, wrist_y, shoulder_x, shoulder_y
    laps_data : List[Dict]
        Lap information with swimming_segment data
    waterline_y : float
        Waterline y-coordinate in pixel space
    output_dir : str
        Directory to save plots
    fps : float
        Frames per second (default 30)
    phase_frames_dict : Dict, optional
        Phase analysis results containing recovery information
    cm_per_pixel : float
        Conversion factor for depth scaling
    """

    os.makedirs(output_dir, exist_ok=True)

    # Process each lap's swimming segment
    for lap in laps_data:
        if lap.get("swimming_segment") is None:
            continue

        lap_index = lap.get("lap_index", 0)
        s_swim, e_swim = lap["swimming_segment"]
        trend = lap.get("trend", "unknown")

        # Extract swimming segment data
        df_swim = df_clean[
            (df_clean["frame_id"] >= s_swim) & (df_clean["frame_id"] <= e_swim)
        ]

        if df_swim.empty:
            continue

        # Prepare data
        frames = df_swim["frame_id"].tolist()
        frame_times = [(f - frames[0]) / fps for f in frames]

        # Get wrist and shoulder coordinates
        wrist_x_pixels = df_swim["wrist_x"].tolist()
        wrist_y_pixels = df_swim["wrist_y"].tolist()
        shoulder_x_pixels = df_swim["shoulder_x"].tolist()
        shoulder_y_pixels = df_swim["shoulder_y"].tolist()

        # Calculate relative coordinates (wrist - shoulder)
        wrist_rel_x = [
            wrist_x_pixels[i] - shoulder_x_pixels[i] for i in range(len(frames))
        ]
        wrist_rel_y = [
            (waterline_y - wrist_y_pixels[i]) * cm_per_pixel
            - (waterline_y - shoulder_y_pixels[i]) * cm_per_pixel
            for i in range(len(frames))
        ]

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 8))

        # Plot wrist motion relative to shoulder
        ax.plot(
            wrist_rel_x,
            wrist_rel_y,
            "b-",
            linewidth=2.5,
            label="Wrist (relative to Shoulder)",
            marker="o",
            markersize=2,
            alpha=0.7,
        )

        # Mark start and end
        ax.plot(wrist_rel_x[0], wrist_rel_y[0], "go", markersize=10, label="Start")
        ax.plot(wrist_rel_x[-1], wrist_rel_y[-1], "ro", markersize=10, label="End")

        # Add shoulder at origin
        ax.plot(0, 0, "k+", markersize=15, markeredgewidth=2, label="Shoulder (Origin)")
        ax.axhline(y=0, color="gray", linestyle="-", linewidth=0.5, alpha=0.3)
        ax.axvline(x=0, color="gray", linestyle="-", linewidth=0.5, alpha=0.3)

        # Add recovery phase coloring for lap2
        if lap_index == 2 and phase_frames_dict:
            recovery_key = f"lap{lap_index}_{trend}"
            if recovery_key in phase_frames_dict:
                phase_data = phase_frames_dict[recovery_key]
                if isinstance(phase_data, dict) and "recovery_regions" in phase_data:
                    for rec_start, rec_end in phase_data["recovery_regions"]:
                        try:
                            rec_start_idx = frames.index(rec_start)
                            rec_end_idx = frames.index(rec_end)

                            # Highlight recovery segment
                            ax.plot(
                                wrist_rel_x[rec_start_idx : rec_end_idx + 1],
                                wrist_rel_y[rec_start_idx : rec_end_idx + 1],
                                "r-",
                                linewidth=4,
                                alpha=0.5,
                                label="Recovery Phase",
                            )
                        except ValueError:
                            continue

        ax.set_xlabel(
            "Wrist X relative to Shoulder (pixels)", fontsize=12, fontweight="bold"
        )
        ax.set_ylabel(
            "Wrist Depth relative to Shoulder (cm)", fontsize=12, fontweight="bold"
        )
        ax.set_title(
            f"Wrist Motion Relative to Shoulder - Lap {lap_index} ({trend.capitalize()})",
            fontsize=14,
            fontweight="bold",
            pad=20,
        )
        ax.grid(True, alpha=0.3)
        ax.set_aspect("equal", adjustable="box")

        # Legend
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc="upper left", fontsize=10)

        plt.tight_layout()

        # Save figure
        output_path = os.path.join(
            output_dir, f"4_wrist_relative_to_shoulder_lap{lap_index}.png"
        )
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"✅ Generated relative motion plot: {output_path}")
