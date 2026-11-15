# -*- coding: utf-8 -*-
"""直播间小游戏：成语接龙 / 猜歌名 / 脑筋急转弯。一次只有一场，服务端判分，积分走 [play] 的积分（award_bonus）。

数据：
  data/idioms.tsv   四字成语 + 拼音（开源数据集 pwxcoo/chinese-xinhua，MIT，见 data/IDIOM_LICENSE.txt）；[ai_plus] idiom_file 可换成自己的（词<TAB>拼音）
  data/songs.tsv    猜歌名题库（歌名 / 歌手 / 提示，原创描述，不含歌词）；也可以直接用「正在播放那首歌的当前歌词」当题（song_game_source）
  data/riddles.tsv  脑筋急转弯题库（原创整理）
开始：弹幕口令（agent 规则）/ 投票选项 / 冷场自己发起 / agent 动作 game_start；结束：时间到、轮数到、没人接、或 game_stop。
"""
import random
import re
import time
import unicodedata
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
ROOT = DATA.parent.parent.parent
NAMES = {"idiom": "成语接龙", "song": "猜歌名", "riddle": "脑筋急转弯"}
ALIAS = {"idiom": "idiom", "成语接龙": "idiom", "接龙": "idiom", "成语": "idiom", "song": "song", "猜歌名": "song", "猜歌": "song", "歌名": "song",
         "riddle": "riddle", "脑筋急转弯": "riddle", "急转弯": "riddle", "谜语": "riddle"}
HAN = re.compile(r"[^\u4e00-\u9fff]")
SKIP_WORDS = ("跳过", "下一题", "换一题", "不会", "放弃")
HINT_WORDS = ("提示", "提示一下", "给点提示", "hint")


