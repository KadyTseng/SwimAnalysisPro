# app.py
import streamlit as st
import os
import pandas as pd
import matplotlib
import traceback
from BD.orchestrator import run_full_analysis  # 確保這行能正確導入您的分析函式

# Set Matplotlib backend to Agg to capture figures correctly in Streamlit
matplotlib.use("Agg")

# --------------------------------------------------------------------------
# 🎯 I. 全域配置與路徑定義
# --------------------------------------------------------------------------

# 設置寬版面配置
st.set_page_config(
    layout="wide", page_title="Swim Analysis Pro", initial_sidebar_state="collapsed"
)

# 請替換為您的實際路徑 (請務必根據您的環境修改)
POSE_MODEL_PATH = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\best_1.pt"
STYLE_MODEL_PATH = (
    r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\data\models\svm_model_new_3.pkl"
)
OUTPUT_DIR = r"D:\Kady\Pool_UI_processed\SwimAnalysisPro\web_output\sessions"
FFMPEG_EXECUTABLE_PATH = r"C:\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe"
TEMP_VIDEO_DIR = "temp_videos"
os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)

# 泳姿翻譯字典
SWIM_STROKES_TRANSLATION = {
    "Freestyle": "自由式",
    "Breaststroke": "蛙式",
    "Backstroke": "仰式",
    "Butterfly": "蝶式",
    "I.m.": "個人混合式",  # I.M. (Individual Medley)
    "N/a": "未偵測",  # 處理 N/A 的情況
    # 您可以根據實際情況，加入其他泳姿的翻譯
}

