# -*- coding: utf-8 -*-
"""玩法提示（[tips]）：观众不知道能发什么弹幕。房间安静时，往 QQ 群聊里发一条「玩法提示」（系统消息样式），
有时猪猪侠真的演示一遍（走冷场玩电脑 / agent 动作管线，光标会动），再说一句「刚才这个你们也能玩，发『xxx』试试」；
另外每隔几分钟（不管安不安静）发一条「玩法菜单」。

只提示**真的能用**的命令：每条提示的命令都由测试 tools/test_tips.py 对规则解析器验证过；运行时还会按当前开关 / 桌面状态再校验一次
（点歌没开、互动关了、窗口不存在……的就先跳过）。一轮里每条只出现一次，用完了才开始下一轮（轮次状态存在 data/tips_state.json，重启不会从头重复）。"""
import asyncio
import hashlib
import json
import random
import re
import time
from pathlib import Path

from . import rules

ROOT = Path(__file__).resolve().parent.parent.parent

# id, 命令, 提示正文（不含前缀）, 处理方：rule / jukebox / memory, 演示：("idle", 活动名) | ("fx", kind) | None
TIPS = [
    ("song", "点歌 晴天", "想听歌？发弹幕『点歌 晴天』（歌名随便换），猪猪侠就给你放", "jukebox", None),
    ("next", "下一首", "这首不喜欢？发弹幕『下一首』，猪猪侠帮你切歌", "rule", None),
    ("ra2", "打开红警", "发弹幕『打开红警』，猪猪侠就会帮你打开", "rule", None),
    ("ra2away", "红警挡住了", "窗口挡视线了？发弹幕『红警挡住了』，猪猪侠帮你挪开", "rule", None),
    ("mine", "玩扫雷", "发弹幕『玩扫雷』，猪猪侠现场演示怎么扫雷", "rule", ("idle", "play_minesweeper")),
    ("sol", "玩纸牌", "发弹幕『玩纸牌』，看猪猪侠玩纸牌", "rule", ("idle", "play_solitaire")),
    ("wall", "换壁纸", "桌面看腻了？发弹幕『换壁纸』，猪猪侠给你换一张", "rule", ("idle", "change_wallpaper")),
    ("bsod", "来个蓝屏", "想看彩蛋？发弹幕『来个蓝屏』（只是演戏，电脑没事）", "rule", None),
    ("paint", "画个太阳", "发弹幕『画个太阳』，猪猪侠在画图里给你画（太阳换成别的也行）", "rule", ("idle", "paint_draw")),
    ("note", "在记事本里写：你好呀", "发弹幕『在记事本里写：你好呀』，猪猪侠会打开记事本，一个字一个字敲出来", "rule", ("idle", "notepad_write")),
    ("calc", "算一下 12*34", "发弹幕『算一下 12*34』，猪猪侠用计算器帮你算", "rule", ("idle", "calc")),
    ("pet", "喂食", "发弹幕『喂食』，给 QQ 宠物喂吃的", "rule", ("idle", "qq_pet_care")),
    ("outfit", "换成圣诞套装", "发弹幕『换成圣诞套装』，猪猪侠的 QQ 秀马上换新衣服", "rule", None),
    ("shake", "抖一下", "发弹幕『抖一下』，群聊窗口抖一抖", "rule", ("idle", "qq_shake")),
    ("fw", "放烟花", "发弹幕『放烟花』，屏幕上放烟花", "rule", ("fx", "fireworks")),
    ("meteor", "来个流星雨", "发弹幕『来个流星雨』，看流星雨", "rule", ("fx", "meteor")),
    ("virus", "熊猫烧香", "发弹幕『熊猫烧香』，来一段怀旧「中毒」整活（假的，电脑没事）", "rule", None),
    ("rank", "看排行榜", "发弹幕『看排行榜』，看看今天谁最活跃", "rule", ("idle", "play_rank")),
    ("idiom", "玩成语接龙", "发弹幕『玩成语接龙』，和猪猪侠接龙，答对有积分", "rule", None),
    ("songgame", "来局猜歌名", "发弹幕『来局猜歌名』，猜猪猪侠放的是哪首歌", "rule", None),
    ("riddle", "脑筋急转弯", "发弹幕『脑筋急转弯』，猪猪侠出题，大家抢答", "rule", None),
    ("screen", "点评一下屏幕", "发弹幕『点评一下屏幕』，猪猪侠看看屏幕，说两句", "rule", None),
    ("memory", "你还记得我吗", "想让猪猪侠记住你？发『记住我』，下次发『你还记得我吗』，它会说记得你什么", "memory", None),
]
BY_ID = {t[0]: t for t in TIPS}
# 玩法菜单里用的命令（短、常用）；第一项永远是点歌
MENU_POOL = ["点歌 晴天", "玩扫雷", "换壁纸", "画个太阳", "放烟花", "看排行榜", "下一首", "玩成语接龙", "算一下 12*34", "喂食", "抖一下", "打开红警", "玩纸牌", "来局猜歌名", "来个流星雨", "脑筋急转弯"]
POOL_CMD = {t[1]: t for t in TIPS}


