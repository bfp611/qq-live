# -*- coding: utf-8 -*-
"""礼物 / 点赞联动（§11.12）页面级验证 + 截图（headless Chrome → screenshots/giftfx/）。假房间 100000000001（QQ_NO_FETCH=1，不连抖音、不推 Bark；临时配置），
   往里灌假事件（/qq/event?t=gift|like|follow|chat）：1 钻小烟花 + 点名感谢（连击合并成一条）、10 钻点播表演、点赞 300 全屏特效、
   关注点名 + 记进好友、100 钻假重装系统（之后 10 分钟内再来一份改放流星雨 + 全屏感谢）、面板开关即时生效。
   python tools/shoot_giftfx.py        （用 playwright；box 上用 /workspace/dev/pw/bin/python）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request
os.environ.setdefault("QQ_NO_FETCH", "1")
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "giftfx"; OUT.mkdir(parents=True, exist_ok=True)
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
E = Path(tempfile.mkdtemp(prefix="gfshoot-"))
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
merge_secs = 1
ask_secs = 6
gap_secs = 1
big_scene = setup
like_step = 300
[xp]
setup_secs = 6
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
        gfx = lambda: pg.evaluate("(window.GFX && GFX.log || []).map(x => x.kind)")
        tok = (E / "tok.txt").read_text().strip()
        def api(path, body_=None):
            req = urllib.request.Request(BASE + "/ops/api/" + path, method="POST" if body_ is not None else "GET", data=json.dumps(body_).encode() if body_ is not None else None, headers={"X-Token": tok, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r_: return json.loads(r_.read())
        hist = lambda: get("/agent/idle")["history"]
        # ---- 1 钻：小烟花 + 点名感谢（连击 3 个合并成一条） ----
        for c in (1, 2, 3): ev(t="gift", uid="g1", name="小花", gift="玫瑰", count=c, value=1); time.sleep(0.3)
        check(wait_for(lambda: "small_fireworks" in gfx(), 20), "1 钻档：页面放了小烟花")
        pg.wait_for_timeout(500); shot(pg, "01_small_gift.png")
        check(wait_for(lambda: "谢谢小花送的玫瑰×3" in body(), 20), "点名感谢，连击合并成『玫瑰×3』一条")
        check(body().count("谢谢小花送的玫瑰") <= 2 and api("state")["giftfx"]["stats"]["t1"] == 1, "连击没有重复感谢（群聊一行 + 头像气泡一处，只排了一个任务）")
        check(api("state")["giftfx"]["stats"]["t1"] == 1, "统计：1 档 1 次")
        # ---- 10 钻：感谢 + 告诉他可以点什么，他点了就演 ----
        ev(t="gift", uid="g2", name="阿强", gift="棒棒糖", count=1, value=10)
        check(wait_for(lambda: "可以点" in body() or "点一个表演" in body() or "想看什么" in body() or "30秒" in body() or "6秒" in body(), 25), "10 钻档：先感谢，再问他想看什么")
        shot(pg, "02_ask_request.png")
        ev(t="chat", uid="g2", name="阿强", text="放烟花")
        check(wait_for(lambda: any(r_.get("name") == "perf_fireworks" for r_ in hist()), 40), "他点了『放烟花』：演的就是烟花")
        pg.wait_for_timeout(1500); shot(pg, "03_requested_fireworks.png")
        check(api("state")["giftfx"]["stats"]["requested"] == 1, "点播的那句弹幕被联动吃掉（统计里 requested=1）")
        wait_for(lambda: not api("state")["giftfx"]["busy"] and api("state")["giftfx"]["queue"] == 0, 60)
        # ---- 点赞 300：全屏特效 ----
        ev(t="like", uid="l1", name="点赞怪", count=300)
        check(wait_for(lambda: "like" in gfx(), 20), "点赞累计 300：页面放了全屏点赞特效")
        pg.wait_for_timeout(700); shot(pg, "04_likes.png")
        wait_for(lambda: not api("state")["giftfx"]["busy"], 30)
        # ---- 关注：点名感谢 + 记进好友 ----
        ev(t="follow", uid="f1", name="新朋友小朋"); 
        check(wait_for(lambda: api("state")["giftfx"]["friends"] >= 1, 20), "关注：记进好友（friend 标记）")
        check(wait_for(lambda: "小朋" in body() and "关注" in body(), 25), "关注：群聊里点名感谢")
        shot(pg, "05_follow_friend.png")
        wait_for(lambda: not api("state")["giftfx"]["busy"], 30)
        # ---- 100 钻：假重装系统 ----
        ev(t="gift", uid="g3", name="土豪哥", gift="嘉年华", count=1, value=500)
        check(wait_for(lambda: pg.evaluate("!!(window.XP && XP.screen)"), 40), "100 钻档：页面进了假重装系统画面")
        pg.wait_for_timeout(2500); shot(pg, "06_big_setup.png")
        check(wait_for(lambda: pg.locator(".gfx").count() >= 1 and not pg.evaluate("!!XP.screen"), 90), "装完回到桌面，随即弹出全屏感谢卡片")
        pg.wait_for_timeout(900); shot(pg, "07_after_setup_thanks.png")
        r = wait_for(lambda: next((x for x in hist() if x.get("name") == "perf_setup" and x.get("result")), None), 90)
        check(r and r["result"] == "完成", f"重装演完：{r and r['result']}")
        wait_for(lambda: not api("state")["giftfx"]["busy"], 40)
        # ---- 再来一份：重型冷却中 → 流星雨 + 全屏感谢 ----
        ev(t="gift", uid="g4", name="富婆姐", gift="跑车", count=1, value=500)
        check(wait_for(lambda: "big_thanks" in gfx(), 40), "10 分钟内再来一份大礼：改放流星雨 + 全屏感谢")
        pg.wait_for_timeout(1500); shot(pg, "08_big_meteor.png")
        check(pg.locator(".gfx").count() >= 1, "全屏感谢卡片在屏幕上")
        # ---- 面板 ----
        s = api("state"); check(any(i["key"] == "giftfx.enabled" for g in s["switches"] for i in g["items"]), "面板开关里有「礼物联动」")
        check(s["giftfx"]["stats"]["t3"] == 2 and s["giftfx"]["stats"]["t2"] == 1 and s["giftfx"]["stats"]["likes"] == 1, f"面板状态：{s['giftfx']['stats']}")
        pg2 = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2); pg2.goto(BASE + "/panel#token=" + tok); pg2.wait_for_timeout(1800)
        pg2.click("#bar button[data-t=sw]") if pg2.locator("#bar button[data-t=sw]").count() else None; pg2.wait_for_timeout(500)
        shot(pg2, "09_panel.png")
        r = api("toggle", {"key": "giftfx.enabled", "on": False}); check(r.get("ok"), "面板关掉礼物联动")
        n0 = api("state")["giftfx"]["stats"]["gifts"]; ev(t="gift", uid="g5", name="关了之后", gift="玫瑰", count=1, value=1); time.sleep(4)
        check(api("state")["giftfx"]["stats"]["gifts"] == n0 and "small_fireworks" not in gfx()[-1:], "关掉后礼物联动不再处理（回到主播自己的感谢）")
        r = api("toggle", {"key": "giftfx.enabled", "on": True})
        check(not errs, f"页面没有 JS 错误 {errs}")
        b.close()
finally:
    srv.terminate()
print("PASS" if not bad else "FAIL " + str(bad)); sys.exit(1 if bad else 0)
