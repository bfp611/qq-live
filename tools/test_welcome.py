# -*- coding: utf-8 -*-
"""进场接待（backend/agent/welcome.py，§11.11）的离线测试：新 / 老 / 老朋友的说法、第几次按不同日子数、没用过的口令才推荐、10 秒合并、同一人 30 分钟一次、
   每分钟限句、文字 / 安静才念、不打断冷场玩电脑、主播和 ai6 让位、开关、昵称安全、接线与配置一致。不联网
   python tools/test_welcome.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import re, sys, time, types, asyncio, random, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from agent import welcome as W, tips as T
from host.config import Config, DEFAULTS
from host.engine import Host
from play import store as S

bad = 0; total = 0
def check(c, m):
    global bad, total
    total += 1
    if not c:
        bad += 1; print("FAIL", m)

class FHost:
    def __init__(s): s.busy_until = 0; s.last = {}; s.said = []; s.name = "猪猪侠"
    def bl_in(s, t): return "违禁" in t
    def bl_out(s, t): return "违禁" in t
    def _say(s, kind, prio, text, emo, to="", **k): s.said.append((kind, text, to))
class FRoom:
    def __init__(s, rid="889"): s.rid = rid; s.clients = {1}; s.evs = []; s.last = {"room": {"anchor": "大主播"}}; s.host = None
    def _broadcast(s, ev): s.evs.append(ev)
class FIdle:
    def __init__(s): s.task = None; s.interrupts = 0; s.cmds = 0
    def interrupt(s, *a): s.interrupts += 1
    def note_command(s): s.cmds += 1
class FTips:
    busy = False
    def __init__(s): s.ok = None
    def available(s, tid): return s.ok is None or tid in s.ok
class FPlay:
    def __init__(s): s.store = S.PlayStore(None); s.mem = S.PlayStore(None)
    def st(s, scope): return s.mem if scope == "demo" else s.store

def mk(**kv):
    cfg = Config("/nonexistent.ini")
    for k, v in kv.items():
        sec, key = k.split("__"); cfg.cp[sec][key] = str(v)
    host = FHost(); room = FRoom(); room.host = host
    app = types.SimpleNamespace(any_host=lambda: host, play=FPlay(), tips=FTips(), idle=FIdle(), ops=None, rooms={"889": room})
    w = W.Welcome(cfg, app, lambda *a: None); w.last_chat = 1e12     # 默认「刚有人聊过」= 不安静 = 只发文字
    return w, app, room, host
def mem(uid, name): return {"t": "member", "uid": uid, "name": name}
def chat(uid, name, text): return {"t": "chat", "uid": uid, "name": name, "text": text}
def run(co): return asyncio.new_event_loop().run_until_complete(co)

# ---- 1. 新观众：欢迎 + 推荐一个没用过的口令 ----
random.seed(1)
w, app, room, host = mk()
e = mem("u1", "小明"); w.on_event(e, room, 1000)
check(e.get("welcome_handled") and e.get("ai6_greeted"), "进场事件被打上「已接待」标记（主播 / ai6 让位）")
check(not room.evs and len(w.pending) == 1, "进场后先攒着（等合并窗口），不立刻发")
check(w.tick(1005) is None and not room.evs, "5 秒：还在合并窗口里")
r = w.tick(1011)
check(r and len(room.evs) == 1, "10 秒后发出一句")
ev = room.evs[0]
check(ev["t"] == "say" and ev["kind"] == "welcome" and ev["audio"] == "" and "小明" in ev["text"] and "欢迎" in ev["text"], f"新观众：文字 say 事件：{ev['text']}")
m = re.search(r"发『(.+?)』试试", ev["text"]); check(m and m.group(1) in [T.BY_ID[i][1] for i in W.DEFAULT_CMDS.split(",")], f"推荐了一个口令：{m and m.group(1)}")
check(not host.said, "默认不出声（刚有人聊过天 / 没满足安静条件之外，文字版）" if False else "文字版没有走 TTS 的 _say")

# ---- 2. 第几次按不同日子数；老观众说法；同一天不重复计数 ----
w, app, room, host = mk()
day = lambda d: time.mktime(time.strptime(f"2026-11-{d:02d} 12:00:00", "%Y-%m-%d %H:%M:%S"))
w.on_event(mem("u2", "阿花"), room, day(10)); w.flush(day(10) + 11)
u = app.play.store.scope("889")["users"]["u2"]
check(u["visits"] == 1 and "欢迎" in room.evs[-1]["text"], "第 1 天：新观众")
w.on_event(mem("u2", "阿花"), room, day(10) + 7200); w.flush(day(10) + 7300)       # 同一天、超过 30 分钟：再欢迎，但次数不加
check(u["visits"] == 1, "同一天再进：次数不增加")
w.on_event(mem("u2", "阿花"), room, day(12)); w.flush(day(12) + 11)
check(u["visits"] == 2 and "第 2 次" in room.evs[-1]["text"] and "阿花" in room.evs[-1]["text"], f"第 2 个不同日子：老观众「第 2 次」：{room.evs[-1]['text']}")
w.on_event(mem("u2", "阿花"), room, day(15)); w.flush(day(15) + 11)
check(u["visits"] == 3 and "第 3 次" in room.evs[-1]["text"], "第 3 个不同日子：第 3 次")
# 积分存档里原来就有的老用户（没有 visits 字段）
w, app, room, host = mk()
old = app.play.store.user("889", "u3", "老张"); old["last"] = int(day(1)); old["pts"] = 50
w.on_event(mem("u3", "老张"), room, day(5)); w.flush(day(5) + 11)
check(app.play.store.scope("889")["users"]["u3"]["visits"] == 2 and "第 2 次" in room.evs[-1]["text"], "积分存档里已有的老用户：按老观众算（第 2 次）")
# 老朋友
w, app, room, host = mk()
app.play.store.user("889", "u4", "小朋")["friend"] = True
w.on_event(mem("u4", "小朋"), room, day(5)); w.flush(day(5) + 11)
check("老朋友" in room.evs[-1]["text"] and "小朋" in room.evs[-1]["text"], f"老朋友（关注过）换亲切说法：{room.evs[-1]['text']}")

# ---- 3. 只推荐没用过的口令 ----
w, app, room, host = mk(welcome__cmds="bsod,fw")
w.on_event(chat("u5", "小A", "来个蓝屏"), room, 1000)
check(app.play.store.scope("889")["users"]["u5"]["cmds"] == {"bsod": 1}, "用过的口令记在用户记录里")
w.on_event(chat("u5", "小A", "我今天心情真的很好呀，想看看直播间有什么好玩的，听说烟花特别好看是吗"), room, 1001)
check("fw" not in app.play.store.scope("889")["users"]["u5"]["cmds"], "长闲聊里带关键词不算用过口令")
for _ in range(6):
    w.last_w.clear(); room.evs.clear()
    w.on_event(mem("u5", "小A"), room, 2000); w.flush(2011)
    check("放烟花" in room.evs[-1]["text"] and "来个蓝屏" not in room.evs[-1]["text"], "bsod 用过 → 只推荐放烟花")
w.on_event(chat("u5", "小A", "放烟花"), room, 3000); w.last_w.clear(); room.evs.clear()
w.on_event(mem("u5", "小A"), room, 4000); w.flush(4011)
check("发『" not in room.evs[-1]["text"] and "小A" in room.evs[-1]["text"], f"全都用过了 → 只欢迎不推荐：{room.evs[-1]['text']}")
w, app, room, host = mk(welcome__recommend="false")
w.on_event(mem("u6", "小B"), room, 1000); w.flush(1011)
check("发『" not in room.evs[-1]["text"], "recommend=false：只欢迎")
w, app, room, host = mk(welcome__cmds="bsod,fw"); app.tips.ok = {"bsod"}
for i in range(5):
    w.on_event(mem(f"v{i}", f"观{i}"), room, 1000 + i * 5000); w.flush(1011 + i * 5000)
check(all("来个蓝屏" in e["text"] for e in room.evs), "现在不能用的口令（Tips.available=False）不推荐")
w, app, room, host = mk(welcome__cmds="bsod,fw,meteor,virus"); seen = set()
for i in range(40):
    w.on_event(mem("same", "同一人"), room, 1000 + i * 100000); w.flush(1011 + i * 100000)
    seen.add(re.search(r"发『(.+?)』", room.evs[-1]["text"]).group(1))
check(len(seen) >= 3, f"同一个人连续进来，推荐的口令会轮换：{seen}")

# ---- 4. 合并 / 单人 30 分钟 / 每分钟限句 ----
w, app, room, host = mk()
for i, n in enumerate(["甲", "乙", "丙", "丁", "戊"]):
    w.on_event(mem(f"m{i}", n), room, 1000 + i * 1.5)
check(w.tick(1009) is None, "窗口内（< 10 秒）不发")
w.tick(1011)
check(len(room.evs) == 1 and "甲、乙 等 5 位" in room.evs[0]["text"], f"5 个人合并成一句：{room.evs[0]['text']}")
w, app, room, host = mk()
w.on_event(mem("p1", "甲"), room, 1000); w.on_event(mem("p2", "乙"), room, 1002); w.tick(1011)
check(len(room.evs) == 1 and "欢迎 甲、乙" in room.evs[0]["text"] and "等" not in room.evs[0]["text"].split("～")[0], f"2 个人：欢迎 甲、乙：{room.evs[0]['text']}")
w, app, room, host = mk()
w.on_event(mem("g1", "甲"), room, 1000); w.tick(1011)
n = len(room.evs); w.on_event(mem("g1", "甲"), room, 1100); w.tick(1200)
check(len(room.evs) == n and w.stats["skip_gap"] == 1, "同一个人 30 分钟内再进：不重复欢迎")
w.on_event(mem("g1", "甲"), room, 1011 + 1801); w.tick(1011 + 1830)
check(len(room.evs) == n + 1, "超过 30 分钟：再欢迎一次")
w, app, room, host = mk(welcome__max_per_min=3)
for i in range(6):
    w.on_event(mem(f"r{i}", f"人{i}"), room, 1000 + i * 12); w.tick(1011 + i * 12)
check(len(room.evs) == 3 and w.stats["skip_rate"] >= 1, f"每分钟最多 3 句：{len(room.evs)}")
w, app, room, host = mk(welcome__merge_secs=3)
w.on_event(mem("x1", "甲"), room, 1000); check(w.tick(1002) is None and w.tick(1004), "merge_secs 可配")

# ---- 5. 文字 / TTS ----
w, app, room, host = mk()
w.last_chat = 1000
w.on_event(mem("q1", "甲"), room, 1010); w.tick(1021)
check(not host.said and room.evs[-1]["audio"] == "", "刚有人发过弹幕（不安静）：只发文字")
async def t5():
    w, app, room, host = mk(); w.last_chat = 0
    now = time.time()
    w.on_event(mem("q2", "乙"), room, now - 20); w.tick(now - 9)
    await asyncio.sleep(0.2)
    check(host.said and host.said[0][0] == "welcome" and "乙" in host.said[0][1] and not room.evs, f"房间安静：走 TTS（主播 _say）：{host.said}")
    check(w.stats["spoken"] == 1, "spoken 计数")
    w, app, room, host = mk(); host.busy_until = time.time() + 30
    w.on_event(mem("q3", "丙"), room, now - 20); w.tick(now - 9)
    await asyncio.sleep(0.1)
    check(not host.said and room.evs, "主播正在说话：不插嘴，只发文字")
    w, app, room, host = mk(welcome__speak="never")
    w.on_event(mem("q4", "丁"), room, now - 20); w.tick(now - 9); await asyncio.sleep(0.1)
    check(not host.said and room.evs, "speak=never：永远只发文字")
    w, app, room, host = mk(welcome__speak="always"); w.last_chat = now
    w.on_event(mem("q5", "戊"), room, now - 20); w.tick(now - 9); await asyncio.sleep(0.1)
    check(host.said, "speak=always：念")
    w, app, room, host = mk(); app.idle.task = types.SimpleNamespace(done=lambda: False)
    w.on_event(mem("q6", "己"), room, now - 20); w.tick(now - 9); await asyncio.sleep(0.1)
    check(not host.said and room.evs, "猪猪侠正在玩电脑：不念")
run(t5())

# ---- 6. 不打断冷场玩电脑；开关；自己 / 主播不欢迎；昵称安全 ----
w, app, room, host = mk()
for i in range(10): w.on_event(mem(f"z{i}", f"人{i}"), room, 1000 + i)
w.tick(1020)
check(app.idle.interrupts == 0 and app.idle.cmds == 0, "进场 / 欢迎从不调用 idle.interrupt / note_command")
w, app, room, host = mk(welcome__enabled="false")
e = mem("o1", "甲"); w.on_event(e, room, 1000); w.tick(1100)
check(not room.evs and not w.pending and "welcome_handled" not in e, "enabled=false：什么都不做，也不抢主播 / ai6 的欢迎")
w, app, room, host = mk()
w.on_event(mem("s1", "猪猪侠"), room, 1000); w.on_event(mem("s2", "大主播"), room, 1000)
check(not w.pending and w.stats["skip_self"] == 2, "主播自己 / 主播本人进场不欢迎")
w, app, room, host = mk()
w.on_event(mem("b1", "违禁词先生"), room, 1000); w.tick(1011)
check("违禁" not in room.evs[-1]["text"] and "这位朋友" in room.evs[-1]["text"], "昵称命中屏蔽词 → 改叫「这位朋友」")
w, app, room, host = mk()
w.on_event(mem("c1", "😀小🌸明✨✨✨✨✨✨超长昵称超长昵称"), room, 1000); w.tick(1011)
check(re.search(r"欢迎 小明超长昵称超长 ", room.evs[-1]["text"]) or "小明" in room.evs[-1]["text"], f"昵称清洗：{room.evs[-1]['text']}")
w, app, room, host = mk(welcome__tpl_new="嘿 {n}！", welcome__tail="来试试『{cmd}』")
w.on_event(mem("t1", "甲"), room, 1000); w.tick(1011)
check(room.evs[-1]["text"].startswith("嘿 甲！来试试『"), f"自定义台词 / tail：{room.evs[-1]['text']}")
w, app, room, host = mk()
w.on_event({"t": "member", "name": "没uid"}, room, 1000); w.tick(1011)
check(room.evs and "没uid" in room.evs[-1]["text"], "没有 uid 的进场用昵称当 key")
dm = FRoom("demo"); w, app, room, host = mk()
w.on_event(mem("d1", "演示"), dm, 1000); w.tick(1011)
check(dm.evs and "d1" in app.play.mem.scope("demo")["users"] and "d1" not in app.play.store.scope("demo")["users"], "demo 房间的记录只放内存（不落盘）")

# ---- 7. 主播 / ai6 让位（真类）----
cfg = Config("/nonexistent.ini"); cfg.cp["behavior"]["welcome_enters"] = "true"
h = Host(cfg, lambda e: None, log=lambda *a: None)
h.feed({"t": "member", "uid": "1", "name": "甲", "ai6_greeted": True}); h.feed({"t": "member", "uid": "2", "name": "乙"})
check(len(h.enters) == 1, "主播引擎：打了标记的进场不再套用普通欢迎词")
src = (ROOT / "backend/ai6/plus.py").read_text(encoding="utf-8")
check('ev.get("welcome_handled")' in src.split("def _maybe_greet")[1][:300], "ai6 的老观众欢迎：welcome_handled 时让位")

# ---- 8. 接线 / 配置 / 面板 / README ----
srv = (ROOT / "backend/server.py").read_text(encoding="utf-8")
check("Welcome(cfg, self, log)" in srv and "self.app.welcome.on_event(ev, self)" in srv and "app_state.welcome.start()" in srv, "server.py：创建 / 事件入口 / 启动")
check(srv.index("self.app.idle.note_event(ev)") < srv.index("self.app.welcome.on_event(ev, self)") < srv.index("pl.on_event(ev, self)"), "welcome 在 play / ai6 之前看到事件")
api = (ROOT / "backend/ops/api.py").read_text(encoding="utf-8")
check('"welcome.enabled"' in api and '"welcome": app.welcome.state()' in api, "手机面板：开关 + 状态")
check("wl.stats" in (ROOT / "web/panel/panel.js").read_text(encoding="utf-8"), "panel.js 显示接待统计")
ini = Config(str(ROOT / "config.ini"))
check(all(ini.cp["welcome"][k] == v for k, v in DEFAULTS["welcome"].items() if v), "config.ini 的 [welcome] 和内置默认一致")
check(set(ini.cp["welcome"]) >= set(DEFAULTS["welcome"]), "config.ini 写全了所有键")
check(set(W.TPL) <= set(DEFAULTS["welcome"]) and all(c in T.BY_ID for c in DEFAULTS["welcome"]["cmds"].split(",")), "默认口令都是 Tips 里的内置口令")
check(set(W.KW) >= set(T.BY_ID) , "每个内置口令都有「用过」关键词：缺 " + str(set(T.BY_ID) - set(W.KW)))
for cid in W.KW:
    if cid in T.BY_ID and cid not in ("note", "calc", "ra2away", "outfit", "screen", "memory", "next", "paint"):
        cmd = T.BY_ID[cid][1]
        check(W.KWC[cid].search(cmd), f"口令『{cmd}』能被「用过」关键词认出")
rd = (ROOT / "README.md").read_text(encoding="utf-8")
check("11.11" in rd and "[welcome]" in rd and "screenshots/welcome/" in rd, "README 有进场接待小节并嵌了截图")
print(f"进场接待测试（{total} 项断言）" + ("全部通过" if not bad else f"失败 {bad} 项"))
sys.exit(1 if bad else 0)
