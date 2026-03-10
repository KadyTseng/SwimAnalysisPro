#!/bin/bash
# SwimAnalysisPro 快速重啟腳本

BASE_DIR="/home/kady6582/SwimAnalysisPro"
BACKEND_LOG="$BASE_DIR/backend.log"
FRONTEND_LOG="$BASE_DIR/frontend.log"

echo "⚡ 正在快速停止舊服務..."
# 1. 直接抓取佔用該 Port 的 PID 並殺掉，這比 fuser 快很多
PIDS=$(lsof -t -i:19191,18181 2>/dev/null)
if [ ! -z "$PIDS" ]; then
    kill -9 $PIDS 2>/dev/null
    echo "✅ 已清理進程: $PIDS"
else
    echo "👌 埠口原本就是空的"
fi

# 2. 雙重保險：清理殘留的 uvicorn
pkill -u kady6582 -f "uvicorn" 2>/dev/null
sleep 1

echo "🚀 啟動後端 (18181)..."
cd "$BASE_DIR"
export LD_PRELOAD="/home/kady6582/.conda/envs/Pool/lib/libiomp5.so"
nohup /home/kady6582/.conda/envs/Pool/bin/uvicorn main:app \
    --host 0.0.0.0 \
    --port 18181 \
    --workers 1 \
    > "$BACKEND_LOG" 2>&1 &

echo "🌐 啟動前端 (19191)..."
cd "$BASE_DIR"
nohup python3 serve_frontend.py > "$FRONTEND_LOG" 2>&1 &

echo "✨ 前端已透過自製 serve_frontend.py 啟動，原生支援路由與 SPA Fallback。"

echo "✨ 服務已重啟！"
echo "---------------------------------------------------"
# 顯示最後幾行日誌確認有無噴錯
sleep 2
echo "📊 最近的後端紀錄："
tail -n 5 "$BACKEND_LOG"