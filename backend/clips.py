# -*- coding: utf-8 -*-
"""高光切片（[clips]）：Mac 上用 ffmpeg 一直录「直播页面那个浏览器窗口」+ BlackHole 的声音，存成滚动的几十秒分段缓冲；
出高光时刻（蓝屏 / 熊猫烧香 / 假重启 / 烟花表演 / 大礼 / 观众发「高光」）把「前 10 秒 + 后 15 秒」剪成 9:16 竖屏 MP4（模糊铺底），存到 data/clips/。

  录制   avfoundation 抓屏（只抓直播页面所在的窗口，用 JXA 找窗口，按显示器的比例裁剪）+ BlackHole 2ch → h264_videotoolbox（低 CPU）→ segment muxer，
         2 秒一段、写在系统临时目录，只留 keep_secs 秒。只在「开播中」录（mode=live），或者面板上手动开 / 一直录（mode=always）。
  剪片   高光事件（App.mark_highlight → on_highlight）等「后 15 秒」录完，把盖到 [t-10, t+15] 的几段拼起来，裁成 1080×1920：前景按宽度铺满，背景是同一画面放大 + 高斯模糊。
         同一段时间里的几个高光合并成一条（min_gap）。文件名 <时间>_<事件>.mp4，旁边一张 .jpg 缩略图。最多留 max_clips 条。
  权限   macOS 的「屏幕录制」：启动时用 CGPreflightScreenCaptureAccess 检测（不会弹窗、不会尝试绕过）；没权限就不录，日志 + 面板写清楚该给哪个 App / 可执行文件授权。
  Bark   bark=true 才推「切到一个高光」（默认关）。
线程：tick 在 asyncio 里，探测 / 起 ffmpeg / 剪片都放到线程池，不卡直播。"""
import asyncio
import atexit
import ctypes
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^(\d{8}-\d{6})_([A-Za-z0-9_\-]{1,40})\.mp4$")
SEG_RE = re.compile(r"^s_(\d{8}-\d{6})\.ts$")
KIND_LABEL = {"bsod": "蓝屏", "restart": "假重启", "virus": "熊猫烧香", "fireworks": "烟花", "meteor": "流星雨", "setup": "重装系统", "gift_big": "大礼", "viewer": "观众点的高光", "manual": "手动"}
TMP_PREFIX = "qqclips-"


# ---------------------------------------------------------------- 纯函数（测试里直接调）
def parse_devices(text):
    """解析 `ffmpeg -f avfoundation -list_devices true -i ""` 的输出 → {"screens": {屏幕序号: 视频设备序号}, "video": {名: 序号}, "audio": {名: 序号}}"""
    sec, out = None, {"screens": {}, "video": {}, "audio": {}}
    for ln in (text or "").splitlines():
        if "video devices" in ln:
            sec = "video"
            continue
        if "audio devices" in ln:
            sec = "audio"
            continue
        m = re.search(r"\]\s*\[(\d+)\]\s+(.+?)\s*$", ln)
        if not m or sec is None:
            continue
        idx, name = int(m.group(1)), m.group(2)
        out[sec][name] = idx
        ms = re.fullmatch(r"Capture screen (\d+)", name)
        if sec == "video" and ms:
            out["screens"][int(ms.group(1))] = idx
    return out


def parse_list(s):
    return [x.strip() for x in re.split(r"[,，;；\s]+", s or "") if x.strip()]


def parse_inset(s):
    try:
        v = [float(x) for x in re.split(r"[,，\s]+", (s or "").strip()) if x != ""]
    except ValueError:
        v = []
    return (v + [0.0] * 4)[:4] if v else [0.0] * 4          # 上, 右, 下, 左（点）


def pick_window(wins, owner, title):
    """JXA 窗口列表 [{owner,name,layer,x,y,w,h}] → 直播页面的窗口（owner 含 owner、标题含 title、普通层、够大；多个取最大的）。找不到 None（不乱猜）"""
    best = None
    for w in wins or []:
        if owner and owner.lower() not in str(w.get("owner", "")).lower():
            continue
        if title and title not in str(w.get("name", "")):
            continue
        if int(w.get("layer", 0) or 0) != 0 or w.get("w", 0) < 200 or w.get("h", 0) < 200:
            continue
        if best is None or w["w"] * w["h"] > best["w"] * best["h"]:
            best = w
    return best


