# -*- coding: utf-8 -*-
"""窗口闲置自动关闭（[autoclose]）页面级验证 + 截图（headless Chrome → screenshots/autoclose/）。
   起一个只有 demo 房间的服务（没有任何真实直播间；QQ_NO_FETCH=1；临时配置，超时调得很短），真页面里验证：
   画图闲置到点自动收掉（带收缩动画）、用户点击 / agent 操作会续命、agent 正在对它做事时不关、群聊 / 千千静听 / 播放列表永远不关、
   投票等 skip 的不管、最小化的不管、有菜单开着先等、游戏有最长时间、开关（面板 + 配置）可关。
   python tools/shoot_autoclose.py        （用 playwright；box 上用 /workspace/dev/pw/bin/python）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, socket, subprocess, sys, tempfile, time, urllib.request
os.environ.setdefault("QQ_NO_FETCH", "1")
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "autoclose"; OUT.mkdir(parents=True, exist_ok=True)
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
E = Path(tempfile.mkdtemp(prefix="acshoot-"))
(E / "t.ini").write_text(f"""[music]
enabled = false
[tts]
backend = none
[ai]
base_url =
[agent]
test_endpoints = true
[idle]
enabled = false
[tips]
enabled = false
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
[autoclose]
check_secs = 0.5
paint = 5
notepad = 5
calc = 5
max_game = 6
""", encoding="utf-8")
PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
srv = subprocess.Popen([str(PY) if PY.exists() else sys.executable, str(ROOT / "backend/server.py"), "--port", str(PORT), "--config", str(E / "t.ini")],
                       env=dict(os.environ, TTS_BACKEND="none", PYTHONIOENCODING="utf-8"), stdout=open(E / "srv.out", "w"), stderr=subprocess.STDOUT)
def wait_for(fn, s=30, step=0.2):
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
        pg.goto(BASE + "/?room=demo&desk=xp&xp_boot=0&host=0&musicdemo=0")
        check(wait_for(lambda: pg.evaluate("!!(window.AC && window.WM && WM.byId.qqchat && window.AG)"), 20), "页面起来了（AC / WM / 群聊 / agent）")
        pg.wait_for_timeout(1500)
        ev = lambda js: pg.evaluate(js)
        closed = lambda wid: ev(f"!WM.byId['{wid}'] || WM.byId['{wid}'].closed")
        cfg = ev("AC.cfg"); check(cfg["paint"] == "5" and cfg["enabled"] in ("true", True), f"配置从 /config.json 进来了：paint={cfg['paint']}")
        check(not ev("AC.managed(WM.byId.qqchat)") and not ev("AC.managed(WM.byId.ttplayer)") and not ev("AC.managed(WM.byId.ttplaylist)"), "群聊 / 千千静听 / 播放列表不在管理范围")
        check(not ev("AC.managed({id:'vote',o:{}})") and not ev("AC.managed({id:'skipvote',o:{}})") and not ev("AC.managed({id:'game',o:{}})") and not ev("AC.managed({id:'qq-panel',o:{}})") and not ev("AC.managed({id:'qqx-pet',o:{}})"), "投票 / 小游戏 / QQ 面板 / QQ 宠物不管")
        # ---- 1. 画图：打开后什么都不做，到点收掉 ----
        ev("WM.open('paint')"); t0 = time.time()
        check(not closed("paint"), "画图打开了")
        shot(pg, "01_paint_open.png")
        check(wait_for(lambda: ev("WM.byId.paint && WM.byId.paint.el.classList.contains('ac-closing')"), 9, 0.05) is not None or closed("paint"), "到点先放收缩动画（ac-closing）")
        check(wait_for(lambda: closed("paint"), 3), "然后关掉")
        dt = time.time() - t0; check(4.3 <= dt <= 8.5, f"画图 5 秒闲置 → 约 {dt:.1f} 秒后收掉")
        shot(pg, "02_paint_closed.png")
        # ---- 2. 用户点击续命 ----
        ev("WM.open('notepad')"); t0 = time.time()
        wid = ev("WM.wins.filter(w => !w.closed && /记事本/.test(w.title)).pop().id")
        while time.time() - t0 < 9:
            ev(f"(() => {{ const w = WM.byId['{wid}']; w.el.dispatchEvent(new PointerEvent('pointerdown', {{ bubbles: true }})); }})()"); time.sleep(1.5)
        check(not closed(wid), "每 1.5 秒点一下记事本（9 秒，超过 5 秒闲置）→ 一直开着")
        t1 = time.time(); check(wait_for(lambda: closed(wid), 10), "不点了 → 关掉"); check(3.5 <= time.time() - t1 <= 8, f"最后一次点击后 {time.time() - t1:.1f} 秒关")
        # ---- 3. agent 正在做事：不关；做完才开始计时 ----
        ev("AG.enqueue({id:'t-wait', by:'测试', text:'', actions:[{action:'open_app', app:'notepad'}, {action:'_wait', secs:8}]})"); t0 = time.time()
        time.sleep(7)
        wid = ev("(WM.wins.filter(w => !w.closed && /记事本/.test(w.title)).pop() || {}).id")
        check(wid and not closed(wid) and ev("AG.running"), "agent 还在对记事本做事（>5 秒闲置）→ 不关")
        check(wait_for(lambda: not ev("AG.running"), 10), "agent 任务结束")
        t1 = time.time(); check(wait_for(lambda: closed(wid), 12), "做完之后才开始计时，到点关掉"); check(3.5 <= time.time() - t1 <= 9, f"任务结束后 {time.time() - t1:.1f} 秒关")
        # ---- 4. 真的 agent 画画：画完 5 秒后收 ----
        ev("AG.enqueue({id:'t-paint', by:'测试', text:'', actions:[{action:'open_app', app:'paint'}, {action:'paint_draw', what:'sun'}]})")
        check(wait_for(lambda: ev("!!WM.byId.paint && !WM.byId.paint.closed"), 8), "agent 打开画图")
        check(wait_for(lambda: not ev("AG.running"), 40), "画好了太阳（agent 任务结束）"); t1 = time.time()
        check(not closed("paint"), "刚画完，画图还开着"); shot(pg, "03_agent_drew_sun.png")
        check(wait_for(lambda: closed("paint"), 12), "画完后自动收掉"); check(3.5 <= time.time() - t1 <= 9, f"画完后 {time.time() - t1:.1f} 秒收掉")
        shot(pg, "04_desktop_clear_after_sun.png")
        # ---- 5. 永不关：把所有超时调到 1 秒，等 6 秒 ----
        ev("AC.setCfg({paint:'1', notepad:'1', calc:'1', default_secs:'1', dialog:'1', qq:'1'})")
        ev("WM.open('calc')"); time.sleep(6)
        check(closed("calc"), "（对照）calc 1 秒闲置 → 关了")
        check(not closed("qqchat") and not closed("ttplayer"), "超时都调成 1 秒：群聊、千千静听 6 秒后还在")
        check(ev("(() => { const p = WM.byId.ttplaylist; return !p || !p.closed; })()"), "播放列表还在")
        # ---- 6. 最小化 / 菜单 / 模态对话框 / 系统画面：先等着 ----
        ev("WM.open('calc')"); ev("WM.byId.calc.min()"); time.sleep(3)
        check(not closed("calc"), "最小化的窗口不关"); ev("WM.byId.calc.restore()"); ev("AC.reset(WM.byId.calc)")
        ev("WM.menu([{t:'测试菜单'}], 300, 300)"); time.sleep(3)
        check(not closed("calc"), "有菜单开着先等"); ev("WM.closeMenus()")
        check(wait_for(lambda: closed("calc"), 6), "菜单收起后到点关")
        ev("WM.open('calc')"); ev("XP.screen = {}; "); time.sleep(3)
        check(not closed("calc"), "开机 / 关机 / 蓝屏画面期间不关"); ev("XP.screen = null")
        check(wait_for(lambda: closed("calc"), 6), "画面结束后关")
        # ---- 7. 游戏最长开 6 秒（一直有互动也关）----
        ev("AC.setCfg({minesweeper:'30'})"); ev("WM.open('minesweeper')"); t0 = time.time()
        while time.time() - t0 < 4.5 and not closed("minesweeper"):
            ev("WM.byId.minesweeper.el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))"); time.sleep(0.8)
        check(not closed("minesweeper"), "扫雷一直有互动，4.5 秒时还开着")
        check(wait_for(lambda: closed("minesweeper"), 6), "开满 max_game（6 秒）→ 即使有互动也关"); check(5.5 <= time.time() - t0 <= 9.5, f"扫雷开了 {time.time() - t0:.1f} 秒后关")
        # ---- 8. 开关：配置 + 面板（不用刷新页面）----
        tok = (E / "tok.txt").read_text().strip()
        def api(path, body=None):
            req = urllib.request.Request(BASE + "/ops/api/" + path, method="POST" if body is not None else "GET", data=json.dumps(body).encode() if body is not None else None, headers={"X-Token": tok, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
        s = api("state"); check(any(i["key"] == "autoclose.enabled" for g in s["switches"] for i in g["items"]), "面板开关里有「窗口闲置自动关闭」")
        r = api("toggle", {"key": "autoclose.enabled", "on": False}); check(r.get("ok") and not r["reload"], f"面板关掉：{r}")
        check(wait_for(lambda: ev("String(AC.cfg.enabled)") == "false", 4), "页面立刻收到（不用刷新）")
        ev("WM.open('calc')"); time.sleep(4); check(not closed("calc"), "关掉之后 calc 闲置 4 秒也不关")
        api("toggle", {"key": "autoclose.enabled", "on": True}); check(wait_for(lambda: ev("String(AC.cfg.enabled)") == "true", 4), "面板打开 → 页面收到")
        check(wait_for(lambda: closed("calc"), 6), "打开后（calc 已闲置很久）到点收掉")
        st = ev("AC.state()"); check(st["closed"] >= 6 and st["log"], f"AC.state：已自动关 {st['closed']} 个，最近：{st['log'][-1]['id']}（{st['log'][-1]['why']}）")
        check(not errs, f"页面没有 JS 错误 {errs}")
        b.close()
finally:
    srv.terminate()
print("PASS" if not bad else "FAIL " + str(bad)); sys.exit(1 if bad else 0)
