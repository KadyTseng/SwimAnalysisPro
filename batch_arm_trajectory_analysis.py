"""
Batch Processing Script for ARM Trajectory Analysis
====================================================

Usage:
    1. Set VIDEO_FOLDER and OUTPUT_FOLDER in the configuration below
    2. Place your 3 MP4 videos in VIDEO_FOLDER
    3. Run: python batch_arm_trajectory_analysis.py

The script will:
- Run full analysis on each video
- Generate enhanced arm trajectory plots (wrist-only)
- Display dual-axis (distance + time)
- Mark recovery phases on lap2
"""

import os
import sys
import logging
from pathlib import Path
from typing import List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

from BD.orchestrator import run_full_analysis
from enhanced_arm_trajectory_plotter import (
    plot_wrist_trajectory_with_dual_axis,
    plot_wrist_relative_to_shoulder,
)

# ============================================================================
# ⚙️ CONFIGURATION - MODIFY THESE PATHS FOR YOUR VIDEOS
# ============================================================================

# 📁 OPTION 1: Specify individual video paths (recommended for videos in different locations)
VIDEO_PATHS = [
    r"E:\Swimmer Records\Mixed_Video_Pool\All_Folder\Excellent Recording\breaststroke\Excellent_20230414_breaststroke_M_3 (10).mp4",
    r"E:\Swimmer Records\New Records\260107\Excellent_20260107_backstroke_M_3(1).mp4",
    r"E:\Swimmer Records\New Records\260120\Excellent_20260120_freestyle_M_3(3).mp4",
]

# 📁 OPTION 2: Or use a folder if all videos are in one place (leave empty if using VIDEO_PATHS)
VIDEO_FOLDER = r""  # Leave empty to use VIDEO_PATHS above

# 📁 Where to save output plots
OUTPUT_FOLDER = (
    r"d:\Kady\Pool_UI_processed\SwimAnalysisPro\test_outputs\batch_arm_trajectory"
)

# 🤖 Model paths
POSE_MODEL_PATH = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\best_1.pt"
STYLE_MODEL_PATH = (
    r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\svm_model_new_3.pkl"
)
FFMPEG_EXECUTABLE_PATH = r"C:\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe"

# 📊 Processing parameters
POOL_LENGTH = 25.0  # meters (standard 25m pool)
CM_PER_PIXEL = 1.0  # Depth scaling (adjust if needed)

