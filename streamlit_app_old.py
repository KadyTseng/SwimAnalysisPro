# streamlit_app.py (修正後的版本)
import streamlit as st
import os
import logging
import pandas as pd
import matplotlib

# Set Matplotlib backend to Agg to capture figures correctly in Streamlit
matplotlib.use("Agg")

# Assuming orchestrator.py and all its dependencies are corrected and runnable
from BD.orchestrator import run_full_analysis


# --- Logging Configuration (Custom Handler for Accumulative Display) ---
class StreamlitLogHandler(logging.Handler):
    """Custom log handler to implement multi-line, large-font, accumulative Step flow display."""

    def __init__(self, log_placeholder):
        super().__init__()
        self.log_placeholder = log_placeholder
        self.log_messages = []  # List to store all Step messages
        self.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )

    def emit(self, record):
        msg = self.format(record)

        # *** KEY CORRECTION: Only process messages containing "Step" ***
        if "Step" in msg:
            # Extract content after "Step X/Y:"
            content = msg.split("Step", 1)[1].strip()

            # Format the step with large font for visual emphasis
            formatted_step = f"<h3 style='color: #1f77b4; margin: 0; padding: 5px 0;'> ▶ Step{content}</h3>"

            # Add new step to the list (check for duplicates is usually helpful)
            if formatted_step not in self.log_messages:
                self.log_messages.append(formatted_step)

            # *** KEY CORRECTION: Overwrite the placeholder with the entire accumulated list ***
            self.log_placeholder.markdown(
                "".join(
                    self.log_messages
                ),  # Join list elements without adding extra <br> if <h3> already includes margin/padding
                unsafe_allow_html=True,
            )
        # Other logging info messages are ignored in the UI


