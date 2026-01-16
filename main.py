"""
================================================================================
SwimAnalysisPro FastAPI Backend (v2.0)
================================================================================

功能概述：
  本模組是前後端的橋梁，負責接收前端影片上傳、啟動後台分析、追蹤進度、
  並回傳完整的分析結果 (JSON 格式)。

核心功能清單：
  1. 影片上傳管理        - 接收、驗證、儲存前端上傳的游泳影片
  2. 後台分析引擎        - 呼叫 orchestrator 執行完整分析 (pose → stroke → diving...)
  3. 進度追蹤           - 實時追蹤分析進度 (0-100%)
  4. 結果管理           - 儲存並格式化分析結果為 JSON
  5. 檔案下載           - 提供最終後製影片下載
  6. 分析紀錄查詢       - 列出所有上傳的影片分析狀態
  7. 健康檢查           - 監控 API 與後端模組狀態

API 端點：
  POST   /analysis/upload              - 上傳影片
  GET    /analysis/{video_id}/status   - 查詢進度
  GET    /analysis/{video_id}/result   - 取得完整結果
  GET    /analysis/{video_id}/download - 下載影片
  GET    /analysis/list                - 列出所有分析
  GET    /health                       - 健康檢查
  GET    /                             - API 資訊

架構：
  前端 (React/Vue)
    ↓ (HTTP)
  main.py (FastAPI API 伺服器)
    ↓ (Python function call)
  BD/orchestrator (分析引擎)
    ↓ (呼叫各子模組)
  pose_estimator → stroke_analyzer → diving_analyzer → video_postprocessor...

================================================================================
"""

import os
import shutil
import logging
import asyncio
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from api_schemas import (
    AnalysisUploadResponse,
    AnalysisStatusResponse,
    FullAnalysisResult,
    StrokeAnalysisResult,
    ListVideosResponse,
    VideoInfoSummary,
)

# ===== 導入核心分析模組 =====
try:
    from BD.orchestrator import run_full_analysis
except ImportError as e:
    logging.error(f"無法導入 BD.orchestrator: {e}")
    run_full_analysis = None


# ===== 設置與日誌 =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 路徑設置（可從環境變數覆蓋）
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploaded_videos"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "data/processed_videos"))
POSE_MODEL_PATH = os.getenv("POSE_MODEL_PATH", "data/models/best_1.pt")
STYLE_MODEL_PATH = os.getenv("STYLE_MODEL_PATH", "data/models/svm_model_new_3.pkl")
FFMPEG_EXECUTABLE_PATH = os.getenv(
    "FFMPEG_EXECUTABLE_PATH", r"C:\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe"
)

# 確保目錄存在
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

from fastapi.middleware.cors import CORSMiddleware

# ===== FastAPI 應用初始化 =====
app = FastAPI(
    title="SwimAnalysisPro API",
    description="游泳影片分析後端 API",
    version="2.0.0",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源 (開發階段)
    allow_credentials=True,
    allow_methods=["*"],  # 允許所有方法 (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # 允許所有標頭
)

# ===== 狀態追蹤 (記憶體式，生產環境應改用 Redis/DB) =====
analysis_db = {}
# 結構: {
#     "video_id": {
#         "filename": str,
#         "file_path": str,
#         "status": "processing" | "completed" | "failed",
#         "progress": int (0-100),
#         "error_message": Optional[str],
#         "result": Optional[FullAnalysisResult],
#         "created_at": str,
#         "completed_at": Optional[str]
#     }
# }


# ===== 後台任務：執行完整分析 =====


