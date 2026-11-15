# -*- coding: utf-8 -*-
"""真人验证守护（[guard]）测试：日志信号解析、日志尾随、Bark（含降级与密钥遮蔽）、提示音设备选择（不进直播）、窗口兜底、冷却 / 提醒 / 补发、
   抓取器「连着时复查下播」、真服务端到端（面板红条 / 测试推送 / 开关 / 日志里没有密钥）。
   python tools/test_guard.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, re, socket, subprocess, sys, tempfile, threading, time, types, urllib.request, urllib.error
os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试服务绝不连真实直播间（测试里的 /qq/event 是假事件）
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from host.config import Config
from ops import guard as G

bad = 0
def check(cond, msg):
    global bad
    if not cond:
        bad += 1; print("FAIL", msg)

KEY = "AbCdEfGhIjKlMnOpQrStUv"            # 22 位，和真密钥同样长，纯测试用
L_OPEN = "[2026-11-15T07:19:48.197.053] [INFO] <render> [VERIFY_DECISION_MESSAGE] evt=verify-decision-message-open room_id=7708169459873139466 timeout=120 current_audience=1 check_reason=adra_punish_center"
L_IDENT = "[2026-11-15T07:19:48.197.628] [INFO] <main> [WINDOW] evt=identify-open check_reason=adra_punish_center current_audience=1 timeout=120"
L_WIN = '[2026-11-15T07:19:48.242.206] [INFO] <main> [WINDOW_DIAG] evt=window-state label=人机交互弹窗 id=2 event=created state={"bounds":{"height":520,"width":380,"x":1530,"y":460}}'
L_WIN_MOVE = '[2026-11-15T07:22:08.747.794] [INFO] <main> [WINDOW_DIAG] evt=window-state label=人机交互弹窗 id=2 event=move state={"bounds":{"height":294}}'
L_CLOSE = "[2026-11-15T07:22:02.298.193] [INFO] <render> [START_LIVE_EXTERNAL_CLOSE] evt=external-live-close-finished source=heartbeat_room_closed room_id=7708169459873139466 stream_id=120440150385492454 stop_ok=true"
L_STOP_LOCAL = "[2026-11-14T20:22:40.531.942] [INFO] <main> [MESSAGE] evt=message-entities-clear lifecycle_status=ENDED lifecycle_reason=local_stop room_id=7708001364978338610 deleted_rows=4"
L_STOPOK = "[2026-11-14T20:22:40.904.181] [INFO] <render> [START_LIVE] evt=stop-live-ok mode=default room_id=7708001364978338610 stream_id=120437521738629596"
NOISE = [
    "[2026-11-15T07:19:38.981.339] [INFO] <main> [MESSAGE] evt=message-worker-state kind=public-room room_id=7708169459873139466 status=connected phase=ws-heartbeat transport=websocket attempts=1 last_error=",
    "[2026-11-15T07:15:00.255.621] [INFO] <main> [AUTH] evt=session-sync-start auth_cookie_count=51 targets=https://streamingtool.douyin.com,https://webcast.amemv.com,https://verify.snssdk.com",
    "      list_fans_group_url: 'sslocal://webcast_lynxview?height=754&radius=8&gravity=bottom&type=popup&animation_type=present'",
    "  Warning: Missing `Description` or `aria-describedby={undefined}` for {DialogContent}.",
    "[2026-11-15T07:19:49.339.733] [INFO] <render> [VERIFY_DECISION] evt=verify-decision-prefetch-success version=4.0.10",
    L_WIN_MOVE, "", "x" * 5000,
]

# ---- 1. 日志信号解析 ----
e = G.parse_line(L_OPEN)
check(e and e["kind"] == "verify" and e["timeout"] == 120 and e["reason"] == "adra_punish_center", f"验证弹窗（VERIFY_DECISION_MESSAGE）：{e}")
check(abs(e["ts"] - time.mktime(time.strptime("2026-11-15 07:19:48", "%Y-%m-%d %H:%M:%S")) - 0.197) < 0.01, "日志时间戳解析（本地时间 + 毫秒）")
e = G.parse_line(L_IDENT); check(e and e["kind"] == "verify" and e["timeout"] == 120, "identify-open 也算验证弹窗")
e = G.parse_line(L_WIN); check(e and e["kind"] == "verify", "「人机交互弹窗」窗口创建也算")
e = G.parse_line(L_CLOSE); check(e and e["kind"] == "closed" and e["reason"] == "heartbeat_room_closed", f"平台关播：{e}")
check(G.parse_line(L_STOP_LOCAL)["kind"] == "local_stop" and G.parse_line(L_STOPOK)["kind"] == "local_stop", "自己结束直播（local_stop / stop-live-ok）")
for ln in NOISE: check(G.parse_line(ln) is None, f"噪声行不触发：{ln[:60]}")
x = G.parse_line("[2026-11-15T08:00:00.000.000] [INFO] <main> [FOO] hello CAPTCHA_SHOWN now", [re.compile("CAPTCHA_SHOWN")])
check(x and x["kind"] == "custom", "extra_patterns 自定义关键字")

# ---- 2. 日志尾随 ----
T = Path(tempfile.mkdtemp(prefix="guard-"))
ld = T / "logs"; ld.mkdir()
a = ld / "2026-11-15-07-14-59.log"
a.write_text("\n".join(NOISE[:2] + [L_OPEN, NOISE[0]]) + "\n", encoding="utf-8")
tl = G.LogTail(ld)
check(tl.available(), "有日志目录")
ev0 = tl.scan_tail(); check([x["kind"] for x in ev0] == ["verify"], f"启动时扫末尾：{ev0}")
check(tl.poll() == [], "没有新内容就没有信号")
with open(a, "a", encoding="utf-8") as f: f.write(L_CLOSE[:60])
check(tl.poll() == [], "半行不处理（等写完）")
with open(a, "a", encoding="utf-8") as f: f.write(L_CLOSE[60:] + "\n" + NOISE[0] + "\n")
r = tl.poll(); check([x["kind"] for x in r] == ["closed"], f"半行补全后识别：{r}")
b = ld / "2026-11-15-09-00-00.log"; time.sleep(0.02); b.write_text(L_IDENT + "\n", encoding="utf-8")
os.utime(b, (time.time() + 5, time.time() + 5))
r = tl.poll(); check([x["kind"] for x in r] == ["verify"], f"直播伴侣重启换了新日志：从头读新文件 {r}")
check(G.LogTail(T / "nope").available() is False, "目录不存在 → 不可用（走窗口兜底）")
tl2 = G.LogTail(ld); tl2.poll(); check(tl2.poll() == [], "第一次 poll 从末尾开始，不重放历史")

# ---- 3. 密钥遮蔽 ----
u = G.bark_url("https://api.day.app", KEY, "GG-Bond 直播", "测试", "critical", "qq-live")
check(u.startswith(f"https://api.day.app/{KEY}/") and "level=critical" in u and "sound=alarm" in u and "group=qq-live" in u, "Bark URL 形状")
check(KEY not in G.mask_text(u) and KEY not in G.mask_text(f"HTTPSConnectionPool: Max retries /{KEY}/x?level=critical", KEY), "mask_text 遮住 URL 里的密钥")
check(KEY not in G.mask_text("boom " + KEY, KEY), "mask_text 遮住裸密钥")
check("***" in G.mask_text("GET https://api.day.app/abcdefghijklmnopqrstuv/title/body"), "没提供密钥时也按 URL 形状遮")

# ---- 4. Bark：成功 / critical 失败降级 / 全失败 / 异常里带 URL ----
def cfgx(**o):
    d = {"enabled": "true", "bark": "true", "bark_key_file": str(T / "key.txt"), "cooldown": "60", "sound": "true", "state_file": str(T / "st.json"), "log_dir": str(ld), "remind_at": "", "drop_grace": "0"}
    d.update({k: str(v) for k, v in o.items()})
    ini = T / "c.ini"; ini.write_text("[guard]\n" + "\n".join(f"{k} = {v}" for k, v in d.items()) + "\n", encoding="utf-8")
    return Config(str(ini))
(T / "key.txt").write_text(KEY + "\n", encoding="utf-8")
class R_:
    def __init__(s, code=200, js=None): s.status_code, s._j = code, js if js is not None else {"code": 200}
    def json(s): return s._j
urls = []
def ok_get(url, t): urls.append(url); return R_()
ok, m = G.bark_push(cfgx(), "GG-Bond 直播", "测试：真人验证提醒已就绪", ok_get)
check(ok and "critical" in m and KEY not in m and "level=critical" in urls[-1], f"Bark 成功：{m}")
urls.clear()
def crit_fail(url, t):
    urls.append(url)
    return R_(400, {"code": 400}) if "level=critical" in url else R_()
ok, m = G.bark_push(cfgx(), "t", "b", crit_fail)
check(ok and "timeSensitive" in m and len(urls) == 2 and "level=timeSensitive" in urls[1] and KEY not in m, f"critical 失败降级 timeSensitive：{m}")
def exc_get(url, t): raise RuntimeError(f"HTTPSConnectionPool(host='api.day.app'): Max retries exceeded with url: {url[len('https://api.day.app'):]}")
ok, m = G.bark_push(cfgx(), "t", "b", exc_get)
check(not ok and KEY not in m and "失败" in m, f"全失败：说明里没有密钥：{m}")
(T / "key2.txt").write_text("", encoding="utf-8")
ok, m = G.bark_push(cfgx(bark_key_file=str(T / "key2.txt")), "t", "b", ok_get); check(not ok and "空" in m, "密钥文件是空的")
ok, m = G.bark_push(cfgx(bark_key_file=str(T / "none.txt")), "t", "b", ok_get); check(not ok and "没有" in m, "没有密钥文件")

# ---- 5. 提示音：只走实体音箱，绝不进直播（BlackHole / 直播多输出）----
OUTS = [("Mi monitor", "61A9"), ("EDIFIER M30", "AppleUSB:Jieli"), ("BlackHole 2ch", "BlackHole2ch_UID"), ("Mac mini扬声器", "BuiltInSpeakerDevice"), ("直播多输出", "qqlive-multiout")]
names = [n for n, _ in G.pick_devices(OUTS, "auto")]
check(names == ["EDIFIER M30", "Mac mini扬声器"], f"auto 选实体音箱（排除 BlackHole / 直播多输出 / 显示器）：{names}")
check([n for n, _ in G.pick_devices(OUTS, "edifier")] == ["EDIFIER M30"], "sound_device 写名字")
check(G.pick_devices(OUTS, "BlackHole") == [] and G.pick_devices(OUTS, "直播多输出") == [], "写了虚拟设备名也不行")
check(G.pick_devices([("BlackHole 2ch", "x"), ("直播多输出", "y")], "auto") == [], "只有虚拟设备 → 不发声")
ran = []
ok, m = G.play_alarm(cfgx(sound="true", sound_file="/System/Library/Sounds/Sosumi.aiff", sound_repeat=3), run=lambda a: ran.append(a), outputs=OUTS)
check(ok and len(ran) == 2 and all(a[:3] == ["osascript", "-l", "JavaScript"] for a in ran) and "AppleUSB:Jieli" in ran[0][4] and "BlackHole" not in " ".join(x[4] for x in ran) and "i<3" in ran[0][4], f"播放命令：{m}")
ok, m = G.play_alarm(cfgx(sound="true"), run=lambda a: ran.append(a), outputs=[("BlackHole 2ch", "x")]); check(not ok and "虚拟" in m, "只有虚拟设备时不发声：" + m)
ok, m = G.play_alarm(cfgx(sound="false"), run=lambda a: ran.append(a), outputs=OUTS); check(not ok, "sound=false")

# ---- 6. 窗口兜底 ----
W0 = [{"id": 1, "owner": "抖音直播伴侣", "name": "抖音直播伴侣", "layer": 0, "w": 1280, "h": 720}]
W1 = W0 + [{"id": 7, "owner": "抖音直播伴侣", "name": "", "layer": 0, "w": 370, "h": 226}]
check(G.new_small_windows(W0, {1}) == [] and G.new_small_windows(W1, {1})[0]["id"] == 7, "新的小窗口 = 疑似弹窗；主窗口不算")
check(G.new_small_windows([{"id": 9, "owner": "x", "layer": 0, "w": 1280, "h": 720}], set()) == [], "新的大窗口不算")
fake = json.dumps([{"id": 1, "owner": "抖音直播伴侣", "name": "a", "layer": 0, "w": 1280, "h": 720}, {"id": 2, "owner": "Finder", "name": "", "layer": 0, "w": 300, "h": 300}])
lw = G.list_windows(["直播伴侣"], run=lambda a: fake); check(lw and len(lw) == 1 and lw[0]["id"] == 1, "只留直播伴侣的窗口")
check(G.list_windows(["直播伴侣"], run=lambda a: "not json") is None, "解析失败返回 None")

# ---- 7. Guard 本体（假 Ops）----
class FakeOps:
    def __init__(s, cfg):
        s.cfg = cfg; s.logs = []; s.stopped = threading.Event(); s.recs = []
        s.app = types.SimpleNamespace(default_room="100000000001")
    def on(s): return True
    def log(s, *a): s.logs.append(" ".join(map(str, a)))
    def record(s, kind, /, **f): s.recs.append((kind, f))
def mk(now=None, **o):
    ops = FakeOps(cfgx(**o)); clock = {"t": now or time.time()}
    g = G.Guard(ops, now=lambda: clock["t"]); g.state_path = T / ("st%d.json" % time.time_ns())
    sent = []
    g.test_hooks = {"bark": lambda t, b: (sent.append((t, b)) or (True, "Bark 已推送（critical）")), "sound": lambda: (True, "提示音：EDIFIER M30"), "windows": lambda: None}
    return g, ops, clock, sent
def wait(fn, s=3):
    t = time.time()
    while time.time() - t < s:
        if fn(): return True
        time.sleep(0.02)
    return False
now = time.mktime(time.strptime("2026-11-15 07:19:50", "%Y-%m-%d %H:%M:%S"))
g, ops, clk, sent = mk(now)
g.handle_log(G.parse_line(L_OPEN))
check(wait(lambda: len(sent) == 1) and sent[0][0] == "GG-Bond 直播" and "真人验证" in sent[0][1] and "118 秒" in sent[0][1] or "11" in sent[0][1], f"验证弹窗 → Bark：{sent}")
check(g.alert and g.alert["kind"] == "verify" and g.snapshot()["alert"]["left"] in (117, 118, 119), f"面板红条 + 倒计时：{g.snapshot()['alert']}")
check(wait(lambda: "提示音" in g.alert["push"]) and "Bark 已推送" in g.alert["push"], "推送结果写进提醒里")
g.handle_log(G.parse_line(L_IDENT)); g.handle_log(G.parse_line(L_WIN)); time.sleep(0.1)
check(len(sent) == 1, "同一次弹窗的三条日志只推一次（冷却）")
check(any("冷却" in x for x in ops.logs), "冷却里记了日志")
clk["t"] = now + 61; g.handle_log(dict(G.parse_line(L_OPEN), ts=clk["t"])); check(wait(lambda: len(sent) == 2), "冷却过了可以再推")
# 提醒
g, ops, clk, sent = mk(now, remind_at="50,90", cooldown=60)
g.handle_log(G.parse_line(L_OPEN)); wait(lambda: len(sent) == 1)
clk["t"] = now + 10; g._remind_tick(); time.sleep(0.1); check(len(sent) == 1, "还没到 50 秒不提醒")
clk["t"] = now + 60; g._remind_tick(); check(wait(lambda: len(sent) == 2) and "还没处理" in sent[1][1], f"50 秒后提醒一次：{sent[-1]}")
g._remind_tick(); time.sleep(0.1); check(len(sent) == 2, "不重复提醒")
clk["t"] = now + 95; g._remind_tick(); check(wait(lambda: len(sent) == 3), "90 秒再提醒一次")
g, ops, clk, sent = mk(now, remind_at="50")
g.handle_log(G.parse_line(L_OPEN)); wait(lambda: len(sent) == 1); g.ack(); clk["t"] = now + 60; g._remind_tick(); time.sleep(0.1)
check(len(sent) == 1 and g.snapshot()["alert"] is None, "点「我已处理」后不再提醒，红条消失")
g, ops, clk, sent = mk(now, remind_at="50")
g.handle_log(G.parse_line(L_OPEN)); wait(lambda: len(sent) == 1); clk["t"] = now + 200; g._remind_tick(); time.sleep(0.1)
check(len(sent) == 1 and g.snapshot()["alert"] is None, "倒计时过了：不提醒，红条自己消失")
# 补发 / 不重复
g, ops, clk, sent = mk(now + 30)
g.catch_up([G.parse_line(L_OPEN), G.parse_line(L_CLOSE)]); check(wait(lambda: len(sent) == 2), f"启动时补发（弹窗仍在倒计时 + 刚被关播）：{sent}")
check(any("补发" in b for _, b in sent), "补发的话术带「补发」")
g.state_path.exists() and check(json.loads(g.state_path.read_text())["verify"] > 0, "记下已处理的日志时间")
g2, ops2, clk2, sent2 = mk(now + 30); g2.seen_ts = dict(g.seen_ts)
g2.catch_up([G.parse_line(L_OPEN), G.parse_line(L_CLOSE)]); time.sleep(0.1); check(len(sent2) == 0, "同样的历史再启动一次不重复提醒")
g3, ops3, clk3, sent3 = mk(now + 4000); g3.catch_up([G.parse_line(L_OPEN), G.parse_line(L_CLOSE)]); time.sleep(0.1); check(len(sent3) == 0, "太老的事件（超过 catchup_secs）不补发")
# 下播
g, ops, clk, sent = mk(now, drop_grace=0)
g.log_ok = True
g.on_event({"t": "live", "live": True}); g.on_event({"t": "live", "live": False}); check(wait(lambda: len(sent) == 1) and "断了" in sent[0][1], f"直播中下播 → 提醒：{sent}")
g, ops, clk, sent = mk(now, drop_grace=0); g.log_ok = True; g.last_local_stop = now - 20
g.on_event({"t": "live", "live": True}); g.on_event({"t": "end"}); time.sleep(0.2); check(len(sent) == 0, "日志说是自己点的结束 → 不提醒")
g, ops, clk, sent = mk(now, drop_grace=0); g.log_ok = True; g.last_log_closed = now - 5
g.on_event({"t": "live", "live": True}); g.on_event({"t": "end"}); time.sleep(0.2); check(len(sent) == 0, "「被平台关了」刚提醒过 → 不重复")
g, ops, clk, sent = mk(now, drop_grace=0); g.on_event({"t": "end"}); time.sleep(0.2); check(len(sent) == 0, "本来就没开播 → 不提醒")
g, ops, clk, sent = mk(now, drop_grace=0, drop_alert="false"); g.on_event({"t": "live", "live": True}); g.on_event({"t": "end"}); time.sleep(0.2); check(len(sent) == 0, "drop_alert=false")
g, ops, clk, sent = mk(now, drop_grace=0); g.on_event({"t": "live", "live": True}); g.on_event({"t": "end"}); time.sleep(0.2); check(len(sent) == 1, "没有日志可读时：下播就提醒")
# 窗口兜底
g, ops, clk, sent = mk(now, window_watch="auto", interval=10); g.log_ok = False
seq = [W0, W0, W1]; g.test_hooks["windows"] = lambda: seq[0] if len(seq) == 1 else seq.pop(0)
g._window_tick(); clk["t"] += 11; g._window_tick(); time.sleep(0.1); check(len(sent) == 0, "窗口没变化不提醒")
clk["t"] += 11; g._window_tick(); check(wait(lambda: len(sent) == 1) and "新窗口" in sent[0][1], f"出现新的小窗口 → 提醒：{sent}")
g, ops, clk, sent = mk(now, window_watch="auto"); g.log_ok = True; g._window_tick(); check(not g.win_active, "日志可用时 auto 不启用窗口兜底")
# 测试推送
g, ops, clk, sent = mk(now); g.test_push(); check(wait(lambda: len(sent) == 1) and sent[0] == ("GG-Bond 直播", "测试：真人验证提醒已就绪"), f"测试推送：{sent}")
g.test_push(); check(wait(lambda: len(sent) == 2), "测试推送不受冷却限制")
# 日志里没有密钥
g, ops, clk, sent = mk(now)
g.test_hooks = {}; g.cfg.cp["guard"]["bark"] = "true"
G_http = lambda url, t: (_ for _ in ()).throw(RuntimeError("boom " + url))
orig = G.bark_push
G.bark_push = lambda cfg, t, b, http_get=None: orig(cfg, t, b, G_http)
g.fire("verify", "verify", "x", deadline=now + 100); wait(lambda: "失败" in g.alert["push"])
G.bark_push = orig
blob = "\n".join(ops.logs) + json.dumps(g.snapshot(), ensure_ascii=False) + json.dumps(g.history, ensure_ascii=False)
check(KEY not in blob and "失败" in blob, "守护日志 / 状态 / 历史里没有密钥（Bark 异常带 URL 的情况）")

# ---- 8. 抓取器：连着时复查「还在直播吗」（强信号一起成立才算下播；接口抽风 / 空壳 JSON / 还在收消息都不算）----
from dy import fetcher as F
class WS:
    closed = 0
    def close(s): s.closed += 1
def mkf(**o):
    evs = []; f = F.DouyinFetcher("123", evs.append, log=lambda *a: None, opts=dict({"recheck": 30}, **o)); f.live = True
    f.last_msg_ts = time.time() - 600                       # 默认：已经 10 分钟没收到任何消息
    ws = WS(); clock = [1000.0]
    return f, evs, ws, clock
def run_checks(f, ws, results, clock, step=30):
    """依次喂接口结果；每次查询相隔 step 秒（假时钟）"""
    res = list(results)
    f._room_info = lambda tries=2: res.pop(0)
    real = F.time.time
    try:
        for _ in range(len(results)):
            F.time.time = lambda: clock[0]
            f._rc_busy = True; f._recheck_live(ws); clock[0] += step
    finally:
        F.time.time = real
ENDED = {"live": False, "status": 2}; LIVE = {"live": True, "status": 0}; EMPTY = {"live": False, "status": None}
ended = lambda evs: [x for x in evs if x["t"] == "end"]

f, evs, ws, ck = mkf(); f.last_msg_ts = ck[0] - 600
run_checks(f, ws, [LIVE, ENDED, ENDED], ck)
check(not ended(evs) and f._rc_off == 2, "两次「已结束」不够（要连续 3 次）")
f, evs, ws, ck = mkf(); f.last_msg_ts = ck[0] - 600
run_checks(f, ws, [ENDED, ENDED, ENDED], ck, step=30)
check(not ended(evs), "3 次但只隔了 60 秒（<90）还不算")
f, evs, ws, ck = mkf(); f.last_msg_ts = ck[0] - 600
run_checks(f, ws, [ENDED, ENDED, ENDED, ENDED], ck, step=30)
e = ended(evs)
check(len(e) == 1 and e[0]["reason"] == "recheck" and ws.closed == 1 and f.live is False and f.ended_at, f"连续 3+ 次已结束、跨度 ≥ 90 秒、一直没消息 → end + 断开：{evs}")
check(any(x["t"] == "live" and x["live"] is False for x in evs), "同时发 live=False")

# 复盘这次的误报：接口限流 / 风控返回的空壳 JSON（room_status 缺失）以前被当成「已结束」
f, evs, ws, ck = mkf(); f.last_msg_ts = ck[0] - 600
run_checks(f, ws, [EMPTY] * 6, ck)
check(not ended(evs) and f._rc_off == 0 and f.live is True, "空壳 JSON（没有 room_status）= 不知道，不是已结束")
f, evs, ws, ck = mkf(); f.last_msg_ts = ck[0] - 600
run_checks(f, ws, [ENDED, ENDED, EMPTY, ENDED, ENDED, None, ENDED, ENDED], ck)
check(not ended(evs), "中间夹着空壳 / 查不到 → 连续计数清零，不下播")
f, evs, ws, ck = mkf(); f.last_msg_ts = ck[0] - 600
run_checks(f, ws, [ENDED, ENDED, ENDED, LIVE, ENDED, ENDED, ENDED], ck)
check(not ended(evs), "中途又查到「直播中」→ 清零")
# 接口说结束，但弹幕 / 进场消息还在来 → 不信
f, evs, ws, ck = mkf(); f.last_msg_ts = ck[0] + 100
real = F.time.time
res = [ENDED] * 6; f._room_info = lambda tries=2: res.pop(0)
try:
    for i in range(6):
        ck[0] += 30; f.last_msg_ts = ck[0] - 5; F.time.time = lambda: ck[0]    # 每次查之前 5 秒还收到过消息
        f._rc_busy = True; f._recheck_live(ws)
finally: F.time.time = real
check(not ended(evs) and ws.closed == 0, "接口说已结束但消息还在来（5 秒前刚收到）→ 不当下播，不断开")
# 真实 _room_info：空壳 JSON → status None，live False，但复查不当结束
class R:
    def __init__(s, body): s.content = body; s.status_code = 200; s.cookies = {}
    def json(s): return json.loads(s.content)
import types
f = F.DouyinFetcher("123", lambda e: None, log=lambda *a: None)
f.session = types.SimpleNamespace(get=lambda *a, **k: R(b'{"data": {}}'), cookies={})
F.get__ac_signature = lambda *a: "sig"
class MR:
    def eval(s, *a): pass
    def call(s, *a): return "ab"
F.MiniRacer = MR
info = f._room_info(tries=1)
check(info is not None and info["status"] is None and info["live"] is False, f"_room_info：{{\"data\":{{}}}} 的 status 是 None（未知）：{info}")
f.session = types.SimpleNamespace(get=lambda *a, **k: R(('{"data": {"room_status": 2, "data": [{"title": "t"}]}}').encode()), cookies={})
info = f._room_info(tries=1); check(info["status"] == 2 and info["live"] is False, "room_status=2 → 明确已结束")

# ---- 8b. 守护：下播信号之后弹幕侧还有动静 / 抓取器又好了 → 不推送；真下播才推 ----
class FakeF:
    def __init__(s, **k): s.live = False; s.last_msg_ts = 0.0; s.connected = False; s.state = "offline"; s.__dict__.update(k)
def drop_case(ff, ev, mid=None):
    g_, ops_, clk_, sent_ = mk(drop_grace=0.3)
    ops_.fetcher_of_default = lambda: ff
    g_.on_event({"t": "live", "live": True}); g_.on_event(ev)
    if mid: time.sleep(0.1); mid()
    time.sleep(0.6)
    return sent_, ops_
RECHK = {"t": "end", "reason": "recheck"}; OFFL = {"t": "live", "live": False}; REAL_END = {"t": "end"}
sent_, o_ = drop_case(FakeF(last_msg_ts=time.time() - 600), RECHK); check(len(sent_) == 1, "真下播（接口复查：连接断了、10 分钟没消息）→ 推送")
sent_, o_ = drop_case(FakeF(last_msg_ts=time.time() - 10), RECHK); check(not sent_ and any("不推送" in l for l in o_.logs), "接口复查说结束，但 10 秒前还收到过消息 → 不推送")
sent_, o_ = drop_case(FakeF(live=True), OFFL); check(not sent_, "抓取器已经回到「直播中」→ 不推送")
sent_, o_ = drop_case(FakeF(last_msg_ts=time.time() - 30), OFFL); check(not sent_, "live=False 信号（重连时查不到房间）但 30 秒前还有消息 → 不推送")
sent_, o_ = drop_case(FakeF(last_msg_ts=time.time() - 3), REAL_END); check(len(sent_) == 1, "弹幕里真收到下播控制消息（status 3）→ 照推")
ff_ = FakeF(); sent_, o_ = drop_case(ff_, OFFL, mid=lambda: setattr(ff_, "last_msg_ts", time.time())); check(not sent_, "宽限期里又收到了消息 → 不推送")
sent_, o_ = drop_case(FakeF(last_msg_ts=time.time() - 600, connected=True, state="connected", live=None), OFFL); check(not sent_, "连接还连着（live 未知）→ 不推送")

# ---- 9. 真服务端到端 ----
def free_port():
    sk = socket.socket(); sk.bind(("127.0.0.1", 0)); p = sk.getsockname()[1]; sk.close(); return p
got = []
class H(BaseHTTPRequestHandler):
    def do_GET(s):
        got.append(s.path); s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers(); s.wfile.write(b'{"code":200,"message":"success"}')
    def log_message(s, *a): pass
bp = free_port(); hs = HTTPServer(("127.0.0.1", bp), H); threading.Thread(target=hs.serve_forever, daemon=True).start()
def http(url, method="GET", body=None, token=None, timeout=15):
    req = urllib.request.Request(url, method=method, data=(json.dumps(body).encode() if body is not None else None), headers={"Content-Type": "application/json", **({"X-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(); return r.status, (json.loads(raw) if raw[:1] in (b"{", b"[") else raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raw = e.read()
        try: return e.code, json.loads(raw)
        except Exception: return e.code, raw.decode("utf-8", "replace")
    except Exception as e:
        return 0, repr(e)
E = Path(tempfile.mkdtemp(prefix="guarde2e-")); eld = E / "mate"; eld.mkdir()
elog = eld / "2026-11-15-10-00-00.log"; elog.write_text(NOISE[0] + "\n", encoding="utf-8")
(E / "key.txt").write_text(KEY, encoding="utf-8")
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
[agent]
test_endpoints = true
[ops]
log_dir = %s
report_dir = %s
panel_token_file = %s
overrides_file = %s
detect_room = false
autoswitch = false
[guard]
bark_server = http://127.0.0.1:%d
bark_key_file = %s
log_dir = %s
state_file = %s
sound = false
cooldown = 2
remind_at =
drop_grace = 0
""" % (E / "play.json", E / "mem.json", E / "logs", E / "reports", E / "tok.txt", E / "ov.json", bp, E / "key.txt", eld, E / "gs.json"), encoding="utf-8")
PORT = free_port(); BASE = f"http://127.0.0.1:{PORT}"
env = dict(os.environ, PYTHONIOENCODING="utf-8", TTS_BACKEND="none"); env.pop("QQ_SUPERVISED", None)
srv = subprocess.Popen([sys.executable, str(ROOT / "backend" / "server.py"), "100000000001", "--port", str(PORT), "--config", str(ini)], env=env, stdout=open(E / "srv.out", "w"), stderr=subprocess.STDOUT)
try:
    up = False
    for _ in range(100):
        if http(BASE + "/config.json", timeout=2)[0] == 200: up = True; break
        time.sleep(0.4)
    check(up, "测试服务起来了")
    TOK = (E / "tok.txt").read_text().strip()
    def st(): return http(BASE + "/ops/api/state", token=TOK)[1]
    check(wait(lambda: st().get("guard", {}).get("log_watch"), 8), f"守护在盯日志：{st().get('guard')}")
    check(st()["guard"]["bark_key"] is True and KEY not in json.dumps(st()), "面板状态里只有「密钥已配置」，没有密钥")
    c, d = http(BASE + "/ops/api/do", "POST", {"action": "guard_test"}, TOK); check(c == 200 and d.get("ok"), f"测试推送按钮：{d}")
    check(wait(lambda: len(got) >= 1, 6), "本地 Bark 桩收到了请求")
    p = urllib.request.unquote(got[0]) if got else ""
    check(p.startswith(f"/{KEY}/GG-Bond 直播/测试：真人验证提醒已就绪") and "level=critical" in p and "sound=alarm" in p and "group=qq-live" in p, f"请求形状（标题 / 正文 / level / sound / group）：{p.replace(KEY, '<KEY>')}")
    a = st()["guard"]["alert"]; check(a and a["test"] and "测试" in a["body"], "测试提醒出现在面板状态里（黄条）")
    c, d = http(BASE + "/ops/api/do", "POST", {"action": "guard_ack"}, TOK); check(st()["guard"]["alert"] is None, "知道了 → 红条消失")
    got.clear()
    with open(elog, "a", encoding="utf-8") as f: f.write(L_OPEN.replace("2026-11-15T07:19:48", time.strftime("%Y-%m-%dT%H:%M:%S")) + "\n")
    check(wait(lambda: len(got) >= 1, 8), "日志里出现验证弹窗 → Bark 请求发出")
    a = st()["guard"]["alert"]; check(a and a["kind"] == "verify" and not a["test"] and a["left"] and a["left"] > 100, f"面板红条（verify + 倒计时）：{a}")
    check(KEY not in json.dumps(st()) and KEY not in json.dumps(http(BASE + "/ops/state")[1]), "状态接口里没有密钥")
    n = len(got); http(BASE + "/ops/api/do", "POST", {"action": "guard_ack"}, TOK)
    with open(elog, "a", encoding="utf-8") as f: f.write(L_OPEN.replace("2026-11-15T07:19:48", time.strftime("%Y-%m-%dT%H:%M:%S")) + "\n")
    time.sleep(1.0); check(len(got) == n, "冷却（2 秒）里的重复弹窗不再推")
    c, d = http(BASE + "/ops/api/toggle", "POST", {"key": "guard.bark", "on": False}, TOK); check(c == 200 and d["ok"], "面板开关：关 Bark")
    time.sleep(2.2); n = len(got)
    with open(elog, "a", encoding="utf-8") as f: f.write(L_OPEN.replace("2026-11-15T07:19:48", time.strftime("%Y-%m-%dT%H:%M:%S")) + "\n")
    check(wait(lambda: st()["guard"]["alert"] is not None, 6) and len(got) == n and "Bark 关了" in st()["guard"]["alert"]["push"], "Bark 关了：红条还在，不推手机")
    c, d = http(BASE + "/ops/api/toggle", "POST", {"key": "guard.enabled", "on": False}, TOK); check(c == 200, "守护总开关")
    c, d = http(BASE + "/ops/api/do", "POST", {"action": "guard_test"}, TOK); check(not d.get("ok"), "守护关了：测试推送被拒")
    c, d = http(BASE + "/panel/panel.js"); check("renderAlarm" in d and "guard_test" in d, "面板页面里有红条和测试按钮")
    time.sleep(0.5)
    out = (E / "srv.out").read_text(encoding="utf-8", errors="replace")
    blob = out + "".join(p.read_text(encoding="utf-8", errors="replace") for p in (E / "logs").rglob("*") if p.is_file())
    check(KEY not in blob, "服务日志和按场日志里没有密钥")
    check("[guard]" in out, "服务日志里有 [guard] 行")
