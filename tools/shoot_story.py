# -*- coding: utf-8 -*-
"""连续剧情 + 观众记忆（§11.14）页面级验证 + 截图（headless Chrome → screenshots/story/）。假房间 100000000001（QQ_NO_FETCH=1，不连抖音；Bark / 提示音硬禁用）。
   时钟悬停提示 / 日历 → 假开播 + 弹幕 / 礼物 / 高光 → 假下播 → 写日记（模板，不调模型）→ 面板「剧情」页 → 往后走一天 → 下次开播发表 → QQ空间里的日志 →
   冷场翻日记念出来 → 老观众进场被「记得」。
   python tools/shoot_story.py        （用 playwright；box 上用 /workspace/dev/pw/bin/python）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request
os.environ.setdefault("QQ_NO_FETCH", "1")
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "story"; OUT.mkdir(parents=True, exist_ok=True)
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
E = Path(tempfile.mkdtemp(prefix="stshoot-"))
RID = "100000000001"
old = {"name": "老观众阿花", "pts": 30, "chats": 5, "gifts": 0, "likes": 0, "follows": 0, "first": int(time.time()) - 86400 * 9, "last": int(time.time()) - 86400 * 2, "visits": 3, "visit_day": "2020-01-01",
       "cmds": {"bsod": 2}, "quotes": ["这首歌太好听了！"]}
red = {"name": "小红", "pts": 12, "chats": 2, "gifts": 0, "likes": 0, "follows": 0, "first": int(time.time()) - 86400 * 5, "last": int(time.time()) - 86400 * 3, "visits": 2, "visit_day": "2020-01-01"}
(E / "p.json").write_text(json.dumps({"v": 1, "scopes": {RID: {"users": {"u_old": old, "u_xh": red}, "days": {}}}}, ensure_ascii=False), encoding="utf-8")
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
idle_after = 3600
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
[ops]
log_dir = {E}/logs
report_dir = {E}/r
panel_token_file = {E}/tok.txt
overrides_file = {E}/ov.json
detect_room = false
autoswitch = false
[welcome]
enabled = true
merge_secs = 1
user_gap = 0
speak = text
[giftfx]
enabled = false
[clips]
enabled = false
[story]
file = {E}/story.json
diary_min_secs = 0
diary_min_events = 3
end_wait = 3
read_gap = 0
recall_p = 1
quote_sample = 0
llm = false
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
        tok = (E / "tok.txt").read_text().strip()
        def api(path, body_=None):
            req = urllib.request.Request(BASE + "/ops/api/" + path, method="POST" if body_ is not None else "GET", data=json.dumps(body_).encode() if body_ is not None else None, headers={"X-Token": tok, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r_: return json.loads(r_.read())
        ss = lambda: api("state")["story"]
        # ---- 没开过播：时钟停在 start_date ----
        check(ss()["enabled"] and ss()["label"] == "2005年9月1日 星期四" and not ss()["started"], f"没开过播：剧情日期停在 2005年9月1日 星期四 {ss()['label']}")
        check(pg.evaluate("window.STORY && STORY.on && STORY.y") == 2005, "页面：STORY 同步到了 2005")
        check(pg.get_attribute("#clk", "title") == "2005年9月1日 星期四", "任务栏时钟悬停提示 = 剧情日期：" + str(pg.get_attribute("#clk", "title")))
        pg.click("#clk"); pg.wait_for_timeout(500)
        check(pg.locator("#story-cal").count() == 1 and "2005年 9月" in pg.inner_text("#story-cal") and pg.locator("#story-cal td.cur").inner_text() == "1", "点时钟：弹出小日历，1 号高亮")
        shot(pg, "01_clock_calendar.png", clip={"x": 880, "y": 330, "width": 400, "height": 390})
        pg.mouse.click(300, 300); pg.wait_for_timeout(300)
        check(pg.locator("#story-cal").count() == 0, "点别处：日历收起")
        # ---- 开播 + 互动 ----
        ev(t="live", live=1)
        check(wait_for(lambda: ss()["started"] and ss()["sess"] and ss()["sess"]["live"], 10), "假开播：第 0 个直播日开始记账")
        for i in range(3):
            ev(t="chat", uid="u_xm", name="小明", text="主播好呀"); time.sleep(0.2)
        ev(t="chat", uid="u_xh", name="小红", text="今天这场直播太好笑了！")
        for _ in range(2): ev(t="chat", uid="u_lr", name="路人甲", text="学到了学到了")
        ev(t="chat", uid="u_ah", name="阿花", text="来个蓝屏"); ev(t="gift", uid="u_th", name="土豪", gift="玫瑰花", count=2, value=2)
        r = None
        for _ in range(20):
            r = api("do", {"action": "perform_now", "which": "fireworks"})
            if r.get("ok"): break
            time.sleep(0.5)
        check(r.get("ok"), f"开一场烟花表演（标记成高光）：{r}")
        check(wait_for(lambda: ss()["sess"]["hl"] >= 1, 20), "高光记进了本场")
        check(wait_for(lambda: api("state")["idle"]["cur"] is None, 60), "烟花演完了")
        pg.wait_for_timeout(1500)
        check(ss()["sess"]["chats"] >= 4 and ss()["sess"]["viewers"] >= 3, f"本场记账：{ss()['sess']}")
        # ---- 下播 → 写日记 ----
        ev(t="live", live=0)
        check(wait_for(lambda: ss()["diaries"] == 1, 20), "下播 3 秒后写出日记")
        d = ss()["last"]
        check(d and not d["published"] and d["how"] == "模板" and "小明" in d["text"] and "土豪" in d["text"], f"日记（模板）：《{d and d['title']}》{d and d['text']}")
        check(get("/story.json")["diaries"] == [], "/story.json：没发表的日记不给页面")
        pg2 = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2); pg2.goto(BASE + "/panel#token=" + tok); pg2.wait_for_timeout(1800)
        pg2.click("#bar button[data-t=story]"); pg2.wait_for_timeout(1500)
        check("2005年9月1日" in pg2.inner_text("#t-story") and "待发表 1" in pg2.inner_text("#t-story"), "面板「剧情」页：剧情日期 / 日记待发表 1")
        shot(pg2, "02_panel_story.png")
        # ---- 往后走一天 → 下次开播发表 ----
        pg2.once("dialog", lambda d_: d_.accept()); pg2.locator("#t-story button", has_text="往后走一天").click()
        check(wait_for(lambda: ss()["label"] == "2005年9月2日 星期五", 10), "面板「往后走一天」→ 2005年9月2日 星期五")
        check(wait_for(lambda: pg.get_attribute("#clk", "title") == "2005年9月2日 星期五", 10), "页面时钟提示跟着变（服务端推 story 事件）")
        ev(t="live", live=1)
        check(wait_for(lambda: ss()["published"] == 1, 10), "下一次开播：日记发表")
        check(wait_for(lambda: pg.evaluate("QQX.zone.data.blogs.some(b => b.diary)"), 10), "页面：日记同步成了 QQ空间 的日志")
        # ---- 冷场翻日记念出来 ----
        r = None
        for _ in range(30):
            r = api("do", {"action": "story_read"})
            if r.get("ok"): break
            time.sleep(0.5)
        check(r and r.get("ok"), f"面板「现在念一篇」：{r}")
        check(wait_for(lambda: pg.locator(".qz [data-diary]").count() >= 1 or pg.locator(".qz .post").count() >= 1, 20), "QQ空间窗口开了，翻到日志页")
        check(wait_for(lambda: any(d["title"] in l and "今天直播了" in l for l in body().split("\n")), 15), "群聊里：猪猪侠念出日记（开场白 + 正文）")
        check(wait_for(lambda: "‹ 返回日志列表" in body(), 10), "点开了最新一篇日记（日志详情）")
        pg.wait_for_timeout(600)
        shot(pg, "03_diary_read_aloud.png")
        check(ss()["unread"] == 0 and ss()["stats"]["reads"] == 1, "念过就标记已读，不会反复念")
        check(wait_for(lambda: api("state")["idle"]["cur"] is None, 60), "念完了，收拾桌面")
        pg.evaluate("WM.open('qzone', {tab: 'blog'})"); pg.wait_for_timeout(1200)
        txt = pg.inner_text(".qz")
        check("2005-09-01" in txt and "· 日记" in txt and "2005-08" in txt, "QQ空间日志列表：日记盖的是剧情日期 2005-09-01，原有的老日志排到剧情开始之前（2005-08…）")
        shot(pg, "04_qzone_diary_dates.png")
        # ---- 观众记忆：欢迎老观众 / 刚才说过的话 ----
        pg.evaluate("WM.byId.qzone && WM.byId.qzone.close()"); pg.wait_for_timeout(500)
        ev(t="member", uid="u_old", name="老观众阿花")
        check(wait_for(lambda: any("老观众阿花" in l and ("还记得" in l or "日记里写到你" in l) for l in body().split("\n")), 40), "老观众进场：欢迎词里带上记得的事（常玩的口令 / 说过的话 / 日记里写到他）")
        ev(t="member", uid="u_xh", name="小红")
        check(wait_for(lambda: any("小红" in l and "「今天这场直播太好笑了！」" in l for l in body().split("\n")), 40), "刚才说过一句话的观众再进场：欢迎词里复述她的话")
        pg.wait_for_timeout(800)
        shot(pg, "05_welcome_memory.png")
        check(not errs, f"页面没有 JS 错误 {errs}")
        b.close()
finally:
    srv.terminate()
print("PASS" if not bad else "FAIL " + str(bad)); sys.exit(1 if bad else 0)
