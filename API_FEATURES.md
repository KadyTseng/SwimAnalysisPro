# SwimAnalysisPro API — 完整功能清單 📋

## 概述
本文檔詳細列出 `main.py` 的所有功能，協助前端開發者理解 API 的能力。

---

## 🎯 核心功能 (7 大功能)

### 1️⃣ **影片上傳管理** 📤
**端點**: `POST /analysis/upload`
**狀態碼**: 202 Accepted
**用途**: 接收並儲存前端上傳的游泳影片

#### 功能細節
- 接收 multipart/form-data 格式的影片檔案
- 使用 UUID 命名，避免檔案名衝突
- 自動驗證並儲存至 `uploaded_videos/` 目錄
- 初始化分析狀態 (status = "processing", progress = 0)
- 啟動後台分析任務 (非同步)

#### 請求
```bash
curl -X POST http://localhost:8000/analysis/upload \
  -F "file=@your_video.mp4"
```

#### 回傳 (202 Accepted)
```json
{
  "video_id": "abc-123-def-456",
  "message": "影片已接收，正在後台分析中...",
  "status_endpoint": "/analysis/abc-123-def-456/status"
}
```

#### 錯誤處理
| 狀態碼 | 原因 |
|--------|------|
| 500 | 檔案儲存失敗 |

#### 前端使用
```javascript
const formData = new FormData();
formData.append('file', videoFile);

const response = await fetch('/analysis/upload', {
  method: 'POST',
  body: formData
});

const { video_id } = await response.json();
console.log('影片 ID:', video_id);
```

---

### 2️⃣ **後台分析引擎** 🔄
**函式**: `run_analysis_task(video_id, video_path)`
**執行方式**: 非同步後台任務
**用途**: 呼叫核心分析邏輯進行完整分析

#### 分析流程
```
姿態估計 → 泳姿識別 → 划手計算 → 跳水分析 → 分段時間 → 影片合成
   ↓
BD.orchestrator.run_full_analysis()
```

#### 執行步驟
1. 狀態更新為 "processing" (progress: 5%)
2. 呼叫 `BD.orchestrator.run_full_analysis()`
3. 透過 `status_callback` 回調更新進度
4. 分析完成後格式化結果
5. 狀態更新為 "completed" 或 "failed" (progress: 0-100)
6. 儲存結果至 analysis_db

#### 分析結果包含
- **泳姿**: backstroke, freestyle, breaststroke, butterfly
- **划手分析**: 總次數、去程/回程次數、每分鐘划手數 (SPM)
- **階段分析**: propulsion/recovery 各階段詳細資訊
- **踢腿角度**: 最小/最大/平均角度、角速度變化
- **分段時間**: 各分段耗時、速度
- **圖表**: 相位波形圖、踢腿角度圖

#### 錯誤處理
- 若 orchestrator 導入失敗，狀態設為 "failed"
- 錯誤訊息存放在 `error_message` 欄位

---

### 3️⃣ **進度追蹤** 📊
**端點**: `GET /analysis/{video_id}/status`
**用途**: 實時查詢分析進度

#### 功能細節
- 輪詢此端點獲取最新進度 (建議每 1-2 秒查詢一次)
- 回傳進度百分比 (0-100)
- 分析失敗時包含錯誤訊息

#### 回傳範例
```json
{
  "video_id": "abc-123-def-456",
  "filename": "pool_video.mp4",
  "status": "processing",
  "progress": 45,
  "error_message": null
}
```

#### 狀態值
| 狀態 | 說明 |
|------|------|
| `processing` | 分析進行中 |
| `completed` | 分析完成 |
| `failed` | 分析失敗 |

#### 前端實現範例
```javascript
async function pollProgress(videoId) {
  let isCompleted = false;
  
  while (!isCompleted) {
    const res = await fetch(`/analysis/${videoId}/status`);
    const status = await res.json();
    
    console.log(`進度: ${status.progress}%`);
    
    if (status.status === 'completed') {
      console.log('✅ 分析完成');
      isCompleted = true;
    } else if (status.status === 'failed') {
      console.error('❌ 分析失敗:', status.error_message);
      isCompleted = true;
    }
    
    // 等待 2 秒後再查詢
    await new Promise(r => setTimeout(r, 2000));
  }
}
```

