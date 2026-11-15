#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运维入口（一键开播 / 状态 / 手机面板二维码 / 复盘）。macOS / Linux / Windows 通用，只用标准库。
通常不直接用它：双击 live.command（macOS）/ live.bat（Windows），或终端里 ./live.sh [房间号]。

  python tools/opsctl.py live [房间号或链接]   一键：检测房间 → 启动服务（带看门狗）→ 自检清单 → 打开直播窗口 → 打印手机面板地址
        --port 8765         服务端口
        --no-window         不自动打开直播窗口
        --no-detect         不从直播伴侣检测房间（直接用 [ops] default_room）
        --detach            后台运行（服务日志写到 data/logs/live-console.log），打印完清单就返回；默认前台，Ctrl+C 停止
        --no-supervisor     不用看门狗（崩了不自动重启）
        --no-qr             不画二维码
  python tools/opsctl.py status                本机服务的状态 + 自检清单
  python tools/opsctl.py panel-qr              打印「带令牌」的手机面板二维码（令牌在 URL 的 # 后面，不会发给服务器 / 进日志）
  python tools/opsctl.py report [sid]          现在生成复盘（缺省 = 最近一场），打印文件路径
  python tools/opsctl.py room [房间号或链接]   只做「检测房间」这一步，打印 web_rid