# --- Main Analysis and UI Integration Function ---
def run_analysis_and_ui():
    st.set_page_config(layout="wide")

    # *** CSS Injection for Theme ***
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #f0f8ff; /* Alice Blue (Light Blue) */
        }
        /* ... (other CSS styles) ... */
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Set large title in the top-left corner
    st.markdown(
        "<h1 style='color: #1f77b4;'>NCKU Swimming Pool Analysis - DEMO</h1>",
        unsafe_allow_html=True,
    )

    # Set temporary output directory (Project Relative)
    if "output_dir" not in st.session_state:
        output_base_dir = os.path.join(os.path.dirname(__file__), "web_output")
        session_id = "session_" + str(os.getpid())
        st.session_state.output_dir = os.path.join(output_base_dir, session_id)
        os.makedirs(st.session_state.output_dir, exist_ok=True)

    # --- 1. File Upload and Layout ---
    col_file, col_video_placeholder = st.columns([1, 2])

    with col_video_placeholder:
        st.subheader("Analysis Flow...")
        video_and_log_container = st.empty()  # Container for displaying video and logs

    with col_file:
        uploaded_file = st.file_uploader("📂 Drag or Select Video (.mp4)", type=["mp4"])

    # Hardcoded Model Paths
    pose_model_path = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\best_1.pt"
    style_model_path = (
        r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\svm_model_new_3.pkl"
    )
    st.sidebar.info("Model paths are Hardcoded.")

    # 3. Start Analysis Button
    if uploaded_file is not None and st.button(" Start Full Analysis", type="primary"):

        root_logger = logging.getLogger()
        handler = StreamlitLogHandler(video_and_log_container)
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

        st.info(f"File {uploaded_file.name} loaded. Starting process...")

        # Save the uploaded file
        temp_video_path = os.path.join(st.session_state.output_dir, uploaded_file.name)
        with open(temp_video_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        try:
            results = run_full_analysis(
                pose_model_path,
                style_model_path,
                temp_video_path,
                st.session_state.output_dir,
            )

            st.success(" Analysis process finished! Check results below.")

            # *** KEY: Remove Handler BEFORE displaying video to prevent overwrite by log events ***
            root_logger.removeHandler(handler)

            import time

            # 延遲 0.5 秒，確保系統有時間釋放檔案鎖定 (這是因為 cv2.VideoWriter 結束後可能仍持有鎖定)
            logging.info("Waiting 0.5s for video file lock release...")
            time.sleep(0.5)

            display_processed_video(results, video_and_log_container)

            # --- Final Summary Section ---
            display_results_summary(results)
        except Exception as e:
            st.error(f"Analysis failed! Check code or models: {e}")


# --- Independent Function: Handle Video Display ---


def display_processed_video(results, container):
    """Displays the final processed video in the log container after the flow is complete."""
    processed_video_path = results["processed_video_path"]

    # Clear logs/flow information before displaying final content
    container.empty()

    if os.path.exists(processed_video_path):
        # 1. 使用 try...except 塊包圍檔案操作和 Streamlit 顯示
        try:
            with open(processed_video_path, "rb") as f:
                video_bytes = f.read()

            # 這裡的 if/else 邏輯是正確的
            # 為了安全起見，如果輸出是 .avi，確保 format 正確。
            if processed_video_path.lower().endswith(".avi"):
                container.video(video_bytes, format="video/avi")
            else:
                # 注意：如果您的影片是 .mov，瀏覽器可能仍然無法播放
                container.video(video_bytes, format="video/mp4")

        # 2. except 區塊對齊 try 語句 (縮排正確)
        except Exception as e:
            # Add explicit error handling
            container.error(f"Error reading or displaying video file: {e}")
            container.warning(
                "The file might be locked, corrupted, or the codec is incompatible. "
                "Ensure the previous process step has released the file lock."
            )

    # 3. 最外層的 else 區塊對齊 if os.path.exists(processed_video_path): (縮排正確)
    else:
        container.error(f"Processed video file not found at: {processed_video_path}")


# --- Independent Function: Display Summary and Plots ---
def display_results_summary(results):
    """Displays analysis summary, counts, timing, and all plots."""

    # Extract core data
    stroke_result = results.get("stroke_result", {})
    diving_segments = results.get("diving_segments", {})
    total_time_display = results.get("total_time", "N/A")

    st.markdown("---")

    # -----------------------------------------------------
    # A. Metrics and Counts (Left Column)
    # -----------------------------------------------------
    col_metrics, col_plots = st.columns([1, 2])

    with col_metrics:
        st.header("🎯 Core Metrics Analysis")
        st.metric("🏊‍♀️ Recognized Stroke Style", results["stroke_style"])
        st.metric("⏱️ Total Analysis Time", f"{total_time_display} s")

        st.subheader("🔢 Stroke Count Results")
        st.markdown(
            f"**Total Strokes:** **{stroke_result.get('total_count', 0)}** cycles"
        )
        st.markdown(
            f"↳ Outbound (R1): {stroke_result.get('range1_recovery_count', 0)} cycles"
        )
        st.markdown(
            f"↳ Inbound (R2): {stroke_result.get('range2_recovery_count', 0)} cycles"
        )

        # Split Timing Results
        st.subheader("⏱️ Split Timing (Seconds)")
        passed_frames = results.get("passed", {})
        fps_val = results.get("fps", 30.0)
        start_frame_val = diving_segments.get("s1", 0)

        time_data = []
        if passed_frames and start_frame_val is not None and fps_val > 0:
            for k, frame in passed_frames.items():
                if frame is not None:
                    time_sec = (frame - start_frame_val) / fps_val
                    time_data.append([k, f"{time_sec:.2f} s"])

        if time_data:
            st.table(pd.DataFrame(time_data, columns=["Distance", "Time"]))
        else:
            st.markdown("No valid split timing data available.")

    # -----------------------------------------------------
    # B. Plot Area (Right Column) - Enhanced
    # -----------------------------------------------------
    with col_plots:
        st.header("📈 Waveform and Angle Analysis")

        # 1. Stroke Waveforms (Using Tabs)
        stroke_plot_figs = results.get("stroke_plot_figs", {})
        if stroke_plot_figs:
            st.markdown("---")
            st.markdown("#### Stroke Cycle Waveform Analysis")

            # Assuming the keys are 'range1' and 'range2'
            tab_names = ["Outbound R1", "Inbound R2"]
            tabs = st.tabs(tab_names)

            for i, range_key in enumerate(stroke_plot_figs.keys()):
                plot_data = stroke_plot_figs[range_key]
                if plot_data:
                    with tabs[i]:
                        fig_stroke_cols = st.columns(2)

                        # Shoulder
                        if plot_data.get("shoulder_fig"):
                            with fig_stroke_cols[0]:
                                st.markdown("**Shoulder Y Waveform**")
                                st.pyplot(plot_data["shoulder_fig"], clear_figure=True)

                        # Wrist
                        if plot_data.get("wrist_fig"):
                            with fig_stroke_cols[1]:
                                st.markdown("**Wrist Y Waveform**")
                                st.pyplot(plot_data["wrist_fig"], clear_figure=True)
                else:
                    tabs[i].info("Stroke data for this range is missing.")

        # 2. Kick Angle Waveform
        st.markdown("---")
        st.markdown("#### 🦵 Dive and Kick Angle Analysis")

        fig_kick_cols = st.columns(2)

        # Phase 1
        if results.get("kick_angle_fig_1"):
            with fig_kick_cols[0]:
                st.markdown("**Kick Angle - Phase 1**")
                st.pyplot(results["kick_angle_fig_1"], clear_figure=True)

        # Phase 2
        if results.get("kick_angle_fig_2"):
            with fig_kick_cols[1]:
                st.markdown("**Kick Angle - Phase 2**")
                st.pyplot(results["kick_angle_fig_2"], clear_figure=True)

        if not results.get("kick_angle_fig_1") and not results.get("kick_angle_fig_2"):
            st.info("No valid dive kick angle data available.")


# --- Run Main Function ---
if __name__ == "__main__":
    run_analysis_and_ui()
