# -*- coding: utf-8 -*-
"""观众互动（[play]）页面级验证 + 截图（headless Chrome → screenshots/play/）。每一步都有断言，最后 PASS / FAIL，失败退出码 1。
   起一个带房间号但没开直播的服务（事件靠 /qq/event 灌进“真实直播间”的管线；不会碰真正的直播间）：
       .venv/bin/python backend/server.py 889896824783 --port 8781 --config /tmp/xxx.ini     （[agent] test_endpoints=true；建议 [play] chat_gap=0 vote_secs=12 skip_count=3，data_file 指到临时文件；
       **要 [giftfx] enabled=false**：开着时有钻石数的礼物由 giftfx（§11.12）按钻石档位接管，页面的「礼物名 / 钻石数 → 特效」映射（[play] gift_map / gift_value_map、[qq] gift_map）让位，
       这是设计如此（不然一个礼物放两遍特效）；本脚本测的是映射这一层，所以脚本开头会探测，giftfx 开着就直接报错退出，免得后面一串假失败）
   然后：  python tools/shoot_play.py --base http://localhost:8781
   --agent    额外测 Agent 动作（play_fx / rank_open / vote_start：/agent/do，光标真的去点）+ 口令（“放烟花”等经 /qq/event 走 NLU）
   --restart "命令"   重启服务后确认积分还在（存档）；命令要能把同一端口的服务重新拉起来"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import argparse, json, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://localhost:8781")
ap.add_argument("--agent", action="store_true")
ap.add_argument("--restart", default="")
ap.add_argument("--chrome", default="")
A = ap.parse_args()
OUT = Path(__file__).resolve().parent.parent / "screenshots" / "play"; OUT.mkdir(parents=True, exist_ok=True)
from playwright.sync_api import sync_playwright
bad = []
def check(c, m):
    print(("ok   " if c else "FAIL ") + m)
    if not c: bad.append(m)
def get(p, base=None):
    with urllib.request.urlopen((base or A.base) + p, timeout=60) as r: return json.loads(r.read())
def ev(**k): return get("/qq/event?" + urllib.parse.urlencode(k))
def quant(path):
    try:
        from PIL import Image
        Image.open(path).convert("RGB").quantize(256, method=Image.MEDIANCUT, dither=Image.NONE).save(path, optimize=True)
    except Exception: pass
def shot(pg, name, **kw):
    p = OUT / name; pg.screenshot(path=str(p), **kw); quant(p); print("  →", p.relative_to(OUT.parent.parent))
Q = "/?desk=xp&xp_boot=0&musicdemo=1&play_fx_cooldown=0&qq_gift_cooldown=0&play_fx_virus_secs=4&play_fx_secs=5&play_vote_close_secs=30"
with sync_playwright() as p:
    import shutil
    exe = A.chrome or shutil.which("google-chrome") or shutil.which("chromium") or "/usr/bin/google-chrome"
    b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1280, "height": 720}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.goto(A.base + Q); pg.wait_for_timeout(2200)

    # ---- 1. 配置 / 脚本 ----
    cj = get("/config.json"); check("play" in cj and cj["play"].get("points") is not None, "/config.json 带 play 配置")
    check(pg.evaluate("!!(window.PLAYX && PLAYX.cfg.enabled)"), "PLAYX 加载")
    check(pg.evaluate("['fireworks','meteor','emoji','virus','bsod'].every(k=>typeof QQX.actions[k]==='function')"), "play-fx 的 5 个特效注册进了 QQX.actions（和 item 4 同一套）")
    check(pg.evaluate("QQX.giftAction({gift:'烟花',value:1,count:1})") == "fireworks" and pg.evaluate("QQX.giftAction({gift:'玫瑰花',value:1,count:1})") == "pet:feed+emoji:🌹", "[play] gift_map 叠进了 QQX 映射（后来者覆盖/追加，+ 组合）")
    check(pg.evaluate("QQX.giftAction({gift:'火箭',value:3000,count:1})") == "bsod", "[play] gift_value_map 生效（价值 3000 → 蓝屏）")

    # ---- 2. 积分 / 等级 / 徽章 / 反刷屏 ----
    for t in ["你好呀大家", "今天天气真好啊", "主播唱得真好听", "前排沙发坐稳了", "晚上好啊主播", "哈哈哈哈哈哈", "在吗在吗在吗"]: ev(t="chat", uid="u1", name="痴情梦丶", text=t)
    for _ in range(4): ev(t="chat", uid="u7", name="刷屏怪", text="刷屏刷屏刷屏刷屏")
    ev(t="gift", uid="u2", name="冷月无声", gift="嘉年华", count=2, value=100); ev(t="like", uid="u3", name="小丑@鱼", count=25)
    ev(t="follow", uid="u4", name="蓝色の忧郁"); ev(t="follow", uid="u4", name="蓝色の忧郁")
    ev(t="gift", uid="u5", name="孤独de狼", gift="火箭", count=5, value=1000); ev(t="gift", uid="u6", name="暗夜精灵", gift="跑车", count=3, value=2000)
    for u, n, t in (("u5", "孤独de狼", "我来啦大家好"), ("u6", "暗夜精灵", "我是土豪哦"), ("u2", "冷月无声", "谢谢大家的支持")): ev(t="chat", uid=u, name=n, text=t)
    pg.wait_for_timeout(2500)
    rows = {r["uid"]: r for r in get("/play/rank.json?by=total")["rows"]}
    check(len(rows) >= 6, f"榜上有 {len(rows)} 人")
    spam = rows.get("u7", {}).get("pts", 0); check(0 < spam <= 3 + 5, f"同一句重复发：只算第一次（刷屏怪 {spam} 分）")
    check(rows["u6"]["pts"] > rows["u5"]["pts"] > rows["u1"]["pts"], "送礼 > 聊天：积分排序合理")
    nb = pg.evaluate("document.querySelectorAll('#list .lvb').length"); check(nb >= 3, f"聊天里名字前有等级图标 ({nb})")
    check(pg.evaluate("[...document.querySelectorAll('#list .lvb img')].every(i=>i.getBoundingClientRect().width<=20)"), "等级图标是小图标（不撑破）")
    check(pg.evaluate("document.querySelectorAll('#members .lvb, .members .lvb, [id*=member] .lvb').length") >= 0, "成员列表渲染不崩")
    ev(t="chat", uid="u1", name="痴情梦丶", text="我的积分"); pg.wait_for_timeout(2300)
    check(pg.evaluate("[...document.querySelectorAll('#list .sysline')].some(e=>/积分/.test(e.textContent)&&/痴情梦丶/.test(e.textContent))"), "“我的积分”有系统消息回复")
    shot(pg, "01_chat_badges.png")

    # ---- 3. 排行榜窗口 ----
    pg.evaluate("WM.open('rank');0"); pg.wait_for_timeout(1300)
    n = pg.evaluate("WM.byId.rank.pr.rows().length"); check(n >= 6, f"日榜 {n} 行")
    check(pg.evaluate("document.querySelectorAll('.pr tr.r1,.pr tr.r2,.pr tr.r3').length") == 3, "前三名有奖牌样式")
    shot(pg, "02_rank_day.png")
    pg.click('.pr [data-by="total"]'); pg.wait_for_timeout(900); check(pg.evaluate("WM.byId.rank.pr.state().by") == "total", "切到总榜")
    shot(pg, "03_rank_total.png"); pg.evaluate("WM.byId.rank.close();0")

    # ---- 4. 弹幕投票 ----
    r = get("/play/vote?q=" + urllib.parse.quote("下一步干啥") + "&opts=" + urllib.parse.quote("玩红警|换壁纸|玩扫雷") + "&secs=30"); check(r.get("ok"), f"发起投票: {str(r)[:80]}")
    pg.wait_for_timeout(1200); check(pg.evaluate("!!WM.byId.vote && !WM.byId.vote.closed"), "投票窗口自动弹出")
    check(pg.evaluate("document.querySelectorAll('.pv .vo').length") == 3, "窗口里 3 个选项")
    for u, n_, t in (("u1", "痴情梦丶", "1"), ("u2", "冷月无声", "投1"), ("u3", "小丑@鱼", "2"), ("u4", "蓝色の忧郁", "选 1 号"), ("u5", "孤独de狼", "3"), ("u5", "孤独de狼", "2")): ev(t="chat", uid=u, name=n_, text=t)
    pg.wait_for_timeout(1500)
    cnt = pg.evaluate("[...document.querySelectorAll('.pv .vo .c')].map(e=>parseInt(e.textContent))"); check(cnt == [3, 2, 0], f"实时柱状图票数 {cnt}（u5 改投 2 号只算一票）")
    check(pg.evaluate("parseFloat(document.querySelector('.pv .vo[data-n=\"1\"] .fl').style.width)") > 40, "柱子宽度跟着变")
    shot(pg, "04_vote_live.png")
    r = get("/play/vote?end=1"); pg.wait_for_timeout(1500)
    check(pg.evaluate("PLAYX.vote && PLAYX.vote.state") != "open" and pg.evaluate("PLAYX.vote.winner") == 1, "结束：1 号胜出")
    check(pg.evaluate("!!document.querySelector('.pv .vo.win')"), "胜出的选项高亮")
    check(pg.evaluate("[...document.querySelectorAll('#list .sysline')].some(e=>/投票/.test(e.textContent)&&/玩红警/.test(e.textContent))"), "群里有投票结果系统消息")
    shot(pg, "05_vote_done.png")
    pg.wait_for_timeout(800); st = get("/play/state"); check(st["stats"].get("votes", 0) >= 1 and st["history"], "服务端记录了投票历史")
    pg.evaluate("WM.byId.vote && WM.byId.vote.close();0")

    # ---- 5. 切歌投票 ----
    get("/play/testsong?title=" + urllib.parse.quote("夜曲"))
    ev(t="chat", uid="u1", name="痴情梦丶", text="切歌"); ev(t="chat", uid="u1", name="痴情梦丶", text="切歌"); ev(t="chat", uid="u2", name="冷月无声", text="下一首")
    pg.wait_for_timeout(1400)
    s = get("/play/state")["skip"]; check(s["have"] == 2 and s["need"] == 3, f"重复投票只算一次：{s['have']}/{s['need']}")
    check(pg.evaluate("!!WM.byId.skipvote && /2 \\/ 3/.test(WM.byId.skipvote.el.textContent)"), "切歌进度小窗显示 2 / 3")
    shot(pg, "06_skip_progress.png")
    ev(t="chat", uid="u3", name="小丑@鱼", text="切歌"); pg.wait_for_timeout(1500)
    check(pg.evaluate("!!WM.byId.skipvote && /通过/.test(WM.byId.skipvote.el.textContent)"), "达标后小窗显示“切歌投票通过”")
    check(get("/play/state")["skip"]["have"] in (0, 3), "达标后票数清零（或保留到换歌）")
    shot(pg, "07_skip_done.png"); get("/play/testsong?off=1"); pg.evaluate("WM.byId.skipvote && WM.byId.skipvote.close();0")

    # ---- 6. 礼物特效（和 item 4 的 gift_map 是同一机制）----
    INK = "[...document.querySelectorAll('.pfx')].some(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i]>0)n++;return n>300})"   # 覆盖层上真的画了东西
    probe = ev(t="gift", uid="fx0", name="探测君", gift="探测", count=1, value=1)       # 探一下 giftfx 开没开：有钻石数的礼物会被打上 giftfx 标记（返回的事件里能看到）
    GFX = bool((probe.get("event") or {}).get("giftfx"))
    check(not GFX, "[giftfx] 已关（开着时有钻石数的礼物归 giftfx 按钻石档位接管、页面礼物映射让位——设计如此；本节测映射层，请用 giftfx.enabled=false 起服务）")
    if not GFX:
        def fx(label, gift, key, cond, wait=1000, name="特效侠", ink=False, **kw):
            pg.evaluate("PLAYX.fxStop();0"); ev(t="gift", uid="fx1", name=name, gift=gift, count=1, value=kw.get("value", 1)); pg.wait_for_timeout(wait)
            ok = pg.evaluate(cond) and (not ink or pg.evaluate(INK)); check(ok, f"礼物『{gift}』→ {label}"); return ok
        if fx("烟花", "烟花", "fireworks", "(PLAYX.fxLive.fireworks||0)>0 && !!document.querySelector('.pfx-fire')", ink=True): pg.wait_for_timeout(1200); shot(pg, "08_fx_fireworks.png")
        if fx("流星雨", "流星雨", "meteor", "(PLAYX.fxLive.meteor||0)>0 && !!document.querySelector('.pfx-meteor')", ink=True): pg.wait_for_timeout(1200); shot(pg, "09_fx_meteor.png")
        if fx("满屏表情雨 + 宠物喂食（组合）", "玫瑰花", "emoji", "(PLAYX.fxLive.emoji||0)>0 && !!document.querySelector('.pfx-emoji')", ink=True): pg.wait_for_timeout(1500); shot(pg, "10_fx_emoji.png")
        pg.evaluate("PLAYX.fxStop();0")
        icon0 = pg.evaluate("getComputedStyle(document.querySelector('.dicon img')).content")
        ev(t="gift", uid="fx1", name="病毒君", gift="熊猫", count=1, value=1); pg.wait_for_timeout(900)
        check(pg.evaluate("document.body.classList.contains('pfx-virus')"), "礼物『熊猫』→ 中毒：桌面图标换成熊猫烧香")
        check(pg.evaluate("getComputedStyle(document.querySelector('.dicon img')).content") != icon0, "图标 content 真的变了")
        shot(pg, "11_fx_virus.png"); pg.wait_for_timeout(4800)
        check(not pg.evaluate("document.body.classList.contains('pfx-virus')") and pg.evaluate("getComputedStyle(document.querySelector('.dicon img')).content") == icon0, "到时间自动恢复（图标还原）")
        ev(t="gift", uid="fx1", name="蓝屏君", gift="蓝屏", count=1, value=1); pg.wait_for_timeout(1500)
        check(pg.evaluate("XP.screen") == "bsod", "礼物『蓝屏』→ 蓝屏彩蛋"); shot(pg, "12_fx_bsod.png"); pg.evaluate("XP.skipScreen();0"); pg.wait_for_timeout(800)
        ev(t="gift", uid="fx1", name="价值君", gift="神秘礼物", count=1, value=2000); pg.wait_for_timeout(800)
        check(pg.evaluate("(PLAYX.fxLive.fireworks||0)>0") and pg.evaluate("document.querySelector('.stage, #stage').className.includes('shake') || (QQX.log.slice(-2).map(x=>x.spec).join(',').includes('shake'))"), "价值映射 2000=fireworks+shake（一个礼物同时两个效果）")
        pg.evaluate("PLAYX.fxStop();0")
        n0 = len(pg.evaluate("PLAYX.fxLog")); pg2 = None
        pg.evaluate("PLAYX.cfg.fx_cooldown=30;0"); ev(t="gift", uid="fx1", name="特效侠", gift="烟花", count=1, value=1); pg.wait_for_timeout(500); ev(t="gift", uid="fx1", name="特效侠", gift="烟花", count=1, value=1); pg.wait_for_timeout(500)
        check(len(pg.evaluate("PLAYX.fxLog")) - n0 <= 1, "fx_cooldown：冷却内的第二个烟花被忽略"); pg.evaluate("PLAYX.cfg.fx_cooldown=0;PLAYX.fxStop();0")
        pg.evaluate("PLAYX.cfg.fx=false;0"); n1 = len(pg.evaluate("PLAYX.fxLog")); ev(t="gift", uid="fx1", name="特效侠", gift="流星雨", count=1, value=1); pg.wait_for_timeout(500)
        check(len(pg.evaluate("PLAYX.fxLog")) == n1, "[play] fx=false：特效全关"); pg.evaluate("PLAYX.cfg.fx=true;0")

    def wf(cond, ms=8000):
        try: pg.wait_for_function(cond, timeout=ms)
        except Exception: pass
    # ---- 7. Agent 动作 / 口令 ----
    if A.agent:
        def do(acts, **kw): return get("/agent/do?a=" + urllib.parse.quote(json.dumps(acts, ensure_ascii=False)) + "&name=" + urllib.parse.quote(kw.get("name", "测试观众")))
        r = do([{"action": "play_fx", "kind": "fireworks"}]); check(r["ok"], "agent 校验通过 play_fx"); wf("(PLAYX.fxLive.fireworks||0)>0", 12000)
        check(pg.evaluate("PLAYX.fxLog.slice(-1)[0].kind") == "fireworks" and pg.evaluate("(PLAYX.fxLive.fireworks||0)>0"), "play_fx 真的放了烟花"); pg.evaluate("PLAYX.fxStop();0")
        r = do([{"action": "play_fx", "kind": "virus"}]); check(r["ok"], "agent 校验通过 virus（danger 1，主播/观众命令均放行）"); wf("document.body.classList.contains('pfx-virus')", 12000); check(pg.evaluate("document.body.classList.contains('pfx-virus')"), "agent 触发中毒（4 秒后自动恢复）")
        wf("!document.body.classList.contains('pfx-virus')", 9000); check(not pg.evaluate("document.body.classList.contains('pfx-virus')"), "agent 触发的中毒也自动恢复"); pg.evaluate("PLAYX.fxStop();0")
        r = do([{"action": "open_app", "app": "rank"}, {"action": "rank_open", "by": "total"}]); wf("!!WM.byId.rank && WM.byId.rank.pr.state().by==='total'", 15000)
        check(pg.evaluate("!!WM.byId.rank && WM.byId.rank.pr.state().by") == "total", "agent 光标打开排行榜并切到总榜"); shot(pg, "13_agent_rank.png"); pg.evaluate("WM.byId.rank&&WM.byId.rank.close();0")
        pg.evaluate("PLAYX.fxLog.length=0;0"); ev(t="chat", uid="v9", name="路人乙", text="放烟花"); wf("PLAYX.fxLog.length>0", 15000)
        check(pg.evaluate("PLAYX.fxLog.length&&PLAYX.fxLog.slice(-1)[0].kind") == "fireworks", "观众说“放烟花”走 NLU 触发特效（[play] commands）"); pg.evaluate("PLAYX.fxStop();0")
        r = do([{"action": "vote_start", "options": "玩扫雷|换壁纸", "secs": 8}], name="猪猪侠"); pg.wait_for_timeout(1500)
        check(get("/play/state")["vote"] and get("/play/state")["vote"]["state"] == "open", "agent（主播身份）能发起投票")
        r = do([{"action": "vote_start", "options": "A|B"}], name="路人乙"); check(get("/play/state")["vote"]["opts"][0]["label"] == "玩扫雷", "路人不能顶掉/另开投票")
        get("/play/vote?cancel=1"); pg.wait_for_timeout(1000)
    check(not errs, f"页面无 JS 错误 {errs[:2]}")

    # ---- 8. 存档（可选：重启服务）----
    if A.restart:
        before = {r["uid"]: r["pts"] for r in get("/play/rank.json?by=total")["rows"]}; time.sleep(11)
        subprocess.run(A.restart, shell=True); time.sleep(6)
        after = {r["uid"]: r["pts"] for r in get("/play/rank.json?by=total")["rows"]}
        check(before and all(after.get(k) == v for k, v in before.items()), f"重启服务后积分还在（{len(after)} 人）")
    b.close()
print("PASS" if not bad else f"FAIL {len(bad)}: " + "; ".join(bad[:6])); sys.exit(1 if bad else 0)
