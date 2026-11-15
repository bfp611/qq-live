# -*- coding: utf-8 -*-
"""观众记忆（老观众）：本地 JSON，原子写入。

隐私：
  - 不存原始 uid：key = sha1(本机随机盐 + uid)[:16]，文件里看不到抖音的 id；
  - 只存 昵称 / 首次·最近出现 / 来的次数 / 最近几句“话题”（过滤掉手机号、网址、微信、地址、证件之类的敏感内容，每句限长）/ 点过的歌 / 送过的礼物统计；
  - 条数、长度都有上限（max_viewers 最久没来的先丢，keep_days 天没来的丢）；
  - 观众说「忘记我」就删光并不再记录（直到说「记住我」），主播 / 本机可以用接口按昵称删，或者整库清空。
"""
import hashlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

SENSITIVE = re.compile(
    r"(\d{6,}|[\w.+-]+@[\w-]+\.[\w.]+|https?:|www\.|\.com|\.cn|微信|薇信|vx|wx|v信|加我|私信|扫码|手机|电话|号码|身份证|银行卡|密码|验证码|住址|地址|定位|家住|我住|真名|本名|实名|"
    r"qq号|扣扣|转账|红包|充值|兼职|刷单|贷款|赌|色情|裸|约炮|傻[逼B比]|[操草艹]你|妈的|死全家|滚)", re.I)
CTRL = re.compile(r"[\x00-\x1f\x7f<>]")


def clean_nick(n):
    return CTRL.sub("", str(n or "")).strip()[:20] or "神秘人"


def safe_topic(text, maxc=30):
    """能当“话题”记下来的一句话：太短 / 敏感 / 像命令的都不要。"""
    t = re.sub(r"\[[^\]]*\]", "", str(text or "")).strip()
    t = CTRL.sub("", t)
    if len(t) < 4 or SENSITIVE.search(t) or re.fullmatch(r"[\W\d_]+", t):
        return ""
    if len(set(t)) <= 2:
        return ""
    return t[:maxc]


def safe_song(title):
    t = re.sub(r"\s+", " ", CTRL.sub("", str(title or ""))).strip()[:30]
    return "" if SENSITIVE.search(t) else t