def toneless(syl):
    s = unicodedata.normalize("NFD", syl.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("ü", "u").replace("v", "u")


def norm(s):
    return re.sub(r"[\s\W_]+", "", str(s or ""), flags=re.U).lower()


def _path(f, default):
    if not f:
        return default
    p = Path(f)
    return p if p.is_absolute() else ROOT / f


def load_idioms(path):
    words, by_first = {}, {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        bits = line.split("\t")
        if len(bits) < 2 or not re.fullmatch(r"[\u4e00-\u9fff]{4}", bits[0]):
            continue
        syl = [toneless(x) for x in bits[1].split()]
        if len(syl) != 4:
            continue
        words[bits[0]] = syl
        by_first.setdefault(syl[0], []).append(bits[0])
    return words, by_first


def load_tsv(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        rows.append(line.split("\t"))
    return rows


class Games:
    def __init__(self, plus):
        self.p, self.cfg, self.log = plus, plus.cfg, plus.log
        self.cur = None
        self.seq = 0
        self.last_end = 0.0
        self.hist = []
        self._idioms = self._riddles = self._songs = None

    # ------------------------------------------------------------ 数据（用到才读）
    @property
    def idioms(self):
        if self._idioms is None:
            self._idioms = load_idioms(_path(self.cfg.s("ai_plus", "idiom_file"), DATA / "idioms.tsv"))
        return self._idioms

    @property
    def riddles(self):
        if self._riddles is None:
            self._riddles = [{"q": r[0], "a": [x.strip() for x in r[1].split("|") if x.strip()], "hint": (r[2] if len(r) > 2 else "")}
                             for r in load_tsv(_path(self.cfg.s("ai_plus", "riddle_file"), DATA / "riddles.tsv")) if len(r) >= 2]
        return self._riddles

    @property
    def songs(self):
        if self._songs is None:
            self._songs = []
            for r in load_tsv(_path(self.cfg.s("ai_plus", "song_game_file"), DATA / "songs.tsv")):
                if len(r) >= 3:
                    names = [x.strip() for x in r[0].split("/") if x.strip()]
                    self._songs.append({"title": names[0], "alias": names, "artist": r[1], "hints": [x.strip() for x in r[2].split("|") if x.strip()]})
        return self._songs

    # ------------------------------------------------------------ 开关 / 小工具
    def on(self):
        return self.p.m("game")

    def anchor_of(self, room):
        a = ((getattr(room, "last", None) or {}).get("room") or {}).get("anchor")
        return a or ""

    def is_host_user(self, name, room):
        return bool(name) and (name == self.cfg.s("host", "name") or name == self.anchor_of(room) or name in ("猪猪侠", "测试"))

    def say(self, room, text, emo="开心"):
        if not self.cfg.b("ai_plus", "game_say"):
            return
        ag = getattr(self.p.app, "agent", None)
        try:
            if ag is not None:
                ag.say(room, text[:100], emo, "game")
        except Exception as e:  # noqa
            self.log(f"[游戏] 说话失败：{e!r}")

    def sys(self, room, text):
        self.p.sysline(room, text)

    def award(self, room, uid, name, pts):
        pl = getattr(self.p.app, "play", None)
        if pl is None or pts <= 0:
            return 0
        try:
            return pl.award_bonus(room, uid, name, pts)
        except Exception as e:  # noqa
            self.log(f"[游戏] 加分失败：{e!r}")
            return 0

    # ------------------------------------------------------------ 开始 / 结束
    def start(self, kind, room, by="", force=False):
        """-> (ok, 说明)"""
        kind = ALIAS.get(str(kind or "").strip().lower(), "")
        if not self.on():
            return False, "小游戏没开（[ai_plus] game）"
        if not kind:
            return False, "不认识的游戏（成语接龙 / 猜歌名 / 脑筋急转弯）"
        if self.cur is not None and self.cur["state"] != "done":
            return False, f"已经有一场「{self.cur['name']}」在进行了"
        now = time.time()
        if not force and now - self.last_end < self.cfg.f("ai_plus", "game_cooldown"):
            return False, "刚玩完，歇一会儿再来"
        if not force and self.cfg.s("ai_plus", "game_who") == "anchor" and not self.is_host_user(by, room):
            return False, "只有群主 / 主播能开游戏"
        self.seq += 1
        g = {"id": self.seq, "kind": kind, "name": NAMES[kind], "room": room, "by": by, "state": "open", "round": 0, "rounds": 0, "scores": {}, "log": [],
             "used": [], "t0": now, "secs": self.cfg.i("ai_plus", "game_timeout"), "deadline": 0, "hinted": False, "prompt": "", "sub": "", "hint": "", "winner": "", "note": "", "next_at": 0,
             "hint_at": 0}
        self.cur = g
        try:
            {"idiom": self._start_idiom, "song": self._start_quiz, "riddle": self._start_quiz}[kind](g, now)
        except Exception as e:  # noqa
            self.cur = None
            self.log(f"[游戏] 开局失败：{e!r}")
            return False, f"开局失败：{e}"
        self.p.note(f"开始游戏 {g['name']}（{by or '系统'}）")
        self.p.stats["games"] = self.p.stats.get("games", 0) + 1
        return True, f"开始了「{g['name']}」"

    def stop(self, room=None, by="", why="结束"):
        g = self.cur
        if g is None or g["state"] == "done":
            return False, "现在没有在进行的游戏"
        self._finish(g, why=f"{by or '主播'}叫停了游戏" if why == "结束" else why, announce=True)
        return True, "游戏结束了"

    # ------------------------------------------------------------ 成语接龙
    def _start_idiom(self, g, now):
        words, by_first = self.idioms
        g["rounds"] = max(1, self.cfg.i("ai_plus", "idiom_rounds"))
        pool = [w for w, s in words.items() if len(by_first.get(s[-1], [])) >= 6]
        w = random.choice(pool or list(words))
        g["used"] = [w]
        self._idiom_prompt(g, w, now)
        self.say(g["room"], f"成语接龙开始啦！我先来：{w}。请接「{w[-1]}」字开头的成语，读音相同也算！", "兴奋")
        self.sys(g["room"], f"【成语接龙】开始！我先来：{w}。请接「{w[-1]}」字（同音也行），{g['secs']} 秒内接上；接对 +{self.cfg.i('ai_plus', 'game_points')} 分")
        self._push(g)

    def _idiom_prompt(self, g, w, now):
        words, _ = self.idioms
        g["prompt"], g["need"] = w, words[w][-1]
        g["sub"] = f"请接「{w[-1]}」字开头的成语（读音相同也行）"
        g["deadline"] = now + g["secs"]
        g["hint"] = ""

    def _idiom_answer(self, g, ev, uid, name, text, now):
        """返回 True = 这句话是接龙答案（被游戏吃掉）。"""
        words, by_first = self.idioms
        w = HAN.sub("", text)
        if len(w) != 4 or w not in words or len(text) > 12:
            return False
        syl = words[w]
        homo = self.cfg.b("ai_plus", "idiom_homophone")
        ok = syl[0] == g["need"] if homo else w[0] == g["prompt"][-1]
        if w in g["used"]:
            self._note_bad(g, f"「{w}」已经用过啦")
            return True
        if not ok:
            self._note_bad(g, f"「{w}」接不上：要以「{g['prompt'][-1]}」（{g['need']}）开头")
            return True
        g["used"].append(w)
        got = self.award(g["room"], uid, name, self.cfg.i("ai_plus", "game_points"))
        sc = g["scores"].setdefault(uid, [name, 0, 0])
        sc[0], sc[1], sc[2] = name, sc[1] + got, sc[2] + 1
        g["round"] += 1
        g["log"].append({"name": name, "text": w, "ok": True})
        g["last_uid"] = uid
        self.sys(g["room"], f"【成语接龙】{name} 接上了「{w}」" + (f" +{got}分" if got else ""))
        if g["round"] >= g["rounds"]:
            self._idiom_prompt(g, w, now)
            self._finish(g, why=f"接满 {g['rounds']} 个啦", announce=True)
            return True
        if self.cfg.b("ai_plus", "idiom_host_plays"):
            nxt = self._host_idiom(g, syl[-1])
            if nxt is None:
                self._idiom_prompt(g, w, now)
                self._finish(g, why="我接不上了，你们赢啦", announce=True, host_lost=True)
                return True
            g["used"].append(nxt)
            g["log"].append({"name": self.cfg.s("host", "name"), "text": nxt, "ok": True})
            self._idiom_prompt(g, nxt, now)
            self.say(g["room"], f"{name}接得好！我接：{nxt}。接「{nxt[-1]}」！", "得意")
            self.sys(g["room"], f"【成语接龙】{self.cfg.s('host', 'name')} 接：{nxt}　下一个请接「{nxt[-1]}」")
        else:
            self._idiom_prompt(g, w, now)
            self.say(g["room"], f"{name}接对了！下一个接「{w[-1]}」", "开心")
        self._push(g)
        return True

    def _note_bad(self, g, text):
        now = time.time()
        if now - g.get("bad_at", 0) > 2:                  # 别被刷屏
            g["bad_at"] = now
            self.sys(g["room"], f"【成语接龙】{text}")

    def _host_idiom(self, g, syl):
        words, by_first = self.idioms
        cands = [x for x in by_first.get(syl, []) if x not in g["used"]]
        good = [x for x in cands if any(y not in g["used"] for y in by_first.get(words[x][-1], []))]
        pick = good or cands
        return random.choice(pick) if pick else None

    def _idiom_timeout(self, g, now):
        words, by_first = self.idioms
        nxt = self._host_idiom(g, g["need"])
        self._finish(g, why=f"时间到，没人接上！我来揭晓：{nxt}" if nxt else "时间到，没人接上", announce=True)

    # ------------------------------------------------------------ 猜歌名 / 脑筋急转弯
    def _start_quiz(self, g, now):
        g["rounds"] = max(1, self.cfg.i("ai_plus", "song_game_rounds" if g["kind"] == "song" else "riddle_rounds"))
        self._quiz_next(g, now, first=True)

    def _song_questions(self, g):
        """挑一道猜歌名：来源 list / current / both。"""
        src = self.cfg.s("ai_plus", "song_game_source").lower()
        cur = self.p.music_state()
        lines = self.p.lyric_lines(cur.get("key")) if (cur.get("key") and cur.get("title")) else []
        use_cur = src in ("current", "both") and lines and (src == "current" or random.random() < 0.4)
        if use_cur:
            cand = [x for x in lines if 5 <= len(re.sub(r"\s", "", x[1])) <= 24] or lines
            ln = random.choice(cand)
            title = cur.get("title", "")
            if title:
                return {"q": f"这句歌词来自哪首歌？「{ln[1]}」", "answers": [title], "title": title, "artist": cur.get("artist", ""),
                        "hints": [f"歌手是 {cur.get('artist', '')}" if cur.get("artist") else "仔细听听现在放的歌", f"歌名共 {len(norm(title))} 个字，第一个字是「{norm(title)[:1]}」"]}
        pool = [s for s in self.songs if s["title"] not in g.get("asked", [])] or self.songs
        s = random.choice(pool)
        return {"q": s["hints"][0] if s["hints"] else "猜猜这是哪首歌", "answers": s["alias"], "title": s["title"], "artist": s["artist"],
                "hints": (s["hints"][1:2] or []) + [f"歌手是 {s['artist']}，歌名共 {len(norm(s['title']))} 个字，第一个字是「{norm(s['title'])[:1]}」"]}

    def _quiz_next(self, g, now, first=False):
        if g["kind"] == "song":
            q = self._song_questions(g)
            g.setdefault("asked", []).append(q["title"])
        else:
            pool = [r for r in self.riddles if r["q"] not in g.get("asked", [])] or self.riddles
            r = random.choice(pool)
            g.setdefault("asked", []).append(r["q"])
            a0 = norm(r["a"][0])
            q = {"q": r["q"], "answers": r["a"], "title": r["a"][0], "artist": "",
                 "hints": [r["hint"]] if r["hint"] else [], "last": f"答案共 {len(a0)} 个字，第一个字是「{a0[:1]}」"}
            q["hints"] = q["hints"] + [q["last"]]
        g["qa"], g["round"], g["state"] = q, g["round"] + 1, "open"
        g["hint_i"] = 0
        g["deadline"] = now + g["secs"]
        g["hint_at"] = now + g["secs"] * 0.5
        g["prompt"], g["hint"] = q["q"], ""
        g["sub"] = f"第 {g['round']} / {g['rounds']} 题　{g['secs']} 秒内在群里发答案" + ("" if g["kind"] == "riddle" else "（可以发「提示」）")
        spoken = (f"第{g['round']}题，" if g["rounds"] > 1 else "") + ("猜歌名！" if g["kind"] == "song" else "脑筋急转弯：") + q["q"].replace("「", "").replace("」", "")
        self.say(g["room"], spoken, "兴奋" if first else "开心")
        self.sys(g["room"], f"【{g['name']}】第 {g['round']}/{g['rounds']} 题：{q['q']}")
        self._push(g)

    def _match(self, guess, answers):
        gn = norm(guess)
        if not gn:
            return False
        for a in answers:
            an = norm(a)
            if not an:
                continue
            if gn == an:
                return True
            if len(an) >= 2 and an in gn and len(gn) <= len(an) + 5:
                return True
        return False

    def _quiz_answer(self, g, ev, uid, name, text, now):
        q = g["qa"]
        if g["state"] != "open" or len(text) > 24:
            return False
        if not self._match(text, q["answers"]):
            if g["kind"] == "idiom":
                return False
            g["log"].append({"name": name, "text": text[:16], "ok": False})
            del g["log"][:-6]
            self._push(g)
            return True                                   # 猜错的也算游戏聊天：不让 AI 主播当普通聊天去回
        got = self.award(g["room"], uid, name, self.cfg.i("ai_plus", "game_points") * (2 if g["kind"] == "song" else 1))
        sc = g["scores"].setdefault(uid, [name, 0, 0])
        sc[0], sc[1], sc[2] = name, sc[1] + got, sc[2] + 1
        g["log"].append({"name": name, "text": text[:16], "ok": True})
        ans = q["title"] + (f" - {q['artist']}" if q.get("artist") and g["kind"] == "song" else "")
        g["state"], g["next_at"], g["reveal"] = "gap", now + 3.5, ans
        g["sub"] = f"{name} 答对了！答案：{ans}"
        self.say(g["room"], f"{name}答对了！答案是{q['title']}" + (f"，{q['artist']}的歌" if g["kind"] == "song" and q.get("artist") else ""), "开心")
        self.sys(g["room"], f"【{g['name']}】{name} 答对了：{ans}" + (f" +{got}分" if got else ""))
        self._push(g)
        return True

    def _quiz_hint(self, g, now, by=""):
        q = g["qa"]
        i = g.get("hint_i", 0)
        if g["state"] != "open" or i >= len(q["hints"]):
            return False
        h = q["hints"][i]
        g["hint_i"], g["hint"] = i + 1, h
        g["hint_at"] = now + g["secs"] * 0.5 if i + 1 < len(q["hints"]) else 0
        self.say(g["room"], "给点提示：" + h.replace("「", "").replace("」", ""), "平静")
        self.sys(g["room"], f"【{g['name']}】提示：{h}")
        self._push(g)
        return True

    def _quiz_timeout(self, g, now):
        q = g["qa"]
        ans = q["title"] + (f" - {q['artist']}" if q.get("artist") and g["kind"] == "song" else "")
        g["state"], g["next_at"], g["reveal"] = "gap", now + 3.5, ans
        g["sub"] = f"时间到，没人答对。答案：{ans}"
        self.say(g["room"], f"时间到！没人答对，答案是{q['title']}", "难过")
        self.sys(g["room"], f"【{g['name']}】时间到，答案：{ans}")
        self._push(g)

    # ------------------------------------------------------------ 结束 / 推送
    def _finish(self, g, why="", announce=True, host_lost=False):
        if g["state"] == "done":
            return
        g["state"] = "done"
        self.last_end = time.time()
        board = sorted(g["scores"].values(), key=lambda x: (-x[1], -x[2]))
        win = ""
        if board and board[0][1] > 0 or (g["kind"] == "idiom" and host_lost and g.get("last_uid")):
            if g["kind"] == "idiom" and host_lost and g.get("last_uid"):
                uid = g["last_uid"]
                win = g["scores"][uid][0]
            else:
                uid = next(u for u, v in g["scores"].items() if v is board[0])
                win = board[0][0]
            bonus = self.award(g["room"], uid, win, self.cfg.i("ai_plus", "game_win_points"))
            g["winner"], g["bonus"] = win, bonus
        g["note"] = why
        g["sub"] = why + (f"　🏆 {win}" if win else "")
        tail = f"本场冠军 {win}，奖励 {g.get('bonus', 0)} 分！" if win else "这局没人得分，下次再来～"
        if announce:
            self.say(g["room"], f"{why}。{tail}", "开心" if win else "平静")
            top = "、".join(f"{x[0]} {x[1]}分" for x in board[:3])
            self.sys(g["room"], f"【{g['name']}】结束：{why}。" + (f"得分榜：{top}。冠军 {win} 另奖 {g.get('bonus', 0)} 分" if win else "没有人得分"))
        self.hist.append({"kind": g["kind"], "by": g["by"], "winner": win, "rounds": g["round"], "at": int(time.time())})
        del self.hist[:-10]
        self._push(g)

    def snapshot(self, g=None):
        g = g or self.cur
        if g is None:
            return None
        now = time.time()
        left = max(0.0, g["deadline"] - now) if g["state"] == "open" else 0.0
        board = sorted(g["scores"].values(), key=lambda x: (-x[1], -x[2]))[:5]
        return {"id": g["id"], "kind": g["kind"], "name": g["name"], "state": g["state"], "round": g["round"], "rounds": g["rounds"], "prompt": g["prompt"], "sub": g["sub"],
                "hint": g.get("hint", ""), "left": round(left, 1), "secs": g["secs"], "by": g["by"], "winner": g.get("winner", ""), "note": g.get("note", ""),
                "board": [{"name": x[0], "pts": x[1], "n": x[2]} for x in board], "log": g["log"][-5:], "reveal": g.get("reveal", "")}

    def _push(self, g):
        room = g["room"]
        if room is not None:
            room._broadcast({"t": "play", "k": "game", "game": self.snapshot(g)})

    # ------------------------------------------------------------ 事件 / 定时
    def on_chat(self, ev, room, uid, name, now=None):
        g = self.cur
        if g is None or g["state"] == "done" or not self.on():
            return False
        now = now or time.time()
        text = (ev.get("text") or "").strip()
        if not text or (g["room"] is not None and room is not None and room is not g["room"]):
            return False
        t = re.sub(r"\s+", "", text)
        if t in HINT_WORDS and g["kind"] != "idiom":
            if now - g.get("hint_cmd", 0) > 8:
                g["hint_cmd"] = now
                self._quiz_hint(g, now, name)
            return True
        if t in SKIP_WORDS and self.is_host_user(name, room):
            if g["kind"] == "idiom":
                self._idiom_timeout(g, now)
            else:
                self._quiz_timeout(g, now)
            return True
        if g["kind"] == "idiom":
            return self._idiom_answer(g, ev, uid, name, t, now)
        return self._quiz_answer(g, ev, uid, name, t, now)

    def tick(self, now=None):
        g = self.cur
        if g is None:
            return
        now = now or time.time()
        if g["state"] == "done":
            if now - self.last_end > 120:
                self.cur = None
            return
        if g["state"] == "open":
            if g["kind"] != "idiom" and g.get("hint_at") and now >= g["hint_at"] and g.get("hint_i", 0) < len(g["qa"]["hints"]):
                self._quiz_hint(g, now)
            if now >= g["deadline"]:
                (self._idiom_timeout if g["kind"] == "idiom" else self._quiz_timeout)(g, now)
        elif g["state"] == "gap" and now >= g["next_at"]:
            if g["round"] >= g["rounds"]:
                self._finish(g, why=f"{g['rounds']} 题全部结束", announce=True)
            else:
                self._quiz_next(g, now)
