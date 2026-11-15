# -*- coding: utf-8 -*-
"""玩法提示（[tips]）页面级验证 + 截图（headless Chrome → screenshots/tips/）。自己起一个没开直播的服务（临时配置，间隔都调得很短），
   真页面连上之后：自动发的提示出现在群聊里、菜单出现、演示（光标动、窗口开了又收拾）后出现「刚才这个你们也能玩」、面板按钮可用、观众说话时不发。
   python tools/shoot_tips.py        （用 playwright；box 上用 /workspace/dev/pw/bin/python）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request
os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试服务绝不连真实直播间（测试里的 /qq/event 是假事件）
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "tips"; OUT.mkdir(parents=True, exist_ok=True)
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
E = Path(tempfile.mkdtemp(prefix="tipshoot-"))
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
min_interval = 1
max_interval = 2
speak = false
llm = false
cursor_speed = 3
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
[guard]
enabled = false
[perform]
enabled = false
[tips]
startup_delay = 4
idle_secs = 3
interval = 6
min_gap = 3
demo_chance = 0
menu_interval = 40
state_file = {E}/tips.json
""", encoding="utf-8")
PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
srv = subprocess.Popen([str(PY) if PY.exists() else sys.executable, str(ROOT / "backend/server.py"), "100000000001", "--port", str(PORT), "--config", str(E / "t.ini")],
                       env=dict(os.environ, TTS_BACKEND="none", PYTHONIOENCODING="utf-8"), stdout=open(E / "srv.out", "w"), stderr=subprocess.STDOUT)
def get(p):
    with urllib.request.urlopen(BASE + p, timeout=60) as r: return json.loads(r.read())
def wait_for(fn, s=30):
    t = time.time()
    while time.time() - t < s:
        v = fn()
        if v: return v
        time.sleep(0.3)
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
        def texts(): return pg.evaluate("Array.from(document.querySelectorAll('.sysline')).map(e => e.textContent)")
        check(wait_for(lambda: get("/agent/state").get("clients"), 15), "页面连上了（agent 通道）")
        pg.wait_for_timeout(1500)
        # 1. 安静时自动发一条
        t = wait_for(lambda: [x for x in texts() if "玩法提示" in x], 30)
        check(t, "安静 → 群聊里自动出现玩法提示：" + (t[0] if t else ""))
        check(t and "『" in t[0] and "』" in t[0], "提示里带命令『…』")
        shot(pg, "01_tip_in_group.png")
        st = get("/tips/state"); check(st["stats"]["tips"] >= 1 and st["last"]["kind"] == "tip", f"/tips/state：{st['stats']}")
        # 2. 观众说话时不发
        n0 = len([x for x in texts() if "玩法提示" in x])
        for i in range(4):
            get(f"/qq/event?t=chat&uid=u1&name=viewer&text=hello{i}"); time.sleep(2)
        n1 = len([x for x in texts() if "玩法提示" in x]); check(n1 == n0, f"观众在聊天（每 2 秒一条）时不发提示（{n0}→{n1}）")
        # 3. 菜单
        r = get("/tips/now?kind=menu"); check(r.get("ok"), f"发菜单：{r}")
        m = wait_for(lambda: [x for x in texts() if "玩法菜单" in x], 8); check(m and " / " in m[0], "菜单出现在群聊：" + (m[0] if m else ""))
        pg.wait_for_timeout(300); shot(pg, "02_menu_in_group.png")
        # 4. 演示：先烟花（走 agent 管线，页面里放烟花），再扫雷（走冷场玩电脑：光标动 + 收拾）→ 各自出现「你们也能玩」
        time.sleep(4)
        def demo(cmd, tries=12, gap=3):
            r = None
            for _ in range(tries):
                r = get("/tips/now?kind=demo&cmd=" + urllib.parse.quote(cmd))
                if r.get("ok"): return r
                time.sleep(gap)
            return r
        d0 = get("/agent/state")["stats"]["dispatched"]
        r = demo("放烟花"); check(r and r.get("ok") and r["kind"] == "demo" and "放烟花" in r["text"], f"演示：放烟花：{r}")
        check(get("/agent/state")["stats"]["dispatched"] == d0 + 1, "烟花演示走 agent 管线，派发给了页面")
        check(wait_for(lambda: [x for x in texts() if "放烟花" in x and "刚才这个你们也能玩" in x], 5), "教学句：刚才这个你们也能玩，发『放烟花』试试")
        shot(pg, "03_demo_fireworks_then_teach.png")
        time.sleep(4)
        # 冷场自己也会玩电脑（间隔调到 1~2 秒），得抢到空档
        r = demo("玩扫雷", 600, 0.2); check(r and r.get("ok") and "玩扫雷" in r["text"], f"演示：玩扫雷：{r}")
        hist = [h for h in (get("/agent/idle").get("history") or []) if h.get("name") == "play_minesweeper"]
        check(hist and hist[-1].get("result") == "完成" and hist[-1].get("beats", 0) >= 3, f"扫雷演示真的跑完了（光标动作 + 收拾）：{hist[-1] if hist else None}")
        check(wait_for(lambda: [x for x in texts() if "玩扫雷" in x and "刚才这个你们也能玩" in x], 5), "教学句：发『玩扫雷』试试")
        pg.wait_for_timeout(300); shot(pg, "03_demo_minesweeper_then_teach.png")
        # 5. 面板按钮
        tok = (E / "tok.txt").read_text().strip()
        def api(path, body=None):
            req = urllib.request.Request(BASE + "/ops/api/" + path, method="POST" if body is not None else "GET", data=json.dumps(body).encode() if body is not None else None, headers={"X-Token": tok, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
        time.sleep(3.5)
        r = api("do", {"action": "tip_now"}); check(r.get("ok"), f"面板「发一条玩法提示」：{r}")
        s = api("state"); check(s["tips"]["enabled"] and any("tips" == g["id"] for g in s["switches"]), "面板状态里有 tips，开关里有玩法提示组")
        pg2 = b.new_page(viewport={"width": 390, "height": 760}, device_scale_factor=2); pg2.goto(BASE + "/panel#token=" + tok); pg2.wait_for_timeout(1800)
        check("玩法提示" in pg2.locator("#t-home").inner_text(), "手机面板概览里有「玩法提示」")
        shot(pg2, "04_panel_tips_status.png")
        pg2.click("#bar button[data-t=do]"); pg2.wait_for_timeout(500)
        check(pg2.locator("button", has_text="发一条玩法提示").count() == 1 and pg2.locator("button", has_text="演示一个").count() == 1, "控制页有「发一条玩法提示 / 发玩法菜单 / 演示一个」")
        shot(pg2, "05_panel_tips_buttons.png")
        # 6. 开关关掉就不发了
        api("toggle", {"key": "tips.enabled", "on": False}); time.sleep(1); n = len([x for x in texts() if "玩法提示" in x]); time.sleep(14)
        check(len([x for x in texts() if "玩法提示" in x]) == n, "面板关掉 tips.enabled 后不再发")
        check(not errs, f"页面没有 JS 错误 {errs}")
        b.close()
finally:
    srv.terminate()
print("PASS" if not bad else "FAIL " + str(bad)); sys.exit(1 if bad else 0)
