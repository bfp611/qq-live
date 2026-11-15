# -*- coding: utf-8 -*-
"""进场接待（§11.11）页面级验证 + 截图（headless Chrome → screenshots/welcome/）。假房间 100000000001（QQ_NO_FETCH=1，不连抖音、不推 Bark；临时配置），
   往里灌假进场事件（/qq/event?t=member）：新观众欢迎 + 推荐口令、老观众「又来啦，第 N 次了」、5 人合并成一句、同一人不重复、
   进场不打断冷场表演（扫雷演到底）、主播自己的「欢迎新人」没有重复发、面板开关即时生效。
   python tools/shoot_welcome.py        （用 playwright；box 上用 /workspace/dev/pw/bin/python）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request
os.environ.setdefault("QQ_NO_FETCH", "1")
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "welcome"; OUT.mkdir(parents=True, exist_ok=True)
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
E = Path(tempfile.mkdtemp(prefix="wlshoot-"))
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
merge_secs = 3
[behavior]
welcome_interval = 2
""", encoding="utf-8")
PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
srv = subprocess.Popen([str(PY) if PY.exists() else sys.executable, str(ROOT / "backend/server.py"), RID, "--port", str(PORT), "--config", str(E / "t.ini")],
                       env=dict(os.environ, TTS_BACKEND="none", PYTHONIOENCODING="utf-8"), stdout=open(E / "srv.out", "w"), stderr=subprocess.STDOUT)
def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r: return json.loads(r.read())
def member(uid, name): return get("/qq/event?t=member&uid=" + uid + "&name=" + urllib.parse.quote(name))
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
        # ---- 新观众 ----
        member("u_new", "小明"); time.sleep(1)
        check(not said("小明"), "进场后先合并窗口里等着（还没发）")
        check(wait_for(lambda: said("小明"), 25), "新观众：群聊里出现主播的欢迎")
        t = said("小明"); check(t and "发『" in t[0], f"带推荐口令：{t[:1]}")
        shot(pg, "01_new_viewer_welcome.png")
        # ---- 老观众：第 3 次 ----
        member("u_old", "老观众阿花")
        check(wait_for(lambda: said("老观众阿花", "第 3 次"), 25), "老观众：第 3 次（积分存档里 visits=2 + 今天）")
        t = said("老观众阿花", "第 3 次")
        check(t and "老观众阿花" in t[0] and "来个蓝屏" not in t[0], f"老观众：用过『来个蓝屏』的不再推荐：{t[:1]}")
        shot(pg, "02_returning_viewer.png")
        # ---- 同一个人不重复 ----
        n0 = len(said("小明")); member("u_new", "小明"); time.sleep(5)
        check(len(said("小明")) == n0, "同一个人 30 分钟内再进：不重复欢迎")
        # ---- 合并 ----
        for i, n in enumerate(["甲甲", "乙乙", "丙丙", "丁丁", "戊戊"]): member(f"g{i}", n); time.sleep(0.2)
        check(wait_for(lambda: "甲甲、乙乙 等 5 位" in body(), 8), "5 个人合并成一句「欢迎 甲甲、乙乙 等 5 位朋友」")
        check(len([l for l in body().split("\n") if "丙丙" in l]) == 1, "合并后只有一句（没人被单独欢迎）")
        shot(pg, "03_merged_five.png")
        # ---- 不打断冷场表演 / 主播自己的欢迎没重复 ----
        tok = (E / "tok.txt").read_text().strip()
        def api(path, body_=None):
            req = urllib.request.Request(BASE + "/ops/api/" + path, method="POST" if body_ is not None else "GET", data=json.dumps(body_).encode() if body_ is not None else None, headers={"X-Token": tok, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r_: return json.loads(r_.read())
        r = api("do", {"action": "perform_now", "which": "mine"})
        for _ in range(20):
            if r.get("ok"): break
            time.sleep(0.5); r = api("do", {"action": "perform_now", "which": "mine"})
        check(r.get("ok"), f"开一场扫雷表演：{r}")
        n0 = get("/agent/idle")["stats"]["started"]
        time.sleep(2); member("m1", "路人甲"); time.sleep(1); member("m2", "路人乙")
        rec = wait_for(lambda: (get("/agent/idle")["history"] and get("/agent/idle")["history"][-1].get("name") == "perf_mine" and get("/agent/idle")["history"][-1].get("result") and get("/agent/idle")["history"][-1]) or None, 90)
        check(rec and rec["result"] == "完成", f"演到一半有人进场：表演没被打断（{rec and rec['result']}）")
        check("欢迎新伙伴" not in body() and "加入正义联盟" not in body(), "主播自己的「欢迎新人」没有重复发")
        check(wait_for(lambda: said("路人甲"), 12), "进场的人事后仍被欢迎")
        shot(pg, "04_welcome_during_performance.png")
        # ---- 面板：开关即时生效 + 统计 ----
        s = api("state"); check(any(i["key"] == "welcome.enabled" for g in s["switches"] for i in g["items"]), "面板开关里有「进场接待」")
        check(s["welcome"]["stats"]["lines"] >= 3, f"面板状态里有接待统计：{s['welcome']['stats']}")
        pg2 = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2); pg2.goto(BASE + "/panel#token=" + tok); pg2.wait_for_timeout(1800)
        pg2.click("#bar button[data-t=sw]") if pg2.locator("#bar button[data-t=sw]").count() else None; pg2.wait_for_timeout(500)
        shot(pg2, "05_panel.png")
        r = api("toggle", {"key": "welcome.enabled", "on": False}); check(r.get("ok"), "面板关掉进场接待")
        time.sleep(0.5); member("off1", "关了之后的人"); time.sleep(5)
        check(not said("关了之后的人"), "关掉后接待模块不再发欢迎")
        check(api("state")["welcome"]["pending"] == 0, "关掉后不再攒进场")
        check(not errs, f"页面没有 JS 错误 {errs}")
        b.close()
finally:
    srv.terminate()
print("PASS" if not bad else "FAIL " + str(bad)); sys.exit(1 if bad else 0)