#### 錯誤處理
| 狀態碼 | 原因 |
|--------|------|
| 404 | 找不到指定的 video_id |

---

### 4️⃣ **結果管理** ✅
**端點**: `GET /analysis/{video_id}/result`
**用途**: 取得完整分析結果 (JSON)

#### 功能細節
- 僅在 status = "completed" 時可用
- 回傳格式化的完整分析結果
- 包含所有分析指標和原始資料

#### 回傳結構 (FullAnalysisResult)
```json
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
    "phases": {
      "range1": [
        {
          "phase_name": "propulsion",
          "start_frame": 100,
          "end_frame": 200,
          "duration_ms": 500
        }
      ]
    },
    "stroke_frames": [100, 250, 400, ...]
  },
  
  "diving_analysis": {
    "segments": [[0, 150], [300, 450]],
    "touch_frame": 300,
    "waterline_y": 240,
    "total_kick_count": 15,
    "kick_frequency": 2.3,
    "kick_angle_analysis": {
      "range1": {
        "angles": [
          {"frame": 10, "angle_degrees": 45.2, "angle_velocity": 12.5}
        ],
        "avg_angle": 42.3,
        "max_angle": 55.8,
        "min_angle": 28.5
      }
    },
    "kick_angle_fig_1": "path/to/figure.png",
    "kick_angle_fig_2": "path/to/figure.png"
  },
  
  "split_timing": {
    "splits": [25.5, 26.2, 25.8],
    "segments": [
      {
        "segment_id": 1,
        "start_frame": 0,
        "end_frame": 765,
        "duration_sec": 25.5,
        "avg_speed_m_per_sec": 1.96
      }
    ],
    "average_speed": 1.94,
    "max_speed": 2.1,
    "min_speed": 1.8
  },
  
  "stroke_plot_figs": {
    "range1": {
       "propulsion": [[100, 150], [200, 250]],
       "recovery": [[150, 160]],
       "segment_metrics": [
         {"label": "1.20m", "start_frame": 100, "end_frame": 150, "value": 1.2}
       ],
       "values": [120, 125, 130, ...]
    }
  },
  "focus_crop_video_path": "data/processed_videos/focus_abc-123.mp4",
  "timestamp": "2026-01-15T10:30:00",
  "analysis_duration_seconds": 45.2
}
```

#### 各欄位說明

| 欄位 | 類型 | 說明 |
|------|------|------|
| `video_id` | string | 影片識別符 |
| `processed_video_path` | string | 最終後製影片路徑 |
| `stroke_style` | string | 泳姿類型 |
| `stroke_result` | object | 划手相關分析 |
| `diving_analysis` | object | 跳水/潛泳/踢腿分析 |
| `split_timing` | object | 分段時間/速度分析 |
| `stroke_plot_figs` | object | **相位分析數據 (JSON)**，包含推進/恢復/滑行區間、Metrics 與圖表原始數據 |
| `focus_crop_video_path` | string | focus 裁切影片 |
| `timestamp` | string | 分析完成時間 (ISO 8601) |
| `analysis_duration_seconds` | float | 分析耗時 (秒) |

#### 前端使用
```javascript
async function getResults(videoId) {
  const res = await fetch(`/analysis/${videoId}/result`);
  const result = await res.json();
  
  // 顯示泳姿
  console.log('泳姿:', result.stroke_style);
  
  // 顯示划手數
  console.log('划手數:', result.stroke_result.total_count);
  console.log('SPM:', result.stroke_result.strokes_per_minute);
  
  // 顯示踢腿角度
  const angles = result.diving_analysis.kick_angle_analysis.range1;
  console.log('平均踢腿角度:', angles.avg_angle, '°');
  console.log('最大踢腿角度:', angles.max_angle, '°');
  
  // 顯示速度
  console.log('平均速度:', result.split_timing.average_speed, 'm/s');
  
  // 顯示各分段
  result.split_timing.segments.forEach(seg => {
    console.log(`分段 ${seg.segment_id}: ${seg.duration_sec.toFixed(2)}s @ ${seg.avg_speed_m_per_sec.toFixed(2)} m/s`);
  });
}
```

