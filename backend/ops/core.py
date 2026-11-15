# -*- coding: utf-8 -*-
"""Ops 核心：常驻房间（keep_room）、开播/下播联动、自动切换到正在直播的房间。
抓取器自己的重连 / 退避 / 开播下播轮询在 dy/fetcher.py；这里负责「服务端」这一层。"""
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

from . import logs as L
from . import report as R
from . import panel as P
from .guard import Guard

ROOT = Path(__file__).resolve().parent.parent.parent


class Ops:
    def __init__(self, cfg, app, log=print):
        self.cfg, self.app, self.log = cfg, app, log
        self.loop = None
        self.stopped = threading.Event()
        self.live_since = None       # 当前这场开始（epoch 秒），没开播 None
        self.last_switch = 0.0
        self.last_probe = 0.0
        self.probe_result = ""       # 最近一次自动检测房间的结果（给控制面板看）
        self.hooks = []              # 其它子模块注册的 on_event(ev, room)
        self._thread = None
        self.rec = L.Recorder(cfg, log, ROOT)
        self.rec.on_end.append(self._session_ended)
        self.hooks.append(self.rec.handle)
        self.guard = Guard(self)
        self.hooks.append(self.guard.on_event)
        self.last_report = None      # {sid, md, html, at} 最近生成的复盘
        self.report_busy = False
        self.overrides = {}          # 手机面板改过的开关：{"agent.enabled": "false"}，存 [ops] overrides_file
        self._orig = {}              # key → config.ini 里原来的值（还原用）
        self.api = None
        self.port = 8765             # server.main 启动时填
        self.lan = False             # 是否绑定了局域网（0.0.0.0）
        self._token = None
        self.lock_out = P.Lockout(int(cfg.f("ops", "panel_fail_lock")))

    # ---------- 开关 ----------
    def on(self):
        return self.cfg.b("ops", "enabled")

    def keep(self, rid):
        """janitor 用：常驻房间不因为「没有页面」被断开（没有页面时日志和复盘也要继续）"""
        return self.on() and self.cfg.b("ops", "keep_room") and rid == self.app.default_room and rid != "demo"

    # ---------- 生命周期 ----------
    def start(self, loop):
        self.loop = loop
        if not self.on():
            return
        self.rec.start()
        self.load_overrides()
        self.guard.start()
        self._thread = threading.Thread(target=self._watch, daemon=True, name="ops-watch")
        self._thread.start()

    def stop(self):
        self.stopped.set()
        try:
            self.rec.stop()
        except Exception as e:
            self.log("[ops] 收尾日志出错：", repr(e)[:100])

    # ---------- 手机面板：开关（运行时改 + 持久化，不动 config.ini）----------
    def overrides_path(self):
        p = Path(self.cfg.s("ops", "overrides_file") or "data/ops_overrides.json")
        return p if p.is_absolute() else ROOT / p

    def load_overrides(self):
        try:
            d = json.loads(self.overrides_path().read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except Exception as e:
            self.log("[ops] 读开关覆盖文件出错：", repr(e)[:80])
            return
        from .api import SWITCH_KEYS
        for k, v in (d or {}).items():
            if k in SWITCH_KEYS and v in ("true", "false"):
                self._apply(k, v)
        if self.overrides:
            self.log(f"[ops] 已套用手机面板改过的 {len(self.overrides)} 个开关（{self.overrides_path()}；面板里可「还原为 config.ini」）")

    def _apply(self, key, val):
        sec, k = key.split(".")
        if key not in self._orig:
            self._orig[key] = self.cfg.cp[sec][k] if self.cfg.cp.has_option(sec, k) else None
        self.cfg.cp[sec][k] = val
        self.overrides[key] = val

    def _save_overrides(self):
        p = self.overrides_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self.overrides, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            self.log("[ops] 存开关覆盖文件出错：", repr(e)[:80])

    def _after(self, key):
        """有些模块在初始化时把开关抄了一份：运行时改了要同步过去"""
        if key == "music.jukebox":
            jb = getattr(self.app, "jukebox", None)
            if jb is not None:
                jb.enabled = self.cfg.b("music", "jukebox")
                try:
                    jb._push()
                except Exception:
                    pass

    def set_switch(self, key, on):
        self._apply(key, "true" if on else "false")
        self._after(key)
        self._save_overrides()
        self.log(f"[ops] 面板把 {key} 改成 {'开' if on else '关'}")
        self.record("switch", key=key, on=bool(on))

    def reset_switches(self):
        n = len(self.overrides)
        for k in list(self.overrides):
            sec, kk = k.split(".")
            o = self._orig.get(k)
            if o is not None:
                self.cfg.cp[sec][kk] = o
            self.overrides.pop(k, None)
            self._after(k)
        self._save_overrides()
        return n

    # ---------- 手机面板：令牌 / 地址 ----------
    def token(self):
        if self._token is None:
            self._token = P.ensure_token(self.cfg, ROOT, self.log)
        return self._token

    def token_path_display(self):
        if self.cfg.s("ops", "panel_token").strip():
            return "config.ini 的 [ops] panel_token"
        return str(P.token_path(self.cfg, ROOT))

    def panel_urls(self):
        """局域网地址（没绑定局域网 = 空列表）"""
        if not (self.cfg.b("ops", "panel") and self.lan):
            return []
        return [f"http://{ip}:{self.port}/panel" for ip in P.lan_ips()]

    # ---------- 记录 / 复盘 ----------
    def record(self, kind, /, **f):
        try:
            return self.rec.record(kind, **f)
        except Exception:
            return False

    def music_event(self, ev):
        try:
            self.rec.handle_music(ev, getattr(self.app, "jukebox", None))
        except Exception:
            pass

    def _session_ended(self, meta):
        c = self.cfg
        if not (c.b("ops", "report") and c.b("ops", "report_on_end")):
            return
        if (meta.get("end", 0) - meta.get("start", 0)) < c.f("ops", "report_min_secs"):
            self.log(f"[ops] 这一场只有 {int(meta.get('end', 0) - meta.get('start', 0))} 秒，不出复盘（[ops] report_min_secs）")
            return
        threading.Thread(target=self.make_report, args=(meta["sid"], None, self.stopped.is_set()), daemon=True, name="ops-report").start()

    def make_report(self, sid=None, use_llm=None, quick=False):
        """生成复盘（阻塞）。sid 缺省 = 最近一场（含正在进行的：先不结束它，按当前日志出一份）。quick=True 不调 LLM（服务停止时用）"""
        c = self.cfg
        if not c.b("ops", "report"):
            return None
        sid = sid or (self.rec.sess["sid"] if self.rec.sess else (L.list_sessions(self.rec.logdir()) or [{}])[0].get("sid"))
        if not sid:
            return None
        self.report_busy = True
        try:
            r = R.generate(c, sid, self.log, use_llm=False if quick else use_llm, root=ROOT)
        except Exception as e:
            self.log(f"[ops] 生成复盘失败：{e!r}"[:200])
            return None
        finally:
            self.report_busy = False
        if r:
            self.last_report = {"sid": sid, "md": r["md"], "html": r["html"], "at": time.time()}
            self.log(f"[ops] 复盘已生成：{r['md']}")
        return r

    def restart(self, delay=0.6):
        """重启服务：被 tools/supervisor.py 管着（环境变量 QQ_SUPERVISED）就用退出码 75 让它拉起；否则原地 execv 重新执行自己"""
        def go():
            self.log("[ops] 重启服务 …")
            try:
                cl = getattr(self.app, "clips", None)
                if cl is not None:
                    cl.shutdown()                        # os._exit 不会跑 atexit：先把 ffmpeg 收了
            except Exception:
                pass
            try:
                self.stop()
            except Exception:
                pass
            sys.stdout.flush()
            if os.environ.get("QQ_SUPERVISED"):
                os._exit(75)
            try:
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                self.log("[ops] 原地重启失败，直接退出（请手动再启动）：", repr(e)[:100])
                os._exit(75)
        self.loop.call_later(delay, go)

    # ---------- 事件（Room._broadcast 最先调用；不得抛异常） ----------
    def on_event(self, ev, room):
        t = ev.get("t")
        if t == "live":
            self.live_since = time.time() if ev.get("live") else None
        for h in self.hooks:
            try:
                h(ev, room)
            except Exception as e:
                self.log("[ops] 事件钩子出错：", repr(e)[:160])

    def state(self):
        f = self.fetcher_of_default()
        return {"enabled": self.on(), "room": self.app.default_room, "fetcher": f.snapshot() if f else None, "session": self.rec.snapshot(),
                "live_since": self.live_since, "probe": self.probe_result, "last_report": self.last_report, "report_busy": self.report_busy,
                "last_switch": self.last_switch, "guard": self.guard.snapshot(), "pages": sum(len(r.clients) for r in self.app.rooms.values())}

    # ---------- 自动切换 ----------
    def fetcher_of_default(self):
        r = self.app.rooms.get(self.app.default_room)
        return r.fetcher if r else None

    def _watch(self):
        while not self.stopped.wait(2):
            try:
                self.rec.tick()
                self._tick()
            except Exception as e:
                self.log("[ops] 看门狗出错：", repr(e)[:160])

    def _tick(self):
        c = self.cfg
        if not (c.b("ops", "watch") and c.b("ops", "autoswitch") and c.b("ops", "detect_room")):
            return
        f = self.fetcher_of_default()
        if f is None or f.live is not False:
            return                                  # 在直播 / 还不知道：不动
        now = time.time()
        if now - self.last_probe < max(60.0, c.f("ops", "live_poll_secs") * 3):
            return
        self.last_probe = now
        rid = self.detect_live_room()
        if rid and rid != self.app.default_room:
            self.switch_room(rid, "自动检测到正在直播的房间")

    def detect_live_room(self):
        """从直播伴侣日志找最近一场的房间；只有它「正在直播」才返回 web_rid（没有直播伴侣的系统直接返回 None）"""
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            import find_room as fr
            if sys.platform not in ("darwin", "win32"):
                self.probe_result = "本系统没有直播伴侣，不自动检测"
                return None
            try:
                room_id = fr.room_id_from_webcast_mate()
            except SystemExit as e:
                self.probe_result = str(e)[:100]
                return None
            web_rid, nick, status = fr.reflow(room_id)
            self.probe_result = f"{nick}（{web_rid}）状态 {status}"
            return web_rid if status == 2 else None
        except BaseException as e:               # find_room 用 SystemExit 报错
            self.probe_result = "检测失败：" + repr(e)[:80]
            return None

    def switch_room(self, rid, why=""):
        rid = re.sub(r"\D", "", str(rid))
        if not rid or rid == self.app.default_room:
            return False
        old = self.app.default_room
        self.log(f"[ops] 切换直播间 {old} → {rid}（{why}）")
        self.last_switch = time.time()
        self.app.default_room = rid

        def go():
            self.app.get_room(rid)
            r = self.app.rooms.get(old)
            if r:
                for ws in list(r.clients):
                    import asyncio
                    asyncio.ensure_future(r._send(ws, '{"t":"switch","room":"%s"}' % rid))
        self.loop.call_soon_threadsafe(go)
        return True