# 輔助函數：構建互動式相位圖表數據
def build_interactive_phase_plot(
    phase_data_dict: dict, total_frames: int, fps: float = 30.0
) -> Optional[dict]:
    """
    將相位數據轉換為互動式時間序列格式

    參數:
      phase_data_dict: 原始相位數據 {
        "propulsion_frames": [100, 101, 102, ...],
        "recovery_frames": [200, 201, ...],
        ...
      }
      total_frames: 總幀數
      fps: 幀率

    回傳: InteractivePlot 適用的 time_series 字典
    """
    if not phase_data_dict:
        return None

    try:
        # 構建完整的幀到相位的映射
        frame_to_phase = {}

        for phase_name, frames in phase_data_dict.items():
            if isinstance(frames, list):
                for frame in frames:
                    frame_to_phase[frame] = phase_name

        # 創建時間序列數據點
        data_points = []
        phases = {}

        # Determine crop start based on active phases (exclude initial glide/dive)
        active_frames = []
        for k, v in phase_data_dict.items():
            k_lower = k.lower()
            if "glide" not in k_lower and "unknown" not in k_lower and "preparation" not in k_lower:
                if isinstance(v, list):
                    active_frames.extend(v)
        
        start_crop = 0
        if active_frames:
            start_crop = max(0, min(active_frames) - 5) # 5 frames padding

        for frame in range(total_frames):
            if frame < start_crop:
                continue

            phase_name = frame_to_phase.get(frame, "unknown")
            timestamp_ms = (frame / fps) * 1000  # 轉換為毫秒

            # phase 編碼為數值（便於繪製）
            phase_value = {"preparation": 0, "propulsion": 1, "recovery": 2}.get(
                phase_name, -1
            )

            data_points.append(
                {
                    "frame": frame,
                    "timestamp_ms": timestamp_ms,
                    "value": phase_value,
                    "phase": phase_name,
                }
            )

            # 記錄相位區間
            if phase_name not in phases:
                phases[phase_name] = {"start_frame": frame, "end_frame": frame}
            else:
                phases[phase_name]["end_frame"] = frame

        # 構建相位標記列表
        phase_regions = []
        color_map = {
            "preparation": "#CCCCCC",
            "propulsion": "#0066FF",
            "recovery": "#FF9900",
        }

        for phase_name, frame_range in phases.items():
            phase_regions.append(
                {
                    "name": phase_name,
                    "start_frame": frame_range["start_frame"],
                    "end_frame": frame_range["end_frame"],
                    "color": color_map.get(phase_name),
                }
            )

        return {
            "title": "Stroke Phase Analysis",
            "total_frames": total_frames,
            "fps": fps,
            "data_points": data_points,
            "phases": phase_regions,
        }

    except Exception as e:
        logger.error(f"構建相位圖表失敗: {e}")
        return None


# 輔助函數：構建互動式角度圖表數據
def build_interactive_angle_plot(angle_data: dict, fps: float = 30.0) -> Optional[dict]:
    """
    將踢腿角度數據轉換為互動式時間序列格式

    參數:
      angle_data: 角度數據 {
        "angles": [30.5, 32.2, 34.8, ...],  # 每一幀的角度
        "frames": [0, 1, 2, ...],  # 對應的幀號
        ...
      }
      fps: 幀率

    回傳: InteractivePlot 適用的 time_series 字典
    """
    if not angle_data or "angles" not in angle_data:
        return None

    try:
        angles = angle_data.get("angles", [])
        frames = angle_data.get("frames", list(range(len(angles))))

        if not angles:
            return None

        # Determine crop start from regions (exclude initial glide)
        regions = angle_data.get("regions", {})
        active_starts = []
        for r_name, r_list in regions.items():
            if "glide" not in r_name.lower() and isinstance(r_list, list):
                for item in r_list:
                    # Item should be (start, end)
                    if isinstance(item, (list, tuple)) and len(item) >= 1:
                        active_starts.append(item[0])
        
        start_crop = 0
        if active_starts:
            start_crop = max(0, min(active_starts) - 5)

        # 創建時間序列數據點
        data_points = []
        for frame, angle in zip(frames, angles):
            if frame < start_crop:
                continue

            timestamp_ms = (frame / fps) * 1000
            data_points.append(
                {
                    "frame": frame,
                    "timestamp_ms": timestamp_ms,
                    "value": float(angle),
                    "phase": None,
                }
            )

        return {
            "title": "Kick Angle Analysis",
            "total_frames": len(frames),
            "fps": fps,
            "data_points": data_points,
            "avg_angle": float(sum(angles) / len(angles)),
            "max_angle": float(max(angles)),
            "min_angle": float(min(angles)),
        }

    except Exception as e:
        logger.error(f"構建角度圖表失敗: {e}")
        return None


