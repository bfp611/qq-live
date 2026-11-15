# -*- coding: utf-8 -*-
"""手机控制面板的接口（/ops/api/*，要令牌）。令牌放 X-Token 请求头（页面用）或 ?token=（只给「打开复盘」这种链接）；
动作一律 POST（浏览器跨站请求带不了自定义头，天然防 CSRF）。写操作有短冷却，防手滑连点。"""
import asyncio
import json
import os
import re
import time

from aiohttp import web

from . import panel as P
from . import report as R
from .web import NAME_RE, jr

# 面板能改的开关：(key, 说明, 分组, 要刷新直播页面才生效)。不在表里的 key 一律拒绝；改动存 data/ops_overrides.json，不动 config.ini。
SWITCHES = [
    ("guard", "真人验证守护（只通知，不碰直播伴侣）", [
        ("guard.enabled", "守护总开关", False), ("guard.bark", "Bark 推送到手机", False), ("guard.sound", "Mac 提示音（走实体音箱）", False),
        ("guard.log_watch", "读直播伴侣日志", False), ("guard.drop_alert", "下播 / 断流提醒", False)]),
    ("tips", "玩法提示（安静时教观众怎么玩）", [
        ("tips.enabled", "玩法提示总开关", False), ("tips.demo", "有时真的演示一遍", False), ("tips.menu", "定时玩法菜单", False), ("tips.use_tts", "提示 / 演示时出声", False), ("perform.enabled", "冷场表演（先说一句再做：蓝屏 / 重启 / 烟花…）", False), ("perform.tip", "表演后补一句「你们也可以发…」", False), ("welcome.enabled", "进场接待（欢迎 + 推荐没用过的玩法）", False), ("giftfx.enabled", "礼物 / 点赞联动（按钻石档位放特效 / 表演 / 大场面）", False), ("giftfx.likes", "点赞满 300 放全屏特效", False)]),
    ("clips", "高光切片（录直播窗口，高光时刻剪成竖屏 MP4）", [
        ("clips.enabled", "高光切片（开播时录制 + 自动剪）", False), ("clips.viewer_cmd", "观众发「高光」也切一个", False), ("clips.bark", "切到高光时 Bark 推送到手机", False)]),
    ("story", "连续剧情（剧情日期 / 下播日记 / 观众记忆）", [
        ("story.enabled", "连续剧情总开关", False), ("story.advance", "每个开播日往后走一天", False), ("story.clock", "任务栏时钟显示剧情日期", False), ("story.zone", "QQ空间日期跟着剧情走", False),
        ("story.diary", "下播后写 QQ空间日记", False), ("story.llm", "日记用 LLM 写（关了用模板）", False), ("story.read_aloud", "冷场时翻出日记念", False),
        ("story.memory", "观众记忆（口令 / 几句话）", False), ("story.recall", "欢迎老观众时带一句记忆", False), ("story.reply_memory", "回弹幕时参考观众记忆", False)]),
    ("host", "AI 主播", [
        ("behavior.reply_chat", "回复弹幕", False), ("behavior.welcome_enters", "欢迎进场", False), ("behavior.thanks_gifts", "感谢礼物", False),
        ("behavior.thanks_follows", "感谢关注", False), ("behavior.proactive", "冷场主动说话", False)]),
    ("agent", "猪猪侠 / 桌面指令", [
        ("agent.enabled", "观众指令（agent）", False), ("agent.llm", "指令走 LLM", False), ("agent.reply", "执行后回话", False),
        ("idle.enabled", "冷场自己玩电脑（idle）", False), ("idle.speak", "玩的时候旁白", False)]),
    ("music", "音乐 / 点歌", [
        ("music.jukebox", "弹幕点歌", False), ("music.ack", "点歌后主播回应", False)]),
    ("play", "观众互动 / 特效", [
        ("play.enabled", "互动总开关", True), ("play.commands", "弹幕互动指令", False), ("play.points", "积分", False), ("play.vote", "投票", False),
        ("play.skip_vote", "切歌投票", False), ("play.fx", "礼物 / 互动特效", True)]),
    ("ai", "AI 加强包", [
        ("ai_plus.enabled", "加强包总开关", False), ("ai_plus.memory", "观众记忆", False), ("ai_plus.memory_greet", "点名欢迎老观众", False),
        ("ai_plus.game", "小游戏", False), ("ai_plus.game_idle", "冷场自动开游戏", False), ("ai_plus.song_comment", "歌曲点评", False), ("ai_plus.screen", "画面点评", False)]),
    ("xp", "XP 桌面 / QQ", [
        ("autoclose.enabled", "窗口闲置自动关闭", False), ("xp.sounds", "XP 系统音效", True), ("xp.qq_sounds", "QQ 提示音", True), ("xp.bsod", "蓝屏彩蛋", True), ("xp.balloons", "托盘气泡", True),
        ("qq.shake", "窗口抖动", False), ("qq.gift_effects", "礼物特效", True), ("qq.pet", "QQ 宠物", True)]),
]
SWITCH_KEYS = {k: (lab, reload_) for _, _, items in SWITCHES for k, lab, reload_ in items}
FX = ("fireworks", "meteor", "emoji", "virus")
COOLDOWN = {"story_diary": 8.0, "story_read": 10.0, "story_day": 2.0, "story_publish": 2.0, "clips_now": 6.0, "clips_check": 3.0, "giftfx_test": 8.0, "perform_now": 10.0, "tip_now": 3.0, "menu_now": 3.0, "demo_now": 10.0, "guard_test": 10.0, "bsod": 8.0, "fx": 2.0, "shake": 2.0, "say": 2.0, "restart": 5.0, "vote_start": 2.0, "game_start": 3.0}


