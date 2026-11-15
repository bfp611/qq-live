#!/usr/bin/env bash
# Linux 声音路由（PulseAudio / PipeWire-pulse 通用，用 pactl）——对应 macOS 的 BlackHole + 多输出设备（README §6）。
# 做法：建一个虚拟输出 qqlive_stream（null sink），再建一条 loopback 把它同时放到你的喇叭上（你自己也听得到）。
# 把网易云音乐 和 直播窗口(Chrome，猪猪侠的声音) 的输出移进 qqlive_stream；OBS 里加「音频输入采集」选 “Monitor of QQLive-Stream”。
#   tools/linux_audio_route.sh up              创建虚拟输出 + 回放到喇叭（重复运行安全）
#   tools/linux_audio_route.sh route [正则]    把匹配的正在播放的程序移到虚拟输出（默认 chrom|netease|cloudmusic|electron；播放器开始播放后再运行）
#   tools/linux_audio_route.sh list            列出当前所有播放中的程序和它们用的输出
#   tools/linux_audio_route.sh status          看虚拟输出是否在
#   tools/linux_audio_route.sh down            拆掉（把程序移回默认输出，卸载模块）
# 环境变量：SINK_NAME=qqlive_stream  LOOPBACK=0（不要回放到喇叭）  LATENCY_MS=40
# 开播前 up + route；程序重启后需要再 route 一次（或在 pavucontrol 里把它们的输出手动选成 QQLive-Stream）。
set -u
SINK="${SINK_NAME:-qqlive_stream}"
DESC="QQLive-Stream"
LAT="${LATENCY_MS:-40}"
command -v pactl >/dev/null 2>&1 || { echo "没有 pactl：sudo apt install pulseaudio-utils（PipeWire 用户另装 pipewire-pulse）" >&2; exit 1; }
pactl info >/dev/null 2>&1 || { echo "连不上声音服务（PulseAudio / pipewire-pulse 没在运行？）" >&2; exit 1; }

sink_exists() { pactl list short sinks | awk '{print $2}' | grep -qx "$SINK"; }
mod_ids() { pactl list short modules | awk -v pat="$1" '$0 ~ pat {print $1}'; }

up() {
  if sink_exists; then echo "虚拟输出 $SINK 已存在"; else
    pactl load-module module-null-sink sink_name="$SINK" sink_properties="device.description=$DESC" >/dev/null \
      && echo "已创建虚拟输出 $SINK（$DESC）" || { echo "创建虚拟输出失败（声音服务禁止加载模块？PipeWire 用户需要 pipewire-pulse）" >&2; exit 1; }
  fi
  if [ "${LOOPBACK:-1}" = 1 ]; then
    if [ -n "$(mod_ids "module-loopback.*source=$SINK.monitor")" ]; then echo "回放（loopback → 默认喇叭）已存在"; else
      pactl load-module module-loopback source="$SINK.monitor" latency_msec="$LAT" >/dev/null \
        && echo "已建回放：$SINK.monitor → 默认输出（你能听到直播里的声音）" || echo "建回放失败（不影响推流，只是你自己听不到）" >&2
    fi
  fi
  echo "下一步：播放器开始出声后运行  $0 route ；OBS 音频输入采集选 “Monitor of $DESC”"
}

route() {
  sink_exists || { echo "还没有 $SINK，先运行：$0 up" >&2; exit 1; }
  local pat="${1:-chrom|netease|cloudmusic|electron}" n=0 idx
  while IFS= read -r idx; do
    [ -n "$idx" ] || continue
    pactl move-sink-input "$idx" "$SINK" 2>/dev/null && { n=$((n+1)); echo "  已移动 sink-input #$idx"; }
  done < <(pactl list sink-inputs | awk -v pat="$pat" '
      /^Sink Input #/ {if (id != "" && match(tolower(blk), tolower(pat))) print id; id=substr($3,2); blk=""; next}
      {blk = blk "\n" $0}
      END {if (id != "" && match(tolower(blk), tolower(pat))) print id}')
  [ "$n" -gt 0 ] && echo "共移动 $n 个播放流到 $SINK" || echo "没有匹配 /$pat/ 的正在播放的程序（先让网易云放歌 / 打开直播窗口；或换个正则）"
}

list() {
  local sinks; sinks="$(pactl list short sinks)"
  pactl list sink-inputs | awk -v sinks="$sinks" '
    BEGIN {n=split(sinks, L, "\n"); for (i=1;i<=n;i++) {split(L[i], f, "\t"); name[f[1]]=f[2]}}
    /^Sink Input #/ {if (id!="") print "#" id "  " app "  [" bin "]  → " name[sink]; id=substr($3,2); app=""; bin=""; sink=""}
    /^\tSink:/ {sink=$2}
    /application.name = / {sub(/.*= "/,""); sub(/"$/,""); app=$0}
    /application.process.binary = / {sub(/.*= "/,""); sub(/"$/,""); bin=$0}
    END {if (id!="") print "#" id "  " app "  [" bin "]  → " name[sink]}'
}

status() {
  if sink_exists; then echo "虚拟输出 $SINK：在（OBS 里选 “Monitor of $DESC”）"; else echo "虚拟输出 $SINK：不在（运行 $0 up）"; fi
  [ -n "$(mod_ids "module-loopback.*source=$SINK.monitor")" ] && echo "回放到喇叭：开" || echo "回放到喇叭：关"
  echo "默认输出：$(pactl get-default-sink 2>/dev/null)"
}

down() {
  local def; def="$(pactl get-default-sink 2>/dev/null)"
  if sink_exists && [ "$def" != "$SINK" ] && [ -n "$def" ]; then
    pactl list short sink-inputs | awk '{print $1 "\t" $2}' | while IFS=$'\t' read -r idx sk; do
      [ "$sk" = "$(pactl list short sinks | awk -v s="$SINK" '$2==s {print $1}')" ] && pactl move-sink-input "$idx" "$def" 2>/dev/null && echo "  #$idx 移回 $def"
    done
  fi
  for m in $(mod_ids "module-loopback.*source=$SINK.monitor"); do pactl unload-module "$m" && echo "已卸载 loopback 模块 $m"; done
  for m in $(mod_ids "module-null-sink.*sink_name=$SINK"); do pactl unload-module "$m" && echo "已卸载 null-sink 模块 $m"; done
  echo "已拆除"
}

case "${1:-}" in
  up) up;; route) shift; route "$@";; list) list;; status) status;; down) down;;
  *) sed -n '2,13p' "$0"; exit 2;;
esac
