# -*- coding: utf-8 -*-
"""弹幕点歌 → 在网易云音乐客户端（macOS / Windows / Linux）里播放。

弹幕格式（开头必须是这几个词之一）：   点歌 稻香  /  点歌 周杰伦 稻香  /  点播 xxx  /  来一首 xxx
播放方式：orpheus://<base64 的 {"type":"song","id":"<歌曲id字符串>","cmd":"play"}>
  macOS：open -a NeteaseMusic <url>；Windows：os.startfile(<url>)；Linux：MPRIS OpenUri（playerctl open），不行再 xdg-open <url>（见 osmusic.py）
  （id 必须是字符串；写成数字客户端会把播放器弄丢。没版权/下架的歌客户端会直接无视，所以播放后用「正在播放」核对歌名，核对不上就当不可播放）
找歌：网易云公开接口 cloudsearch，按「歌名/歌手是否命中 + 热度」打分，惩罚翻唱/童声/伴奏/DJ 等版本。
队列：当前点歌歌曲快放完（剩 near_end 秒）或被客户端自己切走时，自动播下一首；队列空了就还给客户端自己的播放列表。
"""
import asyncio
import re
import time
from collections import deque

import osmusic
from music import norm

CMD = re.compile(r"^\s*(?:点歌|点播|点一首|来一首|来首)[\s:：,，、]*(.+?)\s*$")
BAD_VER = re.compile(r"翻唱|cover|童声|伴奏|dj|remix|钢琴|女声|男声|纯音乐|铃声|抖音|live|现场|降调|升调|加速|慢速|吉他|古筝|版|ver\b", re.I)


def parse_command(text):
    m = CMD.match(text or "")
    if not m:
        return None
    q = re.sub(r"[《》“”\"']", " ", m.group(1)).strip()
    q = re.sub(r"\s+", " ", q)
    return q[:40] if q else None


class Song:
    def __init__(self, d, user="", uid=""):
        self.id = str(d["id"])
        self.title = d["name"]
        self.artist = "/".join(a["name"] for a in d.get("ar", []))
        self.duration = (d.get("dt") or 0) / 1000.0
        self.vip = d.get("fee") in (1, 4)
        self.user, self.uid = user, uid

    def ui(self):
        return {"title": self.title, "artist": self.artist, "user": self.user, "id": self.id}


