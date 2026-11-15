#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Linux 端到端测试（不需要真的网易云）：在 D-Bus 会话总线上起一个假的 MPRIS 播放器（tools/mock_mpris.py，假装是 netease-cloud-music），
让真正的 backend/music.py（MprisSource + playerctl）读到「正在播放」，再让真正的 backend/jukebox.py 走 点歌 → MPRIS OpenUri → 核对 的流程。
依赖：playerctl、dbus-run-session、pip install dbus-fast（只给这个测试用）。运行：
    dbus-run-session -- .venv/bin/python tools/test_mpris_e2e.py
"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import osmusic  # noqa: E402
from host.config import Config  # noqa: E402
from jukebox import Jukebox, Song  # noqa: E402
from music import Music  # noqa: E402

PY = os.environ.get("MOCK_PY", sys.executable)
fails = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond:
        fails.append(name)


def start_mock(*args):
    p = subprocess.Popen([PY, str(ROOT / "tools" / "mock_mpris.py"), *args], stdout=subprocess.PIPE, text=True)
    assert "ready" in p.stdout.readline()
    return p


async def wait_for(fn, t=6.0):
    t0 = time.time()
    while time.time() - t0 < t:
        v = fn()
        if v:
            return v
        await asyncio.sleep(0.2)
    return None


async def main():
    if not shutil.which("playerctl"):
        sys.exit("需要 playerctl")
    tmp = Path(tempfile.mkdtemp())
    logs, events = [], []
    log = lambda *a: logs.append(" ".join(map(str, a)))
    openlog = tmp / "open.log"

    # ---------- 1. 读「正在播放」 ----------
    mock = start_mock("--log", str(openlog), "--start", "1003")
    other = start_mock("--name", "firefox.instance42", "--start", "1002")       # 干扰项：别的播放器也在播
    try:
        m = Music(tmp, events.append, log=log, interval=0.4)
        check("music: 选中 MPRIS 读取", m.method == "mpris", m.method)
        m.start()
        st = await wait_for(lambda: m.state.get("on") and m.state)
        check("music: 读到网易云而不是 firefox", bool(st) and st["title"] == "坏女孩", str(st and st.get("title")))
        check("music: 歌手/专辑/时长", bool(st) and st["artist"].startswith("徐良") and st["album"] == "不良少年" and abs(st["duration"] - 242) < 1, str(st))
        check("music: 进度在走", bool(st) and 0 <= st["pos"] < 20 and st["playing"], str(st and st["pos"]))
        # ---------- 1b. AI 主播操作桌面用的媒体键：暂停 / 继续 / 下一首 / 上一首 ----------
        cfg0 = Config(ROOT / "config.ini")
        ctl = Jukebox(cfg0, m, log, lambda *a, **k: None, lambda *a, **k: None, lambda *a: None).control
        ok = await ctl.command("pause")
        check("control: pause 发出", ok)
        st = await wait_for(lambda: m.state.get("on") and not m.state.get("playing") and m.state)
        check("control: 暂停后 playing=False", bool(st))
        check("control: play 发出", await ctl.command("play"))
        st = await wait_for(lambda: m.state.get("playing") and m.state)
        check("control: 继续后 playing=True", bool(st))
        t_before = m.state.get("title")
        check("control: next 发出", await ctl.command("next"))
        st = await wait_for(lambda: m.state.get("title") and m.state.get("title") != t_before and m.state)
        check("control: 下一首后歌名变了", bool(st), f"{t_before} -> {m.state.get('title')}")
        t_next = m.state.get("title")
        check("control: previous 发出", await ctl.command("previous"))
        st = await wait_for(lambda: m.state.get("title") and m.state.get("title") != t_next and m.state)
        check("control: 上一首后歌名变了", bool(st), f"{t_next} -> {m.state.get('title')}")
        check("control: 未知命令返回 False", not await ctl.command("explode"))
        # ---------- 2. 点歌：MPRIS OpenUri ----------
        cfg = Config(ROOT / "config.ini")
        jb = Jukebox(cfg, m, log, lambda *a, **k: None, lambda *a, **k: None, lambda *a: None)
        jb.verify_timeout = 5
        check("jukebox: 控制方式含 MPRIS OpenUri", [n for n, _ in jb.control.open_methods()][:1] == ["MPRIS OpenUri"],
              str([n for n, _ in jb.control.open_methods()]))
        song = Song({"id": 1002, "name": "稻香", "ar": [{"name": "周杰伦"}], "dt": 223000}, "测试观众", "u1")
        ok = await jb.play(song)
        check("jukebox: OpenUri → 核对通过", ok, [l for l in logs if "点歌" in l][-1:] and logs[-1])
        check("jukebox: 播放器收到 orpheus 链接", openlog.exists() and osmusic.orpheus_url(1002) in openlog.read_text())
        check("music: 正在播放变成《稻香》", m.state.get("title") == "稻香", m.state.get("title"))
        # ---------- 3. 没版权的歌：客户端无视 → 核对失败 → 跳过 ----------
        ghost = Song({"id": 999999, "name": "不存在的歌", "ar": [{"name": "某人"}], "dt": 100000}, "x", "u2")
        t0 = time.time()
        ok = await jb.play(ghost)
        check("jukebox: 客户端不响应的歌被判为不可播放", ok is False and 4 < time.time() - t0 < 12, f"{time.time() - t0:.1f}s")
        # ---------- 4. 切歌 ----------
        before = m.state.get("title")
        await jb.control.next()
        await wait_for(lambda: m.state.get("title") != before)
        check("control.next: playerctl next 生效", m.state.get("title") != before, f"{before} → {m.state.get('title')}")
        await m.stop()
    finally:
        mock.kill(); other.kill()

    # ---------- 5. OpenUri 没效果 → 回退 xdg-open ----------
    fake = tmp / "bin"; fake.mkdir()
    xlog = tmp / "xdg.log"
    (fake / "xdg-open").write_text(f'#!/bin/sh\necho "$1" >> {xlog}\n')
    (fake / "xdg-open").chmod(0o755)
    old_path = os.environ["PATH"]
    os.environ["PATH"] = f"{fake}:{old_path}"
    mock = start_mock("--ignore-open", "--start", "1001")
    try:
        logs.clear()
        m = Music(tmp, events.append, log=log, interval=0.4)
        m.start()
        await wait_for(lambda: m.state.get("on"))
        jb = Jukebox(Config(ROOT / "config.ini"), m, log, lambda *a, **k: None, lambda *a, **k: None, lambda *a: None)
        jb.verify_timeout = 2
        check("jukebox: 方式顺序 MPRIS → xdg-open", [n for n, _ in jb.control.open_methods()] == ["MPRIS OpenUri", "xdg-open"])
        ok = await jb.play(Song({"id": 1002, "name": "稻香", "ar": [{"name": "周杰伦"}], "dt": 223000}, "x", "u3"))
        check("jukebox: 两种方式都试过，最后判不可播放", ok is False and xlog.exists() and osmusic.orpheus_url(1002) in xlog.read_text(), str(logs[-2:]))
        await m.stop()
    finally:
        mock.kill()
        os.environ["PATH"] = old_path

    # ---------- 6. 没有播放器在运行 ----------
    m = Music(tmp, events.append, log=log, interval=0.4)
    check("music: 没有播放器时读取返回 None", await m.read_now() is None)
    print("\n失败：", fails if fails else "无")
    sys.exit(1 if fails else 0)


asyncio.run(main())
