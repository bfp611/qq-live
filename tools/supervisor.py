#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务进程看门狗：崩溃自动重启（退避），手机面板的「重启服务」（退出码 75）立即重启。macOS / Linux / Windows 通用，只用标准库。

  python tools/supervisor.py [房间号或链接] [--port 8765] [--host H]      # 参数原样交给 backend/server.py
  环境变量 / config.ini 的 [ops]：sup_delay（首次重启等几秒，默认 3，之后翻倍到 30）、sup_max_crashes（连续「刚启动就崩」几次后放弃，默认 8）

规则：子进程活过 60 秒就算「稳定」，崩溃计数清零；退出码 0 = 正常关闭（不重启）；退出码 75 = 要求重启（立即）；其它 = 崩溃（退避重启）。
Ctrl+C 会把信号转给子进程并正常收尾。日志同时写到 data/logs/supervisor.log（轮转，最多 3×1MB）。
"""
import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
RESTART_CODE = 75


def cfg_val(path, key, default):
    try:
        from host.config import Config
        c = Config(str(path))
        return type(default)(float(c.s("ops", key))) if isinstance(default, (int, float)) else c.s("ops", key)
    except Exception:
        return default


class Logger:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size > 1_000_000:
                os.replace(self.path, str(self.path) + ".1")
        except Exception:
            pass

    def __call__(self, *a):
        line = time.strftime("%H:%M:%S") + " [supervisor] " + " ".join(str(x) for x in a)
        print(line, flush=True)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d ") + line + "\n")
        except Exception:
            pass


def supervise(cmd, env=None, delay=3.0, max_crashes=8, stable=60.0, log=print, stop_evt=None, popen=subprocess.Popen, now=time.time, poll_s=0.2):
    """循环拉起 cmd。返回最后一次退出码。stop_evt 置位 = 收到停止信号。popen / now 可注入（测试用）。"""
    stop_evt = stop_evt or threading.Event()
    crashes, d, runs, code = 0, delay, 0, 0
    while not stop_evt.is_set():
        t0 = now()
        runs += 1
        log(f"启动服务（第 {runs} 次）…")
        p = popen(cmd, env=env)
        sup_state["child"] = p
        while p.poll() is None and not stop_evt.is_set():
            time.sleep(poll_s)
        if stop_evt.is_set() and p.poll() is None:
            try:
                p.terminate()
                p.wait(timeout=15)
            except Exception:
                p.kill()
        code = p.wait()
        up = now() - t0
        if stop_evt.is_set():
            log("收到停止信号，已关闭服务")
            return code
        if code == 0:
            log("服务正常退出，不再重启")
            return 0
        if code == RESTART_CODE:
            log(f"服务要求重启（退出码 {RESTART_CODE}，已运行 {int(up)} 秒），马上拉起")
            crashes, d = 0, delay
            continue
        if up >= stable:
            crashes, d = 0, delay
        crashes += 1
        if crashes > max_crashes:
            log(f"连续 {crashes - 1} 次启动后很快就崩溃（最后退出码 {code}），放弃。看 data/logs/server.log 找原因")
            return code
        log(f"服务崩溃（退出码 {code}，运行了 {int(up)} 秒；连续第 {crashes} 次），{d:g} 秒后重启")
        stop_evt.wait(d)
        d = min(30.0, d * 2)
    return code


sup_state = {"child": None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("room", nargs="?", default="")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default=None)
    ap.add_argument("--config", default=str(ROOT / "config.ini"))
    a = ap.parse_args(argv)
    log = Logger(ROOT / cfg_val(a.config, "log_dir", "data/logs") / "supervisor.log")
    delay = float(cfg_val(a.config, "sup_delay", 3.0))
    maxc = int(cfg_val(a.config, "sup_max_crashes", 8))
    cmd = [sys.executable, str(ROOT / "backend" / "server.py")] + ([a.room] if a.room else []) + ["--port", str(a.port), "--config", a.config] + (["--host", a.host] if a.host else [])
    env = dict(os.environ, QQ_SUPERVISED="1", PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    stop = threading.Event()

    def on_sig(sig, frm):
        stop.set()
        ch = sup_state.get("child")
        if ch and ch.poll() is None:
            try:
                ch.send_signal(signal.SIGINT if hasattr(signal, "SIGINT") else signal.SIGTERM)
            except Exception:
                pass
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, on_sig)
        except Exception:
            pass
    code = supervise(cmd, env, delay, maxc, 60.0, log, stop)
    sys.exit(0 if stop.is_set() else code)


if __name__ == "__main__":
    main()
