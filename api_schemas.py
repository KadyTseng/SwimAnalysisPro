"""
API Response Schemas for Frontend Integration
定義所有前端串接用的 JSON 格式 (Pydantic models)
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


# ===== 上傳與狀態管理 =====


class AnalysisUploadResponse(BaseModel):
    """上傳影片回應 (202 Accepted)"""

    video_id: str
    message: str
    status_endpoint: str


class AnalysisStatusResponse(BaseModel):
    """分析狀態回應"""

    video_id: str
    filename: str
    status: str  # "processing" | "completed" | "failed"
    progress: Optional[int] = None  # 0-100
    error_message: Optional[str] = None
    current_step: Optional[str] = None # Added for detailed step tracking


# ===== 分析結果 (細項) =====


class StrokePhaseInfo(BaseModel):
    """單次筆劃的相位信息"""

    phase_name: str  # "propulsion" | "recovery" 等
    start_frame: int
    end_frame: int
    duration_ms: Optional[float] = None


class StrokeAnalysisResult(BaseModel):
    """游泳筆劃分析結果"""

    total_count: int  # 總游泳次數
    stroke_style: str  # "backstroke" | "breaststroke" | "freestyle" | "butterfly"

    # 詳細划手分析
    range1_recovery_count: Optional[int] = None  # 去程划手次數
    range2_recovery_count: Optional[int] = None  # 回程划手次數
    stroke_frames: Optional[List[int]] = None  # 標記幀列表

    # 階段分析 (可展開每個階段的詳細信息)
    phases: Optional[Dict[str, List[StrokePhaseInfo]]] = (
        None  # {range1: [...], range2: [...]}
    )

    # 划手節奏
    strokes_per_minute: Optional[float] = None  # SPM (Strokes Per Minute)
    average_stroke_duration_ms: Optional[float] = None  # 平均筆劃耗時

    # 擴展欄位 (未來可新增其他分析)
    metadata: Optional[Dict[str, Any]] = None


class KickAngleData(BaseModel):
    """踢腿角度數據"""

    frame: int
    angle_degrees: float  # 角度 (度數)
    angle_velocity: Optional[float] = None  # 角速度
    timestamp_ms: Optional[float] = None


class DivingAnalysisResult(BaseModel):
    """跳水與潛泳分析結果"""

    # 基本分段
    segments: List[tuple]  # [(s1, e1), (s2, e2)] — dive frames
    touch_frame: Optional[int] = None  # 碰牆幀
    waterline_y: Optional[int] = None  # 水線位置

    # 踢腿角度變化分析
    kick_angle_analysis: Optional[Dict[str, Any]] = None  # {
    #   "range1": {
    #     "angles": [KickAngleData, ...],
    #     "avg_angle": float,
    #     "max_angle": float,
    #     "min_angle": float
    #   },
    #   "range2": {...}
    # }

    # 圖表路徑 (可序列化或嵌入)
    kick_angle_fig_1: Optional[str] = None  # figure 路徑或 base64
    kick_angle_fig_2: Optional[str] = None

    # 潛泳相關
    total_kick_count: Optional[int] = None  # 總踢腿次數
    kick_frequency: Optional[float] = None  # 踢腿頻率 (kicks/sec)

    # 擴展欄位 (未來可新增其他分析)
    metadata: Optional[Dict[str, Any]] = None


class SplitTimingResult(BaseModel):
    """分段時間分析"""

    splits: List[float]  # 秒數列表
    lap_times: Optional[List[float]] = None

    # 詳細分段資訊
    segments: Optional[List[Dict[str, Any]]] = None  # [
    #   {
    #     "segment_id": 1,
    #     "start_frame": 0,
    #     "end_frame": 150,
    #     "duration_sec": 5.0,
    #     "avg_speed_m_per_sec": 1.8
    #   },
    #   ...
    # ]

    # 速度分析
    average_speed: Optional[float] = None  # m/s
    max_speed: Optional[float] = None
    min_speed: Optional[float] = None

    # 擴展欄位 (未來可新增其他分析)
    metadata: Optional[Dict[str, Any]] = None


# ===== 圖表數據結構 =====


class PlotPhaseRegion(BaseModel):
    """圖表中的相位區域標記"""

    name: str  # "propulsion", "recovery" 等
    start_frame: int
    end_frame: int
    color: Optional[str] = None  # RGB hex: "#FF0000"


class TimeSeriesDataPoint(BaseModel):
    """時間序列數據點 - 帶幀號的數據（支持動態同步）"""

    frame: int  # 幀號（與影片播放同步）
    timestamp_ms: float  # 時間戳 (毫秒)
    value: float  # 實際數值 (角度、速度等)
    phase: Optional[str] = None  # 可選：當前相位名稱 (propulsion/recovery)


class InteractivePhaseTimeSeries(BaseModel):
    """划手階段時間序列 - 完整影片的相位數據"""

    title: str  # 如 "Range 1 - Stroke Phase"
    total_frames: int  # 影片該區間的總幀數
    fps: float  # 幀率

    # 完整時間序列數據（每一幀一筆，按幀排序）
    # 例如: [
    #   {frame: 0, timestamp_ms: 0, value: 0, phase: "preparation"},
    #   {frame: 1, timestamp_ms: 33.33, value: 0, phase: "preparation"},
    #   {frame: 50, timestamp_ms: 1666.5, value: 1, phase: "propulsion"},
    #   ...
    # ]
    data_points: List[TimeSeriesDataPoint]

    # 相位區域定義（視覺化用）
    phases: Optional[List[PlotPhaseRegion]] = None

    metadata: Optional[Dict[str, Any]] = None


class InteractiveAngleTimeSeries(BaseModel):
    """踢腿角度變化時間序列 - 完整影片的角度數據"""

    title: str  # 如 "Kick Angle - Range 1"
    total_frames: int
    fps: float

    # 完整時間序列數據（每一幀一筆，按幀排序）
    # 例如: [
    #   {frame: 0, timestamp_ms: 0, value: 30.5, phase: null},
    #   {frame: 1, timestamp_ms: 33.33, value: 32.2, phase: null},
    #   ...
    # ]
    data_points: List[TimeSeriesDataPoint]

    # 統計信息
    avg_angle: float  # 平均角度
    max_angle: float  # 最大角度
    min_angle: float  # 最小角度

    metadata: Optional[Dict[str, Any]] = None


class InteractivePlot(BaseModel):
    """互動式圖表 - 支持隨影片動態更新"""

    plot_type: str  # "phase" | "angle" | "custom"

    # 時間序列數據（主要數據來源）
    # 實際類型是 Union[InteractivePhaseTimeSeries, InteractiveAngleTimeSeries]
    time_series: Optional[Dict[str, Any]] = None

    # 備用：靜態 PNG 路徑（如果不用互動式）
    plot_path: Optional[str] = None


# ===== 完整分析結果 =====


class VideoPostprocessingInfo(BaseModel):
    """後製影片信息"""

    processed_video_path: str  # 影片完整路徑
    file_size_mb: Optional[float] = None  # 檔案大小 (MB)
    resolution: Optional[str] = None  # 分辨率，如 "1920x1080"
    fps: Optional[float] = None  # 幀率
    duration_sec: Optional[float] = None  # 影片時長 (秒)
    codec: Optional[str] = None  # 編碼格式，如 "h264"
    bitrate: Optional[str] = None  # 碼率，如 "5000k"
    overlay_info: Optional[Dict[str, Any]] = None  # overlay 標記資訊
    created_at: Optional[str] = None  # 建立時間 (ISO 8601)


class FullAnalysisResult(BaseModel):
    """完整分析結果 (run_full_analysis 回傳)"""

    video_id: str
    processed_video_path: str  # 最終影片路徑
    stroke_style: str  # 泳姿: "backstroke" | "breaststroke" | "freestyle" | "butterfly"

    # === 核心分析結果 ===
    stroke_result: StrokeAnalysisResult  # 筆劃計數、划手次數、階段分析
    diving_analysis: Optional[DivingAnalysisResult] = None  # 跳水、潛泳、踢腿角度
    split_timing: Optional[SplitTimingResult] = None  # 分段時間、速度分析

    # === 可視化與圖表 ===
    stroke_plot_figs: Optional[Dict[str, InteractivePlot]] = (
        None  # 划手階段圖（互動式，隨影片動態更新）
    )
    diving_plot_figs: Optional[Dict[str, InteractivePlot]] = (
        None  # 踢腿角度圖（互動式，隨影片動態更新）
    )
    focus_crop_video_path: Optional[str] = None  # focus crop 影片

    # === 後製影片資訊 ===
    postprocessing_info: Optional[VideoPostprocessingInfo] = None  # 後製影片詳細資訊

    # === 元資訊 ===
    timestamp: str  # ISO 8601 格式
    analysis_duration_seconds: Optional[float] = None  # 分析耗時

    # === 擴展欄位 (未來可新增其他分析如：轉身分析、身體姿態評分等) ===
    advanced_metrics: Optional[Dict[str, Any]] = None  # {
    #   "turn_analysis": {...},
    #   "body_posture_score": {...},
    #   "efficiency_index": {...},
    #   ...
    # }


# ===== 錯誤回應 =====


class ErrorResponse(BaseModel):
    """統一錯誤回應"""

    detail: str
    error_code: Optional[str] = None
    timestamp: str = datetime.now().isoformat()


# ===== 快速查詢 =====


class VideoInfoSummary(BaseModel):
    """影片摘要"""

    video_id: str
    filename: str
    status: str
    created_at: Optional[str] = None


class ListVideosResponse(BaseModel):
    """所有影片清單"""

    total: int
    videos: List[VideoInfoSummary]
