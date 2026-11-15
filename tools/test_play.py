# -*- coding: utf-8 -*-
"""观众互动（[play]）的离线测试：积分 / 反刷屏 / 等级 / 存档 / 投票（解析、计票、平票、没人投、执行）/ 切歌投票（门槛、窗口、换歌、冷却、群主直切）/ 配置与接线一致。不联网、不开浏览器。
   python tools/test_play.py
   页面级（真浏览器）验证见 tools/shoot_play.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import asyncio, json, re, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from host.config import Config, DEFAULTS
from play import engine as E, store as S
from agent import registry as R, rules, idle as I

bad = 0
def check(cond, msg):
    global bad
    if not cond:
        bad += 1; print("FAIL", msg)

class Room:
    def __init__(self, rid="r1"):
        self.rid, self.evs, self.last = rid, [], {}
    def _broadcast(self, ev): self.evs.append(ev)
    def of(self, t, k=None): return [e for e in self.evs if e.get("t") == t and (k is None or e.get("k") == k)]

class FakeAgent:
    def __init__(self): self.said, self.ran = [], []
    def on(self): return True
    def say(self, room, text, emo="开心", kind="agent"): self.said.append(text)
    async def simulate(self, text, **kw): self.ran.append(text); return {"actions": [{"action": "x"}]}

def mk(**kv):
    cfg = Config("/nonexistent.ini")
    cfg.cp["play"]["data_file"] = ""
    for k, v in kv.items(): cfg.cp["play"][k] = str(v)
    app = types.SimpleNamespace(agent=FakeAgent(), music=None, jukebox=None)
    return E.Play(cfg, app, log=lambda *a: None), app

def chat(p, room, uid, text, name=None, now=None):
    ev = {"t": "chat", "uid": uid, "name": name or uid, "text": text}
    return p.on_event(ev, room)

# ---- 1. 等级 / 图标 ----
check(E.level_of(0, 10) == 0 and E.level_of(10, 10) == 1 and E.level_of(160, 10) == 4 and E.level_of(2560, 10) == 16 and E.level_of(40960, 10) == 64, "等级 = floor(sqrt(分/base))")
check(E.level_glyphs(3) == "⭐⭐⭐" and E.level_glyphs(4) == "🌙" and E.level_glyphs(5) == "🌙⭐" and E.level_glyphs(16) == "☀️" and E.level_glyphs(64) == "👑" and E.level_glyphs(85) == "👑☀️🌙⭐", "4 星 = 月亮，4 月 = 太阳，4 日 = 皇冠")
check(E.level_of(10**9, 10) == 255, "等级封顶 255")

# ---- 2. 积分 + 反刷屏 ----
p, app = mk(chat_gap=0, max_per_min=5, dup_secs=30, daily_cap=0); r = Room()
for t in ["你好呀", "大家好", "哈哈哈", "前排沙发", "主播好", "晚上好", "在吗"]: chat(p, r, "u1", t)
check(p.store.user("r1", "u1")["pts"] == 5 if "r1" in p.store.scopes else p.st("r1").user("r1", "u1")["pts"] == 5, "每分钟最多 5 次得分")
check(p.stats["ignored_cap"] >= 2, "超出每分钟上限的被记为忽略")
p, app = mk(chat_gap=0, max_per_min=50); r = Room()
for t in ["你好呀", "你好呀", "你好 呀", "大家好", "你好呀"]: chat(p, r, "u1", t)
check(p.st("r1").user("r1", "u1")["pts"] == 2 and p.stats["ignored_dup"] == 3, f"重复句子（含夹空格、间隔后重复）不算分: {p.st('r1').user('r1','u1')['pts']} {p.stats}")
p, app = mk(chat_gap=0, max_per_min=50, chat_min_len=2); r = Room()
chat(p, r, "u1", "1"); chat(p, r, "u1", "好")
check(p.st("r1").user("r1", "u1")["pts"] == 0, "太短的话（chat_min_len）不算分")
p, app = mk(chat_gap=10, max_per_min=50); r = Room()
chat(p, r, "u1", "第一句话"); chat(p, r, "u1", "第二句话")
check(p.st("r1").user("r1", "u1")["pts"] == 1, "chat_gap 内第二句不算")
p, app = mk(chat_gap=0, max_per_min=50, daily_cap=3); r = Room()
for i in range(8): chat(p, r, "u1", "不同的话%d" % i)
check(p.st("r1").user("r1", "u1")["pts"] == 3, "daily_cap 当天封顶")
# 礼物 / 点赞 / 关注 / 进场
p, app = mk(); r = Room()
p.on_event({"t": "gift", "uid": "g", "name": "g", "gift": "x", "count": 2, "value": 100}, r)
check(p.st("r1").user("r1", "g")["pts"] == 110, "礼物分 = 数量 × (基础 + 价值×0.5)")
p.on_event({"t": "gift", "uid": "g2", "name": "g2", "gift": "x", "count": 100, "value": 9999}, r)
check(p.st("r1").user("r1", "g2")["pts"] == 5000, "gift_max_pts 封顶")
p.on_event({"t": "like", "uid": "l", "name": "l", "count": 25}, r); p.on_event({"t": "like", "uid": "l", "name": "l", "count": 5}, r)
check(p.st("r1").user("r1", "l")["pts"] == 3, "点赞每 10 个 +1（余数累计）")
p.on_event({"t": "follow", "uid": "f", "name": "f"}, r); p.on_event({"t": "follow", "uid": "f", "name": "f"}, r)
check(p.st("r1").user("r1", "f")["pts"] == 20, "关注每天只算一次")
p, app = mk(enter_points=3); r = Room()
p.on_event({"t": "member", "uid": "m", "name": "m"}, r); p.on_event({"t": "member", "uid": "m", "name": "m"}, r)
check(p.st("r1").user("r1", "m")["pts"] == 3, "进场分每天一次")
p, app = mk(points="false", chat_gap=0); r = Room(); chat(p, r, "u1", "你好呀你好")
check(not p.st("r1").scope("r1")["users"] or p.st("r1").user("r1", "u1")["pts"] == 0, "points=false 不加分")
p, app = mk(enabled="false"); r = Room(); check(chat(p, r, "u1", "我的积分") is False and not r.evs, "enabled=false 什么都不做")

# ---- 3. 等级事件 / 升级消息 / 查积分 ----
p, app = mk(chat_gap=0, max_per_min=0, daily_cap=0, level_base=2); r = Room()
for i in range(8): chat(p, r, "u1", "说话说话%d" % i, name="小明")
lv = r.of("play", "lv"); check(lv and lv[0]["lv"] == 1 and lv[-1]["lv"] == 2, f"等级变了才推 lv 事件: {[e['lv'] for e in lv]}")
check(any("升级" in e["text"] for e in r.of("sys")), "升级写群消息")
check(all(e.get("play") for e in r.of("sys")), "互动系统消息带 play 标记（demo 页面回灌过滤用）")
n0 = len(r.evs); consumed = chat(p, r, "u1", "我的积分", name="小明")
check(consumed and any("【积分】" in e["text"] and "总榜第 1 名" in e["text"] for e in r.of("sys")), "“我的积分”被吃掉并回复")
check(p.snapshot("r1")["lv"].get("u1") == 2, "snap 里有等级")

# ---- 4. 存档 ----
d = Path(tempfile.mkdtemp()); f = d / "play.json"
p, app = mk(chat_gap=0, data_file=str(f)); r = Room("r9"); p.on_event({"t": "gift", "uid": "a", "name": "阿一", "gift": "x", "count": 1, "value": 10}, r)
p.on_event({"t": "gift", "uid": "d", "name": "demo人", "gift": "x", "count": 1, "value": 10}, Room("demo"))
p.stop(); data = json.loads(f.read_text(encoding="utf-8"))
check("r9" in data["scopes"] and "demo" not in data["scopes"], "存档只有真实房间，demo 不落盘")
p2, _ = mk(data_file=str(f)); check(p2.st("r9").user("r9", "a")["pts"] == 10, "重启后积分还在")
check(p2.rank("r9", "day")[0]["name"] == "阿一" and p2.rank("r9", "total")[0]["pts"] == 10, "日榜 / 总榜")
(d / "bad.json").write_text("{坏", encoding="utf-8"); p3, _ = mk(data_file=str(d / "bad.json")); check(p3.st("x").scope("x")["users"] == {}, "坏存档不崩，改名备份后重新开始")
st = S.PlayStore(None, 2)
st.add("r", "u", "u", 5, now=time.time() - 5 * 86400); st.add("r", "u", "u", 7)
st.prune(); check(len(st.scope("r")["days"]) == 1 and st.scope("r")["users"]["u"]["pts"] == 12, "prune 只清过期日榜，总分不动")
rk = S.PlayStore(None); [rk.add("r", f"u{i}", f"n{i}", 10 - i) for i in range(5)]
check([x["uid"] for x in rk.rank("r", "total", 3)] == ["u0", "u1", "u2"] and rk.position("r", "u3") == 4, "排名 / 名次")

# ---- 5. 投票 ----
check(E.parse_options("下一步干啥: 1 玩红警 2 换壁纸 3 扫雷") == ("下一步干啥", ["玩红警", "换壁纸", "扫雷"]), "解析编号选项")
check(E.parse_options("1 玩红警2 2 换壁纸 3 扫雷") == ("", ["玩红警2", "换壁纸", "扫雷"]), "选项里带数字不会被拆")
check(E.parse_options("玩红警|换壁纸|扫雷") == ("", ["玩红警", "换壁纸", "扫雷"]) and E.parse_options("下一步: 红警 壁纸")[1] == ["红警", "壁纸"], "没编号也能解析（| 或空格）")
check(E.VOTE_REPLY.match("2") and E.VOTE_REPLY.match("投3") and E.VOTE_REPLY.match("选 1 号") and not E.VOTE_REPLY.match("12") and not E.VOTE_REPLY.match("我要2个苹果"), "投票回复的格式")

async def t_vote():
    global bad
    p, app = mk(vote_secs=5, vote_execute="true", chat_gap=0); r = Room("r1"); r.last["room"] = {"anchor": "群主甲"}
    # 谁能发起
    check(chat(p, r, "u1", "投票 玩红警 换壁纸") is False and p.vote is None, "vote_who=anchor：路人发起无效（当普通聊天）")
    check(chat(p, r, "z", "投票 下一步干啥: 1 玩红警 2 换壁纸 3 扫雷", name="群主甲") is True and p.vote is not None, "群主发起")
    check(len(p.vote.labels) == 3 and p.vote.title == "下一步干啥", "标题 / 选项")
    check(p.start_vote(r, "又来", ["a", "b"])["ok"] is False, "同时只能有一个投票")
    for uid, t in [("a", "1"), ("b", "2"), ("c", "2"), ("d", "2"), ("e", "投3"), ("f", "9"), ("g", "你好呀")]: chat(p, r, uid, t)
    check(p.vote.counts() == [1, 3, 1], f"计票（9 超范围、闲聊不计）: {p.vote.counts()}")
    check(chat(p, r, "a", "2") is True and p.vote.counts() == [0, 4, 1], "改票")
    p.cfg.cp["play"]["vote_change"] = "false"; chat(p, r, "a", "1"); check(p.vote.counts() == [0, 4, 1], "vote_change=false 不能改票"); p.cfg.cp["play"]["vote_change"] = "true"
    check(p.st("r1").user("r1", "b")["pts"] == 2, "投票 +2 分")
    p.vote.t0 -= 100; await p.tick(); await asyncio.sleep(2.2)
    v = p.vote.snap(); check(v["state"] == "done" and v["winner"] == 2, f"到时间结算: {v['state']} {v['winner']}")
    check(app.agent.ran == ["换壁纸"], f"赢家交给 agent 执行: {app.agent.ran}")
    check(any("胜出" in e["text"] for e in r.of("sys")) and any("换壁纸" in s for s in app.agent.said), "群里 / AI 播报结果")
    check(len(r.of("play", "vote")) >= 2, "实时推 vote 事件")
    # 平票 / 没人投
    p.vote = None; app.agent.ran.clear()
    p.start_vote(r, "平票", ["甲", "乙"], 5); chat(p, r, "a", "1"); chat(p, r, "b", "2"); p.vote.t0 -= 100; await p.tick(); await asyncio.sleep(2.2)
    check(p.vote.winner in (1, 2) and "平票" in p.vote.note and len(app.agent.ran) == 1, "平票抽签")
    p.vote = None; app.agent.ran.clear(); p.cfg.cp["play"]["vote_tie"] = "first"
    p.start_vote(r, "平票2", ["甲", "乙"], 5); chat(p, r, "a", "1"); chat(p, r, "b", "2"); p.vote.t0 -= 100; await p.tick(); await asyncio.sleep(2.2)
    check(p.vote.winner == 1, "vote_tie=first 取靠前")
    p.vote = None; app.agent.ran.clear()
    p.start_vote(r, "没人", ["甲", "乙"], 5); p.vote.t0 -= 100; await p.tick(); await asyncio.sleep(0.3)
    check(p.vote.state == "done" and p.vote.winner == 0 and not app.agent.ran, "vote_nobody=skip：没人投票作废")
    p.vote = None; p.cfg.cp["play"]["vote_nobody"] = "random"
    p.start_vote(r, "没人2", ["甲", "乙"], 5); p.vote.t0 -= 100; await p.tick(); await asyncio.sleep(2.2)
    check(p.vote.winner in (1, 2) and len(app.agent.ran) == 1, "vote_nobody=random：随机抽一个执行")
    p.vote = None; app.agent.ran.clear(); p.cfg.cp["play"]["vote_execute"] = "false"
    p.start_vote(r, "不执行", ["甲", "乙"], 5); chat(p, r, "a", "1"); p.vote.t0 -= 100; await p.tick(); await asyncio.sleep(2.2)
    check(not app.agent.ran, "vote_execute=false 只出结果不执行")
    # 取消 / agent 动作 / 关闭
    p.vote = None; p.cfg.cp["play"]["vote_execute"] = "true"
    check(p.agent_action({"action": "vote_start", "title": "AI 发起", "options": "玩红警|换壁纸|扫雷", "secs": 20}, {}, r, "猪猪侠") is True and p.vote.secs == 20, "agent 动作 vote_start")
    chat(p, r, "z", "取消投票", name="群主甲"); check(p.vote.state == "cancelled", "群主取消投票")
    p.vote = None; p.cfg.cp["play"]["vote"] = "false"; check(p.start_vote(r, "x", ["a", "b"])["ok"] is False and chat(p, r, "u", "1") is False, "vote=false 关闭")
    p.cfg.cp["play"]["vote"] = "true"; p.vote = None
    check(p.start_vote(r, "x", ["a"])["ok"] is False, "少于 2 个选项被拒")
    check(len(p.start_vote(r, "x", [str(i) for i in range(20)])["vote"]["opts"]) == 6, "最多 vote_max_options 个选项")
asyncio.run(t_vote())

# ---- 6. 切歌投票 ----
async def t_skip():
    p, app = mk(skip_count=3, skip_window=90, skip_cooldown=20, chat_gap=0)
    app.music = types.SimpleNamespace(state={"on": True, "key": "song1", "title": "晴天", "artist": "周杰伦"})
    r = Room("r1")
    check(chat(p, r, "a", "切歌") is True and chat(p, r, "a", "切歌") is True and p.skip_snap("r1")["have"] == 1, "同一个人只算一票")
    check(chat(p, r, "b", "别切歌") is False and chat(p, r, "b", "我不要切歌") is False, "带否定的不算票")
    check(chat(p, r, "b", "这歌不好听") is True and p.skip_snap("r1")["have"] == 2, "skip_words 里的词都算")
    check(chat(p, r, "b", "下一首是什么歌呢我想听听看看啊") is False, "太长的句子不算票")
    chat(p, r, "c", "切歌"); await asyncio.sleep(0.1)
    check(app.agent.ran == ["切歌"] and p.stats["skips"] == 1, f"凑够 3 票：切歌（走 agent 的 music_next）{app.agent.ran}")
    check(any(e["skip"]["done"] for e in r.of("play", "skip")) and any("切歌" in e["text"] for e in r.of("sys")), "推进度事件 + 群消息")
    chat(p, r, "d", "切歌"); check(p.skip_snap("r1")["have"] == 0, "冷却期内不再受理")
    p.skip["cool_until"] = 0; app.music.state["key"] = "song2"; chat(p, r, "d", "切歌"); chat(p, r, "e", "切歌"); check(p.skip_snap("r1")["have"] == 2, "换歌后票清零重新算")
    app.music.state["key"] = "song3"; chat(p, r, "d", "切歌"); p.skip["t0"] -= 200; p.skip["voters"]["d"] -= 200; chat(p, r, "e", "切歌"); check(p.skip_snap("r1")["have"] == 1, "超过 skip_window 的票作废")
    # percent 模式
    p2, app2 = mk(skip_mode="percent", skip_percent=50, skip_min=2, chat_gap=0); app2.music = app.music; r2 = Room("r1")
    for u in "abcdef": chat(p2, r2, u, "你好吗朋友们")      # 6 个活跃观众
    check(p2.skip_need("r1") == 3, f"percent：6 人活跃 × 50% = 3: {p2.skip_need('r1')}")
    p3, _ = mk(skip_mode="percent", skip_percent=10, skip_min=2); p3.active = {"r1": {"a": time.time(), "b": time.time()}}; check(p3.skip_need("r1") == 2, "skip_min 兜底")
    p3.active["r1"]["old"] = time.time() - 1000; check(p3.active_count("r1") == 2, "只数 skip_active_secs 内活跃的")
    # 群主直切 / 没歌放行 / 关闭
    p4, app4 = mk(chat_gap=0); app4.music = types.SimpleNamespace(state={"on": True, "key": "k", "title": "t", "artist": "a"}); r4 = Room("r1"); r4.last["room"] = {"anchor": "群主甲"}
    chat(p4, r4, "z", "切歌", name="群主甲"); await asyncio.sleep(0.1); check(app4.agent.ran == ["切歌"], "群主说切歌直接切")
    p5, app5 = mk(chat_gap=0); app5.music = types.SimpleNamespace(state={"on": False}); check(chat(p5, Room(), "a", "切歌") is False, "没在放歌：放行给原来的 agent 规则")
    p6, app6 = mk(skip_vote="false", chat_gap=0); app6.music = app.music; check(chat(p6, Room(), "a", "切歌") is False, "skip_vote=false：恢复原来的（交给 agent）")
asyncio.run(t_skip())

# ---- 6b. Agent 动作 / 口令 / 闲时活动 ----
for t, rule in (("放烟花", "fx_fireworks"), ("来个流星雨", "fx_meteor"), ("下表情雨", "fx_emoji"), ("熊猫烧香", "fx_virus"), ("看排行榜", "rank_open"), ("看看总榜", "rank_open")):
    it = rules.parse(t); check(it is not None and it.rule == rule, f"口令 {t} → {rule}: {it and it.rule}")
for t in ("电脑中毒了", "烟花好看吗", "排行榜在哪", "我中毒了吗"): check(rules.parse(t) is None or rules.parse(t).rule not in ("fx_virus", "fx_fireworks", "rank_open"), f"不误触 {t}")
for a in ("vote_start", "vote_end", "play_fx", "rank_open"): check(a in R.ACTIONS and a in R.PLAY_ACTIONS, f"registry 有 {a}")
check(R.ACTIONS["vote_start"]["backend"] and R.ACTIONS["vote_end"]["backend"] and R.ACTIONS["play_fx"]["danger"] >= 1, "vote_* 是后端动作；play_fx 危险级≥1")
check(R.find_app("积分榜") == "rank" and R.find_app("投票窗口") == "vote", "APPS rank/vote")
async def t_agent():
    p, app = mk(chat_gap=0); r = Room("r1"); r.last["room"] = {"anchor": "群主甲"}
    check(p.agent_action({"action": "vote_start", "options": "玩红警|换壁纸|扫雷"}, {}, r, "路人乙") is False and p.vote is None, "路人（LLM 误判）不能发起投票")
    check(p.agent_action({"action": "vote_start", "options": "玩红警|换壁纸|扫雷", "secs": 10}, {}, r, "群主甲") and p.vote is not None, "群主/主播能发起")
    check(p.vote_open() and not p.idle_vote_ok(), "投票中 idle_vote_ok=False")
    p.agent_action({"action": "vote_end"}, {}, r, "x"); await asyncio.sleep(0.2)
    p2, app2 = mk(chat_gap=0, vote_idle="true", vote_idle_min_viewers=2); r2 = Room("r1")
    check(not p2.idle_vote_ok(), "没活跃观众：闲时不投票")
    chat(p2, r2, "a", "你好呀大家"); chat(p2, r2, "b", "晚上好啊主播")
    check(p2.idle_vote_ok(), "有 2 个活跃观众且 vote_idle=true：闲时可以投票")
    p3, _ = mk(chat_gap=0, vote_idle="false"); chat(p3, Room(), "a", "你好呀大家"); chat(p3, Room(), "b", "晚上好啊主播"); check(not p3.idle_vote_ok(), "vote_idle=false：不会自动投票")
    ia = types.SimpleNamespace(app=app2, cfg=app2.agent and p2.cfg)
    ctx = I.Ctx(types.SimpleNamespace(cfg=p2.cfg, app=app2, agent=app2.agent, sites=lambda: [], agent_site_ok=lambda x: True), None, None)
    app2.play = p2
    beats = I.ACTS["play_vote"](ctx); check(beats and beats[0]["actions"][0]["action"] == "vote_start" and "|" in beats[0]["actions"][0]["options"], "闲时活动 play_vote 计划")
    g, errs, _ = types.SimpleNamespace(), None, None
    p2.cfg.cp["play"]["vote_idle"] = "false"; check(I.ACTS["play_vote"](ctx) is None, "vote_idle=false 时活动不可选")
    p2.cfg.cp["play"]["vote_idle"] = "true"; chat(p2, r2, "a", "我要攒积分哦哈哈", now=None)
    beats = I.ACTS["play_rank"](ctx); check(beats and beats[0]["actions"][1] == {"action": "rank_open", "by": "day"}, "闲时活动 play_rank 计划（榜上有人）")
    check(I.ACTS["play_rank"](I.Ctx(types.SimpleNamespace(cfg=p2.cfg, app=types.SimpleNamespace(play=mk()[0]), agent=None, sites=lambda: [], agent_site_ok=lambda x: True), None, None)) is None, "榜上没人：不看排行榜")
check("play_vote" in I.weights_of(Config("/nonexistent.ini")) and "play_rank" in I.weights_of(Config("/nonexistent.ini")), "weights_new 默认带上新活动")
asyncio.run(t_agent())

# ---- 7. 配置 / 接线一致 ----
import configparser
ini = configparser.ConfigParser(interpolation=None); ini.read(ROOT / "config.ini", encoding="utf-8")
py = DEFAULTS["play"]
check("play" in ini and set(ini["play"]) == set(py), f"config.ini [play] ↔ config.py 键一致: {set(py) ^ set(ini['play'] if 'play' in ini else [])}")
for k, v in py.items():
    if "play" in ini and k in ini["play"]: check(ini["play"][k].strip() == v, f"默认值一致 ini/py: {k}")
js = (ROOT / "web/play-core.js").read_text(encoding="utf-8")
m = re.search(r"const D = \{(.*?)\};", js, re.S); jsd = {}
for k, v in re.findall(r"(\w+):\s*('(?:[^'\\]|\\.)*'|[-\d.]+|true|false)", m.group(1)): jsd[k] = v[1:-1] if v.startswith("'") else v
check(set(jsd) == set(py), f"play-core.js 默认值键一致: {set(py) ^ set(jsd)}")
for k, v in py.items():
    jv = jsd.get(k); same = str(jv).lower() == v.lower() or (jv and re.fullmatch(r"-?[\d.]+", jv) and re.fullmatch(r"-?[\d.]+", v) and float(jv) == float(v))
    check(same, f"默认值一致 py/js: {k} {v!r} vs {jv!r}")
srv = (ROOT / "backend/server.py").read_text(encoding="utf-8")
for s in ('"play": dict(self.cfg.cp["play"])', "/play/rank.json", "on_event(ev, self)", "/play/vote"): check(s in srv, f"server.py 有 {s}")
idx = (ROOT / "web/index.html").read_text(encoding="utf-8")
for f in ("play-core.js", "play-ui.js", "play-fx.js"): check(f'<script src="{f}">' in idx and (ROOT / "web" / f).exists(), f"{f} 存在并被 index.html 引入")
print("观众互动离线测试 " + ("全部通过" if not bad else f"{bad} 项失败"))
sys.exit(1 if bad else 0)
