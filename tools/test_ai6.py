# -*- coding: utf-8 -*-
"""AI 加强包（[ai_plus]）离线测试：观众记忆（隐私 / 上限 / 忘记 / 存档）、多音色解析与路由、歌曲点评、小游戏、画面点评、配置一致。
   python tools/test_ai6.py        页面级（真浏览器）验证见 tools/shoot_ai6.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import asyncio, json, re, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from host.config import Config, DEFAULTS
from host import tts as T
from ai6 import store as S, plus as P

bad = 0
def check(cond, msg):
    global bad
    if not cond:
        bad += 1; print("FAIL", msg)

class Room:
    def __init__(self, rid="r1"): self.rid, self.evs, self.host = rid, [], None
    def _broadcast(self, ev): self.evs.append(ev)
    def of(self, t): return [e for e in self.evs if e.get("t") == t]

class FakeHost:
    def __init__(self): self.said = []; self.plus = None
    def speak(self, kind, prompt, fallback="", emotion="平静", role="", to="", prio=55, keep_history=False, wait=6.0, max_chars=0):
        self.said.append({"kind": kind, "prompt": prompt, "text": fallback, "role": role, "to": to}); return fallback

def mkcfg(**kv):
    cfg = Config("/nonexistent.ini"); cfg.cp["ai_plus"]["memory_file"] = ""
    for k, v in kv.items(): cfg.cp["ai_plus"][k] = str(v)
    return cfg

def mk(**kv):
    cfg = mkcfg(**kv); app = types.SimpleNamespace(play=None, music=None, jukebox=None, agent=None)
    h = FakeHost(); app.any_host = lambda: h
    p = P.Plus(cfg, app, log=lambda *a: None); return p, app, h

# ---- 1. 记忆：存取 / 隐私 / 上限 ----
m = S.MemoryStore(None, max_viewers=50, keep_days=30, topics=3, topic_chars=12, songs=2)
r, nv, before = m.touch("u1", "小明", 1000, 1800); check(r["visits"] == 1 and nv and before is None, "第一次来 visits=1")
r, nv, before = m.touch("u1", "小明", 1100, 1800); check(r["visits"] == 1 and not nv, "半小时内再来不算新一次")
r, nv, before = m.touch("u1", "小明", 5000, 1800); check(r["visits"] == 2 and nv and before["visits"] == 1, "隔了很久再来 = 第 2 次")
for t in ["今天心情很不错呀", "我手机号13812345678", "加我微信abc123", "这首歌真好听啊", "主页 https://x.com/y", "哈", "我家住在北京朝阳区", "我的密码是123", "第四句话聊聊天气"]: m.chat("u1", t)
rec = m.get("u1"); check(all("1381" not in x and "微信" not in x and "http" not in x and "密码" not in x and "住" not in x for x in rec["topics"]), f"敏感内容没进话题: {rec['topics']}")
check(len(rec["topics"]) <= 3 and all(len(x) <= 12 for x in rec["topics"]), "话题条数 / 长度有上限")
check(rec["topics"][-1] == "第四句话聊聊天气", "最近的话题在最后")
for s_ in ["十年", "十年", "晴天", "稻香"]: m.song("u1", s_)
check(m.get("u1")["songs"] == ["晴天", "稻香"], f"点歌最多记 2 首、去重: {m.get('u1')['songs']}")
for g, n in [("玫瑰花", 2), ("玫瑰花", 1), ("火箭", 1)]: m.gift("u1", g, n)
check(m.get("u1")["gifts"] == {"玫瑰花": 3, "火箭": 1} and m.get("u1")["gift_n"] == 4, "礼物统计")
check("u1" not in json.dumps(m.v) and len(next(iter(m.v))) == 16, "存档里没有原始 uid（只有哈希）")
for i in range(80): m.touch(f"x{i}", f"观众{i}", 6000 + i, 1800)
check(len(m.v) <= 50, f"人数上限 max_viewers: {len(m.v)}")
check(m.get("x79") is not None and m.get("x0") is None, "超限时最久没来的先丢")
m2 = S.MemoryStore(None, keep_days=30); m2.touch("old", "老古董", 1000); m2.touch("new", "新人", 1000 + 40 * 86400, 1800); m2.prune(1000 + 41 * 86400); check(m2.get("old") is None and m2.get("new"), "keep_days 过期清理")
m3 = S.MemoryStore(None); m3.touch("a", "甲", 1); m3.touch("b", "乙", 1); check(m3.forget(uid="a", optout=True) == 1 and m3.get("a") is None, "forget 删除")
check(m3.touch("a", "甲", 5)[0] is None, "忘记后不再记录（optout）"); m3.remember("a"); check(m3.touch("a", "甲", 9)[0] is not None, "记住我 → 恢复")
check(m3.forget(name="乙") == 1 and m3.forget(all_=True) == 1 and not m3.v, "按昵称删 / 清空")
d = Path(tempfile.mkdtemp()); f = d / "mem.json"
m4 = S.MemoryStore(f); m4.touch("z", "存档君", 100); m4.chat("z", "这是一句话题内容"); m4.save(force=True)
m5 = S.MemoryStore(f); check(m5.get("z") and m5.get("z")["topics"] == ["这是一句话题内容"] and m5.salt == m4.salt, "存档读回（盐也保留）")
f.write_text("{坏的", encoding="utf-8"); m6 = S.MemoryStore(f, log=lambda *a: None); check(len(m6.v) == 0 and (d / "mem.json.bad").exists(), "坏存档改名 .bad 重新开始")
check(S.clean_nick("<b>x\x00y</b>") == "bxyb" or "<" not in S.clean_nick("<b>x</b>"), "昵称清理控制字符 / 尖括号")
check("上次" in S.facts({"visits": 3, "last": time.time() - 90000, "songs": ["十年"], "gifts": {"火箭": 1}, "topics": ["聊天气"]}, 4, "🌙") and "《十年》" in S.facts({"visits": 3, "last": 1, "songs": ["十年"], "gifts": {}, "topics": []}), "facts 文本")

# ---- 2. Plus：老观众欢迎 / 回复上下文 / 口令 ----
async def t_plus():
    p, app, h = mk(memory_session_gap=1); r = Room(); r.host = h
    ev = lambda t, **k: {"t": t, "uid": "u9", "name": "老王", **k}
    p.on_event(ev("chat", text="今天听了十年真好听呀"), r); p.on_event(ev("gift", gift="玫瑰花", count=2), r)
    e1 = ev("member"); p.on_event(e1, r); check(not e1.get("ai6_greeted") and not h.said, "第一次来：不当老观众欢迎（交给普通欢迎）")
    p.mem.v[p.mem.key("u9")]["last"] -= 100; p.mem.v[p.mem.key("u9")]["visits"] = 2
    e2 = ev("member"); p.on_event(e2, r); await asyncio.sleep(0.2)
    check(e2.get("ai6_greeted") and h.said and h.said[0]["kind"] == "greet" and "老王" in h.said[0]["text"], f"回头客：单独欢迎并带细节: {h.said[:1]}")
    check("玫瑰花" in h.said[0]["text"] or "十年" in h.said[0]["text"], "欢迎词里有记得的细节")
    check("玫瑰花" in h.said[0]["prompt"] or "十年" in h.said[0]["prompt"], "LLM 提示词里带了记忆事实")
    n = len(h.said); e3 = ev("member"); p.mem.v[p.mem.key("u9")]["last"] -= 100; p.on_event(e3, r); check(len(h.said) == n, "greet_gap 内不重复欢迎")
    ctx = p.reply_context(["u9"]); check("老王" in ctx and "【" in ctx, "回复上下文含老观众记忆")
    check(p.reply_context(["nobody"]) == "" and mk(memory_in_replies="false")[0].reply_context(["u9"]) == "", "陌生人 / 关了开关：没有上下文")
    check(p.on_event(ev("chat", text="你还记得我吗"), r) is True and r.of("sys") and "记得" in r.of("sys")[-1]["text"], "「你还记得我吗」")
    check(p.on_event(ev("chat", text="忘记我"), r) is True and p.mem.get("u9") is None, "「忘记我」立刻删除")
    check(p.on_event(ev("chat", text="聊点别的内容吧大家"), r) is False and p.mem.get("u9") is None, "忘记后聊天不再被记")
    check(p.on_event(ev("chat", text="记住我"), r) is True and p.mem.get("u9") is not None, "「记住我」恢复")
    p2, _, h2 = mk(memory="false"); check(p2.mem is None and p2.on_event(ev("chat", text="忘记我"), Room()) is False, "memory=false：整块关闭，口令也不吃")
    p3, _, _ = mk(enabled="false"); check(p3.on_event(ev("chat", text="忘记我"), Room()) is False, "ai_plus enabled=false：全关")
    check(P.greet_template("老王", {"songs": ["十年"]}).startswith("老王你又来啦，上次你点了《十年》"), "模板：上次点了《十年》")
asyncio.run(t_plus())

# ---- 3. 多音色 ----
v = T.parse_voices("narrator=edge:zh-CN-YunjianNeural:+0%:+0Hz,ghost=fish:ref123~zh-CN-XiaoxiaoNeural,bad=zzz:1,=edge:x,k=default")
check(set(v) == {"narrator", "ghost", "k"} and v["ghost"]["fb"] == "zh-CN-XiaoxiaoNeural" and v["narrator"]["args"][0] == "zh-CN-YunjianNeural", f"voices 解析: {sorted(v)}")
cfg = mkcfg(voices="narrator=edge:V1:+3%:-2Hz,vip=fish:REF9~V2,sys=default"); cfg.cp["tts"]["backend"] = "fish"
oc = T.role_cfg(cfg, "narrator"); check(oc.s("tts", "voice") == "V1" and oc.s("tts", "rate") == "+3%" and oc.s("tts", "backend") == "edge" and cfg.s("tts", "backend") == "fish", "edge 角色覆盖音色 / 语速，不影响全局")
oc = T.role_cfg(cfg, "vip"); check(oc.s("tts", "backend") == "fish" and oc.s("tts", "fish_reference_id") == "REF9" and oc.s("tts", "voice") == "V2" and oc.s("tts", "fallback") == "edge", "fish 角色：参考音色 + 回退 edge 音色")
check(T.role_cfg(cfg, "host") is None and T.role_cfg(cfg, "sys") is None and T.role_cfg(cfg, "nope") is None and T.role_cfg(cfg, "") is None, "host / default / 没配的角色 → 用全局音色")
calls = []
orig = dict(T.BACKENDS); T.BACKENDS["edge"] = lambda c, t, e: (calls.append(("edge", c.s("tts", "voice"), c.s("tts", "rate"))) or (b"E", "audio/mpeg"))
T.BACKENDS["fish"] = lambda c, t, e: (calls.append(("fish", c.s("tts", "fish_reference_id"))) or (b"F" * 40, "audio/mpeg"))
T._edge = T.BACKENDS["edge"]
cfg.cp["tts"]["voice"] = "GLOBAL"; cfg.cp["tts"]["backend"] = "edge"; T._fish_key = lambda: "k"
T.synth(cfg, "你好", "平静", "narrator"); T.synth(cfg, "你好", "平静"); T.synth(cfg, "你好", "平静", "host")
check(calls == [("edge", "V1", "+3%"), ("edge", "GLOBAL", "+6%"), ("edge", "GLOBAL", "+6%")], f"synth 按角色选音色: {calls}")
calls.clear(); cfg.cp["tts"]["backend"] = "fish"; T._FISH.ok(); T.synth(cfg, "你好", "平静", "vip"); T.synth(cfg, "你好", "平静"); check(calls == [("fish", "REF9"), ("fish", cfg.s("tts", "fish_reference_id"))], f"fish 角色用自己的参考音色: {calls}")
# 断路器：fish 角色失败 → 回退 edge 音色；冷却中直接走 edge，不再打 fish
def bad_fish(c, t, e):
    calls.append(("fish-bad",)); err = RuntimeError("402 no quota"); err.fish_status = 402; raise err
T.BACKENDS["fish"] = bad_fish; calls.clear(); T._FISH.ok()
out = T.synth(cfg, "你好", "平静", "vip"); check(out[0] == b"E" and calls[0] == ("fish-bad",) and calls[1][0] == "edge" and calls[1][1] == "V2", f"fish 角色失败 → 回退到该角色的 edge 音色: {calls}")
calls.clear(); T.synth(cfg, "你好", "平静", "vip"); check(calls and calls[0][0] == "edge" and not any(c[0] == "fish-bad" for c in calls), "断路器冷却中：角色也不再请求 fish（保护免费额度）")
T._FISH.ok(); cfg.cp["tts"]["backend"] = "none"; check(T.synth(cfg, "你好", "平静", "narrator") == (None, None), "全局 tts=none：角色也不出声")
T.BACKENDS.update(orig)
p, _, _ = mk(); check(p.role_for("vote") == "narrator" and p.role_for("game") == "quiz" and p.role_for("screen") == "" and p.role_for("reply") == "", "voice_ctx：场合 → 角色")
check(p.role_name("quiz") == "出题官" and p.role_name("zzz") == "zzz", "voice_names 显示名")

# ---- 4. 歌曲点评 ----
async def t_song():
    now = 1_000_000.0
    st = {"on": True, "playing": True, "key": "k1", "title": "十年", "artist": "陈奕迅", "album": "黑白灰", "duration": 240, "pos": 0, "ts": now * 1000,
          "lines": [[20, "第一句", 26], [26, "第二句", 50], [50, "间奏很长", 70], [70, "最后一句", 76]]}
    p, app, h = mk(song_comment_chance=1, song_comment_delay=3, song_comment_wait=20, song_comment_gap=100)
    app.play = types.SimpleNamespace(test_song=st, on=lambda: False)
    check(p.safe_window(st, 5, now) and p.safe_window(st, 5, now + 10), "前奏（第一句之前、够说完）可以说")
    check(not p.safe_window(st, 5, now + 17), "第一句快开始（前奏剩不够）不说")
    check(not p.safe_window(st, 5, now + 22) and not p.safe_window(st, 5, now + 24), "唱词中间不说")
    check(not p.safe_window(st, 5, now + 52) and p.safe_window(st, 5, now + 56), "长间奏：先等 4 秒再说，下一句前留够时间才说")
    check(not p.safe_window(st, 5, now + 66) and p.safe_window(st, 5, now + 90), "间奏末尾不说；歌词唱完可以说")
    check(p.safe_window({**st, "lines": []}, 5, now + 30), "没有歌词：随时可以说")
    p.song_tick(now)                                               # 第一次看到这首歌：决定要不要点评
    check(p.song["want"] and p.song["pending"], "chance=1：想点评")
    p.song_tick(now + 1); check(not h.said, "刚换歌 delay 秒内不说")
    st["ts"] = now * 1000; p.song_tick(now + 4); await asyncio.sleep(0.2)
    check(len(h.said) == 1 and h.said[0]["kind"] == "songc" and "十年" in h.said[0]["text"] and "陈奕迅" in h.said[0]["prompt"] and "不要念歌词" in h.said[0]["prompt"], f"点评：kind=songc、提示词带歌手并禁止念歌词/编造: {h.said[:1]}")
    check("绝不要编造" in h.said[0]["prompt"] and "第一句" in h.said[0]["prompt"], "提示词要求不编造；带了歌词开头只供感受情绪")
    p.song_tick(now + 5); p.song_tick(now + 8); await asyncio.sleep(0.1); check(len(h.said) == 1, "同一首歌只点评一次")
    st2 = {**st, "key": "k2", "title": "晴天", "ts": (now + 20) * 1000}; app.play.test_song = st2
    p.song_tick(now + 20); check(not p.song["want"], "song_comment_gap 内换歌：不点评（限频）")
    p.last_song_comment = 0; st3 = {**st, "key": "k3", "title": "稻香", "lines": [[5, "歌词", 60]], "ts": (now + 400) * 1000}; app.play.test_song = st3
    p.song_tick(now + 400); p.song_tick(now + 404); check(p.song["pending"] and len(h.said) == 1, "唱词中间：等空档，不抢着说")
    p.song_tick(now + 400 + 3 + 20 + 3); check(not p.song["pending"] and len(h.said) == 1, "等了 song_comment_wait 还没空档：放弃这首")
    p0, app0, h0 = mk(song_comment_chance=0); app0.play = types.SimpleNamespace(test_song=st, on=lambda: False); p0.song_tick(now); check(not p0.song["want"], "chance=0：从不主动点评")
    p5, app5, h5 = mk(song_comment="false"); app5.play = app0.play; p5.song_tick(now); check(not p5.song["pending"], "song_comment=false：关闭")
    p6, app6, h6 = mk(song_comment_chance=1); app6.play = types.SimpleNamespace(test_song={**st, "duration": 30}, on=lambda: False); p6.song_tick(now); check(not p6.song["want"], "太短的歌（< song_comment_min_secs）不点评")
    p7, app7, h7 = mk(song_comment_chance=1); app7.play = types.SimpleNamespace(test_song=st, on=lambda: False); app7.jukebox = types.SimpleNamespace(current=types.SimpleNamespace(uid="u1")); p7.song_tick(now)
    check(not p7.song["want"], "观众点的歌默认不再点评（song_comment_requests=false）")
    ok, msg = p.agent_action({"action": "song_comment"}, {}, Room(), "路人"); await asyncio.sleep(0.1); check(ok and len(h.said) == 2 and "路人" in h.said[1]["prompt"], "口令/动作 song_comment：强制点评一次")
    ok, msg = p.agent_action({"action": "song_comment"}, {}, Room(), "路人"); check(not ok, "20 秒内再要：拒绝（防刷）")
    app.play.test_song = {"on": False}; ok, msg = mk()[0].agent_action({"action": "song_comment"}, {}, Room(), "路人"); check(not ok, "没在放歌：说明原因")
asyncio.run(t_song())

# ---- 小游戏 ----
from ai6 import games as G
class FakeAgent:
    def __init__(self): self.said = []
    def say(self, room, text, emotion="平静", kind="agent", role=""): self.said.append({"kind": kind, "text": text})
class FakePlay:
    def __init__(self): self.pts = {}; self.test_song = None
    def on(self): return True
    def award_bonus(self, room, uid, name, pts, kind="bonus"): self.pts[uid] = self.pts.get(uid, 0) + pts; return pts
def mkg(**kv):
    p, app, h = mk(**kv); app.agent = FakeAgent(); app.play = FakePlay(); return p, app, h
def chat(p, room, uid, text, name=None):
    ev = {"t": "chat", "uid": uid, "name": name or ("观众" + uid), "text": text}; return p.on_event(ev, room)
def gev(room): return [e["game"] for e in room.evs if e.get("k") == "game"]

w, bf = G.load_idioms(G.DATA / "idioms.tsv")
check(len(w) > 20000 and w["一心一意"] == ["yi", "xin", "yi", "yi"], f"成语库：{len(w)} 条，拼音去声调")
check(G.toneless("lǜ") == "lu" and G.toneless("nǚ") == "nu" and G.toneless("zhōng") == "zhong", "去声调（含 ü）")
check(len(G.load_tsv(G.DATA / "riddles.tsv")) >= 30 and len(G.load_tsv(G.DATA / "songs.tsv")) >= 30, "题库条数")
check((G.DATA / "IDIOM_LICENSE.txt").read_text(encoding="utf-8").count("MIT") >= 2, "成语数据的 MIT 署名文件在")

p, app, h = mkg(game_cooldown=0, idiom_rounds=3, game_points=5, game_win_points=10, game_timeout=45)
room = Room(); room.last = {"room": {"anchor": "主播甲"}}
ok, msg = p.games.start("成语接龙", room, "路人"); check(ok, msg)
g = p.games.cur; first = g["prompt"]; check(len(first) == 4 and g["need"] == w[first][-1], f"开局成语：{first}")
check(not p.games.start("idiom", room, "路人")[0], "已有一场：拒绝再开")
check(gev(room) and gev(room)[-1]["kind"] == "idiom" and gev(room)[-1]["state"] == "open", "推送 play/game 快照")
check(any(x["kind"] == "game" and "成语接龙" in x["text"] for x in app.agent.said), "主播开场白 kind=game")
check(not chat(p, room, "1", "今天天气不错呀"), "普通聊天不被游戏吃掉")
check(not chat(p, room, "1", "天天向上哟"), "不是成语的四字不吃")
bad_w = next(x for x in w if w[x][0] != g["need"] and x not in g["used"])
check(chat(p, room, "1", bad_w) and g["round"] == 0 and any("接不上" in e.get("text", "") for e in room.of("sys")), "接不上：吃掉并提示，不加分")
check(chat(p, room, "1", first), "开局成语被吃掉（算用过）")
def good(g):
    return next(x for x in bf[g["need"]] if x not in g["used"] and len(bf.get(w[x][-1], [])) >= 8)
a1 = good(g); check(chat(p, room, "1", a1) and app.play.pts.get("1") == 5 and g["round"] == 1, f"接对 +5：{a1}")
check(g["log"][-1]["name"] == p.cfg.s("host", "name"), "主播接了一个")
check(w[g["prompt"]][0] == w[a1][-1], "主播接的是合法接龙")
check(not (chat(p, room, "2", a1) and g["round"] > 1), "重复使用不算")
a2 = good(g); chat(p, room, "2", a2); a3 = good(g) if g["state"] != "done" else None
check(g["round"] == 2, "第二个观众接上了")
if g["state"] != "done": chat(p, room, "1", a3)
check(g["state"] == "done" and "接满" in g["note"], f"接满 rounds 结束：{g['note']}")
check(sum(app.play.pts.values()) == 5 * 3 + 10, f"每接 +5，冠军另 +10：{app.play.pts}")
check(p.games.snapshot()["winner"] and p.games.snapshot()["state"] == "done", "快照有冠军")
p.games.last_end = time.time(); p.cfg.cp["ai_plus"]["game_cooldown"] = "30"; p.games.cur = None
check(not p.games.start("idiom", room, "路人")[0], "冷却中不能开")
p.cfg.cp["ai_plus"]["game_who"] = "anchor"; p.games.last_end = 0; check(not p.games.start("idiom", room, "路人")[0], "game_who=anchor：路人不能开")
check(p.games.start("idiom", room, "主播甲")[0], "主播能开"); p.games.stop(room, "主播甲"); check(p.games.cur["state"] == "done", "stop 结束")
# 同音：读音相同也算
p.cfg.cp["ai_plus"]["game_who"] = "anyone"; p.games.last_end = 0; p.cfg.cp["ai_plus"]["game_cooldown"] = "0"; p.cfg.cp["ai_plus"]["idiom_host_plays"] = "false"
p.games.start("idiom", room, "x"); g = p.games.cur
homo = None
for cand in [x for x in w if x not in g["used"]]:
    if w[cand][0] == g["need"] and cand[0] != g["prompt"][-1]: homo = cand; break
check(homo is not None and chat(p, room, "9", homo) and g["round"] == 1, f"同音字也能接：{g['used'][0][-1]}→{homo}")
g["deadline"] = time.time() - 1; p.games.tick(); check(g["state"] == "done" and "时间到" in g["note"], "超时：揭晓并结束")
p.games.last_end = 0
p.cfg.cp["ai_plus"]["idiom_homophone"] = "false"; p.games.start("idiom", room, "x"); g = p.games.cur
homo = next((x for x in w if x not in g["used"] and w[x][0] == g["need"] and x[0] != g["prompt"][-1]), None)
check(homo and chat(p, room, "9", homo) and g["round"] == 0, "idiom_homophone=false：同音字不算"); p.games.stop(room); p.games.last_end = 0
# 机器接不上 → 玩家赢
p.cfg.cp["ai_plus"]["idiom_homophone"] = "true"; p.cfg.cp["ai_plus"]["idiom_host_plays"] = "true"
p.games.start("idiom", room, "x"); g = p.games.cur
g["used"] = list(w)  # 把所有成语都标记已用，除了玩家接的这个
last = g["prompt"]; cand = next(x for x in bf[g["need"]]); g["used"].remove(cand)
chat(p, room, "7", cand); check(g["state"] == "done" and "接不上" in g["note"] and g["winner"] == "观众7", f"主播接不上：玩家赢 {g['note']}")
p.games.last_end = 0
# 猜歌名 / 脑筋急转弯
p2, app2, h2 = mkg(game_cooldown=0, song_game_rounds=2, game_timeout=40, song_game_source="list")
room2 = Room(); ok, msg = p2.games.start("猜歌名", room2, "x"); check(ok, msg); g = p2.games.cur
ans = g["qa"]["title"]; check(g["qa"]["q"] and "歌词" not in g["qa"]["q"], "list 来源：用描述性提示，不是歌词")
check(chat(p2, room2, "1", "不知道呀") and g["log"][-1]["ok"] is False, "猜错：记录但不加分")
chat(p2, room2, "1", "提示"); check(g["hint"] and g["hint_i"] == 1, "提示命令给提示")
chat(p2, room2, "2", "我觉得是《" + ans + "》"); check(app2.play.pts.get("2") == 10 and g["state"] == "gap", f"猜对 +10（猜歌双倍）：{app2.play.pts}")
p2.games.tick(time.time() + 1); check(g["state"] == "gap", "间隔内不进下一题"); p2.games.tick(time.time() + 5); check(g["state"] == "open" and g["round"] == 2, "下一题")
g["deadline"] = time.time() - 1; p2.games.tick(); check(g["state"] == "gap" and "没人答对" in g["sub"], "超时揭晓答案")
p2.games.tick(time.time() + 9); check(g["state"] == "done" and g["winner"] == "观众2", "题数到：结束，冠军 = 最高分")
p2.games.last_end = 0
app2.play.test_song = {"key": "k1", "title": "十年", "artist": "陈奕迅", "duration": 200, "pos": 20, "playing": True, "ts": time.time() * 1000, "lines": [[10, "十年之前我不认识你", 14], [14, "你不属于我", 18]]}
p2.cfg.cp["ai_plus"]["song_game_source"] = "current"; p2.games.start("song", room2, "x"); g = p2.games.cur
check("十年之前我不认识你" in g["qa"]["q"] or "你不属于我" in g["qa"]["q"], "current 来源：用正在播的歌词当题"); chat(p2, room2, "3", "十年"); check(g["state"] == "gap" and "观众3" in g["sub"], "猜中当前歌曲")
p2.games.stop(room2); p2.games.last_end = 0
p2.games.start("riddle", room2, "x"); g = p2.games.cur; rr = g["qa"]; chat(p2, room2, "4", rr["answers"][0]); check(g["state"] == "gap" and app2.play.pts.get("4") == 5, "脑筋急转弯答对 +5")
check(G.Games._match(None, "天空是蓝色的", ["蓝色"]) and not G.Games._match(None, "蓝", ["蓝色"]) and not G.Games._match(None, "", ["x"]), "答案匹配：包含即可，太短不算")
pn, an, hn = mkg(game="false"); check(not pn.games.start("idiom", Room(), "x")[0], "game=false：不能开")
p2.games.stop(room2); p2.games.last_end = 0
ok, msg = p2.agent_action({"action": "game_start", "game": "idiom"}, {}, room2, "x"); check(ok, "agent_action game_start")
ok, msg = p2.agent_action({"action": "game_stop"}, {}, room2, "x"); check(ok and p2.games.cur["state"] == "done", "agent_action game_stop")
p2.games.cur = None; check(p2.games.snapshot() is None, "无游戏时快照 None")

# ---- agent 集成：registry / 口令 / 门控 ----
from agent import registry as R, rules
from agent.core import Agent
for a in ("game_start", "game_stop", "screen_comment", "song_comment"): check(a in R.ACTIONS and R.ACTIONS[a]["backend"] and a in R.AIPLUS_ACTIONS, f"registry 有后端动作 {a}")
for t, g in (("玩成语接龙", "idiom"), ("来局猜歌名", "song"), ("我们来玩脑筋急转弯吧", "riddle"), ("成语接龙吧", "idiom")):
    it = rules.parse(t); check(it and it.rule == "game_start" and it.actions[0]["game"] == g, f"口令 {t} → {g}")
for t, r_ in (("结束游戏", "game_stop"), ("不玩了", "game_stop"), ("点评一下这首歌", "song_comment"), ("说说这个画面", "screen_comment"), ("评价一下屏幕", "screen_comment")): it = rules.parse(t); check(it and it.rule == r_, f"口令 {t} → {r_}")
for t in ("猜歌名好玩吗", "这首歌好听", "成语接龙怎么玩", "屏幕好大", "我今天不玩了哈哈哈哈哈哈"): it = rules.parse(t); check(not (it and it.rule in ("game_start", "game_stop", "song_comment", "screen_comment")), f"不误触 {t}")
def mka(**kv):
    cfg = Config("/nonexistent.ini")
    for k, v in kv.items(): cfg.cp["ai_plus"][k] = str(v)
    return Agent(cfg, types.SimpleNamespace(any_host=lambda: None), log=lambda *a: None)
from agent.desk import Desk
good, errs, _ = mka().validate([{"action": "game_start", "game": "idiom"}], Desk(), "路人"); check(good and not errs, "默认：game_start 通过校验")
good, errs, _ = mka(game="false").validate([{"action": "game_start", "game": "idiom"}], Desk(), "路人"); check(not good and "被禁用" in str(errs), f"game=false：被拦 {errs}")
good, errs, _ = mka(enabled="false").validate([{"action": "song_comment"}], Desk(), "路人"); check(not good, "enabled=false：全拦")
good, errs, _ = mka(screen_cmd="false").validate([{"action": "screen_comment"}], Desk(), "路人"); check(not good, "screen_cmd=false：观众不能点评屏幕")
good, errs, _ = mka(screen_cmd="false").validate([{"action": "screen_comment"}], Desk(), "猪猪侠", viewer=False); check(good, "…但 AI / 闲时仍可")
check(not mka().__class__ is None and not mkg(game_cooldown=0)[0].games.start("bogus", Room(), "x")[0], "不认识的游戏名：开不了")

# ---- 闲时活动 / 画面点评逻辑 ----
from agent import idle as I
from agent.desk import Desk as D2
pi, ai_, hi = mkg(game_idle="true", game_idle_min_viewers=0, game_idle_list="idiom,riddle")
ai_.plus = pi
ctx = I.Ctx(types.SimpleNamespace(cfg=pi.cfg, app=ai_, agent=ai_.agent, sites=lambda: [], agent_site_ok=lambda x: True), None, None)
beats = I.ACTS["ai_game"](ctx); check(beats and beats[0]["actions"][0]["action"] == "game_start" and beats[0]["actions"][0]["game"] in ("idiom", "riddle"), "闲时活动 ai_game 计划（只从 game_idle_list 里选）")
pi.cfg.cp["ai_plus"]["game_idle"] = "false"; check(I.ACTS["ai_game"](ctx) is None, "game_idle=false：不自己开游戏")
pi.cfg.cp["ai_plus"]["game_idle"] = "true"; pi.games.start("riddle", Room(), "x", force=True); check(I.ACTS["ai_game"](ctx) is None, "有游戏在进行：不再开"); pi.games.stop(Room())
w0 = I.weights_of(Config("/nonexistent.ini")); check("ai_game" in w0 and "ai_screen" in w0 and "ai_game" in I.DESC and "ai_screen" in I.DESC, "weights_new 默认带上 ai_game / ai_screen")
check(I.ACTS["ai_screen"](ctx) is None, "ai_screen：没有页面在线时不选")
SN = {"ts": 1, "wins": [{"id": "qqchat", "app": "qqchat", "title": "群聊", "state": "normal", "z": 2}, {"id": "w1", "app": "notepad", "title": "记事本", "state": "normal", "z": 0, "active": True},
                        {"id": "w2", "app": "calc", "title": "计算器", "state": "min", "z": 1}], "music": {"on": True, "title": "十年", "artist": "陈奕迅", "playing": True}, "wall": "Bliss",
      "ai": {"fx": ["fireworks"], "game": {"name": "成语接龙", "prompt": "一心一意", "round": 1}, "vote": {"title": "下一步干啥"}}}
txt, fp, labels = pi.screen_desc(D2(SN))
check("记事本" in txt and "最小化" in txt and "计算器" in txt and "十年" in txt and "烟花" in txt and "成语接龙" in txt and "投票" in txt and "w1" not in txt and "id=" not in txt, f"屏幕描述是人话，不带窗口 id：{txt!r}")
SN2 = json.loads(json.dumps(SN)); SN2["wins"].append({"id": "w3", "app": "paint", "title": "画图", "state": "normal", "z": 0}); SN2["music"]["title"] = "晴天"; SN2["ai"]["bsod"] = True
txt2, fp2, labels2 = pi.screen_desc(D2(SN2)); ch = pi.screen_changes(fp, fp2, labels2)
check(any("画图" in c for c in ch) and any("晴天" in c for c in ch) and any("蓝屏" in c for c in ch) and pi.screen_changes(None, fp2, labels2) == [] and pi.screen_changes(fp, fp, labels) == [], f"变化检测：{ch}")
# 门控：没页面 / 主播忙 / 刚聊过 / 刚评论过
class FW:
    def __init__(self): self.sent = []
    async def send_str(self, d): self.sent.append(d)
async def t_screen():
    p, app, h = mkg(screen_min_gap=60, screen_quiet_secs=20, screen_interval=100)
    h.busy_until = 0
    ws = FW(); app.agent = types.SimpleNamespace(snap_ws=ws, clients={ws: {"snap": SN, "at": time.time()}}, desk=lambda: D2(SN), idle=None, say=lambda *a, **k: None)
    p.loop = asyncio.get_running_loop(); calls = []
    async def fake(force=False, who="", reason=""): calls.append((force, who, reason)); p.scr["busy"] = False
    p.screen_comment = fake; now = time.time()
    p.screen_tick(now + 200); await asyncio.sleep(0.05); check(len(calls) == 1 and not calls[0][2], "间隔到了：点评一次（无事件）")
    p.scr["last"] = now + 200; p.screen_tick(now + 230); await asyncio.sleep(0.05); check(len(calls) == 1, "screen_min_gap 内不重复")
    p.scr["last"] = 0; p.last_chat = now + 299; p.screen_tick(now + 300); await asyncio.sleep(0.05); check(len(calls) == 1, "刚有人聊天（screen_quiet_secs）：不插嘴")
    p.last_chat = 0; h.busy_until = now + 1000; p.screen_tick(now + 301); await asyncio.sleep(0.05); check(len(calls) == 1, "主播还在说话：不点评"); h.busy_until = 0
    app.agent.idle = types.SimpleNamespace(cur={"name": "x"}); p.screen_tick(now + 302); await asyncio.sleep(0.05); check(len(calls) == 1, "闲时活动进行中：不点评"); app.agent.idle = None
    p.games.start("riddle", Room(), "x", force=True); p.screen_tick(now + 303); await asyncio.sleep(0.05); check(len(calls) == 1, "游戏进行中：不点评"); p.games.stop(Room())
    # 事件触发：新开一个窗口 → 3 秒后点评，且带上变化
    p.scr.update(last=now, fp=fp); app.agent.desk = lambda: D2(SN2); app.agent.clients[ws]["snap"] = SN2
    p.screen_tick(now + 70); check(p.scr["changes"] and len(calls) == 1, "有变化但还没沉淀 3 秒：先等")
    p.scr["since"] = now + 60; p.screen_tick(now + 75); await asyncio.sleep(0.05); check(len(calls) == 2 and "画图" in calls[1][2], f"变化后点评并带上原因：{calls[-1]}")
    p.cfg.cp["ai_plus"]["screen_events"] = "false"; p.scr.update(last=now, fp=fp, changes=[]); p.screen_tick(now + 80); await asyncio.sleep(0.05); check(len(calls) == 2, "screen_events=false：只按间隔")
    p.cfg.cp["ai_plus"]["screen"] = "false"; p.scr["last"] = 0; p.screen_tick(now + 500); await asyncio.sleep(0.05); check(len(calls) == 2, "screen=false：关闭")
    # 视觉请求 / 回传 / 断路
    p2, app2, h2 = mkg(screen_vision="auto"); p2.cfg.cp["ai"]["base_url"], p2.cfg.cp["ai"]["model"] = "http://x/v1", "m"; ws2 = FW(); app2.agent = types.SimpleNamespace(snap_ws=ws2, clients={ws2: {"snap": SN, "at": time.time()}}, desk=lambda: D2(SN), idle=None)
    p2.loop = asyncio.get_running_loop()
    t = asyncio.ensure_future(p2.vision_req(timeout=2)); await asyncio.sleep(0.05); req = json.loads(ws2.sent[-1]); check(req["t"] == "vision_req" and req["w"] == 768, "向页面发 vision_req")
    p2.vision_result({"id": req["id"], "img": "data:image/jpeg;base64,AAAA"}); check(await t == "data:image/jpeg;base64,AAAA", "页面回传截图")
    check(await p2.vision_req(timeout=0.2) == "", "页面没回：返回空（退回文字快照）")
    check(p2.vision_on(), "screen_vision=auto：默认试视觉")
    for _ in range(3): p2.vision_failed(RuntimeError("x"))
    check(not p2.vision_on(), "视觉连续失败 3 次：暂停（只用文字）"); p2.vision_ok()
    p3, _, _ = mkg(screen_vision="off"); check(not p3.vision_on(), "screen_vision=off：只用文字")
    # 带图提示词 / 回退
    seen = []
    class H2:
        busy_until = 0
        def speak(self, kind, prompt, fb="", emo="", **kw): seen.append((kind, prompt, kw)); return fb
    p2._screen_say(H2(), txt, "data:image/jpeg;base64,AAAA", "刚打开了「画图」", "路人")
    check(seen[0][0] == "screen" and seen[0][2]["image"].startswith("data:image") and "以截图为准" in seen[0][1] and "刚打开了「画图」" in seen[0][1] and "路人" in seen[0][1] and "记事本" in seen[0][2]["alt_prompt"] and "截图为准" not in seen[0][2]["alt_prompt"], "带图：提示词 + 文字备份")
    p2._screen_say(H2(), txt, "", "", ""); check(not seen[1][2]["image"] and "截图为准" not in seen[1][1], "没图：纯文字提示词")
asyncio.run(t_screen())

# ---- 配置一致：config.py DEFAULTS ↔ config.ini（有 [ai_plus] 段时）；数据文件 / 页面脚本 / README 提到 ----
import configparser
ini = configparser.ConfigParser(interpolation=None); ini.read(ROOT / "config.ini", encoding="utf-8")
py = DEFAULTS["ai_plus"]
if "ai_plus" in ini:
    check(set(ini["ai_plus"]) == set(py), f"config.ini [ai_plus] ↔ config.py 键一致: {set(py) ^ set(ini['ai_plus'])}")
    for k, v in py.items():
        if k in ini["ai_plus"] and k not in ("memory_file",): check(ini["ai_plus"][k].strip() == v, f"默认值一致 ini/py: {k}")
check(len(py) >= 55, f"[ai_plus] 键数 {len(py)}")
for f in ("web/ai-ui.js", "backend/ai6/data/idioms.tsv", "backend/ai6/data/songs.tsv", "backend/ai6/data/riddles.tsv", "backend/ai6/data/IDIOM_LICENSE.txt"): check((ROOT / f).exists(), f"文件在：{f}")
check('src="ai-ui.js"' in (ROOT / "web/index.html").read_text(encoding="utf-8"), "index.html 引用 ai-ui.js")
rd = (ROOT / "README.md").read_text(encoding="utf-8")
check("[ai_plus]" in rd and "pwxcoo/chinese-xinhua" in rd and "忘记我" in rd, "README 讲了 [ai_plus]、数据署名、忘记我")
cr = "".join((ROOT / f).read_text(encoding="utf-8") for f in ("CREDITS.md", "THIRD_PARTY_NOTICES.md") if (ROOT / f).exists())
check("chinese-xinhua" in cr, "CREDITS / THIRD_PARTY_NOTICES 里有成语数据署名")

print("AI 加强包离线测试 " + ("全部通过" if not bad else f"{bad} 项失败"))
sys.exit(1 if bad else 0)