def locate(win, displays, inset=(0, 0, 0, 0)):
    """窗口（全局坐标，点）+ 显示器列表 [{"x","y","w","h"}]（顺序 = ffmpeg 的 Capture screen 序号）→ {"screen": 序号, "fx","fy","fw","fh": 相对该显示器的比例}。
    按窗口和显示器的重叠面积选屏；窗口超出屏幕的部分裁掉。比例与显示器是不是 Retina 无关（ffmpeg 里用 iw/ih 乘比例）。"""
    top, right, bottom, left = inset
    x, y, w, h = win["x"] + left, win["y"] + top, win["w"] - left - right, win["h"] - top - bottom
    best, area = None, 0.0
    for i, d in enumerate(displays):
        ox = max(0.0, min(x + w, d["x"] + d["w"]) - max(x, d["x"]))
        oy = max(0.0, min(y + h, d["y"] + d["h"]) - max(y, d["y"]))
        if ox * oy > area:
            best, area = i, ox * oy
    if best is None or area < 100:
        return None
    d = displays[best]
    x0, y0 = max(x, d["x"]), max(y, d["y"])
    x1, y1 = min(x + w, d["x"] + d["w"]), min(y + h, d["y"] + d["h"])
    r = {"screen": best, "fx": (x0 - d["x"]) / d["w"], "fy": (y0 - d["y"]) / d["h"], "fw": (x1 - x0) / d["w"], "fh": (y1 - y0) / d["h"]}
    return r if r["fw"] > 0.02 and r["fh"] > 0.02 else None


def parse_region(s):
    """[clips] region = x,y,w,h（全局坐标，点；空 = 自动找窗口）→ 虚拟窗口 dict / None"""
    try:
        v = [float(x) for x in re.split(r"[,，\s]+", (s or "").strip()) if x != ""]
    except ValueError:
        return None
    return {"x": v[0], "y": v[1], "w": v[2], "h": v[3]} if len(v) == 4 and v[2] > 0 and v[3] > 0 else None


def crop_filter(g, max_w):
    """按比例裁 + 缩到最大宽度 max_w（偶数边，yuv420p）"""
    return (f"crop=w='trunc(iw*{g['fw']:.5f}/2)*2':h='trunc(ih*{g['fh']:.5f}/2)*2':x='trunc(iw*{g['fx']:.5f}/2)*2':y='trunc(ih*{g['fy']:.5f}/2)*2',"
            f"scale='min({int(max_w)},iw)':-2,format=yuv420p")


def pick_encoder(cfg_enc, have):
    if cfg_enc and cfg_enc != "auto":
        return cfg_enc
    return "h264_videotoolbox" if "h264_videotoolbox" in have else "libx264"


def venc_args(enc, kbps, fps):
    g = str(max(2, int(fps * 2)))
    if enc == "h264_videotoolbox":
        return ["-c:v", enc, "-b:v", f"{int(kbps)}k", "-realtime", "1", "-prio_speed", "1", "-allow_sw", "0", "-g", g, "-profile:v", "high"]
    return ["-c:v", enc, "-preset", "ultrafast", "-b:v", f"{int(kbps)}k", "-g", g]


def build_record_cmd(ff, enc, inputs, vf, out_pattern, fps, kbps, seg_secs, audio):
    """inputs: ffmpeg 输入参数列表（avfoundation 或测试用的 lavfi / 图片）；audio=True 表示有音频流"""
    cmd = [ff, "-hide_banner", "-loglevel", "warning", "-y"] + list(inputs)
    cmd += ["-vf", vf, "-r", str(int(fps))] + venc_args(enc, kbps, fps)
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "48000", "-af", "aresample=async=1:first_pts=0"]
    else:
        cmd += ["-an"]
    cmd += ["-f", "segment", "-segment_time", str(seg_secs), "-segment_atclocktime", "1", "-reset_timestamps", "1", "-segment_format", "mpegts", "-strftime", "1", out_pattern]
    return cmd


def seg_start(name):
    m = SEG_RE.match(name)
    if not m:
        return None
    try:
        return time.mktime(time.strptime(m.group(1), "%Y%m%d-%H%M%S"))
    except Exception:
        return None


def list_segments(d):
    out = []
    try:
        for p in Path(d).iterdir():
            t = seg_start(p.name)
            if t is not None:
                out.append((t, p))
    except FileNotFoundError:
        pass
    return sorted(out, key=lambda x: x[0])


def pick_segments(segs, t0, t1, all_closed=False):
    """segs = [(开始时间, 路径)] 按时间排；返回 ([路径…], 第一段里要跳过的秒数)。最后一段可能还在写（除非 all_closed），不选；一段也盖不到返回 None"""
    closed = segs if all_closed else segs[:-1]
    chosen = []
    for i, (t, p) in enumerate(closed):
        nxt = segs[i + 1][0] if i + 1 < len(segs) else t + 2.0
        if t < t1 and nxt > t0:
            chosen.append((t, p))
    if not chosen:
        return None
    return [p for _, p in chosen], max(0.0, t0 - chosen[0][0])


def vertical_filter(w, h):
    """前景按宽度铺满，背景 = 同一画面放大裁满 + 高斯模糊（先缩小再模糊再放大，省 CPU）"""
    sw, sh = max(2, w // 4), max(2, h // 4)
    return (f"[0:v]split=2[a][b];[a]scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},gblur=sigma=5,scale={w}:{h},setsar=1[bg];"
            f"[b]scale={w}:-2,setsar=1[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")


def build_clip_cmd(ff, enc, listfile, offset, dur, out, w, h, kbps, vertical=True, has_audio=True):
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-ss", f"{offset:.3f}", "-t", f"{dur:.3f}"]
    if vertical:
        cmd += ["-filter_complex", vertical_filter(w, h), "-map", "[v]"]
    else:
        cmd += ["-map", "0:v:0", "-vf", "format=yuv420p"]
    if has_audio:
        cmd += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k"]
    if enc == "h264_videotoolbox":
        cmd += ["-c:v", enc, "-b:v", f"{int(kbps)}k", "-allow_sw", "1"]
    else:
        cmd += ["-c:v", enc, "-preset", "veryfast", "-crf", "23"]
    cmd += ["-movflags", "+faststart", str(out)]
    return cmd


def safe_kind(kind):
    k = re.sub(r"^perf_", "", str(kind or "manual"))
    return re.sub(r"[^A-Za-z0-9_\-]", "", k)[:30] or "manual"


def clip_name(t, kind):
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(t)) + "_" + safe_kind(kind) + ".mp4"


