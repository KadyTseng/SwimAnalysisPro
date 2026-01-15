# Copilot instructions for SwimAnalysisPro

Goal: Help AI coding agents be productive quickly in this repository. Keep changes small, explicit and safe; prefer configuration over patching hard-coded absolute paths.

## Project at a glance
- Main idea: a video analysis pipeline for swimmer videos. Key stages: pose estimation -> keypoint smoothing -> dive segmentation & kick angles -> stroke style classification -> stroke phase segmentation/counting -> split timing -> overlay/postprocessing -> optional mp4 transcode.
- Main components:
  - `BD/` — backend analysis modules (orchestrator, pose estimator, stroke analysis, diving analyzer, split timing, focus crop, postprocessing).
  - `data/` — runtime artifacts: `models/`, `keypoints/`, `processed_videos/`.
  - `web_output/sessions/` — per-session output used by Streamlit UI.
  - top-level `streamlit_app copy.py` (active Streamlit UI) and `main.py` (FastAPI demo endpoints).

## Quick dev / run commands
- Install dependencies (may be large; CUDA-enabled libs present):
  - PowerShell: `python -m pip install -r requirements.txt`
- Run the Streamlit UI (recommended for end-to-end local testing):
  - `streamlit run "streamlit_app copy.py"` (this file wires constants like `POSE_MODEL_PATH`, `STYLE_MODEL_PATH`, `FFMPEG_EXECUTABLE_PATH`).
- Run the FastAPI demo endpoints (simple upload API in `main.py`):
  - `python -m uvicorn main:app --reload --port 8000` (uvicorn may need to be installed separately).
- Small unit-run examples:
  - Run pose estimation on a single file: import and call `BD.pose_estimator.run_pose_estimation(model_path, video_path, output_dir)`
  - Crop focus video: `BD.focus_tracking_view.export_focus_only_video(video_path, txt_path, output_path)`
  
Notes and quick examples:
- For an interactive demo, open `streamlit_app copy.py` and confirm `POSE_MODEL_PATH` and `FFMPEG_EXECUTABLE_PATH` are set for your environment (these are often Windows absolute paths).
- To run the canonical analysis programmatically, call `from BD.orchestrator import run_full_analysis` then `run_full_analysis(pose_model_path, style_model_path, video_path, output_dir, ffmpeg_path=FFMPEG_EXECUTABLE_PATH)`.

## Important, discoverable conventions & patterns
- File and path conventions
  - Models are kept under `data/models/` (example: `svm_model_new_3.pkl`, `best_1.pt`). Streamlit and orchestrator use absolute Windows paths by default — **do not** blindly change these; instead prefer adding configuration or environment variables.
  - Processed session outputs are written to `web_output/sessions/<session_id>/` and `data/processed_videos/`.
  
Tip: Many demo scripts (e.g., `streamlit_app copy.py`, `streamlit_app copy_1.py`, `streamlit_app_old.py`) hard-code `POSE_MODEL_PATH`, `STYLE_MODEL_PATH`, and `FFMPEG_EXECUTABLE_PATH` near the top — prefer injecting these via environment variables or a small `config.py` when making changes or running CI.
- Pipeline order (what modifies what)
  - `BD/orchestrator.py` defines the canonical pipeline order used by the Streamlit UI: pose estimation -> txt smoothing -> diving analysis -> stroke recognition -> phase segmentation -> split timing -> generate overlay focus & processed videos -> transcode options.
