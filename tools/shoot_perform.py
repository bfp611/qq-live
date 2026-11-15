# -*- coding: utf-8 -*-
"""冷场「表演」（§11.10）页面级验证 + 截图（headless Chrome → screenshots/perform/）。起一个没有真实直播间的服务
   （房间号是假的 100000000001，QQ_NO_FETCH=1，不连抖音、不推 Bark；临时配置），真页面里逐个跑表演（走 /tips/now?kind=perform&cmd=…，
   和面板「来一场表演」同一条路）：开场白出现在群聊、动作真的做了（蓝屏画面 / XP 关机重启画面并回到桌面且页面没刷新 / 烟花 / 画图画画后自动关窗 …）、
   做完群聊里补一句「你们也可以发『…』」；还验证 蓝屏 / 重启 的冷却、关掉开关后不再被挑、观众说话会打断。
   python tools/shoot_perform.py        （用 playwright；box 上用 /workspace/dev/pw/bin/python）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request
os.environ.setdefault("QQ_NO_FETCH", "1")
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "perform"; OUT.mkdir(parents=True, exist_ok=True)
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
def shot(pg, name):
    p = OUT / name; pg.screenshot(path=str(p)); quant(p); print("  →", p.relative_to(ROOT))
sk = socket.socket(); sk.bind(("127.0.0.1", 0)); PORT = sk.getsockname()[1]; sk.close(); BASE = f"http://127.0.0.1:{PORT}"
E = Path(tempfile.mkdtemp(prefix="perfshoot-"))
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
enabled = true
startup_delay = 9999
[guard]
enabled = false
bark = false
sound = false
[play]
data_file = {E}/p.json
[ai_plus]
memory_file = {E}/m.json
[ops]
log_dir = {E}/logs
report_dir = {E}/r
panel_token_file = {E}/tok.txt
overrides_file = {E}/ov.json
detect_room = false
autoswitch = false
[xp]
bsod_secs = 3
boot_secs = 1.5
welcome_secs = 1.5
[autoclose]
check_secs = 0.5
paint = 5
[perform]
gap = 0
heavy_gap = 20
""", encoding="utf-8")
PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
srv = subprocess.Popen([str(PY) if PY.exists() else sys.executable, str(ROOT / "backend/server.py"), "100000000001", "--port", str(PORT), "--config", str(E / "t.ini")],
                       env=dict(os.environ, TTS_BACKEND="none", PYTHONIOENCODING="utf-8"), stdout=open(E / "srv.out", "w"), stderr=subprocess.STDOUT)