# ---------------------------------------------------------------- macOS：屏幕录制权限 / 显示器 / 窗口
def screen_perm():
    """True / False / None（不是 macOS / 查不出来）。CGPreflightScreenCaptureAccess：只检测，不弹窗、不申请"""
    if sys.platform != "darwin":
        return None
    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        f = cg.CGPreflightScreenCaptureAccess
        f.restype = ctypes.c_bool
        return bool(f())
    except Exception:
        return None


def responsible_hint(ff=""):
    """告诉用户该给谁开「屏幕录制」：沿父进程往上找第一个 .app（Terminal / iTerm / Grok Bot …）；找不到说明是被 launchd 直接拉起的，要给 python 可执行文件开"""
    py = os.path.realpath(sys.executable)
    app, pid = "", os.getpid()
    for _ in range(12):
        try:
            r = subprocess.run(["ps", "-o", "ppid=,command=", "-p", str(pid)], capture_output=True, text=True, timeout=3).stdout.strip()
        except Exception:
            break
        if not r:
            break
        ppid, _, cmd = r.partition(" ")
        m = re.search(r"/([^/]+)\.app/Contents/MacOS/", cmd)
        if m and pid != os.getpid():
            app = m.group(1)
            break
        try:
            pid = int(ppid)
        except ValueError:
            break
        if pid <= 1:
            break
    path = "系统设置 → 隐私与安全性 → 屏幕与系统音频录制（Screen & System Audio Recording）"
    if app:
        return {"app": app, "python": py, "ffmpeg": ff, "msg": f"要给「{app}」开屏幕录制（{path}）：本服务和 ffmpeg 都是它的子进程，不用单独加。开完要重启服务（面板 → 控制 → 重启服务）。"}
    return {"app": "", "python": py, "ffmpeg": ff, "msg": f"本服务是被 launchd / 后台守护直接拉起的（没有终端 App 当父进程），要给 python 可执行文件开屏幕录制：{py}"
            f"（{path}，点「+」选它；列表里选不到就把它拖进去）。ffmpeg（{ff or 'ffmpeg'}）是 python 的子进程，通常不用单独加，录不到画面再把它也加上。开完要重启服务。"}