#### 錯誤處理
| 狀態碼 | 原因 |
|--------|------|
| 404 | 找不到該影片 |
| 409 | 分析尚未完成 (status != 'completed') |
| 500 | 分析結果缺失 |

---

### 5️⃣ **檔案下載** ⬇️
### 5️⃣ **檔案下載** ⬇️
**端點**: `GET /analysis/{video_id}/download`
**用途**: 下載影片檔案 (後製影片或追焦影片)

#### 參數 (Query Parameters)
| 參數 | 類型 | 必填 | 預設值 | 說明 |
|------|------|------|--------|------|
| `type` | string | 否 | `processed` | 下載檔案類型。可選值: `processed` (後製疊加影片), `focus` (AI追焦影片) |

#### 功能細節
- 支援串流傳輸 (Range requests)
- 自動設定 Content-Type 為 `video/mp4`

#### 回傳
```
Content-Type: video/mp4
Content-Disposition: attachment; filename="processed_xxx.mp4" (或 focus_xxx.mp4)
Body: [二進位影片數據]
```

#### 使用範例 (HTML)
```html
<!-- 下載後製分析影片 -->
<a href="/analysis/abc-123/download" download>下載分析影片</a>

<!-- 下載追焦影片 -->
<a href="/analysis/abc-123/download?type=focus" download>下載追焦影片</a>
```

#### 前端使用 (JavaScript)
```javascript
async function downloadVideo(videoId, type = 'processed') {
  // type = 'processed' or 'focus'
  const response = await fetch(`/analysis/${videoId}/download?type=${type}`);
  const blob = await response.blob();
  
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${type}_${videoId}.mp4`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
```

#### 錯誤處理
| 狀態碼 | 原因 |
|--------|------|
| 404 | 找不到指定的影片檔案 |
| 409 | 影片尚未完成分析 |

---

### 6️⃣ **分析紀錄查詢** 📋
**端點**: `GET /analysis/list`
**用途**: 列出所有上傳的影片分析狀態

#### 功能細節
- 回傳所有分析紀錄的摘要
- 包含 video_id、filename、status、created_at
- 用於管理多個分析工作

#### 回傳範例
```json
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
```

#### 前端使用
```javascript
async function listAnalyses() {
  const res = await fetch('/analysis/list');
  const { total, videos } = await res.json();
  
  console.log(`總共 ${total} 個分析紀錄`);
  
  videos.forEach(v => {
    const statusIcon = v.status === 'completed' ? '✅' : 
                       v.status === 'processing' ? '⏳' : '❌';
    console.log(`${statusIcon} ${v.filename} (${v.video_id})`);
  });
}
```

---

### 7️⃣ **健康檢查** 🏥
**端點**: `GET /health`
**用途**: 監控 API 與後端模組狀態

#### 功能細節
- 檢查 API 伺服器狀態
- 檢查後端分析模組 (orchestrator) 是否可用
- 用於監控和部署檢查

#### 回傳
```json
{
  "status": "healthy",
  "timestamp": "2026-01-15T10:30:00",
  "orchestrator_available": true
}
```

#### 使用場景
- Kubernetes liveness probe
- Docker health check
- 負載均衡器監控
- 前端啟動檢查

#### 前端使用
```javascript
async function checkHealth() {
  try {
    const res = await fetch('/health');
    const health = await res.json();
    
    if (health.status === 'healthy') {
      console.log('✅ API 狀態正常');
      if (health.orchestrator_available) {
        console.log('✅ 後端分析模組可用');
      }
    }
  } catch (e) {
    console.error('❌ 無法連線到 API:', e);
  }
}
```

---

## 📊 完整工作流程

### 標準使用流程
```
1. 上傳影片
   POST /analysis/upload
   ↓ (回傳 video_id)

2. 輪詢進度 (每 1-2 秒)
   GET /analysis/{video_id}/status
   ↓ (progress: 0-100, status: processing)

