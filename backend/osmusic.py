# -*- coding: utf-8 -*-
"""跨平台：各系统「正在播放」读取 + 点歌时让网易云客户端播放/切歌。

  macOS   MediaRemote（mediaremote-adapter / nowplaying-cli）→ 代码仍在 music.py 里（原样保留），点歌用 `open -a NeteaseMusic orpheus://…`
  Windows GSMTC（系统媒体传输控件，Python 包 winrt-*）→ GsmtcSource；点歌用 os.startfile("orpheus://…")，切歌用 GSMTC 的 skip_next
  Linux   MPRIS（D-Bus）→ MprisSource，通过 `playerctl` 命令读取；点歌先试 MPRIS OpenUri，再试 xdg-open orpheus://…

所有来源统一返回 dict(title, artist, album, duration, pos, playing, bundle, art)；pos=None 表示该播放器不上报进度（调用方自己用秒表推算）。
读不到 / 系统不支持：make_source() 返回 (None, 原因)，调用方打一行清楚的日志并停用音乐功能，其它功能不受影响。
winrt / playerctl 都只在对应系统上才会被用到（import 是惰性的），所以 macOS 上不装它们也能正常跑。
"""
import asyncio
import base64
import json
import os
import re
import shutil
import sys
import time

# 各系统默认认哪些播放器（对播放器标识做不区分大小写的正则搜索）。配置项 [music] player 可覆盖；写 any / * = 不过滤
DEFAULT_PLAYER = {
    "win": r"cloudmusic|netease|163music|wangyiyun",                                     # GSMTC 的 source_app_user_model_id，例如 cloudmusic.exe
    "linux": r"netease|cloudmusic|cloud-music|163music|yesplaymusic|orpheus|ncm",          # MPRIS 的 playerName，例如 netease-cloud-music
}


def os_name(platform=None):
    p = platform or sys.platform
    if p == "darwin":
        return "mac"
    if p.startswith("win") or p in ("cygwin", "msys"):
        return "win"
    if p.startswith("linux"):
        return "linux"
    return "other"


OS_LABEL = {"mac": "macOS", "win": "Windows", "linux": "Linux", "other": "此系统"}


def orpheus_url(song_id, cmd="play", kind="song"):
    """网页「在客户端打开」用的协议：orpheus://<base64 的 JSON>。id 必须是字符串（写成数字客户端会把播放器弄丢）。"""
    payload = base64.b64encode(json.dumps({"type": kind, "id": str(song_id), "cmd": cmd}, separators=(",", ":")).encode()).decode()
    return f"orpheus://{payload}"


def player_regex(player, os_key):
    """配置的 player → 编译后的正则；None = 不过滤。"""
    p = (player or "").strip()
    if p.lower() in ("any", "*", "all", "任意"):
        return None
    return re.compile(p or DEFAULT_PLAYER.get(os_key, ""), re.I) if (p or DEFAULT_PLAYER.get(os_key)) else None


