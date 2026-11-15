# -*- coding: utf-8 -*-
"""AI 加强包总管（[ai_plus]）：把 观众记忆 / 多音色 / 歌曲点评 / 小游戏 / 画面点评 接到事件流和 AI 主播上。

事件入口 Plus.on_event(ev, room)：由 server.Room._broadcast 在 play 之后、点歌 / agent / 主播之前调用；
返回 True = 这条弹幕被吃掉了（游戏答案 / 记忆口令），不再交给点歌、agent 和 AI 主播。
"""
import asyncio
import json
import random
import re
import threading
import time
from pathlib import Path

from . import store as S

ROOT = Path(__file__).resolve().parent.parent.parent


def _kv(text):
    out = {}
    for part in re.split(r"[,，;；\s]+", text or ""):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
        elif "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


FORGET_RE = re.compile(r"^(?:请|麻烦)?(?:忘记我|忘掉我|忘了我|把我忘了|清除我的记忆|删除我的记忆|别记(?:住)?我|不要记(?:住)?我|forgetme)(?:吧|啦|了|哦)?[。.!！~]*$", re.I)
REMEMBER_RE = re.compile(r"^(?:请)?(?:记住我|开启记忆|记得我|rememberme)(?:吧|啦|哦)?[。.!！~]*$", re.I)
SONG_CMD = re.compile(r"^\s*(?:点歌|点播|点一首|来一首|来首)")        # 和 jukebox.CMD 同一批前缀：点歌命令不当“话题”记
ASKMEM_RE = re.compile(r"^(?:你)?(?:还)?(?:记得我(?:吗|么|不)?|认识我(?:吗|么)|我的记忆|你对我的记忆|你记得我什么)[?？。.!！~]*$")


SCREEN_APPS_SKIP = ('qqchat',)


