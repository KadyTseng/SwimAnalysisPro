"""
Verification & Quick Run Script
================================

This script checks if everything is configured correctly before running the batch analysis.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))


def verify_configuration():
    """Verify all configuration and paths."""
    print("\n" + "=" * 70)
    print("✅ VERIFICATION CHECKLIST")
    print("=" * 70 + "\n")

    # Import config from batch script
    from batch_arm_trajectory_analysis import (
        VIDEO_PATHS,
        VIDEO_FOLDER,
        OUTPUT_FOLDER,
        POSE_MODEL_PATH,
        STYLE_MODEL_PATH,
        FFMPEG_EXECUTABLE_PATH,
        FPS,
        POOL_LENGTH,
    )

    checks = {"Models & Tools": {}, "Videos": {}, "Output": {}}

    # ========== MODEL CHECKS ==========
    print("📦 Models & Tools:")

    # Pose Model
    if os.path.exists(POSE_MODEL_PATH):
        print(f"   ✅ Pose Model: {Path(POSE_MODEL_PATH).name}")
        checks["Models & Tools"]["Pose Model"] = True
    else:
        print(f"   ❌ Pose Model NOT FOUND: {POSE_MODEL_PATH}")
        checks["Models & Tools"]["Pose Model"] = False

    # Style Model
    if os.path.exists(STYLE_MODEL_PATH):
        print(f"   ✅ Style Model: {Path(STYLE_MODEL_PATH).name}")
        checks["Models & Tools"]["Style Model"] = True
    else:
        print(f"   ❌ Style Model NOT FOUND: {STYLE_MODEL_PATH}")
        checks["Models & Tools"]["Style Model"] = False

    # FFMPEG
    if os.path.exists(FFMPEG_EXECUTABLE_PATH):
        print(f"   ✅ FFMPEG: {Path(FFMPEG_EXECUTABLE_PATH).name}")
        checks["Models & Tools"]["FFMPEG"] = True
    else:
        print(f"   ❌ FFMPEG NOT FOUND: {FFMPEG_EXECUTABLE_PATH}")
        checks["Models & Tools"]["FFMPEG"] = False

    # ========== VIDEO CHECKS ==========
    print("\n🎬 Videos:")

    all_videos = []

    if VIDEO_PATHS and any(VIDEO_PATHS):
        print(
            f"   Using explicit video paths ({len([v for v in VIDEO_PATHS if v.strip()])} videos):"
        )
        for i, video_path in enumerate(VIDEO_PATHS, 1):
            if not video_path.strip():
                continue
            if os.path.exists(video_path):
                print(f"      ✅ [{i}] {Path(video_path).name}")
                all_videos.append(video_path)
                checks["Videos"][f"Video {i}"] = True
            else:
                print(f"      ❌ [{i}] NOT FOUND: {video_path}")
                checks["Videos"][f"Video {i}"] = False

    elif VIDEO_FOLDER:
        video_folder = Path(VIDEO_FOLDER)
        if video_folder.exists():
            mp4_files = sorted(video_folder.glob("*.mp4"))
            if mp4_files:
                print(f"   Found {len(mp4_files)} videos in {VIDEO_FOLDER}:")
                for i, video in enumerate(mp4_files, 1):
                    print(f"      ✅ [{i}] {video.name}")
                    all_videos.append(str(video))
                checks["Videos"]["Folder Scan"] = True
            else:
                print(f"   ❌ No MP4 files found in {VIDEO_FOLDER}")
                checks["Videos"]["Folder Scan"] = False
        else:
            print(f"   ❌ Folder not found: {VIDEO_FOLDER}")
            checks["Videos"]["Folder Exists"] = False
    else:
        print("   ⚠️  Neither VIDEO_PATHS nor VIDEO_FOLDER configured")
        checks["Videos"]["Configuration"] = False

    # ========== OUTPUT FOLDER CHECK ==========
    print("\n📁 Output:")
    output_folder = Path(OUTPUT_FOLDER)
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f"   ✅ Output folder ready: {OUTPUT_FOLDER}")
    checks["Output"]["Folder"] = True

    # ========== PARAMETERS ==========
    print("\n⚙️  Parameters:")
    print(f"   FPS: {FPS}")
    print(f"   Pool Length: {POOL_LENGTH}m")

    # ========== SUMMARY ==========
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)

    total_checks = sum(len(v) for v in checks.values())
    passed_checks = sum(sum(1 for v in vals.values() if v) for vals in checks.values())

    print(f"\nPassed: {passed_checks}/{total_checks} checks")

    if passed_checks == total_checks:
        print("✅ All checks passed! Ready to run.")
        return True, all_videos
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        return False, all_videos


def main():
    """Main function."""
    success, video_list = verify_configuration()

    if not success:
        print("\n" + "=" * 70)
        print("❌ Configuration issues detected. Please fix them first.")
        print("=" * 70)
        sys.exit(1)

    if not video_list:
        print("\n" + "=" * 70)
        print("❌ No videos found to process.")
        print("=" * 70)
        sys.exit(1)

    # Ask user to confirm
    print("\n" + "=" * 70)
    print(f"🚀 Ready to process {len(video_list)} video(s)")
    print("=" * 70)

    response = input("\nStart batch processing now? (yes/no): ").strip().lower()

    if response in ["yes", "y", ""]:
        print("\n⏳ Starting batch processing...\n")
        from batch_arm_trajectory_analysis import main as batch_main

        batch_main()
    else:
        print("❌ Cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
