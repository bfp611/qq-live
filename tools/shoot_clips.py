# -*- coding: utf-8 -*-
"""高光切片（§11.13）页面级验证 + 截图（headless Chrome → screenshots/clips/）。假房间 100000000001（QQ_NO_FETCH=1，不连抖音、不推 Bark；临时配置），
   「屏幕」用一张图（[clips] test_source=image:…，不碰屏幕录制权限）+ 正弦波，跑真 ffmpeg：假开播 → 开始录 → 面板「现在切一个」/ 冷场烟花表演 / 观众发「来个高光」→ 剪出竖屏 MP4，
   面板「切片」页看状态 / 缩略图 / 预览 / 删除，权限没开时的提示（拦截状态接口模拟）。
   python tools/shoot_clips.py        （用 playwright；box 上用 /workspace/dev/pw/bin/python）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request
os.environ.setdefault("QQ_NO_FETCH", "1")
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "clips"; OUT.mkdir(parents=True, exist_ok=True)
from playwright.sync_api import sync_playwright
bad = []
def check(c, m):
    print(("ok   " if c else "FAIL ") + m)
    if not c: bad.append(m)
def quant(path):
    try:
        from PIL import Image
        Image.open(path).convert("RGB").quantize(256, method=Image.MEDIANCUT, dither=Image.NONE).save(path, optimize=True)
    except Exception: pass
def shot(pg, name, clip=None):
    p = OUT / name; pg.screenshot(path=str(p), **({"clip": clip} if clip else {})); quant(p); print("  →", p.relative_to(ROOT))
sk = socket.socket(); sk.bind(("127.0.0.1", 0)); PORT = sk.getsockname()[1]; sk.close(); BASE = f"http://127.0.0.1:{PORT}"
E = Path(tempfile.mkdtemp(prefix="clshoot-"))
RID = "100000000001"
old = {"name": "老观众阿花", "pts": 30, "chats": 5, "gifts": 0, "likes": 0, "follows": 0, "first": int(time.time()) - 86400 * 9, "last": int(time.time()) - 86400 * 2, "visits": 2, "visit_day": time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400 * 2)), "cmds": {"bsod": 2}}
(E / "p.json").write_text(json.dumps({"v": 1, "scopes": {RID: {"users": {"u_old": old}, "days": {}}}}, ensure_ascii=False), encoding="utf-8")
(E / "t.ini").write_text(f"""[music]
enabled = false
[tts]
backend = none
[ai]
base_url =
[agent]
test_endpoints = true
[idle]
startup_delay = 0
idle_after = 2
min_interval = 600
max_interval = 900
speak = true
llm = false
cursor_speed = 3
test_endpoints = true
[tips]
enabled = false
[perform]
enabled = false
[guard]
enabled = false
bark = false
sound = false
[play]
data_file = {E}/p.json
[ai_plus]
memory_file = {E}/m.json
memory_greet_min_visits = 2
[ops]
log_dir = {E}/logs
report_dir = {E}/r
panel_token_file = {E}/tok.txt
overrides_file = {E}/ov.json
detect_room = false
autoswitch = false
[welcome]
enabled = false
[giftfx]
enabled = false
[clips]
mode = live
test_source = image:{ROOT}/screenshots/perform/01_fireworks_intro_and_tip.png
out_dir = {E}/clips
min_gap = 5
keep_secs = 40
fps = 12
out_bitrate = 2500
reply = true
viewer_gap = 5
bark = false
""", encoding="utf-8")
PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
srv = subprocess.Popen([str(PY) if PY.exists() else sys.executable, str(ROOT / "backend/server.py"), RID, "--port", str(PORT), "--config", str(E / "t.ini")],
                       env=dict(os.environ, TTS_BACKEND="none", PYTHONIOENCODING="utf-8"), stdout=open(E / "srv.out", "w"), stderr=subprocess.STDOUT)
def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r: return json.loads(r.read())
def ev(**kw): return get("/qq/event?" + urllib.parse.urlencode(kw))
def wait_for(fn, s=30, step=0.25):
    t = time.time()
    while time.time() - t < s:
        v = fn()
        if v: return v
        time.sleep(step)
    return None
try:
    for _ in range(100):
        try: urllib.request.urlopen(BASE + "/config.json", timeout=2); break
        except Exception: time.sleep(0.4)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1280, "height": 720}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.goto(BASE + f"/?room={RID}&desk=xp&xp_boot=0&host=1&musicdemo=0")
        check(wait_for(lambda: get("/agent/state").get("clients"), 15), "页面连上了（假房间）")
        pg.wait_for_timeout(2500)
        body = lambda: pg.evaluate("document.body.innerText")
        said = lambda who, extra="试试": [l for l in body().split("\n") if who in l and extra in l]      # 群聊消息行（成员列表里也有昵称，所以要带上台词里的字）
        body = lambda: pg.evaluate("document.body.innerText")
        tok = (E / "tok.txt").read_text().strip()
        def api(path, body_=None):
            req = urllib.request.Request(BASE + "/ops/api/" + path, method="POST" if body_ is not None else "GET", data=json.dumps(body_).encode() if body_ is not None else None, headers={"X-Token": tok, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r_: return json.loads(r_.read())
        cs = lambda: api("state")["clips"]
        # ---- 没开播：不录 ----
        check(cs()["enabled"] and not cs()["recording"], "没开播：不录（mode=live）")
        # ---- 开播 → 开始录 ----
        ev(t="live", live=1)
        check(wait_for(lambda: cs()["recording"], 30), f"假开播：开始录制 {cs()['err']}")
        check(wait_for(lambda: cs()["buffer_secs"] >= 12, 40), f"滚动缓冲里有 {cs()['buffer_secs']} 秒")
        pg2 = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2); pg2.goto(BASE + "/panel#token=" + tok); pg2.wait_for_timeout(1800)
        pg2.click("#bar button[data-t=clips]"); pg2.wait_for_timeout(1500)
        shot(pg2, "01_panel_recording.png")
        # ---- 冷场表演烟花 → 自动标记高光 → 剪 ----
        r = api("do", {"action": "perform_now", "which": "fireworks"})
        for _ in range(20):
            if r.get("ok"): break
            time.sleep(0.5); r = api("do", {"action": "perform_now", "which": "fireworks"})
        check(r.get("ok"), f"开一场烟花表演：{r}")
        check(wait_for(lambda: cs()["pending"] >= 1, 30), "表演开演时标记了高光：排了一个剪片任务")
        check(wait_for(lambda: cs()["stats"]["clips"] >= 1, 90), f"后 15 秒录完，剪好了一条：{cs()['last']}")
        c1 = [f for f in cs()["files"] if f["kind"] == "fireworks"]
        check(len(c1) == 1 and c1[0]["thumb"], f"文件名 <时间>_fireworks.mp4：{[f['name'] for f in cs()['files']]}")
        # ---- 观众发「来个高光」 ----
        time.sleep(6)
        ev(t="chat", uid="v1", name="小朋友", text="来个高光")
        check(wait_for(lambda: any("小朋友" in l and "切下来了" in l for l in body().split("\n")), 20), "群聊里回一句「这一段我切下来了」")
        shot(pg, "02_viewer_highlight_reply.png")
        check(wait_for(lambda: cs()["stats"]["clips"] >= 2, 90), f"观众点的也剪好了：{cs()['last']}")
        check(sorted(f["kind"] for f in cs()["files"]) == ["fireworks", "viewer"], "两条：fireworks + viewer")
        # ---- 竖屏文件 ----
        f = [x for x in cs()["files"] if x["kind"] == "fireworks"][0]
        mp4 = E / "clips" / f["name"]
        pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4)], capture_output=True, text=True).stdout)
        v = next(s_ for s_ in pr["streams"] if s_["codec_type"] == "video")
        check(v["width"] == 1080 and v["height"] == 1920 and any(s_["codec_type"] == "audio" for s_ in pr["streams"]) and 24 <= float(pr["format"]["duration"]) <= 26.5, f"1080×1920 竖屏 + 声音 + 约 25 秒：{v['width']}x{v['height']} {pr['format']['duration']}s")
        fr = OUT / "03_vertical_frame.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "11", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=432:-2", str(fr)]); quant(fr); print("  →", fr.relative_to(ROOT))
        check(fr.exists(), "竖屏画面：前景铺满宽度，上下是模糊的放大背景")
        # ---- 面板：列表 / 预览 / 删除 ----
        pg2.wait_for_timeout(2500)
        shot(pg2, "04_panel_clip_list.png")
        pg2.locator(".cl .acts button", has_text="预览").first.click(); pg2.wait_for_timeout(1500)
        check(pg2.evaluate("document.querySelector('.cl video') && document.querySelector('.cl video').readyState >= 1"), "面板里预览：视频加载好了")
        shot(pg2, "05_panel_preview.png")
        n_before = len(cs()["files"])
        pg2.once("dialog", lambda d_: d_.accept())
        pg2.locator(".cl .acts button", has_text="删除").last.click()
        check(wait_for(lambda: len(cs()["files"]) == n_before - 1, 10), "面板里删除一条")
        check(len(list((E / "clips").glob("*.mp4"))) == n_before - 1, "磁盘上的文件和缩略图一起没了")
        # ---- 开关 / 手动录制 ----
        s = api("state"); check(any(i["key"] == "clips.enabled" for g in s["switches"] for i in g["items"]), "面板开关里有「高光切片」")
        # ---- 下播 → 停 ----
        ev(t="live", live=0)
        check(wait_for(lambda: not cs()["recording"], 40), "下播：停止录制，缓冲清掉")
        r = api("do", {"action": "clips_record", "on": True}); check(r.get("ok"), "面板手动开始录制")
        check(wait_for(lambda: cs()["recording"], 30), "手动录制：没开播也录")
        r = api("do", {"action": "clips_record", "on": False}); check(wait_for(lambda: not cs()["recording"], 40), "手动停止")
        # ---- 屏幕录制权限没开时的提示（拦截状态接口，把 perm 改成没授权 —— 只用来截图） ----
        def fake(route):
            resp = route.fetch(); d_ = resp.json()
            d_["clips"]["perm"] = {"ok": False, "msg": "本服务是被 launchd / 后台守护直接拉起的（没有终端 App 当父进程），要给 python 可执行文件开屏幕录制：/path/to/python3.13（系统设置 → 隐私与安全性 → 屏幕与系统音频录制，点「+」选它）。开完要重启服务。"}
            d_["clips"]["err"] = "没有「屏幕录制」权限"; d_["clips"]["recording"] = False
            route.fulfill(response=resp, json=d_)
        pg3 = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2); pg3.route("**/ops/api/state", fake); pg3.goto(BASE + "/panel#token=" + tok); pg3.wait_for_timeout(1800)
        pg3.click("#bar button[data-t=clips]"); pg3.wait_for_timeout(1500)
        check(pg3.locator(".perm.bad").count() == 1, "没权限：面板显示红色提示框")
        shot(pg3, "06_panel_permission_missing.png")
        check(not errs, f"页面没有 JS 错误 {errs}")
        b.close()
finally:
    srv.terminate()
print("PASS" if not bad else "FAIL " + str(bad)); sys.exit(1 if bad else 0)
