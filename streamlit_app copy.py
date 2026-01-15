import streamlit as st
import os
import traceback

# 🎯 由於您在 III. 核心函式定義中使用了 plt，我將其保留在頂部。
# 這裡假設您的 BD.orchestrator 模組沒有使用 matplotlib 或 numpy。
from BD.orchestrator import run_full_analysis

# Set Matplotlib backend to Agg to capture figures correctly in Streamlit
# 如果您打算在遠端環境運行，這行通常是必要的。
# matplotlib.use("Agg")

# --------------------------------------------------------------------------
# 🎯 I. 核心配置與常數定義
# --------------------------------------------------------------------------

# 請替換為您的實際路徑
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
    "I.m.": "個人混合式",
    "N/a": "未偵測",
}

# --------------------------------------------------------------------------
# 🎯 II. 狀態管理初始化
# --------------------------------------------------------------------------
# 🎯 配置頁面 (必須在任何 UI 元素之前)
st.set_page_config(
    layout="wide", page_title="NCKU Pool System", initial_sidebar_state="collapsed"
)
st.markdown(
    """
    <style>
    /* 1. 隱藏拖放區域內部的所有文字 (保持純按鈕外觀) */
    [data-testid="stFileUploaderDropzone"] > div:nth-child(1) {
        visibility: hidden; height: 0px; margin-top: -30px; }
    /* 🎯 讓 st.markdown 的 H4 顯示在同一行，用於分段計時 (調整垂直間距) */
    div[data-testid="stVerticalBlock"] > div:has(h4) {
        margin-top: -10px; /* 減少間距 */
        margin-bottom: -10px; /* 減少間距 */
    }
    
    /* 🎯 隱藏系統警告黃色橫幅 */
    div[data-testid="stStatusWidget"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* ======== 🎯 Tab 標籤字體大小調整 (加大到 24px/18px) ======== */
    /* 讓第一個 Tab 標籤文字變大並加粗 (作為大標題) */
    [data-testid^="stTabs"] [data-baseweb="tab-list"] button:nth-child(1) {
        font-size: 24px; /* 提升至 24px */
        font-weight: bold;
    }
    /* 讓其他圖表 Tab 標籤文字略微放大 */
    [data-testid^="stTabs"] [data-baseweb="tab-list"] button:not(:nth-child(1)) {
        font-size: 18px; /* 提升至 18px */
    }
    /* ========================================================== */
    
    /* ======== 🎯 隱藏右上角設定和頁腳 (新增部分) ======== */
    #MainMenu {
        visibility: hidden; /* 隱藏右上角三個點 */
    }
    footer {
        visibility: hidden; /* 隱藏頁腳 */
    }
    header {
        visibility: hidden; /* 隱藏 Streamlit 內建的 Header/Sidebar 箭頭 */
    }
    /* ================================================= */
    
    </style>
    <script>
    /* ... 您的所有 JavaScript 代碼 ... */
    document.addEventListener('keydown', function(event) {
        let targetButton = null; const pressedKey = event.key.toLowerCase(); const buttons = document.querySelectorAll('button');
        if (pressedKey === 'a') {
            for (let i = 0; i < buttons.length; i++) {
                if (buttons[i].innerText && buttons[i].innerText.includes('Browse files')) { targetButton = buttons[i]; break; } } } 
        else if (pressedKey === 'b') {
            for (let i = 0; i < buttons.length; i++) {
                if (buttons[i].innerText && buttons[i].innerText.includes('開始分析')) { targetButton = buttons[i]; break; } } }
        if (targetButton) { event.preventDefault(); targetButton.click(); }
    });
    </script>
    """,
    unsafe_allow_html=True,
)

if "page_state" not in st.session_state:
    st.session_state["page_state"] = "initial"
    st.session_state["final_results"] = None
    st.session_state["temp_video_path"] = None  # 儲存暫存路徑
    st.session_state["processed_video_path"] = None

    st.session_state["error_message"] = None


# --------------------------------------------------------------------------
# 🎯 III. 核心函式定義
# --------------------------------------------------------------------------


def display_matplotlib_fig(fig):
    if fig is not None:
        st.pyplot(fig, clear_figure=True)
    else:
        # 使用一個佔位符提示
        st.markdown(
            "<p style='text-align: center; color: gray;'>無圖表數據可顯示。</p>",
            unsafe_allow_html=True,
        )


def dummy_status_callback(message):
    pass