"""
import argparse
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
SYS = platform.system()
ICON = {"ok": "[ OK ]", "warn": "[ !! ]", "fail": "[FAIL]", "skip": "[ -- ]"}


def say(*a):
    print(*a, flush=True)


def load_cfg(path=None):
    from host.config import Config
    return Config(str(path or ROOT / "config.ini"))


def http_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def norm_room(s):
    """房间号 / 链接 → 纯数字 web_rid；认不出返回 ''（和 server.norm_room 同口径，19 位 room_id 不在这里换算）"""
    s = (s or "").strip()
    m = re.search(r"live\.douyin\.com/(\d+)", s)
    if m:
        return m.group(1)
    return s if re.fullmatch(r"\d{5,20}", s) else ""


def detect_room(cfg, arg="", detect=True, runner=subprocess.run):
    """→ (web_rid, 来源说明)。优先级：命令行给的 > 直播伴侣检测（macOS / Windows）> [ops] default_room"""
    r = norm_room(arg)
    if arg and not r:
        say(f"看不懂房间参数「{arg}」，忽略它")
    if r:
        return r, "命令行指定"
    if detect and cfg.b("ops", "detect_room") and SYS in ("Darwin", "Windows"):
        try:
            p = runner([sys.executable, str(ROOT / "tools" / "find_room.py"), "--webcast-mate"], capture_output=True, text=True, timeout=40, errors="replace")
            last = (p.stdout or "").strip().splitlines()[-1:] or [""]
            if p.returncode == 0 and re.fullmatch(r"\d{5,20}", last[0].strip()):
                return last[0].strip(), "从直播伴侣日志检测到"
            why = ((p.stderr or "").strip().splitlines() or ["没有输出"])[-1][:80]
        except Exception as e:
            why = repr(e)[:80]
        d = cfg.s("ops", "default_room")
        return d, f"没检测到直播伴侣的房间（{why}），用 [ops] default_room"
    d = cfg.s("ops", "default_room")
    return d, ("本系统没有直播伴侣，" if SYS == "Linux" else "") + "用 [ops] default_room"


def server_up(port, timeout=1.5):
    try:
        return http_json(f"http://127.0.0.1:{port}/config.json", timeout)
    except Exception:
        return None


def wait_server(port, secs=40, stop=None):
    t0 = time.time()
    while time.time() - t0 < secs and not (stop and stop()):
        c = server_up(port)
        if c is not None:
            return c
        time.sleep(0.5)
    return None


def render_checklist(items):
    out = []
    for it in items:
        out.append(f" {ICON.get(it['status'], '[ ?? ]')} {it['label']}：{it['detail']}")
        if it.get("fix") and it["status"] in ("warn", "fail"):
            out.append(f"          → {it['fix']}")
    return "\n".join(out)


def open_window(room, port):
    env = dict(os.environ, PORT=str(port))
    try:
        if SYS == "Windows":
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "open-live-window.ps1"), room], env=env)
        else:
            subprocess.Popen(["bash", str(ROOT / "open-live-window.sh"), room], env=env, cwd=str(ROOT))
        return True
    except Exception as e:
        say("   打开直播窗口失败：", repr(e)[:100])
        return False


def after_start(port, room, args, cfg, stop=lambda: False):
    """服务起来之后：自检清单 → 开窗口 → 打印地址（在线程里跑，不挡住服务日志）"""
    c = wait_server(port, 60, stop)
    if c is None:
        say("\n服务没有在 60 秒内起来：看上面的日志（或 data/logs/server.log）")
        return
    t0 = time.time()                      # 先等抓取器查完直播间状态（通常几秒），自检里的「直播间」才有意义
    while time.time() - t0 < 15 and not stop():
        try:
            fs = (http_json(f"http://127.0.0.1:{port}/ops/state", 3).get("fetcher") or {}).get("state")
        except Exception:
            break
        if fs not in ("init", "preparing", None):
            break
        time.sleep(0.5)
    say("\n" + "=" * 62)
    say(f" 一键开播自检（服务 http://localhost:{port}/ ，房间 {c.get('room') or room}）")
    say("=" * 62)
    items = []
    if cfg.b("ops", "health"):
        try:
            d = http_json(f"http://127.0.0.1:{port}/ops/health.json", 75)
            items = d.get("items", [])
            say(render_checklist(items))
            lan, tokf = d.get("lan") or [], d.get("token_file", "")
        except Exception as e:
            say(f" [FAIL] 自检接口出错：{repr(e)[:100]}")
            lan, tokf = [], ""
    else:
        lan, tokf = [], ""
    say("-" * 62)
    opened = False
    try:
        st = http_json(f"http://127.0.0.1:{port}/ops/state", 5)
    except Exception:
        st = {}
    if args.no_window or not cfg.b("ops", "window"):
        say(" 直播窗口：没自动打开（--no-window / [ops] window=false）；手动：./open-live-window.sh " + room)
    elif st.get("pages"):
        say(f" 直播窗口：已经有 {st['pages']} 个页面连着服务，不重复打开")
    else:
        opened = open_window(room, port)
        say(" 直播窗口：" + ("已打开（1920×1080，直播伴侣「窗口采集」选它）" if opened else "没打开成功，手动：./open-live-window.sh " + room))
    say(f" 弹幕页（浏览器源）：http://localhost:{port}/?room={room}&desk=xp")
    if cfg.b("ops", "enabled") and cfg.b("ops", "panel"):
        if lan:
            say(f" 手机控制面板：{lan[0]}" + ("" if len(lan) == 1 else f"   （还有：{' '.join(lan[1:])}）"))
            say(f" 面板令牌文件：{tokf}（不显示令牌；手机第一次打开输入它，或 python tools/opsctl.py panel-qr 扫带令牌的二维码）")
            if cfg.b("ops", "qr") and not args.no_qr:
                from ops.panel import qr_lines
                q = qr_lines(lan[0], try_install=True)
                say("\n".join("   " + r for r in q) if q else "   （没有装 qrcode 包，二维码略过；pip install qrcode 即可）")
        else:
            say(f" 手机控制面板：http://localhost:{port}/panel（只在本机；[ops] panel_lan=true 才开放局域网）")
    say("=" * 62 + "\n")


def cmd_live(a):
    cfg = load_cfg(a.config)
    room, why = detect_room(cfg, a.room, not a.no_detect)
    say(f"直播间：{room}（{why}）")
    up = server_up(a.port)
    if up is not None:
        say(f"端口 {a.port} 上已经有服务在跑（房间 {up.get('room')}），不重复启动。要换房间：先停掉旧的，或等它自动检测到新场次。")
        after_start(a.port, up.get("room") or room, a, cfg)
        return 0
    cmd = [sys.executable, str(ROOT / "tools" / "supervisor.py"), room, "--port", str(a.port), "--config", a.config] if not a.no_supervisor else \
          [sys.executable, str(ROOT / "backend" / "server.py"), room, "--port", str(a.port), "--config", a.config]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    if a.detach:
        logp = ROOT / (cfg.s("ops", "log_dir") or "data/logs") / "live-console.log"
        logp.parent.mkdir(parents=True, exist_ok=True)
        lf = open(logp, "a", encoding="utf-8")
        kw = {"creationflags": 0x00000008 | 0x00000200} if SYS == "Windows" else {"start_new_session": True}
        subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT), **kw)
        say(f"服务已在后台启动，日志：{logp}")
        after_start(a.port, room, a, cfg)
        return 0
    stop = threading.Event()
    p = subprocess.Popen(cmd, env=env, cwd=str(ROOT))
    threading.Thread(target=after_start, args=(a.port, room, a, cfg, stop.is_set), daemon=True).start()
    try:
        return p.wait()
    except KeyboardInterrupt:
        stop.set()
        try:
            p.wait(timeout=20)
        except Exception:
            p.kill()
        return 0


def cmd_status(a):
    cfg = load_cfg(a.config)
    if server_up(a.port) is None:
        say(f"端口 {a.port} 上没有服务。一键启动：./live.sh")
        return 1
    st = http_json(f"http://127.0.0.1:{a.port}/ops/state", 5)
    f = st.get("fetcher") or {}
    say(f"房间 {st.get('room')}：{f.get('anchor') or '?'}  状态 {f.get('state')}  {'直播中' if f.get('live') else '未开播' if f.get('live') is False else '未知'}  弹幕 {f.get('msgs')}  重连 {f.get('reconnects')}")
    s = st.get("session") or {}
    say("本场：" + (f"{s.get('sid')}  {s.get('events')} 条事件  计数 {s.get('counts')}" if s.get("active") else "没有进行中的一场"))
    d = http_json(f"http://127.0.0.1:{a.port}/ops/health.json", 75)
    say(render_checklist(d["items"]))
    return 0 if d.get("ok") else 2


def cmd_panel_qr(a):
    cfg = load_cfg(a.config)
    from ops.panel import ensure_token, lan_ips, qr_lines
    tok = ensure_token(cfg, ROOT, say)
    ips = lan_ips()
    if not ips:
        say("没有找到局域网地址（没连 Wi-Fi / 网线？）")
        return 1
    url = f"http://{ips[0]}:{a.port}/panel#token={tok}"
    q = qr_lines(url, try_install=True)
    say("扫码即可（令牌在 # 后面：只留在手机浏览器里，不会发给服务器、不进日志；这个二维码等于面板密码，别截图发出去）")
    say("\n".join("   " + r for r in q) if q else "（没有 qrcode 包，装不上；手动在手机输入面板地址，再输入令牌文件里的内容）")
    say(f"地址（不含令牌）：http://{ips[0]}:{a.port}/panel")
    return 0


def cmd_report(a):
    if server_up(a.port) is not None:
        q = ("?sid=" + a.arg) if a.arg else ""
        d = http_json(f"http://127.0.0.1:{a.port}/ops/report/make{q}", 120)
        if not d.get("ok"):
            say("没生成：" + str(d.get("error")))
            return 1
        say(d["summary"])
        say(f"网页：http://localhost:{a.port}{d['html']}   Markdown：{d['md']}（文件在 data/reports/）")
        return 0
    from ops import report as R, logs as L
    cfg = load_cfg(a.config)
    sid = a.arg or (L.list_sessions(Path(ROOT / (cfg.s("ops", "log_dir") or "data/logs")))[:1] or [{}])[0].get("sid")
    r = R.generate(cfg, sid, say, root=ROOT) if sid else None
    if not r:
        say("没有可生成的场次")
        return 1
    say(r["stats"]["summary"])
    say(f"文件：{r['html']}  {r['md']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["live", "status", "panel-qr", "report", "room"])
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    ap.add_argument("--config", default=str(ROOT / "config.ini"))
    for f in ("--no-window", "--no-detect", "--detach", "--no-supervisor", "--no-qr"):
        ap.add_argument(f, action="store_true")
    a = ap.parse_args(argv)
    a.room = a.arg
    if a.cmd == "live":
        return cmd_live(a)
    if a.cmd == "status":
        return cmd_status(a)
    if a.cmd == "panel-qr":
        return cmd_panel_qr(a)
    if a.cmd == "report":
        return cmd_report(a)
    cfg = load_cfg(a.config)
    r, why = detect_room(cfg, a.arg, not a.no_detect)
    print(f"（{why}）", file=sys.stderr)
    print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
