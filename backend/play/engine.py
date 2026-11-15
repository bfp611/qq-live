# -*- coding: utf-8 -*-
"""观众互动（[play]）：积分 / QQ 等级 / 弹幕投票 / 切歌投票。全部在服务端，页面只负责画（play-core.js / play-ui.js / play-fx.js）。

事件入口：server.Room._broadcast → Play.on_event(ev, room)；返回 True = 这条弹幕被互动模块吃掉了（投票数字 / 切歌 / 查积分 / 发起投票），不再交给点歌 / agent / AI 主播。
推给页面的事件（t = "play"）：
  {"t":"play","k":"lv","uid","name","lv","pts"}           某人的等级（变了 / 第一次见到）
  {"t":"play","k":"snap","lv":{uid: lv}}                   页面刚连上时补发（积分榜前 300 名）
  {"t":"play","k":"vote","vote":{…}}                       投票的实时状态（开始 / 每票 / 结束）
  {"t":"play","k":"skip","skip":{…}}                       切歌投票进度
另外会往群里写 {"t":"sys","text":…} 的系统消息。"""
import asyncio
import math
import random
import re
import time

from . import store as S

NEG = re.compile(r"(别|不要|不许|不准|不能|不用|不必|千万别|不想|没让|休想|禁止|莫|勿)")
VOTE_REPLY = re.compile(r"^\s*(?:投|选|我选|我投|投给|选择|#)?\s*([1-9])\s*(?:号|票|个)?\s*[!！。.~～]*\s*$")
OPT_RE = re.compile(r"(?:^|\s)([1-9])[\s、.:：)）]+(\S.*?)(?=\s+[1-9][\s、.:：)）]|\s*$)")


def level_of(pts, base):
    base = max(1.0, float(base))
    return max(0, min(255, int(math.sqrt(max(0, pts) / base))))


