# BD/data_manager.py

import uuid
from typing import Dict, Any, Optional
import os

# ----------------------------------------------------------------------
# 核心狀態儲存區 (模擬資料庫)
# 在生產環境中，這個字典會被替換成 Redis 或 PostgreSQL 來實現持久化儲存。
# ----------------------------------------------------------------------
ANALYSIS_STATUS: Dict[str, Dict[str, Any]] = {}

# 預設狀態碼
STATUS_PENDING = "PENDING"      # 等待開始
STATUS_PROCESSING = "PROCESSING" # 處理中
STATUS_COMPLETED = "COMPLETED"   # 完成
STATUS_FAILED = "FAILED"         # 失敗

# 確保輸出目錄存在
RESULTS_DIR = "data/analysis_results/"
os.makedirs(RESULTS_DIR, exist_ok=True) 

def init_analysis(video_filename: str) -> str:
    """
    初始化分析任務，生成唯一的任務ID，並設定初始狀態。
    
    Args:
        video_filename: 原始影片的檔名。

    Returns:
        task_id: 唯一的任務識別碼 (UUID字串)。
    """
    task_id = str(uuid.uuid4())
    ANALYSIS_STATUS[task_id] = {
        "status": STATUS_PENDING,
        "progress": 0,          
        "filename": video_filename,
        "final_video_path": None,
        "intermediate_data": {},  # 用於儲存 keypoints.txt, 泳姿結果等中間文件路徑
        "error": None,
    }
    print(f"[DATA_MANAGER] 新任務初始化: {task_id[:8]}... 檔案: {video_filename}")
    return task_id

def update_status(
    task_id: str, 
    status: str, 
    progress: Optional[int] = None, 
    final_video_path: Optional[str] = None, 
    error: Optional[str] = None,
    intermediate_data: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
):
    """
    更新特定任務的狀態、進度和結果路徑。
    """
    if task_id in ANALYSIS_STATUS:
        ANALYSIS_STATUS[task_id]["status"] = status
        
        if progress is not None:
            # 確保進度在 0-100 範圍內
            ANALYSIS_STATUS[task_id]["progress"] = max(0, min(100, progress))
            
        if final_video_path is not None:
            ANALYSIS_STATUS[task_id]["final_video_path"] = final_video_path
            
        if error is not None:
            ANALYSIS_STATUS[task_id]["error"] = error
            
        if intermediate_data is not None:
            # 合併新的中間數據
            ANALYSIS_STATUS[task_id]["intermediate_data"].update(intermediate_data)

        current_progress = ANALYSIS_STATUS[task_id]['progress']
        current_status = ANALYSIS_STATUS[task_id]['status']
        current_message = message if message else f"狀態: {current_status}"
        
        print(f"[DATA_MANAGER] 任務ID: {task_id[:8]} | 進度: {current_progress}% | 訊息: {current_message}")

def get_status(task_id: str) -> Dict[str, Any]:
    """
    獲取特定任務的當前狀態。
    """
    status_info = ANALYSIS_STATUS.get(task_id, {"status": "NOT_FOUND"})
    
    # 在返回給前端前，將狀態和進度提取出來，並確保有 message 欄位
    return {
        "task_id": task_id,
        "status": status_info["status"],
        "progress": status_info["progress"],
        "filename": status_info.get("filename"),
        "error": status_info.get("error"),
        "final_video_path": status_info.get("final_video_path"),
        "message": f"當前進度 {status_info['progress']}%" if status_info["status"] == STATUS_PROCESSING else status_info["status"]
    }

def get_intermediate_path(task_id: str, key: str) -> Optional[str]:
    """
    獲取特定中間文件的路徑。
    """
    status = ANALYSIS_STATUS.get(task_id)
    if status:
        return status["intermediate_data"].get(key)
    return None

def get_task_data(task_id: str) -> Optional[Dict[str, Any]]:
    """
    獲取完整的任務數據 (用於 orchestrator 內部調用)。
    """
    return ANALYSIS_STATUS.get(task_id)