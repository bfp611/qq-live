#!/usr/bin/env bash
# 安装 / 自检（macOS 和 Linux）。Windows 用 install.ps1。
#   ./install.sh            建 .venv、装 Python 依赖，并检查浏览器 / 音乐读取工具 / 音频路由工具
#   ./install.sh --quiet    只在需要时装依赖，不打印检查清单（start.sh 内部用）
#   PYTHON=/path/to/python3 ./install.sh     指定 Python（需要 3.9 以上，推荐 3.11~3.13）
# 重复运行是安全的；依赖没变就什么也不做。
set -e
cd "$(dirname "$0")"
QUIET=0; [ "${1:-}" = "--quiet" ] && QUIET=1
SYS="$(uname -s)"
case "$SYS" in Darwin) OSK=mac;; Linux) OSK=linux;; *) echo "这个脚本只支持 macOS / Linux（Windows 请运行 install.ps1）；当前是 $SYS" >&2; exit 1;; esac
say() { [ "$QUIET" = 1 ] || echo "$@"; }
warn() { echo "  ⚠ $*" >&2; }
ok() { say "  ✓ $*"; }

# ---------- Python ----------
pyok() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; }
PY=""
for c in "${PYTHON:-}" python3.12 python3.13 python3.11 python3.10 python3.9 python3 python; do
  [ -n "$c" ] || continue
  p="$(command -v "$c" 2>/dev/null || true)"
  [ -n "$p" ] && pyok "$p" && { PY="$p"; break; }
done
HAVE_UV=0; command -v uv >/dev/null 2>&1 && HAVE_UV=1
if [ -z "$PY" ] && [ "$HAVE_UV" = 0 ]; then
  echo "找不到 Python 3.9 或更新的版本。" >&2
  if [ "$OSK" = mac ]; then echo "  安装：brew install python   （或 brew install uv，uv 会自己下载 Python）" >&2
  else echo "  安装：sudo apt install python3 python3-venv   （Fedora: sudo dnf install python3；Arch: sudo pacman -S python；或安装 uv）" >&2; fi
  exit 1
fi
say ">>> 系统：$([ $OSK = mac ] && echo macOS || echo Linux)   Python：${PY:-（由 uv 提供）} $([ -n "$PY" ] && "$PY" -c 'import sys;print(sys.version.split()[0])')"

# ---------- venv + 依赖 ----------
REQ="$(cksum < requirements.txt)"
if [ "$(cat .venv/.ready 2>/dev/null)" != "$REQ" ]; then
  echo ">>> 安装/更新依赖（第一次约 1 分钟，之后不会再装）"
  if [ "$HAVE_UV" = 1 ]; then
    [ -d .venv ] || { if [ -n "$PY" ]; then uv venv -q --python "$PY" .venv; else uv venv -q .venv; fi; }
    uv pip install -q --python .venv/bin/python -r requirements.txt
  else
    if [ ! -d .venv ]; then
      "$PY" -m venv .venv 2>/dev/null || {
        echo "创建虚拟环境失败。Debian/Ubuntu 需要：sudo apt install python3-venv（或 python3.X-venv）" >&2; rm -rf .venv; exit 1; }
    fi
    .venv/bin/python -m pip install -q --upgrade pip
    .venv/bin/python -m pip install -q -r requirements.txt
  fi
  echo "$REQ" > .venv/.ready
fi
if ! .venv/bin/python -c 'import aiohttp, requests, websocket, betterproto, py_mini_racer, edge_tts' 2>/dev/null; then
  echo "依赖导入失败，试试删掉 .venv 目录再运行 ./install.sh" >&2; exit 1
fi
[ "$QUIET" = 1 ] && exit 0
ok "Python 依赖就绪（.venv）"

# ---------- 浏览器 ----------
say ">>> 检查浏览器（open-live-window.sh 要用 Chrome / Edge / Chromium 的 --app 窗口）"
B=""
if [ "$OSK" = mac ]; then
  for a in "Google Chrome" "Microsoft Edge" "Chromium" "Brave Browser"; do [ -d "/Applications/$a.app" ] && { B="$a"; break; }; done
else
  for c in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge microsoft-edge-stable brave-browser; do command -v $c >/dev/null 2>&1 && { B="$c"; break; }; done
fi
[ -n "$B" ] && ok "浏览器：$B" || warn "没找到 Chrome/Edge/Chromium。装一个，或用 BROWSER_BIN=/path/to/chrome 指定（open-live-window.sh 会读它）"

# ---------- 系统相关 ----------
if [ "$OSK" = mac ]; then
  say ">>> macOS：网易云「正在播放」读取（千千静听 / 歌词 / 点歌）"
  if [ -f tools/mr/mediaremote-adapter/build/MediaRemoteAdapter.framework/MediaRemoteAdapter ] || [ -d tools/mr/mediaremote-adapter/build/MediaRemoteAdapter.framework ]; then ok "mediaremote-adapter 已构建"
  elif command -v nowplaying-cli >/dev/null 2>&1; then ok "nowplaying-cli（备用方式，拿不到进度时间戳）"
  else warn "没有 mediaremote-adapter 构建，也没有 nowplaying-cli：千千静听/歌词/点歌会停用。可以 brew install nowplaying-cli，或按 README 构建 tools/mr"; fi
  [ -d "/Applications/NeteaseMusic.app" ] && ok "网易云音乐客户端已安装" || warn "没找到 /Applications/NeteaseMusic.app（点歌需要它）"
  say ">>> macOS：声音路由用 BlackHole（见 README §6，tools/make_multiout.swift）"
  system_profiler SPAudioDataType 2>/dev/null | grep -qi blackhole && ok "BlackHole 已安装" || warn "没检测到 BlackHole（brew install blackhole-2ch）；不做声音路由可忽略"
else
  say ">>> Linux：网易云「正在播放」读取（MPRIS，需要 playerctl）"
  command -v playerctl >/dev/null 2>&1 && ok "playerctl $(playerctl --version 2>/dev/null)" || warn "没有 playerctl：sudo apt install playerctl（千千静听/歌词/点歌依赖它，缺了就自动停用）"
  command -v xdg-open >/dev/null 2>&1 && ok "xdg-open（点歌的备用启动方式）" || warn "没有 xdg-open（sudo apt install xdg-utils）：点歌只能靠 MPRIS OpenUri"
  if command -v playerctl >/dev/null 2>&1; then
    pl="$(playerctl -l 2>/dev/null | tr '\n' ' ')"; [ -n "$pl" ] && ok "当前能看到的播放器：$pl" || say "  · 现在没有任何 MPRIS 播放器在运行（启动网易云音乐后再看：playerctl -l）"
  fi
  say ">>> Linux：声音路由（PulseAudio / PipeWire）：tools/linux_audio_route.sh"
  command -v pactl >/dev/null 2>&1 && ok "pactl（$(pactl info 2>/dev/null | sed -n 's/^Server Name: //p')）" || warn "没有 pactl（sudo apt install pulseaudio-utils；PipeWire 用户装 pipewire-pulse）"
  say "  · Linux 没有抖音直播伴侣：开播请用 OBS 推流（README「Linux 安装」一节）"
fi
say
say "完成。下一步：  ./start.sh 房间号     然后     ./open-live-window.sh 房间号"
