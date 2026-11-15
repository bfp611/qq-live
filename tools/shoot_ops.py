# -*- coding: utf-8 -*-
"""运维（[ops]）页面级验证 + 截图（headless Chrome → screenshots/ops/）。每一步有断言，最后 PASS / FAIL。
   自己起一个带房间号但没开直播的服务（临时配置：日志 / 复盘 / 令牌都在临时目录；事件靠 /qq/event 灌进「真实直播间」的管线，不碰真正的直播间）：
       python tools/shoot_ops.py            （用 playwright；box 上用 /workspace/dev/pw/bin/python）
   覆盖：手机面板（登录 / 概览 / 弹幕 / 开关 / 控制 / 队列，手机尺寸）、XP 桌面里的「直播复盘」窗口、复盘网页、页面 ws 断线重连、
         服务端重启后页面自动恢复、面板「刷新页面」「切换房间」推到页面、模拟开播 → 下播 → 自动出复盘。"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request
os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试服务绝不连真实直播间（测试里的 /qq/event 是假事件）
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "ops"; OUT.mkdir(parents=True, exist_ok=True)
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
def shot(pg, name, **kw):
    p = OUT / name; pg.screenshot(path=str(p), **kw); quant(p); print("  →", p.relative_to(ROOT))
sk = socket.socket(); sk.bind(("127.0.0.1", 0)); PORT = sk.getsockname()[1]; sk.close(); BASE = f"http://127.0.0.1:{PORT}"
E = Path(tempfile.mkdtemp(prefix="opsshoot-"))
(E / "t.ini").write_text(f"""[music]
enabled = false
[tts]
backend = none
[idle]
enabled = false
[ai]
base_url =
[play]
data_file = {E}/play.json
chat_gap = 0
[ai_plus]
memory_file = {E}/mem.json
[guard]
; 测试服务绝不能推真的 Bark / 响提示音（密钥文件是相对路径，会读到真密钥）
enabled = false
bark = false
sound = false
[agent]
test_endpoints = true
[ops]
log_dir = {E}/logs
report_dir = {E}/reports
panel_token_file = {E}/tok.txt
overrides_file = {E}/ov.json
end_grace = 1.5
report_min_secs = 1
report_llm = false
detect_room = false
""", encoding="utf-8")
env = dict(os.environ, PYTHONIOENCODING="utf-8"); env.pop("QQ_SUPERVISED", None)
VENV = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
def start():
    return subprocess.Popen([str(VENV if VENV.exists() else sys.executable), str(ROOT / "backend" / "server.py"), "100000000001", "--port", str(PORT), "--config", str(E / "t.ini")], env=env, stdout=open(E / "srv.out", "a"), stderr=subprocess.STDOUT)
def get(path, token=None, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json", **({"X-Token": token} if token else {})})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
def up(secs=40):
    t = time.time()
    while time.time() - t < secs:
        try:
            get("/config.json"); return True
        except Exception: time.sleep(0.4)
    return False
def ev(**k): return get("/qq/event?" + urllib.parse.urlencode(k))
srv = start()
try:
    check(up(), "测试服务起来了")
    TOK = (E / "tok.txt").read_text().strip()
    for _ in range(60):                       # 先等真实抓取器查完房间状态（房间没开播，它只会发一次 live=false），之后再灌假开播，免得被它「下播」掉
        try:
            if (get("/ops/state").get("fetcher") or {}).get("live") is not None: break
        except Exception: pass
        time.sleep(0.5)
    time.sleep(1.5)
    ev(t="live", live=1, anchor="GG-Bond学AI", title="今晚唱什么"); time.sleep(0.3)
    ev(t="stat", online=1286, total="3.4万")
    for i, (n, tx) in enumerate([("痴情梦丶", "主播好人一生平安"), ("メ乖乖女ソ", "沙发！！"), ("☆﹏雨后彩虹", "这首歌我QQ空间也设成背景音乐了"), ("冷月无声", "有没有人一起斗地主"), ("小丑@鱼", "求黄钻，谁有送我一个呗")]):
        ev(t="chat", name=n, uid=f"u{i}", text=tx)
    ev(t="gift", name="痴情梦丶", uid="u0", gift="嘉年华", value=3000, count=1); ev(t="gift", name="メ乖乖女ソ", uid="u1", gift="玫瑰花", value=1, count=5); ev(t="follow", name="冷月无声", uid="u3"); ev(t="like", name="小丑@鱼", uid="u4", count=30)
    with sync_playwright() as p:
        exe = shutil.which("google-chrome") or shutil.which("chromium") or "/usr/bin/google-chrome"
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        errs = []
        # ---------------- 手机面板 ----------------
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and "401" not in m.text and errs.append(m.text))
        pg.goto(BASE + "/panel"); pg.wait_for_timeout(600)
        check(pg.is_visible("#login") and not pg.is_visible("#main"), "没令牌：显示登录页")
        shot(pg, "01_panel_login.png")
        pg.fill("#tok", "wrong-token"); pg.click("#go"); pg.wait_for_timeout(800)
        check("令牌不对" in pg.inner_text("#lerr"), "错令牌：提示令牌不对")
        pg.fill("#tok", TOK); pg.click("#go"); pg.wait_for_selector("#main:not(.hide)", timeout=8000); pg.wait_for_timeout(500)
        check(pg.evaluate("localStorage.getItem('qqlive.panel.token')") == TOK, "登录后令牌存在 localStorage（只在手机浏览器里）")
        check("直播中" in pg.inner_text("#chip") or "未开播" in pg.inner_text("#chip") or "连接中" in pg.inner_text("#chip"), "标题栏有状态：" + pg.inner_text("#chip"))
        txt = pg.inner_text("#t-home"); check("GG-Bond学AI" in txt and "1286" in txt and "3.4万" in txt, "概览：主播 / 在线 / 累计观看  " + txt.replace("\n", " ")[:200])
        st = pg.evaluate("PANEL.state().counts"); check(st["chat"] == 5 and st["follow"] == 1 and st["diamonds"] == 3005, f"概览计数：{st}")
        shot(pg, "02_panel_home.png", full_page=True)
        pg.click("#bar button[data-t=chat]"); pg.wait_for_timeout(900)
        t = pg.inner_text("#t-chat"); check("主播好人一生平安" in t and "送出 嘉年华" in t and "关注了主播" in t, "弹幕页：弹幕 / 礼物 / 关注")
        shot(pg, "03_panel_chat.png")
        # 注入脚本样式的昵称：不得被当 HTML 执行
        ev(t="chat", name="<img src=x onerror=window.__xss=1>", uid="x1", text="<script>window.__xss=2</script>"); pg.wait_for_timeout(2300)
        check(pg.evaluate("window.__xss") is None and "<img src=x" in pg.inner_text("#t-chat"), "昵称 / 弹幕里的 HTML 只当文字显示（防注入）")
        pg.click("#bar button[data-t=sw]"); pg.wait_for_timeout(500)
        shot(pg, "04_panel_switches.png", full_page=True)
        box = pg.locator("#t-sw .sw", has_text="回复弹幕").locator("input")
        was = box.is_checked(); box.evaluate("e => e.click()"); pg.wait_for_timeout(900)
        ov = json.loads((E / "ov.json").read_text()); check(ov.get("behavior.reply_chat") == ("false" if was else "true"), f"面板开关 → 服务端生效并写 overrides：{ov}")
        pg.locator("#t-sw .btn", has_text="还原为 config.ini").click(); pg.once("dialog", lambda d: d.accept())
        pg.click("#bar button[data-t=do]"); pg.wait_for_timeout(500)
        pg.fill("#t-do input[placeholder^='想让猪猪侠']", "大家晚上好呀"); shot(pg, "05_panel_controls.png", full_page=True)
        pg.fill("#t-do input[placeholder^='标题']", "下一首唱什么"); pg.fill("#t-do textarea", "晴天|七里香|夜曲")
        pg.locator("#t-do .btn", has_text="发起投票").click(); pg.wait_for_timeout(900)
        pg.click("#bar button[data-t=q]"); pg.wait_for_timeout(2500)
        v = pg.evaluate("PANEL.state().vote"); check(v and v["title"] == "下一首唱什么" and len(v["opts"]) == 3, f"面板发起投票 → 队列页看得到：{v and v['title']}")
        ev(t="chat", name="观众A", uid="a1", text="1"); ev(t="chat", name="观众B", uid="b1", text="2"); ev(t="chat", name="观众C", uid="c1", text="1"); pg.wait_for_timeout(2500)
        check("2 票" in pg.inner_text("#t-q") or "票" in pg.inner_text("#t-q"), "队列页：票数在涨")
        shot(pg, "06_panel_queue.png", full_page=True)
        # 复盘：下播
        ev(t="live", live=0); time.sleep(4.5)
        rp = get("/ops/api/reports", TOK); check(rp["reports"], "下播 → 自动出复盘")
        # ---------------- 复盘网页（独立打开） ----------------
        ctx2 = b.new_context(viewport={"width": 960, "height": 1200}); pg2 = ctx2.new_page()
        pg2.goto(BASE + "/ops/report/latest.html"); pg2.wait_for_timeout(500)
        t = pg2.inner_text("body"); check("直播复盘" in t and "抖币" in t and "不是主播实际收入" in t and "发言榜" in t and "送礼榜" in t, "复盘网页内容齐全（含金额免责声明）")
        shot(pg2, "10_report_page.png", full_page=True)
        ctx2.close()
        pg.click("#bar button[data-t=home]"); pg.wait_for_timeout(2500)
        check("复盘" in pg.inner_text("#t-home") and "最近：" in pg.inner_text("#t-home"), "面板概览显示最近复盘")
        shot(pg, "07_panel_home_after.png", full_page=True)
        check(not errs, "面板没有页面错误：" + "; ".join(errs[:3]))
        ctx.close()
        # 带令牌的 # 链接（二维码）：读完就存、地址栏清掉
        ctx = b.new_context(viewport={"width": 390, "height": 844}); pg = ctx.new_page()
        pg.goto(BASE + "/panel#token=" + urllib.parse.quote(TOK)); pg.wait_for_selector("#main:not(.hide)", timeout=8000)
        check("#" not in pg.url and "token" not in pg.url, "二维码里的 #token= 读完后从地址栏清掉：" + pg.url.replace(BASE, ""))
        ctx.close()
        # ---------------- XP 桌面里的复盘窗口 + 页面重连 ----------------
        ctx = b.new_context(viewport={"width": 1280, "height": 720}); pg = ctx.new_page(); perrs = []
        pg.on("pageerror", lambda e: perrs.append(str(e)))
        pg.goto(BASE + "/?room=100000000001&desk=xp&xp_boot=0&musicdemo=1"); pg.wait_for_timeout(3000)
        check(pg.evaluate("!!(window.OPSX && OPSX.cfg.report)"), "ops-ui.js 加载，/config.json 带 ops.report")
        pg.evaluate("WM.open('report')"); pg.wait_for_timeout(2500)
        check(pg.evaluate("!!(WM.byId.report && !WM.byId.report.closed && WM.byId.report.pv.count() >= 1)"), "直播复盘窗口：列出了复盘")
        fr = pg.frame_locator("iframe[title=直播复盘]"); check("直播复盘" in fr.locator(".tb").inner_text(timeout=5000) and "峰值" in fr.locator("body").inner_text(), "窗口里是复盘网页")
        shot(pg, "08_xp_report_window.png")
        pg.evaluate("WM.byId.report.close()"); pg.wait_for_timeout(300)
        pg.click("#start"); pg.wait_for_timeout(500); pg.locator("#startmenu .allp").click(); pg.wait_for_timeout(800)
        item = pg.locator(".xpm", has_text="直播复盘").locator("text=直播复盘"); check(item.count() >= 1, "开始菜单 → 所有程序 里有「直播复盘」")
        if item.count(): item.first.click(); pg.wait_for_timeout(1500); check(pg.evaluate("!!(WM.byId.report && !WM.byId.report.closed)"), "从开始菜单能打开直播复盘窗口")
        pg.evaluate("WM.byId.report && WM.byId.report.close()")
        # 页面 ws 断线重连：服务重启（execv）→ 页面自动重连并继续收弹幕
        n0 = pg.evaluate("document.querySelectorAll('#chatlist li, .msg, li').length")
        r = get("/ops/api/restart", TOK, "POST", {}); check(r["ok"], "面板重启服务")
        time.sleep(2.5); check(up(40), "服务回来了")
        pg.wait_for_timeout(1500)
        ev(t="chat", name="重连后的观众", uid="rc1", text="服务重启之后我还能看到")
        ok = False
        for _ in range(40):
            if pg.evaluate("document.body.innerText.includes('服务重启之后我还能看到')"): ok = True; break
            pg.wait_for_timeout(500)
        check(ok, "服务重启后页面 websocket 自动重连，新弹幕照常上屏")
        shot(pg, "09_xp_after_reconnect.png")
        # 面板「刷新直播页面」→ 页面真的刷新
        pg.evaluate("window.__marker = 1")
        r = get("/ops/api/reload", TOK, "POST", {}); check(r["ok"] and r["pages"] >= 1, f"面板刷新页面：通知了 {r['pages']} 个页面")
        pg.wait_for_timeout(2500); check(pg.evaluate("window.__marker") is None, "页面收到 reload 后真的刷新了")
        # 自动切换房间：服务端发 switch，页面 URL 里的 room 换掉
        pg.wait_for_timeout(1500)
        ev(t="switch", to="889896824784"); pg.wait_for_timeout(2500)
        check("room=889896824784" in pg.url, "收到 switch：页面切到新房间 " + pg.url.replace(BASE, ""))
        check(not perrs, "桌面页面没有错误：" + "; ".join(perrs[:3]))
        ctx.close()
        b.close()
finally:
    srv.terminate()
    try: srv.wait(8)
    except Exception: srv.kill()
    subprocess.run(["pkill", "-f", f"server.py 100000000001 --port {PORT}"])
    shutil.rmtree(E, ignore_errors=True)
print("PASS" if not bad else f"FAIL {len(bad)}: " + "; ".join(bad))
sys.exit(1 if bad else 0)