3. 分析完成
   status: completed, progress: 100
   ↓

4. 取得結果
   GET /analysis/{video_id}/result
   ↓ (回傳所有分析資料)

5. 下載影片
   GET /analysis/{video_id}/download
   ↓ (取得後製影片檔案)

6. (可選) 查詢歷史
   GET /analysis/list
   ↓ (取得所有分析紀錄)
```

### 前端完整範例
```javascript
// 1. 上傳影片
async function uploadVideo(videoFile) {
  const formData = new FormData();
  formData.append('file', videoFile);
  
  const res = await fetch('/analysis/upload', {
    method: 'POST',
    body: formData
  });
  
  const { video_id } = await res.json();
  return video_id;
}

// 2. 等待分析完成
async function waitForCompletion(videoId) {
  let completed = false;
  
  while (!completed) {
    const res = await fetch(`/analysis/${videoId}/status`);
    const status = await res.json();
    
    console.log(`進度: ${status.progress}%`);
    
    if (status.status === 'completed') {
      completed = true;
    } else if (status.status === 'failed') {
      throw new Error(status.error_message);
    }
    
    await new Promise(r => setTimeout(r, 2000));
  }
}

// 3. 取得結果
async function getResults(videoId) {
  const res = await fetch(`/analysis/${videoId}/result`);
  return await res.json();
}

// 4. 主程式
async function main(videoFile) {
  const videoId = await uploadVideo(videoFile);
  console.log('影片已上傳:', videoId);
  
  await waitForCompletion(videoId);
  console.log('分析完成');
  
  const results = await getResults(videoId);
  console.log('泳姿:', results.stroke_style);
  console.log('划手數:', results.stroke_result.total_count);
  // ... 使用結果
}
```

---

## 🔧 環境設置

### 環境變數
```bash
# API 伺服器配置
UPLOAD_DIR=uploaded_videos              # 上傳影片儲存目錄
OUTPUT_DIR=data/processed_videos        # 後製影片輸出目錄

# 分析模組配置
POSE_MODEL_PATH=/path/to/pose_model.pt
STYLE_MODEL_PATH=/path/to/svm_model.pkl
FFMPEG_EXECUTABLE_PATH=/path/to/ffmpeg
```

### 啟動 API
```bash
# 方式 1: uvicorn 命令
uvicorn main:app --reload --port 8000

# 方式 2: Python 直接運行
python main.py

# 方式 3: gunicorn (生產環境)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

### Swagger UI
啟動後訪問 `http://localhost:8000/docs` 可看到互動式 API 文檔

---

## 💡 最佳實踐

### 1. 輪詢間隔
建議每 1-2 秒查詢一次進度，避免伺服器負擔

### 2. 錯誤處理
```javascript
try {
  const res = await fetch(...);
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail);
  }
} catch (e) {
  console.error('API 錯誤:', e);
}
```

### 3. 超時處理
若分析超過預期時間 (如 10 分鐘)，提示使用者重新嘗試

### 4. 並行分析
可同時上傳多個影片，使用不同的 video_id 追蹤

### 5. 結果快取
取得結果後可在前端快取，減少 API 查詢

---

## 📝 更新日誌

| 版本 | 日期 | 變更 |
|------|------|------|
| v2.0 | 2026-01-15 | 完整整合 orchestrator，支援所有分析功能 |
| v1.0 | 2026-01-10 | 初始版本 |

---

## 🆘 常見問題

### Q: 分析需要多長時間？
A: 取決於影片長度和伺服器效能，通常 30 秒影片需要 2-5 分鐘。

### Q: 後製影片在哪裡？
A: 在 `processed_video_path` 欄位回傳，可透過 `/download` 端點下載。

### Q: 可以同時分析多個影片嗎？
A: 可以，每個影片有獨立的 video_id 和狀態。

### Q: 如何處理分析失敗？
A: 查詢 `/status` 時 status = "failed"，error_message 包含失敗原因。

---

詳細代碼文檔見 `main.py` 的 docstring 註解。🚀
