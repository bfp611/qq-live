# -*- coding: utf-8 -*-
"""AI 加强包（[ai_plus]）页面级验证 + 截图（headless Chrome → screenshots/ai6/）。每一步有断言，最后 PASS / FAIL。
   起一个带房间号但没开直播的服务（事件靠 /qq/event 灌进“真实直播间”的管线；不会碰真正的直播间）：
       .venv/bin/python backend/server.py 889896824783 --port 8781 --config /tmp/xxx.ini
       （[agent] test_endpoints=true；[play] chat_gap=0；[ai_plus] game_cooldown=0 game_timeout=20 idiom_rounds=3 memory_file 指到临时文件 memory_session_gap=2 …）
       还要把画面点评 / 歌曲点评调快：[ai_plus] screen_min_gap=5 screen_quiet_secs=3 song_comment_chance=1 song_comment_gap=0 song_comment_delay=1（默认 60 / 20 / 0.5 / 240 / 6 秒，
       等不到点评；「打开新程序」「换歌后」两条就是因为这个才失败）。画面点评要真的视觉模型，所以 [ai] 得配好（会真的调一次 LLM，不碰抖音 / Bark）。
       **这几项必须设**：脚本按「3 轮接满、游戏之间不冷却」写的，config.ini 里的默认值是 idiom_rounds=8、game_cooldown=30——不设的话「接满结束」永远等不到，
       后面的猜歌 / 急转弯会撞上「已经有一场在进行 / 刚玩完歇一会儿」，连环失败（最后一个 TypeError 是题没开起来）。giftfx / welcome 开不开都行。
       **[welcome] enabled=false**：开着进场接待（§11.11）时，进场事件由它接管（打 ai6_greeted 标记），ai6 的「老观众记忆欢迎」让位——设计如此（README §11.11），
       「隔了一阵再来：主播按记忆打招呼」这条测的是 ai6 自己的那一句，所以要关掉 welcome（welcome 开着时老观众的记忆在欢迎词里，见 §11.14）
       用 QQ_NO_FETCH=1 起服务（假房间，不连抖音）；日志不在 /tmp/qq-box-server-<端口>.log 的话用 --log 指一下（画面点评那段要读服务日志里的主播发言）
   然后：python tools/shoot_ai6.py --base http://localhost:8781 [--log 服务日志]    （--only game|memory|voice|song|screen 只测一部分）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import argparse, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://localhost:8781")
ap.add_argument("--only", default="")
ap.add_argument("--chrome", default="")
ap.add_argument("--log", default="")
A = ap.parse_args()
OUT = ROOT / "screenshots" / "ai6"; OUT.mkdir(parents=True, exist_ok=True)
LOG = A.log or "/tmp/qq-box-server-%s.log" % A.base.rsplit(":", 1)[-1].strip("/")      # 服务日志（读主播发言用）：默认 /tmp/qq-box-server-<端口>.log，别处的用 --log
from playwright.sync_api import sync_playwright
from ai6 import games as G
WORDS, BYF = G.load_idioms(G.DATA / "idioms.tsv")
bad = []
def check(c, m):
    print(("ok   " if c else "FAIL ") + m)
    if not c: bad.append(m)
def get(p):
    with urllib.request.urlopen(A.base + p, timeout=60) as r: return json.loads(r.read())
def ev(**k): return get("/qq/event?" + urllib.parse.urlencode(k))
def say(uid, text, name=None): return ev(t="chat", uid=uid, name=name or "观众" + uid, text=text)
def quant(path):
    try:
        from PIL import Image
        Image.open(path).convert("RGB").quantize(256, method=Image.MEDIANCUT, dither=Image.NONE).save(path, optimize=True)
    except Exception: pass
def shot(pg, name, **kw):
    p = OUT / name; pg.screenshot(path=str(p), **kw); quant(p); print("  →", p.relative_to(ROOT))
def want(part): return not A.only or A.only == part
def game(): return get("/ai/state").get("game") or {}
def wait_for(fn, ms=8000, step=200):
    t = time.time()
    while (time.time() - t) * 1000 < ms:
        v = fn()
        if v: return v
        time.sleep(step / 1000)
    return None
Q = "/?desk=xp&xp_boot=0&musicdemo=1&play_fx_cooldown=0&qq_gift_cooldown=0&play_vote_close_secs=30"
with sync_playwright() as p:
    import shutil
    exe = A.chrome or shutil.which("google-chrome") or shutil.which("chromium") or "/usr/bin/google-chrome"
    b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1280, "height": 720}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(A.base + Q); pg.wait_for_timeout(2500)
    st = get("/ai/state"); check(st.get("enabled"), "/ai/state 可用，ai_plus 开着")
    check(pg.evaluate("!!(window.AIX && AIX.cfg.enabled && AIX.on('game'))"), "ai-ui.js 加载，/config.json 带 ai_plus")

    if want("game"):
        # ---- 成语接龙 ----
        print("== 成语接龙"); get("/ai/do?a=game_stop"); time.sleep(0.5)
        r = get("/ai/do?a=game_start:idiom"); check(r.get("ok"), f"开局：{r}")
        g = wait_for(lambda: game() if game().get("kind") == "idiom" else None); check(g and len(g["prompt"]) == 4, f"题面：{g and g['prompt']}")
        check(wait_for(lambda: pg.evaluate("!!(WM.byId.game && !WM.byId.game.closed)")), "游戏窗口自动弹出")
        pg.wait_for_timeout(600); shot(pg, "01_idiom_open.png")
        say("1", "今天天气真不错"); say("1", "天天向上哟")
        words = G.load_idioms(G.DATA / "idioms.tsv")
        def nxt(g):
            need = WORDS[g["prompt"]][-1]
            return next(x for x in BYF[need] if x != g["prompt"] and len(BYF.get(WORDS[x][-1], [])) >= 8)
        a = nxt(game()); say("1", a, "痴情梦丶")
        g2 = wait_for(lambda: game() if game().get("round") == 1 and game()["prompt"] != a else None)
        check(g2 and WORDS[g2["prompt"]][0] == WORDS[a][-1], f"接对「{a}」，主播接「{g2 and g2['prompt']}」（拼音能接上）")
        check(any(x["name"] == "痴情梦丶" and x["ok"] for x in g2["log"]), "答题记录里有观众")
        say("2", g2["prompt"], "冷月无声")                         # 重复用过的
        pg.wait_for_timeout(300); check(game()["round"] == 1, "用过的成语不算")
        a2 = nxt(game()); say("2", a2, "冷月无声"); wait_for(lambda: game()["round"] == 2)
        pg.wait_for_timeout(700); shot(pg, "02_idiom_playing.png")
        nsys = pg.evaluate("(document.getElementById('list').textContent.match(/【成语接龙】/g)||[]).length")
        check(nsys >= 2, f"群消息里有接龙播报（{nsys} 条）")
        g3 = game(); a3 = nxt(g3); say("1", a3, "痴情梦丶")
        g4 = wait_for(lambda: game() if game().get("state") == "done" else None); check(g4 and "接满" in g4["note"] and g4["winner"], f"接满结束，冠军 {g4 and g4['winner']}")
        pg.wait_for_timeout(700); shot(pg, "03_idiom_done.png")
        rk = {r["name"]: r["pts"] for r in get("/play/rank.json?by=total")["rows"]}
        check(rk.get("痴情梦丶", 0) >= 10 + 0 and rk.get("冷月无声", 0) >= 5, f"积分进了榜单：{ {k: rk[k] for k in ('痴情梦丶', '冷月无声') if k in rk} }")
        check(wait_for(lambda: pg.evaluate("!WM.byId.game || WM.byId.game.closed"), 12000), "结束后窗口自动关闭")
        # ---- 猜歌名 ----
        print("== 猜歌名")
        r = get("/ai/do?a=game_start:song"); check(r.get("ok"), f"开局：{r}")
        wait_for(lambda: pg.evaluate("!!(WM.byId.game && !WM.byId.game.closed)"))
        gs = game(); check(gs.get("kind") == "song" and gs.get("prompt"), f"题面：{gs.get('prompt')}")
        say("3", "不知道呀", "小丑@鱼"); say("3", "提示", "小丑@鱼"); pg.wait_for_timeout(900)
        check(game().get("hint"), f"提示出来了：{game().get('hint')}"); shot(pg, "04_song_hint.png")
        songs = {x[3 if False else 2]: None for x in []}
        tit = {r[2]: r[0].split("/")[0] for r in G.load_tsv(G.DATA / "songs.tsv")}
        # 题面是第一条提示：反查歌名
        ans = next((r[0].split("/")[0] for r in G.load_tsv(G.DATA / "songs.tsv") if r[2].split("|")[0] == gs["prompt"]), None)
        check(ans, f"反查到答案：{ans}"); say("4", ans, "孤独de狼")
        g5 = wait_for(lambda: game() if game().get("sub", "").find("答对了") >= 0 else None); check(g5, "猜对：" + str(g5 and g5["sub"]))
        pg.wait_for_timeout(600); shot(pg, "05_song_correct.png")
        get("/ai/do?a=game_stop"); wait_for(lambda: game().get("state") == "done")
        # ---- 脑筋急转弯 ----
        print("== 脑筋急转弯")
        r = get("/ai/do?a=game_start:riddle"); check(r.get("ok"), f"开局：{r}"); gr = wait_for(lambda: game() if game().get("kind") == "riddle" else None)
        ra = next((r for r in G.load_tsv(G.DATA / "riddles.tsv") if r[0] == gr["prompt"]), None); check(ra, f"题：{gr['prompt']}")
        say("5", ra[1].split("|")[0], "暗夜精灵"); check(wait_for(lambda: "答对了" in game().get("sub", "")), "答对")
        pg.wait_for_timeout(500); shot(pg, "06_riddle.png")
        get("/ai/do?a=game_stop"); wait_for(lambda: game().get("state") == "done")
        # ---- 口令 / 开始菜单 ----
        print("== 口令")
        time.sleep(0.5); say("9", "玩成语接龙", "路人甲"); g6 = wait_for(lambda: game() if game().get("kind") == "idiom" and game().get("state") == "open" else None)
        check(g6, "弹幕口令「玩成语接龙」开局（agent 规则 → game_start）")
        time.sleep(3.5); say("9", "结束游戏", "路人甲"); check(wait_for(lambda: game().get("state") == "done"), "「结束游戏」（开局人）结束")
        pg.evaluate("document.getElementById('startbtn') && document.getElementById('startbtn').click()")
        check(pg.evaluate("!!WM.apps && !!(WM.apps.game || WM.registry && WM.registry.game) || typeof WM.open==='function'"), "WM 可打开 game")

    if want("screen"):
        print("== 画面点评")
        def logtail(): 
            try: return open(LOG, encoding="utf-8", errors="ignore").read()
            except Exception: return ""
        def nsay(kind): return len(re.findall(r"\[主播\] \(" + kind + r"/", logtail()))
        pg2 = b.new_page(viewport={"width": 1280, "height": 720}); pg2.on("pageerror", lambda e: errs.append(str(e)))
        pg2.goto(A.base + Q + "&host=1"); pg2.wait_for_timeout(3500)
        stt = get("/ai/state")["screen"]; check(wait_for(lambda: get("/ai/state")["screen"] is not None), "screen 状态可读")
        def do(acts): return get("/agent/do?" + urllib.parse.urlencode({"a": json.dumps(acts, ensure_ascii=False)}))
        do([{"action": "open_app", "app": "notepad"}, {"action": "open_app", "app": "calc"}]); pg2.wait_for_timeout(7000)
        n0 = nsay("screen"); r = get("/ai/do?a=screen_comment"); check(r.get("ok"), f"screen_comment 动作：{r}")
        check(wait_for(lambda: nsay("screen") > n0, 30000), "主播点评了屏幕（日志里有 screen 台词）")
        sc = get("/ai/state")["screen"]; print("   desc:", sc["text"].replace(chr(10), " | ")[:200]); print("   vision:", sc["vision"])
        check("记事本" in sc["text"] and "计算器" in sc["text"], "描述里有打开的程序（记事本、计算器）")
        check(sc["vision"] is True, "带截图问了视觉模型（页面 DOM→SVG→canvas JPEG）")
        lines = [l for l in logtail().splitlines() if "(screen/" in l]; print("   say:", lines[-1][-90:] if lines else "")
        check(lines and "视觉模型失败" not in logtail().split(lines[-1])[0][-400:], "视觉模型调用成功（没有回退）")
        r2 = get("/ai/do?a=screen_comment"); check(not r2.get("ok"), "20 秒内再要：拒绝（防刷）")
        shot(pg2, "07_screen_comment.png")
        # 事件触发：打开一个新程序 → screen_events 自动点评（min_gap / quiet 在测试 ini 里调小了）
        time.sleep(1); n1 = nsay("screen"); do([{"action": "open_app", "app": "paint"}])
        check(wait_for(lambda: nsay("screen") > n1, 40000), "打开新程序 → 事件触发自动点评")
        note = [x["what"] for x in get("/ai/state")["recent"] if "点评屏幕" in x["what"]][-1]; check("画图" in note, f"记录了变化原因：{note}")
        # 文字快照兜底：关闭视觉
        pg2.close()

    if want("memory"):
        print("== 记住常客")
        def logtail():
            try: return open(LOG, encoding="utf-8", errors="ignore").read()
            except Exception: return ""
        pg3 = b.new_page(viewport={"width": 1280, "height": 720}); pg3.on("pageerror", lambda e: errs.append(str(e)))
        pg3.goto(A.base + Q + "&host=1"); pg3.wait_for_timeout(3000)
        def mem_of(n):
            rows = get("/ai/memory?name=" + urllib.parse.quote(n)).get("rows") or []
            return rows[0] if rows else {}
        get("/ai/forget?all=1")
        ev(t="member", uid="m1", name="痴情梦丶"); time.sleep(0.5)
        for t in ["我最喜欢听陈奕迅的歌", "今天加班好累啊"]: say("m1", t, "痴情梦丶")
        ev(t="gift", uid="m1", name="痴情梦丶", gift="玫瑰花", count=3, value=1)
        ev(t="chat", uid="m2", name="路人乙", text="我手机号13812345678加我微信abc123")
        time.sleep(0.5); mem = mem_of("痴情梦丶"); print("   记忆:", json.dumps(mem, ensure_ascii=False)[:240])
        check(mem.get("visits") == 1 and mem.get("topics") and mem.get("gifts"), "第一次来：visits=1，话题 / 礼物记下了")
        topics = json.dumps(mem_of("路人乙"), ensure_ascii=False); check("13812345678" not in topics and "abc123" not in topics, "手机号 / 微信号没有被记住（隐私过滤）")
        n0 = len(re.findall(r"\(greet/", logtail())); time.sleep(3.2)
        ev(t="member", uid="m1", name="痴情梦丶")
        check(wait_for(lambda: len(re.findall(r"\(greet/", logtail())) > n0, 25000), "隔了一阵再来：主播按记忆打招呼（greet）")
        gl = [l for l in logtail().splitlines() if "(greet/" in l][-1]; print("   greet:", gl[-100:])
        check(mem_of("痴情梦丶").get("visits") == 2, "visits=2")
        pg3.wait_for_timeout(1500); shot(pg3, "08_memory_greet.png")
        say("m1", "忘记我", "痴情梦丶"); time.sleep(0.8)
        mem2 = mem_of("痴情梦丶"); check(not mem2, f"「忘记我」：记忆删除并不再记录 {mem2}")
        say("m1", "记住我", "痴情梦丶"); time.sleep(0.5); ev(t="member", uid="m1", name="痴情梦丶"); time.sleep(0.5)
        check(mem_of("痴情梦丶").get("visits") == 1, "「记住我」：恢复记录（从头算）")
        get("/ai/forget?all=1"); pg3.close()

    if want("voice"):
        print("== 多音色")
        pg4 = b.new_page(viewport={"width": 1280, "height": 720}); pg4.on("pageerror", lambda e: errs.append(str(e)))
        pg4.goto(A.base + Q + "&host=1"); pg4.wait_for_timeout(3000)
        get("/ai/do?a=game_stop"); time.sleep(0.5); r = get("/ai/do?a=game_start:riddle"); check(r.get("ok"), f"开局 {r}")
        check(wait_for(lambda: pg4.evaluate("(document.getElementById('list').textContent||'').includes('出题官')"), 15000), "出题时：群聊里发言人是「出题官」（quiz 角色）")
        pg4.wait_for_timeout(800); shot(pg4, "09_voice_roles.png")
        get("/ai/do?a=game_stop"); pg4.close()
        sj = get("/ai/state"); check(True, "state ok")

    if want("song"):
        print("== 歌曲点评")
        def logtail():
            try: return open(LOG, encoding="utf-8", errors="ignore").read()
            except Exception: return ""
        time.sleep(7); n0 = len(re.findall(r"\(songc/", logtail()))
        q = urllib.parse.quote
        r = get("/play/testsong?key=k" + str(int(time.time())) + "&title=" + q("十年") + "&artist=" + q("陈奕迅") + "&dur=240&pos=0&lines=" + q("60:第一句|66:第二句|90:间奏很长|110:最后一句")); print("   ", r)
        check(wait_for(lambda: len(re.findall(r"\(songc/", logtail())) > n0, 30000), "换歌后：主播点评了这首歌（kind=songc）")
        sl = [l for l in logtail().splitlines() if "(songc/" in l][-1]; print("   songc:", sl[-100:])
        check("陈奕迅" in sl or "十年" in sl, "点评提到歌手 / 歌名")
        get("/play/testsong?off=1")


    check(not errs, "页面没有 JS 报错" + (f"：{errs[:3]}" if errs else ""))
    b.close()
print("\nPASS" if not bad else f"\nFAIL {len(bad)}: {bad}")
sys.exit(1 if bad else 0)
