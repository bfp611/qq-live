# -*- coding: utf-8 -*-
"""进场接待（[welcome]）：观众进直播间时，主播在 QQ 群聊里欢迎一句，顺带推荐一个他还没用过的玩法口令。

- 新观众：「欢迎 xx 来到直播间～发『来个蓝屏』试试」；老观众：「xx 又来啦，第 3 次了～发『放烟花』试试」；
  老朋友（关注过，见 giftfx）：「xx 老朋友来啦～…」。第几次 = 来过的**不同日子数**（存在积分存档 data/play.json 的用户记录里：visits / visit_day）。
- 防刷屏：merge_secs（10）秒内进来的合并成一句「欢迎 A、B 等 3 位朋友～」；同一个人 user_gap（30 分钟）内最多欢迎一次；每分钟最多 max_per_min 句。
- 默认只发文字（群聊里主播的一句，不出声）；speak = quiet 时，只有「房间安静」（quiet_secs 秒没人发弹幕、主播没在说话）才用 TTS 念出来。
- 不打断冷场玩电脑：这里只**观察**进场事件，从不调用 idle.interrupt / note_command。
- 开着本模块时，主播自己的「欢迎新人」和 ai6 的「老观众欢迎」都会让位（事件上打 welcome_handled / ai6_greeted 标记）。
- 顺手记下每个人用过哪些口令（用户记录里的 cmds：口令 id → 次数），供「推荐没用过的」和 [story] 的观众记忆用。
"""
import asyncio
import random
import re
import time
from collections import deque

from host.engine import nick as _nick
from play import store as _S

from . import tips as _tips

# 口令 id → 弹幕里认它的关键词（只认短弹幕，免得闲聊里带个「扫雷」就算用过）
KW = {
    "song": r"点歌", "next": r"下一首|切歌", "ra2": r"红警", "ra2away": r"红警.*(挡|让开|挪)", "mine": r"扫雷", "sol": r"纸牌", "wall": r"壁纸",
    "bsod": r"蓝屏", "paint": r"画个|画一|画只|画朵", "note": r"记事本", "calc": r"算一下|计算", "pet": r"喂食|喂饭|喂球球", "outfit": r"套装|换成.*装",
    "shake": r"抖一下|抖一抖|抖抖", "fw": r"烟花", "meteor": r"流星", "virus": r"熊猫烧香", "rank": r"排行榜|排行", "idiom": r"成语接龙",
    "songgame": r"猜歌", "riddle": r"脑筋急转弯", "screen": r"点评.*屏幕", "memory": r"记住我|还记得我",
}
KWC = {k: re.compile(v) for k, v in KW.items()}
DEFAULT_CMDS = "song,bsod,fw,meteor,virus,shake,pet,wall,mine,paint,rank,sol,idiom,songgame,riddle"

TPL = {
    "tpl_new": "欢迎 {n} 来到直播间～|{n} 来啦，欢迎欢迎～|欢迎 {n}，坐好坐好～",
    "tpl_back": "{n} 又来啦，第 {k} 次了～|欢迎 {n} 回来，这是第 {k} 次见啦～",
    "tpl_friend": "{n} 老朋友来啦～|老朋友 {n} 回来啦，第 {k} 次了～",
    "tpl_group": "欢迎 {n} 等 {k} 位朋友～|{n} 等 {k} 位朋友进来啦，欢迎～",
    "tail": "发『{cmd}』试试",
}


def split(s):
    return [x.strip() for x in re.split(r"[|｜\n]", s or "") if x.strip()]