def level_glyphs(lv):
    """QQ 等级：4 颗星 = 1 个月亮，4 个月亮 = 1 个太阳，4 个太阳 = 1 顶皇冠。"""
    return "👑" * (lv // 64) + "☀️" * ((lv % 64) // 16) + "🌙" * ((lv % 16) // 4) + "⭐" * (lv % 4)


def parse_options(text):
    """“下一步干啥: 1 玩红警 2 换壁纸 3 扫雷” → ("下一步干啥", ["玩红警", "换壁纸", "扫雷"])；没编号就按 | 、， 空格 分。"""
    t = (text or "").strip()
    m = list(OPT_RE.finditer(t))
    if len(m) >= 2:
        title = t[: m[0].start()].strip(" :：，,")
        return title, [x.group(2).strip(" ，,;；") for x in m]
    if "|" in t or "｜" in t:
        parts = [p.strip() for p in re.split(r"[|｜]", t) if p.strip()]
    else:
        parts = [p for p in re.split(r"[\s、，,;；]+", t) if p]
    title = ""
    if parts and re.search(r"[:：?？]$", parts[0]):
        title = parts.pop(0).rstrip(":：")
    return title, parts


class Vote:
    def __init__(self, vid, title, labels, secs, by, room):
        self.id, self.title, self.labels, self.secs, self.by, self.room = vid, title, labels, secs, by, room
        self.t0 = time.time()
        self.ballots = {}          # uid -> 选项号（1 开始）
        self.names = {}
        self.state = "open"
        self.winner = 0
        self.note = ""
        self.dirty = True

    def counts(self):
        c = [0] * len(self.labels)
        for n in self.ballots.values():
            if 1 <= n <= len(c):
                c[n - 1] += 1
        return c

    def snap(self):
        c = self.counts()
        left = max(0.0, self.t0 + self.secs - time.time()) if self.state == "open" else 0
        return {"id": self.id, "title": self.title, "opts": [{"n": i + 1, "label": l, "count": c[i]} for i, l in enumerate(self.labels)], "total": sum(c),
                "secs": self.secs, "left": round(left, 1), "state": self.state, "winner": self.winner, "by": self.by, "note": self.note}


class Play:
    def __init__(self, cfg, app, log=print):
        self.cfg, self.app, self.log = cfg, app, log
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent.parent
        f = cfg.s("play", "data_file")
        path = (root / f) if f and not Path(f).is_absolute() else (Path(f) if f else None)
        self.store = S.PlayStore(path, cfg.i("play", "keep_days"), log)
        self.mem = S.PlayStore(None, cfg.i("play", "keep_days"), log)       # 演示房间：只放内存
        self.seq = 0
        self.vote = None
        self.vote_hist = []
        self.skip = {"key": "", "voters": {}, "t0": 0, "cool_until": 0}
        self.spam = {}             # (scope, uid) -> {"text","t","n","times":[...]}
        self.test_song = None
        self.active = {}           # scope -> {uid: last_ts}
        self.announced = {}        # scope -> {uid: lv}
        self.pcount = {}           # (scope, uid) -> [最近一分钟的加分时间]
        self.loop = None
        self.stats = {"events": 0, "awarded": 0, "ignored_dup": 0, "ignored_cap": 0, "votes": 0, "ballots": 0, "skips": 0, "skip_votes": 0}

    # ------------------------------------------------------------ 基础
    def on(self):
        return self.cfg.b("play", "enabled")

    def st(self, scope):
        return self.mem if scope == "demo" else self.store

    def start(self, loop):
        self.loop = loop
        asyncio.ensure_future(self._ticker())

    async def _ticker(self):
        n = 0
        while True:
            await asyncio.sleep(0.4)
            try:
                await self.tick()
            except Exception as e:  # noqa
                self.log(f"[play] tick 出错：{e!r}")
            n += 1
            if n % 25 == 0:           # 每 10 秒落盘（有改动才写）+ 清过期日榜
                self.store.save()
                if n % 1500 == 0:
                    self.store.prune()

    def stop(self):
        self.store.save(force=True)

    def anchor_of(self, room):
        r = (getattr(room, "last", {}) or {}).get("room") or {}
        return (r.get("anchor") or "").strip()

    def is_starter(self, ev, room):
        who = self.cfg.s("play", "vote_who").lower()
        if who == "off":
            return False
        if who == "anyone":
            return True
        name = (ev.get("name") or "").strip()
        names = {x.strip() for x in re.split(r"[,，;；]+", self.cfg.s("play", "vote_starters")) if x.strip()}
        a = self.anchor_of(room)
        if a:
            names.add(a)
        names.add(self.cfg.s("host", "name"))
        return bool(name) and name in names

    def emit(self, room, ev):
        if room is not None:
            room._broadcast(ev)

    def sysline(self, room, text):
        import html
        text = html.unescape(re.sub(r"</?b>", "", text))
        self.emit(room, {"t": "sys", "text": text, "play": 1, "ts": int(time.time() * 1000)})

    def say(self, room, text, emotion="开心", kind="vote"):
        if not self.cfg.b("play", "ai_say"):
            return
        ag = getattr(self.app, "agent", None)
        if ag is not None:
            try:
                ag.say(room, text, emotion, kind)
            except Exception as e:  # noqa
                self.log(f"[play] 说话失败：{e!r}")

    # ------------------------------------------------------------ 事件入口
    def on_event(self, ev, room):
        if not self.on():
            return False
        t = ev.get("t")
        if t not in ("chat", "gift", "like", "follow", "member") or not ev.get("uid"):
            return False
        scope = getattr(room, "rid", "0") if room is not None else "0"
        self.stats["events"] += 1
        uid, name = str(ev["uid"]), ev.get("name") or "神秘人"
        now = time.time()
        self.active.setdefault(scope, {})[uid] = now
        if len(self.active[scope]) > 3000:
            for k in sorted(self.active[scope], key=self.active[scope].get)[:1000]:
                del self.active[scope][k]
        consumed = False
        try:
            if t == "chat":
                consumed = self._on_chat(ev, room, scope, uid, name, now)
            elif t == "gift":
                c = max(1, int(ev.get("count") or 1))
                v = max(0, float(ev.get("value") or 0))
                pts = min(self.cfg.i("play", "gift_max_pts"), int(round(c * (self.cfg.f("play", "gift_points") + v * self.cfg.f("play", "gift_value_pts")))))
                self._award(room, scope, uid, name, pts, "gifts", now)
            elif t == "like":
                n = max(1, int(ev.get("count") or 1))
                per = max(1, self.cfg.i("play", "like_per"))
                u = self.st(scope).user(scope, uid, name)
                u["like_acc"] = u.get("like_acc", 0) + n
                pts = u["like_acc"] // per
                u["like_acc"] %= per
                if pts:
                    self._award(room, scope, uid, name, pts * self.cfg.i("play", "like_points"), "likes", now, capped=True)
            elif t == "follow":
                u = self.st(scope).user(scope, uid, name)
                day = S.today(now)
                if u.get("follow_day") != day:
                    u["follow_day"] = day
                    self._award(room, scope, uid, name, self.cfg.i("play", "follow_points"), "follows", now)
            elif t == "member":
                ep = self.cfg.i("play", "enter_points")
                u = self.st(scope).user(scope, uid, name)
                day = S.today(now)
                if ep and u.get("enter_day") != day:
                    u["enter_day"] = day
                    self._award(room, scope, uid, name, ep, None, now)
                elif not ep:
                    self.st(scope).add(scope, uid, name, 0, None, now)
                    self._announce(room, scope, uid, name, False)
        except Exception as e:  # noqa
            self.log(f"[play] 处理事件出错：{e!r}")
        return consumed

    # ------------------------------------------------------------ 积分
    def _award(self, room, scope, uid, name, pts, kind, now, capped=False):
        """加分：先过每分钟上限 / 每日上限。capped=True 的（聊天、点赞）才受每日上限限制。"""
        if pts <= 0:
            self.st(scope).add(scope, uid, name, 0, kind, now)
            return 0
        key = (scope, uid)
        if kind in ("chats", "likes"):
            q = [x for x in self.pcount.get(key, []) if now - x < 60]
            cap = self.cfg.i("play", "max_per_min")
            if cap and len(q) >= cap:
                self.stats["ignored_cap"] += 1
                self.pcount[key] = q
                return 0
            q.append(now)
            self.pcount[key] = q
        dcap = self.cfg.i("play", "daily_cap")
        if dcap and kind in ("chats", "likes"):
            have = self.st(scope).scope(scope)["days"].get(S.today(now), {}).get(uid, 0)
            if have >= dcap:
                self.stats["ignored_cap"] += 1
                return 0
        st = self.st(scope)
        old = st.user(scope, uid, name)["pts"]
        st.add(scope, uid, name, pts, kind, now)
        self.stats["awarded"] += pts
        self._announce(room, scope, uid, name, old_pts=old)
        return pts

    def award_bonus(self, room, uid, name, pts, kind="bonus"):
        """给其它模块（小游戏等）用的加分入口：不占聊天的每分钟 / 每日上限。积分系统没开则返回 0。"""
        if not self.on() or pts <= 0 or not uid:
            return 0
        scope = getattr(room, "rid", "0")
        self.active.setdefault(scope, {})[str(uid)] = time.time()
        return self._award(room, scope, str(uid), name or "神秘人", int(pts), kind, time.time())

    def level_for(self, scope, uid):
        u = self.st(scope).scope(scope)["users"].get(uid)
        return self.lv(u["pts"]) if u else 0

    def lv(self, pts):
        return level_of(pts, self.cfg.f("play", "level_base"))

    def _announce(self, room, scope, uid, name, first=True, old_pts=None):
        """等级变了 / 页面还没见过这个人 → 推一条 lv；升级了写群消息。"""
        u = self.st(scope).user(scope, uid, name)
        lv = self.lv(u["pts"])
        ann = self.announced.setdefault(scope, {})
        last = ann.get(uid)
        if last == lv:
            return
        ann[uid] = lv
        if lv == 0 and last is None:
            return                       # 0 级本来就没有图标，不用推
        self.emit(room, {"t": "play", "k": "lv", "uid": uid, "name": u["name"], "lv": lv, "pts": u["pts"]})
        if last is not None and lv > last and old_pts is not None and self.cfg.b("play", "levelup_msg"):
            self.sysline(room, f"恭喜 <b>{_h(u['name'])}</b> 升级了！当前 Lv.{lv} {level_glyphs(lv)}（{u['pts']} 分）")

    def snapshot(self, scope):
        rows = self.st(scope).rank(scope, "total", 300)
        return {"t": "play", "k": "snap", "lv": {r["uid"]: self.lv(r["pts"]) for r in rows}}

    def rank(self, scope, by="total", n=20):
        rows = self.st(scope).rank(scope, by, n)
        for r in rows:
            r["lv"] = self.lv(r["total"])
            r["glyphs"] = level_glyphs(r["lv"])
        return rows

    # ------------------------------------------------------------ 聊天：反刷屏 + 命令
    def _on_chat(self, ev, room, scope, uid, name, now):
        text = (ev.get("text") or "").strip()
        norm = re.sub(r"\s+", "", text).lower()
        # 1) 命令（吃掉）
        if self.cfg.b("play", "points_cmd") and re.fullmatch(r"(?:我的|查|查询|看看我的)?(?:积分|等级|排名|积分查询|我的积分|我的等级|我的排名)(?:是多少|多少|几级)?[?？]?", norm):
            self.me_cmd(room, scope, uid, name)
            return True
        m = re.match(r"^(?:发起投票|开始投票|投票|开个投票)[:：\s]*(.+)$", text)
        if m and self.is_starter(ev, room):
            title, opts = parse_options(m.group(1))
            r = self.start_vote(room, title, opts, by=name)
            if not r.get("ok"):
                self.sysline(room, "【投票】" + _h(r.get("error", "发起失败")))
            return True
        if re.fullmatch(r"(?:取消投票|结束投票|投票结束|关闭投票)", norm) and self.is_starter(ev, room):
            self.end_vote(room, cancel=norm.startswith("取消"))
            return True
        # 2) 投票数字
        v = self.vote
        if v is not None and v.state == "open" and self.cfg.b("play", "vote"):
            mm = VOTE_REPLY.match(text)
            if mm and 1 <= int(mm.group(1)) <= len(v.labels):
                self.ballot(room, scope, v, uid, name, int(mm.group(1)), now)
                return True
        # 3) 切歌投票
        if self.cfg.b("play", "skip_vote") and self._is_skip(text):
            if self.skip_vote(ev, room, scope, uid, name, now):
                return True
        # 4) 积分（反刷屏）
        if not self.cfg.b("play", "points"):
            return False
        if len(norm) < self.cfg.i("play", "chat_min_len"):
            return False
        sp = self.spam.setdefault((scope, uid), {"recent": {}, "t": 0, "last_award": 0})
        dup = self.cfg.f("play", "dup_secs")
        sp["recent"] = {k: t for k, t in sp["recent"].items() if now - t < dup}
        sp["t"] = now
        if norm in sp["recent"]:                        # 最近 dup_secs 秒里发过同一句：刷屏，不算分
            sp["recent"][norm] = now
            self.stats["ignored_dup"] += 1
            return False
        sp["recent"][norm] = now
        if now - sp["last_award"] < self.cfg.f("play", "chat_gap"):
            self.stats["ignored_cap"] += 1
            return False
        if self._award(room, scope, uid, name, self.cfg.i("play", "chat_points"), "chats", now, capped=True):
            sp["last_award"] = now
        else:
            self.st(scope).add(scope, uid, name, 0, None, now)
        if len(self.spam) > 5000:
            for k in sorted(self.spam, key=lambda k: self.spam[k]["t"])[:2000]:
                del self.spam[k]
        return False

    def me_cmd(self, room, scope, uid, name):
        st = self.st(scope)
        u = st.user(scope, uid, name)
        lv = self.lv(u["pts"])
        nxt = self.cfg.f("play", "level_base") * (lv + 1) ** 2
        pos = st.position(scope, uid, "total")
        dpos = st.position(scope, uid, "day")
        day = st.scope(scope)["days"].get(S.today(), {}).get(uid, 0)
        self.sysline(room, f"【积分】<b>{_h(name)}</b>：{u['pts']} 分，Lv.{lv} {level_glyphs(lv)}，总榜第 {pos or '-'} 名，今日 {day} 分（日榜第 {dpos or '-'} 名），升到 Lv.{lv + 1} 还差 {max(0, int(math.ceil(nxt - u['pts'])))} 分")

    # ------------------------------------------------------------ 弹幕投票
    def start_vote(self, room, title, labels, secs=None, by="", scope=None):
        if not self.on() or not self.cfg.b("play", "vote"):
            return {"ok": False, "error": "投票没开启（[play] vote）"}
        if self.vote is not None and self.vote.state == "open":
            return {"ok": False, "error": "已经有一个投票在进行了"}
        labels = [re.sub(r"\s+", " ", str(x)).strip()[:20] for x in labels if str(x).strip()]
        mx = max(2, min(9, self.cfg.i("play", "vote_max_options")))
        if len(labels) < 2:
            return {"ok": False, "error": "至少要 2 个选项"}
        labels = labels[:mx]
        secs = int(secs or self.cfg.i("play", "vote_secs"))
        secs = max(5, min(600, secs))
        title = (title or "").strip(" :：")[:24] or "大家投个票"
        self.seq += 1
        v = Vote(self.seq, title, labels, secs, by, room)
        self.vote = v
        self.stats["votes"] += 1
        opts = "　".join(f"{i + 1} {l}" for i, l in enumerate(labels))
        self.sysline(room, f"【投票】<b>{_h(title)}</b>：{_h(opts)}　——在群里发数字投票，{secs} 秒后揭晓")
        self.emit(room, {"t": "play", "k": "vote", "vote": v.snap()})
        spoken = f"来投票啦！{title}。" + "，".join(f"{i + 1}号{l}" for i, l in enumerate(labels)) + f"。发数字投票，{secs}秒后揭晓！"
        self.say(room, spoken[:120], "兴奋")
        return {"ok": True, "vote": v.snap()}

    def ballot(self, room, scope, v, uid, name, n, now):
        if uid in v.ballots and (v.ballots[uid] == n or not self.cfg.b("play", "vote_change")):
            return
        first = uid not in v.ballots
        v.ballots[uid] = n
        v.names[uid] = name
        v.dirty = True
        self.stats["ballots"] += 1
        if first and self.cfg.i("play", "vote_points"):
            self._award(room, scope, uid, name, self.cfg.i("play", "vote_points"), None, now)

    def end_vote(self, room=None, cancel=False):
        v = self.vote
        if v is None or v.state != "open":
            return False
        v.state = "cancelled" if cancel else "closing"
        v.dirty = True
        if not cancel:
            asyncio.ensure_future(self._finish(v))
        else:
            self.emit(v.room, {"t": "play", "k": "vote", "vote": v.snap()})
            self.sysline(v.room, "【投票】已取消")
            self.vote_hist.append(v.snap())
        return True

    async def _finish(self, v):
        c = v.counts()
        total = sum(c)
        room = v.room
        if total < max(1, self.cfg.i("play", "vote_min_votes")):
            if self.cfg.s("play", "vote_nobody").lower() == "random":
                win = random.randint(1, len(c))
                v.note = "没人投票，主播自己抽了一个"
            else:
                v.state, v.winner, v.note = "done", 0, "没人投票，作废"
                self.vote_hist.append(v.snap())
                self.emit(room, {"t": "play", "k": "vote", "vote": v.snap()})
                self.sysline(room, "【投票】没人投票，这次作废")
                self.say(room, "没人投票啊，那算了吧。", "难过")
                return
        else:
            top = max(c)
            ties = [i + 1 for i, x in enumerate(c) if x == top]
            win = random.choice(ties) if (len(ties) > 1 and self.cfg.s("play", "vote_tie").lower() == "random") else ties[0]
            if len(ties) > 1:
                v.note = f"平票（{'/'.join(map(str, ties))}），" + ("抽签决定" if self.cfg.s("play", "vote_tie").lower() == "random" else "取靠前的")
        v.winner, v.state = win, "done"
        label = v.labels[win - 1]
        self.vote_hist.append(v.snap())
        self.emit(room, {"t": "play", "k": "vote", "vote": v.snap()})
        self.sysline(room, f"【投票结果】<b>{win} 号 {_h(label)}</b> 胜出（{c[win - 1]}/{total} 票）{('，' + _h(v.note)) if v.note else ''}")
        self.say(room, f"投票结果出来了，{win}号，{label}，胜出！{'好，我这就去办。' if self.cfg.b('play', 'vote_execute') else ''}", "开心")
        if self.cfg.b("play", "vote_execute"):
            await self._execute(label, room, win)

    async def _execute(self, text, room, win):
        ag = getattr(self.app, "agent", None)
        if ag is None or not ag.on():
            self.log(f"[play] 投票结果 {text!r}：agent 没开，不执行")
            return
        try:
            await asyncio.sleep(1.5)
            out = await ag.simulate(text, name="投票结果", uid="vote", dry=False, force=True, room=room)
            self.log(f"[play] 投票执行 {text!r} -> {out.get('actions') or out.get('via')}")
        except Exception as e:  # noqa
            self.log(f"[play] 投票执行失败：{e!r}")

    async def tick(self):
        v = self.vote
        if v is not None:
            if v.state == "open" and time.time() >= v.t0 + v.secs:
                v.state = "closing"
                asyncio.ensure_future(self._finish(v))
            if v.dirty and v.state == "open":
                v.dirty = False
                self.emit(v.room, {"t": "play", "k": "vote", "vote": v.snap()})
            if v.state in ("done", "cancelled") and time.time() > v.t0 + v.secs + 30:
                self.vote = None

    def agent_action(self, a, ev, room, user):
        """agent 的后端动作 vote_start / vote_end。"""
        if a["action"] == "vote_end":
            return self.end_vote(room, cancel=bool(a.get("cancel")))
        if not self.is_starter({"name": user}, room):
            self.log(f"[play] {user} 不能发起投票（[play] vote_who）")
            return False
        title, opts = parse_options(a.get("options") or "")
        t = a.get("title") or title
        r = self.start_vote(room, t, opts, a.get("secs"), by=user)
        if not r.get("ok"):
            self.log(f"[play] vote_start 失败：{r.get('error')}")
        return r.get("ok")

    # ------------------------------------------------------------ 给闲时引擎用的小接口
    def vote_open(self):
        return bool(self.vote is not None and self.vote.state == "open")

    def idle_scope(self):
        """活跃观众最多的房间 scope（闲时判断“有没有人在看”）。"""
        best, n = None, 0
        for sc in list(self.active):
            k = self.active_count(sc)
            if k > n:
                best, n = sc, k
        return best, n

    def idle_vote_ok(self):
        c = self.cfg
        if not (self.on() and c.b("play", "vote") and c.b("play", "vote_idle")) or self.vote_open():
            return False
        return self.idle_scope()[1] >= max(1, c.i("play", "vote_idle_min_viewers"))

    # ------------------------------------------------------------ 切歌投票
    def _is_skip(self, text):
        t = re.sub(r"\s+", "", text or "")
        if not t or len(t) > 12 or NEG.search(t):
            return False
        words = [w.strip() for w in re.split(r"[,，;；\s]+", self.cfg.s("play", "skip_words")) if w.strip()]
        return any(w in t for w in words)

    def active_count(self, scope):
        win = self.cfg.f("play", "skip_active_secs")
        now = time.time()
        return sum(1 for ts in self.active.get(scope, {}).values() if now - ts <= win)

    def skip_need(self, scope):
        c = max(1, self.cfg.i("play", "skip_count"))
        if self.cfg.s("play", "skip_mode").lower() == "percent":
            pct = self.cfg.f("play", "skip_percent")
            c = max(self.cfg.i("play", "skip_min"), int(math.ceil(self.active_count(scope) * pct / 100.0)))
        return max(1, c)

    def _song_state(self):
        if self.test_song is not None:                 # 测试钩子：/play/testsong（仅本机 + test_endpoints）
            return self.test_song
        m = getattr(self.app, "music", None)
        return getattr(m, "state", None) or {}

    def _song_key(self):
        st = self._song_state()
        if not st.get("on"):
            return ""
        return str(st.get("key") or (st.get("title", "") + "|" + st.get("artist", "")))

    def skip_snap(self, scope, done=False, by=""):
        s = self.skip
        st = self._song_state()
        left = max(0.0, s["t0"] + self.cfg.f("play", "skip_window") - time.time()) if s["voters"] else 0
        return {"have": len(s["voters"]), "need": self.skip_need(scope), "song": st.get("title", ""), "left": round(left, 1), "done": done, "by": by, "active": self.active_count(scope)}

    def skip_vote(self, ev, room, scope, uid, name, now):
        """返回 True = 这句“切歌”被投票吃掉了。没有在放歌就放行（走原来的 agent 规则）。"""
        key = self._song_key()
        if not key:
            return False
        s = self.skip
        if s["key"] != key:                      # 换歌了：票清零
            s.update(key=key, voters={}, t0=0)
        if now < s["cool_until"]:
            return True
        win = self.cfg.f("play", "skip_window")
        s["voters"] = {u: t for u, t in s["voters"].items() if now - t <= win}
        if not s["voters"]:
            s["t0"] = now
        instant = self.cfg.b("play", "skip_anchor_instant") and self.is_starter(ev, room)
        if uid in s["voters"] and not instant:
            return True
        s["voters"][uid] = now
        self.stats["skip_votes"] += 1
        need = self.skip_need(scope)
        have = len(s["voters"])
        if instant or have >= need:
            snap = self.skip_snap(scope, done=True, by=name)
            snap["have"] = have if not instant else need
            snap["need"] = need
            s["voters"] = {}
            s["cool_until"] = now + self.cfg.f("play", "skip_cooldown")
            self.stats["skips"] += 1
            self.emit(room, {"t": "play", "k": "skip", "skip": snap})
            self.sysline(room, f"【切歌投票】{'主播发话' if instant else f'{have}/{need} 票'}，切歌！")
            self.say(room, "好，大家都说不好听，切歌！" if not instant else "好，切歌。", "开心", "skip")
            asyncio.ensure_future(self._do_skip(room))
        else:
            self.emit(room, {"t": "play", "k": "skip", "skip": self.skip_snap(scope, by=name)})
            self.sysline(room, f"【切歌投票】<b>{_h(name)}</b> 想切歌（{have}/{need}）")
        return True

    async def _do_skip(self, room):
        ag = getattr(self.app, "agent", None)
        try:
            if ag is not None and ag.on():
                await ag.simulate("切歌", name="切歌投票", uid="skipvote", dry=False, force=True, room=room)
                return
            jb = getattr(self.app, "jukebox", None)
            if jb is not None:
                await jb.skip()
        except Exception as e:  # noqa
            self.log(f"[play] 切歌失败：{e!r}")

    # ------------------------------------------------------------ 给页面 / 调试
    def page_cfg(self):
        c = self.cfg.cp["play"]
        return dict(c)

    def state(self, scope="0"):
        return {"enabled": self.on(), "vote": self.vote.snap() if self.vote else None, "skip": self.skip_snap(scope), "history": self.vote_hist[-5:], "stats": self.stats,
                "scopes": {k: len(v["users"]) for k, v in list(self.store.scopes.items()) + list(self.mem.scopes.items())}}


def _h(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
