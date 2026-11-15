#!/bin/bash
# 打开「怀旧 Windows XP 桌面 + QQ 群聊」直播画面（给直播伴侣「窗口采集」用）
#   ./open-live-window.sh                 横屏 1920×1080 窗口 + 演示数据（默认）
#   ./open-live-window.sh 房间号          横屏，接真实直播间弹幕
#   ./open-live-window.sh --portrait [房间号]   老的竖屏模式：在竖屏显示器上全屏（只有 QQ 窗口，没有桌面）
# 可调：  POS=x,y  窗口位置（屏幕坐标，左上角为原点）   TITLEBAR=32  标题栏高度（内容区恰好 1920×1080；Linux 默认 0，见下）
#         DESK=xp|0  是否显示 XP 桌面   PORT=8765  服务端口   （竖屏：SCALE=3 FS=13 POS=3440,-501）
#         BROWSER_BIN=/path/to/chrome   指定浏览器（macOS 上是 App 名，如 "Microsoft Edge"；Linux 上是可执行文件）
# macOS 用 Google Chrome（open -na）；Linux 自动找 google-chrome / chromium / microsoft-edge / brave，用单独的配置目录 ~/.qq-live-chrome。
# Linux 窗口管理器给标题栏的高度不一样：打开后在窗口里按 Ctrl+Shift+I，控制台输入 [innerWidth,innerHeight]，不是 1920,1080 就调 TITLEBAR。
# Wayland 下浏览器会忽略 --window-position（窗口位置由系统决定），可以用 POS 之外的办法手动拖。
cd "$(dirname "$0")"
PORTRAIT=0; ROOM=""
for a in "$@"; do case "$a" in --portrait|-p) PORTRAIT=1;; *) ROOM="$a";; esac; done
PORT="${PORT:-8765}"; BASE="http://localhost:$PORT/"
ROOM="${ROOM##*/}"
if [ -n "$ROOM" ]; then SRC="room=$ROOM"; else SRC="demo=1"; fi
SRC="$SRC&anchor=${ANCHOR:-GG-Bond}"
curl -fs -o /dev/null "$BASE" || { echo "服务没在运行：先在另一个终端执行 ./start.sh（不带房间号就是演示，带房间号接真实弹幕）" >&2; exit 1; }
pkill -f "user-data-dir=$HOME/.qq-live-chrome" 2>/dev/null; sleep 1
COMMON=(--user-data-dir="$HOME/.qq-live-chrome" --no-first-run --no-default-browser-check --autoplay-policy=no-user-gesture-required)
if [ "$PORTRAIT" = 1 ]; then
  URL="$BASE?$SRC&scale=${SCALE:-3}&fs=${FS:-13}"
  ARGS=("${COMMON[@]}" --kiosk --window-position=${POS:-3440,-501} --app="$URL")
else
  URL="$BASE?$SRC&desk=${DESK:-xp}"
  if [ "$(uname -s)" = Darwin ]; then TB="${TITLEBAR:-32}"; else TB="${TITLEBAR:-0}"; fi
  ARGS=("${COMMON[@]}" --window-size=1920,$((1080+TB)) --window-position=${POS:-760,160} --app="$URL")
fi
if [ "$(uname -s)" = Darwin ]; then
  open -na "${BROWSER_BIN:-Google Chrome}" --args "${ARGS[@]}"
  echo "已打开: $URL   (退出: 点一下那个窗口按 Cmd+Q)"
else
  B="${BROWSER_BIN:-}"
  if [ -z "$B" ]; then
    for c in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge microsoft-edge-stable brave-browser; do
      command -v "$c" >/dev/null 2>&1 && { B="$c"; break; }
    done
  fi
  [ -n "$B" ] && command -v "$B" >/dev/null 2>&1 || { echo "没找到 Chrome / Chromium / Edge：先安装一个（sudo apt install chromium），或 BROWSER_BIN=/path/to/chrome $0" >&2; exit 1; }
  nohup "$B" "${ARGS[@]}" --force-device-scale-factor=1 >/dev/null 2>&1 &
  echo "已打开: $URL   (浏览器: $B；退出: 点一下那个窗口按 Ctrl+Q / Alt+F4)"
fi
