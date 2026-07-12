#!/bin/bash
# 一鍵啟動職缺查詢網站（macOS 在 Finder 點兩下即可執行）。
# 會啟動伺服器，並在 2 秒後自動用預設瀏覽器打開頁面。
# 關閉網站：回到這個視窗按 Control + C，或直接關掉視窗。

cd "$(dirname "$0")" || exit 1

PORT="${PORT:-8000}"
( sleep 2 && open "http://127.0.0.1:${PORT}" ) &

echo "啟動職缺查詢網站中… 瀏覽器將自動打開 http://127.0.0.1:${PORT}"
echo "（要停止請按 Control + C）"
PORT="$PORT" python3 app.py