class MemoryStore:
    def __init__(self, path, max_viewers=2000, keep_days=90, topics=5, topic_chars=30, songs=5, log=print):
        self.path = Path(path) if path else None
        self.max_viewers, self.keep_days = max(50, int(max_viewers)), int(keep_days)
        self.topics_n, self.topic_chars, self.songs_n = max(0, int(topics)), max(8, int(topic_chars)), max(0, int(songs))
        self.log = log
        self.lock = threading.RLock()
        self.dirty = False
        self.salt = secrets.token_hex(8)
        self.v = {}               # key -> record
        self.optout = set()       # 要求“忘记我”的 key（不再记录）
        self._load()

    # ---- 存取 ----
    def _load(self):
        if not self.path or not self.path.exists():
            return
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.salt = d.get("salt") or self.salt
            self.v = d.get("viewers") or {}
            self.optout = set(d.get("optout") or [])
        except Exception as e:  # noqa
            bad = self.path.with_suffix(".json.bad")
            try:
                os.replace(self.path, bad)
            except OSError:
                pass
            self.log(f"[记忆] 存档读不了（{e!r}），已改名 {bad.name}，重新开始")

    def save(self, force=False):
        if not self.path or not (self.dirty or force):
            return False
        with self.lock:
            data = json.dumps({"v": 1, "salt": self.salt, "viewers": self.v, "optout": sorted(self.optout)}, ensure_ascii=False, separators=(",", ":"))
            self.dirty = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, self.path)
        return True

    def key(self, uid):
        return hashlib.sha1(f"{self.salt}:{uid}".encode("utf-8")).hexdigest()[:16]

    # ---- 记录 ----
    def touch(self, uid, name, now=None, session_gap=1800):
        """看到这个人了（任何事件）。返回 (rec, is_new_visit, before)；before = 这次之前的快照（第一次来 = None）；被要求忘记的人返回 (None, False, None)。"""
        if not uid:
            return None, False, None
        now = now or time.time()
        k = self.key(uid)
        with self.lock:
            if k in self.optout:
                return None, False, None
            r = self.v.get(k)
            before = None
            new_visit = False
            if r is None:
                r = {"nick": clean_nick(name), "first": int(now), "last": int(now), "visits": 1, "chats": 0, "topics": [], "songs": [], "gifts": {}, "gift_n": 0}
                self.v[k] = r
                new_visit = True
            else:
                before = json.loads(json.dumps(r))
                if now - r["last"] > session_gap:
                    r["visits"] += 1
                    new_visit = True
                r["last"] = int(now)
                if name:
                    r["nick"] = clean_nick(name)
            self.dirty = True
            if len(self.v) > self.max_viewers:
                self._prune(now, hard=True)
            return r, new_visit, before

    def chat(self, uid, text):
        k = self.key(uid)
        with self.lock:
            r = self.v.get(k)
            if not r:
                return
            r["chats"] += 1
            t = safe_topic(text, self.topic_chars)
            if t and self.topics_n:
                if t in r["topics"]:
                    r["topics"].remove(t)
                r["topics"].append(t)
                del r["topics"][:-self.topics_n]
            self.dirty = True

    def song(self, uid, title):
        k = self.key(uid)
        s = safe_song(title)
        with self.lock:
            r = self.v.get(k)
            if not r or not s or not self.songs_n:
                return
            if s in r["songs"]:
                r["songs"].remove(s)
            r["songs"].append(s)
            del r["songs"][:-self.songs_n]
            self.dirty = True

    def gift(self, uid, gift, n=1):
        k = self.key(uid)
        g = re.sub(r"\s+", "", CTRL.sub("", str(gift or "礼物")))[:12] or "礼物"
        with self.lock:
            r = self.v.get(k)
            if not r:
                return
            r["gifts"][g] = r["gifts"].get(g, 0) + int(n or 1)
            if len(r["gifts"]) > 8:                       # 最多记 8 种
                del r["gifts"][min(r["gifts"], key=r["gifts"].get)]
            r["gift_n"] += int(n or 1)
            self.dirty = True

    # ---- 查询 / 忘记 ----
    def get(self, uid):
        with self.lock:
            return self.v.get(self.key(uid))

    def find_name(self, name):
        n = clean_nick(name)
        with self.lock:
            return [(k, r) for k, r in self.v.items() if r["nick"] == n]

    def forget(self, uid=None, name=None, all_=False, optout=False):
        with self.lock:
            if all_:
                n = len(self.v)
                self.v.clear()
                self.dirty = True
                return n
            ks = []
            if uid is not None:
                ks = [self.key(uid)]
                if optout:
                    self.optout.add(ks[0])
            if name:
                ks += [k for k, _ in self.find_name(name)]
            n = 0
            for k in ks:
                if self.v.pop(k, None) is not None:
                    n += 1
            self.dirty = True
            return n

    def remember(self, uid):
        with self.lock:
            self.optout.discard(self.key(uid))
            self.dirty = True

    def _prune(self, now, hard=False):
        cut = now - self.keep_days * 86400
        for k in [k for k, r in self.v.items() if r["last"] < cut]:
            del self.v[k]
        if len(self.v) > self.max_viewers:
            for k in sorted(self.v, key=lambda k: self.v[k]["last"])[:len(self.v) - self.max_viewers + (self.max_viewers // 10 if hard else 0)]:
                del self.v[k]
        self.dirty = True

    def prune(self, now=None):
        with self.lock:
            self._prune(now or time.time())

    def stats(self):
        with self.lock:
            return {"viewers": len(self.v), "optout": len(self.optout), "max": self.max_viewers}


def ago(ts, now=None):
    d = max(0, (now or time.time()) - ts)
    if d < 3600:
        return "刚才" if d < 600 else f"{int(d // 60)}分钟前"
    if d < 86400:
        return f"{int(d // 3600)}小时前"
    return f"{int(d // 86400)}天前"


def facts(rec, level=0, glyphs="", now=None):
    """把记忆写成给 LLM / 模板用的几句话（只含上面允许记的东西）。"""
    if not rec:
        return ""
    L = [f"第{rec['visits']}次来" + (f"（上次是{ago(rec['last'], now)}）" if rec["visits"] > 1 else "")]
    if rec.get("songs"):
        L.append("点过《" + "》《".join(rec["songs"][-2:]) + "》")
    if rec.get("gifts"):
        top = sorted(rec["gifts"].items(), key=lambda x: -x[1])[:2]
        L.append("送过" + "、".join(f"{g}×{n}" for g, n in top))
    if rec.get("topics"):
        L.append("之前说过：" + " / ".join(rec["topics"][-2:]))
    if level:
        L.append(f"QQ等级 Lv.{level}{glyphs}")
    return "；".join(L)
