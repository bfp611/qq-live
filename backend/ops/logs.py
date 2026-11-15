# -*- coding: utf-8 -*-
"""按场结构化日志：每场直播一个 data/logs/session-<时间>.jsonl（一行一个事件，按大小轮转），外加 server.log（服务端日志，同样轮转）。
事件：chat gift like follow member(可选) stat live end song vote game skip agent idle host err。
一场的开始 = 收到 live=True，或（没收到开播信号时）第一条互动；结束 = 下播 / end 事件（宽限 end_grace 秒，期间又有互动就不算结束）或 session_gap 秒没有任何事件。
服务崩溃遗留的、没有结束标记的场次，下次启动时自动补上结束并生成复盘。"""
import json
import os
import re
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ERR_RE = re.compile(r"失败|出错|错误|异常|Traceback|Error|error|崩溃|超时|timeout", re.I)
CONTENT = ("chat", "gift", "like", "follow")


def now_s():
    return time.time()


class RotFile:
    """极简按大小轮转：path → path.1 → path.2 …（最多 keep 个旧文件）。线程安全由调用方的锁保证。"""
    def __init__(self, path, max_bytes, keep):
        self.path, self.max, self.keep = Path(path), max(10_000, int(max_bytes)), max(0, int(keep))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a", encoding="utf-8")
        self.size = self.path.stat().st_size

    def write(self, line):
        data = line if line.endswith("\n") else line + "\n"
        if self.size + len(data.encode("utf-8")) > self.max:
            self._rotate()
        self.fh.write(data)
        self.fh.flush()
        self.size += len(data.encode("utf-8"))

    def _rotate(self):
        self.fh.close()
        for i in range(self.keep, 0, -1):
            src = self.path if i == 1 else Path(f"{self.path}.{i - 1}")
            dst = Path(f"{self.path}.{i}")
            if src.exists():
                if i == self.keep and dst.exists():
                    dst.unlink()
                os.replace(src, dst)
        if self.keep == 0 and self.path.exists():
            self.path.unlink()
        self.fh = open(self.path, "a", encoding="utf-8")
        self.size = 0

    def close(self):
        try:
            self.fh.close()
        except Exception:
            pass


def session_files(logdir, sid):
    """一场的所有日志文件，按时间从旧到新（.N 最旧）"""
    base = Path(logdir) / f"session-{sid}.jsonl"
    olds = sorted(Path(logdir).glob(f"session-{sid}.jsonl.*"), key=lambda p: -int(p.suffix[1:]) if p.suffix[1:].isdigit() else 0)
    return [p for p in olds + [base] if p.exists()]


