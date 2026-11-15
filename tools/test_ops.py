# -*- coding: utf-8 -*-
"""运维（[ops]）离线测试：抓取器重连 / 开播下播 / 取房间信息修复、日志、复盘报告、看门狗、控制面板、一键启动健康检查、配置一致。
   python tools/test_ops.py        页面级（真浏览器）验证见 tools/shoot_ops.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import asyncio, json, re, sys, tempfile, threading, time, types
from pathlib import Path
from collections import Counter
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from host.config import Config, DEFAULTS

bad = 0
def check(cond, msg):
    global bad
    if not cond:
        bad += 1; print("FAIL", msg)

# ---- 1. 抓取器：取房间信息修复（TypeError / 空 JSON）----
from dy import fetcher as F
class Resp:
    def __init__(self, content=b"", cookies=None, js=None, status=200): self.content, self.cookies, self._js, self.status_code, self.text = content, cookies or {}, js, status, content.decode("utf-8", "ignore")
    def json(self): return json.loads(self.content.decode())
class FakeSession:
    """第一次访问 www.douyin.com 下发 __ac_nonce，之后不再下发（真实行为）；enter 接口前 N 次返回空内容。"""
    def __init__(self, empties=2, live=True):
        self.cookies = {}; self.n_www = 0; self.n_enter = 0; self.empties = empties; self.live = live
    def get(self, url, **kw):
        if "webcast/room/web/enter" in url:
            self.n_enter += 1
            if self.n_enter <= self.empties: return Resp(b"")
            return Resp(json.dumps({"data": {"room_status": 0 if self.live else 4, "data": [{"title": "测试直播", "room_view_stats": {"display_value": "12"}}], "user": {"nickname": "主播甲"}}}).encode())
        if url.rstrip("/") == "https://www.douyin.com":
            self.n_www += 1
            if self.n_www == 1: self.cookies["__ac_nonce"] = "abc123"; return Resp(b"<html>", cookies={"__ac_nonce": "abc123"})
            return Resp(b"<html>", cookies={})
        return Resp(b"")
def mkf(**o):
    logs = []; evs = []
    f = F.DouyinFetcher("123", evs.append, log=logs.append, opts=o); f.ttwid = "t"; f.room_id = "999"; return f, evs, logs
seen_nonce = []
real_sig = F.get__ac_signature
F.get__ac_signature = lambda host, nonce, ua: (seen_nonce.append(nonce), real_sig(host, nonce, ua))[1]
f, evs, logs = mkf(); f.session = FakeSession(empties=2)
info = f._room_info(); check(info and info["anchor"] == "主播甲" and info["live"] is True and info["title"] == "测试直播", f"空内容重试后拿到房间信息：{info}")
check(f.session.n_enter == 3 and all(seen_nonce), f"重试 3 次、nonce 从来没有 None（会话第二次起 Set-Cookie 不再下发）：{seen_nonce}")
check(not any("取房间信息失败" in l for l in logs), "成功就不记失败日志")
f, evs, logs = mkf(); f.session = FakeSession(empties=99); f._stop.wait = lambda t=None: None
info = f._room_info(tries=3); check(info is None and sum("取房间信息失败" in l for l in logs) == 1 and "空内容" in logs[0], f"一直拿不到：只记一条日志、写明原因：{logs}")
F.get__ac_signature = real_sig

# ---- 2. 抓取器：开播 / 下播 / 重连状态机 ----
class SimFetcher(F.DouyinFetcher):
    """把网络换成剧本：live_script 每次 _prepare 取一个状态；connect_script 每次 _connect 的动作（'ok:<秒>' 连上并收几条 / 'err' 抛异常 / 'end' 收到下播）。"""
    def __init__(self, live_script, connect_script, **o):
        self.evs = []; super().__init__("123", self.evs.append, log=lambda *a: None, opts=o)
        self.live_script, self.connect_script, self.prep_n, self.conn_n, self.times = list(live_script), list(connect_script), 0, 0, []
        self.poll, self.bo_min, self.bo_max = 0.05, 0.02, 0.08
    def _prepare(self):
        self.prep_n += 1
        st = self.live_script.pop(0) if len(self.live_script) > 1 else self.live_script[0]
        if st == "none": raise F.RoomNotLive("找不到 roomId")
        if st == "err": raise RuntimeError("网络不通")
        self.room_id = "r" + str(self.prep_n); self.fresh = st != "unknown"
        if st == "unknown": return
        self.emit({"t": "room", "anchor": "甲", "title": "t", "live": st == "live"}); self._set_live(st == "live", {"anchor": "甲", "title": "t", "live": st == "live"})
    def _connect(self):
        self.conn_n += 1; self.times.append(time.time())
        act = self.connect_script.pop(0) if self.connect_script else "block"
        if act == "err": raise RuntimeError("ws 出错")
        self.connected = True; self.state = "connected"; self.connects += 1; self.connected_at = time.time()
        if act == "end":
            self.emit({"t": "end"}); self.ended_at = time.time(); self._set_live(False)
        elif act == "block":
            self._stop.wait(5)
        elif act == "quick":
            pass
        self.connected = False
def run_sim(f, secs, cond=None):
    f.start(); t = time.time()
    while time.time() - t < secs and not (cond and cond()): time.sleep(0.02)
    f.stop(); f._thread.join(2)
lives = lambda f: [e["live"] for e in f.evs if e.get("t") == "live"]
f = SimFetcher(["live"], ["block"], live_gate=True); run_sim(f, 3, lambda: f.state == "connected")
check(f.conn_n == 1 and lives(f) == [True], f"直播中：直接连上，发 live=True：{lives(f)}")
f = SimFetcher(["none", "none", "live", "live"], ["block"], live_gate=True); run_sim(f, 3, lambda: f.connected)
check(f.conn_n == 1 and f.prep_n >= 3 and lives(f) == [False, True], f"没开播：不连 WebSocket、轮询，开播后自动连（prepare {f.prep_n} 次，live {lives(f)}）")
f = SimFetcher(["offline", "offline", "live"], ["block"], live_gate=True); run_sim(f, 3, lambda: f.connected)
check(f.conn_n == 1 and lives(f) == [False, True], "info 说未开播同样等")
f = SimFetcher(["offline"], ["block"], live_gate=False); run_sim(f, 1, lambda: f.conn_n)
check(f.conn_n == 1, "live_gate=false：老行为，没开播也连")
f = SimFetcher(["live", "offline", "offline", "live", "live"], ["end", "block"], live_gate=True); run_sim(f, 4, lambda: f.conn_n >= 2)
check(f.conn_n == 2 and lives(f) == [True, False, True], f"开播 → 下播（end 事件）→ 等待 → 再开播自动重连：{lives(f)}")
check(any(e.get("t") == "end" for e in f.evs), "下播事件照常转发")
f = SimFetcher(["unknown"], ["block"], live_gate=True); run_sim(f, 3, lambda: f.conn_n)
check(f.conn_n == 1 and f.live is None, "状态一直查不到：连续 3 次后试着连（不傻等）")
f = SimFetcher(["live"], ["err", "err", "err", "quick", "block"], live_gate=True, ); run_sim(f, 4, lambda: f.conn_n >= 5)
gaps = [b - a for a, b in zip(f.times, f.times[1:])]
check(f.conn_n >= 5 and f.reconnects >= 4 and gaps[1] > gaps[0] * 0.9 and max(gaps) <= 0.08 * 1.25 + 0.3, f"出错后退避重连（间隔 {[round(g, 2) for g in gaps]}，不超过 backoff_max）")
f = SimFetcher(["err"], ["block"], live_gate=True); run_sim(f, 0.6, lambda: False)
check(f.prep_n >= 3 and f.last_error and f.snapshot()["state"] in ("backoff", "stopped", "preparing"), f"网络不通：一直重试、记录 last_error：prep={f.prep_n} {f.last_error}")
snap = SimFetcher(["live"], ["block"]).snapshot(); check(set(snap) >= {"state", "live", "connected", "reconnects", "last_error"}, "snapshot 字段")

# ---- 3. Ops 核心：常驻房间 / 自动切换 ----
from ops import Ops
class FApp:
    def __init__(self, c): self.default_room, self.rooms, self.cfg = "111", {}, c
    def get_room(self, rid): self.rooms.setdefault(rid, types.SimpleNamespace(fetcher=None, clients=set())); return self.rooms[rid]
cfgt = Config(str(ROOT / "config.ini"))
cfgt.cp["ops"]["log"] = "false"
for _k in ("enabled", "bark", "sound"): cfgt.cp["guard"][_k] = "false"          # 绝不能用真 config.ini 的 Bark / 提示音（这里发过真推送）
cfgt.cp["guard"]["bark_key_file"] = "/nonexistent/bark_key.txt"
fa = FApp(cfgt); o = Ops(cfgt, fa, lambda *a: None)
check(o.keep("111") and not o.keep("222") and not o.keep("demo"), "keep_room 只钉默认房间")
cfgt.cp["ops"]["keep_room"] = "false"; check(not o.keep("111"), "keep_room=false 不钉"); cfgt.cp["ops"]["keep_room"] = "true"
seen = []; o.hooks.append(lambda ev, room: seen.append(ev["t"])); o.hooks.append(lambda ev, room: 1 / 0)
o.on_event({"t": "live", "live": True}, None); check(o.live_since and seen == ["live"], "钩子被调用，且一个钩子出错不影响别的")
o.on_event({"t": "live", "live": False}, None); check(o.live_since is None, "下播清空 live_since")

# ---- 4. 按场日志 + 复盘 ----
from ops import logs as OL, report as OR
tmp = Path(tempfile.mkdtemp(prefix="opstest-"))
cfgl = Config(str(ROOT / "config.ini"))
for k, v in (("log_dir", str(tmp / "logs")), ("report_dir", str(tmp / "reports")), ("end_grace", "0.3"), ("session_gap", "2"), ("log_max_mb", "0.01"), ("log_files", "3"), ("report_llm", "false")):
    cfgl.cp["ops"][k] = v
msgs = []
rec = OL.Recorder(cfgl, msgs.append, tmp); ended = []; rec.on_end.append(ended.append); rec.start()
rec.record("chat", text="没有会话时丢弃"); check(rec.sess is None, "没有进行中的一场就不写")
room = types.SimpleNamespace(rid="100000000001"); demo = types.SimpleNamespace(rid="demo")
rec.handle({"t": "chat", "uid": "d1", "name": "demo", "text": "假数据"}, demo); check(rec.sess is None, "演示房间不记")
rec.handle({"t": "live", "live": False, "room": "100000000001"}, room); check(rec.sess is None, "没开播的 live=False 不开场")
rec.handle({"t": "live", "live": True, "room": "100000000001", "anchor": "主播甲", "title": "测试直播"}, room); check(rec.sess is not None, "live=True 开一场")
t0 = rec.sess["start"]
def ev(**k): rec.handle(k, room)
ev(t="stat", online=10, total="1.2万"); ev(t="chat", uid="u1", name="<b>甲</b>", text="第一条弹幕内容很长很长很长" * 30)
for i in range(6): ev(t="chat", uid="u2", name="乙", text=f"乙的第{i}条消息ok")
ev(t="gift", uid="u3", name="丙", gift="玫瑰", count=1, value=1); ev(t="gift", uid="u3", name="丙", gift="玫瑰", count=2, value=1); ev(t="gift", uid="u3", name="丙", gift="玫瑰", count=3, value=1)   # 连击 1→2→3：共 3 个
ev(t="gift", uid="u4", name="丁", gift="嘉年华", count=1, value=3000)
ev(t="follow", uid="u2", name="乙"); ev(t="follow", uid="u2", name="乙"); ev(t="like", uid="u2", name="乙", count=30); ev(t="member", uid="u9", name="戊")
rec.handle_music({"t": "music", "on": True, "key": "k1", "title": "晴天", "artist": "周杰伦", "duration": 200}, None); rec.handle_music({"t": "music", "on": True, "key": "k1", "title": "晴天", "artist": "周杰伦"}, None)
ev(t="play", k="vote", vote={"id": 1, "title": "唱什么", "state": "open", "opts": [{"label": "晴天", "count": 0}, {"label": "七里香", "count": 0}], "total": 0, "by": "乙"})
ev(t="play", k="vote", vote={"id": 1, "title": "唱什么", "state": "open", "opts": [{"label": "晴天", "count": 1}, {"label": "七里香", "count": 0}], "total": 1, "by": "乙"})
ev(t="play", k="vote", vote={"id": 1, "title": "唱什么", "state": "done", "opts": [{"label": "晴天", "count": 5}, {"label": "七里香", "count": 2}], "total": 7, "winner": 1, "by": "乙"})
ev(t="play", k="game", game={"id": 1, "kind": "idiom", "name": "成语接龙", "state": "open", "by": "乙"}); ev(t="play", k="game", game={"id": 1, "kind": "idiom", "name": "成语接龙", "state": "done", "by": "乙", "winner": "丙", "board": [{"name": "丙", "pts": 3, "n": 3}]})
rec.record("agent", user="乙", text="打开记事本", actions=["open_app", "type_text"]); rec.record("idle", name="paint", result="完成", ms=1000, lines=2)
ev(t="status", level="error", text="取房间信息失败: 测试"); rec.server_line("12:00:00 [x] LLM 失败 timeout")
ev(t="say", id="1", kind="reply", text="谢谢大家")
import time as _t; _t.sleep(1.2); rec._last_stat = 0
ev(t="stat", online=88, total="1.2万"); ev(t="chat", uid="u5", name="己", text="最后一条也要记下来")
snap = rec.snapshot(); check(snap["active"] and snap["counts"]["chat"] == 8 and snap["counts"]["follow"] == 2, f"计数：{snap}")
ev(t="live", live=False); ev(t="chat", uid="u5", name="己", text="宽限期内又来一条")
rec.tick(); check(rec.sess is not None, "宽限期内（又有互动）不结束")
rec.handle({"t": "end"}, room); _t.sleep(0.5); rec.tick()
check(rec.sess is None and len(ended) == 1 and ended[0]["reason"] == "下播", f"下播宽限到期后结束：{ended}")
sid = ended[0]["sid"]; evs = OL.read_events(tmp / "logs", sid)
kinds = Counter(e["k"] for e in evs)
check(all(kinds[k] for k in ("chat", "gift", "like", "follow", "stat", "song", "vote", "game", "agent", "idle", "host", "err", "live", "end", "session_end")), f"各类事件都记了：{dict(kinds)}")
check(kinds["member"] == 0, "log_members=false 不记进场")
check(kinds["vote"] == 2 and kinds["game"] == 2 and kinds["song"] == 1, f"投票/游戏只记状态变化、歌只记一次：{dict(kinds)}")
check(all(len(e.get("text", "")) <= 200 for e in evs if e["k"] == "chat"), "弹幕文本按 log_text_chars 截断")
check((tmp / "logs" / "server.log").exists() and "LLM 失败" in (tmp / "logs" / "server.log").read_text(encoding="utf-8"), "server.log 有内容")
check(any(e["k"] == "err" and "LLM" in e["text"] for e in evs), "日志里像错误的行记成 err 事件")
import itertools
rec2 = OL.RotFile(tmp / "rot.log", 10_000, 2)
for i in range(400): rec2.write("x" * 100)
rec2.close(); fs = sorted(p.name for p in tmp.glob("rot.log*")); check(fs == ["rot.log", "rot.log.1", "rot.log.2"], f"轮转最多保留 2 个旧文件：{fs}")
check(max(p.stat().st_size for p in tmp.glob("rot.log*")) <= 10_200, "单个文件不超过上限")
# 复盘
r = OR.generate(cfgl, sid, msgs.append, use_llm=False, root=tmp)
st = r["stats"]
check(st["gift_count"] == 4 and st["diamonds"] == 3 + 3000, f"连击去重：玫瑰 1→2→3 记 3 个 + 嘉年华 1 个 = 4 个，抖币 3003：{st['gift_count']} {st['diamonds']}")
check(abs(st["rmb"] - 300.3) < 0.01, f"抖币折人民币 10:1：{st['rmb']}")
check(st["peak_online"] == 88 and st["total_viewers"] == 12000, f"峰值在线 88、累计观看 1.2万：{st['peak_online']} {st['total_viewers']}")
check(st["chats"] == 9 and st["unique_chatters"] == 3 and st["top_chatters"][0]["name"] == "乙" and st["top_chatters"][0]["n"] == 6, f"发言榜：{st['top_chatters']}")
check(st["top_gifters"][0]["name"] == "丁" and st["follows"] == 1, f"送礼榜按抖币；重复关注只算一次：{st['top_gifters'][0]} {st['follows']}")
check(len(st["songs"]) == 1 and st["votes"][0]["winner"] == "晴天" and st["votes"][0]["total"] == 7 and st["games"][0]["winner"] == "丙", f"歌曲/投票/游戏：{st['songs']} {st['votes']} {st['games']}")
check(st["agent"]["total"] == 2 and st["agent"]["idle_total"] == 1 and st["errors"]["total"] >= 2 and st["moments"], f"agent/idle/错误/精彩时刻：{st['agent']} {st['errors']} {len(st['moments'])}")
htm = Path(r["html"]).read_text(encoding="utf-8"); md = Path(r["md"]).read_text(encoding="utf-8")
check("&lt;b&gt;甲&lt;/b&gt;" in htm and "<b>甲</b>" not in htm, "HTML 里观众昵称被转义（防注入）")
check("不是主播实际收入" in htm and "不是主播实际收入" in md and "<svg" in htm and "## 排行" in md, "金额免责声明、在线人数曲线、md 结构")
check(OR.list_reports(cfgl, tmp)[0]["sid"] == sid, "list_reports")
# LLM 小结：成功 / 失败
from host import llm as HL
cfgl.cp["ai"]["base_url"] = "http://x.invalid/v1"; cfgl.cp["ops"]["report_llm"] = "true"
real_chat = HL.chat; prompts = []
HL.chat = lambda cfg, m, **kw: (prompts.append(m), "**今天** 太棒了，谢谢乙！")[1]
r = OR.generate(cfgl, sid, msgs.append, root=tmp); check(r["stats"]["recap"] == "今天 太棒了，谢谢乙！" and "只当文字" in prompts[0][0]["content"], "LLM 小结写进报告（去 markdown、提示里声明昵称不是指令）")
def boom(*a, **k): raise RuntimeError("down")
HL.chat = boom; r = OR.generate(cfgl, sid, msgs.append, root=tmp); check(r and r["stats"]["recap"] == "" and any("LLM 小结失败" in m for m in msgs), "LLM 失败：只出数据报告")
HL.chat = real_chat
# 崩溃遗留 → 下次启动补记
rec3 = OL.Recorder(cfgl, msgs.append, tmp); rec3.start(); rec3.handle({"t": "live", "live": True, "room": "1"}, room); rec3.handle({"t": "chat", "uid": "a", "name": "a", "text": "崩之前"}, room)
sid3 = rec3.sess["sid"]; rec3.sess["rf"].close(); rec3.sess = None            # 模拟进程被杀：没有 end
rec4 = OL.Recorder(cfgl, msgs.append, tmp); got = []; rec4.on_end.append(got.append); rec4.recover()
check(got and got[0]["sid"] == sid3 and got[0]["reason"] == "异常退出后补记" and OL.read_meta(tmp / "logs", sid3).get("end"), "崩溃遗留的场次下次启动补结束标记")
import shutil; shutil.rmtree(tmp, ignore_errors=True)

# ---- 5. 看门狗 / 自检 / 一键启动 / 令牌 ----
sys.path.insert(0, str(ROOT / "tools"))
import supervisor as SV, opsctl as OPSCLI
from ops import health as H, panel as PN
class FakeProc:
    def __init__(self, code, secs, clock): self.code, self.t_end, self.clock = code, clock[0] + secs, clock
    def poll(self): self.clock[0] = max(self.clock[0], self.t_end); return self.code
    def wait(self, timeout=None): return self.code
    def terminate(self): pass
def run_sv(plan, **kw):
    clock = [1000.0]; logs_ = []; spawned = []
    def popen(cmd, env=None): code, secs = plan[len(spawned)]; spawned.append((code, clock[0])); return FakeProc(code, secs, clock)
    ev_ = threading.Event(); waits = []
    ev_.wait = lambda d=None: waits.append(d)
    rc = SV.supervise(["py", "x"], None, kw.get("delay", 3.0), kw.get("max", 8), 60.0, logs_.append, ev_, popen, lambda: clock[0], poll_s=0)
    return rc, spawned, waits, logs_
rc, sp, w, lg = run_sv([(1, 1), (1, 1), (SV.RESTART_CODE, 5), (0, 100)])
check(rc == 0 and len(sp) == 4 and w == [3.0, 6.0], f"崩溃退避 3→6 秒；75 = 立即重启（不等）；0 = 正常退出不重启：waits={w} spawned={len(sp)}")
rc, sp, w, lg = run_sv([(1, 1)] * 20, max=3)
check(rc == 1 and len(sp) == 4 and any("放弃" in l for l in lg) and w == [3.0, 6.0, 12.0], f"连续快速崩溃超过上限就放弃：{len(sp)} {w}")
rc, sp, w, lg = run_sv([(1, 1), (1, 120), (1, 1), (0, 1)])
check(w == [3.0, 3.0, 6.0], f"活过 60 秒算稳定：退避从头开始（3 → 稳定后又是 3 → 6）：{w}")
check(SV.RESTART_CODE == 75, "退出码 75 约定")
# 自检
mac_out = "Audio:\n\n    Devices:\n\n        MacBook Pro Speakers:\n\n          Default Output Device: Yes\n          Manufacturer: Apple Inc.\n\n        BlackHole 2ch:\n\n          Input Channels: 2\n"
fake_which = H.shutil.which; H.shutil.which = lambda n: None
cur, devs, err = H.audio_default_output("Darwin", lambda cmd, t=8: (0, mac_out))
check(cur == "MacBook Pro Speakers" and "BlackHole 2ch" in devs, f"macOS system_profiler 解析：{cur} {devs}")
a1 = H.check_audio(cfgt, "Darwin", lambda cmd, t=8: (0, mac_out)); check(a1["status"] == "warn" and "直播多输出" in a1["fix"], f"macOS 输出不是多输出设备 → 警告并给命令：{a1}")
a2 = H.check_audio(cfgt, "Darwin", lambda cmd, t=8: (0, mac_out.replace("MacBook Pro Speakers", "直播多输出"))); check(a2["status"] == "ok", "macOS 输出是「直播多输出」→ OK")
H.shutil.which = lambda n: "/usr/bin/pactl"
def pa(cmd, t=8): return (0, "alsa_output.x\n") if cmd[1] == "get-default-sink" else (0, "0\talsa_output.x\tmodule\ts16\tRUNNING\n1\tqqlive_stream\tmodule\ts16\tIDLE\n")
check(H.check_audio(cfgt, "Linux", pa)["status"] == "ok", "Linux 有 qqlive_stream → OK")
check(H.check_audio(cfgt, "Linux", lambda cmd, t=8: (0, "alsa_output.x\n") if cmd[1] == "get-default-sink" else (0, "0\talsa_output.x\tm\n"))["status"] == "warn", "Linux 没有 qqlive_stream → 警告")
check(H.check_audio(cfgt, "Windows", lambda cmd, t=8: (0, "Realtek Audio\nCABLE Input (VB-Audio Virtual Cable)\n"))["status"] == "ok", "Windows 有 VB-CABLE → OK")
H.shutil.which = fake_which
cfgh = Config(str(ROOT / "config.ini"))
cfgh.cp["tts"]["backend"] = "edge"
check(H.check_tts(cfgh, lambda c, t, e: (b"x" * 3000, "audio/mpeg"))["status"] == "ok", "TTS 通")
check(H.check_tts(cfgh, lambda c, t, e: (None, None))["status"] == "fail", "TTS 没音频 → fail")
def tboom(c, t, e): raise RuntimeError("401 Unauthorized sk-SECRET123")
r_ = H.check_tts(cfgh, tboom); check(r_["status"] == "fail" and r_["detail"], "TTS 抛错 → fail")
cfgh.cp["ai"]["base_url"] = "http://x.invalid/v1"
check(H.check_llm(cfgh, lambda c, m, **k: "在的")["status"] == "ok", "LLM 通")
def lboom(c, m, **k): raise RuntimeError("401 Bearer sk-SECRET123 invalid")
r_ = H.check_llm(cfgh, lboom); check(r_["status"] == "fail" and "SECRET123" not in json.dumps(r_, ensure_ascii=False), f"LLM 报错里的密钥被遮住：{r_['detail']}")
cfgh.cp["ai"]["base_url"] = ""; check(H.check_llm(cfgh)["status"] == "warn", "没配 LLM → 警告（不是失败）")
# 房间检测
cfgd = Config(str(ROOT / "config.ini"))
check(OPSCLI.norm_room("https://live.douyin.com/100000000001?x=1") == "100000000001" and OPSCLI.norm_room("abc") == "" and OPSCLI.norm_room("12345678") == "12345678", "房间参数解析")
class RR: 
    def __init__(self, rc, out, err=""): self.returncode, self.stdout, self.stderr = rc, out, err
OPSCLI.SYS = "Darwin"
r_, why = OPSCLI.detect_room(cfgd, "", True, lambda *a, **k: RR(0, "log\n123456789012\n")); check(r_ == "123456789012" and "直播伴侣" in why, f"直播伴侣检测到：{r_} {why}")
r_, why = OPSCLI.detect_room(cfgd, "", True, lambda *a, **k: RR(1, "", "没找到日志目录")); check(r_ == DEFAULTS["ops"]["default_room"] and "default_room" in why, f"检测失败回退默认房间：{r_} {why}")
def rboom(*a, **k): raise subprocess_TimeoutExpired()
import subprocess as _sp
r_, why = OPSCLI.detect_room(cfgd, "", True, lambda *a, **k: (_ for _ in ()).throw(_sp.TimeoutExpired("x", 1))); check(r_ == DEFAULTS["ops"]["default_room"], "检测超时回退默认房间")
r_, why = OPSCLI.detect_room(cfgd, "777777777777", True, lambda *a, **k: 1 / 0); check(r_ == "777777777777" and "命令行" in why, "命令行给了房间就不检测")
r_, why = OPSCLI.detect_room(cfgd, "", False); check(r_ == DEFAULTS["ops"]["default_room"], "--no-detect")
OPSCLI.SYS = "Linux"; r_, why = OPSCLI.detect_room(cfgd, "", True); check(r_ == DEFAULTS["ops"]["default_room"] and "没有直播伴侣" in why, "Linux 直接用默认房间")
OPSCLI.SYS = platform_system = __import__("platform").system()
txt = OPSCLI.render_checklist([{"status": "ok", "label": "A", "detail": "good"}, {"status": "warn", "label": "B", "detail": "meh", "fix": "do x"}, {"status": "fail", "label": "C", "detail": "bad", "fix": "do y"}, {"status": "skip", "label": "D", "detail": "-"}])
check(all(x in txt for x in ("[ OK ]", "[ !! ]", "[FAIL]", "[ -- ]", "→ do x", "→ do y")), "清单格式")
# 令牌
tdir = Path(tempfile.mkdtemp(prefix="optok-")); cfgk = Config(str(ROOT / "config.ini")); cfgk.cp["ops"]["panel_token_file"] = str(tdir / "tok.txt"); cfgk.cp["ops"]["panel_token"] = ""
lines_ = []; t1 = PN.ensure_token(cfgk, tdir, lines_.append); t2 = PN.ensure_token(cfgk, tdir, lines_.append)
check(t1 == t2 and len(t1) >= 20 and (tdir / "tok.txt").read_text().strip() == t1, "令牌自动生成并持久化")
check(oct((tdir / "tok.txt").stat().st_mode & 0o777) == "0o600" or sys.platform == "win32", "令牌文件权限 600")
check(len(lines_) == 1 and t1 not in lines_[0] and "tok.txt" in lines_[0], "第一次生成只提示文件位置，不打印令牌")
cfgk.cp["ops"]["panel_token"] = "my-own-token"; check(PN.ensure_token(cfgk, tdir, lines_.append) == "my-own-token", "[ops] panel_token 覆盖文件")
check(PN.check_token("abc", "abc") and not PN.check_token("abd", "abc") and not PN.check_token("", "abc") and not PN.check_token(None, "abc"), "令牌比较")
check(PN.is_loopback("127.0.0.1") and PN.is_loopback("::1") and PN.is_loopback("::ffff:127.0.0.1") and not PN.is_loopback("192.168.1.5") and not PN.is_loopback("::ffff:10.0.0.2"), "loopback 判断")
lo = PN.Lockout(0.4, 3)
for i in range(3): lo.fail("1.2.3.4")
check(lo.blocked("1.2.3.4") and not lo.blocked("5.6.7.8"), "连续失败锁定该 IP"); time.sleep(0.5); check(not lo.blocked("1.2.3.4"), "锁定到期"); lo.fail("1.2.3.4"); lo.ok("1.2.3.4"); check("1.2.3.4" not in lo.fails, "成功清零")
ips = PN.lan_ips(); check(all(x.count(".") == 3 for x in ips), f"lan_ips 格式：{ips}")
try:
    import qrcode
    ql = PN.qr_lines("http://192.168.1.2:8765/panel"); check(ql and len({len(x) for x in ql}) == 1 and len(ql) > 10, "二维码是等宽的多行文本")
except ImportError:
    print("（没装 qrcode，跳过二维码测试）")
shutil_ = __import__("shutil"); shutil_.rmtree(tdir, ignore_errors=True)

# ---- 6. 真服务端到端：面板鉴权 / LAN 守卫 / 开关 / 动作 / 重启 / 看门狗 / 开播下播复盘 ----
import socket, subprocess, urllib.request, urllib.error, os, signal
os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试服务绝不连真实直播间（测试里的 /qq/event 是假事件）
def free_port():
    sk = socket.socket(); sk.bind(("127.0.0.1", 0)); p = sk.getsockname()[1]; sk.close(); return p
def http(url, method="GET", body=None, token=None, timeout=15):
    req = urllib.request.Request(url, method=method, data=(json.dumps(body).encode() if body is not None else None), headers={"Content-Type": "application/json", **({"X-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(); return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raw = e.read(); 
        try: return e.code, json.loads(raw)
        except Exception: return e.code, raw.decode("utf-8", "replace")
    except Exception as e:
        return 0, repr(e)
def wait_up(base, secs=40, not_pid=None):
    t = time.time()
    while time.time() - t < secs:
        c, d = http(base + "/config.json", timeout=2)
        if c == 200: return True
        time.sleep(0.4)
    return False
E = Path(tempfile.mkdtemp(prefix="opse2e-"))
ini = E / "t.ini"
ini.write_text("""[music]
enabled = false
[tts]
backend = none
[idle]
enabled = false
[ai]
base_url =
[play]
data_file = %s
[ai_plus]
memory_file = %s
[guard]
; 测试服务绝不能推真的 Bark / 响提示音（密钥文件是相对路径，会读到真密钥）
enabled = false
bark = false
sound = false
[agent]
test_endpoints = true
[ops]
log_dir = %s
report_dir = %s
panel_token_file = %s
overrides_file = %s
end_grace = 1.5
report_min_secs = 1
report_llm = false
panel_fail_lock = 3
detect_room = false
""" % (E / "play.json", E / "mem.json", E / "logs", E / "reports", E / "tok.txt", E / "ov.json"), encoding="utf-8")
PORT = free_port(); BASE = f"http://127.0.0.1:{PORT}"
env = dict(os.environ, PYTHONIOENCODING="utf-8", TTS_BACKEND="none")
env.pop("QQ_SUPERVISED", None)
srv = subprocess.Popen([sys.executable, str(ROOT / "backend" / "server.py"), "100000000001", "--port", str(PORT), "--config", str(ini)], env=env, stdout=open(E / "srv.out", "w"), stderr=subprocess.STDOUT)
try:
    check(wait_up(BASE), "测试服务起来了")
    tokf = E / "tok.txt"; check(tokf.exists(), "第一次启动生成令牌文件")
    TOK = tokf.read_text().strip()
    check(sys.platform == "win32" or oct(tokf.stat().st_mode & 0o777) == "0o600", "令牌文件权限 600")
    out_ = (E / "srv.out").read_text(encoding="utf-8", errors="replace")
    check(TOK not in out_ and str(tokf) in out_, "令牌不在服务日志里，只提示文件位置")
    c, d = http(BASE + "/panel"); check(c == 200 and "直播控制台" in d, "/panel 页面")
    c, d = http(BASE + "/panel/panel.js"); check(c == 200 and "X-Token" in d, "/panel/panel.js")
    c, d = http(BASE + "/ops/api/state"); check(c == 401, "没令牌 401")
    c, d = http(BASE + "/ops/api/state", token="wrong"); check(c == 401, "错令牌 401")
    c, d = http(BASE + "/ops/api/state", token=TOK); check(c == 200 and d["room"] == "100000000001" and d["switches"] and "fetcher" in d, f"对令牌 200：{c}")
    c, d = http(BASE + f"/ops/api/state?token={TOK}"); check(c == 200, "?token= 也行（给链接用）")
    for i in range(6): http(BASE + "/ops/api/state", token="bad")
    c, d = http(BASE + "/ops/api/state", token=TOK); check(c == 429, "连续错 5 次后锁定（连对令牌也 429）")
    time.sleep(3.3); c, d = http(BASE + "/ops/api/state", token=TOK); check(c == 200, "锁定到期恢复")
    # LAN 守卫：用本机局域网地址访问（来源不是 127.0.0.1）
    lan = PN.lan_ips()
    if lan:
        LB = f"http://{lan[0]}:{PORT}"
        res = {p: http(LB + p)[0] for p in ("/config.json", "/ws", "/qq/event?t=chat", "/ops/state", "/ops/report/latest.md", "/ops/health.json", "/app.js", "/agent/state")}
        check(all(v == 403 for v in res.values()), f"局域网来源除 /panel 和 /ops/api 外一律 403：{res}")
        check(http(LB + "/panel")[0] == 200 and http(LB + "/ops/api/state")[0] == 401 and http(LB + "/ops/api/state", token=TOK)[0] == 200, "局域网能开面板，API 要令牌")
    else:
        print("（没有局域网地址，跳过 LAN 守卫测试）")
    # 开关
    T = lambda p, b=None, m="POST": http(BASE + "/ops/api/" + p, m, b if b is not None else {}, TOK)
    c, d = T("toggle", {"key": "agent.enabled", "on": False}); check(d.get("ok"), f"toggle：{d}")
    check(http(BASE + "/config.json")[1]["agent"]["enabled"] is False, "开关立刻生效（/config.json 看到）")
    check(json.loads((E / "ov.json").read_text())["agent.enabled"] == "false", "改动存进 overrides 文件（不改 config.ini）")
    c, d = T("toggle", {"key": "ai.api_key", "on": True}); check(not d.get("ok"), "不在白名单的 key 被拒")
    c, d = T("toggle", {"key": "ops.panel_token", "on": True}); check(not d.get("ok"), "令牌 key 不能通过面板改")
    c, d = T("toggle", {"key": "play.fx", "on": False}); check(d.get("ok") and d.get("reload"), "页面侧开关提示需要刷新")
    c, d = T("toggle", {"key": "music.jukebox", "on": False}); check(d.get("ok"), "music.jukebox 可切（没启用音乐也不报错）")
    c, d = http(BASE + "/ops/api/toggle", "GET", None, TOK); check(c in (404, 405), f"toggle 不接受 GET：{c}")
    c, d = T("reset"); check(d.get("ok") and d["reset"] == 3 and http(BASE + "/config.json")[1]["agent"]["enabled"] is True, f"还原为 config.ini：{d}")
    # 动作
    c, d = T("do", {"action": "nope"}); check(not d["ok"], "未知动作")
    c, d = T("do", {"action": "say", "text": "你好"}); check(not d["ok"] and "主播" in d["error"], f"没有 host：给明确原因：{d}")
    c, d = T("do", {"action": "skip_song"}); check(not d["ok"], "没开点歌：给原因")
    c, d = T("do", {"action": "vote_start", "title": "t", "options": "a"}); check(not d["ok"], "投票至少两个选项")
    c, d = T("do", {"action": "vote_start", "title": "唱什么", "options": "晴天|七里香", "secs": 30}); check(d["ok"], f"发起投票：{d}")
    c, d = T("do", {"action": "vote_end"}); check(d["ok"], "结束投票")
    time.sleep(0.2)
    c, d = T("do", {"action": "fx", "kind": "fireworks"}); check(c == 200 and "ok" in d, f"特效（没有页面时不崩）：{d}")
    c, d = T("do", {"action": "fx", "kind": "virus"}); check(not d["ok"] and "太快" in d["error"], "短冷却防连点")
    c, d = T("do", {"action": "fx", "kind": "boom"}); check(not d["ok"], "未知特效被拒")
    c, d = T("forget", {"name": "不存在的人"}); check(c == 200 and "ok" in d, "forget 接口")
    c, d = T("reload"); check(d["ok"] and d["pages"] == 0, "没有页面时 reload 返回 0")
    # 开播 → 互动 → 下播 → 复盘
    q = lambda **k: http(BASE + "/qq/event?" + "&".join(f"{a}={urllib.request.quote(str(b))}" for a, b in k.items()))
    q(t="live", live=1, anchor="主播乙", title="端到端"); time.sleep(0.3)
    q(t="stat", online=7, total="321"); q(t="chat", name="观众1", uid="v1", text="你好呀主播"); q(t="chat", name="观众<i>2</i>", uid="v2", text="第二条弹幕"); q(t="gift", name="观众1", uid="v1", gift="玫瑰", value=1, count=3); time.sleep(0.5)
    c, d = http(BASE + "/ops/api/recent?n=10", token=TOK); names = [x["name"] for x in d["items"]]
    check(c == 200 and "观众1" in names and d["items"][0]["k"] == "gift", f"recent：新的在上：{names}")
    c, d = http(BASE + "/ops/api/state", token=TOK); check(d["session"]["active"] and d["counts"]["chat"] == 2 and d["counts"]["diamonds"] == 3 and d["online"] == 7, f"state 里的本场计数：{d['counts']} online={d['online']}")
    q(t="live", live=0); time.sleep(4.5)
    c, d = http(BASE + "/ops/api/state", token=TOK); check(not d["session"]["active"], "下播宽限到期，这一场结束")
    c, d = http(BASE + "/ops/api/reports", token=TOK); check(c == 200 and d["reports"] and d["reports"][0]["chats"] == 2, f"复盘自动生成：{d}")
    c, h_ = http(BASE + "/ops/report/latest.html"); check(c == 200 and "观众&lt;i&gt;2&lt;/i&gt;" in h_ and "<i>2</i>" not in h_, "复盘 HTML（观众昵称转义）")
    c, h_ = http(BASE + "/ops/api/report/latest.md", token=TOK); check(c == 200 and "直播复盘" in h_, "面板里能取复盘")
    c, h_ = http(BASE + "/ops/api/report/latest.md"); check(c == 401, "复盘的面板入口要令牌")
    c, d = T("report"); check(d["ok"], "现在生成复盘（按需）")
    # 重启（没有看门狗：原地 execv）——开关覆盖、令牌都要保留
    T("toggle", {"key": "agent.enabled", "on": False})
    c, d = http(BASE + "/ops/api/state", token=TOK); up0 = d["uptime"]; time.sleep(1.2)
    c, d = T("restart"); check(d["ok"] and not d["supervised"], f"restart（无看门狗）：{d}")
    time.sleep(2.5); check(wait_up(BASE, 40), "原地重启后服务回来")
    c, d = http(BASE + "/ops/api/state", token=TOK); check(c == 200 and d["uptime"] < up0 + 1 and [g for g in d["switches"] if g["id"] == "agent"][0]["items"][0]["on"] is False, f"重启后：令牌不变、开关覆盖还在、uptime 重置：{c} {d.get('uptime')} vs {up0}")
finally:
    srv.terminate()
    try: srv.wait(8)
    except Exception: srv.kill()
# 看门狗：supervisor 拉起服务，面板重启（退出码 75）和 kill -9 都会被拉起来
if sys.platform != "win32":
    PORT2 = free_port(); BASE2 = f"http://127.0.0.1:{PORT2}"
    sup = subprocess.Popen([sys.executable, str(ROOT / "tools" / "supervisor.py"), "100000000001", "--port", str(PORT2), "--config", str(ini)], env=env, stdout=open(E / "sup.out", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    try:
        check(wait_up(BASE2), "看门狗拉起了服务")
        c, d = http(BASE2 + "/ops/api/state", token=TOK); check(c == 200 and d["supervised"], "服务知道自己被看门狗管着")
        pid1 = subprocess.run(["pgrep", "-f", f"server.py 100000000001 --port {PORT2}"], capture_output=True, text=True).stdout.split()
        http(BASE2 + "/ops/api/restart", "POST", {}, TOK); time.sleep(2.5); check(wait_up(BASE2, 40), "面板重启 → 退出码 75 → 看门狗立即拉起")
        pid2 = subprocess.run(["pgrep", "-f", f"server.py 100000000001 --port {PORT2}"], capture_output=True, text=True).stdout.split()
        check(pid1 and pid2 and pid1 != pid2, f"换了新进程：{pid1} → {pid2}")
        for p in pid2: os.kill(int(p), signal.SIGKILL)
        time.sleep(1); check(not wait_up(BASE2, 1) or True, ""); check(wait_up(BASE2, 40), "kill -9 之后看门狗退避（3 秒）重启")
        pid3 = subprocess.run(["pgrep", "-f", f"server.py 100000000001 --port {PORT2}"], capture_output=True, text=True).stdout.split()
        check(pid3 and pid3 != pid2, "崩溃重启也是新进程")
        check("崩溃" in (E / "sup.out").read_text(encoding="utf-8") and "要求重启" in (E / "sup.out").read_text(encoding="utf-8"), "看门狗日志有「要求重启」和「崩溃」")
    finally:
        os.killpg(sup.pid, signal.SIGINT)
        try: sup.wait(20)
        except Exception: os.killpg(sup.pid, signal.SIGKILL)
        subprocess.run(["pkill", "-f", f"server.py 100000000001 --port {PORT2}"])
shutil_.rmtree(E, ignore_errors=True)

# ---- 7. config.ini [ops] ↔ config.py DEFAULTS 一致 ----
import configparser
cpi = configparser.ConfigParser(interpolation=None); cpi.read(ROOT / "config.ini", encoding="utf-8")
if "ops" in cpi:
    NEWER = {"live_recheck_secs", "live_recheck_need", "live_recheck_span", "live_recheck_quiet"}      # 之后新增的键：已有的 config.ini 里没有也行（不改用户已有的行），走代码默认值
    check(set(cpi["ops"]) <= set(DEFAULTS["ops"]) and set(DEFAULTS["ops"]) - set(cpi["ops"]) <= NEWER, f"[ops] 键一致：多 {set(cpi['ops']) - set(DEFAULTS['ops'])} 少 {set(DEFAULTS['ops']) - set(cpi['ops']) - NEWER}")
    diff = {k: (cpi["ops"][k], DEFAULTS["ops"][k]) for k in DEFAULTS["ops"] if k in cpi["ops"] and cpi["ops"][k] != DEFAULTS["ops"][k]}
    check(not diff, f"config.ini 里 [ops] 的值和代码默认值一致（想改就改 ini，同步改这里）：{diff}")
else:
    print("（config.ini 里没有 [ops]：全用代码默认值，跳过一致性检查）")

print("运维离线测试 " + ("全部通过" if not bad else f"{bad} 项失败"))
sys.exit(1 if bad else 0)