# ======================================================================================================
# Windows：GSMTC
# ======================================================================================================
class GsmtcSource:
    """Windows 10/11 的系统媒体传输控件。需要：pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Storage.Streams
    （requirements.txt 里已按 sys_platform=="win32" 写好，install.ps1 会装）。

    注意：网易云 Windows 客户端要在 设置 → 常规 → 系统 里勾选「开启SMTC」才会上报；有的版本不上报进度（pos=None，这里自己秒表推算）。"""
    name = "gsmtc"

    def __init__(self, pattern, log=print):
        self.pattern, self.log = pattern, log
        self._art_key, self._art = None, None
        self._last_app = None

    # --- 与 winrt 打交道的部分（只有这一个函数碰 WinRT；测试时整个替换成假数据） ---
    async def _snapshot(self, want_art):
        try:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Mgr
        except ImportError:
            from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Mgr   # 旧包名
        for extra in ("winrt.windows.foundation", "winrt.windows.foundation.collections", "winrt.windows.storage.streams"):
            try:                          # pywinrt 要先 import 用到的命名空间，IAsyncOperation / IVectorView 才能用
                __import__(extra)
            except ImportError:
                pass
        mgr = await Mgr.request_async()
        out = []
        for s in mgr.get_sessions():
            it = {"app": s.source_app_user_model_id or ""}
            try:
                pr = await s.try_get_media_properties_async()
                it.update(title=pr.title or "", artist=pr.artist or "", album=pr.album_title or "")
                it["_thumb"] = pr.thumbnail
            except Exception as e:  # noqa
                it.update(title="", artist="", album="", err=repr(e))
            try:
                tl = s.get_timeline_properties()
                try:
                    upd = tl.last_updated_time.timestamp()
                    upd = upd if upd > 1e9 else None          # 没上报过时是 0001/1601 年的默认值
                except Exception:
                    upd = None
                it.update(pos=tl.position.total_seconds(), start=tl.start_time.total_seconds(), end=tl.end_time.total_seconds(), updated=upd)
            except Exception:
                it.update(pos=None, start=0, end=0, updated=None)
            try:
                it["status"] = int(s.get_playback_info().playback_status)      # 4=Playing 5=Paused 3=Stopped
            except Exception:
                it["status"] = 0
            it["_session"] = s
            out.append(it)
        return out

    async def _read_art(self, thumb):
        """GSMTC 缩略图 → (bytes, mime)。尽力而为。"""
        from winrt.windows.storage.streams import DataReader
        stream = await thumb.open_read_async()
        size = int(stream.size)
        if not size or size > 4_000_000:
            return None
        reader = DataReader(stream)
        await reader.load_async(size)
        buf = bytearray(size)
        reader.read_bytes(buf)
        return bytes(buf), (stream.content_type or "image/jpeg")

    # --- 纯逻辑（可测试） ---
    def pick(self, sessions):
        cand = [s for s in sessions if (not self.pattern or self.pattern.search(s.get("app", "")))]
        playing = [s for s in cand if s.get("status") == 4]
        return (playing or cand or [None])[0]

    @staticmethod
    def convert(s, now=None):
        now = now or time.time()
        playing = s.get("status") == 4
        end, start = s.get("end") or 0, s.get("start") or 0
        dur = max(0.0, end - start)
        pos = s.get("pos")
        if not dur or pos is None or (not pos and not s.get("updated")):
            pos = None                       # 该播放器没有上报进度：交给调用方的秒表
        elif playing and s.get("updated"):
            pos = pos + max(0.0, now - s["updated"])
        return dict(title=s.get("title") or "", artist=s.get("artist") or "", album=s.get("album") or "", duration=dur, pos=pos,
                    playing=playing, bundle=s.get("app", ""), art=None)

    async def read_now(self):
        snap = await self._snapshot(True)
        s = self.pick(snap)
        if not s or not s.get("title"):
            return None
        self._last_app = s.get("app")
        d = self.convert(s)
        key = (d["title"], d["artist"])
        if key != self._art_key:
            self._art_key, self._art = key, None
            if s.get("_thumb") is not None:
                try:
                    self._art = await self._read_art(s["_thumb"])
                except Exception:
                    self._art = None
        d["art"] = self._art
        return d

    async def next(self):
        snap = await self._snapshot(False)
        s = self.pick(snap)
        if not s:
            return False
        return bool(await s["_session"].try_skip_next_async())

    async def command(self, cmd):
        """play | pause | toggle | next | previous → 对「正在播放」的会话发 GSMTC 媒体键。"""
        snap = await self._snapshot(False)
        s = self.pick(snap)
        if not s:
            return False
        sess = s["_session"]
        fn = {"play": "try_play_async", "pause": "try_pause_async", "toggle": "try_toggle_play_pause_async",
              "next": "try_skip_next_async", "previous": "try_skip_previous_async"}.get(cmd)
        return bool(fn and await getattr(sess, fn)())


