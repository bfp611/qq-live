# -*- coding: utf-8 -*-
"""冷场「表演」（backend/agent/perform.py，§11.10）的离线测试：每个表演的动作都过 agent 校验、台词 / 自定义台词、开关与间隔与重型冷却、
   权重、表演后的「你们也可以发『…』」提示命令确实能被规则解析、整场跑一遍（开场白 → 动作 → 提示）、被打断不补提示、手动触发。不联网
   python tools/test_perform.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import sys, time, types, asyncio, random
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from agent import idle as I, perform as PF, rules
from agent.core import Agent
from agent.desk import Desk
from agent.tips import Tips
from host.config import Config, DEFAULTS

bad = 0; total = 0
def check(c, m):
    global bad, total
    total += 1
    if not c:
        bad += 1; print("FAIL", m)

SNAP = {"ts": 1, "wins": [{"id": "qqchat", "app": "qqchat", "title": "群聊", "state": "normal", "x": 478, "y": 18, "w": 700, "h": 512, "z": 5}],
        "chat": {"vis": 1.0}, "start": False, "busy": False, "queue": 0, "music": {"on": True, "title": "晴天", "artist": "周杰伦"}}

class FakeHost:
    def __init__(s): s.busy_until = 0; s.last = {}; s.said = []
    def bl_in(s, t): return False
    def bl_out(s, t): return False
    def _say(s, kind, prio, text, emo): s.said.append((kind, text, emo))
class FakeTips:
    def __init__(s): s.posts = []
    def on(s): return True
    def post(s, text, kind, tid=None, spoken=None, emo="开心"): s.posts.append((kind, text)); return True

def mk(**kv):
    cfg = Config("/nonexistent.ini")
    for k, v in kv.items():
        sec, key = k.split("__")
        cfg.cp[sec][key] = str(v)
    host = FakeHost(); tips = FakeTips()
    app = types.SimpleNamespace(any_host=lambda: host, jukebox=types.SimpleNamespace(current=None, queue=[], _busy=False), music=None, tips=tips, rooms={}, default_room="x")
    ag = Agent(cfg, app, log=lambda *a: None)
    ag.clients = {"ws": {"at": time.time()}}; ag.snap_ws = "ws"
    ag.desk = lambda: Desk(dict(SNAP, ts=time.time()))
    idle = I.Idle(cfg, app, ag, log=lambda *a: None)
    idle.t0 -= 1000; idle.last_viewer -= 1000
    return idle, ag, app, host, tips
def ctx_of(idle): return I.Ctx(idle, idle.agent.desk(), None)

# ---- 1. 注册 + 每个表演的动作都过校验 ----
check(set(PF.NAMES) == {f"perf_{k}" for k in PF.PERFS} and all(n in I.ACTS and n in I.FIXED_LINES and n in I.T and n in I.DESC for n in PF.NAMES), "perf_* 注册进了 idle 的 ACTS / T / DESC / FIXED_LINES")
check(len(PF.PERFS) == 11 and PF.HEAVY == {"bsod", "restart", "setup"}, "11 个表演（含只给礼物联动用的重装系统），蓝屏 + 重启 + 重装是重型")
idle, ag, app, host, tips = mk()
for k in PF.PERFS:
    random.seed(k)
    beats = PF.plan(ctx_of(idle), k)
    check(beats, f"{k}：默认条件下能排出动作")
    if not beats: continue
    acts = [a for b in beats for a in b["actions"] if not a["action"].startswith("_")]
    good, errs, _ = ag.validate(acts, ag.desk(), "猪猪侠", viewer=False, trust=("shutdown",) if k == "restart" else ())
    check(len(good) == len(acts) and not errs, f"{k}：动作都能过 agent 校验：{[a['action'] for a in acts]} {errs}")
    check(beats[0]["say"] == "intro" and all(b["say"] is None for b in beats[1:]), f"{k}：只有第一拍有开场白")
    check(any(b["critical"] for b in beats), f"{k}：关键动作失败会中止")
c = ctx_of(idle); b = PF.plan(c, "bsod"); check(any(a["action"] == "bsod" for x in b for a in x["actions"]) and c.fmt["_intro"] in PF.PERFS["bsod"][0], "蓝屏：台词是内置的，动作是 bsod")
b = PF.plan(ctx_of(idle), "restart"); acts = [a for x in b for a in x["actions"]]
check({"action": "shutdown", "mode": "restart"} in acts and any(a["action"] == "_wait" and a["secs"] >= 12 for a in acts), "重启：走 XP 关机 → 重新启动，并等开关机动画放完（≥12 秒）")
check(all(a["action"] != "shutdown" or a.get("mode") == "restart" for k in PF.PERFS for x in (PF.plan(ctx_of(idle), k) or []) for a in x["actions"]), "表演里没有真关机（只有 restart 模式的页面动画）")

# ---- 2. 开关 / 间隔 / 重型冷却 / 依赖的开关 ----
idle, *_ = mk(perform__enabled="false"); check(all(PF.plan(ctx_of(idle), k) is None for k in PF.PERFS), "perform.enabled=false → 全部不选")
idle, *_ = mk(); idle.perf_at = time.time() - 100; check(PF.plan(ctx_of(idle), "fireworks") is None, "perform_gap（240 秒）内不再来下一场")
idle.perf_at = time.time() - 300; check(PF.plan(ctx_of(idle), "fireworks"), "过了 gap 可以")
idle.perf_heavy_at = time.time() - 300; check(PF.plan(ctx_of(idle), "bsod") is None and PF.plan(ctx_of(idle), "restart") is None and PF.plan(ctx_of(idle), "fireworks"), "10 分钟内最多一次蓝屏 / 重启（共用冷却），轻的不受影响")
idle.perf_heavy_at = time.time() - 700; check(PF.plan(ctx_of(idle), "bsod") and PF.plan(ctx_of(idle), "restart"), "超过 10 分钟又可以")
idle, *_ = mk(xp__bsod="false"); check(PF.plan(ctx_of(idle), "bsod") is None, "[xp] bsod=false → 不表演蓝屏")
idle, *_ = mk(xp__shutdown_screens="false"); check(PF.plan(ctx_of(idle), "restart") is None, "[xp] shutdown_screens=false → 不表演重启")
idle, *_ = mk(xp__enabled="false"); check(PF.plan(ctx_of(idle), "bsod") is None and PF.plan(ctx_of(idle), "restart") is None, "[xp] enabled=false → 蓝屏 / 重启都不演")
idle, *_ = mk(qq__shake="false"); check(PF.plan(ctx_of(idle), "shake") is None, "[qq] shake=false → 不抖")
idle, *_ = mk(qq__pet="false"); check(PF.plan(ctx_of(idle), "pet") is None, "[qq] pet=false → 不喂宠物")
idle, *_ = mk(play__enabled="false"); check(PF.plan(ctx_of(idle), "fireworks") is None and PF.plan(ctx_of(idle), "virus") is None, "[play] enabled=false → 烟花 / 熊猫烧香不演（校验不过）")
idle, *_ = mk(play__commands="false"); check(PF.plan(ctx_of(idle), "fireworks"), "[play] commands=false 只管观众口令，主播自己表演烟花不受影响")
idle, ag_, *_ = mk(); check(ag_.validate([{"action": "shutdown", "mode": "restart"}], ag_.desk(), "猪猪侠", viewer=False)[0] == [], "[agent] deny_actions 里的 shutdown 对观众 / 普通动作照旧禁用（只有表演重启例外）")
check(ag_.validate([{"action": "shutdown", "mode": "restart"}], ag_.desk(), "观众", viewer=True)[0] == [], "观众发不了关机")
idle, ag, *_ = mk(); ag.desk = lambda: Desk(dict(SNAP, ts=time.time(), wins=SNAP["wins"] + [{"id": "minesweeper", "app": "minesweeper", "title": "扫雷", "state": "normal", "x": 0, "y": 0, "w": 100, "h": 100, "z": 6}]))
check(PF.plan(ctx_of(idle), "mine") is None, "扫雷已经开着 → 不再演扫雷")
# 手动（forced）不看开关 / 间隔 / 重型冷却
idle, *_ = mk(perform__enabled="false"); idle.perf_at = idle.perf_heavy_at = time.time(); idle.perf_force = "bsod"
check(PF.plan(ctx_of(idle), "bsod") and PF.plan(ctx_of(idle), "fireworks") is None, "手动指定 bsod：不看开关 / 间隔 / 冷却；只对指定的那个生效")

# ---- 3. 台词：内置 / 自定义 ----
it = PF.parse_items("给大家表演一个蓝屏=bsod|电脑太卡了，我重启一下=restart；  乱写=nosuch | 没有等号 |再来一句蓝屏=BSOD")
check(it == {"bsod": ["给大家表演一个蓝屏", "再来一句蓝屏"], "restart": ["电脑太卡了，我重启一下"]}, f"parse_items：{it}")
idle, *_ = mk(perform__items="我自己的蓝屏台词=bsod"); c = ctx_of(idle); PF.plan(c, "bsod"); check(c.fmt["_intro"] == "我自己的蓝屏台词", "自定义台词替换内置")
c = ctx_of(idle); PF.plan(c, "fireworks"); check(c.fmt["_intro"] in PF.PERFS["fireworks"][0], "没写自定义的还用内置")
idle, *_ = mk(perform__builtin="false"); check(PF.plan(ctx_of(idle), "bsod") is None, "builtin=false 且没自定义 → 不演")
idle, *_ = mk(perform__builtin="false", perform__items="来个烟花=fireworks"); check(PF.plan(ctx_of(idle), "fireworks") and PF.plan(ctx_of(idle), "bsod") is None, "builtin=false：只演自定义里有的")
want = ["给大家表演一个蓝屏", "电脑太卡了，我重启一下", "给大家表演一个熊猫烧香", "来，放个烟花庆祝一下", "我来扫个雷给你们看", "给大家画个画", "给大家换个新壁纸", "我抖一下窗口", "给球球喂个饭"]
check(all(any(x in PF.PERFS[k][0] for k in PF.PERFS) for x in want), "需求里的 9 句开场白都在内置里")
check(all(len(t) <= 30 for v in PF.PERFS.values() for t in v[0]), "台词都不长（≤30 字）")

# ---- 4. 权重 ----
idle, *_ = mk(); w = I.weights_of(idle.cfg)
check(all(f"perf_{k}" in w and (w[f"perf_{k}"] > 0 or k == "setup") for k in PF.PERFS) and w["perf_setup"] == 0 and w["perf_bsod"] < w["perf_fireworks"], f"默认权重进了 idle：{ {k: v for k, v in w.items() if k.startswith('perf_')} }")
idle, *_ = mk(perform__weights="bsod:3, mine:0, nosuch:9"); w = I.weights_of(idle.cfg)
check(w["perf_bsod"] == 3 and w["perf_mine"] == 0 and "perf_nosuch" not in w, "perform.weights 可调，0 = 不演，不认识的忽略")
check(sum(v for k, v in I.weights_of(mk()[0].cfg).items() if k.startswith("perf_")) < 0.3 * sum(I.weights_of(mk()[0].cfg).values()), "表演总权重不到整体的 30%（不会天天表演）")
# idle 自己挑：perform 开着时，选得到表演；关了选不到
random.seed(1)
idle, *_ = mk(idle__weights="", idle__weights_new="", idle__repeat_gap="0"); d = ag.desk() if False else Desk(dict(SNAP, ts=time.time()))
got = {idle.pick(d, time.time()) for _ in range(200)}
check(any(x and x.startswith("perf_") for x in got), f"idle 随机挑得到表演：{sorted(x for x in got if x)}")
idle, *_ = mk(idle__weights="", idle__weights_new="", idle__repeat_gap="0", perform__enabled="false")
check(not any((x or "").startswith("perf_") for x in {idle.pick(d, time.time()) for _ in range(200)}), "perform.enabled=false 时一场都挑不到")

# ---- 5. 表演后的提示命令：每一条都能被规则解析成合法动作 ----
dk = Desk(dict(SNAP, ts=time.time()))
for k, v in PF.PERFS.items():
    if v[1] is None: check(k in ("restart", "setup"), f"{k}：没有对应口令的只有重启 / 重装"); continue
    cmds = [PF.tip_cmd(k, w) for w in PF.PAINT_WHAT.values()] if k == "paint" else [PF.tip_cmd(k)]
    for cmd in cmds:
        if k in ("bsod", "virus", "fireworks", "meteor", "mine", "paint", "wall", "shake", "pet"):
            it_ = rules.parse(cmd, dk)
            good, errs, _ = ag.validate(it_.actions, dk, "观众", it_, viewer=True) if it_ and it_.actions else ([], ["无法解析"], "")
            check(it_ and it_.actions and len(good) == len(it_.actions), f"{k}：提示命令『{cmd}』能被解析成合法动作 {errs}")
            check(not it_ or not it_.actions or {"bsod": "bsod", "virus": "play_fx", "fireworks": "play_fx", "meteor": "play_fx"}.get(k, it_.actions[-1]["action"]) in [a["action"] for a in it_.actions] or k in ("mine", "paint", "wall", "shake", "pet"), f"{k}：解析出的动作对得上")

# ---- 6. 整场跑一遍：开场白（主播说）→ 动作 → 提示；被打断不补；paint 留给 autoclose ----
async def flow():
    idle, ag, app, host, tips = mk(perform__gap="0")
    seen = []
    async def disp(acts, name, deadline, label_text=""):
        seen.append((name, label_text, [a["action"] for a in acts])); return {"ok": True, "results": [{"action": a["action"], "ok": True} for a in acts]}
    idle.dispatch = disp
    idle.perf_force = None
    await idle.run("perf_fireworks", True)
    rec = idle.hist[-1]
    check(rec["result"] == "完成" and rec["llm"] == "固定台词", f"整场跑完：{rec['result']} {rec['llm']}")
    check(host.said and host.said[0][0] == "idle" and host.said[0][1] in PF.PERFS["fireworks"][0], f"开场白交给主播说（TTS + 群聊）：{host.said[:1]}")
    flat = [x for s in seen for x in s[2]]
    check("play_fx" in flat and flat.index("play_fx") > flat.index("_wait"), f"先等开场白说完，再放烟花：{flat}")
    check(tips.posts == [("perform", "💡 你们也可以发『放烟花』")] and rec.get("tip"), f"做完补一句：{tips.posts}")
    check(idle.perf_at > 0 and getattr(idle, "perf_heavy_at", 0) == 0, "轻的表演只记 perf_at")
    # 蓝屏：记重型时间；之后 10 分钟内不再选
    host.said.clear(); tips.posts.clear()
    await idle.run("perf_bsod", True)
    check(idle.perf_heavy_at > 0 and PF.plan(ctx_of(idle), "restart") is None and tips.posts and "来个蓝屏" in tips.posts[0][1], "蓝屏：记了重型时间，重启也被冷却；补提示『来个蓝屏』")
    flat = [x for s in seen[-4:] for x in s[2]]
    check("bsod" in flat and flat[-1] == "_idle_cleanup", f"蓝屏动作 + 之后照常收拾：{flat}")
    # 重启没有对应口令 → 不补提示
    idle.perf_heavy_at = 0; tips.posts.clear(); await idle.run("perf_restart", True)
    check(not tips.posts and idle.hist[-1]["result"] == "完成", "重启：没有观众口令，不补提示")
    # 关键动作失败 → 不补提示
    async def fail_disp(acts, name, deadline, label_text=""):
        return {"ok": False, "results": [{"action": a["action"], "ok": False, "note": "x"} for a in acts if not a["action"].startswith("_")] + [{"action": "_wait", "ok": True}]}
    idle.dispatch = fail_disp; tips.posts.clear(); await idle.run("perf_fireworks", True)
    check(idle.hist[-1]["result"].startswith("关键动作失败") and not tips.posts, "动作失败 → 不补提示")
    # 被打断
    idle.dispatch = disp
    async def slow(acts, name, deadline, label_text=""):
        await asyncio.sleep(5); return {"ok": True, "results": []}
    idle.dispatch = slow; tips.posts.clear()
    t = asyncio.ensure_future(idle.run("perf_fireworks", True)); await asyncio.sleep(0.2); t.cancel()
    try: await t
    except asyncio.CancelledError: pass
    check(idle.hist[-1]["result"] == "被打断" and not tips.posts, "被打断 → 不补提示")
    # perf_tip=false
    idle2, ag2, app2, host2, tips2 = mk(perform__gap="0", perform__tip="false"); idle2.dispatch = disp
    await idle2.run("perf_fireworks", True); check(not tips2.posts, "[perform] tip=false → 不补提示")
    # 画图：autoclose 开着 → 不立刻收拾（交给 autoclose）；关了就照旧收拾
    seen.clear(); idle3, ag3, app3, host3, tips3 = mk(perform__gap="0"); idle3.dispatch = disp
    await idle3.run("perf_paint", True)
    flat = [x for s in seen for x in s[2]]
    check("paint_draw" in flat and "_idle_cleanup" not in flat, f"画画：autoclose 开着 → 画完不立刻收拾，留给自动关窗：{flat}")
    seen.clear(); idle4, *_ = mk(perform__gap="0", autoclose__enabled="false"); idle4.dispatch = disp
    await idle4.run("perf_paint", True); flat = [x for s in seen for x in s[2]]
    check(flat[-1] == "_idle_cleanup", "autoclose 关了 → 照旧收拾")
    check("💡 你们也可以发『画个" in tips3.posts[0][1] and tips3.posts[0][1].endswith("』"), f"画画后的提示带上画的东西：{tips3.posts}")
asyncio.run(flow())

# ---- 7. 手动触发：Tips.perform_now ----
async def manual():
    idle, ag, app, host, tips_ = mk(perform__enabled="false")
    tp = Tips(idle.cfg, app, ag, idle, lambda *a: None)
    r = tp.perform_now("fireworks")
    check(r["ok"] and r["id"] == "fireworks" and idle.task is not None, f"手动表演（开关关着也行）：{r}")
    await asyncio.sleep(0.05); idle.task.cancel()
    try: await idle.task
    except BaseException: pass
    ag.clients = {"ws": {"at": time.time()}}; ag.snap_ws = "ws"
    r = tp.perform_now("nosuch"); check(not r["ok"] and "没有这个表演" in r["error"], "不认识的表演名")
    idle.task = types.SimpleNamespace(done=lambda: False); r = tp.perform_now(); check(not r["ok"] and "忙" in r["error"], "正在忙：不叠加"); idle.task = None
    ag.clients = {}; r = tp.perform_now(); check(not r["ok"] and "页面" in r["error"], "没页面不开")
    ag.clients = {"ws": {"at": time.time()}}; ag.snap_ws = "ws"
    idle.cfg.cp["xp"]["bsod"] = "false"; r = tp.perform_now("bsod"); check(not r["ok"] and "做不了" in r["error"], "蓝屏开关关着：手动也不行（页面会拒绝的事不发）")
    ag.clients = {"ws": {"at": time.time()}}; ag.snap_ws = "ws"
    r = tp.perform_now(); check(r["ok"], f"不指定：按权重挑一个现在能做的：{r.get('id')}"); await asyncio.sleep(0.05); idle.task.cancel()
    try: await idle.task
    except BaseException: pass
asyncio.run(manual())

# ---- 8. 配置一致 ----
d = DEFAULTS["perform"]
check(d["enabled"] == "true" and float(d["heavy_gap"]) >= 600 and float(d["gap"]) >= 120 and d["tip"] == "true", "默认值：开、重型冷却 ≥ 10 分钟、间隔 ≥ 2 分钟、补提示")
ci = Config(str(ROOT / "config.ini"))
if "perform" in ci.cp:
    miss = [k for k in ci.cp["perform"] if k not in d]; check(not miss, f"config.ini [perform] 里有代码不认识的键：{miss}")
    for k, v in d.items():
        if k in ci.cp["perform"]: check(ci.cp["perform"][k] == v, f"config.ini [perform] {k} = {ci.cp['perform'][k]!r} ≠ 默认 {v!r}")
else:
    print("（config.ini 里还没有 [perform]，跳过一致性检查）")
print(f"冷场表演测试（{total} 项断言）" + ("全部通过" if not bad else f" 有 {bad} 项失败"))
sys.exit(1 if bad else 0)
