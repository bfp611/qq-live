#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查直播间号：把 房间链接 / 分享短链 / 19 位内部 room_id 换成 web_rid（也就是 live.douyin.com/<这串数字> 里的数字）。
只用标准库，不需要装依赖：

  python3 tools/find_room.py https://live.douyin.com/889896824783      # 链接里本来就有 web_rid → 直接打印
  python3 tools/find_room.py 7708002792107215666                        # 19 位内部 room_id → 走 reflow 接口换算
  python3 tools/find_room.py https://v.douyin.com/xxxxxx/               # 手机分享出来的短链 → 跟随跳转取 room_id 再换算（没有实测过真实短链）
  python3 tools/find_room.py --webcast-mate                             # 从抖音直播伴侣的日志里取最近一次开播的 room_id 再换算
                                                                        #   macOS：~/Library/Logs/Douyin Webcast Mate/*.log（实测过）
                                                                        #   Windows：%APPDATA%\\webcast_mate\\logs 等（路径来自网上资料，我没在 Windows 上验证）
                                                                        #   Linux：没有直播伴侣，这个选项不可用（用 OBS 推流，直接给房间链接/数字）
  python3 tools/find_room.py 889896824783                               # 12 位左右的数字：当作 web_rid 原样打印

最后一行输出就是 web_rid（别的信息打在 stderr），可以直接用：   ./open-live-window.sh "$(python3 tools/find_room.py --webcast-mate)"
"""
import glob
import json
import os
import re
import sys
import platform
import urllib.parse
import urllib.request

MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
REFLOW = "https://webcast.amemv.com/webcast/room/reflow/info/?type_id=0&live_id=1&room_id=%s&app_id=1128"


def say(*a):
    print(*a, file=sys.stderr)


def http(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": MOBILE_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:      # 自动跟随跳转
        return r.geturl(), r.read(400000).decode("utf-8", "replace")


def reflow(room_id):
    """room_id → (web_rid, 昵称, 状态)。web_rid 在返回 JSON 的 data.room.owner.web_rid。"""
    _, body = http(REFLOW % room_id)
    d = json.loads(body)
    room = (d.get("data") or {}).get("room") or {}
    owner = room.get("owner") or {}
    if not owner.get("web_rid"):
        raise SystemExit("接口没有返回 web_rid（room_id 过期/写错，或者这场直播已经结束了）：" + body[:200])
    return str(owner["web_rid"]), owner.get("nickname", ""), room.get("status")


def webcast_log_globs(system=None, env=None, home=None):
    """直播伴侣日志的候选位置（glob 列表，按优先级）。
    macOS 的路径是实测的；Windows 的路径来自第三方项目（heplex/douyin-rtmp 读 %USERPROFILE%/AppData/Roaming/webcast_mate/logs 里文件名含 client 的日志）
    和常见 Electron 应用习惯，**没有在 Windows 上验证过**；设环境变量 WEBCAST_MATE_LOG_DIR 可以直接指定目录。"""
    system = system or platform.system()
    env = os.environ if env is None else env
    home = home or os.path.expanduser("~")
    out = []
    if env.get("WEBCAST_MATE_LOG_DIR"):
        d = env["WEBCAST_MATE_LOG_DIR"]
        out += [os.path.join(d, "*.log*"), os.path.join(d, "**", "*.log*")]
    if system == "Darwin":
        out.append(os.path.join(home, "Library", "Logs", "Douyin Webcast Mate", "*.log"))
    elif system == "Windows":
        roaming = env.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        local = env.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
        for base in (roaming, local):
            for name in ("webcast_mate", "Douyin Webcast Mate", "webcast-mate"):
                out += [os.path.join(base, name, "logs", "*.log*"), os.path.join(base, name, "**", "*client*.log*")]
    return out


def room_id_from_webcast_mate(system=None):
    system = system or platform.system()
    if system == "Linux" or system not in ("Darwin", "Windows"):
        raise SystemExit("这个系统（%s）没有抖音直播伴侣，所以没有日志可读。Linux 开播请用 OBS 推流；"
                         "把直播间链接或数字直接传给本脚本即可：python3 tools/find_room.py https://live.douyin.com/<数字>" % system)
    files = []
    for g in webcast_log_globs(system):
        files += [f for f in glob.glob(g, recursive=True) if os.path.isfile(f) and "watchdog" not in f.lower()]
    files = sorted(set(files), key=os.path.getmtime, reverse=True)[:40]
    if not files:
        raise SystemExit("没找到直播伴侣的日志目录（%s）。%s设环境变量 WEBCAST_MATE_LOG_DIR 指向它的日志文件夹，或直接传房间链接。" % (
            "；".join(webcast_log_globs(system)[:2]), "Windows 路径没有验证过，" if system == "Windows" else ""))
    for f in files:                                              # 从最新的日志往前找，取文件里最后一次出现的
        with open(f, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - 16_000_000))              # 只看末尾 16MB（日志可能很大）
            ids = re.findall(rb"room_?[iI]d[\"': =]{1,6}(\d{19})", fh.read())
        if ids:
            say("从直播伴侣日志取到 room_id（%s）" % f)
            return ids[-1].decode()
    raise SystemExit("直播伴侣日志里没找到 room_id（先在直播伴侣里点一次「开始直播」）")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    arg = sys.argv[1].strip()
    if arg in ("--webcast-mate", "-w"):
        return finish_room_id(room_id_from_webcast_mate())
    m = re.search(r"live\.douyin\.com/(\d+)", arg)
    if m:
        say("链接里就是 web_rid")
        return print(m.group(1))
    if re.fullmatch(r"\d{19}", arg):
        return finish_room_id(arg)
    if re.fullmatch(r"\d{5,17}", arg):
        say("这串数字不是 19 位，当作 web_rid 原样输出")
        return print(arg)
    if arg.startswith("http"):
        final, body = http(arg)
        say("跳转到：" + final)
        m = re.search(r"live\.douyin\.com/(\d+)", final)
        if m:
            return print(m.group(1))
        for text in (final, urllib.parse.unquote(final), body):
            m = re.search(r"(?:reflow/|room_id[=:\"' ]{1,4})(\d{19})", text)
            if m:
                return finish_room_id(m.group(1))
        raise SystemExit("链接里没找到 room_id / web_rid；试试在电脑浏览器里打开它，看地址栏是不是 live.douyin.com/数字")
    raise SystemExit("看不懂这个输入：" + arg)


def finish_room_id(room_id):
    web_rid, nick, status = reflow(room_id)
    say("room_id=%s → 主播 %s，直播状态=%s（2=正在直播；4 是已结束的场次）" % (room_id, nick, status))
    print(web_rid)


if __name__ == "__main__":
    main()