def handle_start_analysis_and_run():
    """
    🎯 回調函式：只負責檔案處理和設置狀態。
    """

    uploaded_file = st.session_state.get("uploaded_file")

    if uploaded_file is None:
        st.warning("等待錄製影片")
        st.rerun()
        return

    # 1. 處理檔案
    try:
        # 使用 .read() 獲取檔案內容
        file_bytes = uploaded_file.read()
        file_name = uploaded_file.name
        temp_video_path = os.path.join(TEMP_VIDEO_DIR, file_name)

        # 寫入暫存
        with open(temp_video_path, "wb") as f:
            f.write(file_bytes)

        # 2. 設置狀態為 processing
        st.session_state["page_state"] = "processing"
        st.session_state["error_message"] = None
        st.session_state["temp_video_path"] = temp_video_path  # 儲存路徑

        # 3. 觸發 RERUN 進入 processing 狀態
        st.rerun()

    except Exception as e:
        st.session_state.page_state = "initial"
        st.session_state.error_message = (
            f"❌ **檔案處理失敗：**\n{traceback.format_exc()}\n主要錯誤訊息: {e}"
        )
        st.rerun()


# --------------------------------------------------------------------------
# 🎯 IV. UI 佈局實現
# --------------------------------------------------------------------------

# --- 頂部區域：錯誤處理與按鈕 ---
if st.session_state.get("error_message"):
    st.error(st.session_state.error_message)
    st.session_state.error_message = None


with st.container():
    # 🎯 六欄佈局：[上傳: 2 | 按鈕: 2 | 預留空間: 15 | 泳姿: 4 | 划手: 4 | 計時: 4]
    (
        col_upload,
        col_button,
        col_spacer,
        col_style,
        col_stroke,
        col_split,
    ) = st.columns([2, 2, 15, 4, 4, 4])

    # --- 欄位 1: 上傳按鈕 ---
    with col_upload:
        st.file_uploader(
            "上傳影片",
            type=["mp4", "mov"],
            key="uploaded_file",
            label_visibility="collapsed",
        )

    # --- 欄位 2: 開始分析按鈕 ---
    with col_button:
        can_start = (
            st.session_state.get("uploaded_file") is not None
            and st.session_state.page_state != "processing"
        )

        # 使用一欄放置「開始分析」按鈕
        st.button(
            "開始分析",
            key="start_analysis_manual",
            disabled=not can_start,
            on_click=handle_start_analysis_and_run,
        )

    # --- 欄位 3: 預留空間 ---
    with col_spacer:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # --- 欄位 4, 5, 6: 核心指標區塊的佔位符 ---
    with col_style:
        style_placeholder = st.empty()
    with col_stroke:
        stroke_placeholder = st.empty()
    with col_split:
        split_placeholder = st.empty()


# --- 影片容器 (用於顯示進度日誌或最終影片) ---
video_and_log_placeholder = st.empty()