class Plus:
    def __init__(self, cfg, app, log=print):
        self.cfg, self.app, self.log = cfg, app, log
        self.loop = None
        self.mem = None
        self.last_greet = 0.0
        self.stats = {"events": 0, "greets": 0, "mem_replies": 0, "forgets": 0}
        self._task = None
        self.song = {"key": "", "t0": 0.0, "pending": False, "want": False, "tries": 0}
        self.last_song_comment = 0.0
        self.cmd_at = {}
        self.scr = {"fp": None, "changes": [], "since": 0.0, "last": 0.0, "busy": False, "last_text": "", "vision": None}
        self.vis_wait = {}
        self.vis_seq = 0
        self.vis_fail = 0
        self.vis_off_until = 0.0
        self.last_chat = 0.0
        from .games import Games
        self.games = Games(self)
        self.recent = []          # 最近几条“加强包”动作记录，给 /ai/state 看
        if self.on() and self.m("memory"):
            f = cfg.s("ai_plus", "memory_file")
            p = (ROOT / f) if f and not Path(f).is_absolute() else (Path(f) if f else None)
            self.mem = S.MemoryStore(p, cfg.i("ai_plus", "memory_max_viewers"), cfg.i("ai_plus", "memory_keep_days"), cfg.i("ai_plus", "memory_topics"),
                                     cfg.i("ai_plus", "memory_topic_chars"), cfg.i("ai_plus", "memory_songs"), log)
        self.voices_ctx = _kv(cfg.s("ai_plus", "voice_ctx"))
        self.voice_names = _kv(cfg.s("ai_plus", "voice_names"))

    # ---- 开关 ----
    def on(self):
        return self.cfg.b("ai_plus", "enabled")

    def m(self, k):
        return self.on() and self.cfg.b("ai_plus", k)

    def note(self, what):
        self.recent.append({"at": int(time.time()), "what": what})
        del self.recent[:-30]

    # ---- 多音色：说话的场合(kind) → 角色(role) → 显示名 ----
    def role_for(self, kind):
        if not self.on():
            return ""
        r = self.voices_ctx.get(kind, "")
        return "" if r in ("host", "default") else r

    def role_name(self, role):
        return self.voice_names.get(role) or role

    # ---- 生命周期 ----
    def start(self, loop):
        self.loop = loop
        self._task = asyncio.ensure_future(self._run())

    def stop(self):
        if self._task:
            self._task.cancel()
        if self.mem:
            try:
                self.mem.save(force=True)
            except Exception as e:  # noqa
                self.log(f"[记忆] 退出时保存失败：{e!r}")

    async def _run(self):
        n = 0
        while True:
            await asyncio.sleep(1)
            n += 1
            try:
                self.games.tick()
                if n % 2 == 0:
                    self.song_tick()
                if n % 3 == 0:
                    self.screen_tick()
                if self.mem and n % 10 == 0:
                    self.mem.save()
                if self.mem and n % 3600 == 0:
                    self.mem.prune()
            except Exception as e:  # noqa
                self.log(f"[ai_plus] 后台任务出错：{e!r}")

    # ---- 工具 ----
    def host_of(self, room):
        h = getattr(room, "host", None) if room is not None else None
        return h or (self.app.any_host() if hasattr(self.app, "any_host") else None)

    def in_thread(self, fn, *a):
        def run():
            try:
                fn(*a)
            except Exception as e:  # noqa
                self.log(f"[ai_plus] 后台说话出错：{e!r}")
        if self.loop is None:
            threading.Thread(target=run, daemon=True).start()
        else:
            self.loop.run_in_executor(None, run)

    def sysline(self, room, text):
        if room is not None:
            room._broadcast({"t": "sys", "text": text, "play": 1, "ts": int(time.time() * 1000)})

    def level(self, room, uid):
        pl = getattr(self.app, "play", None)
        if pl is None or not pl.on():
            return 0, ""
        try:
            sc = getattr(room, "rid", "0")
            lv = pl.level_for(sc, uid)
            from play.engine import level_glyphs
            return lv, level_glyphs(lv) if lv else ""
        except Exception:
            return 0, ""

    # ---- 事件入口 ----
    def on_event(self, ev, room):
        if not self.on():
            return False
        t = ev.get("t")
        self.stats["events"] += 1
        uid = str(ev.get("uid") or "")
        name = ev.get("name") or ""
        consumed = False
        if t == "chat":
            self.last_chat = time.time()
        if t == "chat" and self.games.cur is not None:
            try:
                if self.games.on_chat(ev, room, uid or name, name):
                    return True
            except Exception as e:  # noqa
                self.log(f"[游戏] 处理弹幕出错：{e!r}")
        if self.mem is not None and uid and t in ("chat", "member", "gift", "like", "follow"):
            now = time.time()
            rec, new_visit, before = self.mem.touch(uid, name, now, self.cfg.i("ai_plus", "memory_session_gap"))
            if t == "chat" and self.m("memory_cmd"):
                text = re.sub(r"\s+", "", ev.get("text") or "")
                if FORGET_RE.match(text):
                    return self._forget(ev, room, uid, name)
                if REMEMBER_RE.match(text):
                    return self._remember(ev, room, uid, name)
                if ASKMEM_RE.match(text):
                    return self._ask_memory(ev, room, uid, name)
            if rec is not None:
                if t == "chat":
                    if not SONG_CMD.match(ev.get("text") or ""):
                        self.mem.chat(uid, ev.get("text"))
                elif t == "gift":
                    self.mem.gift(uid, ev.get("gift"), ev.get("count") or 1)
                elif t == "member" and new_visit and before is not None and self.m("memory_greet"):
                    self._maybe_greet(ev, room, uid, name, rec, before, now)
        return consumed

    # ---- 老观众：欢迎 / 回复上下文 / 口令 ----
    def _facts(self, room, uid, rec, now=None):
        lv, gl = self.level(room, uid)
        return S.facts(rec, lv, gl, now), lv

    def _maybe_greet(self, ev, room, uid, name, rec, before, now):
        if ev.get("welcome_handled"):
            return                                  # [welcome] 进场接待开着：由它统一欢迎
        if rec["visits"] < max(2, self.cfg.i("ai_plus", "memory_greet_min_visits")):
            return
        if now - self.last_greet < self.cfg.f("ai_plus", "memory_greet_gap"):
            return
        h = self.host_of(room)
        if h is None:
            return
        self.last_greet = now
        ev["ai6_greeted"] = True                   # 告诉主播：这个人我单独欢迎了，别再套用普通欢迎词
        self.stats["greets"] += 1
        facts, lv = self._facts(room, uid, before, now)
        nick = _nick(name or rec["nick"])
        self.note(f"欢迎老观众 {rec['nick']}（第{rec['visits']}次）")
        self.in_thread(self._greet, h, nick, before, facts, lv)

    def _greet(self, h, nick, before, facts, lv):
        fb = greet_template(nick, before, lv)
        prompt = None
        if self.cfg.b("ai_plus", "memory_greet_llm"):
            prompt = (f"【老观众回来了】观众「{nick}」又来直播间了。你对他的记忆：{facts}。\n"
                      "请用你的口吻热情欢迎他回来，自然地提一两个你记得的细节（比如上次点的歌、送的礼物、聊过的话），像老朋友一样；不要像念档案一样报数字，不要提任何隐私。")
        h.speak("greet", prompt, fb, "开心", to=nick, prio=50)

    def reply_context(self, uids):
        """给 AI 主播回复弹幕时的提示词补一段“老观众记忆”（只含允许记的东西，限长）。"""
        if not (self.mem and self.m("memory_in_replies")):
            return ""
        L = []
        for u in dict.fromkeys(x for x in uids if x):
            r = self.mem.get(u)
            if r and r["visits"] >= 2:
                f = S.facts(r)
                L.append(f"- {_nick(r['nick'])}：{f}")
            if len(L) >= 3:
                break
        if not L:
            return ""
        return "【你对这几位老观众的记忆（只在合适时自然带一句，别刻意）】\n" + "\n".join(L)[:400]

    def _forget(self, ev, room, uid, name):
        self.mem.forget(uid=uid, optout=True)
        sy = getattr(self.app, "story", None)
        if sy is not None:
            try:
                sy.forget(uid)                 # 剧情模块里记的口令 / 话也一起清掉
            except Exception as e:  # noqa
                self.log(f"[记忆] 清剧情记录出错：{e!r}")
        self.stats["forgets"] += 1
        nick = _nick(name)
        self.sysline(room, f"【记忆】已忘记 {nick} 的全部记录，之后也不会再记（想让我重新记住就说「记住我」）")
        h = self.host_of(room)
        if h:
            self.in_thread(lambda: h.speak("greet", "", f"好的{nick}，我已经把你忘光啦，以后也不记了", "平静", to=nick, prio=55))
        self.note(f"{nick} 要求忘记")
        return True

    def _remember(self, ev, room, uid, name):
        self.mem.remember(uid)
        self.mem.touch(uid, name, time.time(), self.cfg.i("ai_plus", "memory_session_gap"))
        self.sysline(room, f"【记忆】好的，重新记住 {_nick(name)} 了")
        return True

    def _ask_memory(self, ev, room, uid, name):
        nick = _nick(name)
        rec = self.mem.get(uid)
        h = self.host_of(room)
        if rec and rec["visits"] >= 2:
            f, lv = self._facts(room, uid, rec)
            f = re.sub(r"Lv\.(\d+)\S*", r"\1级", f)                # 念出来的话：不要念星星月亮
            txt = "记得呀" + nick + "，" + f.replace("；", "，")
        elif rec:
            txt = f"{nick}，这是我们第一次见面呢，以后我会记住你的"
        else:
            txt = f"{nick}，我现在不记你的事了（想让我记住就说「记住我」）"
        self.sysline(room, "【记忆】" + txt)
        self.stats["mem_replies"] += 1
        if h:
            self.in_thread(lambda: h.speak("greet", "", txt[:60], "开心", to=nick, prio=55))
        return True

    # ================= 歌曲点评 =================
    def music_state(self):
        pl = getattr(self.app, "play", None)
        if pl is not None and getattr(pl, "test_song", None) is not None:
            return pl.test_song                           # 测试钩子 /play/testsong
        m = getattr(self.app, "music", None)
        return getattr(m, "state", None) or {}

    def lyric_lines(self, key):
        st = self.music_state()
        if st.get("lines"):                                # 测试钩子带的歌词
            return st["lines"]
        m = getattr(self.app, "music", None)
        ly = getattr(m, "lyric", None) or {}
        return (ly.get("lines") or []) if ly.get("key") == key else []

    def song_pos(self, st, now=None):
        pos = float(st.get("pos") or 0)
        if st.get("playing") and st.get("ts"):
            pos += max(0.0, (now or time.time()) - st["ts"] / 1000.0)
        return pos

    def safe_window(self, st, dur, now=None):
        """现在开口会不会盖住歌词：没有歌词 / 前奏里 / 长间奏里 / 歌词已经唱完 = 可以说；唱词中间不说。"""
        lines = self.lyric_lines(st.get("key"))
        pos = self.song_pos(st, now)
        if not lines:
            return True
        first = lines[0][0]
        if pos < first:
            return pos < first - dur - 0.5                      # 前奏：要在第一句唱出来之前说完
        last_end = lines[-1][2] if len(lines[-1]) > 2 else lines[-1][0] + 6
        if pos > last_end + 0.5:
            return True
        for ln in lines:
            t0, t1 = ln[0], (ln[2] if len(ln) > 2 else ln[0] + 6)
            if t0 <= pos < t1:
                # 一句歌词挂了很久（多半是间奏）：唱完 ~4 秒以后、下一句前留够时间才说
                return (t1 - t0) >= 10 and pos >= t0 + 4 and t1 - pos >= dur + 1
        return True

    def song_tick(self, now=None):
        if not self.m("song_comment"):
            return
        now = now or time.time()
        st = self.music_state()
        sg = self.song
        if not st.get("on"):
            sg.update(key="", pending=False)
            return
        key = str(st.get("key") or st.get("title") or "")
        if key != sg["key"]:                                           # 换歌了：决定要不要点评
            sg.update(key=key, t0=now, pending=False, tries=0)
            want = self.song_wanted(st, now)
            sg["want"] = want
            sg["pending"] = want
            return
        if not sg["pending"] or now - sg["t0"] < self.cfg.f("ai_plus", "song_comment_delay"):
            return
        if now - sg["t0"] > self.cfg.f("ai_plus", "song_comment_wait") + self.cfg.f("ai_plus", "song_comment_delay"):
            sg["pending"] = False                                       # 等了这么久都没有合适的空档：这首不说了
            self.note("歌曲点评：一直没有空档，放弃")
            return
        h = self.host_of(None)
        if h is None or now < getattr(h, "busy_until", 0):
            return                                                      # 主播正在说话
        cc = self.cfg.i("ai_plus", "song_comment_chars")
        if not self.safe_window(st, 1.0 + cc * 0.28, now):
            return
        sg["pending"] = False
        self.comment_song(st, now)

    def song_wanted(self, st, now):
        c = self.cfg
        if not st.get("playing", True):
            return False
        if st.get("duration") and st["duration"] < c.f("ai_plus", "song_comment_min_secs"):
            return False
        if now - self.last_song_comment < c.f("ai_plus", "song_comment_gap"):
            return False
        jb = getattr(self.app, "jukebox", None)
        cur = getattr(jb, "current", None) if jb is not None else None
        if cur is not None and getattr(cur, "uid", "") and not c.b("ai_plus", "song_comment_requests"):
            return False                                                # 观众点的歌：主播已经答谢过了，不再点评
        return random.random() < c.f("ai_plus", "song_comment_chance")

    def comment_song(self, st=None, now=None, force=False, who=""):
        """让主播点评当前这首歌。返回 (ok, 说明)。"""
        st = st or self.music_state()
        now = now or time.time()
        if not st.get("on"):
            return False, "现在没有在放歌"
        h = self.host_of(None)
        if h is None:
            return False, "没有 AI 主播在岗"
        self.last_song_comment = now
        self.stats["song_comments"] = self.stats.get("song_comments", 0) + 1
        title, artist = st.get("title", ""), st.get("artist", "")
        self.note(f"点评歌曲《{title}》")
        self.in_thread(self._song_say, h, st, who)
        return True, f"点评《{title}》"

    def _song_say(self, h, st, who=""):
        title, artist, album = st.get("title", "这首歌"), st.get("artist", "歌手"), st.get("album", "")
        cc = self.cfg.i("ai_plus", "song_comment_chars")
        lyric = ""
        lines = self.lyric_lines(st.get("key"))
        if lines:
            lyric = "；".join(x[1] for x in lines[:3])[:60]
        fb = random.choice([f"这首《{title}》真好听，{artist}的歌总能让人安静下来",
                            f"《{title}》，{artist}唱的，适合边听边发呆",
                            f"听到{artist}的《{title}》，感觉心情都变好了"])
        prompt = None
        if self.cfg.b("ai_plus", "song_comment_llm"):
            prompt = (f"【歌曲点评】直播间正在放《{title}》，歌手：{artist}" + (f"，专辑《{album}》" if album else "") + "。"
                      + (f"歌词开头几句（只用来感受情绪，别照着念）：{lyric}。" if lyric else "")
                      + f"请你用口吻点评这首歌：可以说一个关于{artist}或这首歌的小知识，但只能说你有把握的事实，没把握就聊歌曲的情绪和听感，绝不要编造；"
                        f"不要念歌词，不要报一串数据，{cc}个字以内，口语，像边听边随口说的一句。" + (f"（是观众「{who}」让你点评的）" if who else ""))
        h.speak("songc", prompt, fb, "开心", prio=25, wait=8.0, max_chars=cc)

    # ---- agent 后端动作 ----
    def agent_action(self, a, ev, room, user):
        """registry 里的后端动作：song_comment / screen_comment / game_start / game_stop。返回 (ok, 说明)。"""
        n = a.get("action")
        now = time.time()
        if n == "song_comment":
            if not self.m("song_comment"):
                return False, "歌曲点评没开（[ai_plus] song_comment）"
            if now - self.cmd_at.get(n, 0) < 20:
                return False, "刚评论过，歇一会儿"
            self.cmd_at[n] = now
            return self.comment_song(force=True, who=user)
        if n == "screen_comment":
            if not self.m("screen"):
                return False, "画面点评没开（[ai_plus] screen）"
            if now - self.cmd_at.get(n, 0) < 20:
                return False, "刚评论过，歇一会儿"
            if self.scr["busy"]:
                return False, "正在看屏幕呢"
            ok, msg = self.screen_ready(True)
            if not ok:
                return False, msg
            self.cmd_at[n] = now
            self.scr["busy"] = True
            self._spawn(self.screen_comment(force=True, who=user))
            return True, "看一眼屏幕"
        if n == "game_start":
            ok, msg = self.games.start(a.get("game") or "", room, user)
            return ok, msg
        if n == "game_stop":
            g = self.games.cur
            if g is not None and g["state"] != "done" and user and not (self.games.is_host_user(user, room) or user == g["by"]):
                return False, "只有开局的人或主播能结束游戏"
            return self.games.stop(room, user)
        return False, f"未知动作 {n}"

    # ---- 闲时活动用 ----
    def idle_game_list(self):
        ok = [x for x in re.split(r"[,，\s|]+", self.cfg.s("ai_plus", "game_idle_list")) if x in ("idiom", "song", "riddle")]
        if "song" in ok and not self.games.songs:
            ok.remove("song")
        return ok or ["riddle"]

    def idle_game_ok(self):
        c = self.cfg
        if not (self.m("game") and c.b("ai_plus", "game_idle")) or (self.games.cur is not None and self.games.cur["state"] != "done"):
            return False
        if time.time() - self.games.last_end < c.f("ai_plus", "game_cooldown"):
            return False
        pl = getattr(self.app, "play", None)
        try:
            viewers = pl.idle_scope()[1] if pl is not None else 0
        except Exception:
            viewers = 0
        return viewers >= max(0, c.i("ai_plus", "game_idle_min_viewers"))

    # ================= 画面点评 =================
    def _spawn(self, coro):
        try:
            asyncio.ensure_future(coro)
        except Exception as e:  # noqa
            self.scr["busy"] = False
            self.log(f"[画面点评] 启动失败：{e!r}")

    def vision_failed(self, e):
        self.vis_fail += 1
        if self.vis_fail >= 3:
            self.vis_off_until = time.time() + 1800
            self.vis_fail = 0
            self.log("[画面点评] 视觉模型连续失败，30 分钟内只用文字快照")
            self.note("视觉模型不可用 → 文字快照")

    def vision_ok(self):
        self.vis_fail = 0

    def vision_on(self):
        m = self.cfg.s("ai_plus", "screen_vision").lower()
        if m in ("off", "false", "0", "no", "") or not self.cfg.ai_enabled:
            return False
        return time.time() >= self.vis_off_until            # on / auto：都试；连续失败会自动停一阵

    def vision_result(self, d):
        fut = self.vis_wait.pop(d.get("id"), None)
        if fut is not None and not fut.done():
            fut.set_result(d.get("img") or "")

    async def vision_req(self, timeout=None):
        """让页面截一张桌面图（base64 JPEG data URL）。拿不到就返回 ''。"""
        ag = getattr(self.app, "agent", None)
        ws = getattr(ag, "snap_ws", None)
        if ws is None:
            return ""
        self.vis_seq += 1
        i = f"v{self.vis_seq}"
        fut = asyncio.get_running_loop().create_future()
        self.vis_wait[i] = fut
        try:
            await ws.send_str(json.dumps({"t": "vision_req", "id": i, "w": 768}))
            return await asyncio.wait_for(fut, timeout or self.cfg.f("ai_plus", "screen_vision_timeout") * 0.4)
        except Exception as e:  # noqa
            self.log(f"[画面点评] 截图没拿到：{e!r}")
            return ""
        finally:
            self.vis_wait.pop(i, None)

    def screen_desc(self, desk):
        """把桌面快照写成给 LLM 看的人话（不带窗口 id）。返回 (文字, 指纹 dict)。"""
        s = desk.s
        wins = [w for w in desk.wins if w.get("id") not in ("qqchat",) and w.get("state") != "min"]
        mins = [w for w in desk.wins if w.get("state") == "min" and w.get("id") not in ("qqchat",)]
        names = lambda ws: "、".join(dict.fromkeys(desk.label(w) for w in ws if desk.label(w)))   # noqa
        ai = s.get("ai") or {}
        m = s.get("music") or {}
        act = next((w for w in wins if w.get("active")), None)
        L = []
        L.append("屏幕上打开着：" + (names(wins) or "只有 QQ 群聊窗口，桌面比较空") + (f"（最前面：{desk.label(act)}）" if act else ""))
        if mins:
            L.append("最小化在任务栏里：" + names(mins))
        if m.get("on"):
            L.append(f"正在放歌：{m.get('artist', '')} - {m.get('title', '')}" + ("" if m.get("playing") else "（暂停中）"))
        if ai.get("game"):
            g = ai["game"]
            L.append(f"正在和观众玩「{g.get('name')}」小游戏，现在的题目/题面：{g.get('prompt')}")
        if ai.get("vote"):
            L.append(f"正在进行弹幕投票：{ai['vote'].get('title')}")
        if ai.get("fx"):
            nm = {"fireworks": "烟花", "meteor": "流星雨", "emoji": "表情雨", "virus": "“中毒”熊猫烧香"}
            L.append("屏幕上正在放特效：" + "、".join(nm.get(x, x) for x in ai["fx"]))
        if ai.get("bsod") or any("蓝屏" in (w.get("title") or "") for w in wins):
            L.append("刚刚出现了蓝屏彩蛋")
        if s.get("dialogs"):
            L.append("弹出的对话框：" + "、".join(s["dialogs"][:3]))
        if s.get("wall"):
            L.append("壁纸：" + str(s["wall"]))
        fp = {"apps": frozenset(w.get("id") for w in wins), "mins": frozenset(w.get("id") for w in mins), "song": m.get("title") if m.get("on") else "",
              "fx": frozenset(ai.get("fx") or []), "game": (ai.get("game") or {}).get("name", ""), "vote": bool(ai.get("vote")), "bsod": bool(ai.get("bsod")), "wall": s.get("wall")}
        return "\n".join(L), fp, {w.get("id"): desk.label(w) for w in wins}

    def screen_changes(self, old, new, labels):
        """两次指纹的差别 → 人话列表（只取有“事件感”的变化）。"""
        out = []
        if old is None:
            return out
        for i in new["apps"] - old["apps"]:
            out.append(f"刚打开了「{labels.get(i, i)}」")
        if new["fx"] - old["fx"]:
            out.append("刚放了特效")
        if new["game"] and new["game"] != old["game"]:
            out.append(f"刚开了「{new['game']}」游戏")
        if new["vote"] and not old["vote"]:
            out.append("刚发起了投票")
        if new["bsod"] and not old["bsod"]:
            out.append("刚出现蓝屏彩蛋")
        if new["song"] and new["song"] != old["song"]:
            out.append(f"刚换歌到《{new['song']}》")
        if new["wall"] != old["wall"] and old["wall"] is not None:
            out.append("刚换了壁纸")
        return out

    def screen_ready(self, force=False):
        """页面在线、有快照、主播空闲？（force=观众/AI 明确要点评时，放宽“冷场”类条件，但页面必须在。）"""
        ag = getattr(self.app, "agent", None)
        if ag is None or getattr(ag, "snap_ws", None) is None:
            return False, "没有页面在线（看不到屏幕）"
        c = ag.clients.get(ag.snap_ws) or {}
        if not c.get("snap") or time.time() - c.get("at", 0) > 120:
            return False, "桌面状态太久没更新"
        h = self.host_of(None)
        if h is None:
            return False, "没有 AI 主播在岗"
        return True, ""

    def screen_tick(self, now=None):
        now = now or time.time()
        if not self.m("screen") or self.scr["busy"]:
            return
        ok, _ = self.screen_ready()
        if not ok:
            self.scr["fp"] = None
            return
        ag = self.app.agent
        text, fp, labels = self.screen_desc(ag.desk())
        ch = self.screen_changes(self.scr["fp"], fp, labels)
        self.scr["fp"] = fp
        if ch:
            if not self.scr["changes"]:
                self.scr["since"] = now
            self.scr["changes"] = (self.scr["changes"] + [c for c in ch if c not in self.scr["changes"]])[-4:]
        c = self.cfg
        if now - self.scr["last"] < c.f("ai_plus", "screen_min_gap"):
            return
        h = self.host_of(None)
        if now < getattr(h, "busy_until", 0) or now - self.last_chat < c.f("ai_plus", "screen_quiet_secs"):
            return
        idle = getattr(ag, "idle", None)
        if idle is not None and getattr(idle, "cur", None):
            return                                                       # 自己在玩电脑（idle）：动作自带台词，别插嘴
        if self.games.cur is not None and self.games.cur["state"] != "done":
            return                                                       # 游戏中：别打断出题
        pl = getattr(self.app, "play", None)
        if pl is not None and getattr(pl, "vote", None) is not None and getattr(pl.vote, "state", "") == "open":
            return
        if self.song.get("pending"):
            return
        due_ev = c.b("ai_plus", "screen_events") and self.scr["changes"] and now - self.scr["since"] >= 3
        due_iv = now - self.scr["last"] >= c.f("ai_plus", "screen_interval")
        if due_ev or due_iv:
            self.scr["busy"] = True
            self._spawn(self.screen_comment(reason="；".join(self.scr["changes"]) if due_ev else ""))

    async def screen_comment(self, force=False, who="", reason=""):
        try:
            ag = self.app.agent
            text, fp, labels = self.screen_desc(ag.desk())
            self.scr["fp"] = fp
            self.scr["changes"] = []
            self.scr["last"] = time.time()
            h = self.host_of(None)
            if h is None:
                return
            img = ""
            if self.vision_on():
                img = await self.vision_req()
            self.stats["screen_comments"] = self.stats.get("screen_comments", 0) + 1
            self.scr["vision"] = bool(img)
            self.scr["last_text"] = text
            self.note("点评屏幕" + ("（带截图）" if img else "（文字快照）") + (f"：{reason}" if reason else ""))
            self.in_thread(self._screen_say, h, text, img, reason, who)
        except Exception as e:  # noqa
            self.log(f"[画面点评] 出错：{e!r}")
        finally:
            self.scr["busy"] = False

    def _screen_say(self, h, text, img, reason, who):
        cc = self.cfg.i("ai_plus", "screen_chars")
        base = (f"【画面点评】你正在直播，你自己的 XP 桌面现在是这样的：\n{text}\n" + (f"刚刚发生的变化：{reason}。\n" if reason else "") + (f"（观众「{who}」让你点评一下屏幕）\n" if who else ""))
        rule = (f"请像边玩边随口吐槽的主播，只就屏幕上看得见的事说一句，{cc}个字以内，口语，有点俏皮；"
                "不要说“桌面快照/截图/文字描述”这类词，不要念聊天窗口里的原话，不要编造上面没有的内容。")
        alt = base + rule
        prompt = (base + "下面还附了一张桌面的实际截图，以截图为准、文字只作参考。" + rule) if img else alt
        names = [x for x in text.split("\n")[0].replace("屏幕上打开着：", "").split("（")[0].split("、") if x][:2]
        fb = random.choice([f"我这桌面开着{'、'.join(names)}，还挺热闹的" if names else "我这桌面挺干净的，要不要整点活？", "大家看我桌面，今天也是认真摸鱼的一天", "屏幕上的东西越来越多了，我得收拾一下"])
        h.speak("screen", prompt, fb, "开心", prio=25, wait=8.0, max_chars=cc, image=img, alt_prompt=alt,
                vmodel=self.cfg.s("ai_plus", "screen_vision_model"), vtimeout=self.cfg.f("ai_plus", "screen_vision_timeout"))

    # ---- 查看 / 调试 ----
    def state(self):
        return {"enabled": self.on(), "memory": self.mem.stats() if self.mem else None, "stats": self.stats, "song": {k: v for k, v in self.song.items()}, "game": self.games.snapshot(), "games_recent": self.games.hist[-5:], "screen": {"last": int(self.scr["last"]), "busy": self.scr["busy"], "vision": self.scr["vision"], "vision_off_for": max(0, int(self.vis_off_until - time.time())), "text": self.scr["last_text"], "pending": self.scr["changes"]}, "recent": self.recent[-10:]}


def _nick(name):
    from host.engine import nick
    return nick(name)


def greet_template(nick, before, lv=0):
    songs, gifts, topics = before.get("songs") or [], before.get("gifts") or {}, before.get("topics") or []
    if songs:
        t = f"{nick}你又来啦，上次你点了《{songs[-1]}》，今天还听吗？"
    elif gifts:
        g = max(gifts, key=gifts.get)
        t = f"{nick}欢迎回来，上次你送我的{g}我还记着呢"
    elif topics:
        t = f"{nick}又见面啦，上次你说「{topics[-1][:14]}」，后来怎么样了？"
    else:
        t = f"{nick}你又来啦，欢迎老朋友回家"
    if lv >= 4:
        t += f"，都Lv.{lv}啦"
    return t
