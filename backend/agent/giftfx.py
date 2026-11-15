# -*- coding: utf-8 -*-
"""礼物 / 点赞联动（[giftfx]）：按**钻石价值**（不是礼物名）分档，观众送礼 / 点赞 / 关注时直播画面里有对应的场面。

  1 钻起      小烟花 + 主播一句感谢（群聊 + TTS）
  10 钻起     一场随机「表演」（perform.py：蓝屏 / 烟花 / 流星雨 / 熊猫烧香 / 扫雷 / 画画 …）；送礼的人在 ask_secs（30）秒内发『烟花』『蓝屏』…就演他点的（这句弹幕被吃掉，不再走别的指令管线）
  100 钻起    大场面：假「重装系统」（XP 安装画面 → 开机 → 欢迎 → 桌面，只在页面里演）或 流星雨 + 全屏感谢卡片；并标记成**高光**（app.mark_highlight → 以后的切片模块）
  点赞        本场累计每 like_step（300）个赞：全屏点赞特效 + 主播念一句谢谢
  关注        主播点名感谢 + 记进「好友列表」（积分存档用户记录 friend=true；[welcome] 之后用亲切的说法欢迎他）

和冷场表演的关系：礼物触发的表演不看 [perform] 的开关 / 240 秒间隔（会打断正在玩的冷场活动），但蓝屏 / 重启 / 重装仍受 heavy_gap（10 分钟）约束；
做完不补「你们也可以发…」。连击合并：同一个人 merge_secs（3）秒内的礼物（含抖音连击的累计数）合成一次，按总钻石数定档；队列最多 queue_max 个，一次只放一个，满了丢掉最低档的。
开着本模块时：这条礼物 / 关注事件上会打 giftfx_handled / giftfx 标记 —— 主播自己的「感谢礼物 / 关注」和页面 qq-core 的礼物映射特效让位（不重复）。
钻石数为 0 / 没有的礼物不归这里管（照旧：主播自己感谢 + [qq] gift_map 映射）。"""
import asyncio
import random
import re
import time
from collections import deque

from host.engine import nick as _nick

from . import perform as PF

# 观众点表演的关键词（送礼后 ask_secs 秒内、只认送礼的那个人）
REQ_KW = {"bsod": r"蓝屏", "restart": r"重启", "virus": r"熊猫烧香|烧香", "fireworks": r"烟花", "meteor": r"流星", "mine": r"扫雷", "paint": r"画", "wall": r"壁纸", "shake": r"抖", "pet": r"喂|球球"}
REQ_RX = {k: re.compile(v) for k, v in REQ_KW.items()}
ASK_NAMES = {"fireworks": "烟花", "meteor": "流星雨", "bsod": "蓝屏", "virus": "熊猫烧香", "mine": "扫雷", "paint": "画画", "wall": "换壁纸", "shake": "抖一下", "pet": "喂食", "restart": "重启"}


