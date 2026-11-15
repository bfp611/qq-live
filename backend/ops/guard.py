# -*- coding: utf-8 -*-
"""真人验证守护（[guard]）：只通知，绝不操作直播伴侣。

抖音会不定期在直播伴侣里弹「人机交互弹窗」（真人验证 / 主播是否在线），限时（日志里写着 timeout=120）内不处理就会被平台关播。
这里盯三类信号，出事就：Bark 推送到 iPhone（critical 级别，静音也响）+ Mac 提示音（走实体音箱，**不进直播**）+ 控制面板顶部红条。

信号（按优先级）：
  1. 直播伴侣日志（只读 ~/Library/Logs/Douyin Webcast Mate/*.log）。弹窗出现时会写：
        [VERIFY_DECISION_MESSAGE] evt=verify-decision-message-open room_id=… timeout=120 current_audience=1 check_reason=adra_punish_center
        [WINDOW] evt=identify-open check_reason=… timeout=120
        [WINDOW_DIAG] evt=window-state label=人机交互弹窗 … event=created
     没处理被平台关播时会写：
        [START_LIVE_EXTERNAL_CLOSE] evt=external-live-close-finished source=heartbeat_room_closed …
     自己点「结束直播」写的是 lifecycle_reason=local_stop（不算意外）。
  2. 兜底（没有日志时才启用，window_watch=auto）：每 interval 秒列出直播伴侣的窗口，出现新的小窗口就提醒。
  3. 弹幕抓取器发现下播（直播还在进行中 → 断了）：等 drop_grace 秒，期间日志没说是自己停的，就提醒。
密钥（data/bark_key.txt）只在发请求时读，任何日志 / 面板 / 报错里都会被遮成 ***。"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------- 日志信号解析
TS_RE = re.compile(r"^\[(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)\.(\d+)")
LOG_RULES = [
    ("verify", re.compile(r"\[VERIFY_DECISION_MESSAGE\].*evt=verify-decision-message-open")),
    ("verify", re.compile(r"\[WINDOW\] evt=identify-open")),
    ("verify", re.compile(r"label=人机交互弹窗 .*event=created")),
    ("closed", re.compile(r"evt=external-live-close-finished")),
    ("local_stop", re.compile(r"lifecycle_reason=local_stop")),
    ("local_stop", re.compile(r"\[START_LIVE\] evt=stop-live-ok")),
]


def parse_ts(line):
    """日志行首的本地时间 → epoch 秒；不是时间戳开头的行返回 None"""
    m = TS_RE.match(line)
    if not m:
        return None
    try:
        return time.mktime(time.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S")) + float("0." + m.group(3)[:3])
    except Exception:
        return None


def parse_line(line, extra=()):
    """一行日志 → None 或 {kind, ts, timeout, reason}。kind：verify / closed / local_stop / custom"""
    if not line or len(line) > 4000:
        return None
    kind = None
    for k, rx in LOG_RULES:
        if rx.search(line):
            kind = k
            break
    if kind is None:
        for rx in extra:
            if rx.search(line):
                kind = "custom"
                break
    if kind is None:
        return None
    ev = {"kind": kind, "ts": parse_ts(line) or time.time(), "timeout": 0, "reason": ""}
    m = re.search(r"\btimeout=(\d+)", line)
    if m:
        ev["timeout"] = int(m.group(1))
    m = re.search(r"\bcheck_reason=([\w-]+)", line)
    if m:
        ev["reason"] = m.group(1)
    m = re.search(r"\bsource=([\w-]+)", line)
    if kind == "closed" and m:
        ev["reason"] = m.group(1)
    if kind == "custom":
        ev["reason"] = line[line.find("]") + 1:][:80].strip()
    return ev


def default_log_dir():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "Douyin Webcast Mate"
    if sys.platform.startswith("win"):
        for base in (os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA")):
            if base:
                for name in ("Douyin Webcast Mate", "douyin-webcast-mate", "webcast_mate"):
                    p = Path(base) / name / "logs"
                    if p.exists():
                        return p
    return None


def newest_log(d):
    try:
        fs = [p for p in Path(d).glob("*.log") if p.is_file()]
        return max(fs, key=lambda p: p.stat().st_mtime) if fs else None
    except Exception:
        return None


class LogTail:
    """只读地盯着最新的日志文件：开始时跳到文件末尾（catch_up 时先读末尾一段），之后每次 poll 读新增的整行；新文件出现（直播伴侣重启）就换过去从头读"""

    def __init__(self, d, extra=()):
        self.dir, self.extra = d, list(extra)
        self.path, self.pos, self.buf, self.ino = None, 0, b"", None

    def available(self):
        return bool(self.dir) and Path(self.dir).is_dir() and newest_log(self.dir) is not None

    def scan_tail(self, nbytes=262144):
        """启动时：读最新日志的末尾一段，返回里面所有信号（按时间顺序），并把游标放到文件末尾"""
        out = []
        p = newest_log(self.dir)
        if not p:
            return out
        try:
            size = p.stat().st_size
            with open(p, "rb") as f:
                f.seek(max(0, size - nbytes))
                data = f.read(nbytes)
                self.pos = f.tell()
            self.path = p
            for ln in data.decode("utf-8", "replace").splitlines():
                ev = parse_line(ln, self.extra)
                if ev:
                    out.append(ev)
        except Exception:
            pass
        return out

    def poll(self):
        """新增的信号（可能为空）。不抛异常"""
        out = []
        try:
            p = newest_log(self.dir)
            if not p:
                return out
            st = p.stat()
            if self.path is None or p != self.path or st.st_size < self.pos:
                first = self.path is None
                self.path, self.pos, self.buf = p, (st.st_size if first else 0), b""
            if st.st_size <= self.pos:
                return out
            with open(p, "rb") as f:
                f.seek(self.pos)
                data = f.read(min(st.st_size - self.pos, 2 * 1024 * 1024))
                self.pos = f.tell()
            data = self.buf + data
            cut = data.rfind(b"\n")
            if cut < 0:
                self.buf = data[-65536:]
                return out
            self.buf = data[cut + 1:][-65536:]
            for ln in data[:cut].decode("utf-8", "replace").splitlines():
                ev = parse_line(ln, self.extra)
                if ev:
                    out.append(ev)
        except Exception:
            pass
        return out


# ---------------------------------------------------------------- 密钥遮蔽
def mask_text(s, key=None):
    s = str(s)
    if key:
        s = s.replace(key, "***").replace(quote(key, safe=""), "***")
    s = re.sub(r"(//[^/\s]+/)[A-Za-z0-9_-]{16,}(?=[/?\s'\"]|$)", r"\1***", s)      # api.day.app/<key>/…
    return s


def read_key(cfg):
    """读 Bark 密钥文件（每次现读，不缓存）；没有返回 ''。只用来发请求和遮蔽日志，不外传"""
    try:
        kf = Path(cfg.s("guard", "bark_key_file") or "data/bark_key.txt")
        return (kf if kf.is_absolute() else ROOT / kf).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------- Bark
def bark_url(server, key, title, body, level, group, volume=10):
    return f"{server.rstrip('/')}/{key}/{quote(title, safe='')}/{quote(body, safe='')}?level={level}&sound=alarm&group={quote(group, safe='')}&volume={volume}"


def _truthy(v):
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def push_blocked(server=""):
    """测试 / 假房间里 Bark 和提示音一律硬禁用，不管 config 怎么写、环境里有没有密钥：QQ_NO_FETCH=1（假房间 / 测试服务）、QQ_NO_BARK=1，
    或者进程本身是 tools/test_*.py / shoot_*.py。唯一例外：Bark 服务器指向本机（127.0.0.1 / localhost，测试里的假 Bark），那发不到手机。"""
    if re.match(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:|/|$)", (server or "").strip(), re.I):
        return False
    if _truthy(os.environ.get("QQ_NO_FETCH")) or _truthy(os.environ.get("QQ_NO_BARK")):
        return True
    return os.path.basename(sys.argv[0] or "").startswith(("test_", "shoot_"))


def bark_push(cfg, title, body, http_get=None):
    """推送到 Bark。返回 (ok, 说明)。说明里没有密钥。critical 失败（HTTP 非 200 / 返回 code 非 200 / 异常）就降到 timeSensitive 再试一次。"""
    c = cfg
    if http_get is None and push_blocked(c.s("guard", "bark_server") or "https://api.day.app"):
        return False, "测试 / 假房间：Bark 已硬禁用（QQ_NO_FETCH / 测试脚本），没有发送"        # 连密钥文件都不读
    kf = Path(c.s("guard", "bark_key_file") or "data/bark_key.txt")
    if not kf.is_absolute():
        kf = ROOT / kf
    try:
        key = kf.read_text(encoding="utf-8").strip()
    except Exception:
        return False, "没有 Bark 密钥文件（[guard] bark_key_file）"
    if not key:
        return False, "Bark 密钥文件是空的"
    if http_get is None:
        import requests
        http_get = lambda url, timeout: requests.get(url, timeout=timeout)       # noqa: E731
    server = c.s("guard", "bark_server") or "https://api.day.app"
    group = c.s("guard", "bark_group") or "qq-live"
    levels = []
    for lv in (c.s("guard", "bark_level") or "critical", "timeSensitive"):
        if lv not in levels:
            levels.append(lv)
    why = []
    for lv in levels:
        try:
            r = http_get(bark_url(server, key, title, body, lv, group), c.f("guard", "bark_timeout"))
            code = r.status_code
            try:
                code = int(r.json().get("code", code))
            except Exception:
                pass
            if r.status_code == 200 and code == 200:
                return True, f"Bark 已推送（{lv}）" + ("；critical 失败已降级：" + "；".join(why) if why else "")
            why.append(f"{lv}: HTTP {r.status_code}/code {code}")
        except Exception as e:
            why.append(f"{lv}: {mask_text(repr(e), key)[:80]}")
    return False, "Bark 推送失败：" + "；".join(why)


# ---------------------------------------------------------------- Mac 提示音（走实体音箱，不进直播）
VIRTUAL_RE = re.compile(r"blackhole|多输出|multi-?output|aggregate|聚合|loopback|soundflower|直播|virtual|vb-?cable|zoom|teams", re.I)
DISPLAY_RE = re.compile(r"monitor|显示器|hdmi|displayport|display|tv\b", re.I)


def list_outputs():
    """[(name, uid)]，用 SwitchAudioSource（brew install switchaudio-osx，README §6.1 本来就要装）。没有就返回 []"""
    import shutil
    exe = shutil.which("SwitchAudioSource") or ("/opt/homebrew/bin/SwitchAudioSource" if os.path.exists("/opt/homebrew/bin/SwitchAudioSource") else None)
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "-a", "-t", "output", "-f", "json"], capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return []
    res = []
    for ln in out.splitlines():
        try:
            d = json.loads(ln)
            res.append((d.get("name", ""), d.get("uid", "")))
        except Exception:
            continue
    return res


def pick_devices(outputs, want="auto"):
    """auto = 所有「实体」输出（排除 BlackHole / 直播多输出等虚拟设备和显示器音箱）；也可以写设备名（逗号分隔，包含匹配）。
    永远排除虚拟设备：提示音进了直播就是事故。"""
    real = [(n, u) for n, u in outputs if n and not VIRTUAL_RE.search(n) and not VIRTUAL_RE.search(u or "")]
    want = (want or "auto").strip()
    if want.lower() == "auto":
        pref = [(n, u) for n, u in real if not DISPLAY_RE.search(n)]
        return pref or real
    names = [w.strip().lower() for w in re.split(r"[,，]", want) if w.strip()]
    return [(n, u) for n, u in real if any(w in n.lower() for w in names)]


def jxa_script(path, uid, repeat, dur=1.2):
    return ("ObjC.import('AppKit');"
            f"var s=$.NSSound.alloc.initWithContentsOfFileByReference({json.dumps(path)},true);"
            f"s.playbackDeviceIdentifier={json.dumps(uid)};s.volume=1.0;"
            f"for(var i=0;i<{int(repeat)};i++){{s.play;$.NSThread.sleepForTimeInterval({dur});}}")


def play_alarm(cfg, run=None, outputs=None):
    """返回 (ok, 说明)。只在 macOS 上发声（NSSound 指定设备）；其它系统返回 (False, 不支持)"""
    if not cfg.b("guard", "sound"):
        return False, "提示音关了"
    if run is None and push_blocked():
        return False, "测试 / 假房间：提示音已硬禁用，没有发声"
    if sys.platform != "darwin" and run is None:
        return False, "提示音只支持 macOS"
    path = cfg.s("guard", "sound_file") or "/System/Library/Sounds/Sosumi.aiff"
    if run is None and not os.path.exists(path):
        return False, "提示音文件不存在：" + path
    outs = outputs if outputs is not None else list_outputs()
    devs = pick_devices(outs, cfg.s("guard", "sound_device"))
    if not devs:
        return False, "没找到实体音箱（只有虚拟设备时不发声，免得进直播）；[guard] sound_device 可以写设备名"
    n = max(1, min(10, cfg.i("guard", "sound_repeat")))
    runner = run or (lambda argv: subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for name, uid in devs:
        runner(["osascript", "-l", "JavaScript", "-e", jxa_script(path, uid, n)])
    return True, "提示音：" + "、".join(n for n, _ in devs)


# ---------------------------------------------------------------- 窗口兜底（macOS）
JXA_WINDOWS = ("ObjC.import('CoreGraphics');"
               "var l=ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(1,0)));"
               "JSON.stringify(l.filter(function(w){return w.kCGWindowOwnerName;}).map(function(w){return {id:w.kCGWindowNumber,owner:w.kCGWindowOwnerName,name:w.kCGWindowName||'',layer:w.kCGWindowLayer,w:w.kCGWindowBounds.Width,h:w.kCGWindowBounds.Height};}))")


def list_windows(owners, run=None):
    """直播伴侣的屏幕上的窗口 [{id, owner, name, layer, w, h}]；不支持 / 失败返回 None"""
    if sys.platform != "darwin" and run is None:
        return None
    try:
        out = (run or (lambda a: subprocess.run(a, capture_output=True, text=True, timeout=8).stdout))(["osascript", "-l", "JavaScript", "-e", JXA_WINDOWS])
        arr = json.loads(out.strip() or "[]")
    except Exception:
        return None
    return [w for w in arr if any(o and o.lower() in str(w.get("owner", "")).lower() for o in owners)]


def new_small_windows(wins, baseline_ids, max_w=520, max_h=700):
    return [w for w in wins if w["id"] not in baseline_ids and w.get("layer", 0) >= 0 and 80 <= w["w"] <= max_w and 60 <= w["h"] <= max_h]


# ---------------------------------------------------------------- 守护本体
class Guard:
    def __init__(self, ops, now=time.time):
        self.ops, self.cfg, self.now = ops, ops.cfg, now
        self.log = lambda *a: ops.log(*[mask_text(x, read_key(self.cfg)) for x in a])
        self.thread = None
        self.lock = threading.Lock()
        self.alert = None                # 当前红色提醒 {id, kind, title, body, at, deadline, push, ack}
        self.history = []                # 最近的提醒（给面板看）
        self.last_sent = {}              # kind → 上次发送时间（冷却）
        self.tail = None
        self.log_ok = False
        self.win_active = False
        self.baseline = set()
        self.baseline_at = 0.0
        self.last_win = 0.0
        self.was_live = False
        self.drop_timer = None
        self.last_local_stop = 0.0
        self.last_log_closed = 0.0
        self.notified = []               # 测试用：发出的 (kind, title, body)
        self.state_path = None
        self.seen_ts = {}                # kind → 已处理过的日志事件时间（重启后不重复提醒）
        self.test_hooks = {}             # 测试用：bark / sound / windows 的替身
        self.last_poll_err = ""

    # ---- 配置 ----
    def on(self):
        return self.ops.on() and self.cfg.b("guard", "enabled")

    def extra(self):
        out = []
        for p in re.split(r"[;；\n]", self.cfg.s("guard", "extra_patterns") or ""):
            p = p.strip()
            if p:
                try:
                    out.append(re.compile(p))
                except re.error:
                    pass
        return out

    def log_dir(self):
        v = (self.cfg.s("guard", "log_dir") or "auto").strip()
        return default_log_dir() if v.lower() == "auto" else Path(v).expanduser()

    def owners(self):
        return [x.strip() for x in re.split(r"[,，]", self.cfg.s("guard", "window_owners") or "") if x.strip()]

    # ---- 生命周期 ----
    def start(self):
        sp = Path(self.cfg.s("guard", "state_file") or "data/guard_state.json")
        self.state_path = sp if sp.is_absolute() else ROOT / sp
        try:
            self.seen_ts = {k: float(v) for k, v in json.loads(self.state_path.read_text(encoding="utf-8")).items()}
        except Exception:
            self.seen_ts = {}
        self.thread = threading.Thread(target=self._run, daemon=True, name="ops-guard")
        self.thread.start()

    def _save_state(self):
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.seen_ts), encoding="utf-8")
        except Exception:
            pass

    def _run(self):
        try:
            self._setup()
        except Exception as e:
            self.log("[guard] 初始化出错：", repr(e)[:120])
        while not self.ops.stopped.wait(max(0.5, self.cfg.f("guard", "log_poll"))):
            try:
                self.tick()
            except Exception as e:
                self.log("[guard] 出错：", repr(e)[:120])

    def _setup(self):
        if not self.on():
            return
        self.tail = LogTail(self.log_dir(), self.extra())
        self.log_ok = self.cfg.b("guard", "log_watch") and self.tail.available()
        if self.log_ok:
            self.log(f"[guard] 盯着直播伴侣日志：{newest_log(self.tail.dir).name}（只读）；Bark {'开' if self.cfg.b('guard', 'bark') else '关'}，提示音 {'开' if self.cfg.b('guard', 'sound') else '关'}")
            self.catch_up(self.tail.scan_tail())
        else:
            self.log("[guard] 没有直播伴侣日志可读" + ("（[guard] log_watch 关了）" if not self.cfg.b("guard", "log_watch") else f"（{self.log_dir()}）") + "：只用窗口兜底和下播检测")

    def catch_up(self, evs):
        """启动时扫一遍日志末尾：还在倒计时的验证弹窗 / 最近被平台关播而没提醒过的，现在补一次提醒"""
        now = self.now()
        win = self.cfg.f("guard", "catchup_secs")
        for ev in evs:
            if ev["kind"] == "local_stop":
                self.last_local_stop = max(self.last_local_stop, ev["ts"])
        for ev in evs:
            if ev["kind"] in ("verify", "closed", "custom") and ev["ts"] > self.seen_ts.get(ev["kind"], 0) and now - ev["ts"] <= win:
                if ev["kind"] == "verify" and now - ev["ts"] > (ev["timeout"] or 120) + 30:
                    continue
                self.handle_log(ev, late=True)
        for ev in evs:
            self.seen_ts[ev["kind"]] = max(self.seen_ts.get(ev["kind"], 0), ev["ts"])
        self._save_state()

    def tick(self):
        if not self.on():
            return
        if self.tail is None:
            self._setup()                                     # 启动时守护是关的、后来在面板打开：现在才初始化
        if self.tail is not None and self.cfg.b("guard", "log_watch"):
            self.tail.dir = self.log_dir() or self.tail.dir
            was = self.log_ok
            self.log_ok = self.tail.available()
            if self.log_ok and not was:
                self.tail.path = None                     # 日志目录刚出现：从末尾开始
            for ev in self.tail.poll():
                self.handle_log(ev)
        else:
            self.log_ok = False
        self._window_tick()
        self._remind_tick()

    # ---- 信号处理 ----
    def handle_log(self, ev, late=False):
        k = ev["kind"]
        self.seen_ts[k] = max(self.seen_ts.get(k, 0), ev["ts"])
        if k == "local_stop":
            self.last_local_stop = ev["ts"]
            return
        if k == "verify":
            t = ev["timeout"] or 120
            left = max(0, int(ev["ts"] + t - self.now()))
            body = f"⚠️ 真人验证弹窗！{left} 秒内回直播伴侣点验证，不然会被平台关播" + ("（补发：启动时发现）" if late else "")
            self.fire("verify", "verify", body, deadline=ev["ts"] + t, reason=ev["reason"])
        elif k == "closed":
            self.last_log_closed = ev["ts"]
            self.fire("closed", "closed", "🔴 直播被平台关了（没通过验证 / 心跳断了），需要重新开播" + ("（补发）" if late else ""), reason=ev["reason"])
        elif k == "custom":
            self.fire("custom", "custom", "⚠️ 直播伴侣日志里出现了你配置的关键字：" + ev["reason"][:60], reason="extra_patterns")
        self._save_state()

    def on_event(self, ev, room=None):
        """Ops.on_event 的钩子（Room._broadcast 里最先调用；不得抛异常）：弹幕抓取器发现下播"""
        if not self.on() or not self.cfg.b("guard", "drop_alert"):
            return
        if room is not None and getattr(room, "rid", "") != self.ops.app.default_room:
            return
        t = ev.get("t")
        if t == "live":
            if ev.get("live"):
                self.was_live = True
                return
            went_off = self.was_live
            self.was_live = False
            if went_off:
                self._drop_soon("live")
        elif t == "end":
            if self.was_live:
                self.was_live = False
                self._drop_soon("recheck" if ev.get("reason") == "recheck" else "end")

    def _drop_soon(self, why):
        self.drop_sig_at = time.time()
        g = max(0.0, self.cfg.f("guard", "drop_grace"))
        if self.drop_timer:
            self.drop_timer.cancel()
        self.drop_timer = threading.Timer(g, self._drop_check, args=(why,))
        self.drop_timer.daemon = True
        self.drop_timer.start()

    def _drop_still_live(self, why):
        """下播信号之后弹幕侧还有动静 / 抓取器又变回「直播中」/ 连接还连着且刚收到过消息 → 不是真下播，不推送。返回原因或 None"""
        try:
            f = self.ops.fetcher_of_default()
        except Exception:
            f = None
        if f is None:
            return None
        sig = getattr(self, "drop_sig_at", 0.0)
        lm = getattr(f, "last_msg_ts", 0.0) or 0.0
        if f.live is True:
            return "抓取器又回到「直播中」"
        if lm and lm > sig:
            return "下播信号之后还收到了弹幕侧消息"
        quiet = max(0.0, self.cfg.f("guard", "drop_quiet"))
        if why != "end" and lm and time.time() - lm < quiet:             # 「end」= 弹幕里真收到了下播控制消息（status 3），其它信号（接口复查 / 重连时查不到）要更谨慎
            return f"{int(time.time() - lm)} 秒前还收到过消息"
        if why != "end" and getattr(f, "connected", False) and getattr(f, "state", "") == "connected" and f.live is not False:
            return "连接还连着"
        return None

    def _drop_check(self, why):
        now = self.now()
        sk = self._drop_still_live(why)
        if sk:
            self.log(f"[guard] 疑似下播（{why}）但{sk}，不推送")
            return
        if self.log_ok and now - self.last_local_stop < 120:
            self.log("[guard] 下播：直播伴侣日志说是自己点的结束，不提醒")
            return
        if now - self.last_log_closed < 120:
            return                                           # 日志那边已经提醒过「被平台关了」
        self.fire("drop", "drop", "🔴 直播好像断了：弹幕侧检测到下播，直播伴侣日志里没有「自己结束」的记录，快去看看", reason=why)

    # ---- 提醒 ----
    def fire(self, key, kind, body, deadline=None, reason="", test=False):
        """冷却里就只记一笔不推。返回 alert 或 None"""
        now = self.now()
        cd = self.cfg.f("guard", "cooldown")
        title = self.cfg.s("guard", "bark_title") or "GG-Bond 直播"
        with self.lock:
            if not test and now - self.last_sent.get(key, 0) < cd:
                self.log(f"[guard] {key} 提醒在冷却中（{int(cd)} 秒），不重复推")
                return None
            self.last_sent[key] = now
            self.alert = {"id": int(now * 1000), "kind": kind, "title": title, "body": body, "at": now, "deadline": deadline, "push": "发送中…", "ack": False,
                          "reason": reason, "reminded": 0, "test": test}
            a = self.alert
            self.history = ([dict(a)] + self.history)[:20]
        self.ops.record("guard", kind=kind, reason=reason)
        self.log(f"[guard] 提醒：{kind} {reason}")
        threading.Thread(target=self._deliver, args=(a, title, body), daemon=True, name="guard-notify").start()
        return a

    def _deliver(self, a, title, body):
        msgs = []
        h = self.test_hooks
        if self.cfg.b("guard", "bark"):
            ok, m = (h.get("bark") or (lambda t, b: bark_push(self.cfg, t, b)))(title, body)
            msgs.append(m)
        else:
            msgs.append("Bark 关了")
        if self.cfg.b("guard", "sound"):
            ok, m = (h.get("sound") or (lambda: play_alarm(self.cfg)))()
            msgs.append(m)
        a["push"] = "；".join(mask_text(x, read_key(self.cfg)) for x in msgs)
        self.notified.append((a["kind"], title, body))
        self.log("[guard] " + a["push"])
        for hh in self.history:
            if hh["id"] == a["id"]:
                hh["push"] = a["push"]

    def _remind_tick(self):
        a = self.alert
        if not a or a["ack"] or a["kind"] != "verify" or a.get("test"):
            return
        steps = []
        for x in re.split(r"[,，\s]+", self.cfg.s("guard", "remind_at") or ""):
            try:
                steps.append(float(x))
            except ValueError:
                pass
        steps.sort()
        i = a["reminded"]
        if i >= len(steps):
            return
        now = self.now()
        if a["deadline"] and now > a["deadline"]:
            a["reminded"] = len(steps)
            return
        if now - a["at"] >= steps[i]:
            a["reminded"] = i + 1
            left = max(0, int(a["deadline"] - now)) if a["deadline"] else 0
            body = f"⏰ 真人验证还没处理！还剩约 {left} 秒" if left else "⏰ 真人验证还没处理！"
            threading.Thread(target=self._deliver, args=(a, a["title"], body), daemon=True, name="guard-remind").start()

    def ack(self):
        a = self.alert
        if a:
            a["ack"] = True
        return bool(a)

    def test_push(self):
        title = self.cfg.s("guard", "bark_title") or "GG-Bond 直播"
        return self.fire("test", "test", "测试：真人验证提醒已就绪", test=True) is not None

    # ---- 窗口兜底 ----
    def _window_tick(self):
        mode = (self.cfg.s("guard", "window_watch") or "auto").lower()
        want = mode in ("true", "1", "yes", "on") or (mode == "auto" and not self.log_ok)
        self.win_active = want
        if not want:
            return
        now = self.now()
        if now - self.last_win < max(2.0, self.cfg.f("guard", "interval")):
            return
        self.last_win = now
        lw = self.test_hooks.get("windows") or (lambda: list_windows(self.owners()))
        wins = lw()
        if wins is None:
            return
        if not self.baseline_at:
            self.baseline = {w["id"] for w in wins}
            self.baseline_at = now
            return
        news = new_small_windows(wins, self.baseline)
        if news and not (self.alert and not self.alert["ack"] and now - self.alert["at"] < 120):
            w = news[0]
            self.fire("window", "verify", f"⚠️ 直播伴侣出现了新窗口（{int(w['w'])}×{int(w['h'])}），疑似真人验证弹窗，快去看看", deadline=now + 120, reason="window")
        if not news and not (self.alert and not self.alert["ack"]):
            self.baseline = {w["id"] for w in wins}              # 没有提醒时：把现有窗口当作正常的

    # ---- 状态（给面板 / /ops/state）----
    def snapshot(self):
        now = self.now()
        a = self.alert
        act = None
        if a and not a["ack"]:
            if a["kind"] == "verify" and a["deadline"] and now > a["deadline"] + 60:
                act = None                                       # 倒计时早就过了
            elif a["kind"] in ("drop", "closed", "custom") and now - a["at"] > 1800:
                act = None
            elif a.get("test") and now - a["at"] > 30:
                act = None
            else:
                act = {k: a[k] for k in ("id", "kind", "title", "body", "at", "deadline", "push", "reason", "test")}
                act["left"] = max(0, int(a["deadline"] - now)) if a["deadline"] else None
        key_ok = False
        try:
            kf = Path(self.cfg.s("guard", "bark_key_file") or "data/bark_key.txt")
            kf = kf if kf.is_absolute() else ROOT / kf
            key_ok = kf.exists() and kf.stat().st_size > 0
        except Exception:
            pass
        return {"enabled": self.on(), "log_watch": self.log_ok, "log_file": (self.tail.path.name if self.tail and self.tail.path else None),
                "window_watch": self.win_active, "bark": self.cfg.b("guard", "bark"), "bark_key": key_ok, "sound": self.cfg.b("guard", "sound"),
                "alert": act, "history": [{k: x[k] for k in ("kind", "body", "at", "push", "reason")} for x in self.history[:8]]}