class PanelApi:
    def __init__(self, ops):
        self.ops = ops
        self.cd = {}
        self.t0 = time.time()

    # ---------- 鉴权 ----------
    def auth(self, request):
        o = self.ops
        if not (o.on() and o.cfg.b("ops", "panel")):
            return web.json_response({"ok": False, "error": "手机面板没开（[ops] panel）"}, status=404)
        ip = request.remote or "local"
        if o.lock_out.blocked(ip):
            return web.json_response({"ok": False, "error": "错误次数太多，稍后再试"}, status=429)
        given = request.headers.get("X-Token") or request.query.get("token") or ""
        if not P.check_token(given, o.token()):
            o.lock_out.fail(ip)
            return web.json_response({"ok": False, "error": "令牌不对"}, status=401)
        o.lock_out.ok(ip)
        return None

    def cool(self, name):
        """True = 还在冷却里（只有成功执行过的动作才开始冷却，填错了重填不用等）"""
        s = COOLDOWN.get(name)
        return bool(s and time.time() - self.cd.get(name, 0) < s)

    # ---------- 状态 ----------
    def room(self):
        app = self.ops.app
        return app.rooms.get(app.default_room) or next((r for rid, r in app.rooms.items() if rid != "demo"), None)

    def switches(self):
        c = self.ops.cfg
        out = []
        for gid, title, items in SWITCHES:
            out.append({"id": gid, "title": title, "items": [{"key": k, "label": lab, "on": c.b(*k.split(".")), "reload": rl, "changed": k in self.ops.overrides} for k, lab, rl in items]})
        return out

    def state(self):
        o, app = self.ops, self.ops.app
        f = o.fetcher_of_default()
        r = self.room()
        last = (r.last if r else {}) or {}
        ri, st, lv = last.get("room") or {}, last.get("stat") or {}, last.get("live")
        now = time.time()
        snap = o.rec.snapshot()
        game = None
        try:
            if app.plus.games.cur is not None:
                game = app.plus.games.snapshot()
        except Exception:
            pass
        vote = app.play.vote.snap() if getattr(app.play, "vote", None) is not None else None
        idle = app.idle
        return {
            "now": now, "room": app.default_room, "uptime": int(now - self.t0), "supervised": bool(os.environ.get("QQ_SUPERVISED")),
            "live": (lv["live"] if lv else (f.live if f else None)), "fetcher": f.snapshot() if f else None,
            "anchor": ri.get("anchor") or (lv or {}).get("anchor") or (f.snapshot()["anchor"] if f else ""), "title": ri.get("title") or (lv or {}).get("title") or "",
            "online": st.get("online"), "total": st.get("total"),
            "session": dict(snap, dur=int(now - snap["start"])) if snap.get("active") else snap,
            "counts": dict(o.rec.counts) if snap.get("active") else {k: 0 for k in o.rec.counts},
            "pages": sum(len(x.clients) for x in app.rooms.values()), "agent_clients": len(app.agent.clients), "host": bool(app.any_host()),
            "switches": self.switches(), "overrides": len(o.overrides),
            "music": app.music.state if app.music else None,
            "jukebox": app.jukebox.snapshot() if app.jukebox else None,
            "vote": vote, "game": game,
            "idle": {"cur": (idle.cur or {}).get("name") if idle.cur else None, "stats": dict(idle.stats)},
            "report": {"last": o.last_report, "busy": o.report_busy, "count": len(R.list_reports(o.cfg))},
            "errors": o.rec._errs, "guard": o.guard.snapshot(), "tips": app.tips.state(), "welcome": app.welcome.state(), "giftfx": app.giftfx.state(), "clips": app.clips.state(), "story": app.story.state(),
        }

    # ---------- 动作 ----------
    async def run_agent(self, acts, name="手机面板"):
        app = self.ops.app
        good, errs, _say = app.agent.validate(acts, app.agent.desk(), name, viewer=False)
        if not good:
            return {"ok": False, "error": "；".join(errs) or "动作被拒绝"}
        r = self.room()
        await app.agent.execute(good, {"t": "chat", "uid": "panel", "name": name, "text": "(手机面板)"}, r, "(手机面板)", name)
        return {"ok": True, "pages": len(app.agent.clients)}

    async def do(self, a):
        if self.cool(str(a.get("action") or "")):
            return {"ok": False, "error": "太快了，稍等一下再点"}
        r = await self._do(a)
        if r.get("ok"):
            self.cd[str(a.get("action") or "")] = time.time()
        return r

    async def _do(self, a):
        o, app = self.ops, self.ops.app
        act = str(a.get("action") or "")
        if act in ("tip_now", "menu_now", "demo_now"):
            r = await app.tips.now({"tip_now": "tip", "menu_now": "menu", "demo_now": "demo"}[act])
            return r
        if act == "giftfx_test":
            k = str(a.get("which") or "1")
            if k in ("1", "2", "3"):
                return app.giftfx.trigger("gift", int(k))
            return app.giftfx.trigger(k)
        if act == "clips_now":
            return app.clips.manual("面板")
        if act == "clips_record":
            return app.clips.set_manual(bool(a.get("on")))
        if act == "clips_check":
            return await asyncio.get_running_loop().run_in_executor(None, app.clips.recheck)
        if act == "clips_delete":
            ok = app.clips.remove(str(a.get("name") or ""))
            return {"ok": ok} if ok else {"ok": False, "error": "没有这个切片"}
        if act == "story_diary":
            return await asyncio.get_running_loop().run_in_executor(None, app.story.force_diary)
        if act == "story_publish":
            return {"ok": True, "n": app.story.publish()}
        if act == "story_day":
            return {"ok": True, "date": app.story.date_label_next()}
        if act == "story_read":
            from agent import diary_act as _da
            return _da.read_now(app)
        if act == "perform_now":
            return app.tips.perform_now(str(a.get("which") or "") or None)
        if act == "guard_test":
            if not o.guard.cfg.b("guard", "enabled"):
                return {"ok": False, "error": "守护没开（[guard] enabled）"}
            o.guard.test_push()
            return {"ok": True}
        if act == "guard_ack":
            return {"ok": o.guard.ack()}
        if act == "skip_song":
            if not app.jukebox:
                return {"ok": False, "error": "点歌没开（[music]）"}
            return {"ok": True, "from_queue": await app.jukebox.skip()}
        if act == "clear_queue":
            if app.jukebox:
                app.jukebox.clear()
            return {"ok": True}
        if act == "vote_start":
            title = str(a.get("title") or "").strip()[:30]
            opts = [x.strip() for x in re.split(r"[|｜\n]", str(a.get("options") or "")) if x.strip()]
            if len(opts) < 2:
                return {"ok": False, "error": "至少两个选项，用 | 分开"}
            res = app.play.start_vote(self.room(), title or "投个票", opts, float(a.get("secs") or 0) or None, by="手机面板")
            return {"ok": bool(res.get("ok")), "error": res.get("error", "")}
        if act == "vote_end":
            return {"ok": bool(app.play.end_vote(self.room(), cancel=bool(a.get("cancel"))))}
        if act == "fx":
            k = a.get("kind")
            return await self.run_agent([{"action": "play_fx", "kind": k}]) if k in FX else {"ok": False, "error": "没有这个特效"}
        if act == "shake":
            t = a.get("target") if a.get("target") in ("chat", "desk") else "chat"
            return await self.run_agent([{"action": "shake", "target": t}])
        if act == "bsod":
            return await self.run_agent([{"action": "bsod"}])
        if act == "game_start":
            g = a.get("game") if a.get("game") in ("idiom", "song", "riddle") else "idiom"
            return await self.run_agent([{"action": "game_start", "game": g}])
        if act in ("game_stop", "song_comment", "screen_comment"):
            return await self.run_agent([{"action": act}])
        if act == "say":
            text = re.sub(r"\s+", " ", str(a.get("text") or "")).strip()[:o.cfg.i("ops", "panel_say_max")]
            host = app.any_host()
            if not text:
                return {"ok": False, "error": "没写内容"}
            if host is None:
                return {"ok": False, "error": "AI 主播没启动（要有页面连着直播间，主播才会创建）"}
            emo = a.get("emotion") if a.get("emotion") in ("开心", "兴奋", "得意", "害羞", "难过", "生气", "惊讶", "挥手", "平静") else "平静"
            await asyncio.get_running_loop().run_in_executor(None, lambda: host._say("panel", 30, text, emo))
            o.record("host", kind="panel", text=text)
            return {"ok": True}
        return {"ok": False, "error": f"不认识的动作 {act}"}

    def toggle(self, key, val):
        if key not in SWITCH_KEYS:
            return {"ok": False, "error": "这个开关不在面板白名单里"}
        self.ops.set_switch(key, bool(val))
        return {"ok": True, "key": key, "on": bool(val), "reload": SWITCH_KEYS[key][1]}

    def forget(self, name):
        mem = getattr(self.ops.app.plus, "mem", None)
        if mem is None:
            return {"ok": False, "error": "观众记忆没开（[ai_plus] memory）"}
        name = str(name or "").strip()
        if not name:
            return {"ok": False, "error": "没写昵称"}
        n = mem.forget(name=name)
        return {"ok": True, "forgot": n}


