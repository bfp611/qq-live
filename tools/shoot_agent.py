# -*- coding: utf-8 -*-
"""开发用：无头 Chrome 录制「AI 主播操作 XP 桌面」——真实光标速度，经 /agent/say 走完整管线，截图 + 录像 → gif。
   python tools/shoot_agent.py [http://localhost:8780] [输出目录=screenshots/agent]
   需要：服务已启动（config.ini [agent] test_endpoints=true）、playwright、ffmpeg"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import sys, json, time, shutil, subprocess, urllib.parse, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8780").rstrip("/")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "screenshots" / "agent"); OUT.mkdir(parents=True, exist_ok=True)

def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r: return json.loads(r.read())
def say(text, via=None, name="小明", uid=None):
    q = {"text": text, "name": name, "uid": uid or "s%d" % (abs(hash(text)) % 99999), "dry": "0"}
    if via: q["via"] = via
    return get("/agent/say?" + urllib.parse.urlencode(q))
def wait_job(pg, text, secs=40):
    t = time.time()
    while time.time() - t < secs:
        h = [x for x in get("/agent/state")["history"] if x["text"][:20] == text[:20]]
        if h and h[-1].get("result") is not None: return h[-1]
        pg.wait_for_timeout(250)

# (标题, 弹幕, 截图时机秒数(动作进行中), via)
SCRIPT = [("01-open-ra2", "打开红警", [0.5, 1.4], None), ("02-blocked", "红警挡住了", [0.8, 1.8], None), ("03-close", "把红警关掉", [0.9], None),
          ("04-notepad-type", "在记事本里写：猪猪侠最帅", [1.6, 2.6], None), ("05-wallpaper", "换壁纸", [1.4, 2.6], None),
          ("06-start-menu", "打开开始菜单", [1.0], None), ("07-minesweeper", "玩扫雷", [2.5, 4.0], None),
          ("08-llm-natural", "主播能不能把窗口都整理一下，太乱了", [1.5, 3.0], "llm"), ("09-close-chat-guard", "把群聊关了", [1.6], None)]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(OUT / "_vid"), record_video_size={"width": 1280, "height": 720})
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/?desk=xp"); pg.wait_for_timeout(2500)
    print("agent clients:", get("/agent/state")["clients"])
    for name, text, shots, via in SCRIPT:
        t0 = time.time(); r = say(text, via)
        for k, s in enumerate(shots):
            pg.wait_for_timeout(max(0, int((s - (time.time() - t0)) * 1000)))
            pg.screenshot(path=str(OUT / f"{name}-{k+1}.png"))
        h = wait_job(pg, text) or {}
        print(f"{name:22} via={r.get('via')} nlu={r.get('ms')}ms page={h.get('page_ms')}ms {[(x['action'], x['ok']) for x in h.get('result') or []]} {r.get('say')!r}")
        pg.wait_for_timeout(700)
    pg.screenshot(path=str(OUT / "10-before-restore.png"))
    pg.wait_for_function("window.AG && AG.chatVis && AG.chatVis() > 0.5", timeout=45000)   # 守卫：群聊被关后自动还原
    pg.wait_for_timeout(1500); pg.screenshot(path=str(OUT / "11-chat-restored.png"))
    print("chat auto-restored; page errors:", errs)
    vp = pg.video.path(); ctx.close(); b.close()
shutil.move(vp, str(OUT / "agent-demo.webm"))
shutil.rmtree(OUT / "_vid", ignore_errors=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT / "agent-demo.webm"), "-vf", "fps=8,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4", str(OUT / "agent-demo.gif")], check=True)
print("done ->", OUT)
