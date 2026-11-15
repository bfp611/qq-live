# -*- coding: utf-8 -*-
"""网易云音乐正在播放 → 页面。

读取方式（按系统，见 osmusic.py）：
  macOS   MediaRemote（系统“正在播放”）。macOS 15.4 起私有接口被限制，所以用开源的
          ungive/mediaremote-adapter（借 /usr/bin/perl 的系统权限，tools/mr/ 下，BSD-3）。
  Windows GSMTC（系统媒体控件）；Linux  MPRIS（playerctl）。不支持/没装依赖时打一行日志并停用，不影响别的功能。
拿到：歌名/歌手/专辑/总时长/已播放位置(带时间戳，可外推)/播放中或暂停/封面。
没有歌曲 id → 用 歌名+歌手+专辑+时长 去网易云公开搜索接口匹配，再取 LRC 歌词（缓存在 .cache/music/）。
"""
import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path

import aiohttp

import osmusic

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      "Referer": "https://music.163.com/"}
CREDIT = re.compile(r"^\s*(作词|作曲|编曲|制作人|监制|混音|录音|母带|吉他|贝斯|鼓|和声|演唱|策划|统筹|出品|发行|OP|SP|词|曲|Lyrics?|Composer|Arranger|Producer)\s*[:：]", re.I)
TAG = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def norm(s):
    s = re.sub(r"[\(（\[【].*?[\)）\]】]", "", s or "")
    return re.sub(r"[\s\-_·•・.,，。!！?？'\"“”‘’~～]+", "", s).lower()


def parse_lrc(text):
    """-> [(秒, 文字)]，空文字的行保留（用来标记上一句的结束时间）。"""
    rows, offset = [], 0.0
    for raw in (text or "").splitlines():
        m = re.match(r"\s*\[offset:\s*(-?\d+)\]", raw, re.I)
        if m:
            offset = int(m.group(1)) / 1000.0
            continue
        tags = TAG.findall(raw)
        if not tags:
            continue
        body = TAG.sub("", raw).strip()
        for mm, ss, frac in tags:
            f = float("0." + frac) if frac else 0.0
            rows.append((int(mm) * 60 + int(ss) + f - offset, body))
    rows.sort(key=lambda r: r[0])
    return rows


def clean_lines(rows):
    """去掉“作词/作曲”等制作信息行，保留 [起点, 文字, 结束点]。"""
    out = []
    for i, (t, txt) in enumerate(rows):
        if not txt:
            continue
        if CREDIT.match(txt) and t < 40:
            continue
        end = rows[i + 1][0] if i + 1 < len(rows) else t + 6
        out.append([round(t, 2), txt, round(max(end, t + 0.5), 2)])
    return out


