#!/usr/bin/env bash
# 一键启动：./start.sh <直播间号或链接> [端口]
#   ./start.sh 200124183517
#   ./start.sh https://live.douyin.com/200124183517
#   ./start.sh            （不带房间号：只启动页面，用 ?demo=1 看假数据，或 URL 里自己写 ?room=）
set -e
cd "$(dirname "$0")"
ROOM="${1:-}"
PORT="${2:-${PORT:-8765}}"

REQ="$(cksum < requirements.txt)"
if [ "$(cat .venv/.ready 2>/dev/null)" != "$REQ" ]; then
  ./install.sh --quiet || exit 1       # 检查 Python 版本、建 .venv、装依赖（macOS / Linux 通用）
fi

exec .venv/bin/python backend/server.py "$ROOM" --port "$PORT"