class Welcome:
    def __init__(self, cfg, app, log=print):
        self.cfg, self.app, self.log = cfg, app, log
        self.pending = []                 # [{rid, room, uid, name, nick, k, new, friend, ts}]
        self.first_at = 0.0
        self.last_w = {}                  # (rid, uid) → 上次欢迎时间
        self.lines = deque(maxlen=60)     # 最近发出的欢迎时间（限每分钟句数）
        self.last_chat = 0.0
        self.stats = {"enters": 0, "lines": 0, "spoken": 0, "merged": 0, "recs": 0, "skip_gap": 0, "skip_rate": 0, "skip_self": 0}
        self.last = None
        self.hist = []
        self.task = None

    def on(self):
        return self.cfg.b("welcome", "enabled")

    def start(self):
        self.task = asyncio.ensure_future(self.loop())

    async def loop(self):
        while True:
            await asyncio.sleep(0.5)
            try:
                self.tick(time.time())
            except Exception as e:  # noqa
                self.log(f"[welcome] tick 出错：{e!r}")

    def state(self):
        return {"enabled": self.on(), "stats": dict(self.stats), "pending": len(self.pending), "last": self.last, "history": self.hist[-6:]}

    # ---------------------------------------------------------------- 事件入口（只观察，不吃事件）
    def on_event(self, ev, room, now=None):
        t = ev.get("t")
        if t not in ("chat", "member") or not self.on():
            return
        now = now or time.time()
        rid = getattr(room, "rid", "0") if room is not None else "0"
        uid = str(ev.get("uid") or "")
        if t == "chat":
            self.last_chat = now
            if uid:
                self.note_cmd(rid, uid, ev.get("name") or "", ev.get("text") or "")
            return
        if not uid:
            uid = "n:" + str(ev.get("name") or "")
        ev["welcome_handled"] = True            # 告诉主播 / ai6：进场我来欢迎，你们别再各发一句
        ev["ai6_greeted"] = True
        name = ev.get("name") or ""
        self.stats["enters"] += 1
        if self.is_self(room, name):
            self.stats["skip_self"] += 1
            return
        u, new, k = self.visit(rid, uid, name, now)
        if now - self.last_w.get((rid, uid), -1e12) < self.cfg.f("welcome", "user_gap") or any(p["uid"] == uid and p["rid"] == rid for p in self.pending):
            self.stats["skip_gap"] += 1
            return
        if len(self.pending) >= max(2, self.cfg.i("welcome", "pending_max")):
            return
        self.pending.append({"rid": rid, "room": room, "uid": uid, "name": name, "nick": self.safe_nick(room, name), "k": k, "new": new, "friend": bool(u.get("friend")), "ts": now})
        if not self.first_at:
            self.first_at = now

    def is_self(self, room, name):
        n = (name or "").strip()
        if not n:
            return False
        if n == self.cfg.s("host", "name"):
            return True
        a = ((getattr(room, "last", {}) or {}).get("room") or {}).get("anchor") or ""
        return bool(a) and n == a.strip()

    def safe_nick(self, room, name):
        n = _nick(name)
        h = getattr(room, "host", None) or self.app.any_host()
        try:
            if h is not None and (h.bl_in(n) or h.bl_out(n)):
                return "这位朋友"
        except Exception:
            pass
        return n

    # ---------------------------------------------------------------- 观众记录（积分存档里的用户记录）
    def store(self, rid):
        pl = getattr(self.app, "play", None)
        return pl.st(rid) if pl is not None else None

    def visit(self, rid, uid, name, now):
        """记一次进场：不同日子才算新的一次。返回 (用户记录, 是不是第一次, 第几次)"""
        st = self.store(rid)
        if st is None:
            return {}, True, 1
        existed = uid in st.scope(rid)["users"]
        u = st.user(rid, uid, name)
        day = _S.today(now)
        if "visits" not in u:
            u["visits"] = 1 if existed else 0
            u["visit_day"] = _S.today(u.get("last") or now) if existed else ""
        if u.get("visit_day") != day:
            u["visits"] += 1
            u["visit_day"] = day
        st.dirty = True
        return u, u["visits"] <= 1, u["visits"]

    def note_cmd(self, rid, uid, name, text):
        text = (text or "").strip()
        if not text or len(text) > 24:
            return
        st = self.store(rid)
        if st is None:
            return
        for cid, rx in KWC.items():
            if rx.search(text):
                u = st.user(rid, uid, name)
                u.setdefault("cmds", {})
                u["cmds"][cid] = u["cmds"].get(cid, 0) + 1
                if len(u["cmds"]) > 24:
                    del u["cmds"][min(u["cmds"], key=u["cmds"].get)]
                st.dirty = True
                break

    def cmd_ids(self):
        return [x for x in re.split(r"[,，\s]+", self.cfg.s("welcome", "cmds") or DEFAULT_CMDS) if x in _tips.BY_ID]

    def pick_cmd(self, rid, uid):
        """给这个人挑一个他没用过、现在能用的口令（最近推荐过的先躲开）；挑不出来返回 None"""
        if not self.cfg.b("welcome", "recommend"):
            return None
        st = self.store(rid)
        u = st.scope(rid)["users"].get(uid, {}) if st is not None else {}
        used = set(u.get("cmds") or {})
        recent = list(u.get("rec") or [])
        tp = getattr(self.app, "tips", None)
        ids = [i for i in self.cmd_ids() if i not in used]
        fresh = [i for i in ids if i not in recent[-3:]] or ids
        random.shuffle(fresh)
        for cid in fresh:
            try:
                if tp is not None and not tp.available(cid):
                    continue
            except Exception:
                continue
            if st is not None and uid in st.scope(rid)["users"]:
                u2 = st.scope(rid)["users"][uid]
                u2["rec"] = (recent + [cid])[-6:]
                st.dirty = True
            return cid
        return None

    # ---------------------------------------------------------------- 合并 / 出句
    def tpl(self, key):
        return random.choice(split(self.cfg.s("welcome", key)) or split(TPL[key]))

    def compose(self, batch):
        """一批进场 → (文字, 推荐口令 id)"""
        rid = batch[0]["rid"]
        first = next((b for b in batch if b["new"]), batch[0])
        cid = self.pick_cmd(rid, first["uid"])
        mx = max(1, self.cfg.i("welcome", "max_names"))
        if len(batch) == 1:
            b = batch[0]
            key = "tpl_friend" if b["friend"] else ("tpl_new" if b["new"] else "tpl_back")
            head = self.tpl(key).format(n=b["nick"], k=b["k"])
        elif len(batch) <= mx:
            head = "欢迎 " + "、".join(b["nick"] for b in batch) + " 来到直播间～"
        else:
            head = self.tpl("tpl_group").format(n="、".join(b["nick"] for b in batch[:mx]), k=len(batch))
        text = head
        sy = getattr(self.app, "story", None)
        if sy is not None and len(batch) == 1 and not batch[0]["new"]:
            try:
                text += sy.recall(rid, batch[0]["uid"], batch[0]["nick"])           # 老观众：带一句记得的事（[story] recall）
            except Exception as e:  # noqa
                self.log(f"[welcome] 读剧情记忆出错：{e!r}")
        if cid:
            cmd = _tips.BY_ID[cid][1]
            text += (self.cfg.s("welcome", "tail") or TPL["tail"]).format(cmd=cmd)
        return text, cid

    def tick(self, now):
        if not self.pending or not self.first_at:
            return None
        if now - self.first_at < self.cfg.f("welcome", "merge_secs"):
            return None
        return self.flush(now)

    def flush(self, now=None):
        now = now or time.time()
        batch, self.pending, self.first_at = self.pending, [], 0.0
        if not batch or not self.on():
            return None
        rooms = {}
        for b in batch:
            rooms.setdefault(b["rid"], []).append(b)
        out = None
        for rid, items in rooms.items():
            room = items[0]["room"]
            if room is None or not getattr(room, "clients", True):
                continue
            while self.lines and now - self.lines[0] > 60:
                self.lines.popleft()
            if len(self.lines) >= max(1, self.cfg.i("welcome", "max_per_min")):
                self.stats["skip_rate"] += 1
                continue
            text, cid = self.compose(items)
            for b in items:
                self.last_w[(rid, b["uid"])] = now
            if len(self.last_w) > 4000:
                for k in sorted(self.last_w, key=self.last_w.get)[:1500]:
                    del self.last_w[k]
            spoken = self.say(room, text, items[0]["nick"], now)
            self.lines.append(now)
            self.stats["lines"] += 1
            self.stats["spoken"] += 1 if spoken else 0
            self.stats["merged"] += 1 if len(items) > 1 else 0
            self.stats["recs"] += 1 if cid else 0
            self.last = {"at": now, "text": text, "n": len(items), "cmd": cid, "spoken": spoken}
            self.hist.append(self.last)
            self.hist = self.hist[-20:]
            self.log(f"[welcome] {'念出来' if spoken else '文字'}：{text}")
            ops = getattr(self.app, "ops", None)
            if ops is not None:
                try:
                    ops.record("welcome", text=text[:80], n=len(items))
                except Exception:
                    pass
            out = self.last
        return out

    def quiet(self, now, host):
        if now - self.last_chat < self.cfg.f("welcome", "quiet_secs"):
            return False
        if host is not None and now < getattr(host, "busy_until", 0):
            return False
        tp = getattr(self.app, "tips", None)
        if tp is not None and getattr(tp, "busy", False):
            return False
        idl = getattr(self.app, "idle", None)
        if idl is not None and idl.task and not idl.task.done():
            return False
        return True

    def say(self, room, text, to, now):
        """发出去。返回是否用 TTS 念了。文字版 = 一条 say 事件（audio 为空，群聊里出现主播的一句），不占主播的「正在说话」计时"""
        mode = (self.cfg.s("welcome", "speak") or "quiet").lower()
        host = getattr(room, "host", None) or self.app.any_host()
        talk = host is not None and (mode == "always" or (mode == "quiet" and self.quiet(now, host)))
        if talk:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None:
                host.last["welcome"] = now
                host.last["idle"] = now
                loop.run_in_executor(None, lambda: host._say("welcome", 30, text, "挥手", to=to))
                return True
        room._broadcast({"t": "say", "id": f"wl{int(now * 1000)}", "kind": "welcome", "prio": 20, "text": text, "emotion": "挥手", "audio": "",
                         "dur": max(2.0, min(4.5, len(text) * 0.22)), "to": to, "name": self.cfg.s("host", "name"), "role": "", "hot": False, "gift": "", "blocked": False,
                         "ts": int(now * 1000), "browser_tts": False})
        return False