- Status tracking
  - `BD/data_manager.py` keeps an in-memory `ANALYSIS_STATUS` dict with statuses (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`) and `intermediate_data` paths. This is the place to interact with background tasks or to add persistence (swap to Redis/Postgres in production).

## Data formats you will see and must respect
- Keypoints TXT format (produced by `BD/pose_estimator.py`)
  - Each line format: `frame_id cls x_center y_center width height conf (kpt_x kpt_y kpt_conf)*`
  - `BD/stroke_style_recognizer.read_full_keypoints_txt` converts each line into a DataFrame with columns: `frame_id, col1, col2, ..., col27` (default `expected_cols=28`).
  - Usage examples in code:
    - Hip coordinates: `col19` (x) and `col20` (y) in the DataFrame produced by `read_full_keypoints_txt`.
    - `BD/focus_tracking_view` expects `parts[19]` and `parts[20]` to be hip x/y when parsing a raw line.
  
Concrete parsing details:
- `BD/stroke_style_recognizer.read_full_keypoints_txt(path, expected_cols=28)` will only keep lines with at least `expected_cols` entries and map them to `frame_id, col1...col27`.
- `BD/diving_analyzer_track_angles.read_and_clean_txt(path, expected_cols=4)` uses a smaller-column parsing variant (used for diving analysis input files in `temp_videos/`).

## Configuration hotspots agents should not break
- Hard-coded paths:
  - `FFMPEG_EXECUTABLE_PATH` is hard-coded in `BD/orchestrator.py` and Streamlit apps. If adding fflags or moving to a server, provide a refactor that reads this from environment or a small config module.
  - Model paths (e.g., `POSE_MODEL_PATH`, `STYLE_MODEL_PATH`) are set in `streamlit_app copy.py`; change via config or env rather than inline edits.
- In-memory status: `BD/data_manager.ANALYSIS_STATUS` is not persistent — when adding background workers or APIs, prefer introducing a persistence layer (Redis or database) so status survives process restarts.
  
Concurrency / long-running notes:
- `BD/data_manager.ANALYSIS_STATUS` is the central in-memory status tracker used by UIs. Background workers should update this dict; do not assume persistence across process restarts.
- `run_full_analysis` orchestrates many I/O-bound stages (pose estimation, file writes, ffmpeg transcode). When adding async or worker-based execution, isolate each pipeline step and persist intermediate artifacts in `web_output/sessions/<session_id>/intermediate/`.

## Where to look for examples / tests
- End-to-end orchestration example: `BD/orchestrator.py` (contains a commented, step-by-step implementation of the full pipeline and return values used by the UI).
- Streamlit glue and status expectations: `streamlit_app copy.py` (how `run_full_analysis` results are consumed and which dict keys are expected: `processed_video_path`, `stroke_style`, `stroke_result`, `stroke_plot_figs`, `kick_angle_fig_1/2`, etc.).
- Small utility examples:
  - `BD/pose_estimator.py` (how keypoints are generated and formatted)
  - `BD/focus_tracking_view.py` (how focus crops are computed and the expected keypoint columns)
  
Other useful files:
- `BD/stroke_style_recognizer.py` — shows the full keypoints DataFrame usage and SVM model loading (`data/models/svm_model_new_3.pkl`).
- `BD/diving_analyzer_track_angles.py` — diving-specific parsing and cleaning helpers (look for `read_and_clean_txt`).
- `main.py` / `test_api.py` — simple FastAPI endpoints and quick upload examples.

## Good first changes an agent can propose (actionable)
- Extract configuration constants (ffmpeg path, model paths, output directories) into a small `config.py` that reads environment variables with sensible defaults.
- Add a tiny CLI/test script showing how to run `run_full_analysis()` on a single file (useful for prerelease debugging).
- Add a short `CONTRIBUTING.md` or extend `Readme.txt` to document the standard dev run steps above and which Streamlit file is the canonical entrypoint.
 
Additional low-effort contributions:
- Add `scripts/run_example.py` which imports `BD.orchestrator.run_full_analysis` and runs a short example against `temp_videos/` with paths drawn from environment variables.
- Add a minimal `tests/test_readers.py` that verifies `read_full_keypoints_txt` and `read_and_clean_txt` handle expected column counts and malformed lines.

---
If you'd like, I can open a PR that:
1) Adds this file to `.github/` (already prepared),
2) Adds a minimal `config.py` and replaces the most obvious absolute paths in `streamlit_app copy.py` with environment-driven values, and
3) Add a tiny `scripts/run_example.py` to exercise `run_full_analysis` on a sample video.

Please tell me which of those (if any) you'd like me to implement next, or what part of this draft needs more detail or examples.