class Music:
    def __init__(self, root, broadcast, log=print, bundle="com.netease.163music", interval=1.0, lyric_offset=0.0, player=""):
        self.root = Path(root)
        self.broadcast = broadcast          # 同步函数 broadcast(dict)
        self.log = log
        self.bundle = bundle
        self.interval = interval
        self.lyric_offset = lyric_offset
        self.cache = self.root / ".cache" / "music"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.os = osmusic.os_name()
        self.source = None              # Windows / Linux 的读取器（osmusic.py）；macOS 仍走下面原来的 mediaremote-adapter
        self.unsupported = ""           # 没有可用读取方式时的原因（start() 里打日志）
        self.perl = "/usr/bin/perl"
        self.script = self.root / "tools" / "mr" / "mediaremote-adapter" / "bin" / "mediaremote-adapter.pl"
        self.fw = self.root / "tools" / "mr" / "mediaremote-adapter" / "build" / "MediaRemoteAdapter.framework"
        if self.os == "mac":
            self.method = "mediaremote-adapter" if (self.script.exists() and self.fw.exists() and os.path.exists(self.perl)) else (
                "nowplaying-cli" if self._which("nowplaying-cli") else None)
            if not self.method:
                self.unsupported = "tools/mr 没构建且没有 nowplaying-cli（见 README：macOS 安装）"
        else:
            self.bundle = ""            # 这两个系统用 [music] player（正则）过滤，在读取器里完成
            self.source, self.unsupported = osmusic.make_source(self.os, player, log)
            self.method = self.source.name if self.source else None
        self.state = {"t": "music", "on": False}
        self.lyric = {"t": "lyric", "key": "", "lines": [], "found": False}
        self.key = None
        self.cover = None               # (key, bytes, mime)
        self._lyric_task = None
        self._miss = {}                 # key -> 下次可重试的时间
        self._track_seen = 0.0          # nowplaying-cli 回退用：观察到这首歌开始的时刻
        self._session = None
        self._task = None

    @staticmethod
    def _which(n):
        for p in os.environ.get("PATH", "").split(os.pathsep) + ["/opt/homebrew/bin", "/usr/local/bin"]:
            if os.access(os.path.join(p, n), os.X_OK):
                return os.path.join(p, n)

    def start(self):
        if not self.method:
            self.log(f"音乐：{osmusic.OS_LABEL[self.os]} 上没有可用的“正在播放”读取方式（{self.unsupported}），"
                     "千千静听/桌面歌词/点歌已停用，其它功能照常")
            return
        flt = self.bundle or (getattr(self.source, "pattern", None) and self.source.pattern.pattern) or ""
        self.log(f"音乐：用 {self.method} 读取网易云音乐的正在播放" + (f"（只认 {flt}）" if flt else "（不过滤播放器）"))
        self._task = asyncio.ensure_future(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
        if self._session:
            await self._session.close()

    # ---------- 读取正在播放 ----------
    async def _run(self, *args):
        p = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            out, _ = await asyncio.wait_for(p.communicate(), 5)
        except asyncio.TimeoutError:
            p.kill()
            return None
        return out.decode("utf-8", "replace")

    async def read_now(self):
        """-> dict(title, artist, album, duration, pos, playing, bundle, art) 或 None"""
        if self.source is not None:
            return await self.source.read_now()
        if self.method == "mediaremote-adapter":
            t0 = time.time()
            out = await self._run(self.perl, str(self.script), str(self.fw), "get", "--now")
            if not out or not out.strip() or out.strip() == "null":
                return None
            d = json.loads(out)
            if not d:
                return None
            pos = d.get("elapsedTimeNow")
            if pos is None:
                pos = d.get("elapsedTime") or 0
                if d.get("playing") and d.get("timestamp"):
                    try:
                        import datetime as dt
                        ts = dt.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).timestamp()
                        pos += (time.time() - ts) * (d.get("playbackRate") or 1)
                    except Exception:
                        pass
            else:
                pos += (time.time() - t0) / 2          # adapter 在进程中间时刻算的
            art = None
            if d.get("artworkData"):
                import base64
                try:
                    art = (base64.b64decode(d["artworkData"]), d.get("artworkMimeType") or "image/jpeg")
                except Exception:
                    pass
            return dict(title=d.get("title") or "", artist=d.get("artist") or "", album=d.get("album") or "",
                        duration=float(d.get("duration") or 0), pos=float(pos), playing=bool(d.get("playing")),
                        bundle=d.get("bundleIdentifier") or "", art=art)
        # 回退：nowplaying-cli（拿不到时间戳，位置只能从“发现换歌”那一刻开始自己算）
        out = await self._run(self._which("nowplaying-cli"), "get-raw")
        if not out or "kMRMediaRemoteNowPlayingInfoTitle" not in out:
            return None
        txt = out.strip()
        d = {}
        for k in ("Title", "Artist", "Album", "ClientBundleIdentifier"):
            m = re.search(r'"kMRMediaRemoteNowPlayingInfo%s"\s*:\s*"((?:[^"\\]|\\.)*)"' % k, txt)
            d[k] = json.loads('"' + m.group(1) + '"') if m else ""
        num = lambda k: float((re.search(r'"kMRMediaRemoteNowPlayingInfo%s"\s*:\s*([\d.]+)' % k, txt) or [0, 0])[1])
        return dict(title=d["Title"], artist=d["Artist"], album=d["Album"], duration=num("Duration"), pos=None,
                    playing=num("PlaybackRate") > 0, bundle=d["ClientBundleIdentifier"], art=None)

    async def _loop(self):
        fails = 0
        while True:
            try:
                n = await self.read_now()
                fails = 0
                self._update(n)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa
                fails += 1
                if fails in (1, 10, 100):
                    self.log("音乐：读取失败", repr(e))
                self._update(None)
            await asyncio.sleep(self.interval)

    # ---------- 状态 ----------
    def _update(self, n):
        if not n or not n["title"] or (self.bundle and n["bundle"] != self.bundle):
            if self.state.get("on"):
                self.state = {"t": "music", "on": False}
                self.broadcast(self.state)
            self.key = None
            return
        key = hashlib.md5(f"{n['title']}|{n['artist']}|{n['album']}|{round(n['duration'])}".encode()).hexdigest()[:12]
        if key != self.key:
            self.key = key
            self._track_seen = time.time()
            self.cover = None
            self.lyric = {"t": "lyric", "key": key, "lines": [], "found": False, "loading": True}
            self.log(f"音乐：{n['artist']} - {n['title']}（{n['album']}，{n['duration']:.0f}s）")
            self.broadcast(self.lyric)
            if self._lyric_task:
                self._lyric_task.cancel()
            self._lyric_task = asyncio.ensure_future(self._load_lyric(key, n))
        if n.get("art") and (not self.cover or self.cover[0] != key):
            self.cover = (key, n["art"][0], n["art"][1])
        pos = n["pos"]
        if pos is None:      # 回退方式
            pos = (time.time() - self._track_seen) if n["playing"] else 0
        pos = max(0.0, min(pos, n["duration"] or pos))
        self.state = {"t": "music", "on": True, "key": key, "title": n["title"], "artist": n["artist"], "album": n["album"],
                      "duration": round(n["duration"], 2), "pos": round(pos, 2), "playing": n["playing"],
                      "cover": f"/music/cover?k={key}" if self.cover and self.cover[0] == key else "",
                      "offset": self.lyric_offset, "method": self.method, "ts": int(time.time() * 1000)}
        self.broadcast(self.state)

    # ---------- 歌词 ----------
    async def _http(self, url):
        if not self._session:
            self._session = aiohttp.ClientSession(headers=UA, timeout=aiohttp.ClientTimeout(total=10))
        async with self._session.get(url) as r:
            return json.loads(await r.text())

    async def _post(self, url, data):
        if not self._session:
            self._session = aiohttp.ClientSession(headers=UA, timeout=aiohttp.ClientTimeout(total=10))
        async with self._session.post(url, data=data) as r:
            return json.loads(await r.text())

    async def _load_lyric(self, key, n):
        f = self.cache / f"{key}.json"
        if f.exists():
            try:
                d = json.loads(f.read_text("utf-8"))
                self._set_lyric(key, d)
                return
            except Exception:
                pass
        if self._miss.get(key, 0) > time.time():
            self._set_lyric(key, {"id": 0, "lines": []})
            return
        try:
            sid = await self._search(n)
            lines = []
            if sid:
                # 注意 lv/kv/tv 要用 -1：用 lv=1 有些歌（例如许嵩的）会返回空歌词
                d = await self._http(f"https://music.163.com/api/song/lyric?os=pc&id={sid}&lv=-1&kv=-1&tv=-1")
                lines = clean_lines(parse_lrc((d.get("lrc") or {}).get("lyric")))
                if not lines:    # 备用接口
                    d = await self._http(f"https://music.163.com/api/song/media?id={sid}")
                    lines = clean_lines(parse_lrc(d.get("lyric")))
            res = {"id": sid or 0, "lines": lines}
            if lines:
                f.write_text(json.dumps(res, ensure_ascii=False), "utf-8")
            else:
                self._miss[key] = time.time() + 120
            self._set_lyric(key, res)
            self.log(f"音乐：歌词 {'%d 行' % len(lines) if lines else '没找到'}（网易云歌曲 id={sid or '无'}）")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa
            self.log("音乐：取歌词失败", repr(e))
            self._miss[key] = time.time() + 20
            self._set_lyric(key, {"id": 0, "lines": []})

    def _set_lyric(self, key, d):
        if key != self.key:
            return
        self.lyric = {"t": "lyric", "key": key, "id": d.get("id", 0), "lines": d.get("lines", []), "found": bool(d.get("lines"))}
        self.broadcast(self.lyric)

    async def _search(self, n):
        from urllib.parse import quote
        q = quote(f"{n['title']} {n['artist'].split('/')[0].split(',')[0].split('、')[0]}")
        d = await self._http(f"https://music.163.com/api/search/get/web?csrf_token=&hlpretag=&hlposttag=&s={q}&type=1&offset=0&total=true&limit=10")
        songs = (d.get("result") or {}).get("songs") or []
        if not songs:
            d = await self._http("https://music.163.com/api/search/get/web?s=%s&type=1&offset=0&limit=10" % quote(n["title"]))
            songs = (d.get("result") or {}).get("songs") or []
        nt, na, nal = norm(n["title"]), norm(n["artist"]), norm(n["album"])
        best, bs = None, -1
        for s in songs:
            sc = 0
            if norm(s.get("name")) == nt:
                sc += 4
            elif nt and (nt in norm(s.get("name")) or norm(s.get("name")) in nt):
                sc += 1
            arts = [norm(a.get("name")) for a in s.get("artists", [])]
            if any(a and a in na for a in arts):
                sc += 3
            if nal and norm((s.get("album") or {}).get("name")) == nal:
                sc += 2
            dd = abs((s.get("duration") or 0) / 1000.0 - n["duration"]) if n["duration"] else 99
            sc += 3 if dd < 1.5 else 2 if dd < 4 else 1 if dd < 10 else 0
            if sc > bs:
                best, bs = s, sc
        return best["id"] if best and bs >= 5 else None