def handler_of(cmd):
    """这条命令会被谁处理：'jukebox' / 'memory' / 'rule'（规则解析器出动作）/ None（没人理——这条提示不能发）。不依赖运行状态"""
    try:
        import jukebox
        if jukebox.CMD.match(cmd):
            return "jukebox"
    except Exception:
        pass
    try:
        from ai6 import plus
        if plus.ASKMEM_RE.match(cmd):
            return "memory"
    except Exception:
        pass
    it = rules.parse(cmd, None)
    if it is not None and not it.skip and it.actions:
        return "rule"
    return None


def split_list(s, sep=r"[|｜\n]"):
    return [x.strip() for x in re.split(sep, s or "") if x.strip()]


class Tips:
    def __init__(self, cfg, app, agent, idle, log=print):
        self.cfg, self.app, self.agent, self.idle, self.log = cfg, app, agent, idle, log
        self.t0 = time.time()
        self.next_tip = self.t0 + max(0.0, cfg.f("tips", "startup_delay"))
        self.next_menu = self.t0 + cfg.f("tips", "menu_interval")
        self.last_post = 0.0
        self.bag = []                 # 这一轮还没发过的提示 id
        self.menu_pos = 0
        self.busy = False             # 正在演示
        self.why = "启动中"
        self.stats = {"tips": 0, "demos": 0, "menus": 0, "performs": 0, "skipped": 0}
        self.last = None              # {at, kind, text}
        self.hist = []
        self.round = 0
        self.state_path = None
        self.task = None

    # ---------------------------------------------------------------- 开关 / 状态
    def on(self):
        return self.cfg.b("tips", "enabled")

    def start(self):
        sp = Path(self.cfg.s("tips", "state_file") or "data/tips_state.json")
        self.state_path = sp if sp.is_absolute() else ROOT / sp
        try:
            d = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.bag = [x for x in d.get("bag", []) if x in self.pool_ids()]
            self.round = int(d.get("round", 0))
            self.menu_pos = int(d.get("menu_pos", 0))
        except Exception:
            pass
        self.task = asyncio.ensure_future(self.loop())

    def _save(self):
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps({"bag": self.bag, "round": self.round, "menu_pos": self.menu_pos}), encoding="utf-8")
        except Exception:
            pass

    def customs(self):
        return {"c" + hashlib.md5(t.encode()).hexdigest()[:6]: t for t in split_list(self.cfg.s("tips", "custom"))}

    def pool_ids(self):
        ids = [t[0] for t in TIPS] if self.cfg.b("tips", "builtin") else []
        return ids + list(self.customs())

    def state(self):
        now = time.time()
        return {"enabled": self.on(), "why": self.why, "stats": dict(self.stats), "last": self.last, "round": self.round, "bag": len(self.bag), "pool": len(self.pool_ids()),
                "next_tip_in": max(0, int(self.next_tip - now)), "next_menu_in": max(0, int(self.next_menu - now)) if self.cfg.b("tips", "menu") else None,
                "history": self.hist[-8:], "busy": self.busy}

    # ---------------------------------------------------------------- 房间 / 条件
    def room(self):
        app = self.app
        return app.rooms.get(app.default_room) or next((r for rid, r in app.rooms.items() if rid != "demo"), None) or app.rooms.get("demo")

    def common_ok(self, now):
        """发任何一条（提示 / 菜单）都要满足的：有页面看着、没在演示 / 投票 / 小游戏、主播没在说话、离上一条够远"""
        if not self.on():
            return False, "已关闭"
        r = self.room()
        if r is None or not r.clients:
            return False, "没有页面连着"
        if self.busy:
            return False, "正在演示"
        if now - self.last_post < self.cfg.f("tips", "min_gap"):
            return False, "离上一条太近"
        pl = getattr(self.app, "play", None)
        if pl is not None and pl.vote_open():
            return False, "弹幕投票进行中"
        try:
            if self.app.plus.games.cur is not None and getattr(self.app.plus.games.cur, "state", "") != "done":
                return False, "小游戏进行中"
        except Exception:
            pass
        h = self.app.any_host()
        if h is not None and now < getattr(h, "busy_until", 0):
            return False, "主播正在说话"
        return True, ""

    def quiet(self, now):
        lv = getattr(self.idle, "last_viewer", 0) if self.idle is not None else 0
        return now - lv >= self.cfg.f("tips", "idle_secs")

    def available(self, tid):
        """这条提示现在还能用吗（开关 / 桌面状态）。自定义文本永远可用"""
        if tid in self.customs():
            return True
        t = BY_ID.get(tid)
        if t is None:
            return False
        _id, cmd, _txt, kind, _demo = t
        c = self.cfg
        if kind == "jukebox":
            jb = getattr(self.app, "jukebox", None)
            return bool(jb is not None and getattr(jb, "enabled", False))
        if kind == "memory":
            pl = getattr(self.app, "plus", None)
            return bool(pl is not None and getattr(pl, "mem", None) is not None and c.b("ai_plus", "enabled") and c.b("ai_plus", "memory") and c.b("ai_plus", "memory_cmd"))
        if not self.agent.on() or not self.agent.clients:
            return False
        desk = self.agent.desk()
        it = rules.parse(cmd, desk)
        if it is None or it.skip or not it.actions:
            return False
        good, errs, _say = self.agent.validate(it.actions, desk, "观众", it, viewer=True)
        return len(good) == len(it.actions) and not errs

    # ---------------------------------------------------------------- 选提示（一轮不重复）
    def next_id(self, only=None, need_demo=False):
        if only:                                            # 指定了某一条（面板 / 测试）：不看这一轮用没用过，只看现在能不能用
            if only in BY_ID and (not need_demo or BY_ID[only][4] is not None) and self.available(only):
                return only
            return None
        pool = set(self.pool_ids())
        if not pool:
            return None
        self.bag = [x for x in self.bag if x in pool]
        for attempt in range(2):
            if not self.bag:
                self.bag = list(pool)
                random.shuffle(self.bag)
                if self.last and self.last.get("id") in self.bag and len(self.bag) > 1 and self.bag[0] == self.last["id"]:
                    self.bag.append(self.bag.pop(0))
                self.round += 1
            for tid in list(self.bag):
                if only and tid != only:
                    continue
                if need_demo and not (tid in BY_ID and BY_ID[tid][4] is not None):
                    continue
                if self.available(tid):
                    return tid
            if only:
                return None
            self.bag = []                                   # 剩下的现在都不能用：这一轮算用完，下一轮重新来
        return None

    def mark(self, tid):
        if tid in self.bag:
            self.bag.remove(tid)
        self._save()

    # ---------------------------------------------------------------- 发
    def post(self, text, kind, tid=None, spoken=None, emo="开心"):
        """发一条群聊系统消息；spoken 不为空且 use_tts 时让猪猪侠也说一句"""
        r = self.room()
        if r is None:
            return False
        now = time.time()
        r._broadcast({"t": "sys", "text": text, "tip": kind, "ts": int(now * 1000)})
        self.last_post = now
        self.last = {"at": now, "kind": kind, "id": tid, "text": text}
        self.hist.append({"at": now, "kind": kind, "text": text})
        self.hist = self.hist[-30:]
        self.stats[{"tip": "tips", "demo": "demos", "menu": "menus", "perform": "performs"}.get(kind, "tips")] += 1
        self.log(f"[tips] {kind}：{text}")
        ops = getattr(self.app, "ops", None)
        if ops is not None:
            ops.record("tip", kind=kind, text=text[:80])
        if spoken and self.cfg.b("tips", "use_tts"):
            h = self.app.any_host()
            if h is not None and not (h.bl_in(spoken) or h.bl_out(spoken)):
                h.last["idle"] = now                          # 推迟主播自己的「冷场暖场」，别俩一起说
                asyncio.get_running_loop().run_in_executor(None, lambda: h._say("tip", 30, spoken, emo))
        return True

    def tip_text(self, tid):
        pre = self.cfg.s("tips", "prefix") or "💡 玩法提示："
        c = self.customs().get(tid)
        if c is not None:
            return c if c.startswith(("💡", "📋")) else pre + c
        return pre + BY_ID[tid][2]

    def menu_text(self):
        items = split_list(self.cfg.s("tips", "menu_items"), r"[|｜,，\n]")
        if not items:
            ok = [c for c in MENU_POOL if self.available(POOL_CMD[c][0])]
            n = max(3, min(8, self.cfg.i("tips", "menu_size")))
            if len(ok) > n:
                first = [ok[0]] if ok[0] == MENU_POOL[0] else []
                rest = [c for c in ok if c not in first]
                k = self.menu_pos % len(rest)
                rot = rest[k:] + rest[:k]
                items = first + rot[: n - len(first)]
                self.menu_pos = (self.menu_pos + n - len(first)) % max(1, len(rest))
            else:
                items = ok
        if not items:
            return None
        return "📋 玩法菜单：直接发弹幕就行 → " + " / ".join(items)

    # ---------------------------------------------------------------- 演示
    async def demo(self, tid):
        """猪猪侠真的演示一遍这个命令，演完说「你们也能玩」。返回是否演示了"""
        t = BY_ID.get(tid)
        if t is None or t[4] is None or not self.cfg.b("tips", "demo"):
            return False
        kind, what = t[4]
        now = time.time()
        r = self.room()
        ok_demo = False
        self.busy = True
        try:
            if kind == "idle":
                idl = self.idle
                if idl is None or not idl.on() or not idl.allowed(what):
                    self.why = "演示不了：冷场玩电脑没开 / 这个活动被禁用"
                    return False
                ok, why = idl.ready(now)
                if not ok:
                    self.why = f"演示不了：{why}"
                    return False
                if idl.pick(self.agent.desk(), now, only=what) != what:
                    self.why = f"演示不了：{what} 现在条件不满足"
                    return False
                self.log(f"[tips] 演示：{what}（{t[1]}）")
                task = idl.begin(what, force=True)
                await asyncio.wait([task])
                rec = (list(idl.hist) or [{}])[-1]
                ok_demo = rec.get("name") == what and rec.get("result") == "完成"
            elif kind == "fx":
                desk = self.agent.desk()
                good, errs, _ = self.agent.validate([{"action": "play_fx", "kind": what}], desk, "猪猪侠", viewer=False)
                if not good:
                    return False
                lv = self.idle.last_viewer if self.idle is not None else None
                self.log(f"[tips] 演示：{t[1]}")
                await self.agent.execute(good, {"t": "chat", "uid": "tips", "name": "猪猪侠", "text": "(玩法演示)"}, r, "(玩法演示)", self.cfg.s("host", "name"))
                if self.idle is not None and lv is not None:
                    self.idle.last_viewer = lv                 # execute 会当成观众指令：别因此把「安静计时」清零
                await asyncio.sleep(7)
                ok_demo = True
            if ok_demo:
                cmd = t[1]
                short = cmd.split("：")[0] if cmd.startswith("在记事本") else cmd
                self.post(f"💡 刚才这个你们也能玩，发弹幕『{cmd}』试试", "demo", tid, spoken=f"刚才这个你们也能玩，发{short}试试", emo="得意")
            return ok_demo
        finally:
            self.busy = False

    # ---------------------------------------------------------------- 主循环
    async def loop(self):
        while True:
            await asyncio.sleep(1.0)
            try:
                await self.tick()
            except Exception as e:  # noqa
                self.log(f"[tips] tick 出错：{e!r}")

    async def tick(self):
        now = time.time()
        ok, why = self.common_ok(now)
        self.why = why or "就绪"
        if not ok:
            return
        c = self.cfg
        if c.b("tips", "menu") and now >= self.next_menu:
            txt = self.menu_text()
            self.next_menu = now + c.f("tips", "menu_interval") * random.uniform(0.9, 1.1)
            if txt:
                self.post(txt, "menu")
                return
        if now < self.next_tip:
            self.why = "间隔未到"
            return
        if not self.quiet(now):
            self.why = "观众刚说过话"
            return
        if self.idle is not None and self.idle.task and not self.idle.task.done():
            self.why = "猪猪侠正在玩电脑"
            return
        await self.send_next(now)

    async def send_next(self, now, kind=None, only=None):
        """发下一条（提示或演示）。返回发出的 {kind,text} 或 None"""
        c = self.cfg
        self.next_tip = now + c.f("tips", "interval") * random.uniform(0.85, 1.3)
        tid = self.next_id(only, need_demo=(kind == 'demo'))
        if tid is None:
            self.why = "没有可发的提示"
            self.stats["skipped"] += 1
            return None
        t = BY_ID.get(tid)
        want_demo = kind == "demo" or (kind is None and t is not None and t[4] is not None and c.b("tips", "demo") and random.random() < c.f("tips", "demo_chance"))
        if want_demo and t is not None and t[4] is not None:
            self.mark(tid)
            if await self.demo(tid):
                return self.last
            self.log(f"[tips] 演示 {t[1]} 没成功（条件不满足 / 被打断），改发文字提示" if kind != "demo" else f"[tips] 演示 {t[1]} 没成功")
            if kind == "demo":
                return None
        self.mark(tid)
        self.post(self.tip_text(tid), "tip", tid, spoken=None)
        return self.last

    def perform_now(self, which=None):
        """面板「来一场表演」/ 测试：马上开一场冷场表演（perform.py；不看安静计时 / 间隔 / 开关，其余条件照旧）。which = 表演 id（bsod restart virus fireworks meteor mine paint wall shake pet），不填 = 按权重随机挑一个现在能做的"""
        from . import perform as PF
        from .idle import Ctx, weights_of
        if which and which not in PF.PERFS:
            return {"ok": False, "error": f"没有这个表演：{which}（可选：{' '.join(PF.PERFS)}）"}
        idl = self.idle
        if idl is None or not idl.on():
            return {"ok": False, "error": "冷场玩电脑没开（[idle] enabled）"}
        if idl.task and not idl.task.done():
            return {"ok": False, "error": "猪猪侠正在忙别的"}
        ag = self.agent
        if not ag.clients:
            return {"ok": False, "error": "没有页面连着"}
        desk = ag.desk()
        if not desk.known or time.time() - (ag.clients.get(ag.snap_ws) or {}).get("at", 0) > 15:
            return {"ok": False, "error": "桌面快照太旧（页面刚连上，等几秒）"}
        pl = getattr(self.app, "play", None)
        if pl is not None and pl.vote_open():
            return {"ok": False, "error": "弹幕投票进行中"}
        w = weights_of(self.cfg)
        ids = [which] if which else sorted(PF.PERFS, key=lambda k: random.random() ** (1.0 / max(w.get(f"perf_{k}", 1.0), 1e-6)), reverse=True)    # 按权重随机排个序
        for k in ids:
            idl.perf_force = k
            ctx = Ctx(idl, desk, idl.song(desk))
            if PF.plan(ctx, k):
                name = f"perf_{k}"
                idl.perf_force = k
                self.log(f"[tips] 手动表演：{k}")
                idl.begin(name, force=True)
                return {"ok": True, "kind": "perform", "id": k, "text": f"开始表演：{PF.PERFS[k][4]}（开场白：{ctx.fmt.get('_intro')}）"}
        idl.perf_force = None
        return {"ok": False, "error": "现在没有能做的表演（开关 / 桌面状态不满足）" if not which else f"现在做不了 {which}（开关 / 桌面状态不满足）"}

    async def now(self, kind="tip", cmd=None):
        """面板按钮 / 测试接口：立刻发一条（不看安静计时和间隔，只要有页面；离上一条太近时拒绝以免连点刷屏）"""
        now = time.time()
        r = self.room()
        if r is None or not r.clients:
            return {"ok": False, "error": "没有页面连着（直播间页面没开）"}
        if self.busy:
            return {"ok": False, "error": "正在演示"}
        if kind == "perform":
            return self.perform_now(cmd)
        if now - self.last_post < 3:
            return {"ok": False, "error": "太快了，稍等几秒"}
        if kind == "menu":
            txt = self.menu_text()
            if not txt:
                return {"ok": False, "error": "没有可用的玩法"}
            self.post(txt, "menu")
            return {"ok": True, "text": txt}
        only = None
        if cmd:
            only = next((t[0] for t in TIPS if t[1] == cmd), None)
            if only is None:
                return {"ok": False, "error": "没有这条提示"}
        res = await self.send_next(now, kind=("demo" if kind == "demo" else "tip"), only=only)
        if res is None:
            return {"ok": False, "error": "没有可发的提示" if kind != "demo" else "现在演示不了（" + (self.why or "条件不满足") + "）"}
        return {"ok": True, "kind": res["kind"], "text": res["text"]}