finally:
    srv.terminate()
    try: srv.wait(8)
    except Exception: srv.kill()
    hs.shutdown()
import shutil
shutil.rmtree(T, ignore_errors=True); shutil.rmtree(E, ignore_errors=True)

# ---- 10. 配置：config.ini 和代码默认值一致 ----
from host.config import DEFAULTS
ci = Config(str(ROOT / "config.ini")); miss = []
if "guard" in ci.cp:
    for k in ci.cp["guard"]:
        if k not in DEFAULTS["guard"]: miss.append(k)
    check(not miss, f"config.ini [guard] 里有代码不认识的键：{miss}")
    for k, v in DEFAULTS["guard"].items():
        if k in ci.cp["guard"] and k not in ("bark_key_file",): check(str(ci.cp["guard"][k]) == str(v), f"config.ini [guard] {k} = {ci.cp['guard'][k]!r} 和默认值 {v!r} 不一致")
else:
    print("（config.ini 里还没有 [guard]，跳过一致性检查）")

# ---- 11. 真实日志回放（只在装了直播伴侣的机器上）：不能有误报 ----
ld_real = G.default_log_dir()
if ld_real and Path(ld_real).is_dir():
    cnt = {}
    for p in sorted(Path(ld_real).glob("*.log")):
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            ev = G.parse_line(ln)
            if ev: cnt[(p.name, ev["kind"])] = cnt.get((p.name, ev["kind"]), 0) + 1
    print("真实日志信号计数：", {f"{a}:{b}": n for (a, b), n in cnt.items()})
    verify = sum(n for (a, b), n in cnt.items() if b == "verify")
    check(verify <= 3 * len({a for (a, b) in cnt if b == "verify"}), "真实日志里验证信号的数量合理（每次弹窗最多 3 行）")

print("真人验证守护测试 " + ("全部通过" if not bad else f"有 {bad} 项失败"))
sys.exit(1 if bad else 0)
