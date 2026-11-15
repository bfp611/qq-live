# -*- coding: utf-8 -*-
"""玩法提示（[tips]）离线测试：每条提示的命令都能被解析成有效动作、提示文字里引用的命令也都有效；
   一轮不重复 / 重启不重头 / 不可用的跳过；安静 / 间隔 / 投票 / 主播说话等门槛；演示 → 「你们也能玩」；菜单；面板接口。
   python tools/test_tips.py        页面级（真浏览器看群聊里出现）见 tools/shoot_tips.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import asyncio, json, re, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from host.config import Config, DEFAULTS
from agent import rules, registry as REG
from agent import tips as T
from agent.core import Agent
from agent.desk import Desk
import jukebox
from ai6 import plus as PLUS

bad = 0; total = 0
def check(c, m):
    global bad, total
    total += 1
    if not c:
        bad += 1; print("FAIL", m)

# ---- 1. 每条内置提示的命令：真的会被处理，而且动作有效 ----
EXPECT = {"next": "music_next", "ra2": "open_app", "ra2away": "move_away", "mine": "mine_play", "sol": "sol_play", "wall": "change_wallpaper", "bsod": "bsod",
          "paint": "paint_draw", "note": "notepad_type", "calc": "calc", "pet": "pet_care", "outfit": "outfit_change", "shake": "shake", "fw": "play_fx",
          "meteor": "play_fx", "virus": "play_fx", "rank": "rank_open", "idiom": "game_start", "songgame": "game_start", "riddle": "game_start", "screen": "screen_comment"}
check(len(T.TIPS) == 23 and len({t[0] for t in T.TIPS}) == 23, "23 条内置提示，id 不重复")
for tid, cmd, text, kind, demo in T.TIPS:
    h = T.handler_of(cmd)
    check(h == kind, f"[{tid}] {cmd!r} 处理方 {h} ≠ 声明的 {kind}")
    if kind == "rule":
        it = rules.parse(cmd, None)
        names = [a["action"] for a in it.actions]
        check(EXPECT[tid] in names, f"[{tid}] {cmd!r} 动作 {names} 里没有 {EXPECT[tid]}")
        for a in it.actions:
            check(a["action"] in REG.ACTIONS, f"[{tid}] 动作 {a['action']} 不在注册表里")
            args, err = REG.coerce(a["action"], {k: v for k, v in a.items() if k != "action"}, 200)
            check(not err, f"[{tid}] {a} 参数无效：{err}")
    # 提示文字里引用的『命令』也要有效（点歌 / 在记事本 / 记住我 这类带参数的也算）
    quoted = re.findall(r"『([^』]+)』", text)
    check(quoted, f"[{tid}] 提示文字里没有『命令』")
    for q in quoted:
        ok = T.handler_of(q) is not None or PLUS.REMEMBER_RE.match(q)
        check(ok, f"[{tid}] 提示里写的『{q}』没人理")
    check(len(text) <= 60, f"[{tid}] 提示太长：{len(text)} 字")
    if demo:
        check(demo[0] in ("idle", "fx"), f"[{tid}] 演示类型")
        if demo[0] == "idle":
            from agent.idle import ACTS
            check(demo[1] in ACTS, f"[{tid}] 演示活动 {demo[1]} 不存在")
        else:
            check(demo[1] in ("fireworks", "meteor"), f"[{tid}] 演示特效 {demo[1]}")
check(not any(t[0] == "bsod" and t[4] for t in T.TIPS), "蓝屏不做演示")
check(all(c in T.POOL_CMD for c in T.MENU_POOL) and T.MENU_POOL[0] == "点歌 晴天", "菜单池里的命令都在提示表里")
# 错的命令会被发现（防止测试本身是摆设）
check(T.handler_of("今天天气真好") is None, "普通聊天不会被当成命令")

# ---- 2. 假的运行环境 ----
def mkcfg(**o):
    ini = Path(tempfile.mkdtemp(prefix="tips-")) / "t.ini"
    lines = ["[tips]"] + [f"{k} = {v}" for k, v in o.items()] + ["[agent]", "test_endpoints = true"]
    ini.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return Config(str(ini)), ini.parent
class Host:
    def __init__(s): s.busy_until = 0; s.last = {}; s.said = []
    def bl_in(s, t): return False
    def bl_out(s, t): return False
    def _say(s, kind, prio, text, emo): s.said.append((kind, text, emo))
class Room:
    def __init__(s): s.clients = {1}; s.evs = []
    def _broadcast(s, ev): s.evs.append(ev)
class Idle:
    def __init__(s): s.last_viewer = 0; s.task = None; s.hist = []; s.begun = []; s.result = "完成"; s.ready_ok = True
    def on(s): return True
    def allowed(s, n): return True
    def ready(s, now): return (s.ready_ok, "" if s.ready_ok else "观众刚说过话")
    def pick(s, desk, now, only=None): return only
    def begin(s, name, force=False):
        s.begun.append(name)
        async def run():
            await asyncio.sleep(0.05)
            s.hist.append({"name": name, "result": s.result})
            if s.result == "被打断": raise asyncio.CancelledError()
        s.task = asyncio.ensure_future(run()); return s.task
    def note_command(s): s.last_viewer = time.time()
def mk(**o):
    cfg, d = mkcfg(state_file=str(Path(tempfile.mkdtemp()) / "st.json"), startup_delay=0, **o)
    host, room, idle = Host(), Room(), Idle()
    ag = Agent(cfg, None, lambda *a: None); ws = object(); ag.add_client(ws); ag.set_snap(ws, {"wins": [{"id": "w1", "app": "ra2", "state": "normal", "z": 0}], "ts": time.time(), "chat": {"vis": 1}})
    app = types.SimpleNamespace(rooms={"889": room}, default_room="889", any_host=lambda: host, play=types.SimpleNamespace(vote_open=lambda: False),
                                plus=types.SimpleNamespace(games=types.SimpleNamespace(cur=None), mem=object()), jukebox=types.SimpleNamespace(enabled=True), ops=None)
    ag.app = app
    idle.agent = ag
    tp = T.Tips(cfg, app, ag, idle, lambda *a: None); tp.state_path = Path(cfg.s("tips", "state_file"))
    return tp, app, host, room, idle, ag
def run(co): return asyncio.get_event_loop().run_until_complete(co) if False else asyncio.new_event_loop().run_until_complete(co)

# ---- 3. 一轮不重复；用完才重来；重启不重头 ----
async def t3():
    tp, app, host, room, idle, ag = mk()
    seen = []
    for _ in range(40):
        tid = tp.next_id()
        if tid is None: break
        seen.append(tid); tp.mark(tid)
    first_round = seen[:len(tp.pool_ids())]
    check(len(set(first_round)) == len(first_round), f"一轮里不重复：{first_round}")
    check(tp.round >= 1, "轮次计数")
    tp2, *_ = mk(); tp2.state_path = tp.state_path
    tp2.bag = []; 
    import copy
    tp3, app3, *_ = mk(); tp3.state_path = tp.state_path
    for _ in range(5):
        t_ = tp.next_id(); tp.mark(t_)
    saved = json.loads(tp.state_path.read_text())
    tp3.start_state = None
    tp3.bag = [x for x in saved["bag"] if x in tp3.pool_ids()]
    check(set(tp3.bag) == set(tp.bag), "状态文件里存着这一轮还没发的")
asyncio.new_event_loop().run_until_complete(t3())
# 一整轮：23 条每条恰好一次（所有提示都可用时）
async def t3b():
    tp, app, host, room, idle, ag = mk()
    order = []
    for _ in range(23):
        tid = tp.next_id(); order.append(tid); tp.mark(tid)
    check(sorted(order) == sorted(t[0] for t in T.TIPS), f"一轮正好 23 条各一次：缺 {set(t[0] for t in T.TIPS) - set(order)}")
    nxt = tp.next_id(); check(nxt in BY and tp.round == 2, "用完才开始第二轮")
    check(nxt != order[-1], "新一轮第一条不和上一轮最后一条相同")
BY = T.BY_ID
asyncio.new_event_loop().run_until_complete(t3b())

# ---- 4. 不可用的跳过：点歌没开 / 互动关了 / 窗口不存在 / 记忆没开 ----
async def t4():
    tp, app, host, room, idle, ag = mk()
    check(tp.available("song") and tp.available("fw") and tp.available("ra2away") and tp.available("memory"), "默认都可用（桌面上有红警窗口）")
    app.jukebox.enabled = False; check(not tp.available("song"), "点歌没开 → 点歌提示不发")
    app.jukebox = None; check(not tp.available("song"), "没有 jukebox")
    ag.set_snap(next(iter(ag.clients)), {"wins": [], "ts": time.time()}); check(not tp.available("ra2away"), "桌面上没有红警窗口 → 『红警挡住了』不发")
    check(tp.available("ra2"), "『打开红警』仍可用")
    tp.cfg.cp["play"]["commands"] = "false"; check(not tp.available("fw"), "[play] commands 关了 → 放烟花提示不发")
    tp.cfg.cp["ai_plus"]["memory_cmd"] = "false"; check(not tp.available("memory"), "记忆命令关了 → 『你还记得我吗』不发")
    tp.cfg.cp["agent"]["enabled"] = "false"; check(not tp.available("mine"), "agent 关了 → 所有桌面命令不发")
    tp.cfg.cp["agent"]["enabled"] = "true"
    tp.cfg.cp["play"]["commands"] = "true"; tp.cfg.cp["ai_plus"]["memory_cmd"] = "true"
    # 选提示时跳过不可用的，但不丢（留在这一轮里）
    ag.set_snap(next(iter(ag.clients)), {"wins": [], "ts": time.time()})
    tp.bag = ["ra2away", "ra2"]; check(tp.next_id() == "ra2", "跳过不可用的，选后面可用的")
    check("ra2away" in tp.bag, "不可用的留在这一轮里，之后可用了还会发")
    tp.bag = ["ra2away"]; r = tp.next_id(); check(r is not None and r != "ra2away", "这一轮剩下的全不可用 → 这一轮算用完，开新一轮")
    tp.bag = ["ra2"]; check(tp.next_id(only="mine") == "mine", "指定某条（面板 / 测试）：不管这一轮用没用过，只要现在能用就行")
    check(tp.next_id(only="mine", need_demo=True) == "mine" and tp.next_id(only="ra2", need_demo=True) is None, "指定演示：没有演示的提示（红警）返回 None")
    check(tp.next_id(only="ra2away") is None, "指定的现在不能用（没红警窗口）→ None")
asyncio.new_event_loop().run_until_complete(t4())

# ---- 5. 门槛：安静 / 间隔 / 投票 / 主播说话 / 没页面 ----
async def t5():
    tp, app, host, room, idle, ag = mk(idle_secs=40, interval=150, min_gap=90, demo_chance=0, menu="false")
    now = time.time(); idle.last_viewer = now - 5
    await tp.tick(); check(not room.evs and "刚说过话" in tp.why, f"观众刚说过话不发：{tp.why}")
    idle.last_viewer = now - 100
    await tp.tick(); check(len(room.evs) == 1 and room.evs[0]["t"] == "sys" and room.evs[0]["text"].startswith("💡 玩法提示：") and room.evs[0].get("tip") == "tip", f"安静 → 发一条系统消息：{room.evs}")
    await tp.tick(); check(len(room.evs) == 1 and tp.why in ("离上一条太近",), f"刚发完：{tp.why}")
    tp.last_post = now - 100; await tp.tick(); check(len(room.evs) == 1 and tp.why == "间隔未到", f"min_gap 过了但 interval 没到：{tp.why}")
    tp.next_tip = 0; tp.last_post = now - 100
    app.play.vote_open = lambda: True; await tp.tick(); check(len(room.evs) == 1, "投票进行中不发")
    app.play.vote_open = lambda: False
    host.busy_until = time.time() + 5; await tp.tick(); check(len(room.evs) == 1 and "主播" in tp.why, "主播正在说话不发")
    host.busy_until = 0; room.clients = set(); await tp.tick(); check(len(room.evs) == 1, "没有页面连着不发")
    room.clients = {1}; app.plus.games.cur = types.SimpleNamespace(state="playing"); await tp.tick(); check(len(room.evs) == 1, "小游戏进行中不发")
    app.plus.games.cur = None
    idle.task = asyncio.ensure_future(asyncio.sleep(1)); await tp.tick(); check(len(room.evs) == 1 and "玩电脑" in tp.why, "猪猪侠正在玩电脑不发"); idle.task.cancel()
    idle.task = None; tp.cfg.cp["tips"]["enabled"] = "false"; await tp.tick(); check(len(room.evs) == 1, "enabled=false 不发")
    tp.cfg.cp["tips"]["enabled"] = "true"
    await tp.tick(); check(len(room.evs) == 2, "条件都满足又发一条")
    check(not host.said, "普通提示不出声（只有演示后的那句出声）")
asyncio.new_event_loop().run_until_complete(t5())

# ---- 6. 菜单：不要求安静，但不打断投票 ----
async def t6():
    tp, app, host, room, idle, ag = mk(menu_interval=480, min_gap=90, demo_chance=0)
    now = time.time(); idle.last_viewer = now
    tp.next_menu = 0
    await tp.tick(); m = [e for e in room.evs if e.get("tip") == "menu"]
    check(len(m) == 1 and m[0]["text"].startswith("📋 玩法菜单") and "点歌 晴天" in m[0]["text"], f"没人安静也发菜单：{room.evs}")
    cmds = m[0]["text"].split("→", 1)[1].split("/")
    check(5 <= len(cmds) <= 6, f"菜单 5~6 条命令：{len(cmds)}")
    check(all(T.handler_of(c.strip()) for c in cmds), f"菜单里的命令都有效：{cmds}")
    check(tp.next_menu > now + 400, "下次菜单在 ~8 分钟后")
    tp.next_menu = 0; tp.last_post = now - 100; app.play.vote_open = lambda: True; n = len(room.evs); await tp.tick(); check(len(room.evs) == n, "投票时不发菜单")
    app.play.vote_open = lambda: False; await tp.tick(); m2 = [e for e in room.evs if e.get("tip") == "menu"]
    check(len(m2) == 2 and m2[1]["text"] != m2[0]["text"], f"下一份菜单换了一批命令：{m2[1]['text'] if len(m2) > 1 else None}")
    tp.cfg.cp["tips"]["menu_items"] = "点歌 晴天, 玩扫雷 | 放烟花"; tp.next_menu = 0; tp.last_post = 0; await tp.tick()
    check(room.evs[-1]["text"].endswith("点歌 晴天 / 玩扫雷 / 放烟花"), f"menu_items 自定义：{room.evs[-1]['text']}")
    tp.cfg.cp["tips"]["menu"] = "false"; tp.next_menu = 0; tp.last_post = 0; n = len(room.evs); tp.next_tip = 1e12; await tp.tick(); check(len(room.evs) == n, "menu=false")
asyncio.new_event_loop().run_until_complete(t6())

# ---- 7. 演示 → 你们也能玩 ----
async def t7():
    tp, app, host, room, idle, ag = mk(demo_chance=1, use_tts=True, min_gap=0)
    now = time.time(); idle.last_viewer = now - 100
    tp.bag = ["mine", "fw", "song"]
    r = await tp.send_next(now)
    check(idle.begun == ["play_minesweeper"], f"演示：走冷场玩电脑的活动 {idle.begun}")
    d = [e for e in room.evs if e.get("tip") == "demo"]
    check(len(d) == 1 and "刚才这个你们也能玩" in d[0]["text"] and "『玩扫雷』" in d[0]["text"], f"演示后发「你们也能玩」：{room.evs}")
    await asyncio.sleep(0.1)
    check(host.said and host.said[0][0] == "tip" and "玩扫雷" in host.said[0][1] and len(host.said[0][1]) <= 20, f"TTS 一句很短的话：{host.said}")
    check(not tp.busy and "mine" not in tp.bag, "演示结束；这条在这一轮里用掉了")
    # 被打断：不发教学句
    idle.result = "被打断"; room.evs.clear(); host.said.clear(); tp.bag = ["sol", "song"]
    await tp.send_next(now)
    check(idle.begun[-1] == "play_solitaire" and not [e for e in room.evs if e.get("tip") == "demo"], "演示被观众打断 → 不发教学句")
    check([e for e in room.evs if e.get("tip") == "tip"] and "纸牌" in room.evs[-1]["text"], f"演示没成功 → 改发文字提示：{room.evs}")
    # idle 说现在不行（观众刚说过话）→ 改发文字
    idle.result = "完成"; idle.ready_ok = False; room.evs.clear(); tp.bag = ["paint", "song"]; n = len(idle.begun)
    await tp.send_next(now); check(len(idle.begun) == n and room.evs and room.evs[-1]["tip"] == "tip", "idle 没准备好 → 文字提示")
    # demo=false
    idle.ready_ok = True; tp.cfg.cp["tips"]["demo"] = "false"; room.evs.clear(); tp.bag = ["wall", "song"]; n = len(idle.begun)
    await tp.send_next(now); check(len(idle.begun) == n and room.evs[-1]["tip"] == "tip", "demo=false 只发文字")
    tp.cfg.cp["tips"]["demo"] = "true"
    # use_tts=false
    tp.cfg.cp["tips"]["use_tts"] = "false"; host.said.clear(); room.evs.clear(); tp.bag = ["calc", "song"]
    await tp.send_next(now); await asyncio.sleep(0.1); check([e for e in room.evs if e.get("tip") == "demo"] and not host.said, "use_tts=false：只发文字不出声")
    # 蓝屏之类没有演示的：永远只是文字
    tp.bag = ["bsod"]; room.evs.clear(); await tp.send_next(now); check(room.evs[-1]["tip"] == "tip" and idle.begun[-1] != "bsod", "蓝屏只发文字提示")
asyncio.new_event_loop().run_until_complete(t7())

# ---- 8. 烟花 / 流星雨演示走 agent 动作管线（校验 + execute）----
async def t8():
    tp, app, host, room, idle, ag = mk(demo_chance=1, min_gap=0)
    sent = []
    async def fake_exec(actions, ev, room_, text, user): sent.append(actions); idle.note_command()
    ag.execute = fake_exec
    import agent.tips as TT
    orig_sleep = asyncio.sleep
    TT.asyncio.sleep = lambda s: orig_sleep(0)
    idle.last_viewer = time.time() - 100; tp.bag = ["fw", "song"]
    await tp.send_next(time.time())
    check(sent and sent[0][0]["action"] == "play_fx" and sent[0][0]["kind"] == "fireworks", f"烟花演示动作：{sent}")
    check(time.time() - idle.last_viewer > 50, "演示不会把「安静计时」清零（execute 里的 note_command 被还原）")
    check(room.evs and room.evs[-1]["tip"] == "demo" and "放烟花" in room.evs[-1]["text"], "教学句")
    tp.cfg.cp["play"]["enabled"] = "false"; sent.clear(); room.evs.clear(); tp.bag = ["meteor", "song"]
    await tp.send_next(time.time()); check(not sent and room.evs[-1]["tip"] == "tip", "互动关了 → 校验不过，不演示，也不发这条文字（不可用）→ 换下一条")
    TT.asyncio.sleep = orig_sleep
asyncio.new_event_loop().run_until_complete(t8())

# ---- 9. 自定义提示 + 面板 / 手动 ----
async def t9():
    tp, app, host, room, idle, ag = mk(custom="发『玩扫雷』试试 | 💡 自己写的整句", builtin="false", demo_chance=0, min_gap=0)
    check(len(tp.pool_ids()) == 2, "builtin=false：只用自己写的")
    idle.last_viewer = 0
    a = await tp.now("tip"); check(a["ok"] and a["text"] == "💡 玩法提示：发『玩扫雷』试试" or a["text"] == "💡 自己写的整句", f"自定义提示（缺前缀的会加上）：{a}")
    tp.last_post = 0; b = await tp.now("tip"); check(b["ok"] and b["text"] != a["text"], "两条自定义轮着发")
    tp.last_post = 0; c = await tp.now("tip"); check(c["ok"], "用完一轮后开新一轮")
    r = await tp.now("tip"); check(not r["ok"] and "太快" in r["error"], "3 秒内连点被拒")
    tp.last_post = 0; room.clients = set(); r = await tp.now("tip"); check(not r["ok"] and "页面" in r["error"], "没有页面：拒绝")
    room.clients = {1}; tp.last_post = 0; tp.cfg.cp["tips"]["builtin"] = "true"; tp.cfg.cp["tips"]["custom"] = ""; tp.bag = []
    r = await tp.now("tip", cmd="玩扫雷"); check(r["ok"] and "玩扫雷" in r["text"], f"指定命令：{r}")
    tp.last_post = 0; r = await tp.now("tip", cmd="不存在的命令"); check(not r["ok"], "指定了不存在的命令")
    tp.last_post = 0; r = await tp.now("menu"); check(r["ok"] and "玩法菜单" in r["text"], "面板：发菜单")
    tp.last_post = 0; idle.last_viewer = time.time() - 100; r = await tp.now("demo"); check(r["ok"] and r["kind"] == "demo", f"面板：演示一个：{r}")
    st = tp.state(); check(st["enabled"] and st["stats"]["demos"] >= 1 and st["last"], f"状态：{st['stats']}")
asyncio.new_event_loop().run_until_complete(t9())

# ---- 10. 配置：默认值和 config.ini 一致 ----
d = DEFAULTS["tips"]
check(d["enabled"] == "true" and float(d["min_gap"]) >= 90 and float(d["menu_interval"]) == 480 and float(d["demo_chance"]) > 0, "默认值：开、间隔 ≥ 90 秒、菜单 8 分钟、有演示")
ci = Config(str(ROOT / "config.ini"))
if "tips" in ci.cp:
    miss = [k for k in ci.cp["tips"] if k not in d]
    check(not miss, f"config.ini [tips] 里有代码不认识的键：{miss}")
    for k, v in d.items():
        if k in ci.cp["tips"]: check(ci.cp["tips"][k] == v, f"config.ini [tips] {k}={ci.cp['tips'][k]!r} ≠ 默认 {v!r}")
else:
    print("（config.ini 里还没有 [tips]，跳过一致性检查）")

print(f"玩法提示测试（{total} 项断言）" + ("全部通过" if not bad else f" 有 {bad} 项失败"))
sys.exit(1 if bad else 0)