class Jukebox:
    def __init__(self, cfg, music, log, emit, ack, notify):
        self.music, self.log, self.emit, self.ack, self.notify = music, log, emit, ack, notify
        self.enabled = cfg.b("music", "jukebox")
        self.max_queue = cfg.i("music", "max_queue")
        self.cooldown = cfg.f("music", "user_cooldown")
        self.max_per_user = cfg.i("music", "max_per_user")
        self.allow_vip = cfg.b("music", "allow_vip")
        self.first_immediate = cfg.b("music", "first_immediate")
        self.near_end = cfg.f("music", "near_end")
        self.verify_timeout = cfg.f("music", "verify_timeout")
        self.app_name = cfg.s("music", "app_name") or "NeteaseMusic"
        self.control = osmusic.Control(music.os, music.source, self.app_name, log)
        self.queue = deque()
        self.current = None
        self.started = 0.0
        self.last_req = {}
        self.inbox = asyncio.Queue()
        self.history = deque(maxlen=20)
        self._busy = False          # 正在启动一首歌（核对中）
        self._last_key = None
        self._off_since = None
        self._tasks = []

    def start(self):
        if not self.enabled:
            return
        why = "" if self.music.method else f"读不到网易云的「正在播放」（{self.music.unsupported}），没法核对有没有播起来"
        if not why and not self.control.available():
            why = self.control.reason()
        if why:
            self.enabled = False
            self.log(f"点歌：{osmusic.OS_LABEL[self.music.os]} 上已停用——{why}。弹幕里的「点歌」会当普通聊天处理")
            return
        self.log(f"点歌：已开启（队列最多 {self.max_queue} 首，每人冷却 {self.cooldown:g}s，每人最多排 {self.max_per_user} 首）")
        self._tasks = [asyncio.ensure_future(self._worker()), asyncio.ensure_future(self._loop())]

    def stop(self):
        for t in self._tasks:
            t.cancel()

    # ---------- 状态 ----------
    def snapshot(self):
        return {"t": "jukebox", "on": self.enabled, "current": self.current.ui() if self.current else None,
                "queue": [s.ui() for s in self.queue]}

    def _push(self):
        self.notify(self.snapshot())

    # ---------- 入口：弹幕 ----------
    def on_chat(self, ev, room=None):
        """返回 True = 这条弹幕是点歌命令（不再交给 AI 主播当普通聊天）。"""
        q = parse_command(ev.get("text"))
        if not q or not self.enabled:
            return False
        self.inbox.put_nowait((ev, q, room))
        return True

    def say(self, text, room=None, ack=None):
        self.emit({"t": "sys", "text": text}, room)
        if ack:
            self.ack(ack, room)

    async def _worker(self):
        while True:
            ev, q, room = await self.inbox.get()
            try:
                await self._handle(ev, q, room)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa
                self.log("点歌：处理出错", repr(e))

    async def _handle(self, ev, q, room):
        user = (ev.get("name") or "神秘人")[:12]
        uid = str(ev.get("uid") or user)
        now = time.time()
        if now - self.last_req.get(uid, 0) < self.cooldown:
            self.say(f"{user} 点歌太频繁啦，请 {int(self.cooldown - (now - self.last_req[uid])) + 1} 秒后再点", room)
            return
        if len(self.queue) >= self.max_queue:
            self.say(f"点歌队列已满（{self.max_queue} 首），请稍后再点", room)
            return
        if sum(1 for s in self.queue if s.uid == uid) >= self.max_per_user:
            self.say(f"{user} 已经点了 {self.max_per_user} 首在排队啦，等放完再点吧", room)
            return
        self.last_req[uid] = now
        song = await self.find(q)
        if not song:
            self.say(f"{user} 点的「{q}」没找到能播放的版本（可能没有版权），换一首试试", room, ack=f"{user}点的{q}没找到，换一首吧")
            return
        song.user, song.uid = user, uid
        if any(s.id == song.id for s in self.queue) or (self.current and self.current.id == song.id):
            self.say(f"《{song.title}》已经在点歌队列里啦", room)
            return
        self.queue.append(song)
        self.log(f"点歌：{user} 点了 {song.artist} - {song.title}（id {song.id}）")
        busy_now = self.current is not None or self._busy
        if busy_now:
            self.say(f"{user} 点了《{song.title}》- {song.artist}，排在第 {len(self.queue)} 位", room,
                     ack=f"收到，{user}点的{self._short(song.title)}，排第{len(self.queue)}位")
        else:
            self.say(f"{user} 点了《{song.title}》- {song.artist}", room, ack=f"收到，马上播放{user}点的{self._short(song.title)}")
        self._push()

    @staticmethod
    def _short(t):
        return re.sub(r"\s*[\(（].*?[\)）]", "", t).strip() or t

    # ---------- 找歌 ----------
    async def find(self, q):
        try:
            d = await self.music._post("https://music.163.com/api/cloudsearch/pc", {"s": q, "type": 1, "limit": 30, "offset": 0})
        except Exception as e:  # noqa
            self.log("点歌：搜索失败", repr(e))
            return None
        songs = (d.get("result") or {}).get("songs") or []
        toks = [norm(t) for t in q.split() if norm(t)]
        nq = norm(q)
        scored = []
        for rank, s in enumerate(songs):
            pv = s.get("privilege") or {}
            if (pv.get("st") or 0) < 0 or s.get("fee") == 4 or (s.get("fee") == 1 and not self.allow_vip):
                continue      # 无版权/下架、付费专辑、不允许 VIP 歌
            raw = s["name"]
            name, arts = norm(raw), [norm(a["name"]) for a in s.get("ar", [])]
            full, tok = name == nq, name in toks
            ts = 6 if (full or tok) else 3 if (any(t and t in name for t in toks) or (nq and nq in name)) else 2 if any(name and name in t for t in toks) else 0
            art = any(a and (a in nq or a in toks) for a in arts)
            sc = ts + ((5 if len(toks) > 1 or name != nq else 2) if art else 0)
            if sc < 3:
                continue
            if len(toks) > 1 and (ts == 0 or not (full or art)):
                continue      # 「歌手 歌名」：歌名没对上，或歌手没对上（例如周杰伦不在网易云）→ 宁可没找到，也不放翻唱版/别的歌
            extra = raw + "".join(s.get("alia") or []) + (s.get("al") or {}).get("name", "")
            if BAD_VER.search(extra) and not BAD_VER.search(q):
                if len(toks) > 1 and not art:
                    continue  # 歌手没对上、还是 DJ/翻唱/伴奏版 → 肯定不是想要的
                sc -= 4
            if re.search(r"[\(（]", raw) and not re.search(r"[\(（]", q):
                sc -= 3       # 带括号备注的一般是别的版本（0.8x、原唱xx、伴奏……）
            if "原唱" in extra and "原唱" not in q:
                sc -= 4
            sc += (s.get("pop") or 0) / 100.0 * 3 + (30 - rank) / 30.0 * 1.5
            if s.get("fee") == 1:
                sc -= 0.3
            scored.append((sc, s))
        scored.sort(key=lambda x: -x[0])
        for sc, s in scored[:4]:
            if await self._copyright_ok(s["id"]):
                return Song(s)
        return None

    async def _copyright_ok(self, sid):
        """匿名查询播放地址：code 404 = 没版权（客户端一定播不了）；-110 = 需要 VIP/登录（用户账号可能能播，放行）。"""
        try:
            d = await self.music._http(f"https://music.163.com/api/song/enhance/player/url?ids=%5B{sid}%5D&br=128000")
            return (d["data"][0].get("code") != 404)
        except Exception:
            return True

    # ---------- 播放 ----------
    def _now(self):
        st = self.music.state
        if not st.get("on"):
            return None
        pos = st["pos"] + ((time.time() - st["ts"] / 1000.0) if st.get("playing") else 0)
        return st, min(pos, st.get("duration") or pos)

    async def play(self, song):
        self._busy = True
        try:
            before = self.music.state.get("key") if self.music.state.get("on") else None
            url = osmusic.orpheus_url(song.id)
            for mname, fn in self.control.open_methods():
                try:
                    ok = await fn(url)
                except Exception as e:  # noqa
                    self.log(f"点歌：{mname} 出错", repr(e))
                    ok = False
                if ok and await self._verify(song, before, mname):
                    return True
                if not ok:
                    self.log(f"点歌：{mname} 没发出去，试下一种方式")
            self.log(f"点歌：《{song.title}》启动后没有在 {self.verify_timeout:g}s 内变成正在播放（无版权/需要会员/客户端没响应），跳过")
            return False
        finally:
            self._busy = False

    async def _verify(self, song, before, mname):
        """用「正在播放」核对：歌名对得上，并且是新的一首（或进度在开头）。"""
        t0 = time.time()
        nt = norm(song.title)
        while time.time() - t0 < self.verify_timeout:
            await asyncio.sleep(0.5)
            n = self._now()
            if not n:
                continue
            st, pos = n
            tt = norm(st.get("title"))
            if tt and (tt == nt or tt in nt or nt in tt) and (st.get("key") != before or pos < 8):
                self.current, self.started = song, time.time()
                self._last_key = st.get("key")
                self.history.append(song.ui())
                self.log(f"点歌：开始播放 {song.artist} - {song.title}（{mname}，核对通过，{time.time() - t0:.1f}s）")
                return True
        return False

    async def _advance(self):
        """从队列取下一首并播放；播不了就继续下一首。"""
        while self.queue:
            song = self.queue.popleft()
            self.current = None
            self._push()
            if await self.play(song):
                self._push()
                return
            self.say(f"《{song.title}》播放失败（可能没版权或需要会员），已跳过 @{song.user}", None)
        self.current = None
        self._push()

    async def _loop(self):
        while True:
            await asyncio.sleep(0.5)
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa
                self.log("点歌：调度出错", repr(e))

    async def _tick(self):
        if self._busy:
            return
        n = self._now()
        st, pos = n if n else ({}, 0)
        key = st.get("key") if n else None
        ending = bool(n and st.get("playing") and st.get("duration") and st["duration"] - pos <= self.near_end)
        if n:
            self._off_since = None
        elif self._off_since is None:
            self._off_since = time.time()
        if self.current:
            same = n and norm(st.get("title")) and (norm(st["title"]) in norm(self.current.title) or norm(self.current.title) in norm(st["title"]))
            # 当前点歌放完了 = 正在播的是别的歌；「正在播放」信息偶尔会短暂丢失，所以丢失要超过 10 秒才算放完
            gone = (n and not same) or (not n and time.time() - self._off_since > 10)
            if gone and time.time() - self.started > 5:
                self.log(f"点歌：《{self.current.title}》播放结束")
                self.current = None
                self._push()
            elif self.queue and ending:
                await self._advance()
                return
        if not self.current and self.queue:
            go = self.first_immediate or not n or ending or (key != self._last_key and self._last_key is not None)
            if go:
                await self._advance()
        if n:
            self._last_key = key

    # ---------- 管理（测试/切歌） ----------
    async def skip(self):
        if self.queue:
            await self._advance()
            return True
        await self.control.next()
        self.current = None
        self._push()
        return False

    def clear(self):
        self.queue.clear()
        self._push()