class GiftFx:
    def __init__(self, cfg, app, log=print):
        self.cfg, self.app, self.log = cfg, app, log
        self.streak = {}                  # (rid, uid, gift) → (ts, n)
        self.bursts = {}                  # (rid, uid) → {room, name, gift, n, value, first, last}
        self.q = deque()
        self.hold = 1.0                   # 页面特效播放时长的缩放（测试里调小）
        self.busy = False
        self.ask = {}                     # uid → {deadline, req}
        self.follows = []                 # [{rid, room, uid, name, ts}]
        self.followed = {}                # (rid, uid) → ts
        self.last_follow_say = 0.0
        self.likes = 0
        self.next_like = 0
        self.stats = {"gifts": 0, "t1": 0, "t2": 0, "t3": 0, "likes": 0, "follows": 0, "requested": 0, "dropped": 0, "failed": 0}
        self.last = None
        self.hist = []
        self.tasks = []

    # ---------------------------------------------------------------- 基础
    def on(self):
        return self.cfg.b("giftfx", "enabled")

    def start(self):
        self.tasks = [asyncio.ensure_future(self._ticker()), asyncio.ensure_future(self._worker())]

    async def _ticker(self):
        while True:
            await asyncio.sleep(0.5)
            try:
                self.tick(time.time())
            except Exception as e:  # noqa
                self.log(f"[giftfx] tick 出错：{e!r}")

    async def _worker(self):
        while True:
            await asyncio.sleep(0.4)
            if not self.q or self.busy or not self.on():
                continue
            job = self.q.popleft()
            self.busy = True
            try:
                await self.run_job(job)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa
                self.stats["failed"] += 1
                self.log(f"[giftfx] {job.get('kind')} 出错：{e!r}")
            finally:
                self.busy = False
                await asyncio.sleep(max(0.0, self.cfg.f("giftfx", "gap_secs")))

    def state(self):
        return {"enabled": self.on(), "stats": dict(self.stats), "queue": len(self.q), "busy": self.busy, "likes": self.likes, "next_like": self.next_like,
                "friends": self.friend_count(), "last": self.last, "history": self.hist[-8:]}

    def tier_of(self, v):
        c = self.cfg
        if v >= c.i("giftfx", "tier3") and c.b("giftfx", "t3"):
            return 3
        if v >= c.i("giftfx", "tier2") and c.b("giftfx", "t2"):
            return 2
        if v >= max(1, c.i("giftfx", "tier1")) and c.b("giftfx", "t1"):
            return 1
        return 0

    # ---------------------------------------------------------------- 事件入口（返回 True = 这条弹幕被吃掉）
    def on_event(self, ev, room, now=None):
        if not self.on():
            return False
        t = ev.get("t")
        now = now or time.time()
        rid = getattr(room, "rid", "0") if room is not None else "0"
        uid = str(ev.get("uid") or ("n:" + str(ev.get("name") or "")))
        if t == "gift":
            self.on_gift(ev, room, rid, uid, now)
        elif t == "like":
            self.on_like(ev, room, int(ev.get("count") or 1))
        elif t == "follow":
            self.on_follow(ev, room, rid, uid, now)
        elif t == "chat":
            a = self.ask.get(uid)
            if a and now < a["deadline"] and a["req"] is None:
                k = self.match_req(ev.get("text") or "")
                if k:
                    a["req"] = k
                    self.stats["requested"] += 1
                    return True
        elif t in ("live", "end"):
            self.likes, self.next_like = 0, 0
        return False

    def match_req(self, text):
        text = (text or "").strip()
        if not text or len(text) > 30:
            return None
        for k, rx in REQ_RX.items():
            if rx.search(text):
                return k
        return None

    # ---- 礼物：连击合并 → 按总钻石数定档 ----
    def on_gift(self, ev, room, rid, uid, now):
        value = int(ev.get("value") or 0)
        if value < max(1, self.cfg.i("giftfx", "tier1")) or not (self.cfg.b("giftfx", "t1") or self.cfg.b("giftfx", "t2") or self.cfg.b("giftfx", "t3")):
            return                                           # 没有钻石数 / 低于最低档：不归这里管
        n = max(1, int(ev.get("count") or 1))
        gift = str(ev.get("gift") or "礼物")
        prev = self.streak.get((rid, uid, gift))
        if prev and now - prev[0] <= 2 and n == prev[1]:
            credit = 0                                       # 同一个累计数重复发：当重复包
        elif prev and now - prev[0] <= 8 and n > prev[1]:
            credit = n - prev[1]                             # 抖音连击：发的是累计个数，只算新增的
        else:
            credit = n
        self.streak[(rid, uid, gift)] = (now, n)
        if len(self.streak) > 2000:
            self.streak.clear()
        ev["giftfx"] = True                                  # 页面 qq-core 的礼物映射让位
        ev["giftfx_handled"] = True                          # 主播自己的感谢让位
        self.stats["gifts"] += 1
        if credit <= 0:
            return
        b = self.bursts.get((rid, uid))
        if b is None:
            b = self.bursts[(rid, uid)] = {"rid": rid, "room": room, "uid": uid, "name": ev.get("name") or "", "gift": gift, "n": 0, "value": 0, "first": now, "last": now}
        b["n"] += credit
        b["value"] += credit * value
        b["gift"], b["last"] = gift, now

    # ---- 点赞：本场累计，每 like_step 个触发一次 ----
    def on_like(self, ev, room, n):
        if not (self.cfg.b("giftfx", "likes") and self.on()):
            return
        step = max(10, self.cfg.i("giftfx", "like_step"))
        if not self.next_like:
            self.next_like = step
        self.likes += max(1, n)
        if self.likes >= self.next_like:
            total = self.likes
            self.next_like = (self.likes // step + 1) * step
            self.enqueue({"kind": "like", "tier": 1, "room": room, "rid": getattr(room, "rid", "0"), "name": "", "n": total, "value": 0, "gift": "", "uid": ""})

    # ---- 关注：好友列表 + 点名感谢 ----
    def on_follow(self, ev, room, rid, uid, now):
        if not self.cfg.b("giftfx", "follow"):
            return
        ev["giftfx_handled"] = True
        name = ev.get("name") or ""
        self.set_friend(rid, uid, name, now)
        if now - self.followed.get((rid, uid), -1e12) < 3600:
            return
        self.followed[(rid, uid)] = now
        if len(self.followed) > 3000:
            self.followed.clear()
        self.stats["follows"] += 1
        self.follows.append({"rid": rid, "room": room, "uid": uid, "name": name, "ts": now})

    def store(self, rid):
        pl = getattr(self.app, "play", None)
        return pl.st(rid) if pl is not None else None

    def set_friend(self, rid, uid, name, now=None):
        st = self.store(rid)
        if st is None:
            return
        u = st.user(rid, uid, name)
        if not u.get("friend"):
            u["friend"] = True
            u["friend_since"] = int(now or time.time())
            st.dirty = True

    def friend_count(self):
        n = 0
        try:
            for st in (self.app.play.store, self.app.play.mem):
                for s in st.scopes.values():
                    n += sum(1 for u in s["users"].values() if u.get("friend"))
        except Exception:
            pass
        return n

    # ---------------------------------------------------------------- 合并 → 队列
    def tick(self, now):
        if not self.on():
            return
        mg = self.cfg.f("giftfx", "merge_secs")
        for key, b in list(self.bursts.items()):
            if now - b["last"] >= mg or now - b["first"] >= 15:
                del self.bursts[key]
                tier = self.tier_of(b["value"])
                if tier:
                    self.enqueue({"kind": "gift", "tier": tier, "room": b["room"], "rid": b["rid"], "uid": b["uid"], "name": _nick(b["name"]), "gift": b["gift"][:12], "n": b["n"], "value": b["value"]})
        if self.follows and now - self.follows[0]["ts"] >= mg:
            fs, self.follows = self.follows, []
            self.enqueue({"kind": "follow", "tier": 0, "room": fs[0]["room"], "rid": fs[0]["rid"], "names": [_nick(f["name"]) for f in fs], "uid": fs[0]["uid"], "name": _nick(fs[0]["name"]), "n": len(fs), "value": 0, "gift": ""})

    def enqueue(self, job):
        mx = max(1, self.cfg.i("giftfx", "queue_max"))
        job.setdefault("at", time.time())
        if len(self.q) >= mx:
            low = min(self.q, key=lambda j: (j["tier"], -j["at"]))
            if job["tier"] <= low["tier"] and job["kind"] != "like":
                self.stats["dropped"] += 1
                self.log(f"[giftfx] 队列满了，丢掉 {job['kind']} 档{job['tier']}")
                return False
            self.q.remove(low)
            self.stats["dropped"] += 1
        self.q.append(job)
        return True

    def trigger(self, kind="gift", tier=1, name="测试观众", gift="玫瑰花"):
        """面板「来一场礼物联动」/ 测试：不经过事件管线（不加积分、不进日志），直接排一个任务"""
        room = self.room()
        if room is None:
            return {"ok": False, "error": "没有直播间 / 页面"}
        v = {1: max(1, self.cfg.i("giftfx", "tier1")), 2: self.cfg.i("giftfx", "tier2"), 3: self.cfg.i("giftfx", "tier3")}.get(int(tier), 1)
        if kind == "like":
            job = {"kind": "like", "tier": 1, "n": max(self.cfg.i("giftfx", "like_step"), 300), "name": "", "gift": "", "value": 0, "uid": ""}
        elif kind == "follow":
            job = {"kind": "follow", "tier": 0, "names": [_nick(name)], "name": _nick(name), "n": 1, "value": 0, "gift": "", "uid": ""}
        else:
            job = {"kind": "gift", "tier": int(tier), "name": _nick(name), "gift": gift, "n": 1, "value": v, "uid": "test:" + name}
        job.update(room=room, rid=getattr(room, "rid", "0"), test=True)
        ok = self.enqueue(job)
        return {"ok": ok, "queued": len(self.q), "job": {k: job[k] for k in ("kind", "tier", "name", "gift", "n", "value")}} if ok else {"ok": False, "error": "队列满了"}

    def room(self):
        app = self.app
        rooms = getattr(app, "rooms", {}) or {}
        return rooms.get(getattr(app, "default_room", None)) or next((r for rid, r in rooms.items() if rid != "demo"), None) or rooms.get("demo")

    # ---------------------------------------------------------------- 执行
    async def ready(self, room, maxwait=25.0):
        """等到页面能放（有页面 / 快照新 / 没投票 / 没在开关机蓝屏）；正在冷场玩电脑的先打断。超时 False"""
        t0 = time.time()
        ag = self.app.agent
        idl = self.app.idle
        while True:
            now = time.time()
            ok = bool(room is not None and ag.clients and ag.on())
            if ok:
                desk = ag.desk()
                cl = ag.clients.get(ag.snap_ws) or {}
                ok = bool(desk.known and now - (cl.get("at") or 0) <= 15 and not desk.s.get("xpbusy"))
            pl = getattr(self.app, "play", None)
            if ok and pl is not None and pl.vote_open():
                ok = False
            if ok and (ag.pending and any(now - t < 60 for t in ag.pending.values())) and not (idl is not None and idl.task and not idl.task.done()):
                ok = False
            if ok:
                if idl is not None and idl.task and not idl.task.done():
                    idl.interrupt("礼物联动")
                    for _ in range(25):
                        if idl.task.done():
                            break
                        await asyncio.sleep(0.2)
                return True
            if now - t0 > maxwait:
                return False
            await asyncio.sleep(0.5)

    def speak(self, room, kind, prompt, fallback, emo="开心", to=""):
        """主播说一句（LLM 失败回退 fallback；TTS 在线程里）。没有主播就只发一条文字 say"""
        host = (getattr(room, "host", None) if room is not None else None) or self.app.any_host()
        try:
            if host is not None and (host.bl_out(fallback) or host.bl_in(fallback)):
                return False
        except Exception:
            pass
        if host is None or not self.cfg.b("giftfx", "speak"):
            if room is not None:
                now = time.time()
                room._broadcast({"t": "say", "id": f"gf{int(now * 1000)}", "kind": kind, "prio": 40, "text": fallback, "emotion": emo, "audio": "", "dur": max(2.0, min(5.0, len(fallback) * 0.25)),
                                 "to": to, "name": self.cfg.s("host", "name"), "role": "", "hot": False, "gift": "", "blocked": False, "ts": int(now * 1000), "browser_tts": False})
            return False
        try:
            asyncio.get_running_loop().run_in_executor(None, lambda: host.speak(kind, prompt, fallback, emo, to=to, prio=62))
            return True
        except RuntimeError:
            return False

    async def exec_actions(self, room, actions, text):
        ag = self.app.agent
        good, errs, _ = ag.validate(actions, ag.desk(), self.cfg.s("host", "name"), viewer=False)
        if not good:
            self.log(f"[giftfx] 动作被校验拦下：{errs}")
            return False
        await ag.execute(good, {"t": "chat", "uid": "giftfx", "name": self.cfg.s("host", "name"), "text": "(礼物联动)"}, room, text, self.cfg.s("host", "name"))
        return True

    async def start_perf(self, k, prefix="", thanks=None):
        """走冷场表演的管线演 k（不看 [perform] 开关 / 间隔；蓝屏 / 重启 / 重装仍受 heavy_gap）。返回活动记录 / None"""
        idl = self.app.idle
        if idl is None or not idl.on():
            return None
        now = time.time()
        if k in PF.HEAVY and now - getattr(idl, "perf_heavy_at", 0) < self.cfg.f("perform", "heavy_gap"):
            return None
        from .idle import Ctx
        desk = self.app.agent.desk()
        try:
            idl.perf_force, idl.perf_prefix, idl.perf_thanks, idl.perf_quiet = k, prefix, thanks, True
            ctx = Ctx(idl, desk, idl.song(desk))
            if not PF.plan(ctx, k):
                return None
            task = idl.begin(f"perf_{k}", force=True)
            await asyncio.wait([task], timeout=self.cfg.f("idle", "max_duration") + 30)
            rec = (list(idl.hist) or [{}])[-1]
            return rec if rec.get("name") == f"perf_{k}" else None
        finally:
            idl.perf_force, idl.perf_prefix, idl.perf_thanks, idl.perf_quiet = None, "", None, False

    def pool(self):
        """随机表演的候选（按 [perform] 权重；不含重装；重型的冷却中就不挑）"""
        w = PF.weights(self.cfg)
        idl = self.app.idle
        now = time.time()
        ids = [k for k in PF.PERFS if k != "setup" and w.get(f"perf_{k}", 1.0) > 0]
        if idl is not None and now - getattr(idl, "perf_heavy_at", 0) < self.cfg.f("perform", "heavy_gap"):
            ids = [k for k in ids if k not in PF.HEAVY]
        ids.sort(key=lambda k: random.random() ** (1.0 / max(w.get(f"perf_{k}", 1.0), 1e-6)), reverse=True)
        return ids

    async def run_job(self, job):
        room = job.get("room") or self.room()
        t0 = time.time()
        kind, tier = job["kind"], job["tier"]
        who = job.get("name") or "朋友"
        res = ""
        if kind == "follow":
            names = job.get("names") or [who]
            txt = "谢谢 " + "、".join(names[:3]) + ("等 %d 位" % len(names) if len(names) > 3 else "") + " 的关注，以后就是老朋友啦～"
            self.speak(room, "follow", f"【关注】{'、'.join(names[:3])} 关注了你。用你的口吻点名感谢，说以后就是老朋友了，简短。", txt, "开心", to=names[0])
            res = "点名感谢"
        else:
            if not await self.ready(room):
                self.stats["failed"] += 1
                self.log(f"[giftfx] 页面一直没准备好，放弃 {kind} 档{tier}（{who}）")
                return
            if kind == "like":
                n = job["n"]
                self.stats["likes"] += 1
                self.speak(room, "gift", f"【点赞】直播间本场累计收到 {n} 个赞了。用你的口吻简短谢谢大家。", f"哇，已经 {n} 个赞啦，谢谢大家的点赞！", "兴奋")
                await self.exec_actions(room, [{"action": "gift_fx", "kind": "like", "n": n}], "点赞特效")
                await asyncio.sleep(5 * self.hold)
                res = f"点赞 {n}"
            elif tier == 1:
                self.stats["t1"] += 1
                g, n, v = job["gift"], job["n"], job["value"]
                self.speak(room, "gift", f"【礼物】{who} 送出了 {g}×{n}（{v}钻）。用你的口吻简短感谢，提到昵称和礼物。", f"谢谢{who}送的{g}" + (f"×{n}" if n > 1 else "") + "，爱你哟！", "开心", to=who)
                await self.exec_actions(room, [{"action": "gift_fx", "kind": "small_fireworks", "name": who}], "小烟花")
                await asyncio.sleep(3.5 * self.hold)
                res = "小烟花"
            elif tier == 2:
                res = await self.run_t2(job, room)
            else:
                res = await self.run_t3(job, room)
        self.last = {"at": time.time(), "kind": kind, "tier": tier, "who": who, "gift": job.get("gift"), "value": job.get("value"), "result": res, "ms": int((time.time() - t0) * 1000)}
        self.hist.append(self.last)
        self.hist = self.hist[-20:]
        self.log(f"[giftfx] 档{tier} {kind}：{who} {job.get('gift') or ''}×{job.get('n')}（{job.get('value')}钻）→ {res}")
        ops = getattr(self.app, "ops", None)
        if ops is not None:
            try:
                ops.record("giftfx", kind=kind, tier=tier, who=who, result=res[:40])
            except Exception:
                pass

    async def run_t2(self, job, room):
        self.stats["t2"] += 1
        who, g, uid = job["name"], job["gift"], job["uid"]
        secs = max(0.0, self.cfg.f("giftfx", "ask_secs"))
        a = {"deadline": time.time() + secs, "req": None}
        req = None
        if secs > 0:
            self.ask[uid] = a
            opts = "、".join(f"『{ASK_NAMES[k]}』" for k in self.pool()[:4] if k in ASK_NAMES)
            self.speak(room, "gift", f"【礼物】{who} 送出了 {g}（{job['value']}钻）。用你的口吻简短感谢，并说{int(secs)}秒内发{opts or '想看的表演'}之一你就现场表演，不点就随机来一个。", f"谢谢{who}送的{g}！{int(secs)}秒内发{opts}点一个，我现场表演，不点我就随机来一个～", "兴奋", to=who)
            try:
                while time.time() < a["deadline"] and a["req"] is None:
                    await asyncio.sleep(0.3)
            finally:
                self.ask.pop(uid, None)
            req = a["req"]
        else:
            self.speak(room, "gift", f"【礼物】{who} 送出了 {g}（{job['value']}钻）。用你的口吻简短感谢。", f"谢谢{who}送的{g}！给你来一场表演", "兴奋", to=who)
        order = self.pool()
        if req and req in order:
            order.remove(req)
            order.insert(0, req)
        elif req:
            self.speak(room, "gift", "", f"刚演过大场面，{PF.PERFS[req][4]} 先歇一会儿，换个别的给你～", "开心", to=who)
        for k in order:
            rec = await self.start_perf(k)
            if rec and rec.get("result") in ("完成", "被打断"):
                return f"表演 {k}" + ("（点的）" if k == req else "（随机）") + f"：{rec['result']}"
        await self.exec_actions(room, [{"action": "gift_fx", "kind": "small_fireworks", "name": who}], "小烟花")
        return "没有能演的表演，放了小烟花"

    async def run_t3(self, job, room):
        self.stats["t3"] += 1
        who, g, n, v = job["name"], job["gift"], job["n"], job["value"]
        mark = getattr(self.app, "mark_highlight", None)
        if mark is not None:
            try:
                mark("gift_big", who=who, gift=g, value=v)
            except Exception as e:  # noqa
                self.log(f"[giftfx] 标记高光出错：{e!r}")
        scene = (self.cfg.s("giftfx", "big_scene") or "random").lower()
        if scene == "random":
            scene = random.choice(["setup", "meteor"])
        th = {"name": who, "gift": g, "n": n, "value": v}
        if scene == "setup":
            rec = await self.start_perf("setup", prefix=f"谢谢{who}送的{g}！", thanks=th)
            if rec and rec.get("result") in ("完成", "被打断"):
                return f"重装系统：{rec['result']}"
        self.speak(room, "gift", f"【大礼】{who} 送出了 {g}×{n}（{v}钻）。用你的口吻激动地感谢，说给他放一场流星雨。", f"哇！谢谢{who}送的{g}！大礼！给你放一场流星雨～", "兴奋", to=who)
        await self.exec_actions(room, [{"action": "gift_fx", "kind": "big_thanks", "name": who, "gift": g, "n": n, "value": v, "secs": 8}], "流星雨 + 感谢")
        await asyncio.sleep(9 * self.hold)
        return "流星雨 + 全屏感谢" + ("（重装系统冷却中）" if scene == "setup" else "")
