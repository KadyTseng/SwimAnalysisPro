# SwimAnalysisPro 部署指南 🚀

本指南將協助您將專案部署至伺服器 (Server)，使應用程式可透過固定 IP 或網域訪問。

## 📋 事前準備

1.  **伺服器規格建議**：
    *   **OS**: Linux (Ubuntu 20.04/22.04) 為佳，亦支援 Windows Server。
    *   **GPU**: 強烈建議具備 NVIDIA GPU (支援 CUDA)，以加速 YOLO 骨架提取與影片分析。
    *   **RAM**: 建議 8GB 以上 (處理影片與 AI 模型需要較多記憶體)。
    *   **Disk**: 預留至少 20GB 空間 (存放影片與產出的數據)。

2.  **必要的系統工具**：
    *   `git`
    *   `python 3.9+` (建議使用 Conda 或 venv)
    *   **`ffmpeg`** (⚠️ 非常重要，後端依賴此工具處理影片)

---

## 🛠️ 第一步：前端編譯 (Local 本機操作)

在將代碼推送到 Server 前，我們需要將 Flutter 專案編譯成網頁靜態檔。

1.  **設定 API 網址**：
    打開 `frontend/lib/api_service.dart`，找到 `baseUrl`。
    *   如果使用 Nginx 反向代理 (推薦)：可以設為相對路徑 (需修改代碼邏輯) 或指向 Server ID。
    *   **簡單作法**：將 `http://127.0.0.1:9001` 改為 `http://<您的_SERVER_IP>:9001`。

    ```dart
    // frontend/lib/api_service.dart
    ApiService({this.baseUrl = 'http://YOUR_SERVER_IP:9001'}); 
    ```

2.  **執行編譯**：
    在專案根目錄執行：
    ```bash
    cd frontend
    flutter build web --release
    ```

3.  **產出結果**：
    編譯完成後，會產生 `frontend/build/web/` 資料夾。這個資料夾內的內容就是您的網站。之後需將此資料夾上傳至 Server。

---

## 🖥️ 第二步：伺服器環境設定 (Server 端操作)

假設您使用 **Ubuntu Linux** (Windows 步驟類似，主要是安裝方式不同)。

### 1. 取得專案代碼
```bash
git clone <您的專案Git地址> SwimAnalysisPro
cd SwimAnalysisPro
```
*(或者直接將本機整個資料夾複製到 Server)*

### 2. 安裝系統依賴 (Linux)
```bash
sudo apt-get update
sudo apt-get install ffmpeg libsm6 libxext6  # OpenCV 與 Video 處理依賴
```

### 3. 安裝 Python 環境
```bash
# 建議建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝 Python 套件
pip install -r requirements.txt
```
*注意：如果是 GPU 版本，請確保安裝了對應 CUDA 版本的 `torch` 和 `ultralytics`。*

### 4. 建立必要的資料夾
```bash
mkdir -p uploaded_videos
mkdir -p data/keypoints
mkdir -p data/processed_videos
mkdir -p data/Stroke_Phase_Frames
```

---

## 🚀 第三步：啟動服務

我們需要同時運行前端 (Web Server) 與後端 (API Server)。

### 方案 A：使用 Nginx (生產環境推薦 - Linux)

這是最穩定且標準的做法。Nginx 負責提供前端網頁，並將 `/analysis` 開頭的請求轉發給 Python 後端。

1.  **啟動後端 (Python)**
    使用 `nohup` 或 `systemd` 讓它在背景執行：
    ```bash
    # 在專案根目錄
    nohup python main.py > backend.log 2>&1 &
    # 或使用 uvicorn
    # nohup uvicorn main:app --host 127.0.0.1 --port 9001 > backend.log 2>&1 &
    ```

2.  **設定 Nginx**
    編輯 `/etc/nginx/sites-available/swim_analysis`：
    ```nginx
    server {
        listen 80;
        server_name YOUR_SERVER_IP_OR_DOMAIN;

        # 1. 前端網頁 (指向 build/web 資料夾)
        location / {
            root /path/to/SwimAnalysisPro/frontend/build/web;
            index index.html;
            try_files $uri $uri/ /index.html;
        }

        # 2. 後端 API 反向代理
        location /analysis/ {
            proxy_pass http://127.0.0.1:9001; # 轉發給 Python
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            
            # 設定上傳限制 (影片較大)
            client_max_body_size 500M;
        }
        
        # 3. 健康檢查與其他 API
        location /health {
            proxy_pass http://127.0.0.1:9001;
        }
    }
    ```
    連結並重啟 Nginx：
    ```bash
    sudo ln -s /etc/nginx/sites-available/swim_analysis /etc/nginx/sites-enabled/
    sudo systemctl restart nginx
    ```

### 方案 B：簡易測試 (不使用 Nginx)

如果您只是想快速測試，可以分別啟動。

1.  **啟動後端** (監聽所有 IP)：
    ```bash
    # 修改 main.py 的 uvicorn.run 設定 host="0.0.0.0"
    # 或者直接命令行啟動
    uvicorn main:app --host 0.0.0.0 --port 9001
    ```

2.  **啟動前端** (簡易 Python HTTP Server)：
    ```bash
    cd frontend/build/web
    python3 -m http.server 8000
    ```
    現在訪問 `http://<SERVER_IP>:8000` 即可看到網頁，API 會打向 `:9001`。

---

## ⚠️ 重要注意事項

1.  **CORS (跨來源資源共享)**：
    如果前端與後端 port 不同 (例如前端 :8000, 後端 :9001)，需要在 `main.py` 的 `CORSMiddleware` 中加入前端的 IP/網域，否則瀏覽器會阻擋請求。
    ```python
    # main.py
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # 測試時可設為 *，生產環境建議指定 IP
        ...
    )
    ```

2.  **防火牆**：
    確保 Server 的防火牆 (AWS Security Group / GCP Firewall / ufw) 有開啟對應的 Port (80, 9001 等)。

3.  **影片上傳限制**：
    Nginx 預設上傳限制很小 (1MB)，務必設定 `client_max_body_size 500M;` 以支援影片上傳。

---

## Windows Server 特別說明

如果是部署在 Windows Server：
1.  安裝 [Python for Windows](https://www.python.org/downloads/windows/)。
2.  下載 [FFmpeg Static Build](https://ffmpeg.org/download.html)，解壓並將 `bin` 資料夾加入系統 **Path 環境變數**。
3.  前端推薦使用 IIS 或是簡單的 `python -m http.server`。
4.  後端直接執行 `python main.py`。