def add_routes(app, ops):
    api = PanelApi(ops)
    ops.api = api

    def guarded(fn, post=False):
        async def h(request):
            bad = api.auth(request)
            if bad:
                return bad
            try:
                return await fn(request)
            except web.HTTPException:
                raise
            except Exception as e:
                ops.log("[ops] 面板接口出错：", repr(e)[:160])
                return jr({"ok": False, "error": "服务端出错：" + repr(e)[:100]}, 500)
        return h

    async def body(request):
        try:
            d = await request.json()
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    async def state(request):
        return jr(api.state())

    async def recent(request):
        n = max(1, min(200, int(request.query.get("n", ops.cfg.i("ops", "panel_recent")) or 60)))
        return jr({"items": ops.rec.recent[-n:][::-1], "now": time.time()})

    async def do(request):
        return jr(await api.do(await body(request)))

    async def toggle(request):
        d = await body(request)
        res = api.toggle(d.get("key"), d.get("on"))
        if res.get("ok") and str(d.get("key", "")).startswith("autoclose."):          # 不用刷新页面：直接推给页面
            msg = json.dumps({"t": "autoclose_cfg", "cfg": dict(ops.cfg.cp["autoclose"])}, ensure_ascii=False)
            for rr in list(ops.app.rooms.values()):
                for ws in list(rr.clients):
                    asyncio.ensure_future(rr._send(ws, msg))
        return jr(res)

    async def reset(request):
        return jr({"ok": True, "reset": ops.reset_switches()})

    async def forget(request):
        return jr(api.forget((await body(request)).get("name")))

    async def restart(request):
        if api.cool("restart"):
            return jr({"ok": False, "error": "刚重启过"})
        api.cd["restart"] = time.time()
        ops.restart()
        return jr({"ok": True, "supervised": bool(os.environ.get("QQ_SUPERVISED")), "note": "服务马上重启，几秒后面板会自动重连"})

    async def reload_(request):
        r = api.room()
        n = 0
        for rr in list(ops.app.rooms.values()):
            for ws in list(rr.clients):
                asyncio.ensure_future(rr._send(ws, '{"t":"reload"}'))
                n += 1
        return jr({"ok": True, "pages": n})

    async def make_report(request):
        res = await asyncio.get_running_loop().run_in_executor(None, lambda: ops.make_report(None, None))
        if not res:
            return jr({"ok": False, "error": "还没有可生成的场次"})
        return jr({"ok": True, "sid": res["sid"], "summary": res["stats"]["summary"]})

    async def reports(request):
        return jr({"reports": R.list_reports(ops.cfg)[:20]})

    async def report_file(request):
        name = request.match_info["name"]
        m = NAME_RE.match(name)
        if not m:
            return web.Response(status=404, text="no such report")
        d = R.report_dir(ops.cfg)
        p = (sorted(d.glob(f"report-*.{m.group(2)}")) or [None])[-1] if m.group(1) == "latest" else d / name
        if not p or not p.exists():
            return web.Response(status=404, text="no such report")
        return web.Response(body=p.read_bytes(), content_type="text/html" if m.group(2) == "html" else "text/markdown", charset="utf-8")

    async def clip_file(request):
        p = ops.app.clips.path_of(request.match_info["name"])
        if p is None:
            return web.Response(status=404, text="no such clip")
        return web.FileResponse(p)             # 支持 Range（手机上能拖进度条）

    r = app.router
    r.add_get("/ops/api/clip/{name}", guarded(clip_file))
    r.add_get("/ops/api/state", guarded(state))
    r.add_get("/ops/api/recent", guarded(recent))
    r.add_get("/ops/api/reports", guarded(reports))
    r.add_get("/ops/api/report/{name}", guarded(report_file))
    for path, fn in (("do", do), ("toggle", toggle), ("reset", reset), ("forget", forget), ("restart", restart), ("reload", reload_), ("report", make_report)):
        r.add_post("/ops/api/" + path, guarded(fn, True))