# ======================================================================================================
# Linux：MPRIS（playerctl）
# ======================================================================================================
class MprisSource:
    """Linux：通过 `playerctl`（apt install playerctl）读 MPRIS。网易云 Linux 版（netease-cloud-music）会注册
    org.mpris.MediaPlayer2.netease-cloud-music。playerctl 的 position/length 单位是微秒。"""
    name = "mpris"
    SEP = "\x1f"
    FMT = SEP.join(["{{playerName}}", "{{status}}", "{{position}}", "{{mpris:length}}", "{{xesam:title}}",
                    "{{xesam:artist}}", "{{xesam:album}}", "{{mpris:artUrl}}"])

    def __init__(self, pattern, playerctl, log=print):
        self.pattern, self.playerctl, self.log = pattern, playerctl, log
        self._art_key, self._art = None, None
        self.player = None           # 最近一次读到的播放器名（点歌/切歌时用）

    async def _run(self, *args, timeout=5):
        p = await asyncio.create_subprocess_exec(self.playerctl, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            out, _ = await asyncio.wait_for(p.communicate(), timeout)
        except asyncio.TimeoutError:
            p.kill()
            return None, -1
        return out.decode("utf-8", "replace"), p.returncode

    def parse(self, text):
        """playerctl -a metadata --format … 的输出（每个播放器一行）→ 候选列表"""
        out = []
        for line in (text or "").splitlines():
            f = line.split(self.SEP)
            if len(f) < 8:
                continue
            name, status, pos, length, title, artist, album, art = f[:8]
            num = lambda x: float(x) if re.fullmatch(r"-?\d+(\.\d+)?", x or "") else None
            out.append(dict(player=name, status=status, pos=num(pos), length=num(length), title=title, artist=artist, album=album, art=art))
        return out

    def pick(self, cands):
        cand = [c for c in cands if (not self.pattern or self.pattern.search(c["player"]))]
        playing = [c for c in cand if c["status"] == "Playing"]
        return (playing or cand or [None])[0]

    @staticmethod
    def convert(c):
        dur = (c["length"] or 0) / 1e6
        pos = None if c["pos"] is None else c["pos"] / 1e6
        # 有的播放器 Position 恒为 0（不上报）：位置交给调用方的秒表
        if pos == 0 and c["status"] == "Playing" and dur == 0:
            pos = None
        return dict(title=c["title"], artist=c["artist"], album=c["album"], duration=dur, pos=pos,
                    playing=c["status"] == "Playing", bundle=c["player"], art=None)

    async def _fetch_art(self, url):
        if not url:
            return None
        try:
            if url.startswith("file://"):
                from urllib.parse import unquote, urlparse
                path = unquote(urlparse(url).path)
                with open(path, "rb") as fh:
                    data = fh.read(4_000_000)
                mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
                return data, mime
            if url.startswith("http"):
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as ss:
                    async with ss.get(url) as r:
                        if r.status == 200:
                            return await r.read(), r.headers.get("Content-Type", "image/jpeg")
        except Exception:
            pass
        return None

    async def read_now(self):
        text, rc = await self._run("-a", "metadata", "--format", self.FMT)
        if not text or rc != 0:
            return None
        c = self.pick(self.parse(text))
        if not c or not c["title"]:
            return None
        self.player = c["player"]
        d = self.convert(c)
        key = (c["title"], c["artist"], c["art"])
        if key != self._art_key:
            self._art_key, self._art = key, await self._fetch_art(c["art"])
        d["art"] = self._art
        return d

    async def _target(self):
        if self.player:
            return self.player
        text, _ = await self._run("-l")
        for n in (text or "").split():
            if not self.pattern or self.pattern.search(n):
                return n
        return None

    async def next(self):
        t = await self._target()
        if not t:
            return False
        _, rc = await self._run("-p", t, "next")
        return rc == 0

    async def command(self, cmd):
        """play | pause | toggle | next | previous → playerctl。"""
        t = await self._target()
        verb = {"play": "play", "pause": "pause", "toggle": "play-pause", "next": "next", "previous": "previous"}.get(cmd)
        if not t or not verb:
            return False
        _, rc = await self._run("-p", t, verb)
        return rc == 0

    async def open_uri(self, uri):
        """MPRIS OpenUri（playerctl open）。播放器不支持 / 没有对应播放器就返回 False。"""
        t = await self._target()
        if not t:
            return False
        _, rc = await self._run("-p", t, "open", uri)
        return rc == 0


# ======================================================================================================
# 工厂
# ======================================================================================================
def make_source(os_key, player="", log=print, which=shutil.which):
    """-> (source 或 None, 失败原因)。macOS 不走这里（music.py 里原来的 mediaremote-adapter 逻辑不动）。"""
    pat = player_regex(player, os_key)
    if os_key == "win":
        try:
            try:
                import winrt.windows.media.control  # noqa: F401
            except ImportError:
                import winsdk.windows.media.control  # noqa: F401
        except ImportError:
            return None, ("没装 WinRT 包：在项目目录运行 install.ps1，或  .venv\\Scripts\\pip install winrt-runtime "
                          "winrt-Windows.Media.Control winrt-Windows.Storage.Streams winrt-Windows.Foundation winrt-Windows.Foundation.Collections")
        return GsmtcSource(pat, log), ""
    if os_key == "linux":
        pc = which("playerctl")
        if not pc:
            return None, "没找到 playerctl：sudo apt install playerctl（Fedora: dnf install playerctl；Arch: pacman -S playerctl）"
        return MprisSource(pat, pc, log), ""
    return None, f"{OS_LABEL.get(os_key, '此系统')} 暂不支持读取网易云的「正在播放」（只支持 macOS / Windows / Linux）"


# ======================================================================================================
# 点歌：让网易云客户端播放 / 切歌
# ======================================================================================================
class Control:
    """open_methods() → [(名字, 异步函数(url) -> bool)]，按顺序尝试（每次尝试后由 Jukebox 用「正在播放」核对是否真的开始了）。"""

    def __init__(self, os_key, source=None, app_name="NeteaseMusic", log=print, which=shutil.which):
        self.os, self.source, self.app_name, self.log, self.which = os_key, source, app_name, log, which

    def available(self):
        return bool(self.open_methods())

    def reason(self):
        if self.os == "mac":
            return "" if os.path.exists("/usr/bin/open") else "没有 /usr/bin/open"
        if self.os == "win":
            return "" if hasattr(os, "startfile") else "os.startfile 不可用"
        if self.os == "linux":
            return "" if (self.source or self.which("xdg-open")) else "既没有 playerctl（MPRIS OpenUri）也没有 xdg-open"
        return f"{OS_LABEL.get(self.os)} 不支持点歌播放"

    def open_methods(self):
        if self.os == "mac":
            return [("open -a", self._mac_open)] if os.path.exists("/usr/bin/open") else []
        if self.os == "win":
            return [("os.startfile", self._win_open)] if hasattr(os, "startfile") else []
        if self.os == "linux":
            m = []
            if isinstance(self.source, MprisSource):
                m.append(("MPRIS OpenUri", self.source.open_uri))
            if self.which("xdg-open"):
                m.append(("xdg-open", self._xdg_open))
            return m
        return []

    async def _exec(self, *args):
        p = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return await p.wait()

    async def _mac_open(self, url):
        return await self._exec("/usr/bin/open", "-a", self.app_name, url) == 0

    async def _win_open(self, url):
        # ShellExecute 打开 orpheus:// 协议（网易云安装时注册）。第三方项目 Seraph310/cloudmusic-desktop-mcp 在 Win11 + 客户端 3.1.24 上用的就是同样的格式
        try:
            await asyncio.get_running_loop().run_in_executor(None, os.startfile, url)
            return True
        except OSError as e:
            self.log("点歌：os.startfile 打开 orpheus:// 失败（网易云没装或没注册协议？）", repr(e))
            return False

    async def _xdg_open(self, url):
        return await self._exec(self.which("xdg-open"), url) == 0

    async def next(self):
        """切到播放器的下一首。-> 是否发出了命令"""
        if self.os == "mac":
            cli = _mac_which("nowplaying-cli")
            if cli:
                await self._exec(cli, "next")
                return True
            return False
        if self.source is not None and hasattr(self.source, "next"):
            try:
                return bool(await self.source.next())
            except Exception as e:  # noqa
                self.log("点歌：切歌失败", repr(e))
        return False

    async def command(self, cmd):
        """play | pause | toggle | next | previous → 当前平台的系统媒体键（mac: nowplaying-cli；win: GSMTC；linux: playerctl）。-> 是否发出了命令"""
        if cmd not in ("play", "pause", "toggle", "next", "previous"):
            return False
        if self.os == "mac":
            cli = _mac_which("nowplaying-cli")
            if cli:
                await self._exec(cli, {"toggle": "togglePlayPause"}.get(cmd, cmd))
                return True
            return False
        if self.source is not None and hasattr(self.source, "command"):
            try:
                return bool(await self.source.command(cmd))
            except Exception as e:  # noqa
                self.log(f"点歌：{cmd} 失败", repr(e))
        return False


def _mac_which(n):
    for p in os.environ.get("PATH", "").split(os.pathsep) + ["/opt/homebrew/bin", "/usr/local/bin"]:
        if os.access(os.path.join(p, n), os.X_OK):
            return os.path.join(p, n)
