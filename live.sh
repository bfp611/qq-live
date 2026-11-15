#!/usr/bin/env bash
# 一键开播（macOS / Linux）：./live.sh [房间号或链接] [--no-window] [--detach] [--port 8765] …（完整选项：.venv/bin/python tools/opsctl.py -h）
#   做的事：检测房间（直播伴侣 → 失败用 config.ini [ops] default_room）→ 启动服务（带崩溃自动重启的看门狗）
#           → 打印自检清单（音频设备 / TTS / LLM / 直播间 / 音乐 / 浏览器 / 手机面板）→ 打开 1920×1080 直播窗口 → 打印手机面板地址和二维码
cd "$(dirname "$0")" || exit 1
REQ="$(cksum < requirements.txt)"
if [ "$(cat .venv/.ready 2>/dev/null)" != "$REQ" ]; then
  ./install.sh --quiet || exit 1
fi
exec .venv/bin/python tools/opsctl.py live "$@"
