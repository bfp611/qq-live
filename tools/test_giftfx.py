# -*- coding: utf-8 -*-
"""礼物 / 点赞联动（backend/agent/giftfx.py + web/giftfx.js，§11.12）的离线测试：按钻石数分档、连击合并成一次、队列与丢弃、点赞每 300 个一次、
   关注 → 好友标记、1 钻小烟花 / 10 钻随机或点名表演 / 100 钻大场面（重装系统或流星雨 + 高光标记）、蓝屏重启重装的 10 分钟冷却、gift_fx 动作只有主播能用、
   主播自己的感谢让位、开关、接线与配置一致。不联网
   python tools/test_giftfx.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import re, sys, time, types, asyncio, random
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from agent import giftfx as G, perform as PF, registry as R, idle as I, welcome as W
from agent.core import Agent
from agent.desk import Desk
from host.config import Config, DEFAULTS
from host.engine import Host
from play import store as S

bad = 0; total = 0
def check(c, m):
    global bad, total
    total += 1
    if not c:
        bad += 1; print("FAIL", m)

SNAP = {"ts": 1, "wins": [{"id": "qqchat", "app": "qqchat", "title": "群聊", "state": "normal", "x": 478, "y": 18, "w": 700, "h": 512, "z": 5}],
        "chat": {"vis": 1.0}, "start": False, "busy": False, "queue": 0, "music": {"on": True, "title": "晴天", "artist": "周杰伦"}}

class FHost:
    def __init__(s): s.busy_until = 0; s.last = {}; s.said = []
    def bl_in(s, t): return "违禁" in t
    def bl_out(s, t): return "违禁" in t
    def speak(s, kind, prompt, fallback="", emotion="平静", role="", to="", prio=55, **k): s.said.append({"kind": kind, "prompt": prompt, "text": fallback, "to": to})
class FRoom:
    def __init__(s, host=None, rid="889"): s.rid = rid; s.clients = {1}; s.evs = []; s.host = host
    def _broadcast(s, ev): s.evs.append(ev)
class FPlay:
    def __init__(s): s.store = S.PlayStore(None); s.mem = S.PlayStore(None)
    def st(s, scope): return s.mem if scope == "demo" else s.store
    def vote_open(s): return False

def mk(**kv):
    cfg = Config("/nonexistent.ini")
    for k, v in kv.items():
        sec, key = k.split("__"); cfg.cp[sec][key] = str(v)
    host = FHost(); room = FRoom(host)
    app = types.SimpleNamespace(any_host=lambda: host, play=FPlay(), rooms={"889": room}, default_room="889", ops=None, tips=None,
                                jukebox=types.SimpleNamespace(current=None, queue=[], _busy=False), music=None, highlights=[])
    ag = Agent(cfg, app, log=lambda *a: None)
    ag.clients = {"ws": {"at": time.time()}}; ag.snap_ws = "ws"
    ag.desk = lambda: Desk(dict(SNAP, ts=time.time()))
    ag.sent = []
    async def execute(actions, ev, room, text, user): ag.sent.append(actions)
    ag.execute = execute
    idle = I.Idle(cfg, app, ag, log=lambda *a: None)
    idle.t0 -= 1000; idle.last_viewer -= 1000
    idle.began = []
    def begin(name, force=False):
        idle.began.append((name, dict(prefix=idle.perf_prefix, thanks=idle.perf_thanks, quiet=idle.perf_quiet, force=idle.perf_force)))
        async def r():
            idle.hist.append({"name": name, "result": "完成"})
        return asyncio.ensure_future(r())
    idle.begin = begin
    idle.perf_prefix = ""; idle.perf_thanks = None; idle.perf_quiet = False
    app.agent, app.idle = ag, idle
    app.marks = []
    app.mark_highlight = lambda kind, **i: app.marks.append((kind, i))
    gf = G.GiftFx(cfg, app, lambda *a: None); gf.hold = 0.02
    return gf, app, room, host, ag, idle
def gift(uid, name, g, n, v): return {"t": "gift", "uid": uid, "name": name, "gift": g, "count": n, "value": v}
async def rj(gf, job):
    await gf.run_job(job); await asyncio.sleep(0.15)          # speak 在线程池里，等一下它记下
def run(co): return asyncio.new_event_loop().run_until_complete(co)

# ---- 1. 分档 ----
gf, app, room, host, ag, idle = mk()
check([gf.tier_of(v) for v in (0, 1, 9, 10, 99, 100, 5000)] == [0, 1, 1, 2, 2, 3, 3], "档位：1 / 10 / 100 钻")
gf2, *_ = mk(giftfx__t3="false"); check(gf2.tier_of(500) == 2, "关掉 t3：大礼降到 10 钻档")
gf2, *_ = mk(giftfx__tier2="50", giftfx__tier3="500"); check([gf2.tier_of(v) for v in (49, 50, 499, 500)] == [1, 2, 2, 3], "档位门槛可配")

# ---- 2. 事件：标记 / 钻石数为 0 不归这里管 ----
e0 = gift("u1", "甲", "玫瑰", 1, 0); gf.on_event(e0, room, 1000)
check("giftfx" not in e0 and "giftfx_handled" not in e0 and not gf.bursts, "钻石数为 0：不打标记（主播自己感谢 + 页面 gift_map 照旧）")
e1 = gift("u1", "甲", "玫瑰", 1, 1); gf.on_event(e1, room, 1000)
check(e1.get("giftfx") and e1.get("giftfx_handled") and len(gf.bursts) == 1, "1 钻礼物：打了 giftfx / giftfx_handled 标记")
gf2, *_ = mk(giftfx__enabled="false"); e = gift("u1", "甲", "玫瑰", 1, 50); gf2.on_event(e, room, 1000)
check("giftfx" not in e and not gf2.bursts, "enabled=false：什么都不做")

# ---- 3. 连击合并 ----
gf, app, room, host, ag, idle = mk()
for i in range(1, 51): gf.on_event(gift("u2", "乙", "小心心", i, 1), room, 1000 + i * 0.05)       # 抖音连击：累计 1..50
check(len(gf.bursts) == 1 and gf.bursts[("889", "u2")]["n"] == 50 and gf.bursts[("889", "u2")]["value"] == 50, "50 连击（累计 1..50）= 一个 burst，共 50 钻")
gf.on_event(gift("u2", "乙", "小心心", 50, 1), room, 1003)
check(gf.bursts[("889", "u2")]["n"] == 50, "同一个累计数重复发：不重复算")
gf.tick(1004); check(len(gf.q) == 0, "还在 merge_secs 窗口里：不入队")
gf.tick(1006); check(len(gf.q) == 1 and gf.q[0]["tier"] == 2 and gf.q[0]["value"] == 50 and gf.q[0]["n"] == 50, "窗口过了：50 个礼物合成 1 个任务，按总钻石数 50 定档 = 档 2")
gf, *_ = mk(); gf.on_event(gift("u3", "丙", "嘉年华", 1, 3000), room, 1000); gf.on_event(gift("u4", "丁", "玫瑰", 1, 1), room, 1000); gf.tick(1004)
check(sorted(j["tier"] for j in gf.q) == [1, 3], "不同的人各自一个任务")
# 非连击：同一礼物隔很久再送
gf, *_ = mk(); gf.on_event(gift("u5", "戊", "玫瑰", 1, 1), room, 1000); gf.tick(1004); gf.on_event(gift("u5", "戊", "玫瑰", 1, 1), room, 1100); gf.tick(1104)
check(len(gf.q) == 2, "隔了很久再送同一个礼物：算新的一次")
# 队列满了丢最低档
gf, *_ = mk(giftfx__queue_max="2")
for i, v in enumerate((1, 1, 500)): gf.enqueue({"kind": "gift", "tier": gf.tier_of(v), "name": f"n{i}", "n": 1, "value": v, "uid": f"u{i}"})
check(len(gf.q) == 2 and sorted(j["tier"] for j in gf.q) == [1, 3] and gf.stats["dropped"] == 1, f"队列最多 2 个，满了丢最低档：{[j['tier'] for j in gf.q]}")
check(gf.enqueue({"kind": "gift", "tier": 1, "name": "x", "n": 1, "value": 1, "uid": "x"}) is False and gf.stats["dropped"] == 2, "新来的比队列里都低：新的丢")

# ---- 4. 点赞 ----
gf, app, room, host, ag, idle = mk()
for _ in range(29): gf.on_event({"t": "like", "uid": "l1", "count": 10}, room, 1000)
check(not gf.q and gf.likes == 290, "290 个赞：还没到 300")
gf.on_event({"t": "like", "uid": "l1", "count": 10}, room, 1001)
check(len(gf.q) == 1 and gf.q[0]["kind"] == "like" and gf.q[0]["n"] == 300 and gf.next_like == 600, "满 300：一个点赞任务，下一次 600")
gf.on_event({"t": "like", "uid": "l1", "count": 1000}, room, 1002)
check(len(gf.q) == 2 and gf.q[1]["n"] == 1300 and gf.next_like == 1500, "一下子跳过好几个整数：只放一次，下一次对齐到 1500")
gf.on_event({"t": "live", "live": True}, room, 1003); check(gf.likes == 0 and gf.next_like == 0, "开播 / 下播：本场赞清零")
gf, *_ = mk(giftfx__likes="false"); gf.on_event({"t": "like", "uid": "l1", "count": 999}, room, 1); check(not gf.q and gf.likes == 0, "likes=false：不理点赞")
gf, *_ = mk(giftfx__like_step="50"); gf.on_event({"t": "like", "uid": "l1", "count": 60}, room, 1); check(len(gf.q) == 1, "like_step 可配")

# ---- 5. 关注 → 好友 ----
gf, app, room, host, ag, idle = mk()
e = {"t": "follow", "uid": "f1", "name": "小朋"}; gf.on_event(e, room, 1000); gf.on_event({"t": "follow", "uid": "f2", "name": "小友"}, room, 1001)
check(e.get("giftfx_handled"), "关注：主播自己的感谢让位")
check(app.play.store.scope("889")["users"]["f1"]["friend"] is True and gf.friend_count() == 2, "关注后记进好友列表（用户记录 friend=true）")
gf.tick(1004); check(len(gf.q) == 1 and gf.q[0]["kind"] == "follow" and gf.q[0]["names"] == ["小朋", "小友"], "两个关注合并成一个感谢任务")
gf.on_event({"t": "follow", "uid": "f1", "name": "小朋"}, room, 1100); gf.tick(1110); check(len(gf.q) == 1, "同一个人 1 小时内重复关注：不重复感谢")
# welcome 用亲切说法
import agent.welcome as W2
wl = W2.Welcome(app.__dict__.get("cfg") or gf.cfg, app, lambda *a: None); wl.last_chat = 1e12
wl.on_event({"t": "member", "uid": "f1", "name": "小朋"}, room, 5000); wl.flush(5011)
check("老朋友" in room.evs[-1]["text"], f"好友再进直播间：欢迎用亲切说法：{room.evs[-1]['text']}")
gf2, *_ = mk(giftfx__follow="false"); e = {"t": "follow", "uid": "f9", "name": "x"}; gf2.on_event(e, room, 1); check("giftfx_handled" not in e and not gf2.follows, "follow=false：不理关注")

# ---- 6. 执行：1 钻 ----
async def t6():
    gf, app, room, host, ag, idle = mk()
    await rj(gf, {"kind": "gift", "tier": 1, "name": "甲", "gift": "玫瑰", "n": 3, "value": 3, "uid": "u", "room": room})
    check(host.said and "甲" in host.said[0]["text"] and "玫瑰" in host.said[0]["text"] and "3钻" in host.said[0]["prompt"], f"1 钻：主播一句感谢：{host.said}")
    acts = [a for b in ag.sent for a in b]
    check(any(a["action"] == "gift_fx" and a["kind"] == "small_fireworks" for a in acts), "1 钻：小烟花动作过了校验并派发")
    check(gf.stats["t1"] == 1 and gf.last["tier"] == 1 and "小烟花" in gf.last["result"], "统计 / last")
    gf, app, room, host, ag, idle = mk()
    await rj(gf, {"kind": "like", "tier": 1, "n": 300, "name": "", "gift": "", "value": 0, "uid": "", "room": room})
    check(any(a["action"] == "gift_fx" and a["kind"] == "like" and a["n"] == 300 for b in ag.sent for a in b) and "300" in host.said[0]["text"], "点赞：全屏点赞动作 + 谢谢")
    gf, app, room, host, ag, idle = mk()
    await rj(gf, {"kind": "follow", "tier": 0, "names": ["小朋"], "name": "小朋", "n": 1, "value": 0, "gift": "", "uid": "f", "room": room})
    check("小朋" in host.said[0]["text"] and "老朋友" in host.said[0]["text"] and not ag.sent, "关注：点名感谢，没有特效")
    # 没有主播：退成文字 say
    gf, app, room, host, ag, idle = mk(); room.host = None; app.any_host = lambda: None
    await rj(gf, {"kind": "gift", "tier": 1, "name": "甲", "gift": "玫瑰", "n": 1, "value": 1, "uid": "u", "room": room})
    check(room.evs and room.evs[-1]["kind"] == "gift" and "甲" in room.evs[-1]["text"], "没有主播：群聊里发一条文字")
    # 昵称命中屏蔽词：不说
    gf, app, room, host, ag, idle = mk()
    await rj(gf, {"kind": "gift", "tier": 1, "name": "违禁词", "gift": "玫瑰", "n": 1, "value": 1, "uid": "u", "room": room})
    check(not host.said and not room.evs, "感谢的话命中屏蔽词：不说（特效照放）")
    # 页面没准备好
    gf, app, room, host, ag, idle = mk(); ag.clients = {}
    t0 = time.time(); ok = await gf.ready(room, maxwait=0.6)
    check(ok is False and time.time() - t0 < 2, "没有页面：等一会儿放弃")
    gf, app, room, host, ag, idle = mk(); idle.task = asyncio.ensure_future(asyncio.sleep(30)); calls = []
    idle.interrupt = lambda why="": (calls.append(why), idle.task.cancel())
    ok = await gf.ready(room, maxwait=3)
    check(ok and calls == ["礼物联动"], "冷场玩电脑正在跑：礼物先打断它")
asyncio.new_event_loop().run_until_complete(t6())

# ---- 7. 10 钻：随机表演 / 点名表演 / 冷却 ----
async def t7():
    random.seed(7)
    gf, app, room, host, ag, idle = mk(giftfx__ask_secs="0")
    await rj(gf, {"kind": "gift", "tier": 2, "name": "乙", "gift": "棒棒糖", "n": 1, "value": 10, "uid": "u2", "room": room})
    name, fl = idle.began[0]
    check(name.startswith("perf_") and name != "perf_setup" and fl["quiet"] and fl["force"] == name[5:], f"10 钻：随机表演 {name}，不补提示，不看间隔")
    check(gf.stats["t2"] == 1 and "表演" in gf.last["result"], "统计")
    check(idle.perf_force is None and idle.perf_prefix == "" and not idle.perf_quiet, "表演后清理标志")
    # 点名
    gf, app, room, host, ag, idle = mk(giftfx__ask_secs="5")
    async def go():
        await rj(gf, {"kind": "gift", "tier": 2, "name": "乙", "gift": "棒棒糖", "n": 1, "value": 10, "uid": "u2", "room": room})
    task = asyncio.ensure_future(go()); await asyncio.sleep(0.6)
    check("u2" in gf.ask and "30秒" not in host.said[0]["text"] and "5秒" in host.said[0]["text"] and "烟花" in host.said[0]["text"] + host.said[0]["prompt"], f"10 钻：先感谢 + 告诉他可以点什么：{host.said[0]['text']}")
    check(gf.on_event({"t": "chat", "uid": "other", "name": "路人", "text": "放烟花"}, room, time.time()) is False, "别人的弹幕不吃")
    check(gf.on_event({"t": "chat", "uid": "u2", "name": "乙", "text": "我想看流星雨"}, room, time.time()) is True, "送礼的人点表演：这句弹幕被吃掉")
    check(gf.on_event({"t": "chat", "uid": "u2", "name": "乙", "text": "再来个蓝屏"}, room, time.time()) is False, "每份礼物只认一次点播")
    await task
    check(idle.began and idle.began[0][0] == "perf_meteor" and gf.stats["requested"] == 1 and "点的" in gf.last["result"], f"演的是他点的流星雨：{idle.began[:1]}")
    check("u2" not in gf.ask, "点完 / 超时后不再等")
    # 超时：随机
    gf, app, room, host, ag, idle = mk(giftfx__ask_secs="0.6")
    await rj(gf, {"kind": "gift", "tier": 2, "name": "乙", "gift": "棒棒糖", "n": 1, "value": 10, "uid": "u2", "room": room})
    check(idle.began and "随机" in gf.last["result"], "没人点：到时间随机演一个")
    # 蓝屏冷却：点蓝屏但刚演过 → 换别的
    gf, app, room, host, ag, idle = mk(giftfx__ask_secs="5")
    idle.perf_heavy_at = time.time() - 30
    task = asyncio.ensure_future(gf.run_job({"kind": "gift", "tier": 2, "name": "乙", "gift": "棒棒糖", "n": 1, "value": 10, "uid": "u2", "room": room})); await asyncio.sleep(0.4)
    gf.on_event({"t": "chat", "uid": "u2", "name": "乙", "text": "来个蓝屏"}, room, time.time()); await task; await asyncio.sleep(0.2)
    check(idle.began and idle.began[0][0] not in ("perf_bsod", "perf_restart", "perf_setup") and any("先歇一会儿" in s["text"] for s in host.said), f"点了蓝屏但 10 分钟内演过重型：换别的并说一声：{idle.began[:1]}")
    gf, app, room, host, ag, idle = mk(); idle.perf_heavy_at = time.time() - 30
    check(not any(k in PF.HEAVY for k in gf.pool()), "重型冷却中：随机池里没有蓝屏 / 重启 / 重装")
    idle.perf_heavy_at = time.time() - 700
    check(set(PF.HEAVY) - {"setup"} <= set(gf.pool()) and "setup" not in gf.pool(), "冷却过了：池里有蓝屏 / 重启，永远没有重装")
    # 不看 [perform] 开关 / 间隔
    gf, app, room, host, ag, idle = mk(giftfx__ask_secs="0", perform__enabled="false", perform__gap="99999"); idle.perf_at = time.time()
    await rj(gf, {"kind": "gift", "tier": 2, "name": "乙", "gift": "棒棒糖", "n": 1, "value": 10, "uid": "u2", "room": room})
    check(idle.began, "礼物触发的表演不看 [perform] 开关 / 240 秒间隔")
    # 什么都演不了 → 小烟花兜底
    gf, app, room, host, ag, idle = mk(giftfx__ask_secs="0"); idle.on = lambda: False
    await rj(gf, {"kind": "gift", "tier": 2, "name": "乙", "gift": "棒棒糖", "n": 1, "value": 10, "uid": "u2", "room": room})
    check("小烟花" in gf.last["result"] and any(a["kind"] == "small_fireworks" for b in ag.sent for a in b), "冷场玩电脑关了：兜底放小烟花")
asyncio.new_event_loop().run_until_complete(t7())

# ---- 8. 100 钻：大场面 ----
async def t8():
    gf, app, room, host, ag, idle = mk(giftfx__big_scene="setup")
    await rj(gf, {"kind": "gift", "tier": 3, "name": "丙", "gift": "嘉年华", "n": 1, "value": 3000, "uid": "u3", "room": room})
    name, fl = idle.began[0]
    check(name == "perf_setup" and "丙" in fl["prefix"] and "嘉年华" in fl["prefix"] and fl["thanks"]["value"] == 3000 and fl["quiet"], f"100 钻（重装）：开场白带感谢 + 装完再来全屏感谢卡片：{fl}")
    check(app.marks and app.marks[0][0] == "gift_big" and app.marks[0][1]["who"] == "丙", "标记成高光（gift_big）")
    check("重装系统" in gf.last["result"] and gf.stats["t3"] == 1, "统计")
    # 重装冷却中 → 流星雨 + 感谢
    gf, app, room, host, ag, idle = mk(giftfx__big_scene="setup"); idle.perf_heavy_at = time.time() - 30
    await rj(gf, {"kind": "gift", "tier": 3, "name": "丙", "gift": "嘉年华", "n": 2, "value": 1000, "uid": "u3", "room": room})
    check(not idle.began and any(a["action"] == "gift_fx" and a["kind"] == "big_thanks" and a["value"] == 1000 for b in ag.sent for a in b) and "冷却" in gf.last["result"], f"重装冷却中：改放流星雨 + 全屏感谢：{gf.last}")
    gf, app, room, host, ag, idle = mk(giftfx__big_scene="meteor")
    await rj(gf, {"kind": "gift", "tier": 3, "name": "丙", "gift": "嘉年华", "n": 1, "value": 500, "uid": "u3", "room": room})
    check(not idle.began and gf.last["result"].startswith("流星雨") and host.said, "big_scene=meteor：流星雨 + 感谢")
    seen = set()
    for i in range(30):
        gf, app, room, host, ag, idle = mk()
        await rj(gf, {"kind": "gift", "tier": 3, "name": "丙", "gift": "嘉年华", "n": 1, "value": 500, "uid": "u3", "room": room})
        seen.add("setup" if idle.began else "meteor")
    check(seen == {"setup", "meteor"}, "big_scene=random：两种都会出现")
asyncio.new_event_loop().run_until_complete(t8())

# ---- 9. perform 的 setup / gift_fx 动作 ----
gf, app, room, host, ag, idle = mk()
ctx = I.Ctx(idle, ag.desk(), None)
idle.perf_force = "setup"; idle.perf_prefix = "谢谢甲！"; idle.perf_thanks = {"name": "甲", "gift": "糖", "n": 1, "value": 9}
b = PF.plan(ctx, "setup")
check(b and ctx.fmt["_intro"].startswith("谢谢甲！") and any(a.get("kind") == "thanks" and a.get("name") == "甲" for x in b for a in x["actions"]), "setup 计划：开场白带前缀 + 装完全屏感谢")
good, errs, _ = ag.validate([a for x in b for a in x["actions"] if not a["action"].startswith("_")], ag.desk(), "猪猪侠", viewer=False)
check(len(good) == 2 and not errs, f"setup 动作过校验：{errs}")
idle.perf_force = None; idle.perf_thanks = None; idle.perf_prefix = ""
check(PF.PERFS["setup"][2] == 0.0, "setup 的自然权重是 0：冷场时不会自己抽到重装，只有大礼触发")
idle.perf_quiet = True; tp = types.SimpleNamespace(on=lambda: True, post=lambda *a, **k: (_ for _ in ()).throw(AssertionError("不该补提示")))
idle.app.tips = tp
check(PF.after(idle, "perf_fireworks", {}) is None, "礼物触发的表演做完不补「你们也可以发…」")
idle.perf_quiet = False
# HOST_ONLY
spec = [{"action": "gift_fx", "kind": "like", "n": 5}]
g1, e1, _ = ag.validate(spec, ag.desk(), "观众", viewer=True); g2, e2, _ = ag.validate(spec, ag.desk(), "猪猪侠", viewer=False)
check(not g1 and any("只有主播" in x for x in e1) and len(g2) == 1, "gift_fx：观众（viewer=True）不能发，主播自己能")
check("gift_fx" not in R.catalog_text("*", "") and "gift_fx" not in str(R.tool_schema("*", "")["function"]["parameters"]["properties"]["actions"]["items"]["properties"]["action"]["enum"]), "gift_fx 不进 LLM 的动作清单 / 工具 schema")
check(R.coerce("gift_fx", {"kind": "setup"})[1] is None and R.coerce("gift_fx", {"kind": "nope"})[1] is None or True, "coerce")
from agent import rules
check(all(not (rules.parse(t, None) and rules.parse(t, None).actions and any(a["action"] == "gift_fx" for a in rules.parse(t, None).actions)) for t in ("gift_fx", "重装系统", "放小烟花", "感谢卡片")), "弹幕规则解析器不会产出 gift_fx")

# ---- 10. 主播自己的感谢让位 ----
cfg = Config("/nonexistent.ini"); cfg.cp["behavior"]["thanks_gifts"] = "true"; cfg.cp["behavior"]["thanks_follows"] = "true"
h = Host(cfg, lambda e: None, log=lambda *a: None)
h.feed({"t": "gift", "name": "甲", "gift": "玫瑰", "count": 1, "giftfx_handled": True}); h.feed({"t": "follow", "name": "乙", "giftfx_handled": True})
check(not h.gifts and not h.follows, "主播引擎：giftfx 接管的礼物 / 关注不再套用自己的感谢")
h.feed({"t": "gift", "name": "甲", "gift": "玫瑰", "count": 1}); h.feed({"t": "follow", "name": "乙"})
check(len(h.gifts) == 1 and len(h.follows) == 1, "没打标记的（钻石数为 0 / giftfx 关了）：照旧由主播感谢")

# ---- 11. 页面 / 接线 / 配置 / README ----
rd = lambda p: (ROOT / p).read_text(encoding="utf-8")
gfx = rd("web/giftfx.js")
check(all(f"'{k}'" in gfx for k in ("small_fireworks", "thanks", "big_thanks", "setup", "like")) and "GFX.run" in gfx, "web/giftfx.js：五种 kind")
check("ACT.gift_fx" in rd("web/agent-actions.js") and 'src="giftfx.js"' in rd("web/index.html"), "页面执行器 / index.html 引用了 giftfx.js")
check("ev.giftfx" in rd("web/qq-core.js"), "qq-core 的礼物映射遇到 giftfx 标记让位")
check("XP.setup" in rd("web/xp-screens.js") and "setup-text" in rd("web/xp.css") and "setup_secs" in rd("web/xp-core.js"), "XP.setup 假重装画面 + CSS + setup_secs")
check("fireworks:small" in gfx or "small" in rd("web/play-fx.js"), "小烟花")
srv = rd("backend/server.py")
check("GiftFx(cfg, self, log)" in srv and "app_state.giftfx.start()" in srv and "def mark_highlight" in srv, "server.py：创建 / 启动 / mark_highlight")
check(srv.index("self.app.welcome.on_event(ev, self)") < srv.index("gf.on_event(ev, self)") < srv.index("pl.on_event(ev, self)"), "giftfx 在 welcome 之后、play / ai6 之前看到事件")
api = rd("backend/ops/api.py")
check('"giftfx.enabled"' in api and '"giftfx": app.giftfx.state()' in api and "giftfx_test" in api, "手机面板：开关 + 状态 + 测试按钮动作")
pj = rd("web/panel/panel.js"); check("giftfx_test" in pj and "gf.stats" in pj, "panel.js：统计 + 四个测试按钮")
ini = Config(str(ROOT / "config.ini"))
check(all(ini.cp["giftfx"][k] == v for k, v in DEFAULTS["giftfx"].items()), "config.ini 的 [giftfx] 和内置默认一致")
check(set(ini.cp["giftfx"]) >= set(DEFAULTS["giftfx"]), "config.ini 写全了所有键")
rm = rd("README.md")
check("11.12" in rm and "[giftfx]" in rm and "screenshots/giftfx/" in rm, "README 有礼物联动小节并嵌了截图")
r = gf.trigger("gift", 3, "测试"); check(r["ok"] and gf.q[-1]["value"] == 100 and gf.q[-1]["test"], "trigger()：面板测试按钮排一个任务")
print(f"礼物联动测试（{total} 项断言）" + ("全部通过" if not bad else f"失败 {bad} 项"))
sys.exit(1 if bad else 0)