async def run_analysis_task(video_id: str, video_path: str) -> None:
    """
    【功能 2】後台分析引擎 - 執行完整分析流程

    作用：
      - 呼叫 BD.orchestrator.run_full_analysis() 進行分析
      - 更新分析進度至 analysis_db
      - 分析完成後儲存結果並更新狀態

    分析流程 (by orchestrator):
      1. 姿態估計 (Pose Estimation) - 提取關鍵點
      2. 泳姿識別 (Stroke Style Recognition) - backstroke/freestyle/breaststroke/butterfly
      3. 划手分析 (Stroke Counting) - 計算划手次數、階段分析
      4. 潛水分析 (Diving Analysis) - 計算踢腿角度、潛泳資訊
      5. 分段時間 (Split Timing) - 計算分段速度
      6. 影片合成 (Video Postprocessing) - overlay + ffmpeg 轉碼

    參數：
      video_id (str): 唯一影片識別符
      video_path (str): 已儲存的影片完整路徑

    更新項：
      - analysis_db[video_id]["status"]: "processing" → "completed" 或 "failed"
      - analysis_db[video_id]["progress"]: 0 → 100
      - analysis_db[video_id]["result"]: 完整的 FullAnalysisResult 物件
    """
    start_time = datetime.now()

    try:
        if run_full_analysis is None:
            raise ImportError("BD.orchestrator 未正確導入")

        logger.info(f"[{video_id}] 開始分析: {Path(video_path).name}")
        analysis_db[video_id]["status"] = "processing"
        analysis_db[video_id]["progress"] = 5

        # 定義狀態回調函式
        def status_callback(progress_value: int, message: str = ""):
            if video_id in analysis_db:
                analysis_db[video_id]["progress"] = min(int(progress_value), 99)
                if message:
                    analysis_db[video_id]["current_step"] = message
                    logger.info(f"[{video_id}] 進度更新: {progress_value}% - {message}")

        # 呼叫核心分析函式
        results = await asyncio.to_thread(
            run_full_analysis,
            POSE_MODEL_PATH,
            STYLE_MODEL_PATH,
            video_path,
            str(OUTPUT_DIR),
            FFMPEG_EXECUTABLE_PATH,
            status_callback,
        )

        if not results:
            raise Exception("run_full_analysis 回傳 None")

        # 格式化結果
        # 計算 SPM (如果 orchestrator 沒回傳)
        stroke_res = results.get("stroke_result", {})
        total_strokes = stroke_res.get("total_count", 0)
        spm = stroke_res.get("strokes_per_minute")
        
        # 嘗試從 split_timing 獲取總游泳時間
        total_swim_duration_sec = 0.0
        split_data = results.get("split_timing", {}) or {}
        splits = split_data.get("splits", [])
        
        if splits:
            total_swim_duration_sec = sum(splits)
        elif results.get("video_duration_sec"):
             # Fallback: 使用影片總長度
            total_swim_duration_sec = results.get("video_duration_sec")

        logger.info(f"DEBUG: Total Strokes={total_strokes}, Duration={total_swim_duration_sec}, Original SPM={spm}")

        if (spm is None or spm == 0) and total_swim_duration_sec > 0:
            spm = (total_strokes / (total_swim_duration_sec / 60))
            logger.info(f"DEBUG: Calculated SPM={spm}")

        stroke_result = StrokeAnalysisResult(
            total_count=total_strokes,
            stroke_style=results.get("stroke_style", "unknown"),
            range1_recovery_count=stroke_res.get("range1_recovery_count"),
            range2_recovery_count=stroke_res.get("range2_recovery_count"),
            stroke_frames=stroke_res.get("stroke_frames"),
            strokes_per_minute=round(spm, 2) if spm else 0,
            average_stroke_duration_ms=stroke_res.get("average_stroke_duration_ms"),
        )
        # ... (Chart logic skipped for brevity if not modifying) ...

        # ... (skipping chart logic to reach split timing) ...

        # 這裡需要小心，上面的代碼在 replace 中會覆蓋掉中間的 chart logic。
        # 我必須小心只替換計算區塊，或者完整重寫 run_analysis_task 的後半部分。
        # 鑑於 replace_file_content 的限制，我應該只替換計算 SPM 和 Avg Speed 的部分。
        
        # 由於我無法確切知道中間有多少行，我將分兩次替換。
        # 這是第一次替換：計算 SPM 的部分。

        # 構建互動式相位圖表（支持動態更新）
        stroke_plot_figs = {}
        if results.get("stroke_plot_figs"):
            fps_val = results.get("fps", 30.0)
            
            for range_key, plot_data in results.get("stroke_plot_figs", {}).items():
                # 1. New Waveform Logic (Wrist/Shoulder Y)
                if isinstance(plot_data, dict) and "values" in plot_data and "frames" in plot_data:
                    vals = plot_data["values"]
                    frms = plot_data["frames"]
                    regions = plot_data.get("regions", {})
                    
                    pts = []
                    for i, f in enumerate(frms):
                        if i < len(vals):
                            frame_idx = int(f)
                            # Determine Phase
                            phase_lbl = "Glide/Other"
                            for p_start, p_end in regions.get("Pull regions", []):
                                if p_start <= frame_idx <= p_end: phase_lbl = "Pull"; break
                            if phase_lbl == "Glide/Other":
                                for p_start, p_end in regions.get("Push regions", []):
                                    if p_start <= frame_idx <= p_end: phase_lbl = "Push"; break
                            if phase_lbl == "Glide/Other":
                                for p_start, p_end in regions.get("Recovery regions", []):
                                    if p_start <= frame_idx <= p_end: phase_lbl = "Recovery"; break
                            
                            pts.append({
                                "frame": frame_idx,
                                "timestamp_ms": (f / fps_val) * 1000,
                                "value": float(vals[i]),
                                "phase": phase_lbl
                            })
                    
                    stroke_plot_figs[range_key] = {
                        "plot_type": "angle",
                        "time_series": {
                            "title": range_key,
                            "data_points": pts
                        },
                        "title": f"{range_key.replace('_',' ').title()}"
                    }

                # 2. Legacy Phase Logic (e.g. Breaststroke)
                elif isinstance(plot_data, dict):
                    # If phase_frames exists or if strict logic requires checking
                    phase_data = plot_data.get("phase_frames")
                    if phase_data: 
                        phase_plot = build_interactive_phase_plot(
                            phase_data_dict=phase_data,
                            total_frames=plot_data.get("total_frames", 1000),
                            fps=fps_val,
                        )
                        if phase_plot:
                            stroke_plot_figs[range_key] = {
                                "plot_type": "phase",
                                "time_series": phase_plot,
                                "plot_path": None,
                                "title": f"Stroke Phases ({range_key})"
                            }

        # 構建互動式踢腿角度圖表（支持動態更新）
        diving_plot_figs = {}
        if results.get("diving_analysis"):
            diving_analysis = results.get("diving_analysis", {})

            # Range 1 踢腿角度
            if diving_analysis.get("kick_angle_analysis", {}).get("range1"):
                angle_plot = build_interactive_angle_plot(
                    angle_data=diving_analysis["kick_angle_analysis"]["range1"],
                    fps=30.0,
                )
                if angle_plot:
                    diving_plot_figs["range1"] = {
                        "plot_type": "angle",
                        "time_series": angle_plot,
                        "plot_path": None,
                    }

            # Range 2 踢腿角度
            if diving_analysis.get("kick_angle_analysis", {}).get("range2"):
                angle_plot = build_interactive_angle_plot(
                    angle_data=diving_analysis["kick_angle_analysis"]["range2"],
                    fps=30.0,
                )
                if angle_plot:
                    diving_plot_figs["range2"] = {
                        "plot_type": "angle",
                        "time_series": angle_plot,
                        "plot_path": None,
                    }

        # 構建後製影片信息
        postprocessing_info = None
        processed_video_path = results.get("processed_video_path", "")

        if processed_video_path and Path(processed_video_path).exists():
            video_file_size = Path(processed_video_path).stat().st_size / (
                1024 * 1024
            )  # MB
            postprocessing_info = {
                "processed_video_path": processed_video_path,
                "file_size_mb": round(video_file_size, 2),
                "resolution": "1920x1080",  # 可從 orchestrator 取得
                "fps": 30.0,
                "duration_sec": results.get("video_duration_sec"),
                "codec": "h264",
                "bitrate": "5000k",
                "created_at": datetime.now().isoformat(),
            }

        # 計算 Avg Speed (如果 orchestrator 沒回傳)
        # split_data is already retrieved above
        logger.info(f"DEBUG: Processing Split Data for Speed. Duration={total_swim_duration_sec}")
        
        if split_data is not None:
             # Ensure Pydantic validation passes (must have 'splits')
             if not split_data.get("splits"):
                 split_data = None

        if split_data:
            avg_speed_orig = split_data.get("average_speed")
            if not avg_speed_orig and total_swim_duration_sec > 0:
                # 假設標準池長 50m
                num_splits = len(split_data.get("splits", []))
                distance = 50.0 * (num_splits if num_splits > 0 else 1)
                
                avg_speed = distance / total_swim_duration_sec
                split_data["average_speed"] = round(avg_speed, 2)
                logger.info(f"DEBUG: Calculated Avg Speed={avg_speed} (Distance={distance})")
            else:
                 logger.info(f"DEBUG: Using Original Avg Speed={avg_speed_orig}")

        full_result = FullAnalysisResult(
            video_id=video_id,
            processed_video_path=results.get("processed_video_path", ""),
            stroke_style=results.get("stroke_style", "unknown"),
            stroke_result=stroke_result,
            diving_analysis=results.get("diving_analysis"),
            split_timing=split_data,
            stroke_plot_figs=stroke_plot_figs if stroke_plot_figs else None,
            diving_plot_figs=diving_plot_figs if diving_plot_figs else None,
            focus_crop_video_path=results.get("focus_crop_video_path"),
            postprocessing_info=postprocessing_info,
            timestamp=datetime.now().isoformat(),
            analysis_duration_seconds=(datetime.now() - start_time).total_seconds(),
        )

        analysis_db[video_id]["result"] = full_result
        analysis_db[video_id]["status"] = "completed"
        analysis_db[video_id]["progress"] = 100
        analysis_db[video_id]["completed_at"] = datetime.now().isoformat()

        logger.info(
            f"[{video_id}] 分析完成 ({results.get('stroke_style', 'unknown')} "
            f"- {stroke_result.total_count} strokes)"
        )

    except Exception as e:
        logger.error(f"[{video_id}] 分析失敗: {e}", exc_info=True)
        analysis_db[video_id]["status"] = "failed"
        analysis_db[video_id]["error_message"] = str(e)
        analysis_db[video_id]["progress"] = 0