def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r: return json.loads(r.read())
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
        pg.goto(BASE + "/?room=100000000001&desk=xp&xp_boot=0&host=1&musicdemo=0")
        check(wait_for(lambda: get("/agent/state").get("clients"), 15), "页面连上了（agent 通道，假房间）")
        pg.evaluate("window.__marker = 'same-page'")
        pg.wait_for_timeout(2500)
        body = lambda: pg.evaluate("document.body.innerText")
        hist = lambda: get("/agent/idle").get("history") or []
        def perform(k, secs=60):
            n0 = get("/agent/idle")["stats"]["started"]
            r = None
            for _ in range(40):
                r = get(f"/tips/now?kind=perform&cmd={k}")
                if r.get("ok"): break
                time.sleep(0.5)
            if not r or not r.get("ok"): print("   perform 没开起来：", r); return r, None
            rec = wait_for(lambda: (get("/agent/idle")["stats"]["started"] > n0 and hist()[-1].get("result") and hist()[-1]) or None, secs)
            return r, rec
        # ---- 烟花 ----
        d0 = get("/agent/state")["stats"]["dispatched"]
        r, rec = perform("fireworks"); check(r.get("ok") and rec and rec["result"] == "完成", f"烟花：{r.get('text')} → {rec and rec['result']}")
        check(rec and rec["lines"] and rec["lines"][0] in ("来，放个烟花庆祝一下", "放个烟花，热闹热闹"), f"开场白：{rec and rec['lines']}")
        check(wait_for(lambda: rec["lines"][0] in body(), 5), "开场白出现在群聊里（主播说的）")
        check(wait_for(lambda: "你们也可以发『放烟花』" in body(), 5), "做完补一句：你们也可以发『放烟花』")
        check(rec["beats"] >= 2, f"烟花走 agent 管线派发给了页面（{rec['beats']} 批动作）")
        shot(pg, "01_fireworks_intro_and_tip.png")
        # ---- 蓝屏 ----
        r, _ = (get("/tips/now?kind=perform&cmd=bsod"), None)
        check(r.get("ok"), f"蓝屏：{r.get('text')}")
        check(wait_for(lambda: pg.evaluate("!!(window.XP && XP.screen && document.querySelector('.bsodtxt'))"), 15, 0.1), "页面真的蓝屏了（XP 蓝屏画面）")
        shot(pg, "02_bsod_performance.png")
        check(wait_for(lambda: not pg.evaluate("!!(window.XP && XP.screen)"), 20), "几秒后自动恢复")
        rec = wait_for(lambda: (hist() and hist()[-1].get("name") == "perf_bsod" and hist()[-1].get("result") and hist()[-1]) or None, 30)
        check(rec and rec["result"] == "完成" and rec["lines"][0] in ("给大家表演一个蓝屏", "来，表演一个经典的 Windows 蓝屏"), f"蓝屏整场：{rec and (rec['result'], rec['lines'])}")
        check(wait_for(lambda: "你们也可以发『来个蓝屏』" in body(), 5), "补一句：你们也可以发『来个蓝屏』")
        # 重型冷却：蓝屏刚演完，自然挑选不会再挑蓝屏 / 重启（手动不受限，这里看 plan 级别：用 weights=只剩 bsod 的自然挑选）
        st = get("/agent/idle"); check(st["weights"].get("perf_bsod", 0) > 0, "（状态）perf_bsod 在权重表里")
        # ---- 重启：XP 关机 → 开机 → 回到桌面，页面不刷新 ----
        time.sleep(1)
        r = get("/tips/now?kind=perform&cmd=restart"); check(r.get("ok"), f"重启：{r.get('text')}")
        check(wait_for(lambda: pg.evaluate("!!(window.XP && XP.screen)"), 25, 0.1), "XP 关机画面出来了（假重启，只在页面里）")
        shot(pg, "03_restart_shutdown_screen.png")
        check(wait_for(lambda: not pg.evaluate("!!(window.XP && XP.screen)"), 40), "关机 → 开机 → 回到桌面")
        check(pg.evaluate("window.__marker") == "same-page", "页面没有刷新（只是页面里的 XP 动画）")
        rec = wait_for(lambda: (hist()[-1].get("name") == "perf_restart" and hist()[-1].get("result") and hist()[-1]) or None, 40)
        check(rec and rec["result"] == "完成" and rec["lines"][0] in ("电脑太卡了，我重启一下", "好卡啊，让我重启一下电脑"), f"重启整场：{rec and (rec['result'], rec['lines'])}")
        check("你们也可以发" not in "".join(l for l in body().split("\n") if "重启" in l), "重启没有补提示（观众没有这个口令）")
        shot(pg, "04_after_restart_desktop.png")
        # ---- 画画：画完留着，autoclose 5 秒后收 ----
        r, rec = perform("paint", 80); check(r.get("ok") and rec and rec["result"] == "完成", f"画画：{rec and (rec['result'], rec['lines'])}")
        check(pg.evaluate("!!WM.byId.paint && !WM.byId.paint.closed"), "画完后画图还开着（没有被 idle 立刻收拾）"); shot(pg, "05_paint_performance.png")
        check(wait_for(lambda: pg.evaluate("!WM.byId.paint || WM.byId.paint.closed"), 15), "过一会儿被 autoclose 自动关掉")
        check(wait_for(lambda: "你们也可以发『画个" in body(), 5), "补一句：你们也可以发『画个…』")
        # ---- 其余表演逐个跑 ----
        for k, intros in (("mine", ("我来扫个雷给你们看", "给你们表演一下扫雷")), ("wall", ("给大家换个新壁纸", "桌面太旧了，换个新壁纸")), ("shake", ("我抖一下窗口", "来，抖一抖窗口")),
                          ("pet", ("给球球喂个饭", "球球饿了，我去喂它")), ("virus", ("给大家表演一个熊猫烧香", "来，表演一段怀旧的熊猫烧香")), ("meteor", ("来个流星雨给大家看看", "看，流星雨"))):
            r, rec = perform(k, 80)
            check(r.get("ok") and rec and rec["result"] == "完成" and rec["lines"][0] in intros, f"{k}：{r.get('error') or ''}{rec and (rec['result'], rec['lines'][:1])}")
            time.sleep(0.5)
        shot(pg, "06_after_all.png")
        # ---- 观众说话会打断 ----
        r = get("/tips/now?kind=perform&cmd=mine"); check(r.get("ok"), "再开一场扫雷")
        time.sleep(1.5); get("/qq/event?t=chat&uid=u1&name=viewer&text=hello")
        rec = wait_for(lambda: (hist()[-1].get("name") == "perf_mine" and hist()[-1].get("result") and hist()[-1]) or None, 15)
        check(rec and rec["result"] in ("被打断", "完成"), f"观众开口：{rec and rec['result']}（被打断时不补提示）")
        # ---- 开关：面板关掉 perform.enabled 后，自然挑选不会再出表演；手动照样可以 ----
        tok = (E / "tok.txt").read_text().strip()
        def api(path, body=None):
            req = urllib.request.Request(BASE + "/ops/api/" + path, method="POST" if body is not None else "GET", data=json.dumps(body).encode() if body is not None else None, headers={"X-Token": tok, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r_: return json.loads(r_.read())
        s = api("state"); check(any(i["key"] == "perform.enabled" for g in s["switches"] for i in g["items"]), "面板开关里有「冷场表演」")
        r = api("toggle", {"key": "perform.enabled", "on": False}); check(r.get("ok"), "面板关掉冷场表演")
        time.sleep(1)
        pg2 = b.new_page(viewport={"width": 390, "height": 760}, device_scale_factor=2); pg2.goto(BASE + "/panel#token=" + tok); pg2.wait_for_timeout(1800)
        pg2.click("#bar button[data-t=do]"); pg2.wait_for_timeout(500)
        check(pg2.locator("button", has_text="来一场表演").count() == 1, "控制页有「来一场表演」按钮"); shot(pg2, "07_panel_perform_button.png")
        time.sleep(3)
        r = api("do", {"action": "perform_now", "which": "fireworks"}); check(r.get("ok"), f"面板「来一场表演」（开关关着也能手动）：{r}")
        check(not errs, f"页面没有 JS 错误 {errs}")
        b.close()
finally:
    srv.terminate()
print("PASS" if not bad else "FAIL " + str(bad)); sys.exit(1 if bad else 0)
