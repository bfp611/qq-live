# -*- coding: utf-8 -*-
"""怀旧 QQ 直播间：静态页面 + WebSocket 弹幕转发。

  python backend/server.py [房间号] [--port 8765] [--host 127.0.0.1]

页面 ?room=XXXX 会让服务器按需连接该直播间（多个页面同房间共享一个连接）；
不带 room 则使用启动时给的默认房间号。
"""
import argparse
import os
import asyncio
import json
import sys
import time
from pathlib import Path

from aiohttp import web, WSMsgType

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
sys.path.insert(0, str(ROOT / "backend"))
from dy.fetcher import DouyinFetcher  # noqa: E402
from host.config import Config  # noqa: E402
from host.engine import Host  # noqa: E402
from music import Music  # noqa: E402
from jukebox import Jukebox, parse_command  # noqa: E402
from agent.core import Agent  # noqa: E402
from agent.idle import ACTS as IDLE_ACTS, Idle  # noqa: E402
from agent.tips import Tips  # noqa: E402
from agent.welcome import Welcome  # noqa: E402
from agent.giftfx import GiftFx  # noqa: E402
from clips import Clips  # noqa: E402
from story import Story  # noqa: E402
from play.engine import Play  # noqa: E402
from ai6.plus import Plus  # noqa: E402
from ops import Ops  # noqa: E402


def norm_room(x):
    """接受纯数字，或完整的 https://live.douyin.com/123456?xxx 链接。"""
    import re
    x = str(x or "")
    m = re.search(r"live\.douyin\.com/(\d+)", x)
    return m.group(1) if m else "".join(c for c in x if c.isdigit())


def _parse_lines(s):
    """测试钩子：lines=0:前奏后第一句|12:第二句 → [[起点, 文字, 结束点]]"""
    rows = []
    for part in (s or "").split("|"):
        if ":" in part:
            t, txt = part.split(":", 1)
            try:
                rows.append([float(t), txt])
            except ValueError:
                pass
    return [[r[0], r[1], rows[i + 1][0] if i + 1 < len(rows) else r[0] + 6] for i, r in enumerate(rows)]


LOG_SINK = []          # ops 的 server.log：每一行日志都交给它