# ============================================================================
# Create output folder first, then setup logging
# ============================================================================
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(OUTPUT_FOLDER, "batch_processing.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def find_video_files(video_paths_list: List[str], video_folder: str = "") -> List[str]:
    """
    Find video files. Priority:
    1. Use VIDEO_PATHS list if provided
    2. Otherwise scan VIDEO_FOLDER
    """
    if video_paths_list and any(video_paths_list):
        # Use explicit video paths
        valid_videos = []
        for video_path in video_paths_list:
            if not video_path.strip():
                continue
            video_path = video_path.strip()
            if os.path.exists(video_path):
                valid_videos.append(video_path)
                logger.info(f"   ✅ Found: {Path(video_path).name}")
            else:
                logger.warning(f"   ⚠️ Not found: {video_path}")

        if not valid_videos:
            logger.error("❌ No valid video files found in the specified paths")
            return []

        logger.info(f"✅ Total videos to process: {len(valid_videos)}")
        return valid_videos

    elif video_folder:
        # Scan folder for MP4 files
        video_folder = Path(video_folder)

        if not video_folder.exists():
            logger.error(f"❌ Video folder not found: {video_folder}")
            return []

        mp4_files = sorted(video_folder.glob("*.mp4"))

        if not mp4_files:
            logger.warning(f"⚠️ No MP4 files found in {video_folder}")
            return []

        logger.info(f"✅ Found {len(mp4_files)} video file(s):")
        for video in mp4_files:
            logger.info(f"   - {video.name}")

        return [str(v) for v in mp4_files]

    else:
        logger.error("❌ No VIDEO_PATHS or VIDEO_FOLDER configured")
        return []


def process_single_video(video_path: str, output_dir: str) -> bool:
    """
    Process a single video through the full pipeline.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        video_name = Path(video_path).stem
        logger.info(f"\n{'='*70}")
        logger.info(f"🎬 Processing: {video_name}")
        logger.info(f"{'='*70}")

        # Extract video FPS
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        if fps <= 0 or not isinstance(fps, float):
            fps = 30.0
            logger.warning("⚠️ Could not read FPS, falling back to 30.0")
        else:
            logger.info(f"📹 Video FPS detected: {fps}")

        # Create video-specific output directory
        video_output_dir = os.path.join(output_dir, video_name)
        os.makedirs(video_output_dir, exist_ok=True)

        # Run full analysis
        logger.info("📊 Running full analysis pipeline...")
        result = run_full_analysis(
            pose_model_path=POSE_MODEL_PATH,
            style_model_path=STYLE_MODEL_PATH,
            video_path=video_path,
            output_dir=video_output_dir,
            ffmpeg_path=FFMPEG_EXECUTABLE_PATH,
            save_postprocessed_video=False,
        )

        if not result:
            logger.error(f"❌ Analysis failed for {video_name}")
            return False

        logger.info(f"✅ Analysis complete for {video_name}")

        # Remove final processed video if not needed
        processed_video_path = result.get("processed_video_path")
        focus_video_path = result.get("focus_video_path")
        for p in [processed_video_path, focus_video_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                    logger.info(f"🗑️ Removed generated video: {p}")
                except Exception as ex:
                    logger.warning(f"⚠️ Could not delete {p}: {ex}")

        # Log key results
        logger.info(f"   Stroke Style: {result.get('stroke_style', 'Unknown')}")
        logger.info(
            f"   Total Strokes: {result.get('stroke_result', {}).get('total_count', 0)}"
        )
        logger.info(f"   Total Time: {result.get('total_time', 'N/A')}s")
        logger.info(f"   Avg Speed: {result.get('avg_speed', 'N/A')} m/s")

        # Generate enhanced arm trajectory plots
        logger.info("🎨 Generating enhanced arm trajectory plots...")

        # Read keypoints and laps data from diving_analysis
        df_hip = result.get("diving_analysis", {}).get("df_hip_data")
        laps_data = result.get("diving_analysis", {}).get("laps_data")
        waterline_y = result.get("waterline_y", 200)

        # Extract phase frames data (recovery regions) if available
        phase_frames_dict = {}
        stroke_plot_figs = result.get("stroke_plot_figs", {})
        for key, data in stroke_plot_figs.items():
            if isinstance(data, dict) and "regions" in data:
                phase_frames_dict[key] = data["regions"]

        if df_hip is not None and laps_data:
            try:
                plot_wrist_trajectory_with_dual_axis(
                    df_clean=df_hip,
                    laps_data=laps_data,
                    waterline_y=waterline_y,
                    output_dir=video_output_dir,
                    fps=fps,
                    pool_length=POOL_LENGTH,
                    phase_frames_dict=phase_frames_dict if phase_frames_dict else None,
                    cm_per_pixel=CM_PER_PIXEL,
                )
                logger.info("✅ Enhanced arm trajectory plots generated")

                # Also generate relative-to-shoulder plots
                try:
                    plot_wrist_relative_to_shoulder(
                        df_clean=df_hip,
                        laps_data=laps_data,
                        waterline_y=waterline_y,
                        output_dir=video_output_dir,
                        fps=fps,
                        phase_frames_dict=(
                            phase_frames_dict if phase_frames_dict else None
                        ),
                        cm_per_pixel=CM_PER_PIXEL,
                    )
                    logger.info("✅ Relative motion plots generated")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to generate relative motion plots: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to generate enhanced plots: {e}")
        else:
            logger.warning("⚠️ Missing data for arm trajectory plotting")

        logger.info(f"📁 Results saved to: {video_output_dir}")
        return True

    except Exception as e:
        logger.error(f"❌ Error processing {video_path}: {e}", exc_info=True)
        return False


def main():
    """Main batch processing loop."""
    logger.info(f"{'='*70}")
    logger.info("🚀 ARM TRAJECTORY BATCH PROCESSING")
    logger.info(f"{'='*70}")

    if VIDEO_PATHS and any(VIDEO_PATHS):
        logger.info(
            f"Using explicit video paths ({len([v for v in VIDEO_PATHS if v.strip()])} videos)"
        )
    elif VIDEO_FOLDER:
        logger.info(f"Video Folder: {VIDEO_FOLDER}")

    logger.info(f"Output Folder: {OUTPUT_FOLDER}")
    logger.info(f"Pool Length: {POOL_LENGTH}m")

    # Find video files
    video_files = find_video_files(VIDEO_PATHS, VIDEO_FOLDER)

    if not video_files:
        logger.error("❌ No videos to process. Exiting.")
        return

    # Process each video
    results = {}
    for i, video_path in enumerate(video_files, 1):
        video_name = Path(video_path).stem
        logger.info(f"\n[{i}/{len(video_files)}] Processing {video_name}...")

        success = process_single_video(video_path, OUTPUT_FOLDER)
        results[video_name] = "✅ Success" if success else "❌ Failed"

    # Summary report
    logger.info(f"\n{'='*70}")
    logger.info("📋 PROCESSING SUMMARY")
    logger.info(f"{'='*70}")

    for video_name, status in results.items():
        logger.info(f"{status}: {video_name}")

    success_count = sum(1 for s in results.values() if "Success" in s)
    logger.info(
        f"\nTotal: {success_count}/{len(results)} videos processed successfully"
    )
    logger.info("\n✅ Batch processing complete!")
    logger.info(f"📁 All results saved to: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error in batch processing: {e}", exc_info=True)
        sys.exit(1)
