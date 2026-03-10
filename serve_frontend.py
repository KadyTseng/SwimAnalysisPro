import http.server
import socketserver
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "frontend", "build", "web")
PORT = 19191
PREFIX = "/swimming_analysis"

if not os.path.exists(WEB_DIR):
    print(f"Error: {WEB_DIR} does not exist. Please build the flutter web app first.")
    sys.exit(1)

class SPARequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def translate_path(self, path):
        # 去除反向代理的 prefix
        if path.startswith(PREFIX):
            path = path[len(PREFIX):]
            if not path.startswith('/'):
                path = '/' + path
                
        # 取得系統絕對路徑
        filepath = super().translate_path(path)
        
        # SPA 路由：如果請求的檔案不存在，且該請求沒有副檔名，則返回 index.html 讓 Flutter 處理路由
        if not os.path.exists(filepath):
            if "." not in os.path.basename(filepath):
                return os.path.join(WEB_DIR, "index.html")
        
        return filepath

    def list_directory(self, path):
        # 禁用 Directory Listing，避免暴露伺服器目錄
        self.send_error(404, "No permission to list directory")
        return None

# 允許 Port 快速重用
socketserver.TCPServer.allow_reuse_address = True

with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), SPARequestHandler) as httpd:
    print(f"Serving HTTP on port {PORT}")
    print(f"Serving directory: {WEB_DIR}")
    print(f"Mapping prefix: {PREFIX} -> /")
    httpd.serve_forever()
