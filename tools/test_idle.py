# -*- coding: utf-8 -*-
"""AI 主播“冷场自己玩电脑”（idle）的离线测试：就绪条件 / 权重 / 白黑名单 / 重复间隔 / 不碰音乐 / 旁白清洗 / 打断。不联网
   python tools/test_idle.py
   端到端（真页面 + 真 LLM）见 README「冷场自己玩电脑」一节：/agent/idle?run=… 与 tools/shoot_idle.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import sys, time, types, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from agent import idle as I
from agent.core import Agent
from agent.desk import Desk
from host.config import Config

bad = 0
def check(cond, msg):
    global bad
    if not cond:
        bad += 1; print("FAIL", msg)

SNAP = {"ts": 1, "wins": [{"id": "qqchat", "app": "qqchat", "title": "群聊", "state": "normal", "x": 478, "y": 18, "w": 700, "h": 512, "z": 5}],
        "chat": {"vis": 1.0}, "start": False, "busy": False, "queue": 0, "music": {"on": True, "title": "晴天", "artist": "周杰伦"}}

class FakeHost:
    busy_until = 0
    last = {}
    said = []
    def bl_in(self, t): return "禁词" in t
    def bl_out(self, t): return "禁词" in t
    def _say(self, *a): self.said.append(a)

def mk(**kv):
    cfg = Config("/nonexistent.ini")
    cfg.cp["perform"]["enabled"] = "false"          # 冷场表演（perform.py）有自己的测试（test_perform.py），这里不让它混进随机挑选
    for k, v in kv.items():
        sec, key = k.split("__")
        cfg.cp[sec][key] = str(v)
    host = FakeHost()
    app = types.SimpleNamespace(any_host=lambda: host, jukebox=types.SimpleNamespace(current=None, queue=[], _busy=False), music=None)
    ag = Agent(cfg, app, log=lambda *a: None)
    ag.clients = {"ws": {"at": time.time()}}
    ag.snap_ws = "ws"
    ag.desk = lambda: Desk(dict(SNAP, ts=time.time()))
    idle = I.Idle(cfg, app, ag, log=lambda *a: None)
    idle.t0 -= 1000; idle.last_viewer -= 1000
    return idle, ag, app, host

# ---- 1. 就绪条件
idle, ag, app, host = mk()
now = time.time()
ok, why = idle.ready(now); check(ok, f"全部满足应就绪: {why}")
idle, *_ = mk(idle__enabled="false"); check(not idle.ready(time.time())[0], "enabled=false 不应启动")
idle, *_ = mk(agent__enabled="false"); check(not idle.ready(time.time())[0], "agent 关了 idle 也不应启动")
idle, *_ = mk(); idle.last_viewer = time.time() - 10; check(idle.ready(time.time())[1] == "观众刚说过话", "idle_after 之内不启动")
idle, *_ = mk(idle__idle_after=5); idle.last_viewer = time.time() - 10; check(idle.ready(time.time())[0], "idle_after=5 时 10s 后可启动")
idle, *_ = mk(); idle.next_at = time.time() + 30; check(idle.ready(time.time())[1] == "间隔未到", "间隔未到")
idle, *_ = mk(); idle.t0 = time.time(); check(idle.ready(time.time())[1] == "启动延迟", "startup_delay")
idle, ag, app, host = mk(); host.busy_until = time.time() + 5; check(idle.ready(time.time())[1] == "主播正在说话", "主播在说话时让路")
idle, ag, app, host = mk(idle__wait_host_quiet="false"); host.busy_until = time.time() + 5; check(idle.ready(time.time())[0], "wait_host_quiet=false")
idle, ag, app, host = mk(); app.jukebox.current = {"title": "x"}; check(idle.ready(time.time())[1] == "点歌队列忙", "点歌中不启动")
idle, ag, app, host = mk(); ag.pending["x"] = time.time(); check("正忙" in idle.ready(time.time())[1], "agent 有任务不启动")
idle, ag, app, host = mk(); SNAP["chat"]["vis"] = 0.3; r = idle.ready(time.time()); SNAP["chat"]["vis"] = 1.0
check(not r[0], "群聊被盖住不启动")
idle, ag, app, host = mk(idle__max_per_hour=2); [idle.starts.append(time.time()) for _ in range(2)]; check(idle.ready(time.time())[1] == "每小时上限", "每小时上限")
idle, *_ = mk(); idle.task = types.SimpleNamespace(done=lambda: False); check(idle.ready(time.time())[1] == "正在进行", "同时只跑一个")

# ---- 2. 聊天 / 礼物 / 指令
idle, *_ = mk(); idle.last_viewer -= 1000
idle.note_event({"t": "gift"}); check(time.time() - idle.last_viewer < 1, "礼物重置安静计时")
idle, *_ = mk(idle__gifts_reset_quiet="false"); idle.last_viewer -= 1000; idle.note_event({"t": "gift"}); check(time.time() - idle.last_viewer > 900, "gifts_reset_quiet=false")
idle, *_ = mk(); idle.note_event({"t": "chat"}); check(time.time() - idle.last_viewer < 1, "弹幕重置安静计时")

# ---- 3. 权重 / 白黑名单 / 重复间隔
w = I.parse_weights("a:3, b:1 ,c:0,bad,d:x"); check(w == {"a": 3.0, "b": 1.0, "c": 0.0, "bad": 1.0}, f"parse_weights {w}")
idle, *_ = mk(); d = Desk(dict(SNAP, ts=time.time()))
check(all(idle.allowed(n) for n in I.ACTS), "默认全部允许")
idle, *_ = mk(idle__allow_activities="calc,browse_ie"); check([n for n in I.ACTS if idle.allowed(n)] == [n for n in I.ACTS if n in ("calc", "browse_ie")], "allow_activities")
idle, *_ = mk(idle__deny_activities="qq_chat"); check(not idle.allowed("qq_chat") and idle.allowed("calc"), "deny_activities")
idle, *_ = mk(idle__weights="calc:1", idle__weights_new="", idle__repeat_gap=300)
d = Desk(dict(SNAP, ts=time.time()))
check(idle.pick(d, time.time()) == "calc", "只有一个权重时选它")
idle.recent["calc"] = time.time(); check(idle.pick(d, time.time()) is None, "repeat_gap 内不重复")
check(idle.pick(d, time.time(), only="calc") == "calc", "手动指定无视 repeat_gap")
idle, *_ = mk(idle__weights="calc:0,browse_ie:0", idle__weights_new=""); check(idle.pick(d, time.time()) is None, "权重 0 不选")
cnt = {}
idle, *_ = mk(idle__weights="calc:9,browse_ie:1", idle__weights_new="", idle__repeat_gap=0)
for _ in range(600): n = idle.pick(d, time.time()); cnt[n] = cnt.get(n, 0) + 1
check(cnt.get("calc", 0) > 4 * cnt.get("browse_ie", 1), f"权重分布 {cnt}")

# ---- 4. 不碰音乐：music_* / song_request 在派发前就被丢掉
async def t_dispatch():
    idle, ag, app, host = mk()
    sent = []
    async def sp(m): sent.append(m)
    ag.send_pages = sp
    async def go(**kw):
        sent.clear()
        task = asyncio.ensure_future(idle.dispatch([{"action": "music_next"}, {"action": "music_pause"}, {"action": "song_request", "text": "晴天"},
                                                    {"action": "calc", "expr": "1+1"}], "t", time.time() + 5))
        await asyncio.sleep(0.05)
        for k in list(idle.waiters): idle.waiters.pop(k).set_result({"ok": True})
        await task
        return [a["action"] for m in sent for a in m.get("actions", [])]
    r = await go(); check(r == ["calc"], f"默认不允许音乐控制: {r}")
    idle.cfg.cp["idle"]["allow_music_control"] = "true"
    r = await go(); check("music_next" in r, f"allow_music_control=true 才放行: {r}")
    # 只有音乐动作 → 不派发
    idle.cfg.cp["idle"]["allow_music_control"] = "false"; sent.clear()
    r = await idle.dispatch([{"action": "music_next"}], "t", time.time() + 5); check(not sent and r["ok"], "全是音乐动作 → 空操作")
asyncio.run(t_dispatch())
check(all(not a["action"].startswith("music_") for n in I.ACTS for a in sum([b.get("actions", []) for b in (I.ACTS[n](I.Ctx(mk()[0], Desk(dict(SNAP, ts=time.time())), {"title": "晴天", "artist": "周杰伦", "album": "", "pos": 1, "lyric": "故事"})) or [])], [])),
      "活动脚本本身不含 music_*（默认就不会想去切歌）")

# ---- 5. 旁白清洗 / 占位
h = FakeHost()
check(I.Idle.clean("（笑）哈哈，这首歌不错！[开心]", 28) == "哈哈，这首歌不错！", f"{I.Idle.clean('（笑）哈哈，这首歌不错！[开心]', 28)}")
check(len(I.Idle.clean("啊" * 80, 28)) <= 28, "超长截断")
check(I.Idle.clean("这是禁词啊", 28, h) == "", "黑名单")
check(I.Idle.clean(None, 28) == "", "非字符串")
idle, *_ = mk()
r = idle.fill([{"action": "notepad_type", "text": "@a"}, {"action": "notepad_type", "text": "@zz"}, {"action": "calc", "expr": "1+1"}], {"a": "你好"})
check([x["action"] for x in r] == ["notepad_type", "calc"] and r[0]["text"] == "你好", f"fill: {r}")
for n, (desc, keys) in I.DESC.items():
    check(all(k in I.T.get(n, {}) or I.T.get(n) for k in keys), f"{n} 缺模板兜底")

# ---- 5b. 和主播自己的“冷场暖场”（behavior.idle_interval）并存：旁白后顺延它；speak=false 不出声
idle, ag, app, host = mk(); host.last = {}
async def t_speak():
    rec = {"lines": []}
    idle.speak("你好呀", "开心", rec); await asyncio.sleep(0.05)
    check("idle" in host.last and len(host.said) == 1, "旁白走主播 _say 并顺延主播暖场")
    host.said.clear(); idle.cfg.cp["idle"]["speak"] = "false"; idle.speak("你好呀", "开心", rec); await asyncio.sleep(0.05)
    check(not host.said and len(rec["lines"]) == 2, "speak=false 只记录不出声")
    idle.cfg.cp["idle"]["speak"] = "true"; idle.speak("这是禁词", "开心", rec); await asyncio.sleep(0.05)
    check(not host.said, "旁白过黑名单")
asyncio.run(t_speak())

# ---- 6. 打断：取消任务并通知页面
async def t_int():
    idle, ag, app, host = mk()
    sent = []
    async def sp(m): sent.append(m)
    ag.send_pages = sp
    async def long(): await asyncio.sleep(30)
    idle.task = asyncio.ensure_future(long()); idle.cur = {"name": "calc"}
    fut = asyncio.get_running_loop().create_future(); idle.waiters["i1"] = fut
    check(idle.interrupt("t"), "有任务时打断返回 True")
    await asyncio.sleep(0.05)
    check(idle.task.cancelled() and fut.cancelled() and not idle.waiters, "任务和等待都被取消")
    check(any(m.get("t") == "agent_abort" for m in sent), "通知页面 abort")
    check(not idle.interrupt("t"), "没有任务时返回 False")
    idle.task = None
    idle.cfg.cp["idle"]["stop_on_chat"] = "false"
    idle.task = asyncio.ensure_future(long()); idle.note_event({"t": "chat"}); await asyncio.sleep(0.02)
    check(not idle.task.cancelled(), "stop_on_chat=false 不打断")
    idle.task.cancel()
asyncio.run(t_int())

# ---- 新活动（item 3）：纸牌 / 空当接龙 / 画图 / 声音设置 的动作都在注册表里，旁白模板 / DESC 齐全，默认权重生效
from agent import registry as _R
_i = mk()[0]
for _n in ("play_solitaire", "play_freecell", "paint_draw", "tweak_sound"):
    _c = I.Ctx(_i, Desk(dict(SNAP, ts=time.time())), None); _p = I.ACTS[_n](_c)
    check(_p and all(a["action"] in _R.ACTIONS or a["action"].startswith("_") for b in _p for a in b["actions"]), f"{_n} 的动作都在注册表里")
    check(_n in I.T and _n in I.DESC, f"{_n} 有模板和 DESC")
    check(set(b["say"] for b in _p if b["say"]) <= set(I.T[_n]) | set(I.DESC[_n][1]), f"{_n} 的旁白键都有模板")
check(all(I.weights_of(_i.cfg).get(n, 0) > 0 for n in ("play_solitaire", "play_freecell", "paint_draw", "tweak_sound")), "新活动默认权重 > 0（老 config.ini 没有 weights_new 也生效）")

# ---- QQ 生态活动（item 4）
_QA = ("qq_pet_care", "qq_zone_visit", "qq_show_change", "qq_files_download", "qq_shake")
for _n in _QA:
    _c = I.Ctx(_i, Desk(dict(SNAP, ts=time.time())), None); _p = I.ACTS[_n](_c)
    check(_p and all(a["action"] in _R.ACTIONS or a["action"].startswith("_") for b in _p for a in b["actions"]), f"{_n} 的动作都在注册表里")
    check(_n in I.T and _n in I.DESC, f"{_n} 有模板和 DESC")
    check(set(b["say"] for b in _p if b["say"]) <= set(I.T[_n]) | set(I.DESC[_n][1]), f"{_n} 的旁白键都有模板")
    ph = {x[1:] for b in _p for a in b["actions"] for x in a.values() if isinstance(x, str) and x.startswith("@")}
    check(ph <= set(I.T[_n]) and ph <= set(I.DESC[_n][1]), f"{_n} 的 @占位符 有模板 / DESC: {ph}")
    check(_n in I.weights_of(_i.cfg), f"{_n} 在默认 weights_new 里")
_j = mk()[0]; _j.cfg.cp["qq"]["pet"] = "false"; _j.cfg.cp["qq"]["zone"] = "false"
check(I.ACTS["qq_pet_care"](I.Ctx(_j, Desk(dict(SNAP, ts=time.time())), None)) is None, "[qq] pet=false 不演宠物")
check(I.ACTS["qq_zone_visit"](I.Ctx(_j, Desk(dict(SNAP, ts=time.time())), None)) is None, "[qq] zone=false 不逛空间")
_j.cfg.cp["qq"]["enabled"] = "false"
check(all(I.ACTS[n](I.Ctx(_j, Desk(dict(SNAP, ts=time.time())), None)) is None for n in _QA), "[qq] enabled=false 全不演")
_c = I.Ctx(_i, Desk(dict(SNAP, ts=time.time(), wins=SNAP["wins"] + [{"id": "qzone", "app": "qzone", "title": "空间", "state": "normal", "x": 1, "y": 1, "w": 5, "h": 5, "z": 6}])), None)
check(I.ACTS["qq_zone_visit"](_c) is None, "空间已经开着就不再开")

print("idle 离线测试 " + ("全部通过" if not bad else f"{bad} 项失败"))
sys.exit(1 if bad else 0)
