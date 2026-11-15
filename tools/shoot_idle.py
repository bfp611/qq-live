# -*- coding: utf-8 -*-
"""开发用：无头 Chrome 录制「冷场时猪猪侠自己玩电脑」——真实光标速度、真 LLM 旁白（speak 打开，旁白出现在群聊窗口里）。
   依次演若干活动 → 观众弹幕打断 → 观众指令打断 → 安静后自动开工；截图 + 录像 → gif。
   python tools/shoot_idle.py [http://localhost:8780] [输出目录=screenshots/idle]
   需要：服务已启动（[agent]/[idle] test_endpoints=true）、playwright、ffmpeg；页面用 demo 模式（无假弹幕、有假歌曲）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import sys, json, time, shutil, subprocess, urllib.parse, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8780").rstrip("/")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "screenshots" / "idle"); OUT.mkdir(parents=True, exist_ok=True)

def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r: return json.loads(r.read())
def chat(text, uid="v1", full=True):
    return get("/agent/say?" + urllib.parse.urlencode({"text": text, "uid": uid, "name": "小明", "dry": "0", "full": "1" if full else "0"}))
def cfg(**kv): return get("/agent/idle?" + "&".join(f"cfg={k}:{v}" for k, v in kv.items()))
def wins(pg): return pg.evaluate("WM.wins.filter(w=>!w.closed).map(w=>w.id)")
def wait_done(pg, secs=90):
    t = time.time()
    while time.time() - t < secs:
        if not get("/agent/idle")["running"]: return True
        pg.wait_for_timeout(300)
def last(): return (get("/agent/idle")["history"] or [{}])[-1]

# (活动, 截图时机秒)
SCRIPT = [("browse_ie", [4, 9]), ("play_minesweeper", [5, 11]), ("comment_song", [4, 8]), ("notepad_write", [5, 9]),
          ("qq_chat", [8, 18]), ("arrange_icons", [4]), ("change_wallpaper", [4])]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(OUT / "_vid"), record_video_size={"width": 1280, "height": 720})
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/?demo=1&demoquiet=1&host=1&desk=xp&musicdemo=1"); pg.wait_for_timeout(3000)
    cfg(speak="true", llm="true", weights="calc:1")
    base = wins(pg); print("base windows:", base)
    for name, shots in SCRIPT:
        t0 = time.time(); r = get(f"/agent/idle?run={name}")
        if r.get("ok") is False: print(name, "不能开始:", r.get("error")); continue
        for k, s in enumerate(shots):
            pg.wait_for_timeout(max(0, int((s - (time.time() - t0)) * 1000)))
            pg.screenshot(path=str(OUT / f"{name}-{k+1}.png"))
        wait_done(pg); pg.wait_for_timeout(600)
        h = last(); left = [w for w in wins(pg) if w not in base]
        print(f"{name:18} {h.get('result')!s:12} {h.get('ms')}ms {h.get('llm') or '模板'} lines={h.get('lines')} 残留窗口={left}")
    # 打断 1：弹幕
    get("/agent/idle?run=browse_ie"); pg.wait_for_timeout(5000)
    pg.screenshot(path=str(OUT / "interrupt-1-before.png")); t = time.time(); chat("哈哈哈主播好呀")
    while get("/agent/idle")["running"] and time.time() - t < 10: pg.wait_for_timeout(100)
    print(f"弹幕打断：{time.time()-t:.2f}s 后服务端停手")
    pg.wait_for_timeout(300); pg.screenshot(path=str(OUT / "interrupt-2-chat.png")); pg.wait_for_timeout(2500)
    pg.screenshot(path=str(OUT / "interrupt-3-cleaned.png")); print("  打断后窗口:", wins(pg), "页面队列:", pg.evaluate("AG.queue.length"), "last:", last().get("result"))
    # 打断 2：观众指令，随后正常执行
    get("/agent/idle?run=notepad_write"); pg.wait_for_timeout(6000)
    r = get("/agent/say?" + urllib.parse.urlencode({"text": "打开计算器", "uid": "v2", "name": "小明", "dry": "0"})); pg.wait_for_timeout(5000)
    pg.screenshot(path=str(OUT / "interrupt-4-command.png")); print("指令打断：", [a["action"] for a in r.get("actions", [])], "窗口:", wins(pg))
    pg.evaluate("AG.exec([{action:'close_window',target:'calc'}])"); pg.wait_for_timeout(2500)
    # 自动开工：弹幕不断时不开，安静够久才开
    cfg(idle_after=8, startup_delay=1, min_interval=3, max_interval=5, weights="comment_song:1", repeat_gap=0)
    get("/agent/idle?reset=1"); st0 = get("/agent/idle")["stats"]["started"]
    for i in range(5): chat(f"聊天{i}", uid=f"c{i}"); pg.wait_for_timeout(2000)
    print("有人说话期间自动开工次数:", get("/agent/idle")["stats"]["started"] - st0, "(应为 0)", get("/agent/idle")["why"])
    t = time.time()
    while time.time() - t < 40 and get("/agent/idle")["stats"]["started"] == st0: pg.wait_for_timeout(500)
    print(f"安静后 {time.time()-t:.0f}s 自动开工：", get("/agent/idle")["running"]); pg.wait_for_timeout(4000)
    pg.screenshot(path=str(OUT / "auto-start.png")); wait_done(pg)
    print("自动开工结果:", last().get("name"), last().get("result"), "页面报错:", errs)
    vp = pg.video.path(); ctx.close(); b.close()
shutil.move(vp, str(OUT / "idle-demo.webm"))
shutil.rmtree(OUT / "_vid", ignore_errors=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(OUT / "idle-demo.webm"), "-vf",
                "fps=3,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48[p];[b][p]paletteuse=dither=bayer:bayer_scale=5", str(OUT / "idle-demo.gif")], check=True)
(OUT / "idle-demo.webm").unlink()
try:                                  # PNG 量化成 96 色，仓库小很多
    from PIL import Image
    for f in OUT.glob("*.png"): Image.open(f).convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(f, optimize=True)
except ImportError: pass
print("done ->", OUT)