def read_events(logdir, sid):
    out = []
    for p in session_files(logdir, sid):
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def read_meta(logdir, sid):
    try:
        return json.loads((Path(logdir) / f"session-{sid}.meta.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def list_sessions(logdir):
    """[{sid, start, end, room, anchor, title, ...}]，新的在前"""
    out = []
    for p in Path(logdir).glob("session-*.meta.json"):
        sid = p.name[len("session-"):-len(".meta.json")]
        m = read_meta(logdir, sid)
        if m:
            m["sid"] = sid
            out.append(m)
    return sorted(out, key=lambda m: -m.get("start", 0))


class Recorder:
    def __init__(self, cfg, log=print, root=ROOT):
        self.cfg, self.log, self.root = cfg, log, root
        self.lock = threading.RLock()
        self.sess = None            # 当前这场：{sid, start, room, anchor, title, rf, n, last, end_pending}
        self.srv = None
        self.on_end = []            # 回调(meta)：场次结束
        self.recent = []            # 最近的 chat/gift/follow（给手机面板 / 统计），环形
        self.counts = {"chat": 0, "gift": 0, "like": 0, "follow": 0, "member": 0, "diamonds": 0}            # 当前场计数：chat gift like follow member diamonds
        self._vote_state = {}
        self._game_state = {}
        self._last_stat = 0.0
        self._last_song = None
        self._errs = 0
        self._streak = {}
        self.recent_n = 200

    # ---- 路径 ----
    def logdir(self):
        d = Path(self.cfg.s("ops", "log_dir") or "data/logs")
        d = d if d.is_absolute() else self.root / d
        d.mkdir(parents=True, exist_ok=True)
        return d

    def on(self):
        return self.cfg.b("ops", "enabled") and self.cfg.b("ops", "log")

    def _rot(self, path):
        return RotFile(path, self.cfg.f("ops", "log_max_mb") * 1024 * 1024, self.cfg.i("ops", "log_files"))

    # ---- 生命周期 ----
    def start(self):
        if not self.on():
            return
        try:
            self.srv = self._rot(self.logdir() / "server.log")
        except Exception as e:
            self.log("[ops] 打不开 server.log：", repr(e)[:100])
        self.cleanup()
        self.recover()

    def stop(self):
        with self.lock:
            if self.sess:
                self.end_session("服务停止")
            if self.srv:
                self.srv.close()
                self.srv = None

    def cleanup(self):
        days = self.cfg.i("ops", "log_keep_days")
        if days <= 0:
            return
        cut = time.time() - days * 86400
        try:
            for p in self.logdir().glob("session-*"):
                if p.stat().st_mtime < cut:
                    p.unlink()
        except Exception as e:
            self.log("[ops] 清理旧日志出错：", repr(e)[:100])

    def recover(self):
        """崩溃遗留的场次：补结束标记（结束时间 = 最后一条事件的时间），交给 on_end（生成复盘）"""
        try:
            for m in list_sessions(self.logdir()):
                if m.get("end"):
                    continue
                ev = read_events(self.logdir(), m["sid"])
                m["end"] = (ev[-1]["ts"] if ev else m.get("start", time.time()))
                m["reason"] = "异常退出后补记"
                self._write_meta(m)
                self.log(f"[ops] 补记上次没正常结束的一场：{m['sid']}")
                for cb in self.on_end:
                    cb(m)
        except Exception as e:
            self.log("[ops] 补记场次出错：", repr(e)[:100])

    # ---- 服务端日志 ----
    def server_line(self, line):
        """server.log()：每一行都进 server.log；像错误的行同时记成一条 err 事件"""
        if self.srv is None:
            return
        try:
            with self.lock:
                self.srv.write(line)
            if ERR_RE.search(line) and "[ops]" not in line[:30]:
                self.record("err", text=line[9:][:200])
        except Exception:
            pass

    # ---- 写事件 ----
    def _write_meta(self, m):
        try:
            (self.logdir() / f"session-{m['sid']}.meta.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            self.log("[ops] 写 meta 出错：", repr(e)[:100])

    def begin_session(self, room=None, anchor="", title="", ts=None):
        if not self.on():
            return None
        with self.lock:
            if self.sess:
                return self.sess
            ts = ts or now_s()
            sid = time.strftime("%Y%m%d-%H%M%S", time.localtime(ts))
            self.sess = {"sid": sid, "start": ts, "room": str(room or ""), "anchor": anchor, "title": title, "n": 0, "last": ts, "end_pending": 0}
            self.sess["rf"] = self._rot(self.logdir() / f"session-{sid}.jsonl")
            self.counts = {"chat": 0, "gift": 0, "like": 0, "follow": 0, "member": 0, "diamonds": 0}
            self.recent = []
            self._streak = {}
            self._vote_state, self._game_state, self._last_song = {}, {}, None
            self._write_meta({k: v for k, v in self.sess.items() if k not in ("rf", "n", "last", "end_pending")})
            self.log(f"[ops] 新的一场开始记录：{sid}（{self.logdir()}）")
            return self.sess

    def end_session(self, reason=""):
        with self.lock:
            s = self.sess
            if not s:
                return None
            last = s["last"]
            self._write(s, {"ts": now_s(), "k": "session_end", "reason": reason})
            end = last if reason == "空闲超时" else now_s()
            s["rf"].close()
            meta = {k: v for k, v in s.items() if k not in ("rf", "n", "last", "end_pending")}
            meta.update({"end": end, "reason": reason, "events": s["n"], "counts": dict(self.counts)})
            self.sess = None
            self._write_meta(meta)
            self.log(f"[ops] 这一场结束（{reason}）：{meta['sid']}，{s['n']} 条事件")
        for cb in self.on_end:
            try:
                cb(meta)
            except Exception as e:
                self.log("[ops] 场次结束回调出错：", repr(e)[:100])
        return meta

    def _write(self, s, rec):
        s["rf"].write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
        s["n"] += 1
        s["last"] = rec["ts"]

    def record(self, kind, /, **f):
        """写一条事件（没有进行中的一场就丢弃——日志是按场的）。返回是否写入"""
        if not self.on():
            return False
        with self.lock:
            s = self.sess
            if not s:
                return False
            rec = {"ts": round(now_s(), 3), "k": kind}
            rec.update(f)
            try:
                self._write(s, rec)
            except Exception as e:
                self._errs += 1
                if self._errs < 4:
                    self.log("[ops] 写日志出错：", repr(e)[:100])
                return False
        return True

    # ---- 接事件 ----
    def handle(self, ev, room=None):
        t = ev.get("t")
        if room is not None and getattr(room, "rid", "") == "demo":
            return                              # 演示房间的假数据不记
        mx = self.cfg.i("ops", "log_text_chars")
        now = now_s()
        if t == "live":
            if ev.get("live"):
                with self.lock:
                    if self.sess and self.sess.get("end_pending"):
                        self.sess["end_pending"] = 0          # 宽限期内又开播了：还是同一场
                    elif not self.sess:
                        self.begin_session(ev.get("room"), ev.get("anchor", ""), ev.get("title", ""))
                self.record("live", live=True, room=ev.get("room"), room_id=ev.get("room_id"), anchor=ev.get("anchor"), title=ev.get("title"))
            else:
                self.record("live", live=False)
                self._pend_end()
            return
        if t == "end":
            self.record("end")
            self._pend_end()
            return
        if t in CONTENT:
            with self.lock:
                if not self.sess:
                    self.begin_session(getattr(room, "rid", ""), ts=now)
                if self.sess:
                    self.sess["end_pending"] = 0
        if t == "chat":
            self.counts["chat"] += 1
            self._recent("chat", ev)
            self.record("chat", uid=ev.get("uid"), name=ev.get("name"), text=(ev.get("text") or "")[:mx])
        elif t == "gift":
            n = int(ev.get("count") or 1)
            v = int(ev.get("value") or 0)
            key = (ev.get("uid"), ev.get("gift"))
            prev = self._streak.get(key)
            credit = (n - prev[1]) if prev and now - prev[0] <= 8 and n >= prev[1] else n      # 连击：抖音每次发的是累计个数，只算新增的
            self._streak[key] = (now, n)
            if len(self._streak) > 2000:
                self._streak.clear()
            self.counts["gift"] += max(0, credit)
            self.counts["diamonds"] += max(0, credit) * v
            self._recent("gift", ev)
            self.record("gift", uid=ev.get("uid"), name=ev.get("name"), gift=ev.get("gift"), count=n, value=v)
        elif t == "like":
            self.counts["like"] += int(ev.get("count") or 1)
            self.record("like", uid=ev.get("uid"), name=ev.get("name"), count=int(ev.get("count") or 1))
        elif t == "follow":
            self.counts["follow"] += 1
            self._recent("follow", ev)
            self.record("follow", uid=ev.get("uid"), name=ev.get("name"))
        elif t == "member":
            self.counts["member"] += 1
            if self.cfg.b("ops", "log_members"):
                self.record("member", uid=ev.get("uid"), name=ev.get("name"))
        elif t == "stat":
            if now - self._last_stat >= 10:
                self._last_stat = now
                self.record("stat", online=ev.get("online"), total=ev.get("total"))
        elif t == "say":
            if ev.get("text") and ev.get("kind") != "idle_probe":
                self.record("host", kind=ev.get("kind"), text=(ev.get("text") or "")[:mx])
        elif t == "status":
            if ev.get("level") in ("error", "warn"):
                self.record("err", text=(ev.get("text") or "")[:200], level=ev.get("level"))
        elif t == "play":
            self._play(ev)

    def _recent(self, kind, ev):
        self.recent.append({"k": kind, "ts": round(now_s(), 1), "name": ev.get("name"), "text": (ev.get("text") or ev.get("gift") or "")[:80],
                            "count": ev.get("count"), "uid": ev.get("uid")})
        if len(self.recent) > self.recent_n:
            del self.recent[:len(self.recent) - self.recent_n]

    def _pend_end(self):
        with self.lock:
            if self.sess and not self.sess.get("end_pending"):
                self.sess["end_pending"] = now_s()

    def _play(self, ev):
        k = ev.get("k")
        if k == "vote":
            v = ev.get("vote") or {}
            vid, st = v.get("id"), v.get("state")
            if st and self._vote_state.get(vid) != st:
                self._vote_state[vid] = st
                if st == "open":
                    self.record("vote", id=vid, state="open", title=v.get("title"), opts=[o.get("label") for o in v.get("opts", [])], by=v.get("by"))
                else:
                    self.record("vote", id=vid, state=st, title=v.get("title"), total=v.get("total"), winner=v.get("winner"),
                                opts=[{"label": o.get("label"), "count": o.get("count")} for o in v.get("opts", [])], by=v.get("by"))
        elif k == "game":
            g = ev.get("game") or {}
            gid, st = g.get("id"), g.get("state")
            if g and (self._game_state.get(gid) != st) and st in ("open", "done"):
                first = gid not in self._game_state
                self._game_state[gid] = st
                if first or st == "done":
                    self.record("game", id=gid, kind=g.get("kind"), name=g.get("name"), state=("start" if first and st != "done" else st), by=g.get("by"),
                                winner=g.get("winner"), board=g.get("board") if st == "done" else None, rounds=g.get("rounds"))
        elif k == "skip":
            sk = ev.get("skip") or {}
            if sk.get("state") in ("done", "passed", "skipped") or sk.get("passed"):
                self.record("skip", skip=sk)

    def handle_music(self, ev, jukebox=None):
        """App.music_broadcast：正在播放的歌换了 → song 事件（点歌的人从点歌队列当前曲目里取）"""
        if ev.get("t") != "music" or not ev.get("on") or not ev.get("title"):
            return
        key = ev.get("key") or (ev.get("title"), ev.get("artist"))
        if key == self._last_song:
            return
        self._last_song = key
        by = ""
        try:
            cur = jukebox.current if jukebox else None
            if cur and cur.title and (cur.title in ev.get("title", "") or ev.get("title", "") in cur.title):
                by = cur.user or ""
        except Exception:
            pass
        self.record("song", title=ev.get("title"), artist=ev.get("artist"), by=by, duration=ev.get("duration"))

    def tick(self):
        """每几秒调一次：下播宽限到期 / 空闲超时 → 结束这一场"""
        s = self.sess
        if not s:
            return
        now = now_s()
        grace = self.cfg.f("ops", "end_grace")
        if s.get("end_pending") and now - s["end_pending"] >= grace:
            self.end_session("下播")
        elif now - s["last"] >= self.cfg.f("ops", "session_gap"):
            self.end_session("空闲超时")

    def snapshot(self):
        s = self.sess
        if not s:
            return {"active": False}
        return {"active": True, "sid": s["sid"], "start": s["start"], "room": s["room"], "events": s["n"], "counts": dict(self.counts),
                "ending": bool(s.get("end_pending"))}