# 根據狀態更新內容
if st.session_state.page_state == "processing":
    # 🎯 狀態 1: 顯示處理中訊息，然後執行分析 (UI 將凍結)
    with video_and_log_placeholder.container():
        st.markdown(
            """
            <div style='text-align: center; padding: 150px 0; border: 2px dashed #ff4b4b; background-color: #ffebeb; border-radius: 10px; color: black;'> 
                <h2>辨識中...</h2>
                <p>等待分析完成...</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 處理中狀態，同時在頂部佔位符顯示提示
    with style_placeholder.container():
        st.info("泳姿分析中...")
    with stroke_placeholder.container():
        st.info("划手次數分析中...")
    with split_placeholder.container():
        st.info("分段計時分析中...")

    # -------------------------------------------------------
    # 🎯 關鍵：在主腳本中執行分析 (這裡會阻塞 UI)
    # -------------------------------------------------------
    try:
        temp_video_path = st.session_state.temp_video_path

        # 運行分析
        results = run_full_analysis(
            POSE_MODEL_PATH,
            STYLE_MODEL_PATH,
            temp_video_path,
            OUTPUT_DIR,
            FFMPEG_EXECUTABLE_PATH,
            status_callback=dummy_status_callback,
        )

        # 分析完成，設置結果並觸發最後一次 RERUN
        st.session_state.page_state = "complete"
        st.session_state.final_results = results
        st.session_state.processed_video_path = results.get("processed_video_path")

        # 清理暫存檔案 (可選)
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)

        # 最終 RERUN，顯示結果
        st.rerun()

    except Exception as e:
        # 錯誤處理
        st.session_state.page_state = "initial"
        st.session_state.error_message = f"❌ **分析在內部崩潰！請檢查以下錯誤：**\n{traceback.format_exc()}\n主要錯誤訊息: {e}"
        st.rerun()

elif st.session_state.page_state == "complete":
    # 🎯 狀態 2: 顯示結果
    results = st.session_state.final_results

    with video_and_log_placeholder.container():
        video_path = st.session_state.processed_video_path

        if video_path and os.path.exists(video_path):
            st.video(video_path, format="video/mp4")
        else:
            st.error(
                "Processed video not found. 請檢查 run_full_analysis 是否回傳有效路徑。"
            )
else:
    # 狀態 3: 初始畫面
    with video_and_log_placeholder.container():
        st.markdown(
            """
            <div style='text-align: center; padding: 150px 0; background-color: #f0f2f6; border-radius: 10px; color: black;'>
                <h2>等待錄製影片...
            </div>
            """,
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------------------
# 🎯 V. 核心指標區塊 (Metric 邏輯)
# --------------------------------------------------------------------------

if st.session_state.page_state == "complete" and st.session_state.final_results:
    results = st.session_state.final_results

    # 1. 泳姿 (col_style)
    with style_placeholder.container():
        english_style = results.get("stroke_style", "N/A").capitalize()
        chinese_style = SWIM_STROKES_TRANSLATION.get(english_style, english_style)
        st.markdown(f"## **泳姿:** {chinese_style}")

    # 2. 划手次數 (col_stroke)
    with stroke_placeholder.container():
        st.markdown("## 划手次數")
        stroke_result = results.get("stroke_result", {})
        # 使用 H4 級別顯示次數
        st.markdown(
            f"#### **去程:** {stroke_result.get('range1_recovery_count', 0)} 次"
        )
        st.markdown(
            f"#### **回程:** {stroke_result.get('range2_recovery_count', 0)} 次"
        )

    # 3. 分段計時 (col_split)
    with split_placeholder.container():
        st.markdown("### 分段計時 (秒)")

        passed_frames = results.get("passed", {})
        fps_val = results.get("fps", 30.0)
        diving_segments = results.get("diving_segments", {})
        start_frame_val = diving_segments.get("s1", 0)

        time_data_list = []

        if passed_frames and start_frame_val is not None and fps_val > 0:
            for k, frame in passed_frames.items():
                if frame is not None and frame > start_frame_val:
                    distance = k.replace("_frame", "").upper()
                    time_sec = (frame - start_frame_val) / fps_val
                    # 使用 H4 標籤輸出 "距離M : 時間 s" 格式
                    time_data_list.append(f"#### {distance}  :  **{time_sec:.2f} s**")

        if time_data_list:
            for item in time_data_list:
                st.markdown(item)
        else:
            st.info("無有效分段計時數據。")

# 🎯 處理 'processing' 和其他狀態的佔位符 (防止內容殘留)
elif st.session_state.page_state == "processing":
    pass
else:
    # 初始狀態，確保佔位符被清空
    style_placeholder.empty()
    stroke_placeholder.empty()
    split_placeholder.empty()

col_waveform = st.container()

# --------------------------------------------------------------------------
# 🎯 VI. 波形圖區塊 (col_waveform) - Tab 結構
# --------------------------------------------------------------------------
with col_waveform:

    if st.session_state.page_state == "complete" and st.session_state.final_results:
        results = st.session_state.final_results
        stroke_figs = results.get("stroke_plot_figs", {})

        # --- 步驟 1: 定義七個切換標籤 (包含標題 Tab) ---
        tab_titles = [
            "划水階段變化圖 / 潛泳踢腿角度曲線圖",  # 🎯 標題作為第一個 Tab 名稱
            "去程 肩膀",
            "去程 手腕",
            "去程 踢腿",
            "回程 肩膀",
            "回程 手腕",
            "回程 踢腿",
        ]

        # 創建 tabs 容器
        tabs = st.tabs(tab_titles)

        # --- 獲取圖表數據 ---
        range1_data = stroke_figs.get("range1", {})
        range2_data = stroke_figs.get("range2", {})
        kick_fig_1 = results.get("kick_angle_fig_1")
        kick_fig_2 = results.get("kick_angle_fig_2")

        # 1. 標題 Tab (tabs[0]) - 總結
        with tabs[0]:
            st.markdown("### ")

        # 2. 去程 肩膀 (tabs[1])
        with tabs[1]:
            display_matplotlib_fig(range1_data.get("shoulder_fig"))

        # 3. 去程 手腕 (tabs[2])
        with tabs[2]:
            display_matplotlib_fig(range1_data.get("wrist_fig"))

        # 4. 去程 踢腿 (tabs[3])
        with tabs[3]:
            display_matplotlib_fig(kick_fig_1)

        # 5. 回程 肩膀 (tabs[4])
        with tabs[4]:
            display_matplotlib_fig(range2_data.get("shoulder_fig"))

        # 6. 回程 手腕 (tabs[5])
        with tabs[5]:
            display_matplotlib_fig(range2_data.get("wrist_fig"))

        # 7. 回程 踢腿 (tabs[6])
        with tabs[6]:
            display_matplotlib_fig(kick_fig_2)

    elif st.session_state.page_state == "processing":
        st.info("請等待分析完成以顯示圖表...")