# --- 🎯 CSS 注入：檔案上傳器、影片最大化與快捷鍵準備 ---
st.markdown(
    """
    <style>
    /* 1. 隱藏拖放區域內部的所有文字 (保持純按鈕外觀) */
    [data-testid="stFileUploaderDropzone"] > div:nth-child(1) {
        visibility: hidden;
        height: 0px;  
        margin-top: -30px;  
    }
    [data-testid="stFileUploaderDropzone"] {
        padding: 5px;
        min-height: 45px;  
        border: none !important;  
    }
    [data-testid="stFileUploaderDropzone"] button {
        visibility: visible;
    }

    /* 修正 A：隱藏上傳成功後顯示的檔案名稱、檔案大小及刪除按鈕 */
    [data-testid="stFileUploaderContent"] {
        display: none;
    }

    /* 修正 B：影片/佔位符容器寬度最大化 (占滿版面) */
    [data-testid="stVideo"] {
        width: 100% !important;
    }
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"]:first-child > div {
        width: 100% !important;
    }

    /* 2. 影片區域固定 (Sticky Position) */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"]:first-child {
        position: sticky;
        top: 0;  
        z-index: 999;  
        background-color: white;  
        padding-top: 10px;  
        padding-bottom: 10px;  
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 🎯 JavaScript 注入：快捷鍵 'A' 和 'B' ---
st.markdown(
    """
    <script>
    document.addEventListener('keydown', function(event) {
        let targetButton = null;
        const pressedKey = event.key.toLowerCase();

        // 1. 快捷鍵 'A' -> 上傳影片按鈕 (Browse files)
        if (pressedKey === 'a') {
            // 尋找包含 "Browse files" 文字的按鈕
            const buttons = document.querySelectorAll('button');
            for (let i = 0; i < buttons.length; i++) {
                if (buttons[i].innerText.includes('Browse files')) {
                    targetButton = buttons[i];
                    break;
                }
            }
        } 
        // 2. 快捷鍵 'B' -> 開始分析按鈕 (🚀 開始分析 (診斷模式))
        else if (pressedKey === 'b') {
            // 尋找包含 "開始分析" 文字的按鈕
            const buttons = document.querySelectorAll('button');
            for (let i = 0; i < buttons.length; i++) {
                if (buttons[i].innerText.includes('開始分析')) {
                    targetButton = buttons[i];
                    break;
                }
            }
        }

        if (targetButton) {
            // 阻止瀏覽器預設行為
            event.preventDefault(); 
            // 模擬點擊按鈕
            targetButton.click();
        }
    });
    </script>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# 🎯 II. 狀態管理初始化
# --------------------------------------------------------------------------

if "page_state" not in st.session_state:
    st.session_state["page_state"] = "initial"
    st.session_state["final_results"] = None
    st.session_state["processed_video_path"] = None

    st.session_state["current_stroke_fig_key"] = "Outbound_Shoulder"
    st.session_state["current_kick_fig_key"] = "Kick_1"

    st.session_state["file_bytes"] = None
    st.session_state["file_name"] = None
    # ⚠️ 關鍵修正：移除 st.session_state["uploaded_file"] = None
    # Streamlit 會自動處理 key="uploaded_file" 的初始化


# --------------------------------------------------------------------------
# 🎯 III. 核心函式定義
# --------------------------------------------------------------------------


def set_stroke_fig(direction, part):
    """設定划水圖表狀態的回調函式。"""
    new_key = f"{direction}_{part}"
    if st.session_state.current_stroke_fig_key != new_key:
        st.session_state.current_stroke_fig_key = new_key


def set_kick_fig(phase):
    """設定踢腿圖表狀態的回調函式。"""
    st.session_state.current_kick_fig_key = phase


def display_matplotlib_fig(fig):
    """用於顯示 Matplotlib 圖表。"""
    if fig is not None:
        st.pyplot(fig, clear_figure=True)
    else:
        st.warning("無圖表數據可顯示。")


def dummy_status_callback(message):
    """用於在診斷時取代實際的狀態更新。"""
    pass


def handle_start_analysis_and_run():
    """
    🎯 核心診斷函式：直接在按鈕回調中讀取檔案並執行分析。
    """

    # 從 Session State 獲取檔案 (由 file_uploader 自動賦值)
    uploaded_file = st.session_state.get("uploaded_file")

    if uploaded_file is not None:
        try:
            # 1. 立即讀取並儲存檔案內容 (解決檔案緩衝區丟失問題)
            file_bytes = uploaded_file.getbuffer()
            file_name = uploaded_file.name

            # 寫入暫存
            temp_video_path = os.path.join(TEMP_VIDEO_DIR, file_name)
            with open(temp_video_path, "wb") as f:
                f.write(file_bytes)

            # 2. 設置狀態為 processing
            st.session_state["page_state"] = "processing"

            # 3. 運行分析 (同步執行)
            st.info("🚀 **分析啟動中...** (請等待直到完成或看到錯誤)")

            results = run_full_analysis(
                POSE_MODEL_PATH,
                STYLE_MODEL_PATH,
                temp_video_path,
                OUTPUT_DIR,
                FFMPEG_EXECUTABLE_PATH,
                status_callback=dummy_status_callback,
            )

            # 4. 設置結果
            st.session_state.page_state = "complete"
            st.session_state.final_results = results
            st.session_state.processed_video_path = results.get("processed_video_path")
            # st.success("✅ **分析成功完成！**")

        except Exception as e:
            # 捕獲所有異常並顯示詳細的堆棧追蹤
            st.session_state.page_state = "initial"
            st.error("❌ **分析在內部崩潰！請檢查以下錯誤：**")
            st.code(traceback.format_exc())
            st.error(f"主要錯誤訊息: {e}")
            st.rerun()
        # finally:
        #     st.rerun()
    else:
        st.warning("請先上傳影片檔案。")
        st.rerun()


# --------------------------------------------------------------------------
# 🎯 IV. UI 佈局實現
# --------------------------------------------------------------------------

# --- 頂部區域：極簡化上傳按鈕 + 開始分析按鈕 ---
with st.container():
    col_upload, col_button, col_title_spacer = st.columns([1, 1, 3])

    with col_upload:
        # 上傳元件，使用 key="uploaded_file" 讓 Streamlit 自動管理狀態
        uploaded_file = st.file_uploader(
            "上傳影片",
            type=["mp4", "mov"],
            key="uploaded_file",
            label_visibility="collapsed",
        )

    with col_button:
        # 檢查檔案狀態
        can_start = (
            st.session_state.get("uploaded_file") is not None
            and st.session_state.page_state != "processing"
        )

        if st.button(
            "🚀 開始分析 (診斷模式)",
            key="start_analysis_manual",
            disabled=not can_start,
            on_click=handle_start_analysis_and_run,
        ):
            pass


# --- 影片容器 (用於顯示進度日誌或最終影片) ---
video_and_log_placeholder = st.empty()

# 根據狀態更新內容
if st.session_state.page_state == "processing":
    # 顯示診斷訊息
    with video_and_log_placeholder.container():
        st.markdown(
            """
            <div style='text-align: center; padding: 150px 0; border: 2px dashed #ff4b4b; background-color: #ffebeb; border-radius: 10px;'>
                <h2>分析正在後台同步執行中...</h2>
                <p>請耐心等待或檢查控制台（Terminal）輸出是否有即時日誌。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
elif st.session_state.page_state == "complete":
    with video_and_log_placeholder.container():
        video_path = st.session_state.processed_video_path
        if video_path and os.path.exists(video_path):
            st.video(video_path, format="video/mp4")
        else:
            st.error("Processed video not found.")
else:
    # 'initial' 狀態
    with video_and_log_placeholder.container():
        st.markdown(
            """
            <div style='text-align: center; padding: 150px 0; background-color: #f0f2f6; border-radius: 10px;'>
                <h2>請點擊上傳按鈕載入影片（A 鍵），然後點擊「🚀 開始分析 (診斷模式)」（B 鍵）</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# --- 下方分析區塊：核心指標 (Metrics) & 波形圖 (Waveforms) ---
col_metrics, col_waveform = st.columns([1, 2])

# --------------------------------------------------------------------------
# 🎯 V. 核心指標區塊 (col_metrics)
# --------------------------------------------------------------------------

with col_metrics:

    if st.session_state.page_state == "complete" and st.session_state.final_results:
        results = st.session_state.final_results

        english_style = results.get("stroke_style", "N/A").capitalize()
        # 確保找不到時回傳英文 (或 N/A 的翻譯)
        chinese_style = SWIM_STROKES_TRANSLATION.get(english_style, english_style)

        # 修正：使用 st.markdown 和 H1 標題 (#) 來放大字樣並顯示中文泳姿
        st.markdown(f"### **泳姿:** {chinese_style}")

        st.subheader("分段計時 (秒)")

        passed_frames = results.get("passed", {})
        fps_val = results.get("fps", 30.0)
        diving_segments = results.get("diving_segments", {})
        start_frame_val = diving_segments.get("s1", 0)

        time_data = []

        if passed_frames and start_frame_val is not None and fps_val > 0:
            for k, frame in passed_frames.items():
                if frame is not None and frame > start_frame_val:
                    distance = k.replace("_frame", "").upper()
                    time_sec = (frame - start_frame_val) / fps_val
                    time_data.append([distance, f"{time_sec:.2f} s"])

        if time_data:
            st.table(pd.DataFrame(time_data, columns=["距離", "時間"]))
        else:
            st.info("無有效分段計時數據。")

        st.subheader("划手次數")
        stroke_result = results.get("stroke_result", {})
        # 顯示總划手次數
        # st.markdown(f"**總划手次數:** **{stroke_result.get('total_count', 0)}** 次")
        st.markdown(f"去程: {stroke_result.get('range1_recovery_count', 0)} 次")
        st.markdown(f"回程: {stroke_result.get('range2_recovery_count', 0)} 次")

    elif st.session_state.page_state == "processing":
        st.info("請等待分析完成。")
    else:
        st.info("請上傳影片並點擊「🚀 開始分析 (診斷模式)」。")


# --------------------------------------------------------------------------
# 🎯 VI. 波形圖區塊 (col_waveform)
# --------------------------------------------------------------------------
with col_waveform:

    if st.session_state.page_state == "complete" and st.session_state.final_results:
        results = st.session_state.final_results
        stroke_figs = results.get("stroke_plot_figs", {})

        # --- 划手波形圖切換 (單張顯示) ---
        st.subheader("划水波形圖")

        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)

        current_dir = (
            st.session_state.current_stroke_fig_key.split("_")[0]
            if "_" in st.session_state.current_stroke_fig_key
            else "Outbound"
        )

        with col_btn1:
            if st.button(
                "去程",
                key="btn_dir_out",
                disabled=(current_dir == "Outbound"),
                on_click=set_stroke_fig,
                args=("Outbound", "Shoulder"),
            ):
                pass
        with col_btn2:
            if st.button(
                "回程",
                key="btn_dir_in",
                disabled=(current_dir == "Inbound"),
                on_click=set_stroke_fig,
                args=("Inbound", "Shoulder"),
            ):
                pass

        with col_btn3:
            if st.button(
                "肩膀波形圖",
                key="btn_part_shoulder",
                disabled=(st.session_state.current_stroke_fig_key.endswith("Shoulder")),
                on_click=set_stroke_fig,
                args=(current_dir, "Shoulder"),
            ):
                pass
        with col_btn4:
            if st.button(
                "手腕波形圖",
                key="btn_part_wrist",
                disabled=(st.session_state.current_stroke_fig_key.endswith("Wrist")),
                on_click=set_stroke_fig,
                args=(current_dir, "Wrist"),
            ):
                pass

        st.markdown("---")

        # 3. 划手圖表顯示邏輯 (只顯示一張圖)
        display_fig = None
        current_key_parts = st.session_state.current_stroke_fig_key.split("_")
        dir_map = {"Outbound": "range1", "Inbound": "range2"}
        fig_range_key = dir_map.get(current_key_parts[0])
        fig_part_key = f"{current_key_parts[1].lower()}_fig"

        if fig_range_key in stroke_figs:
            plot_data = stroke_figs[fig_range_key]
            if plot_data and fig_part_key in plot_data:
                display_fig = plot_data[fig_part_key]

        if display_fig:
            display_matplotlib_fig(display_fig)
        else:
            st.warning(
                f"當前狀態 ({current_key_parts[0]} - {current_key_parts[1]}) 無有效波形數據。"
            )

        st.markdown("---")

        # --- 踢腿角度分析切換 (單張顯示) ---
        st.subheader("潛水踢腿角度分析")

        # 1. 踢腿按鈕 (Kick 1 / Kick 2)
        col_kick1, col_kick2 = st.columns(2)
        with col_kick1:
            if st.button(
                "去程踢腿角度",
                key="btn_kick1_only",
                disabled=(st.session_state.current_kick_fig_key == "Kick_1"),
                on_click=set_kick_fig,
                args=("Kick_1",),
            ):
                pass
        with col_kick2:
            if st.button(
                "回程踢腿角度",
                key="btn_kick2_only",
                disabled=(st.session_state.current_kick_fig_key == "Kick_2"),
                on_click=set_kick_fig,
                args=("Kick_2",),
            ):
                pass

        # 2. 踢腿圖表顯示邏輯 (只顯示一張圖)
        kick_fig_to_display = None

        if st.session_state.current_kick_fig_key == "Kick_1":
            kick_fig_to_display = results.get("kick_angle_fig_1")
        elif st.session_state.current_kick_fig_key == "Kick_2":
            kick_fig_to_display = results.get("kick_angle_fig_2")

        if kick_fig_to_display:
            display_matplotlib_fig(kick_fig_to_display)
        else:
            st.warning("無相關踢腿角度分析圖數據。")

    elif st.session_state.page_state == "processing":
        st.info("請查看上方的日誌流程。")
    else:
        st.info("請上傳影片以開始分析。")


# --------------------------------------------------------------------------
# 🎯 VII. 程式入口點：判斷是否需要啟動分析流程 (無操作)
# --------------------------------------------------------------------------
pass
