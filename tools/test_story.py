# -*- coding: utf-8 -*-
"""连续剧情 + 观众记忆（backend/story.py、agent/diary_act.py，§11.14）的离线测试：剧情日期（开播日才往后走、同一天第二场不走、advance 关了不走）、
   本场记账、下播 → 等 end_wait → 写日记（太短不写 / 模板 / LLM（假的）/ 脏输出清洗 / 失败回退 / 提示词里没有 uid）、下次开播发表、冷场朗读（条件 / 已读）、
   观众记忆（口令 / 值得记的短弹幕的过滤：电话 · 网址 · @ · 联系方式 · 屏蔽词 · 命令 · 去重 · 条数上限）、忘记我、欢迎词和回弹幕里用上记忆、
   存档读写 / 损坏备份、页面 / 面板 / 接线 / 配置一致。不联网，不碰 Bark / 提示音
   python tools/test_story.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, re, sys, time, types, asyncio, random, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import story as ST
from agent import welcome as W, diary_act as DA, idle as I, registry as REG
from host.config import Config, DEFAULTS
from host.engine import Host
from play import store as S

bad = 0; total = 0
def check(c, m):
    global bad, total
    total += 1
    if not c:
        bad += 1; print("FAIL", m)

TMP = Path(tempfile.mkdtemp(prefix="story-test-"))
class FHost:
    name = "猪猪侠"
    def bl_in(s, t): return "违禁" in t
    def bl_out(s, t): return "违禁" in t
class FRoom:
    def __init__(s, rid="889"): s.rid = rid; s.clients = {1}; s.evs = []; s.last = {"room": {"anchor": "大主播"}}; s.host = None
    def _broadcast(s, ev): s.evs.append(ev)
class FPlay:
    def __init__(s): s.store = S.PlayStore(None); s.mem = S.PlayStore(None)
    def st(s, scope): return s.mem if scope == "demo" else s.store
class FMem:
    def __init__(s): s.optout = set()
    def key(s, uid): return "k" + str(uid)

def mk(name="s.json", **kv):
    cfg = Config("/nonexistent.ini")
    cfg.cp["story"]["file"] = str(TMP / name)
    cfg.cp["story"]["quote_sample"] = "0"
    for k, v in kv.items():
        sec, key = k.split("__"); cfg.cp[sec][key] = str(v)
    host = FHost(); room = FRoom(); room.host = host
    app = types.SimpleNamespace(any_host=lambda: host, play=FPlay(), rooms={"889": room}, default_room="889", plus=types.SimpleNamespace(mem=FMem()), welcome=None, story=None)
    s = ST.Story(cfg, app, lambda *a: None); app.story = s
    return s, app, room
def chat(uid, name, text): return {"t": "chat", "uid": uid, "name": name, "text": text}
def gift(uid, name, g, n=1): return {"t": "gift", "uid": uid, "name": name, "gift": g, "count": n}
def live(on): return {"t": "live", "live": on}
H = 3600; D = 86400
T0 = time.mktime((2026, 11, 10, 20, 0, 0, 0, 0, -1))      # 一个固定的「当天晚上 8 点」

def stream(s, room, t0, mins=30, chats=8):
    """开播 → 一些互动 → 返回结束时间"""
    s.on_event(live(True), room, t0)
    for i in range(chats):
        s.on_event(chat("u1", "小明", "哈哈这个太好笑了" if i % 2 else "主播好"), room, t0 + 60 + i)
    s.on_event(chat("u2", "阿花", "来个蓝屏"), room, t0 + 100)
    s.on_event(gift("u3", "土豪", "玫瑰", 2), room, t0 + 200)
    s.on_event({"t": "follow", "uid": "u4", "name": "新人"}, room, t0 + 300)
    s.on_highlight("perf_bsod", {"who": "阿花"}, t0 + 400)
    return t0 + mins * 60

# ---- 1. 剧情日期 ----
s, app, room = mk()
check(s.date_now().isoformat() == "2005-09-01" and s.cur_day() == 0 and "2005年9月1日" in s.label(s.date_now()), "没开过播：停在 start_date（2005-09-01）")
check(s.snapshot()["wd"] == "星期四" and s.snapshot()["start"] == "2005-09-01", "2005-09-01 是星期四")
s.on_event(live(True), room, T0)
check(s.cur_day() == 0 and s.data["sess"] is not None and s.stats["sessions"] == 1, "第一次开播：第 0 天（= start_date）")
s.on_event(live(True), room, T0 + 60)
check(s.stats["sessions"] == 1 and s.cur_day() == 0, "重复的开播事件（重启 / 重连）不新开一场")
s.on_event(live(False), room, T0 + 3600); s.tick(T0 + 3600 + 1000)
s.on_event(live(True), room, T0 + 3600 + 2000)           # 同一个真实日期的第二场
check(s.cur_day() == 0 and s.stats["sessions"] == 2, "同一天开第二场：日期不往后走")
s.on_event(live(False), room, T0 + 2 * H + 3000)
s.on_event(live(True), room, T0 + D + 100)                # 第二天
check(s.cur_day() == 1 and s.date_now().isoformat() == "2005-09-02" and s.snapshot()["wd"] == "星期五", "第二天开播：2005-09-02 星期五")
s.on_event(live(False), room, T0 + D + 5 * H); s.on_event(live(True), room, T0 + 3 * D)
check(s.cur_day() == 2 and s.date_now().isoformat() == "2005-09-03", "隔了一天没开播：只算开播的日子（不是真实日历天数）")
s2, _, r2 = mk("adv.json", story__advance="false")
for i in range(3):
    s2.on_event(live(True), r2, T0 + i * D); s2.on_event(live(False), r2, T0 + i * D + H)
check(s2.cur_day() == 0, "advance=false：日期固定")
s3, _, r3 = mk("start.json", story__start_date="2005-12-30")
s3.on_event(live(True), r3, T0); s3.on_event(live(False), r3, T0 + H); s3.on_event(live(True), r3, T0 + D)
check(s3.date_now().isoformat() == "2005-12-31" and s3.date_of(2).isoformat() == "2006-01-01", "start_date 可配，跨年")
sb, _, _ = mk("badstart.json", story__start_date="不是日期")
check(sb.start_date().isoformat() == "2005-09-01", "start_date 写坏了：回退 2005-09-01")
s.next_day()
check(s.cur_day() == 3 and s.pushed[-1]["t"] == "story", "面板「往后走一天」+ 推 story 事件给页面")
off, _, ro = mk("off.json", story__enabled="false")
off.on_event(live(True), ro, T0); off.on_event(chat("u1", "x", "哈哈哈哈哈哈哈"), ro, T0)
check(off.data["sess"] is None and off.snapshot() == {"on": False} and not off.on(), "总开关关了：什么都不记、/story.json 只有 on=false")

# ---- 2. 本场记账 ----
s, app, room = mk("tally.json")
end = stream(s, room, T0)
sess = s.data["sess"]
check(sess["chats"] == 9 and sess["follows"] == 1 and len(sess["gifts"]) == 1 and sess["hl"][0]["k"] == "bsod", "记账：弹幕 / 关注 / 礼物 / 高光（perf_ 前缀去掉）")
check(sess["cmds"] == {"bsod": 1} and sess["viewers"]["u1"]["c"] == 8 and sess["viewers"]["u3"]["g"] == 2, "记账：口令、每个人的弹幕 / 礼物数")
s.on_highlight("gift_big", {"who": "土豪", "gift": "嘉年华", "value": 3000}, T0 + 500)
check(sess["hl"][-1]["g"] == "嘉年华", "高光带礼物名")
check(all("uid" not in json.dumps(v) for v in sess["viewers"].values()), "本场记账里没有 uid 以外的东西（昵称 + 条数）")
for i in range(400):
    s.on_event(chat(f"x{i}", f"路人{i}", "来了"), room, T0 + 600)
check(len(sess["viewers"]) <= 300, "本场观众记账有上限（300）")

# ---- 3. 下播 → end_wait → 写日记 ----
s, app, room = mk("diary.json", story__diary_min_secs="600")
random.seed(3)
end = stream(s, room, T0, mins=30)
s.on_event(live(False), room, end)
check(s.data["sess"]["ended"] == end and not s.data["diaries"], "下播：先等 end_wait，不马上写")
s.tick(end + 60)
check(not s.data["diaries"] and s.data["sess"] is not None, "end_wait（180 秒）没到：不写")
s.on_event(live(True), room, end + 100)
check(s.data["sess"] is not None and not s.data["sess"].get("ended") and s.stats["sessions"] == 1, "掉线 100 秒又回来：还是同一场")
s.on_event(live(False), room, end + 200)
s.tick(end + 200 + 181)
check(len(s.data["diaries"]) == 1 and s.data["sess"] is None and not s.data["closing"], "下播超过 end_wait：写出日记")
d = s.data["diaries"][0]
check(d["how"] == "模板" and d["date"] == "2005-09-01" and d["title"].startswith("9月1日"), "没配 LLM（测试里 QQ_NO_FETCH）：模板日记，日期是剧情日期")
check("小明" in d["text"] and "土豪" in d["text"] and "玫瑰" in d["text"] and "蓝屏" in d["text"], "日记里有：最能聊的人 / 送礼的人和礼物 / 高光")
check(len(d["text"]) <= 220 and not d["published"] and not d["read"], "字数在上限内；写完还没发表")
check(set(d["names"]) >= {"小明", "土豪"} and "u1" not in json.dumps(d), "日记记着点名的昵称（给「日记里写到你」用），没有 uid")
f = s.facts({"start": T0, "ended": T0 + 1800, "date": "2005-09-01", "day": 0, "chats": 5, "viewers": {"u_secret123": {"n": "甲", "c": 5, "g": 0}}, "gifts": [], "follows": 0, "hl": [], "cmds": {}}, T0 + 1800)
check("u_secret123" not in json.dumps(f, ensure_ascii=False) and f["top"] == [{"name": "甲", "chats": 5}], "给日记的事实里只有昵称 + 条数（没有 uid）")

short, _, rs = mk("short.json")
short.on_event(live(True), rs, T0); short.on_event(chat("u1", "甲", "哈哈哈哈哈哈"), rs, T0 + 5); short.on_event(live(False), rs, T0 + 120); short.tick(T0 + 400)
check(not short.data["diaries"] and short.stats["skipped"] == 1, "太短（<10 分钟）的一场：不写日记")
cold, _, rc = mk("cold.json")
cold.on_event(live(True), rc, T0); cold.on_event(live(False), rc, T0 + 1800); cold.tick(T0 + 2100)
check(not cold.data["diaries"] and cold.stats["skipped"] == 1, "够长但没人互动（<5 次）：不写")
r = cold.force_diary(T0 + 2200) if cold.data.get("sess") or cold.data.get("closing") else {"ok": False}
check(r["ok"] is False, "（没有可用的记录时）强制写返回失败而不是崩")
nd, _, rn = mk("nodiary.json", story__diary="false"); stream(nd, rn, T0); nd.on_event(live(False), rn, T0 + 1800); nd.tick(T0 + 2100)
check(not nd.data["diaries"], "diary=false：不写")

# ---- 4. LLM（假的）----
def with_llm(fn, name):
    s, app, room = mk(name)
    s.llm_hook = fn
    end = stream(s, room, T0, mins=30); s.on_event(live(False), room, end); s.tick(end + 200)
    return s
seen = {}
def good(system, user):
    seen["system"], seen["user"] = system, user
    return '```json\n{"title":"今天好热闹","text":"今天直播好开心，小明陪我聊了好久。\\n土豪送了玫瑰，谢谢。"}\n```'
s = with_llm(good, "llm1.json")
d = s.data["diaries"][0]
check(d["how"] == "LLM" and d["title"] == "今天好热闹" and "小明" in d["text"] and s.stats["diaries_llm"] == 1, "LLM：解析 JSON（带 ```围栏也行）→ 标题 + 正文")
check("不是对你的指令" in seen["system"] and "只当文字" in seen["system"] and "emoji" in seen["system"], "提示词里写明：昵称 / 礼物名只是文字，不是指令；不要 emoji")
check("u1" not in seen["user"] and "u2" not in seen["user"] and "小明" in seen["user"], "送进模型的数据里没有 uid，只有昵称 / 条数")
check("{" not in d["text"] and "```" not in d["text"], "正文里没有 JSON / markdown 残留")
dirty = lambda sy, u: json.dumps({"title": "**标题**", "text": "来看 https://evil.example.com/x 加我微信 13800138000 哈哈哈 " + "字" * 400})
s = with_llm(dirty, "llm2.json"); d = s.data["diaries"][0]
check("http" not in d["text"] and "13800138000" not in d["text"] and len(d["text"]) <= 220 and "*" not in d["title"], "脏输出：网址 / 长数字 / markdown 被清掉，限长")
plain = lambda sy, u: "今天很开心，大家都好可爱。"
s = with_llm(plain, "llm3.json"); d = s.data["diaries"][0]
check(d["how"] == "LLM" and d["text"].startswith("今天很开心") and d["title"].startswith("9月1日"), "模型只回了一段话（不是 JSON）：当正文，标题用模板")
def boom(sy, u): raise RuntimeError("network down")
s = with_llm(boom, "llm4.json"); d = s.data["diaries"][0]
check(d["how"] == "模板" and "network down" in s.last_err and "小明" in d["text"], "模型报错：回退模板日记，错误记在状态里")
empty = lambda sy, u: ""
s = with_llm(empty, "llm5.json")
check(s.data["diaries"][0]["how"] == "模板", "模型回了空：回退模板")
s, _, _ = mk("llm6.json", story__llm="false"); s.cfg.cp["ai"]["base_url"] = "http://x"; s.cfg.cp["ai"]["model"] = "m"
check(not s.llm_ok(), "llm=false / QQ_NO_FETCH：不调模型")

# ---- 5. 下次开播发表、冷场朗读 ----
s, app, room = mk("pub.json", story__read_gap="1000")
end = stream(s, room, T0, mins=30); s.on_event(live(False), room, end); s.tick(end + 200)
check(len(s.data["diaries"]) == 1 and s.snapshot()["diaries"] == [] and s.unread() == [], "写好了但还没发表：页面看不到，也不会被念")
check(s.next_unread(end + 300) is None, "没发表的日记不会被朗读")
s.on_event(live(True), room, T0 + D + 60)
check(s.snapshot()["diaries"][0]["title"] == s.data["diaries"][0]["title"] and s.stats["published"] == 1, "下一次开播：发表（/story.json 里出现）")
check(s.snapshot()["date"] == "2005-09-02" and s.pushed[-1]["t"] == "story", "同时日期往后走一天、推 story 事件给页面")
dd = s.snapshot()["diaries"][0]
check(dd["date"] == "2005-09-01" and set(dd) == {"id", "date", "hm", "title", "text"}, "页面拿到的日记带写它那天的剧情日期，只有 5 个字段（没有 names / 内部状态）")
nu = s.next_unread(T0 + D + 100)
check(nu is not None and nu["id"] == dd["id"], "发表后、没念过：冷场朗读能选到")
s.mark_read(nu["id"], T0 + D + 100)
check(s.next_unread(T0 + D + 200) is None and s.stats["reads"] == 1, "念过的不再念")
check(s.publish() == 0, "重复发表：没有新的")
s.data["diaries"].append({"id": 99, "day": 1, "date": "2005-09-02", "hm": "22:00", "title": "新的", "text": "新日记", "names": [], "at": T0, "how": "模板", "published": T0, "read": 0})
check(s.next_unread(T0 + D + 300) is None and s.next_unread(T0 + D + 1200)["id"] == 99, "朗读间隔（read_gap）没到不念；到了念最新的")
sr, _, rr = mk("ra.json", story__read_aloud="false"); sr.data["diaries"].append({"id": 1, "published": 1, "read": 0, "title": "t", "text": "x", "date": "2005-09-01", "hm": "1:00"})
check(sr.next_unread(T0) is None, "read_aloud=false：不念")

# ---- 6. 冷场活动 diary_read ----
check("diary_read" in I.ACTS and "diary_read" in I.DESC and "diary_read" in I.T and "diary_read" in I.FIXED_LINES, "diary_read 注册进 idle（ACTS / DESC / T / FIXED_LINES 固定台词）")
cfg = Config("/nonexistent.ini")
check(I.weights_of(cfg)["diary_read"] == 2.0, "idle 权重里有 diary_read（[story] read_weight）")
cfg.cp["story"]["read_weight"] = "0"
check(I.weights_of(cfg)["diary_read"] == 0.0, "read_weight=0 就不会被抽到")
class FIdle: pass
def ctx_for(story, apps=(), cfgx=None):
    idl = FIdle(); idl.app = types.SimpleNamespace(story=story); c = types.SimpleNamespace(cfg=cfgx or story.cfg if story else Config("/nonexistent.ini"), idle=idl, apps=set(apps), fmt={})
    return c
s, app, room = mk("act.json", story__read_gap="0")
c = ctx_for(s)
check(DA.plan(c) is None, "没有没念过的日记：不做")
s.data["diaries"].append({"id": 5, "day": 0, "date": "2005-09-01", "hm": "23:10", "title": "晴天日记", "text": "今天直播好开心，大家都好可爱。", "names": [], "at": T0, "how": "模板", "published": T0, "read": 0})
check(DA.plan(ctx_for(s, ["qzone"])) is None, "QQ空间已经开着：不做")
c = ctx_for(s); beats = DA.plan(c)
check(beats and c.fmt["_diary_id"] == 5 and "晴天日记" in c.fmt["_intro"] and "今天直播好开心" in c.fmt["_intro"], "有日记：开场白 = 标题 + 日记正文（固定台词）")
acts = [a for b in beats for a in b["actions"]]
check([a["action"] for a in acts][:3] == ["open_app", "_idle_clear", "zone_open"] and acts[2] == {"action": "zone_open", "tab": "blog", "post": "diary"} and beats[0]["critical"], "动作：打开空间 → 日志页 → 点开最新一篇日记")
check(any(a["action"] == "_wait" and a["secs"] >= 8 for a in acts), "念的时候停够时间（按字数）")
s.cfg.cp["qq"]["zone"] = "false"
check(DA.plan(ctx_for(s)) is None, "[qq] zone 关了：不做")
check("post" in REG.ACTIONS["zone_open"]["args"] and "diary" in REG.ACTIONS["zone_open"]["args"]["post"], "registry：zone_open 有 post=diary 参数")

# ---- 7. 观众记忆：口令 / 短弹幕 ----
s, app, room = mk("mem.json")
st = app.play.store
s.on_event(live(True), room, T0)
s.on_event(chat("u1", "阿花", "来个蓝屏"), room, T0 + 1); s.on_event(chat("u1", "阿花", "再来个蓝屏"), room, T0 + 2); s.on_event(chat("u1", "阿花", "点歌 晴天"), room, T0 + 3)
u = st.scope("889")["users"]["u1"]
check(u["cmds"] == {"bsod": 2, "song": 1}, "welcome 没开时：story 自己记常用口令")
check(s.fav_cmds(u, 2) == ["蓝屏", "点歌"], "常用口令按次数排，用口令名")
s.on_event(chat("u1", "阿花", "这首歌太好听了！"), room, T0 + 4)
check(u.get("quotes") == ["这首歌太好听了！"], "值得记的短弹幕（有感叹）被记下")
for txt, why in [("加我微信 abc123 聊聊吧", "联系方式字样"), ("我的电话 13800138000 哈哈", "长数字（电话）"), ("看这个 https://x.cn/abc 太好笑了", "网址（去掉后太短）"), ("@大主播 你好呀哈哈哈", "@"),
                 ("哈", "太短"), ("哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈哈", "太长"), ("aaaaaaaa!!", "没有汉字"), ("违禁词哈哈哈哈哈", "命中屏蔽词"), ("来个蓝屏好不好！", "命令不当成话记"),
                 ("今天天气一般般吧", "没有感叹 / 夸（quote_sample=0）")]:
    s.on_event(chat("u1", "阿花", txt), room, T0 + 10)
check(u["quotes"] == ["这首歌太好听了！"], "不记：联系方式 / 电话 / 网址 / @ / 太短 / 太长 / 没汉字 / 屏蔽词 / 命令 / 普通闲聊")
s.on_event(chat("u1", "阿花", "这首歌太好听了！"), room, T0 + 11)
check(u["quotes"] == ["这首歌太好听了！"], "同一句不重复记")
for i, q in enumerate(["第二句真好笑！", "第三句太棒了！", "第四句我爱了！"]):
    s.on_event(chat("u1", "阿花", q), room, T0 + 20 + i)
check(u["quotes"] == ["第二句真好笑！", "第三句太棒了！", "第四句我爱了！"], "最多 3 句（quotes_max），旧的先丢")
s.on_event(chat("u9", "大主播", "主播自己说的话真好！"), room, T0 + 30)
s.on_event(chat("u8", "猪猪侠", "我自己说的话真好！"), room, T0 + 31)
check("u9" not in st.scope("889")["users"] and "u8" not in st.scope("889")["users"], "主播自己（房间主播名 / host 名）的话不记")
s.on_event(chat("", "无uid", "没有 uid 的话真好！"), room, T0 + 32)
check(len(st.scope("889")["users"]) == 1, "没有 uid 的弹幕不记")
s.cfg.cp["story"]["quote_sample"] = "1"
s.on_event(chat("u5", "小李", "今天天气一般般吧"), room, T0 + 40)
check(st.scope("889")["users"]["u5"]["quotes"] == ["今天天气一般般吧"], "quote_sample=1：普通闲聊也会被抽中（概率可配）")
s.cfg.cp["story"]["quote_sample"] = "0"
check(not any(k in json.dumps(u, ensure_ascii=False) for k in ("13800138000", "http", "微信")), "用户记录里没有任何电话 / 网址 / 联系方式")
sm, am, rm = mk("memoff.json", story__memory="false"); sm.on_event(chat("u1", "阿花", "这首歌太好听了！"), rm, T0)
check(not am.play.store.scope("889")["users"], "memory=false：一句都不记")

# ---- 8. 忘记我 / opt-out ----
app.plus.mem.optout.add("ku7")
s.on_event(chat("u7", "路人甲", "来个蓝屏"), room, T0 + 50); s.on_event(chat("u7", "路人甲", "这首歌太好听了！"), room, T0 + 51)
check("u7" not in st.scope("889")["users"] or not st.scope("889")["users"]["u7"].get("quotes"), "要求过「忘记我」（ai6 optout）的人：不记")
check(s.recall("889", "u7", "路人甲", force=True) == "" and s.reply_context(["u7"]) == "", "…也不拿出来用")
n = s.forget("u1")
check(n == 1 and "quotes" not in u and "cmds" not in u and s.stats["forgets"] == 1 and "u1" not in s.data["sess"]["viewers"], "forget：清掉口令 / 话 / 本场记账")

# ---- 9. recall / reply_context ----
s, app, room = mk("recall.json", story__recall_p="1")
st = app.play.store
u = st.user("889", "u1", "阿花"); u.update({"visits": 4, "cmds": {"bsod": 3, "song": 1}, "quotes": ["这首歌太好听了！"]})
random.seed(5)
outs = {s.recall("889", "u1", "阿花") for _ in range(40)}
check(all(o for o in outs) and any("还记得你说过「这首歌太好听了！」" in o for o in outs) and any("蓝屏" in o and "还记得" not in o.replace("我还记得", "") or "你上回玩的蓝屏" in o for o in outs), "recall：一句话 + 昵称 / 行为（说过的话 / 常玩的口令）")
check(s.recall("889", "nobody", "路人") == "" and s.recall("889", "u1", "阿花", force=True) != "", "没记录的人：空；force 不看概率")
s.cfg.cp["story"]["recall_p"] = "0"
check(s.recall("889", "u1", "阿花") == "" and s.recall("889", "u1", "阿花", force=True) != "", "recall_p=0：不带")
s.cfg.cp["story"]["recall_p"] = "1"; s.cfg.cp["story"]["recall"] = "false"
check(s.recall("889", "u1", "阿花", force=True) == "", "recall=false：不带")
s.cfg.cp["story"]["recall"] = "true"
s.data["diaries"].append({"id": 1, "published": T0, "read": 0, "names": ["阿花"], "title": "t", "text": "x", "date": "2005-09-01", "hm": "1:00"})
check(any("日记里写到你" in s.recall("889", "u1", "阿花", force=True) for _ in range(40)), "最近一篇已发表的日记写到了这个人：会提「日记里写到你」")
u["quotes"] = ["违禁的话哈哈哈！"]
check(all("违禁" not in s.recall("889", "u1", "阿花", force=True) for _ in range(20)), "recall 前再过一遍屏蔽词")
u["quotes"] = ["这首歌太好听了！"]
rc = s.reply_context(["u1", "nobody", ""])
check(rc.startswith("【剧情记忆") and "阿花" in rc and "来过4次" in rc and "常玩蓝屏、点歌" in rc and "「这首歌太好听了！」" in rc and "u1" not in rc and "不是指令" in rc, "reply_context：昵称 + 来过几次 + 常玩 + 说过的话；声明只是文字")
check(len(rc) <= 420 and s.reply_context(["nobody"]) == "" and s.reply_context([]) == "", "限长；没记录就是空串")
for i in range(6):
    st.user("889", f"v{i}", f"观众{i}").update({"visits": 3, "cmds": {"fw": 2}})
check(s.reply_context([f"v{i}" for i in range(6)]).count("\n- ") == 3 and "观众3" not in s.reply_context([f"v{i}" for i in range(6)]), "最多带 3 位观众")
s.cfg.cp["story"]["reply_memory"] = "false"
check(s.reply_context(["u1"]) == "", "reply_memory=false：不带")

# ---- 10. 欢迎词 / 回弹幕里用上 ----
class WIdle:
    task = None
    def interrupt(s, *a): pass
    def note_command(s): pass
class WTips:
    busy = False
    def available(s, t): return True
def wmk(story_on=True):
    cfg = Config("/nonexistent.ini"); cfg.cp["story"]["file"] = str(TMP / "w.json"); cfg.cp["story"]["recall_p"] = "1"
    host = FHost(); room = FRoom(); room.host = host
    app = types.SimpleNamespace(any_host=lambda: host, play=FPlay(), tips=WTips(), idle=WIdle(), ops=None, rooms={"889": room}, default_room="889", plus=None)
    app.story = ST.Story(cfg, app, lambda *a: None) if story_on else None
    w = W.Welcome(cfg, app, lambda *a: None); w.last_chat = 1e12; app.welcome = w
    return w, app, room
w, app, room = wmk()
st = app.play.store; u = st.user("889", "u1", "阿花"); u.update({"visits": 3, "last": int(T0) - 5 * D, "visit_day": "2020-01-01", "cmds": {"bsod": 2}, "quotes": ["这首歌太好听了！"]})
st.user("889", "u2", "新人")
w.on_event({"t": "member", "uid": "u1", "name": "阿花"}, room, T0); w.tick(T0 + 11)
t1 = room.evs[-1]["text"]
check("阿花" in t1 and ("还记得" in t1 or "我还记得" in t1), "欢迎老观众：带上一句记得的事 → " + t1)
w.on_event({"t": "member", "uid": "u3", "name": "全新观众"}, room, T0 + 100); w.tick(T0 + 111)
check("还记得" not in room.evs[-1]["text"] and "你上回" not in room.evs[-1]["text"], "欢迎全新观众：不带记忆")
w.on_event({"t": "member", "uid": "u1", "name": "阿花"}, room, T0 + 3000); w.on_event({"t": "member", "uid": "u2", "name": "新人"}, room, T0 + 3001); w.tick(T0 + 3012)
w0, app0, room0 = wmk(False)
u0 = app0.play.store.user("889", "u1", "阿花"); u0.update({"visits": 3, "visit_day": "2020-01-01", "cmds": {"bsod": 2}, "quotes": ["这首歌太好听了！"]})
w0.on_event({"t": "member", "uid": "u1", "name": "阿花"}, room0, T0); w0.tick(T0 + 11)
check("还记得" not in room0.evs[-1]["text"] and "你上回" not in room0.evs[-1]["text"], "没有 story 模块：欢迎词跟以前一样")
cfg = Config("/nonexistent.ini"); cfg.cp["story"]["file"] = str(TMP / "e.json"); cfg.cp["story"]["quote_sample"] = "0"
h = Host(cfg, lambda e: None, log=lambda *a: None)
app = types.SimpleNamespace(any_host=lambda: FHost(), play=FPlay(), rooms={}, default_room="889", plus=None, welcome=None)
sy = ST.Story(cfg, app, lambda *a: None); app.story = sy
su = app.play.store.user("889", "u1", "阿花"); su.update({"visits": 4, "cmds": {"fw": 2}, "quotes": ["这首歌太好听了！"]})
prompts = []
h.use_ai = True; h._llm = lambda p, **k: (prompts.append(p), "好的阿花")[1]; h._say = lambda *a, **k: None; h.story = sy
h._reply([{"uid": "u1", "user": "阿花", "text": "主播晚上好", "hot": False, "done": False}], 40)
check(prompts and "剧情记忆" in prompts[0] and "常玩烟花" in prompts[0] and "u1" not in prompts[0].replace("主播晚上好", ""), "AI 主播回弹幕：提示词里带观众记忆（昵称 / 行为 / 话），没有 uid")
h.story = None; prompts.clear()
h._reply([{"uid": "u1", "user": "阿花", "text": "主播晚上好", "hot": False, "done": False}], 40)
check(prompts and "剧情记忆" not in prompts[0], "没挂 story：提示词跟以前一样")

# ---- 11. 存档 ----
s, app, room = mk("persist.json")
end = stream(s, room, T0, mins=30); s.on_event(live(False), room, end); s.tick(end + 200); s.publish(); s.save(force=True)
s2 = ST.Story(s.cfg, app, lambda *a: None)
check(s2.data["diaries"] == s.data["diaries"] and s2.cur_day() == s.cur_day() and s2.data["real_day"] == s.data["real_day"], "存档读回：日记 / 日期 / 日子一致")
mid, am, rm = mk("mid.json")
mid.on_event(live(True), rm, T0); mid.on_event(chat("u1", "甲", "主播好呀"), rm, T0 + 5); mid.save(force=True)
mid2 = ST.Story(mid.cfg, am, lambda *a: None)
mid2.on_event(live(True), rm, T0 + 600)
check(mid2.data["sess"]["chats"] == 1 and mid2.stats["sessions"] == 0, "直播中服务重启：接着记这一场，日期不重复往后走")
mid3 = ST.Story(mid.cfg, am, lambda *a: None); mid3.data["sess"]["seen"] = T0 - 10 * H
mid3.on_event(live(True), rm, T0 + 3 * H)
check(mid3.stats["sessions"] == 1 and len(mid3.data["closing"]) == 1, "上一场记录太旧（>6 小时没动静）：收尾那一场，另开新的")
dead = (TMP / "bad.json"); dead.write_text("{坏掉的", encoding="utf-8")
sb, _, _ = mk("bad.json")
check(sb.cur_day() == 0 and (TMP / "bad.json.bad").exists(), "存档损坏：改名备份后重新开始，不崩")
srv = mk("srv.json")[0]
st_ = srv.state()
check(set(("enabled", "date", "label", "day", "sess", "diaries", "published", "pending", "unread", "last", "stats", "err")) <= set(st_) and "uid" not in json.dumps(st_, ensure_ascii=False), "state()：面板需要的字段，没有 uid")

# ---- 12. 配置 / 接线 / 页面 / README ----
rd = lambda p: (ROOT / p).read_text(encoding="utf-8")
ini = rd("config.ini")
import configparser
cp = configparser.ConfigParser(interpolation=None); cp.read_string(ini)
check("story" in cp and dict(cp["story"]) == DEFAULTS["story"], "config.ini [story] 和 DEFAULTS 一致")
check(len(re.findall(r"^\[story\]", ini, re.M)) == 1, "config.ini 里 [story] 只有一段")
srvsrc = rd("backend/server.py")
check("Story(cfg, self, log)" in srvsrc and "app_state.story.start()" in srvsrc and "app_state.story.shutdown()" in srvsrc and "story_json" in srvsrc and "/story.json" in srvsrc, "server.py：创建 / 启动 / 关闭 / /story.json")
check(srvsrc.index("self.app.welcome.on_event(ev, self)") < srvsrc.index("self.app.story.on_event(ev, self)") < srvsrc.index("gf.on_event(ev, self)"), "story 在 welcome 之后、giftfx / play / ai6 之前看到事件（只观察）")
check("sy.on_highlight(kind, h)" in srvsrc and "self.host.story" in srvsrc, "mark_highlight 通知 story；Host 挂上 story")
check("sy.forget(uid)" in rd("backend/ai6/plus.py"), "ai6「忘记我」同时清 story 的记录")
api = rd("backend/ops/api.py")
check('("story", "连续剧情' in api and '"story": app.story.state()' in api and all(k in api for k in ("story_diary", "story_publish", "story_day", "story_read")), "面板：开关组 / state / 4 个动作")
for k in ("story.enabled", "story.advance", "story.clock", "story.zone", "story.diary", "story.llm", "story.read_aloud", "story.memory", "story.recall", "story.reply_memory"):
    check(f'"{k}"' in api, f"面板开关 {k}")
check("renderStory" in rd("web/panel/panel.js") and 'data-t="story"' in rd("web/panel/index.html") and 'id="t-story"' in rd("web/panel/index.html"), "面板「剧情」页")
sj = rd("web/story.js")
check("window.STORY" in sj and "story.json" in sj and "story-cal" in sj and "c.title" in sj and "storydate" in sj, "web/story.js：STORY / /story.json / 时钟提示 + 日历")
check('src="story.js"' in rd("web/index.html"), "index.html 引用 story.js")
zj = rd("web/qq-zone.js")
check("STORY" in zj and "syncDiaries" in zj and "data-diary" in zj and "shown(" in zj, "qq-zone.js：剧情日期 / 日记同步 / data-diary")
check("a.post === 'diary'" in rd("web/agent-actions.js"), "agent-actions.js：zone_open post=diary 点开最新日记")
check("data/story.json" in rd(".gitignore"), ".gitignore 里有 data/story.json")
check("story" in rd("backend/host/engine.py") and "story.reply_context" in rd("backend/host/engine.py"), "engine：回弹幕带 story 记忆")
check("sy.recall(" in rd("backend/agent/welcome.py"), "welcome：compose 带 recall")
check("name == \"diary_read\"" in rd("backend/agent/idle.py") and "mark_read" in rd("backend/agent/idle.py"), "idle：开念时标记已读")
readme = rd("README.md")
check("11.14" in readme and "[story]" in readme and "test_story" in readme and "screenshots/story/" in readme, "README：§11.14 / [story] / 测试 / 截图")
shots = [m for m in re.findall(r"screenshots/story/[\w\-.]+\.png", readme)]
check(len(shots) >= 5 and all((ROOT / p).exists() for p in shots), f"README 引用的 story 截图都存在（{len(shots)} 张）")

print(f"\n{total - bad}/{total} 通过" + ("" if not bad else f"，{bad} 个失败"))
sys.exit(1 if bad else 0)
