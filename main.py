from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float
    is_offer: Union[bool, None] = None


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI!"}


@app.get("/items/{item_id}")
async def read_item(item_id: int, query: str = None):
    return {"item_id": item_id, "query": query}


# @app.put("/items/{item_id}")
# def update_item(item_id: int, item: Item):
#     return {"item_name": item.name, "item_id": item_id}


import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse

# 設置影片儲存的根目錄
# 由於是開發階段，我們將它設在與 main.py 同一個目錄下的 'uploaded_videos' 資料夾
# 請確保這個目錄存在，否則程式碼會自動創建它
UPLOAD_DIR = Path("uploaded_videos")

# 確保影片儲存目錄存在
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="游泳影片後製 API (MVP)",
    description="具備影片上傳和下載的基礎服務",
    version="1.0.0",
)

# --- 模擬資料庫/狀態追蹤 ---
# 在開發階段，我們使用一個簡單的字典來追蹤影片狀態
video_db = {}
# 範例結構: { "uuid": {"filename": "original_name.mp4", "status": "uploaded"} }

# ----------------------------------------------------
# 1. 後台任務：模擬耗時的影片後製處理
# ----------------------------------------------------


def process_video_in_background(video_id: str):
    """
    模擬影片後製處理的耗時任務。
    在實際應用中，這裡會調用 OpenCV 或 FFmpeg 等庫。
    """
    import time

    print(f"--- 啟動影片 {video_id} 的後製處理 (模擬 10 秒) ---")

    # 模擬影片分析和處理時間
    time.sleep(10)

    # 假設處理完成，更新狀態
    if video_id in video_db:
        video_db[video_id]["status"] = "completed"
        # 假設產生了一個新的後製檔案（這裡只是用原檔案名）
        video_db[video_id]["processed_path"] = video_db[video_id]["file_path"]

    print(f"--- 影片 {video_id} 處理完成，狀態更新為：completed ---")


# ----------------------------------------------------
# 2. API 端點：影片上傳
# ----------------------------------------------------


@app.post("/videos/upload", status_code=202)
async def upload_video(
    file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    上傳游泳影片，並將檔案儲存至本地，隨後啟動後台處理任務。
    """
    # 產生一個唯一的 ID 作為影片的唯一識別符
    video_id = str(uuid4())

    # 構建儲存路徑
    # 建議：儲存時使用 UUID 作為檔案名，以避免名稱衝突，並保留原始副檔名
    file_extension = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{video_id}{file_extension}"

    # 1. 儲存檔案到本地
    try:
        # 使用 shutil.copyfileobj 處理 UploadFile，避免讀取整個大檔案到記憶體
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        # 清理已上傳的（可能損壞的）檔案
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {e}")
    finally:
        # 確保關閉上傳的檔案流
        await file.close()

    # 2. 更新影片狀態追蹤
    video_db[video_id] = {
        "filename": file.filename,
        "file_path": str(file_path),
        "status": "uploaded",
        "processed_path": None,  # 初始沒有後製版本
    }

    # 3. 啟動後台任務進行處理
    # BackgroundTasks 會在 API 響應發送給客戶端後，於後台執行 process_video_in_background 函數
    background_tasks.add_task(process_video_in_background, video_id)

    return JSONResponse(
        status_code=202,  # 202 Accepted 表示請求已接受，正在處理中
        content={
            "video_id": video_id,
            "message": "影片已接收，正在後台處理中。",
            "status_endpoint": f"/videos/{video_id}/status",
        },
    )


# ----------------------------------------------------
# 3. API 端點：獲取影片狀態
# ----------------------------------------------------


@app.get("/videos/{video_id}/status")
async def get_video_status(video_id: str):
    """
    根據 video_id 查詢影片的處理狀態。
    """
    if video_id not in video_db:
        raise HTTPException(status_code=404, detail="找不到該影片 ID。")

    return video_db[video_id]


# ----------------------------------------------------
# 4. API 端點：下載影片 (介面去 Server 撈影片)
# ----------------------------------------------------


@app.get("/videos/{video_id}/download")
async def download_video(video_id: str):
    """
    下載後製完成的影片。如果未完成，則返回提示。
    """
    if video_id not in video_db:
        raise HTTPException(status_code=404, detail="找不到該影片 ID。")

    video_info = video_db[video_id]

    if video_info["status"] != "completed" or not video_info["processed_path"]:
        raise HTTPException(
            status_code=409,  # 409 Conflict 表示資源狀態不允許操作
            detail=f"影片狀態為 '{video_info['status']}'，尚未完成後製。",
        )

    # FastAPI 的 FileResponse 會處理檔案讀取和 HTTP 標頭設置（如 Content-Disposition）
    return FileResponse(
        path=video_info["processed_path"],
        filename=f"processed_{video_info['filename']}",  # 提供一個下載時使用的檔案名
        media_type="video/mp4",  # 假設輸出的都是 mp4，您可以根據需求調整
    )


# ----------------------------------------------------
# 5. API 端點：查詢所有影片
# ----------------------------------------------------


@app.get("/videos")
async def list_videos():
    """
    返回所有已上傳影片的 ID 列表及狀態摘要。
    """
    # 返回一個簡潔的列表
    summary = [
        {"id": vid, "filename": info["filename"], "status": info["status"]}
        for vid, info in video_db.items()
    ]
    return summary


@app.get("/data")
async def list_videos():
    """
    返回所有已上傳影片的 ID 列表及狀態摘要。
    """
    # 返回一個簡潔的列表
    summary = [
        {"id": vid, "filename": info["filename"], "status": info["status"]}
        for vid, info in video_db.items()
    ]
    return summary