def log(*a):
    line = time.strftime("%H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(line, flush=True)
    for f in LOG_SINK:
        f(line)


class Room:
    def __init__(self, rid, loop, cfg, audio):
        self.rid = rid
        self.loop = loop
        self.cfg = cfg
        self.audio = audio
        self.clients = set()
        self.last = {}          # t -> 最近一条 room/stat/status，给新连入的页面补发
        self.idle_since = None
        self.host = None
        self.fetcher = None
        self.app = None
        if rid != "demo" and not os.environ.get("QQ_NO_FETCH"):       # demo 房间的事件由页面自己推上来；QQ_NO_FETCH=1（测试用）= 任何房间都不连抖音
            c = cfg
            self.fetcher = DouyinFetcher(rid, self.emit_threadsafe, log=log, opts={
                "live_gate": c.b("ops", "enabled") and c.b("ops", "live_gate"), "poll": c.f("ops", "live_poll_secs"), "backoff_min": c.f("ops", "backoff_min"),
                "backoff_max": c.f("ops", "backoff_max"), "stale_secs": c.f("ops", "stale_secs") if c.b("ops", "enabled") else 0,
                "recheck": c.f("ops", "live_recheck_secs") if c.b("ops", "enabled") else 0,
                "recheck_need": c.f("ops", "live_recheck_need"), "recheck_span": c.f("ops", "live_recheck_span"), "recheck_quiet": c.f("ops", "live_recheck_quiet")})
            self.fetcher.start()

    def ensure_host(self):
        if self.host is None and self.cfg.b("host", "enabled"):
            self.host = Host(self.cfg, self.emit_threadsafe, log=log, audio_store=self.audio)
            self.host.start()
            self.host.plus = getattr(self.app, "plus", None) if self.app else None
            self.host.story = getattr(self.app, "story", None) if self.app else None

    def stop(self):
        if self.fetcher:
            self.fetcher.stop()
        if self.host:
            self.host.stop()

    def emit_threadsafe(self, ev):
        self.loop.call_soon_threadsafe(self._broadcast, ev)

    def _broadcast(self, ev):
        if self.app and getattr(self.app, "ops", None):
            self.app.ops.on_event(ev, self)            # 日志 / 复盘 / 开播下播状态
        if self.app and getattr(self.app, "idle", None):
            self.app.idle.note_event(ev)               # 观众开口 → 自己玩电脑立刻停手
        if self.app and getattr(self.app, "welcome", None):
            self.app.welcome.on_event(ev, self)        # 进场接待：只观察（进场不会打断冷场玩电脑），给进场事件打「已接待」标记
        if self.app and getattr(self.app, "clips", None):
            self.app.clips.on_event(ev, self)          # 高光切片：只观察（观众发「高光」就切一个），不吃弹幕
        if self.app and getattr(self.app, "story", None):
            self.app.story.on_event(ev, self)          # 连续剧情：只观察（本场记账 / 观众记忆 / 开播下播推进日期），不吃弹幕
        if ev.get("t") in ("room", "stat", "status", "live"):
            self.last[ev["t"]] = ev
        jb = self.app.jukebox if self.app else None
        ag = self.app.agent if self.app else None
        pl = getattr(self.app, "play", None) if self.app else None
        plus = getattr(self.app, "plus", None) if self.app else None
        gf = getattr(self.app, "giftfx", None) if self.app else None
        if gf is not None and gf.on_event(ev, self):
            pass                       # 送礼的人点表演的那句弹幕：礼物联动吃掉（页面照常显示）
        elif pl is not None and pl.on_event(ev, self):
            pass                       # 互动模块吃掉的弹幕（投票数字 / 切歌 / 查积分…）：页面照常显示，但不再交给点歌 / agent / AI 主播
        elif plus is not None and plus.on_event(ev, self):
            pass                       # 加强包吃掉的弹幕（游戏答案 / 「忘记我」…）
        elif ev.get("t") == "chat" and jb and jb.on_chat(ev, self):
            if ag:
                ag.song_visual(ev, self)   # 点歌命令：不再当普通聊天交给 AI 主播；画面里让光标演一下
        elif ev.get("t") == "chat" and ag and ag.on_chat(ev, self):
            pass                       # 桌面指令：规则 / LLM 处理（普通聊天会由 agent 回头交给主播）
        elif self.host and ev.get("t") not in ("say", "status"):
            self.host.feed(ev)
        data = json.dumps(ev, ensure_ascii=False)
        for ws in list(self.clients):
            asyncio.ensure_future(self._send(ws, data))

    @staticmethod
    async def _send(ws, data):
        try:
            await ws.send_str(data)
        except Exception:
            pass


class App:
    def __init__(self, default_room, cfg):
        self.default_room = default_room
        self.cfg = cfg
        self.audio = {}      # TTS 音频缓存 id -> (bytes, mime)
        self.rooms = {}
        self.music = None
        self.jukebox = None
        self.agent = Agent(cfg, self, log)
        self.idle = Idle(cfg, self, self.agent, log)      # 冷场时猪猪侠自己玩电脑
        self.agent.idle = self.idle
        self.tips = Tips(cfg, self, self.agent, self.idle, log)   # 安静时往群聊里发「玩法提示」/ 演示一遍 / 定时玩法菜单（[tips]）
        self.welcome = Welcome(cfg, self, log)            # 进场接待：欢迎 + 推荐没用过的玩法（[welcome]）
        self.giftfx = GiftFx(cfg, self, log)              # 礼物 / 点赞 / 关注联动：按钻石档位放特效 / 表演 / 大场面（[giftfx]）
        self.highlights = []                              # 高光标记（giftfx 大礼 / 冷场表演 / 观众点的）
        self.clips = Clips(cfg, self, log)                # 高光切片：录制直播窗口，高光时刻剪成 9:16 竖屏 MP4（[clips]）
        self.story = Story(cfg, self, log)                # 连续剧情：剧情日期 / 下播后的 QQ空间日记 / 观众记忆（[story]）
        self.play = Play(cfg, self, log)                  # 积分 / QQ 等级 / 投票 / 切歌投票（[play]）
        self.plus = Plus(cfg, self, log)                  # AI 加强包：观众记忆 / 多音色 / 歌曲点评 / 小游戏 / 画面点评（[ai_plus]）
        self.ops = Ops(cfg, self, log)
        LOG_SINK[:] = [self.ops.rec.server_line]                    # 运维：看门狗 / 日志 / 复盘 / 手机面板（[ops]）
        self.music_clients = set()   # 订阅了“正在播放”的页面（?desk=xp 的千千静听）

    def music_broadcast(self, ev):
        self.ops.music_event(ev)
        data = json.dumps(ev, ensure_ascii=False)
        for ws in list(self.music_clients):
            asyncio.ensure_future(Room._send(ws, data))

    def mark_highlight(self, kind, **info):
        """标记一个「高光时刻」（giftfx 大礼 / 表演 / 以后的切片模块）：记日志 + 运维事件，切片模块开着就让它存一段"""
        h = {"at": time.time(), "kind": kind, **{k: v for k, v in info.items() if isinstance(v, (str, int, float, bool))}}
        self.highlights.append(h)
        del self.highlights[:-50]
        log(f"[高光] {kind} {' '.join(f'{k}={v}' for k, v in h.items() if k not in ('at', 'kind'))}")
        if getattr(self, "ops", None) is not None:
            try:
                self.ops.record("highlight", kind=kind, **{k: v for k, v in h.items() if k not in ("at", "kind")})
            except Exception:
                pass
        sy = getattr(self, "story", None)
        if sy is not None:
            try:
                sy.on_highlight(kind, h)
            except Exception as e:  # noqa
                log(f"[高光] 剧情模块出错：{e!r}")
        cl = getattr(self, "clips", None)
        if cl is not None:
            try:
                cl.on_highlight(kind, h)
            except Exception as e:  # noqa
                log(f"[高光] 切片模块出错：{e!r}")
        return h

    def any_host(self):
        for r in self.rooms.values():
            if r.host:
                return r.host
        return None

    def get_room(self, rid):
        r = self.rooms.get(rid)
        if not r:
            log(f"连接直播间 {rid} …")
            r = self.rooms[rid] = Room(rid, asyncio.get_running_loop(), self.cfg, self.audio)
            r.app = self
        r.idle_since = None
        return r

    async def janitor(self):
        while True:
            await asyncio.sleep(10)
            for rid, r in list(self.rooms.items()):
                if self.ops.keep(rid):
                    continue                  # [ops] keep_room：常驻房间，没有页面也继续抓、记日志
                if not r.clients:
                    r.idle_since = r.idle_since or time.time()
                    if time.time() - r.idle_since > 60:
                        log(f"直播间 {rid} 无页面使用超过 60s，断开")
                        r.stop()
                        del self.rooms[rid]

    async def ws_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        room = None
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                try:
                    d = json.loads(msg.data)
                except Exception:
                    continue
                if d.get("ev") and room and room.rid == "demo":
                    if d["ev"].get("t") in ("say", "play") or d["ev"].get("play"):
                        continue                  # 服务端自己推下去的事件别再回灌（会死循环）
                    room._broadcast(d["ev"])      # demo：页面把假事件推给服务器，让主播也能“看到”
                    continue
                if d.get("agent"):
                    await ws.send_str(json.dumps({"t": "agent_cfg", "cfg": self.agent.add_client(ws)}, ensure_ascii=False))
                    continue
                if "agent_snap" in d:
                    self.agent.set_snap(ws, d["agent_snap"])
                    continue
                if "vision" in d:
                    self.plus.vision_result(d["vision"])
                    continue
                if "agent_result" in d:
                    self.agent.job_done(d["agent_result"])
                    continue
                if d.get("music"):
                    self.music_clients.add(ws)
                    if self.music:
                        await ws.send_str(json.dumps(self.music.state, ensure_ascii=False))
                        await ws.send_str(json.dumps(self.music.lyric, ensure_ascii=False))
                    if self.jukebox:
                        await ws.send_str(json.dumps(self.jukebox.snapshot(), ensure_ascii=False))
                    continue
                if d.get("sub"):
                    rid = "demo" if str(d["sub"]) == "demo" else norm_room(d["sub"])
                    if not rid:
                        await ws.send_str(json.dumps({"t": "status", "level": "error",
                                                      "text": "房间号必须是数字（live.douyin.com/ 后面那串）"}, ensure_ascii=False))
                        continue
                    if room:
                        room.clients.discard(ws)
                    room = self.get_room(rid)
                    room.clients.add(ws)
                    if d.get("host"):
                        room.ensure_host()
                    await ws.send_str(json.dumps({"t": "hello", "room": rid}))
                    await ws.send_str(json.dumps(self.play.snapshot(rid), ensure_ascii=False))
                    if self.play.vote is not None:
                        await ws.send_str(json.dumps({"t": "play", "k": "vote", "vote": self.play.vote.snap()}, ensure_ascii=False))
                    gs = self.plus.games.snapshot() if self.plus.games.cur is not None else None
                    if gs and gs["state"] != "done":
                        await ws.send_str(json.dumps({"t": "play", "k": "game", "game": gs}, ensure_ascii=False))
                    for ev in room.last.values():
                        await ws.send_str(json.dumps(ev, ensure_ascii=False))
        finally:
            self.agent.drop_client(ws)
            self.music_clients.discard(ws)
            if room:
                room.clients.discard(ws)
        return ws

    async def music_json(self, request):
        m = self.music
        return web.json_response({"state": m.state if m else None, "lyric": (m.lyric if m else None), "method": m.method if m else None, "os": m.os if m else None,
                                  "clients": len(self.music_clients)},
                                 dumps=lambda o: json.dumps(o, ensure_ascii=False))

    # ---- 点歌：给 Jukebox 的回调 + 测试接口 ----
    def jb_emit(self, ev, room=None):
        for r in ([room] if room else list(self.rooms.values())):
            r._broadcast(ev)

    def jb_ack(self, text, room=None):
        """让 AI 主播（猪猪侠）用一句话回应点歌（有 host 才说；在线程里合成 TTS）。"""
        if not self.cfg.b("music", "ack"):
            return
        rooms = [room] if room else list(self.rooms.values())
        for r in rooms:
            if r and r.host:
                asyncio.get_running_loop().run_in_executor(None, lambda h=r.host: h._say("song", 8, text, "开心"))
                return

    async def jukebox_request(self, request):
        q = request.query
        text = q.get("text", "")
        ev = {"t": "chat", "uid": q.get("uid", "test1"), "name": q.get("name", "测试观众"), "text": text, "ts": int(time.time() * 1000)}
        if not self.jukebox or not parse_command(text):
            return web.json_response({"ok": False, "error": "不是点歌命令（要以 点歌/点播/来一首 开头）或点歌没开启"}, dumps=lambda o: json.dumps(o, ensure_ascii=False))
        real = [r for rid, r in self.rooms.items() if rid != "demo"]
        if real:
            real[0]._broadcast(ev)        # 和真实弹幕走同一条路（页面里也会出现这条弹幕）
        else:
            self.jukebox.on_chat(ev, None)
        return web.json_response({"ok": True})

    async def jukebox_json(self, request):
        j = self.jukebox
        return web.json_response({"jukebox": j.snapshot() if j else None, "history": list(j.history) if j else []},
                                 dumps=lambda o: json.dumps(o, ensure_ascii=False))

    async def jukebox_skip(self, request):
        return web.json_response({"ok": True, "from_queue": await self.jukebox.skip()} if self.jukebox else {"ok": False})

    async def jukebox_clear(self, request):
        if self.jukebox:
            self.jukebox.clear()
        return web.json_response({"ok": True})

    # ---- 桌面 Agent：状态 + 测试接口（仅本机访问，agent.test_endpoints=false 关闭）----
    def _agent_guard(self, request):
        if not self.cfg.b("agent", "test_endpoints") or request.remote not in ("127.0.0.1", "::1", None):
            return web.json_response({"ok": False, "error": "测试接口只允许本机访问且需 [agent] test_endpoints=true"}, status=403)
        return None

    def _jr(self, o, status=200):
        return web.json_response(o, status=status, dumps=lambda x: json.dumps(x, ensure_ascii=False))

    async def agent_state(self, request):
        bad = self._agent_guard(request)
        return bad or self._jr(self.agent.state())

    async def agent_say(self, request):
        """/agent/say?text=把红警关掉&name=小明&dry=1&via=rule|llm&full=1
        dry=1（默认）只解析不执行；dry=0 解析+校验+执行+说话（跳过限速）；full=1 走真实弹幕管线（含限速、聊天兜底）。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        q = request.query
        text, name, uid = q.get("text", ""), q.get("name", "测试观众"), q.get("uid", "test1")
        real = [r for rid, r in self.rooms.items()]
        room = real[0] if real else None
        if q.get("full") == "1":
            ev = {"t": "chat", "uid": uid, "name": name, "text": text, "ts": int(time.time() * 1000)}
            if room:
                room._broadcast(ev)
            return self._jr({"ok": bool(room), "full": True})
        out = await self.agent.simulate(text, name=name, uid=uid, dry=q.get("dry", "1") != "0", force=True, room=room, via=q.get("via") or None)
        return self._jr(out)

    async def tips_api(self, request):
        """/tips/state 看状态；/tips/now?kind=tip|menu|demo[&cmd=玩扫雷] 立刻发一条（测试用，仅本机 + [agent] test_endpoints=true）"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        q = request.query
        if request.path.endswith("/now"):
            return self._jr(await self.tips.now(q.get("kind", "tip"), q.get("cmd") or None))
        return self._jr(self.tips.state())

    async def agent_idle(self, request):
        """/agent/idle 看状态；?run=browse_ie 立刻演一次（无视冷场计时，其余条件照旧）；?stop=1 打断；?reset=1 清掉冷却；?cfg=k:v 临时改 [idle] 配置（测试用）。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        if not self.cfg.b("idle", "test_endpoints"):
            return web.json_response({"ok": False, "error": "需要 [idle] test_endpoints=true"}, status=403)
        q, idle = request.query, self.idle
        for kv in q.getall("cfg", []):
            k, _, v = kv.partition(":")
            if k in idle.cfg.cp["idle"]:
                idle.cfg.cp["idle"][k] = v
        if q.get("reset"):
            idle.next_at = 0
            idle.last_viewer = 0
        if q.get("stop"):
            idle.interrupt("手动停止")
        if q.get("run"):
            name = q["run"]
            if name not in IDLE_ACTS:
                return self._jr({"ok": False, "error": "没有这个活动"}, 400)
            if idle.task and not idle.task.done():
                return self._jr({"ok": False, "error": "已经在进行了", **idle.state()}, 409)
            if not self.agent.clients:
                return self._jr({"ok": False, "error": "没有页面连着"}, 409)
            idle.begin(name, force=True)
        return self._jr(idle.state())

    async def agent_do(self, request):
        """/agent/do?a=[{"action":"close_window","target":"ra2"}] 直接执行动作列表（校验照常，不过 NLU）。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        try:
            acts = json.loads(request.query.get("a", "[]"))
        except Exception:
            return self._jr({"ok": False, "error": "a 不是 JSON"}, 400)
        if isinstance(acts, dict):
            acts = [acts]
        user = request.query.get("name", "测试观众")
        good, errs, say = self.agent.validate(acts, self.agent.desk(), user)
        ev = {"t": "chat", "uid": "test1", "name": user, "text": request.query.get("text", "(test)")}
        real = list(self.rooms.values())
        if good:
            await self.agent.execute(good, ev, real[0] if real else None, ev["text"], user)
        return self._jr({"ok": bool(good), "actions": good, "rejected": errs, "say": say, "clients": len(self.agent.clients)})

    async def qq_event(self, request):
        """/qq/event?t=gift&name=小明&gift=玫瑰花&value=1&count=1（也可 t=chat&text=..）把一个假事件灌进真实直播间的管线（页面、AI 主播都会收到），测试 QQ 生态的礼物 / 留言用；仅本机，[agent] test_endpoints 控制。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        q = request.query
        t = q.get("t", "gift")
        ev = {"t": t, "uid": q.get("uid", "t" + str(abs(hash(q.get("name", "测试观众"))) % 100000)), "name": q.get("name", "测试观众"), "ts": int(time.time() * 1000)}
        if t == "gift":
            ev.update({"gift": q.get("gift", "玫瑰花"), "count": int(q.get("count", "1") or 1), "value": int(q.get("value", "0") or 0)})
        elif t == "chat":
            ev["text"] = q.get("text", "")
        elif t == "like":
            ev["count"] = int(q.get("count", "1") or 1)
        elif t == "live":                      # 模拟开播 / 下播（[ops]：日志按场、复盘、面板），live=0 是下播
            ev = {"t": "live", "live": q.get("live", "1") not in ("0", "false"), "room": self.default_room, "room_id": "0", "anchor": q.get("anchor", "测试主播"), "title": q.get("title", "测试直播")}
        elif t == "end":
            ev = {"t": "end"}
        elif t == "switch":                    # 测试：让页面切到另一个房间（自动切换时服务端发的就是这条）
            ev = {"t": "switch", "room": q.get("to", "")}
        elif t == "stat":
            ev = {"t": "stat", "online": int(q.get("online", "10") or 0), "total": q.get("total", "100")}
        if q.get("room") == "demo" and "demo" in self.rooms:
            self.rooms["demo"]._broadcast(ev)
            return self._jr({"ok": True, "event": ev, "room": "demo"})
        real = [r for rid, r in self.rooms.items() if rid != "demo"]
        if not real:
            return self._jr({"ok": False, "error": "没有真实直播间"}, 400)
        real[0]._broadcast(ev)
        return self._jr({"ok": True, "event": ev})


    # ---- 观众互动（[play]）：榜单 / 状态 / 测试 ----
    def _play_scope(self, request):
        r = request.query.get("room") or ""
        if r:
            return "demo" if r == "demo" else norm_room(r)
        real = [rid for rid in self.rooms if rid != "demo"]
        return self.default_room or (real[0] if real else "demo")

    async def play_rank(self, request):
        """/play/rank.json?room=&by=day|total&n=20 —— 积分榜（页面的排行榜窗口每几秒拉一次）。"""
        q = request.query
        sc = self._play_scope(request)
        by = "day" if q.get("by") == "day" else "total"
        return self._jr({"ok": True, "scope": sc, "by": by, "rows": self.play.rank(sc, by, max(1, min(100, int(q.get("n", "20") or 20))))})

    async def play_state(self, request):
        bad = self._agent_guard(request)
        if bad:
            return bad
        return self._jr(self.play.state(self._play_scope(request)))

    async def ai_state(self, request):
        """/ai/state —— AI 加强包状态（记忆条数、游戏、最近动作）。仅本机，[agent] test_endpoints。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        return self._jr(self.plus.state())

    async def ai_do(self, request):
        """/ai/do?a=song_comment|screen_comment|game_start:idiom|game_stop —— 手动触发加强包动作（测试）。仅本机，[agent] test_endpoints。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        a = request.query.get("a", "")
        act, _, arg = a.partition(":")
        spec = {"action": act}
        if act == "game_start":
            spec["game"] = arg or "idiom"
        real = [r for rid, r in self.rooms.items() if rid != "demo"] or list(self.rooms.values())
        ok, msg = self.plus.agent_action(spec, {}, real[0] if real else None, request.query.get("name", "测试"))
        if asyncio.iscoroutine(ok):
            ok, msg = await ok
        return self._jr({"ok": bool(ok), "msg": msg})

    async def ai_memory(self, request):
        """/ai/memory?name=昵称 查某个观众的记忆；/ai/forget?name=昵称 或 ?all=1 删除。仅本机，[agent] test_endpoints。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        q = request.query
        mem = self.plus.mem
        if mem is None:
            return self._jr({"ok": False, "error": "记忆没开（[ai_plus] memory）"})
        if request.path.endswith("forget"):
            n = mem.forget(name=q.get("name"), all_=bool(q.get("all")))
            return self._jr({"ok": True, "forgot": n})
        rows = [r for _, r in mem.find_name(q["name"])] if q.get("name") else []
        return self._jr({"ok": True, "rows": rows, "stats": mem.stats()})

    async def play_testsong(self, request):
        """/play/testsong?title=夜曲（&off=1 关掉）—— 测试钩子：假装正在放歌，好测切歌投票（真放歌时不需要）。仅本机，[agent] test_endpoints。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        q = request.query
        self.play.test_song = None if q.get("off") else {"on": True, "key": q.get("key") or q.get("title", "测试歌"), "title": q.get("title", "测试歌"), "artist": q.get("artist", "测试"), "playing": True, "pos": float(q.get("pos", "0") or 0), "ts": int(time.time() * 1000), "duration": float(q.get("dur", "200") or 200), "lines": _parse_lines(q.get("lines"))}
        return self._jr({"ok": True, "song": self.play.test_song})

    async def play_vote(self, request):
        """/play/vote?q=下一步干啥&opts=玩红警|换壁纸|扫雷&secs=20（&end=1 提前结束，&cancel=1 取消）—— 测试用，仅本机，[agent] test_endpoints。"""
        bad = self._agent_guard(request)
        if bad:
            return bad
        q = request.query
        sc = self._play_scope(request)
        room = self.rooms.get(sc) or next(iter(self.rooms.values()), None)
        if q.get("end") or q.get("cancel"):
            return self._jr({"ok": self.play.end_vote(room, cancel=bool(q.get("cancel")))})
        from play.engine import parse_options
        title, opts = parse_options(q.get("opts", ""))
        return self._jr(self.play.start_vote(room, q.get("q") or title, opts, int(q["secs"]) if q.get("secs") else None, by="测试"))

    async def music_cover(self, request):
        c = self.music.cover if self.music else None
        if not c:
            return web.Response(status=404)
        return web.Response(body=c[1], content_type=c[2])

    async def config(self, request):
        return web.json_response({"room": self.default_room, "host_name": self.cfg.s("host", "name"),
                                  "host_label": self.cfg.s("host", "label"),
                                  "host_enabled": self.cfg.b("host", "enabled"),
                                  "tts": self.cfg.s("tts", "backend"), "agent": self.agent.page_cfg(), "xp": dict(self.cfg.cp["xp"]), "qq": dict(self.cfg.cp["qq"]), "play": dict(self.cfg.cp["play"]), "autoclose": dict(self.cfg.cp["autoclose"]),
                                  "ops": {"report": self.cfg.b("ops", "enabled") and self.cfg.b("ops", "report")},
                                  "ai_plus": {k: self.cfg.s("ai_plus", k) for k in ("enabled", "game", "game_window", "game_close_secs", "screen", "song_comment", "memory")}})

    async def story_json(self, request):
        return web.json_response(self.story.snapshot())

    async def tts_file(self, request):
        item = self.audio.get(request.match_info["sid"])
        if not item:
            return web.Response(status=404)
        return web.Response(body=item[0], content_type=item[1])


@web.middleware
async def no_cache(request, handler):
    resp = await handler(request)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@web.middleware
async def lan_guard(request, handler):
    """监听局域网（手机面板）时：非本机来源只能访问 /panel 页面和 /ops/api/*（后者自己验令牌）；其余（弹幕页 / ws / 测试接口 / 配置）一律 403"""
    from ops.panel import is_loopback
    p = request.path
    if not is_loopback(request.remote) and not (p == "/panel" or p.startswith("/panel/") or p.startswith("/ops/api/")):
        return web.Response(status=403, text="forbidden: 局域网只开放手机面板 /panel", content_type="text/plain", charset="utf-8")
    return await handler(request)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("room", nargs="?", default="")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default=None, help="监听地址。不写：默认 127.0.0.1；[ops] panel_lan=true 时监听 0.0.0.0（局域网手机面板），但除 /panel 和 /ops/api 外的路径只放行本机")
    ap.add_argument("--config", default=str(ROOT / "config.ini"))
    a = ap.parse_args()
    app_state = App(norm_room(a.room), Config(a.config))
    c0 = app_state.cfg
    lan = c0.b("ops", "enabled") and c0.b("ops", "panel") and c0.b("ops", "panel_lan") and a.host is None
    host = a.host or ("0.0.0.0" if lan else "127.0.0.1")
    app_state.ops.port, app_state.ops.lan = a.port, host not in ("127.0.0.1", "localhost", "::1")
    app = web.Application(middlewares=[no_cache] + ([lan_guard] if lan else []))
    app.router.add_get("/ws", app_state.ws_handler)
    app.router.add_get("/config.json", app_state.config)
    app.router.add_get("/story.json", app_state.story_json)
    app.router.add_get("/tts/{sid}", app_state.tts_file)
    app.router.add_get("/music.json", app_state.music_json)
    app.router.add_get("/music/cover", app_state.music_cover)
    app.router.add_get("/jukebox/request", app_state.jukebox_request)
    app.router.add_get("/jukebox.json", app_state.jukebox_json)
    app.router.add_get("/jukebox/skip", app_state.jukebox_skip)
    app.router.add_get("/jukebox/clear", app_state.jukebox_clear)
    app.router.add_get("/agent/state", app_state.agent_state)
    app.router.add_get("/agent/say", app_state.agent_say)
    app.router.add_get("/agent/idle", app_state.agent_idle)
    app.router.add_get("/tips/state", app_state.tips_api)
    app.router.add_get("/tips/now", app_state.tips_api)
    app.router.add_get("/agent/do", app_state.agent_do)
    app.router.add_get("/qq/event", app_state.qq_event)
    app.router.add_get("/play/rank.json", app_state.play_rank)
    app.router.add_get("/play/state", app_state.play_state)
    app.router.add_get("/play/vote", app_state.play_vote)
    app.router.add_get("/play/testsong", app_state.play_testsong)
    app.router.add_get("/ai/state", app_state.ai_state)
    app.router.add_get("/ai/do", app_state.ai_do)
    app.router.add_get("/ai/memory", app_state.ai_memory)
    app.router.add_get("/ai/forget", app_state.ai_memory)
    from ops.web import add_routes as ops_routes
    ops_routes(app, app_state.ops)
    app.router.add_get("/panel", lambda r: web.FileResponse(WEB / "panel" / "index.html"))
    app.router.add_get("/", lambda r: web.FileResponse(WEB / "index.html"))
    app.router.add_static("/", WEB, show_index=False)

    async def on_start(app):
        asyncio.ensure_future(app_state.janitor())
        app_state.idle.start()
        app_state.tips.start()
        app_state.welcome.start()
        app_state.giftfx.start()
        app_state.clips.start()
        app_state.story.start()
        app_state.ops.start(asyncio.get_running_loop())
        app_state.play.start(asyncio.get_running_loop())
        app_state.plus.start(asyncio.get_running_loop())
        cfg = app_state.cfg
        if cfg.b("music", "enabled"):
            app_state.music = Music(ROOT, app_state.music_broadcast, log=log, bundle=cfg.s("music", "bundle"), player=cfg.s("music", "player"),
                                    interval=max(0.4, cfg.f("music", "interval")), lyric_offset=cfg.f("music", "lyric_offset"))
            app_state.music.start()
            app_state.jukebox = Jukebox(cfg, app_state.music, log, app_state.jb_emit, app_state.jb_ack, app_state.music_broadcast)
            app_state.jukebox.start()
        if app_state.default_room:
            app_state.get_room(app_state.default_room)
    app.on_startup.append(on_start)

    async def on_stop(app):
        app_state.clips.shutdown()
        app_state.story.shutdown()
        app_state.ops.stop()
        app_state.play.stop()
        app_state.plus.stop()
    app.on_shutdown.append(on_stop)

    base = f"http://localhost:{a.port}/"
    log("=" * 60)
    log(f"怀旧 QQ 直播间已启动。浏览器源地址：{base}" + (f"" if app_state.default_room else "?room=你的房间号"))
    log(f"测试（假数据）：{base}?demo=1")
    if app_state.ops.on() and c0.b("ops", "panel"):
        app_state.ops.token()                         # 第一次运行：生成令牌文件（只提示文件位置，不打印令牌）
        urls = app_state.ops.panel_urls()
        log("手机控制面板（同一 Wi-Fi 的手机打开）：" + ("  ".join(urls) if urls else f"{base}panel（只在本机；[ops] panel_lan=true 才开放局域网）"))
        log(f"面板令牌文件：{app_state.ops.token_path_display()}")
    log("=" * 60)
    web.run_app(app, host=host, port=a.port, print=None)


if __name__ == "__main__":
    main()