def active_displays():
    """macOS：活动显示器 [{"x","y","w","h"}]（点，全局坐标，主屏左上角为原点；顺序 = CGGetActiveDisplayList = ffmpeg 的 Capture screen 序号）。没有（显示器休眠 / 非 macOS）返回 []"""
    if sys.platform != "darwin":
        return []
    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

        class P(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

        class S(ctypes.Structure):
            _fields_ = [("w", ctypes.c_double), ("h", ctypes.c_double)]

        class R(ctypes.Structure):
            _fields_ = [("o", P), ("s", S)]
        cg.CGDisplayBounds.restype = R
        cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        ids = (ctypes.c_uint32 * 16)()
        n = ctypes.c_uint32()
        cg.CGGetActiveDisplayList(16, ids, ctypes.byref(n))
        out = []
        for i in range(n.value):
            b = cg.CGDisplayBounds(ids[i])
            out.append({"x": b.o.x, "y": b.o.y, "w": b.s.w, "h": b.s.h})
        return out
    except Exception:
        return []


JXA_WINDOWS = ("ObjC.import('CoreGraphics');"
               "var l=ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(1,0)));"
               "JSON.stringify(l.filter(function(w){return w.kCGWindowOwnerName;}).map(function(w){var b=w.kCGWindowBounds;"
               "return {id:w.kCGWindowNumber,owner:w.kCGWindowOwnerName,name:w.kCGWindowName||'',layer:w.kCGWindowLayer,x:b.X,y:b.Y,w:b.Width,h:b.Height};}))")


def list_windows(run=None):
    if sys.platform != "darwin" and run is None:
        return None
    try:
        out = (run or (lambda a: subprocess.run(a, capture_output=True, text=True, timeout=8).stdout))(["osascript", "-l", "JavaScript", "-e", JXA_WINDOWS])
        return json.loads(out.strip() or "[]")
    except Exception:
        return None


def which_ffmpeg(cfg_val=""):
    for c in ([cfg_val] if cfg_val and cfg_val != "auto" else []) + ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return shutil.which("ffmpeg") or ""


# ---------------------------------------------------------------- 本体
class Clips:
    def __init__(self, cfg, app, log=print):
        self.cfg, self.app, self.log = cfg, app, log
        self.proc = None
        self.buf = None                    # 分段缓冲目录
        self.old_buf = None                # 停止录制时还有没剪完的任务：缓冲目录多留一会儿
        self.geom = None                   # 正在录的比例
        self.since = 0.0
        self.manual_on = False             # 面板手动开录（不管开没开播）
        self.jobs = []                     # 等后 15 秒录完再剪
        self.err = ""
        self.perm = {"ok": None, "msg": "", "checked": 0.0}
        self.next_try = 0.0
        self.fail = 0
        self.last_reloc = 0.0
        self.last_accept = 0.0
        self.user_last = {}
        self.stats = {"events": 0, "clips": 0, "skip_close": 0, "skip_norec": 0, "skip_kind": 0, "failed": 0, "viewer": 0, "starts": 0, "restarts": 0}
        self.last = None
        self.hist = []
        self.task = None
        self.loop = None
        self.busy_jobs = 0
        self._files = ([], 0.0)
        self._warned = {}
        self.push = self._push             # 测试里换成假的
        self.hooks = {}                    # 测试替身：probe / windows / displays / perm
        self.lock = threading.Lock()
        atexit.register(self.shutdown)

    # ---- 配置
    def on(self):
        return self.cfg.b("clips", "enabled")

    def out_dir(self):
        p = Path(self.cfg.s("clips", "out_dir") or "data/clips")
        return p if p.is_absolute() else ROOT / p

    def events(self):
        return set(parse_list(self.cfg.s("clips", "events")))

    def seg_secs(self):
        return max(1, self.cfg.i("clips", "seg_secs"))

    def pre(self):
        return max(1.0, self.cfg.f("clips", "pre"))

    def post(self):
        return max(1.0, self.cfg.f("clips", "post"))

    def keep(self):
        return max(self.cfg.f("clips", "keep_secs"), self.pre() + self.post() + 3 * self.seg_secs() + 10)

    def test_source(self):
        return self.cfg.s("clips", "test_source")

    # ---- 开播判断
    def is_live(self):
        app = self.app
        r = app.rooms.get(app.default_room) or next((x for k, x in app.rooms.items() if k != "demo"), None)
        lv = (getattr(r, "last", None) or {}).get("live") if r else None
        if lv:
            return bool(lv.get("live"))
        f = getattr(r, "fetcher", None) if r else None
        if f is not None and f.live is not None:
            return bool(f.live)
        ops = getattr(app, "ops", None)
        if ops is not None and getattr(ops, "live_since", None):
            return True
        return None

    def want_record(self):
        if not self.on():
            return False
        if self.manual_on:
            return True
        mode = (self.cfg.s("clips", "mode") or "live").lower()
        if mode == "always":
            return True
        if mode == "manual":
            return False
        return self.is_live() is True

    # ---- 生命周期
    def start(self):
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None
        self.kill_stale()
        self.task = asyncio.ensure_future(self.run())

    def kill_stale(self):
        """上一次服务重启 / 崩溃留下的 ffmpeg 和临时目录（只认我们自己的 qqclips- 目录）"""
        try:
            if os.name == "posix":
                subprocess.run(["pkill", "-f", TMP_PREFIX], capture_output=True, timeout=3)
            tmp = Path(tempfile.gettempdir())
            for d in tmp.glob(TMP_PREFIX + "*"):
                if d.is_dir() and time.time() - d.stat().st_mtime > 600:
                    shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass

    def startup_check(self):
        """启动时检测一次（不开录、不弹窗）：屏幕录制权限 / ffmpeg，结果写日志和面板，让人开播前就知道缺什么"""
        if not self.on():
            return
        ok, why, ff = self.check_env()
        if ok:
            self.log(f"[clips] 环境检查：ffmpeg {ff or '?'}，屏幕录制权限 {'已授权' if self.perm.get('ok') else '（不适用 / 无法检测）'}；{(self.cfg.s('clips', 'mode') or 'live')} 模式，开播后自动录")
        else:
            self.err = why
            self.log(f"[clips] ⚠ 环境检查没过：{why}")

    async def run(self):
        loop = asyncio.get_running_loop()
        await asyncio.sleep(2.0)
        try:
            await loop.run_in_executor(None, self.startup_check)
        except Exception as e:  # noqa
            self.log(f"[clips] 环境检查出错：{e!r}")
        while True:
            await asyncio.sleep(1.0)
            try:
                await self.tick(loop)
            except Exception as e:  # noqa
                self.log(f"[clips] tick 出错：{e!r}")

    def warn_once(self, key, msg, every=600):
        now = time.time()
        if now - self._warned.get(key, 0) > every:
            self._warned[key] = now
            self.log(msg)

    async def tick(self, loop, now=None):
        now = now or time.time()
        want = self.want_record()
        pending = [j for j in self.jobs if not j.get("done")]
        if self.proc is not None:
            if self.proc.poll() is not None:
                await loop.run_in_executor(None, self.on_exit)
            elif want or pending:
                # 盯着有没有在出新分段（卡住就重启）
                segs = list_segments(self.buf) if self.buf else []
                newest = max([p.stat().st_mtime for _, p in segs if p.exists()] or [self.since])
                if now - newest > 6 * self.seg_secs() + 6 and now - self.since > 12:
                    self.log("[clips] 分段很久没有新文件，重启录制")
                    self.stats["restarts"] += 1
                    await loop.run_in_executor(None, self.stop_proc)
                elif want and now - self.last_reloc >= max(10.0, self.cfg.f("clips", "relocate_secs")):
                    self.last_reloc = now
                    g = await loop.run_in_executor(None, self.find_geom)
                    if g and self.geom and self.moved(g, self.geom):
                        self.log("[clips] 直播窗口位置 / 大小变了，重新对准后继续录")
                        self.stats["restarts"] += 1
                        await loop.run_in_executor(None, self.stop_proc)
        if self.proc is None and want and now >= self.next_try:
            await loop.run_in_executor(None, self.start_proc)
        elif self.proc is not None and not want and not pending:
            self.log("[clips] 不在录制时段了（下播 / 手动关），停止录制")
            await loop.run_in_executor(None, self.stop_proc)
        elif self.proc is not None and not want and pending and now - max(j["due"] for j in pending) > 40:
            await loop.run_in_executor(None, self.stop_proc)
        # 到点的任务去剪
        for j in list(self.jobs):
            if not j.get("done") and not j.get("running") and now >= j["due"]:
                j["running"] = True
                asyncio.ensure_future(self.do_job(j, loop))
        self.jobs = [j for j in self.jobs if not j.get("done") or now - j["due"] < 5]
        if self.buf and self.proc is not None and int(now) % 3 == 0:
            await loop.run_in_executor(None, self.janitor, now)

    @staticmethod
    def moved(a, b):
        return a["screen"] != b["screen"] or any(abs(a[k] - b[k]) > 0.01 for k in ("fx", "fy", "fw", "fh"))

    # ---- 检测 / 起录
    def check_env(self):
        """返回 (ok, 说明)。权限没开 / 没 ffmpeg / 没屏幕 / 找不到窗口都会说清楚，不尝试绕过"""
        h = self.hooks
        ff = which_ffmpeg(self.cfg.s("clips", "ffmpeg"))
        if not ff:
            return False, "没找到 ffmpeg（brew install ffmpeg，或在 [clips] ffmpeg 写完整路径）", None
        if self.test_source():
            return True, "", ff
        p = (h.get("perm") or screen_perm)()
        self.perm = {"ok": p, "msg": "", "checked": time.time()}
        if p is False:
            hint = responsible_hint(ff)
            self.perm["msg"] = hint["msg"]
            self.perm.update(app=hint["app"], python=hint["python"], ffmpeg=ff)
            return False, "没有「屏幕录制」权限：" + hint["msg"], ff
        return True, "", ff

    def find_geom(self):
        h = self.hooks
        displays = (h.get("displays") or active_displays)()
        if not displays:
            return None
        win = parse_region(self.cfg.s("clips", "region"))
        if win is None:
            wins = (h.get("windows") or list_windows)()
            win = pick_window(wins, self.cfg.s("clips", "window_owner"), self.cfg.s("clips", "window_title"))
        if win is None:
            return None
        return locate(win, displays, parse_inset(self.cfg.s("clips", "inset")))

    def probe_devices(self, ff):
        h = self.hooks
        if h.get("probe"):
            return h["probe"]()
        try:
            r = subprocess.run([ff, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""], capture_output=True, text=True, timeout=15)
            return parse_devices(r.stderr + r.stdout)
        except Exception:
            return {"screens": {}, "video": {}, "audio": {}}

    def encoders(self, ff):
        if self.hooks.get("encoders"):
            return self.hooks["encoders"]()
        try:
            return subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=10).stdout
        except Exception:
            return ""

    def fail_start(self, msg, backoff=None):
        self.err = msg
        self.fail += 1
        self.next_try = time.time() + (backoff or min(120, self.cfg.f("clips", "retry_secs") * min(self.fail, 4)))
        self.warn_once("fail:" + msg[:30], f"[clips] 不能开始录制：{msg}", 300)
        return False

    def start_proc(self):
        with self.lock:
            if self.proc is not None:
                return False
            ok, why, ff = self.check_env()
            if not ok:
                return self.fail_start(why, 60)
            c = self.cfg
            fps, kbps, maxw = c.i("clips", "fps"), c.i("clips", "bitrate"), c.i("clips", "max_width")
            ts = self.test_source()
            audio = False
            if ts:
                inputs, geom, audio = self.test_inputs(ts, fps)
                if geom is None:
                    return self.fail_start("test_source 不对：" + ts)
            else:
                dev = self.probe_devices(ff)
                geom = self.find_geom()
                if not dev["screens"]:
                    return self.fail_start("ffmpeg 看不到任何屏幕（显示器休眠了，或这个进程没有屏幕录制权限）；亮屏后会自动再试", 30)
                if geom is None:
                    return self.fail_start(f"找不到直播窗口（{c.s('clips', 'window_owner')} 标题含「{c.s('clips', 'window_title')}」），也可以在 [clips] region 写 x,y,w,h", 30)
                vidx = dev["screens"].get(geom["screen"])
                if vidx is None:
                    return self.fail_start(f"ffmpeg 没有第 {geom['screen']} 号屏幕", 30)
                an = c.s("clips", "audio")
                aidx = next((i for n, i in dev["audio"].items() if an and an.lower() in n.lower()), None) if an else None
                if an and aidx is None:
                    self.warn_once("noaudio", f"[clips] 没找到音频设备「{an}」，这次只录画面（没有声音）", 600)
                audio = aidx is not None
                inputs = ["-f", "avfoundation", "-capture_cursor", "0", "-framerate", str(fps), "-i", f"{vidx}:{aidx if aidx is not None else 'none'}"]
            enc = pick_encoder(c.s("clips", "encoder"), self.encoders(ff))
            buf = tempfile.mkdtemp(prefix=TMP_PREFIX)
            cmd = build_record_cmd(ff, enc, inputs, crop_filter(geom, maxw), os.path.join(buf, "s_%Y%m%d-%H%M%S.ts"), fps, kbps, self.seg_secs(), audio)
            try:
                errf = open(os.path.join(buf, "ffmpeg.err"), "wb")
                self.proc = (self.hooks.get("popen") or subprocess.Popen)(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errf, start_new_session=True)
            except Exception as e:  # noqa
                shutil.rmtree(buf, ignore_errors=True)
                return self.fail_start(f"启动 ffmpeg 失败：{e!r}")
            self.buf, self.geom, self.since, self.err, self.fail = buf, geom, time.time(), "", 0
            self.last_reloc = time.time()
            self.stats["starts"] += 1
            self.enc = enc
            self.log(f"[clips] 开始录制：{enc}，{fps}fps，屏幕 {geom['screen']} 比例 x={geom['fx']:.3f} y={geom['fy']:.3f} w={geom['fw']:.3f} h={geom['fh']:.3f}，{'带' if audio else '没有'}音频，缓冲目录 {buf}")
            return True

    def test_inputs(self, ts, fps):
        """测试 / 演示用的输入：lavfi 彩条 + 正弦波，或 image:<路径>（循环一张图）+ 正弦波"""
        g = {"screen": 0, "fx": 0.0, "fy": 0.0, "fw": 1.0, "fh": 1.0}
        if ts == "lavfi":
            return ["-f", "lavfi", "-re", "-i", f"testsrc2=size=1280x720:rate={fps}", "-f", "lavfi", "-re", "-i", "sine=frequency=440:sample_rate=48000"], g, True
        if ts.startswith("image:"):
            p = ts[6:]
            if not os.path.isfile(p):
                return None, None, False
            return ["-loop", "1", "-framerate", str(fps), "-re", "-i", p, "-f", "lavfi", "-re", "-i", "sine=frequency=330:sample_rate=48000"], g, True
        return None, None, False

    def on_exit(self):
        with self.lock:
            p, self.proc = self.proc, None
            tail = ""
            try:
                tail = Path(self.buf, "ffmpeg.err").read_text(errors="replace")[-400:].strip() if self.buf else ""
            except Exception:
                pass
            rc = p.returncode if p else None
        self.fail_start(f"ffmpeg 退出了（{rc}）：{tail or '没有输出'}")
        self.stats["restarts"] += 1

    def stop_proc(self):
        with self.lock:
            p, self.proc = self.proc, None
            if p is not None:
                try:
                    p.stdin.write(b"q")
                    p.stdin.flush()
                except Exception:
                    pass
                try:
                    p.wait(timeout=4)
                except Exception:
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except Exception:
                        p.kill()
                    try:
                        p.wait(timeout=2)
                    except Exception:
                        pass
            buf, self.buf = self.buf, None
            self.geom = None
            if buf:
                if any(not j.get("done") for j in self.jobs):
                    self.old_buf = buf
                    threading.Timer(60, shutil.rmtree, args=(buf, True)).start()          # 还有没剪完的片：缓冲多留一会儿
                else:
                    shutil.rmtree(buf, ignore_errors=True)

    def shutdown(self):
        try:
            self.stop_proc()
        except Exception:
            pass

    def janitor(self, now):
        keep = self.keep()
        for t, p in list_segments(self.buf):
            if now - t > keep:
                try:
                    p.unlink()
                except Exception:
                    pass

    # ---- 高光
    def on_highlight(self, kind, h):
        """App.mark_highlight 调用：排一个剪片任务（后 post 秒录完再剪）"""
        if not self.on():
            return None
        t = float(h.get("at") or time.time())
        k = safe_kind(kind)
        self.stats["events"] += 1
        if str(kind) not in self.events() and k not in self.events():
            self.stats["skip_kind"] += 1
            return None
        if self.proc is None and self.buf is None:
            self.stats["skip_norec"] += 1
            self.warn_once("norec", f"[clips] 高光 {k} 没录到：现在没在录制（{self.err or '没开播 / 没开手动录制'}）", 120)
            return None
        if t - self.last_accept < self.cfg.f("clips", "min_gap"):
            self.stats["skip_close"] += 1
            self.log(f"[clips] 高光 {k} 和上一个太近（{self.cfg.f('clips', 'min_gap'):.0f} 秒内），并进上一条")
            return None
        self.last_accept = t
        job = {"t": t, "kind": k, "info": {x: y for x, y in h.items() if x not in ("at", "kind")}, "due": t + self.post() + self.seg_secs() + 2, "done": False}
        self.jobs.append(job)
        self.log(f"[clips] 高光 {k}：{self.post():.0f} 秒后剪（前 {self.pre():.0f} 秒 + 后 {self.post():.0f} 秒）")
        return job

    def manual(self, note="手动"):
        """面板「现在切一个」：把刚才的 pre 秒 + 之后的 post 秒剪下来"""
        if not self.on():
            return {"ok": False, "error": "高光切片没开（[clips] enabled）"}
        if self.proc is None:
            return {"ok": False, "error": "现在没在录制：" + (self.err or "没开播，可以先点「开始录制」")}
        j = self.on_highlight_force("manual", {"at": time.time(), "who": str(note)[:10]})
        return {"ok": True, "due_in": int(max(0, j["due"] - time.time()))}

    def on_highlight_force(self, kind, h):
        self.stats["events"] += 1
        self.last_accept = float(h.get("at") or time.time())
        t = self.last_accept
        job = {"t": t, "kind": safe_kind(kind), "info": {x: y for x, y in h.items() if x not in ("at", "kind")}, "due": t + self.post() + self.seg_secs() + 2, "done": False}
        self.jobs.append(job)
        return job

    CMD_RX = None

    def on_event(self, ev, room, now=None):
        """观众发「高光 / 切片 / 剪辑」（短弹幕）→ 切一个。只观察，不吃弹幕。返回是否触发"""
        if ev.get("t") != "chat" or not self.on() or not self.cfg.b("clips", "viewer_cmd"):
            return False
        text = str(ev.get("text") or "").strip()
        if not text or len(text) > 12:
            return False
        kw = self.cfg.s("clips", "viewer_kw")
        if not kw or not re.search(kw, text):
            return False
        now = now or time.time()
        uid = str(ev.get("uid") or ev.get("name") or "")
        if now - self.user_last.get(uid, 0) < self.cfg.f("clips", "viewer_gap"):
            return False
        if self.proc is None and self.buf is None:
            return False                                          # 没在录：不答应也不记（免得骗人）
        self.user_last[uid] = now
        if len(self.user_last) > 500:
            self.user_last.clear()
        job = self.on_highlight("viewer", {"at": now, "who": str(ev.get("name") or "")[:12]})
        self.stats["viewer"] += 1
        if job and self.cfg.b("clips", "reply") and room is not None:
            self.say(room, f"收到 {str(ev.get('name') or '朋友')[:8]}！这一段我切下来了 ✂", now)
        return bool(job)

    def say(self, room, text, now):
        room._broadcast({"t": "say", "id": f"cl{int(now * 1000)}", "kind": "clips", "prio": 20, "text": text, "emotion": "开心", "audio": "", "dur": max(2.0, min(4.0, len(text) * 0.22)),
                         "to": "", "name": self.cfg.s("host", "name"), "role": "", "hot": False, "gift": "", "blocked": False, "ts": int(now * 1000), "browser_tts": False})

    # ---- 剪片
    async def do_job(self, j, loop):
        self.busy_jobs += 1
        try:
            r = await loop.run_in_executor(None, self.make_clip, j)
        except Exception as e:  # noqa
            r = {"ok": False, "error": repr(e)[:120]}
        finally:
            self.busy_jobs -= 1
        j["done"], j["running"] = True, False
        self.hist.append(dict(r, kind=j["kind"], t=j["t"]))
        del self.hist[:-10]
        self.last = self.hist[-1]
        if r.get("ok"):
            self.stats["clips"] += 1
            self.log(f"[clips] 剪好了：{r['name']}（{r['size'] // 1024} KB，{r['secs']:.0f} 秒）")
            if self.cfg.b("clips", "bark"):
                try:
                    await loop.run_in_executor(None, lambda: self.push(self.cfg.s("clips", "bark_text") or "切到一个高光", f"{KIND_LABEL.get(j['kind'], j['kind'])} · {r['name']}"))
                except Exception as e:  # noqa
                    self.log(f"[clips] Bark 推送出错：{e!r}")
        else:
            self.stats["failed"] += 1
            self.log(f"[clips] 剪片失败：{r.get('error')}")

    def _push(self, title, body):
        from ops.guard import bark_push
        ok, m = bark_push(self.cfg, title, body)
        self.log(f"[clips] {m}")
        return ok

    def make_clip(self, j):
        c = self.cfg
        buf = self.buf or self.old_buf
        if not buf or not os.path.isdir(buf):
            return {"ok": False, "error": "缓冲目录没了（录制已停止）"}
        t0, t1 = j["t"] - self.pre(), j["t"] + self.post()
        segs = list_segments(buf)
        pk = pick_segments(segs, t0, t1, all_closed=self.proc is None)
        if not pk:
            return {"ok": False, "error": "缓冲里没有这段时间的录像"}
        files, off = pk
        out_dir = self.out_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        name = clip_name(j["t"], j["kind"])
        out = out_dir / name
        lst = Path(buf) / f"job_{int(j['t'] * 1000)}.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in files), encoding="utf-8")
        ff = which_ffmpeg(c.s("clips", "ffmpeg"))
        enc = getattr(self, "enc", None) or pick_encoder(c.s("clips", "encoder"), self.encoders(ff))
        dur = t1 - t0
        w, h = c.i("clips", "out_w"), c.i("clips", "out_h")
        has_audio = self.has_audio(ff, files[0])
        tmp = out_dir / (name + ".part.mp4")
        cmd = build_clip_cmd(ff, enc, lst, off, dur, tmp, w, h, c.i("clips", "out_bitrate"), c.b("clips", "vertical"), has_audio)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size < 1000:
            try:
                tmp.unlink()
            except Exception:
                pass
            return {"ok": False, "error": f"ffmpeg 失败（{r.returncode}）：{(r.stderr or '')[-200:].strip()}"}
        tmp.replace(out)
        try:
            lst.unlink()
        except Exception:
            pass
        try:
            subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{min(self.pre(), max(0.5, dur / 2)):.2f}", "-i", str(out), "-frames:v", "1", "-vf", "scale=270:-2", "-q:v", "5", str(out_dir / (name[:-4] + ".jpg"))],
                           capture_output=True, timeout=30)
        except Exception:
            pass
        self.trim(out_dir)
        self._files = ([], 0.0)
        return {"ok": True, "name": name, "size": out.stat().st_size, "secs": dur, "files": len(files)}

    def has_audio(self, ff, f):
        try:
            r = subprocess.run([ff, "-hide_banner", "-i", str(f)], capture_output=True, text=True, timeout=10)
            return "Audio:" in (r.stderr or "")
        except Exception:
            return False

    def trim(self, d):
        mx = max(5, self.cfg.i("clips", "max_clips"))
        fs = sorted(p for p in d.iterdir() if NAME_RE.match(p.name))
        for p in fs[:-mx]:
            self.remove(p.name)

    # ---- 文件列表 / 删除（面板用）
    def files(self, limit=40, fresh=False):
        now = time.time()
        if not fresh and now - self._files[1] < 2.0:
            return self._files[0][:limit]
        out = []
        d = self.out_dir()
        try:
            for p in d.iterdir():
                m = NAME_RE.match(p.name)
                if not m:
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                out.append({"name": p.name, "kind": m.group(2), "label": KIND_LABEL.get(m.group(2), m.group(2)), "size": st.st_size,
                            "at": time.mktime(time.strptime(m.group(1), "%Y%m%d-%H%M%S")), "thumb": (d / (p.name[:-4] + ".jpg")).exists()})
        except FileNotFoundError:
            pass
        out.sort(key=lambda x: x["at"], reverse=True)
        self._files = (out, now)
        return out[:limit]

    def path_of(self, name):
        m = NAME_RE.match(name or "")
        if m:
            p = self.out_dir() / name
            return p if p.is_file() else None
        if re.fullmatch(r"\d{8}-\d{6}_[A-Za-z0-9_\-]{1,40}\.jpg", name or ""):
            p = self.out_dir() / name
            return p if p.is_file() else None
        return None

    def remove(self, name):
        if not NAME_RE.match(name or ""):
            return False
        d = self.out_dir()
        ok = False
        for n in (name, name[:-4] + ".jpg"):
            p = d / n
            if p.is_file():
                try:
                    p.unlink()
                    ok = ok or n == name
                except OSError:
                    pass
        self._files = ([], 0.0)
        return ok

    def state(self):
        now = time.time()
        segs = list_segments(self.buf) if self.buf else []
        files = self.files(30)
        return {"enabled": self.on(), "mode": self.cfg.s("clips", "mode"), "recording": self.proc is not None and self.proc.poll() is None, "since": self.since if self.proc is not None else None,
                "manual": self.manual_on, "live": self.is_live(), "want": self.want_record(), "err": self.err, "perm": {k: v for k, v in self.perm.items() if k != "checked"},
                "segments": len(segs), "buffer_secs": int(now - segs[0][0]) if segs else 0, "pending": len([j for j in self.jobs if not j.get("done")]), "stats": dict(self.stats),
                "last": self.last, "files": files, "count": len(files), "bytes": sum(f["size"] for f in files), "encoder": getattr(self, "enc", None),
                "geom": self.geom, "bark": self.cfg.b("clips", "bark")}

    def set_manual(self, on):
        self.manual_on = bool(on)
        if on:
            self.next_try = 0.0
        return {"ok": True, "manual": self.manual_on}

    def recheck(self):
        """面板「重新检测权限」：只检测，不弹窗"""
        ok, why, ff = self.check_env()
        self.next_try = 0.0
        return {"ok": ok, "msg": why or "环境正常（权限 / ffmpeg 都可以）", "perm": self.perm.get("ok")}