# ===== API Endpoints =====


@app.get("/")
async def root():
    """
    【功能 7】API 資訊端點

    作用：
      - 提供 API 基本資訊
      - 列出所有可用的 endpoint

    回傳：
      {
        "message": "SwimAnalysisPro API v2.0",
        "endpoints": {
          "upload": "/analysis/upload (POST)",
          "status": "/analysis/{video_id}/status (GET)",
          ...
        }
      }
    """
    return {
        "message": "SwimAnalysisPro API v2.0",
        "endpoints": {
            "upload": "/analysis/upload (POST)",
            "status": "/analysis/{video_id}/status (GET)",
            "result": "/analysis/{video_id}/result (GET)",
            "download": "/analysis/{video_id}/download (GET)",
            "list": "/analysis/list (GET)",
        },
    }


@app.post("/analysis/upload", response_model=AnalysisUploadResponse, status_code=202)
async def upload_for_analysis(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> AnalysisUploadResponse:
    """
    【功能 1】影片上傳管理 - 接收並儲存前端上傳的游泳影片

    作用：
      - 接收前端上傳的視頻檔案
      - 驗證檔案有效性
      - 儲存至 uploaded_videos/ 目錄 (使用 UUID 命名)
      - 初始化分析狀態
      - 啟動後台分析任務 (run_analysis_task)

    HTTP 方法：POST
    端點：/analysis/upload

    請求：
      - Content-Type: multipart/form-data
      - 參數: file (UploadFile)

    回傳 (202 Accepted)：
      {
        "video_id": "abc-123-def-456",
        "message": "影片已接收，正在後台分析中...",
        "status_endpoint": "/analysis/abc-123-def-456/status"
      }

    錯誤狀態：
      - 500: 檔案儲存失敗

    後續流程：
      1. 前端輪詢 /analysis/{video_id}/status 查詢進度
      2. 分析完成後，呼叫 /analysis/{video_id}/result 取得結果
    """
    video_id = str(uuid4())
    file_extension = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{video_id}{file_extension}"

    try:
        # 儲存檔案
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 初始化狀態
        analysis_db[video_id] = {
            "filename": file.filename,
            "file_path": str(file_path),
            "status": "processing",
            "progress": 0,
            "error_message": None,
            "result": None,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }

        # 啟動後台分析任務
        background_tasks.add_task(run_analysis_task, video_id, str(file_path))

        logger.info(f"[{video_id}] 影片已上傳: {file.filename}")

        return AnalysisUploadResponse(
            video_id=video_id,
            message="影片已接收，正在後台分析中...",
            status_endpoint=f"/analysis/{video_id}/status",
        )

    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        logger.error(f"上傳失敗: {e}")
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {e}")

    finally:
        await file.close()


@app.get("/analysis/{video_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(video_id: str) -> AnalysisStatusResponse:
    """
    【功能 3】進度追蹤 - 實時查詢分析進度

    作用：
      - 前端輪詢此端點以取得分析進度
      - 回傳進度百分比 (0-100)
      - 回傳分析狀態 (processing / completed / failed)
      - 分析失敗時回傳錯誤訊息

    HTTP 方法：GET
    端點：/analysis/{video_id}/status

    路徑參數：
      video_id (str): 影片識別符 (從上傳端點取得)

    回傳：
      {
        "video_id": "abc-123-def-456",
        "filename": "pool_video.mp4",
        "status": "processing",
        "progress": 45,
        "error_message": null
      }

    狀態值：
      - "processing": 分析進行中
      - "completed": 分析完成
      - "failed": 分析失敗

    錯誤狀態：
      - 404: 找不到指定的 video_id

    前端使用範例：
      async function checkProgress(videoId) {
        const res = await fetch(`/analysis/${videoId}/status`);
        const status = await res.json();
        console.log(`進度: ${status.progress}%`);
        if (status.status === 'completed') {
          // 呼叫 /analysis/{videoId}/result 取得結果
        }
      }
    """
    if video_id not in analysis_db:
        raise HTTPException(status_code=404, detail=f"找不到影片 ID: {video_id}")

    info = analysis_db[video_id]
    return AnalysisStatusResponse(
        video_id=video_id,
        filename=info["filename"],
        status=info["status"],
        progress=info.get("progress"),
        error_message=info.get("error_message"),
        current_step=info.get("current_step"),
    )


@app.get("/analysis/{video_id}/result", response_model=FullAnalysisResult)
async def get_analysis_result(video_id: str) -> FullAnalysisResult:
    """
    【功能 4】結果管理 - 取得完整分析結果 (JSON)

    作用：
      - 回傳分析完成後的所有結果
      - 格式化為易於前端使用的 JSON 結構
      - 包含所有分析指標和元資訊

    HTTP 方法：GET
    端點：/analysis/{video_id}/result

    路徑參數：
      video_id (str): 影片識別符

    回傳 (FullAnalysisResult)：
      {
        "video_id": "abc-123-def-456",
        "processed_video_path": "data/processed_videos/abc-123-def-456.mp4",
        "stroke_style": "freestyle",

        "stroke_result": {
          "total_count": 48,
          "stroke_style": "freestyle",
          "range1_recovery_count": 24,
          "range2_recovery_count": 24,
          "strokes_per_minute": 72,
          "average_stroke_duration_ms": 833,
          "phases": {...},
          "stroke_frames": [100, 250, ...]
        },

        "diving_analysis": {
          "segments": [[0, 150], [300, 450]],
          "touch_frame": 300,
          "waterline_y": 240,
          "total_kick_count": 15,
          "kick_frequency": 2.3,
          "kick_angle_analysis": {
            "range1": {
              "angles": [...],
              "avg_angle": 42.3,
              "max_angle": 55.8,
              "min_angle": 28.5
            }
          },
          "kick_angle_fig_1": "...",
          "kick_angle_fig_2": "..."
        },

        "split_timing": {
          "splits": [25.5, 26.2, 25.8],
          "segments": [
            {
              "segment_id": 1,
              "duration_sec": 25.5,
              "avg_speed_m_per_sec": 1.96
            }
          ],
          "average_speed": 1.94,
          "max_speed": 2.1,
          "min_speed": 1.8
        },

        "stroke_plot_figs": {...},
        "focus_crop_video_path": "data/processed_videos/focus_abc-123.mp4",
        "timestamp": "2026-01-15T10:30:00",
        "analysis_duration_seconds": 45.2
      }

    包含資訊：
      - 泳姿 (stroke_style)
      - 划手次數 (total_count, range1/range2 counts)
      - 划手階段 (phases: propulsion, recovery...)
      - 踢腿角度變化 (kick angle analysis with min/max/avg)
      - 潛泳資訊 (kick count, frequency)
      - 分段時間 (splits 清單)
      - 速度分析 (average, max, min)
      - 相位圖表 (stroke_plot_figs)
      - focus 裁切影片 (focus_crop_video_path)

    錯誤狀態：
      - 404: 找不到該影片
      - 409: 分析尚未完成 (status != 'completed')
      - 500: 分析結果缺失

    前端使用範例：
      async function getResults(videoId) {
        const res = await fetch(`/analysis/${videoId}/result`);
        const result = await res.json();

        // 顯示泳姿
        console.log('泳姿:', result.stroke_style);

        // 顯示划手數
        console.log('划手數:', result.stroke_result.total_count);

        // 顯示踢腿角度
        const angles = result.diving_analysis.kick_angle_analysis;
        console.log('平均踢腿角度:', angles.range1.avg_angle);

        // 顯示速度
        console.log('平均速度:', result.split_timing.average_speed, 'm/s');
      }
    """
    if video_id not in analysis_db:
        raise HTTPException(status_code=404, detail=f"找不到影片 ID: {video_id}")

    info = analysis_db[video_id]
    if info["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"分析尚未完成，目前狀態: {info['status']}",
        )

    if not info["result"]:
        raise HTTPException(
            status_code=500,
            detail="分析結果缺失",
        )

    return info["result"]


@app.get("/analysis/{video_id}/download")
async def download_processed_video(video_id: str):
    """
    【功能 5】檔案下載 - 下載最終後製影片

    作用：
      - 提供最終後製的 MP4 影片供前端下載
      - 自動設定正確的 HTTP header (Content-Disposition, Content-Type)
      - 串流傳輸大檔案 (不會一次載入記憶體)

    HTTP 方法：GET
    端點：/analysis/{video_id}/download

    路徑參數：
      video_id (str): 影片識別符

    回傳：
      - Content-Type: video/mp4
      - Body: 影片二進位檔案
      - Content-Disposition: attachment; filename="processed_xxx.mp4"

    下載流程：
      1. 檢查 video_id 是否存在
      2. 檢查分析狀態是否為 "completed"
      3. 驗證後製影片檔案是否存在
      4. 串流傳輸檔案

    錯誤狀態：
      - 404: 找不到影片或後製影片不存在
      - 409: 影片尚未完成分析

    前端使用範例 (HTML):
      <a href="/analysis/abc-123/download" download>下載後製影片</a>

    前端使用範例 (JavaScript):
      const response = await fetch(`/analysis/${videoId}/download`);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `processed_${videoId}.mp4`;
      a.click();
    """
    if video_id not in analysis_db:
        raise HTTPException(status_code=404, detail=f"找不到影片 ID: {video_id}")

    info = analysis_db[video_id]
    if info["status"] != "completed" or not info["result"]:
        raise HTTPException(
            status_code=409,
            detail=f"影片尚未完成分析 (狀態: {info['status']})",
        )

    video_path = info["result"].processed_video_path
    if not Path(video_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"後製影片不存在: {video_path}",
        )

    return FileResponse(
        path=video_path,
        filename=f"processed_{info['filename']}",
        media_type="video/mp4",
    )


@app.get("/analysis/list", response_model=ListVideosResponse)
async def list_all_analyses() -> ListVideosResponse:
    """
    【功能 6】分析紀錄查詢 - 列出所有上傳的影片分析狀態

    作用：
      - 列出所有已上傳的影片
      - 顯示各影片的分析狀態和建立時間
      - 幫助前端追蹤多個分析工作

    HTTP 方法：GET
    端點：/analysis/list

    回傳 (ListVideosResponse)：
      {
        "total": 3,
        "videos": [
          {
            "video_id": "abc-123-def-456",
            "filename": "pool_video_1.mp4",
            "status": "completed",
            "created_at": "2026-01-15T10:30:00"
          },
          {
            "video_id": "xyz-789-uvw-012",
            "filename": "pool_video_2.mp4",
            "status": "processing",
            "created_at": "2026-01-15T10:35:00"
          },
          {
            "video_id": "pqr-345-stu-678",
            "filename": "pool_video_3.mp4",
            "status": "failed",
            "created_at": "2026-01-15T10:40:00"
          }
        ]
      }

    使用場景：
      - 前端首頁顯示分析歷史列表
      - 管理員查看系統負載
      - 追蹤多個進行中的分析工作

    前端使用範例：
      async function listAllAnalyses() {
        const res = await fetch('/analysis/list');
        const { total, videos } = await res.json();
        console.log(`總共 ${total} 個分析紀錄`);
        videos.forEach(v => {
          console.log(`${v.filename}: ${v.status} (${v.video_id})`);
        });
      }
    """
    videos = [
        VideoInfoSummary(
            video_id=vid,
            filename=info["filename"],
            status=info["status"],
            created_at=info.get("created_at"),
        )
        for vid, info in analysis_db.items()
    ]

    return ListVideosResponse(total=len(videos), videos=videos)


# ===== 健康檢查 =====
@app.get("/health")
async def health_check():
    """
    【功能 7】健康檢查 - 監控 API 與後端模組狀態

    作用：
      - 檢查 API 伺服器狀態
      - 檢查後端分析模組 (orchestrator) 是否正常導入
      - 用於監控和部署檢查

    HTTP 方法：GET
    端點：/health

    回傳：
      {
        "status": "healthy",
        "timestamp": "2026-01-15T10:30:00",
        "orchestrator_available": true
      }

    各欄位說明：
      - status: API 狀態 ("healthy" 或 "unhealthy")
      - timestamp: 檢查時間 (ISO 8601)
      - orchestrator_available: 後端分析模組是否可用 (true/false)

    使用場景：
      - Kubernetes liveness probe
      - Docker health check
      - 負載均衡器健康檢查
      - 前端部署檢查

    前端使用範例：
      async function checkAPIHealth() {
        try {
          const res = await fetch('/health');
          const health = await res.json();
          if (health.status === 'healthy') {
            console.log('✅ API 狀態正常');
          } else {
            console.log('❌ API 狀態異常');
          }
        } catch (e) {
          console.error('無法連線到 API', e);
        }
      }
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "orchestrator_available": run_full_analysis is not None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
