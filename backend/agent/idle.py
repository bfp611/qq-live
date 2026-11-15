# -*- coding: utf-8 -*-
"""冷场时猪猪侠“自己玩电脑”：没人说话够久了，就随机挑一件事（逛 IE、扫雷、点开酷狗评论当前的歌、记事本写日记、
QQ 私聊好友、看游戏菜单、整理图标、换壁纸、算个数…），用 agent 的动作系统 + 光标在 XP 桌面上演一遍，一边用 TTS 说几句短旁白。

设计要点
  - 一次活动 = 几个“节拍”（beat）：每个节拍 = 一句旁白 + 一批动作，页面做完一批再发下一批，所以随时能停。
  - 旁白由大模型根据 桌面快照 + 当前歌曲 + 人设 生成（一次调用，JSON），失败/超时用模板兜底。
  - 观众一开口（弹幕）/ 来了指令，立刻 agent_abort：页面丢掉排队的任务、打断当前动作、不带动画地把它打开的窗口收拾掉。
  - 和别的东西共存：群聊窗口受 agent 的保护；音乐永远不动（除非 allow_music_control 且活动用到）；点歌队列忙时不开工；
    主播正在说话时不抢话；每次旁白都推迟主播自己的“冷场暖场”（host.last["idle"]），避免两边同时开口。
"""
import asyncio
import json
import random
import re
import time
from collections import deque

import requests

from . import llm as L
from . import registry as R

SITES_FALLBACK = ["www.hao123.com", "www.baidu.com", "www.sina.com.cn", "www.163.com"]
GAMES = ["cs", "ra2", "war3", "vc", "mir2", "audition"]
NOTE_PREFIX_RE = re.compile(r"[\[\]（）()*_`#>]|https?://|www\.|\.com|微信|加我|私信")


# ---------------------------------------------------------------- 模板旁白（LLM 失败时兜底；{x} 会被替换）
T = {
    "browse_ie": {
        "intro": ["没人聊天，我去冲会儿浪~", "冷场啦，我上网逛逛先", "趁大家不说话，我开个浏览器看看"],
        "mid": ["{site}还是老样子嘛", "这网页打开好慢，宽带不行啊", "哇这个页面好花哨，十年前的审美"],
    },
    "play_minesweeper": {
        "intro": ["闲着也是闲着，我来扫两把雷", "没人理我，那我玩扫雷咯", "来来来，扫雷时间"],
        "mid": ["这格肯定是雷，我插旗", "稳住，别手抖", "数字告诉我这边安全"],
        "outro": ["扫雷还是要靠推理的~", "这局先到这，下次再战", "怎么样，我厉不厉害"],
    },
    "play_solitaire": {
        "intro": ["来把纸牌，放松一下", "没人理我，那我玩纸牌咯", "发牌发牌，纸牌时间"],
        "mid": ["这张红桃7正好接在黑8上", "翻出来一张A，送上去", "这一列先挪开再说"],
        "outro": ["纸牌就是图个心静~", "这局先摆到这里", "还差几张就能赢了"],
    },
    "play_freecell": {
        "intro": ["来一局空当接龙，动动脑子", "闲着没事，空当接龙走起", "空当接龙，第{no}号，我来试试"],
        "mid": ["空当要省着用，不能随便放", "这张先挪到空当里", "把它接到那一列上，A就出来了"],
        "outro": ["空当接龙几乎每局都能解开~", "哈哈，摆得还不错吧", "这局先走到这"],
    },
    "paint_draw": {
        "intro": ["打开画图，我来画点东西", "无聊，涂鸦一下", "画图打开，给大家画个{what}"],
        "mid": ["线条歪了没关系，艺术就是这样", "颜色就用这个吧", "再填个色就好看了"],
        "outro": ["怎么样，画得像{what}吗", "我的画功，十年前学的", "大家觉得好看吗"],
    },
    "tweak_sound": {
        "intro": ["去控制面板看看声音设置", "打开控制面板，调调声音", "我听听系统音效"],
        "outro": ["还是这个启动音最有味道", "XP 的声音真怀旧", "好啦，声音设置没问题"],
    },
    "comment_song": {
        "intro": ["让我看看现在放的是什么歌", "来看看这首歌的歌词"],
        "comment": ["《{title}》，{artist}唱的，真好听", "现在放的是{artist}的《{title}》，大家觉得怎么样", "{artist}的《{title}》，百听不厌"],
    },
    "notepad_write": {
        "intro": ["无聊，我来写写日记", "开个记事本，记点东西"],
        "note1": ["今天直播间好安静", "今天也是想吃token的一天"],
        "note2": ["明天继续加油", "等会儿有人来就好了"],
        "outro": ["好啦，日记写完了", "写完收工，不存了"],
    },
    "qq_chat": {
        "intro": ["我去QQ上找朋友聊两句", "没人说话，我给好友发个消息"],
        "msg1": ["在吗，我在直播间摸鱼", "最近怎么样呀"],
        "msg2": ["晚上一起玩游戏吗", "哈哈那下次聊"],
        "outro": ["聊完啦，继续直播"],
    },
    "game_menu": {
        "intro": ["看看有什么游戏能玩", "打开游戏看看菜单", "好久没玩了，看看主菜单"],
        "outro": ["回头有空再玩，先看看菜单过过瘾"],
    },
    "arrange_icons": {
        "intro": ["桌面有点乱，整理整理图标", "强迫症犯了，排一下图标"],
        "outro": ["清爽多了"],
    },
    "change_wallpaper": {
        "intro": ["换张壁纸，换换心情", "这壁纸看腻了，换一张"],
        "outro": ["这张好看吧"],
    },
    "qq_pet_care": {
        "intro": ["我的企鹅宠物好久没管了，去看看", "宠物该照顾啦，我来露一手", "闲着也是闲着，逗逗桌面上的小企鹅"],
        "outro": ["球球开心就好", "养宠物还是要勤快点", "你看它多高兴"],
    },
    "qq_zone_visit": {
        "intro": ["好久没逛QQ空间了，去看看", "没人说话，我去空间串串门", "打开空间，回忆杀一下"],
        "mid": ["这相册里的照片都是满满的青春", "留言板里全是踩踩，十年前的味道", "这个背景音乐设置得有点东西"],
        "title": ["今天直播间好安静", "无聊的下午", "我的小日记"],
        "body": ["今天没什么人来，就在空间里写点东西，希望明天有人陪我聊天。", "闲下来才发现，好久没认真写日志了，记录一下今天的心情。"],
        "outro": ["日志发出去了，等你们来踩", "写完啦，欢迎来空间留言", "空间逛完了，怀念~"],
    },
    "qq_show_change": {
        "intro": ["腻了，换身QQ秀试试", "这套衣服穿太久了，换一套", "来，给大家换个造型"],
        "outro": ["怎么样，帅不帅", "这套还行吧", "新造型，给个好评"],
    },
    "qq_files_download": {
        "intro": ["群共享里好像有新东西，去看看", "我去群文件里淘点好东西", "来，群共享下载走起"],
        "outro": ["丢给迅雷慢慢下，不着急", "下载中，十年前的网速你们懂的", "等它下完再看"],
    },
    "play_vote": {
        "intro": ["来个投票吧，下一步干啥你们说了算", "我选择困难，大家帮我投个票", "发数字投票，赢的我就去干"],
        "outro": ["快投快投，发数字就行", "票数我盯着呢~"],
    },
    "play_rank": {
        "intro": ["来看看今天的积分榜", "我翻一下排行榜，看看谁最勤快", "排行榜打开，点名表扬一下"],
        "outro": ["榜一是{top}，{pts}分，厉害", "{top}霸榜了，大家加油", "继续聊天攒积分，冲榜~"],
    },
    "ai_game": {
        "intro": ["冷场了，我来出题，大家抢答", "来玩个小游戏吧，答对有积分", "无聊了，来一局小游戏"],
        "outro": ["发答案就行，抢答有分~", "别光看呀，参与一下"],
    },
    "qq_shake": {
        "intro": ["没人理我，我来抖一下提醒大家", "咳咳，来个窗口抖动，醒醒啦", "抖一抖，看看有没有人在"],
        "outro": ["嘿嘿，抖完了", "还在的吱一声~"],
    },
    "calc": {
        "intro": ["我来算算今天吃了多少token", "打开计算器算个数"],
        "outro": ["嗯，数学还行"],
    },
}
FIXED_LINES = {}          # 台词是固定的（perform.py 的表演）：不走大模型
DESC = {   # 给大模型看的：这次在做什么、每个键该写什么
    "browse_ie": ("在 IE 浏览器里随便逛网页", {"intro": "开始上网前说的一句", "mid": "看到网页（{site}）后吐槽的一句"}),
    "play_minesweeper": ("在玩扫雷", {"intro": "开始玩前一句", "mid": "玩的过程中的一句", "outro": "玩完后的感想"}),
    "play_solitaire": ("在玩纸牌（Windows 经典纸牌，用鼠标拖牌）", {"intro": "开始玩前一句", "mid": "玩的过程中的一句", "outro": "玩了十几步后的感想（这局还没玩完，别说赢了/通关）"}),
    "play_freecell": ("在玩空当接龙（第 {no} 号牌局，先想好整局怎么解再一张张拖）", {"intro": "开始玩前一句", "mid": "玩的过程中的一句", "outro": "玩了十几步后的感想（这局还没玩完，别说赢了/通关）"}),
    "paint_draw": ("在画图里用鼠标画一幅简笔画：{what}", {"intro": "打开画图时说的一句", "mid": "画的过程中的一句", "outro": "画完后让观众评价的一句（可以提到画的是{what}）"}),
    "tweak_sound": ("打开控制面板，进“声音和音频设备”，试听一个 XP 系统声音", {"intro": "打开控制面板时说的一句", "outro": "试听完的一句"}),
    "comment_song": ("打开音乐播放器，看正在放的歌，并点评这首歌", {"intro": "打开播放器时说的一句", "comment": "点评这首歌（要提到歌名或歌手，可以引用歌词）"}),
    "notepad_write": ("打开记事本写几句日记/随笔", {"intro": "开始写之前一句", "note1": "要在记事本里打的第一句日记（不是对观众说的话，像日记）",
                                          "note2": "第二句日记", "outro": "写完后对观众说的一句"}),
    "qq_chat": ("登录 QQ，和一个好友私聊", {"intro": "打开 QQ 时说的一句", "msg1": "发给好友的第一条消息（口吻像发给朋友）",
                                  "msg2": "发给好友的第二条消息", "outro": "聊完后对观众说的一句"}),
    "game_menu": ("打开一个游戏，在主菜单里看看（不玩）", {"intro": "打开游戏时说的一句", "outro": "看完菜单的感想"}),
    "arrange_icons": ("整理桌面图标", {"intro": "整理前一句", "outro": "整理后一句"}),
    "change_wallpaper": ("换一张桌面壁纸", {"intro": "换之前一句", "outro": "换完后一句"}),
    "qq_pet_care": ("照顾桌面上的QQ宠物小企鹅：{what}", {"intro": "去照顾宠物前说的一句", "outro": "照顾完宠物的一句"}),
    "qq_zone_visit": ("打开QQ空间逛一逛，{blog}", {"intro": "打开QQ空间时说的一句", "mid": "逛空间时的一句吐槽", "title": "要发表的日志标题（不是对观众说的话，8个字以内）",
                                          "body": "日志正文（像随笔，20~40字）", "outro": "逛完 / 写完日志后对观众说的一句"}),
    "qq_show_change": ("给自己的QQ秀换一套衣服（换成：{outfit}）", {"intro": "换装前一句", "outro": "换完后让观众评价的一句"}),
    "qq_files_download": ("打开群共享，挑一个文件用迅雷下载", {"intro": "打开群共享时说的一句", "outro": "开始下载后的一句"}),
    "play_vote": ("发起一个弹幕投票，让观众投票决定你下一步玩什么（选项：{opts}）", {"intro": "发起投票时说的一句", "outro": "催大家投票的一句"}),
    "play_rank": ("打开 QQ积分排行榜窗口看看，表扬一下榜一的观众（榜一：{top}，{pts} 分）", {"intro": "打开排行榜时说的一句", "outro": "点名表扬榜一的一句"}),
    "ai_game": ("没什么人说话，自己发起一个观众小游戏（{game}）拉拉人气", {"intro": "宣布要玩游戏的一句", "outro": "催大家来答题的一句"}),
    "ai_screen": ("看一眼自己的屏幕，随口点评一句", {}),
    "qq_shake": ("给群聊窗口发一个窗口抖动，提醒大家", {"intro": "抖之前一句", "outro": "抖完后一句"}),
    "calc": ("用计算器算一个数", {"intro": "打开计算器时说的一句", "outro": "算完的一句"}),
}


def weights_of(cfg):
    """[idle] weights（老活动）+ weights_new（后加的活动，老 config.ini 里没有 weights_new 时用默认值）；weights 里写了同名的以 weights 为准。"""
    w = parse_weights(cfg.s("idle", "weights_new"))
    w.update(parse_weights(cfg.s("idle", "weights")))
    from . import perform as _pf                             # 冷场表演（perform.py）：权重在 [perform] weights；开关 / 间隔在 perform.py 里管
    for k, v in _pf.weights(cfg).items():
        w.setdefault(k, v)
    w.setdefault("diary_read", cfg.f("story", "read_weight"))   # 翻QQ空间念日记（diary_act.py）：权重在 [story] read_weight
    return w


def parse_weights(s):
    out = {}
    for part in re.split(r"[,，;；\s]+", s or ""):
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                out[k.strip()] = max(0.0, float(v))
            except ValueError:
                pass
        elif part.strip():
            out[part.strip()] = 1.0
    return out


class Ctx:
    def __init__(self, idle, desk, song):
        self.idle, self.desk, self.song, self.cfg = idle, desk, song, idle.cfg
        self.apps = set(desk.apps_open()) if desk else set()
        self.fmt = {}
        self.rnd = random

    def sites(self):
        raw = [x.strip() for x in re.split(r"[,，\s]+", self.cfg.s("idle", "sites")) if x.strip()]
        ok = [x for x in raw if self.idle.agent_site_ok(x)] or SITES_FALLBACK
        return random.sample(ok, min(2, len(ok))) if len(ok) > 1 else ok * 2


# ---------------------------------------------------------------- 活动：eligible(ctx) / plan(ctx, L) → [beat]
HIGHLIGHT_PERFS = {"perf_bsod", "perf_restart", "perf_virus", "perf_fireworks", "perf_meteor"}     # 开演时标记成高光（App.mark_highlight → [clips]）


# beat = {"say": key|None, "emo": 情绪, "actions": [...], "critical": bool(失败就中止)}
def B(say=None, actions=None, emo="开心", critical=False):
    return {"say": say, "emo": emo, "actions": actions or [], "critical": critical}


def clear():
    return {"action": "_idle_clear"}


R_AIPLUS = ("game_start", "game_stop", "screen_comment", "song_comment")   # 同 registry.AIPLUS_ACTIONS
ACTS = {}


def act(name):
    def deco(fn):
        ACTS[name] = fn
        return fn
    return deco


@act("browse_ie")
def _browse(ctx):
    if "ie" in ctx.apps:
        return None
    s1, s2 = ctx.sites()
    ctx.fmt["site"] = s2.replace("www.", "")
    return [B("intro", [{"action": "open_app", "app": "ie"}, clear(), {"action": "browse", "url": s1}], critical=True),
            B("mid", [{"action": "_wait", "secs": 1.5}, {"action": "browse", "url": s2}, clear()], "平静")]


@act("play_minesweeper")
def _mine(ctx):
    if "minesweeper" in ctx.apps:
        return None
    n = max(4, ctx.cfg.i("idle", "mine_steps"))
    return [B("intro", [{"action": "open_app", "app": "minesweeper"}, clear(), {"action": "mine_new", "level": "beginner"}], critical=True),
            B("mid", [{"action": "mine_play", "steps": n // 2}], "得意"),
            B("outro", [{"action": "mine_play", "steps": n - n // 2}], "得意")]


@act("play_solitaire")
def _sol(ctx):
    if "solitaire" in ctx.apps:
        return None
    n = max(4, ctx.cfg.i("idle", "cards_steps"))
    return [B("intro", [{"action": "open_app", "app": "solitaire"}, clear()], critical=True),
            B("mid", [{"action": "sol_play", "steps": n // 2}], "得意"),
            B("outro", [{"action": "sol_play", "steps": n - n // 2}], "得意")]


@act("play_freecell")
def _fc(ctx):
    if "freecell" in ctx.apps:
        return None
    n = max(4, ctx.cfg.i("idle", "cards_steps"))
    no = random.randint(1, 32000)
    if no == 11982:
        no = 617
    ctx.fmt["no"] = str(no)
    return [B("intro", [{"action": "open_app", "app": "freecell"}, clear(), {"action": "fc_new", "no": no}], critical=True),
            B("mid", [{"action": "fc_play", "steps": n // 2}], "得意"),
            B("outro", [{"action": "fc_play", "steps": n - n // 2}], "得意")]


PAINT_WHAT = {"smile": "笑脸", "house": "房子", "sun": "太阳", "flower": "花", "heart": "爱心", "star": "星星", "tree": "树", "boat": "小船"}
PAINT_COLORS = ["红", "蓝", "粉", "橙", "紫", "黄"]


@act("paint_draw")
def _paint(ctx):
    if "paint" in ctx.apps:
        return None
    k = random.choice(list(PAINT_WHAT))
    ctx.fmt["what"] = PAINT_WHAT[k]
    d = {"action": "paint_draw", "what": k}
    if k in ("flower", "heart", "boat", "house", "tree"):
        d["color"] = random.choice(PAINT_COLORS if k != "tree" else ["深绿", "草绿"])
    return [B("intro", [{"action": "open_app", "app": "paint"}, clear()], "平静", critical=True),
            B("mid", [d], "得意"), B("outro", [{"action": "_wait", "secs": 2.5}], "开心")]


@act("tweak_sound")
def _sound(ctx):
    if ctx.apps & {"control", "sndcpl"}:
        return None
    return [B("intro", [{"action": "control_open", "item": "声音"}, clear()], "平静", critical=True), B("outro", [{"action": "_wait", "secs": 1.5}], "开心")]


@act("comment_song")
def _song(ctx):
    s = ctx.song
    if not s or not s.get("title"):
        return None
    ctx.fmt.update(title=s["title"], artist=s.get("artist") or "不知名歌手")
    if "ttplayer" in ctx.apps and random.random() < 0.5:
        opener = {"action": "focus_window", "target": "ttplayer"}
    elif "kugou" not in ctx.apps:
        opener = {"action": "open_app", "app": "kugou"}
    else:
        opener = {"action": "focus_window", "target": "kugou"}
    return [B("intro", [opener, clear()], "平静", critical=True),
            B("comment", [{"action": "_hover_song"}, {"action": "_wait", "secs": 2.5}], "开心")]


@act("notepad_write")
def _note(ctx):
    if "notepad" in ctx.apps:
        return None
    return [B("intro", [{"action": "open_app", "app": "notepad"}, clear()], "平静", critical=True),
            B(None, [{"action": "notepad_type", "text": "@note1"}, clear()], "平静"),
            B("outro", [{"action": "notepad_type", "text": "@note2"}], "平静")]


@act("qq_chat")
def _qq(ctx):
    if ctx.apps & {"qq"}:
        return None
    friend = ctx.cfg.s("idle", "friend")
    a1 = {"action": "qq_private", "text": "@msg1"}
    a2 = {"action": "qq_private", "text": "@msg2"}
    if friend:
        a1["friend"] = a2["friend"] = friend
    return [B("intro", [a1, clear()], critical=True), B(None, [{"action": "_wait", "secs": 1}, a2, clear()]), B("outro", [{"action": "_wait", "secs": 2}])]


@act("game_menu")
def _game(ctx):
    free = [g for g in GAMES if g not in ctx.apps]
    if not free:
        return None
    g = random.choice(free)
    ctx.fmt["game"] = R.APPS[g][0]
    return [B("intro", [{"action": "open_app", "app": g}, clear(), {"action": "_peek_menu"}], "惊讶", critical=True),
            B("outro", [{"action": "_wait", "secs": 1.5}], "开心")]


@act("arrange_icons")
def _arrange(ctx):
    return [B("intro", [{"action": "arrange_icons", "by": random.choice(["name", "type", "time", "size"])}], critical=True), B("outro", [{"action": "refresh_desktop"}])]


@act("change_wallpaper")
def _wall(ctx):
    return [B("intro", [{"action": "change_wallpaper", "name": "random"}], "兴奋", critical=True), B("outro", [{"action": "_wait", "secs": 1.5}])]


@act("calc")
def _calc(ctx):
    if "calc" in ctx.apps:
        return None
    a, b = random.randint(12, 99), random.randint(12, 99)
    ctx.fmt["expr"] = f"{a}*{b}"
    return [B("intro", [{"action": "open_app", "app": "calc"}, clear(), {"action": "calc", "expr": f"{a}*{b}"}], "得意", critical=True),
            B("outro", [{"action": "_wait", "secs": 1.5}])]


# ---- QQ 生态活动（受 [qq] 控制；[qq] commands 关了也一样会做——它管的是观众弹幕口令）----
def _qq_on(ctx, k):
    return ctx.cfg.b("qq", "enabled") and ctx.cfg.b("qq", k)


@act("qq_pet_care")
def _qpet(ctx):
    if not _qq_on(ctx, "pet"):
        return None
    what = random.choice(["feed", "feed", "bath", "play", "play", "sing"])
    ctx.fmt["what"] = {"feed": "喂食", "bath": "洗澡", "play": "玩耍", "sing": "唱歌"}[what]
    d = {"action": "pet_care", "what": what}
    if what == "feed":
        d["food"] = random.choice(["apple", "fish", "cake", "drumstick"])
    return [B("intro", [d], "开心", critical=True), B("outro", [{"action": "_wait", "secs": 2.5}], "开心")]


@act("qq_zone_visit")
def _qzone(ctx):
    if not _qq_on(ctx, "zone") or "qzone" in ctx.apps:
        return None
    tab = random.choice(["album", "msg", "music", "home"])
    blog = ctx.cfg.b("qq", "zone_blog") and random.random() < 0.5
    ctx.fmt["blog"] = "再写一篇日志发表" if blog else "翻翻" + {"album": "相册", "msg": "留言板", "music": "音乐盒", "home": "主页"}[tab]
    beats = [B("intro", [{"action": "open_app", "app": "qzone"}, clear()], "平静", critical=True), B("mid", [{"action": "zone_open", "tab": tab}, {"action": "_wait", "secs": 2.5}], "开心")]
    if blog:
        beats.append(B(None, [{"action": "zone_blog", "title": "@title", "text": "@body"}], "平静"))
    beats.append(B("outro", [{"action": "_wait", "secs": 2}], "开心"))
    return beats


@act("qq_show_change")
def _qshow(ctx):
    if not _qq_on(ctx, "show"):
        return None
    pool = [("santa", "圣诞套装"), ("cool", "酷炫墨镜"), ("king", "国王驾到"), ("sailor", "小水手"), ("wizard", "魔法学徒"), ("party", "派对时间"), ("love", "爱心满满"), ("gentleman", "绅士风度"), ("summer", "夏日海滩")]
    k, nm = random.choice(pool)
    ctx.fmt["outfit"] = nm
    return [B("intro", [{"action": "outfit_change", "name": k}], "得意", critical=True), B("outro", [{"action": "_wait", "secs": 2.5}], "得意")]


@act("qq_files_download")
def _qfiles(ctx):
    if not _qq_on(ctx, "files") or "qqfiles" in ctx.apps:
        return None
    return [B("intro", [{"action": "open_app", "app": "qqfiles"}, clear()], "平静", critical=True), B("outro", [{"action": "files_download"}, {"action": "_wait", "secs": 2}], "开心")]


@act("play_vote")
def _pvote(ctx):
    pl = getattr(ctx.idle.app, "play", None)
    if pl is None or not pl.idle_vote_ok():
        return None
    pool = [x.strip() for x in re.split(r"[,，|]+", ctx.cfg.s("play", "vote_idle_options")) if x.strip()]
    if len(pool) < 2:
        return None
    opts = random.sample(pool, min(3, len(pool)))
    ctx.fmt["opts"] = "、".join(opts)
    secs = ctx.cfg.i("play", "vote_idle_secs")
    return [B("intro", [{"action": "vote_start", "title": "下一步干啥", "options": "|".join(opts), "secs": secs}], "兴奋", critical=True), B("outro", [{"action": "_wait", "secs": 2}], "开心")]


@act("play_rank")
def _prank(ctx):
    pl = getattr(ctx.idle.app, "play", None)
    if pl is None or not (pl.on() and ctx.cfg.b("play", "points")):
        return None
    sc, _ = pl.idle_scope()
    rows = pl.rank(sc, "day", 1) if sc else []
    if not rows:
        return None
    ctx.fmt["top"], ctx.fmt["pts"] = rows[0]["name"], rows[0]["pts"]
    return [B("intro", [{"action": "open_app", "app": "rank"}, {"action": "rank_open", "by": "day"}, clear()], "平静", critical=True), B("outro", [{"action": "_wait", "secs": 3}], "开心")]


@act("ai_game")
def _aigame(ctx):
    pl = getattr(ctx.idle.app, "plus", None)
    if pl is None or not pl.idle_game_ok():
        return None
    g = random.choice(pl.idle_game_list())
    ctx.fmt["game"] = {"idiom": "成语接龙", "song": "猜歌名", "riddle": "脑筋急转弯"}.get(g, g)
    return [B("intro", [{"action": "game_start", "game": g}], "兴奋", critical=True), B("outro", [{"action": "_wait", "secs": 2}], "开心")]


@act("ai_screen")
def _aiscreen(ctx):
    pl = getattr(ctx.idle.app, "plus", None)
    if pl is None or not pl.m("screen") or not pl.screen_ready()[0]:
        return None
    return [B(None, [{"action": "screen_comment"}, {"action": "_wait", "secs": 6}], "开心", critical=True)]


@act("qq_shake")
def _qshake(ctx):
    if not _qq_on(ctx, "shake"):
        return None
    return [B("intro", [{"action": "shake", "target": "chat"}], "开心", critical=True), B("outro", [{"action": "_wait", "secs": 1.5}], "开心")]


# ---------------------------------------------------------------- 引擎
class Idle:
    def __init__(self, cfg, app, agent, log=print):
        self.cfg, self.app, self.agent, self.log = cfg, app, agent, log
        self.t0 = time.time()
        self.last_viewer = time.time()
        self.next_at = 0.0
        self.task = None
        self.cur = None
        self.waiters = {}
        self.seq = 0
        self.hist = deque(maxlen=30)
        self.recent = {}
        self.starts = deque()
        self.why = "启动中"
        self.stats = {"started": 0, "finished": 0, "interrupted": 0, "failed": 0, "llm_lines": 0, "template_lines": 0, "spoken": 0}

    # ------------------------------------------------------------ 配置 / 状态
    def on(self):
        return self.cfg.b("idle", "enabled") and self.agent.on()

    def agent_site_ok(self, s):
        from .core import SITE_OK
        return bool(SITE_OK.match(s.strip()))

    def host(self):
        return getattr(self.app, "any_host", lambda: None)()

    def song(self, desk):
        m = getattr(self.app, "music", None)
        st = getattr(m, "state", None) or {}
        if st.get("on") and st.get("title"):
            return {"title": st["title"], "artist": st.get("artist") or "", "album": st.get("album") or "", "pos": st.get("pos"), "lyric": self._lyric(m, st)}
        ds = (desk.s.get("music") if desk else None) or {}
        if ds.get("on") and ds.get("title"):
            return {"title": ds["title"], "artist": ds.get("artist") or "", "album": "", "pos": None, "lyric": ""}
        return None

    @staticmethod
    def _lyric(m, st):
        try:
            lines, pos = (m.lyric or {}).get("lines") or [], float(st.get("pos") or 0)
            cur = ""
            for ln in lines:
                if ln[0] <= pos:
                    cur = ln[1]
                else:
                    break
            return cur
        except Exception:  # noqa
            return ""

    # ------------------------------------------------------------ 事件入口（Room._broadcast 里调用）
    def note_event(self, ev):
        t = ev.get("t")
        if t == "chat":
            self.last_viewer = time.time()
            if self.cfg.b("idle", "stop_on_chat"):
                self.interrupt("观众开口了")
        elif t in ("gift", "follow") and self.cfg.b("idle", "gifts_reset_quiet"):
            self.last_viewer = time.time()

    def note_command(self):
        """观众指令（规则 / LLM 认出来的）→ 一定打断。"""
        self.last_viewer = time.time()
        self.interrupt("观众指令")

    def on_result(self, res):
        fut = self.waiters.pop((res or {}).get("id"), None)
        if fut is not None and not fut.done():
            fut.set_result(res)

    # ------------------------------------------------------------ 主循环
    def start(self):
        asyncio.ensure_future(self.loop())

    async def loop(self):
        while True:
            await asyncio.sleep(1.0)
            try:
                await self.tick()
            except Exception as e:  # noqa
                self.log(f"[idle] tick 出错：{e!r}")

    def ready(self, now):
        c = self.cfg
        ag = self.agent
        if not self.on():
            return False, "已关闭"
        if self.task and not self.task.done():
            return False, "正在进行"
        pl = getattr(self.app, "play", None)
        if pl is not None and pl.vote_open():
            return False, "弹幕投票进行中"
        if not ag.clients:
            return False, "没有页面连着"
        cl = ag.clients.get(ag.snap_ws) or {}
        desk = ag.desk()
        if not desk.known or now - (cl.get("at") or 0) > 15:
            return False, "桌面快照太旧"
        if now - self.t0 < c.f("idle", "startup_delay"):
            return False, "启动延迟"
        if now < self.next_at:
            return False, "间隔未到"
        if now - self.last_viewer < c.f("idle", "idle_after"):
            return False, "观众刚说过话"
        while self.starts and now - self.starts[0] > 3600:
            self.starts.popleft()
        if len(self.starts) >= c.i("idle", "max_per_hour"):
            return False, "每小时上限"
        if c.b("idle", "wait_agent"):
            for k in [k for k, t in ag.pending.items() if now - t > 90]:
                ag.pending.pop(k, None)
            if ag.pending or desk.s.get("busy") or (desk.s.get("queue") or 0) > 0:
                return False, "页面正忙（有指令在执行）"
        if c.b("idle", "wait_jukebox"):
            jb = getattr(self.app, "jukebox", None)
            if jb is not None and (jb.current or jb.queue or getattr(jb, "_busy", False)):
                return False, "点歌队列忙"
        h = self.host()
        if c.b("idle", "wait_host_quiet") and h is not None and now < getattr(h, "busy_until", 0):
            return False, "主播正在说话"
        if desk.s.get("xpbusy"):
            return False, "开机 / 关机 / 蓝屏画面中"
        chat = desk.s.get("chat") or {}
        if chat and (chat.get("vis") or 0) < 0.5:
            return False, "群聊窗口没完全显示（可能在自动恢复）"
        if desk.s.get("start"):
            return False, "开始菜单开着"
        return True, ""

    def allowed(self, name):
        c = self.cfg
        if name not in ACTS:
            return False
        allow, deny = R.split_list(c.s("idle", "allow_activities")), R.split_list(c.s("idle", "deny_activities"))
        if name in deny:
            return False
        return not allow or "*" in allow or name in allow

    def pick(self, desk, now, only=None):
        w = weights_of(self.cfg)
        gap = self.cfg.f("idle", "repeat_gap")
        ctx = Ctx(self, desk, self.song(desk))
        cands = []
        for name, wt in w.items():
            if only and name != only:
                continue
            if wt <= 0 or not self.allowed(name):
                continue
            if not only and now - self.recent.get(name, 0) < gap:
                continue
            if ACTS[name](Ctx(self, desk, ctx.song)) is None:      # 当前条件不满足（比如记事本已经开着、没在放歌）
                continue
            cands.append((name, wt))
        if not cands:
            return None
        tot = sum(x[1] for x in cands)
        r = random.random() * tot
        for name, wt in cands:
            r -= wt
            if r <= 0:
                return name
        return cands[-1][0]

    async def tick(self):
        now = time.time()
        ok, why = self.ready(now)
        self.why = why or "就绪"
        if not ok:
            return
        name = self.pick(self.agent.desk(), now)
        if not name:
            self.why = "没有合适的活动"
            self.next_at = now + 20
            return
        self.begin(name)

    def begin(self, name, force=False):
        now = time.time()
        self.starts.append(now)
        self.recent[name] = now
        self.stats["started"] += 1
        self.task = asyncio.ensure_future(self.run(name, force))
        return self.task

    # ------------------------------------------------------------ 打断
    def interrupt(self, reason=""):
        if not (self.task and not self.task.done()):
            return False
        self.log(f"[idle] 打断：{reason}（{(self.cur or {}).get('name')}）")
        self.stats["interrupted"] += 1
        self.task.cancel()
        for k, f in list(self.waiters.items()):
            self.waiters.pop(k, None)
            if not f.done():
                f.cancel()
        asyncio.ensure_future(self.agent.send_pages({"t": "agent_abort", "reason": reason}))
        return True

    # ------------------------------------------------------------ 一次活动
    async def run(self, name, force=False):
        c = self.cfg
        t0 = time.time()
        deadline = t0 + c.f("idle", "max_duration")
        rec = {"name": name, "start": int(t0 * 1000), "beats": 0, "lines": [], "result": "", "llm": ""}
        self.hist.append(rec)
        self.cur = {"name": name, "rec": rec}
        interrupted = False
        try:
            desk = self.agent.desk()
            ctx = Ctx(self, desk, self.song(desk))
            beats = ACTS[name](ctx)
            if not beats:
                rec["result"] = "条件不满足"
                return
            if name in FIXED_LINES:
                _pf.on_start(self, name)
            if name == "diary_read":
                sy = getattr(self.app, "story", None)
                if sy is not None:
                    sy.mark_read(ctx.fmt.get("_diary_id"))                 # 开念就算读过（不会反复念同一篇）
            lines = await self.make_lines(name, ctx, rec)
            marked = False
            for i, b in enumerate(beats):
                if time.time() > deadline:
                    rec["result"] = "超过 max_duration，提前收尾"
                    break
                text = lines.get(b["say"]) if b["say"] else None
                if text:
                    await self.wait_host()
                    self.speak(text, b["emo"], rec)
                acts = self.fill(b["actions"], lines)
                if acts and b["critical"] and name in HIGHLIGHT_PERFS and not marked:
                    marked = True
                    mh = getattr(self.app, "mark_highlight", None)          # 高光时刻：蓝屏 / 假重启 / 熊猫烧香 / 烟花 / 流星雨真的要开演了（切片模块剪前 10 秒 + 后 15 秒）
                    if mh is not None:
                        try:
                            mh(name)
                        except Exception as e:  # noqa
                            self.log(f"[idle] 标记高光出错：{e!r}")
                if acts:
                    res = await self.dispatch(acts, name, deadline)
                    rec["beats"] += 1
                    if res is None:
                        rec["result"] = "页面没回应"
                        break
                    bad = [x for x in res.get("results", []) if not x.get("ok") and not x.get("action", "").startswith("_")]
                    if bad and b["critical"]:
                        rec["result"] = f"关键动作失败：{bad[0].get('action')} {bad[0].get('note', '')[:40]}"
                        self.stats["failed"] += 1
                        break
            else:
                rec["result"] = rec["result"] or "完成"
            if c.b("idle", "cleanup") and not (name == "perf_paint" and rec["result"] == "完成" and c.b("autoclose", "enabled")):   # 画完的画图留给 autoclose 过一会儿收（观众看得到画）
                await self.dispatch([{"action": "_idle_cleanup"}], name, time.time() + 25, label_text="收拾")
            self.stats["finished"] += 1
            if name in FIXED_LINES and rec["result"] == "完成":
                try:
                    rec["tip"] = _pf.after(self, name, ctx.fmt)
                except Exception as e:  # noqa
                    self.log(f"[idle] 表演后的提示出错：{e!r}")
        except asyncio.CancelledError:
            interrupted = True
            rec["result"] = "被打断"
            raise
        except Exception as e:  # noqa
            rec["result"] = f"出错 {e!r}"[:120]
            self.stats["failed"] += 1
            self.log(f"[idle] {name} 出错：{e!r}")
            try:
                await self.agent.send_pages({"t": "agent_abort", "reason": "error"})
            except Exception:  # noqa
                pass
        finally:
            rec["ms"] = int((time.time() - t0) * 1000)
            self.cur = None
            now = time.time()
            self.next_at = max(self.next_at, now + random.uniform(c.f("idle", "min_interval"), max(c.f("idle", "min_interval"), c.f("idle", "max_interval"))))
            self.log(f"[idle] {name}：{rec['result']}（{rec['ms']}ms，{rec['beats']} 批动作，{len(rec['lines'])} 句旁白，{rec['llm']}）")
            ops = getattr(self.app, "ops", None)
            if ops is not None:
                ops.record("idle", name=name, result=rec["result"], ms=rec["ms"], lines=len(rec["lines"]))

    def fill(self, actions, lines):
        out = []
        for a in actions:
            a = dict(a)
            for k, v in list(a.items()):
                if isinstance(v, str) and v.startswith("@"):
                    a[k] = lines.get(v[1:]) or ""
            if a.get("action") in ("notepad_type", "qq_private") and not a.get("text"):
                continue
            out.append(a)
        return out

    async def wait_host(self, maxwait=6.0):
        h = self.host()
        if h is None:
            return
        t = time.time() + maxwait
        while time.time() < t and time.time() < getattr(h, "busy_until", 0):
            await asyncio.sleep(0.3)

    # ------------------------------------------------------------ 说话
    def speak(self, text, emo, rec):
        rec["lines"].append(text)
        if not self.cfg.b("idle", "speak"):
            return
        h = self.host()
        if h is None:
            self.log(f"[idle] (没有主播实例，旁白只记录) {text}")
            return
        if h.bl_in(text) or h.bl_out(text):
            return
        self.stats["spoken"] += 1
        h.last["idle"] = time.time()               # 推迟主播自己的“冷场暖场”，别俩一起说
        asyncio.get_running_loop().run_in_executor(None, lambda: h._say("idle", 20, text, emo))

    # ------------------------------------------------------------ 派发给页面
    async def dispatch(self, actions, name, deadline, label_text=""):
        ag = self.agent
        desk = ag.desk()
        good = []
        deny_music = not self.cfg.b("idle", "allow_music_control")
        for a in actions:
            n = a["action"]
            if n.startswith("_"):
                good.append(a)
                continue
            if deny_music and (n.startswith("music_") or n == "song_request"):
                continue
            trust = (("shutdown",) if (n == "shutdown" and a.get("mode") == "restart" and (self.cur or {}).get("name") == "perf_restart") else ())   # 表演「重启」：页面里的 XP 假重启，越过 deny_actions
            g, errs, _ = ag.validate([a], desk, "猪猪侠", viewer=False, trust=trust)
            if g and n in R_AIPLUS:                              # 加强包后端动作（开游戏 / 点评屏幕）：当场做
                pl = getattr(self.app, "plus", None)
                rooms = [r for rid, r in self.app.rooms.items() if rid != "demo"] or list(self.app.rooms.values())
                if pl is not None:
                    pl.agent_action(g[0], {}, rooms[0] if rooms else None, self.cfg.s("host", "name"))
                continue
            if g and n in ("vote_start", "vote_end"):          # 后端动作：当场做，不发给页面（投票窗口由 play 事件自己弹出）
                pl = getattr(self.app, "play", None)
                rooms = [r for rid, r in self.app.rooms.items() if rid != "demo"] or list(self.app.rooms.values())
                if pl is not None:
                    pl.agent_action(g[0], {}, rooms[0] if rooms else None, self.cfg.s("host", "name"))
                continue
            if g:
                good.append(g[0])
            else:
                self.log(f"[idle] 动作被校验拦下 {n}: {errs}")
        if not good:
            return {"ok": True, "results": []}
        self.seq += 1
        job = f"i{self.seq}"
        fut = asyncio.get_running_loop().create_future()
        self.waiters[job] = fut
        ag.pending[job] = time.time()
        label = self.cfg.s("idle", "who_label") or self.cfg.s("host", "name")
        await ag.send_pages({"t": "agent_do", "id": job, "by": label, "text": label_text or name, "idle": True,
                             "speed": max(0.2, self.cfg.f("idle", "cursor_speed")), "actions": good})
        try:
            return await asyncio.wait_for(fut, timeout=max(5.0, min(60.0, deadline - time.time() + 10)))
        except asyncio.TimeoutError:
            self.waiters.pop(job, None)
            await ag.send_pages({"t": "agent_abort", "reason": "timeout"})
            return None
        finally:
            ag.pending.pop(job, None)

    # ------------------------------------------------------------ 旁白生成
    async def make_lines(self, name, ctx, rec):
        if name in FIXED_LINES:
            rec["llm"] = "固定台词"
            return {"intro": ctx.fmt.get("_intro") or random.choice(T[name]["intro"])}
        keys = DESC[name][1]
        lines = None
        if self.cfg.b("idle", "speak") and self.cfg.b("idle", "llm") and self.cfg.ai_enabled:
            try:
                lines = await asyncio.get_running_loop().run_in_executor(None, lambda: self.llm_lines(name, ctx))
                if lines:
                    rec["llm"] = f"LLM {lines.pop('_ms', 0)}ms"
                    self.stats["llm_lines"] += len(lines)
            except Exception as e:  # noqa
                rec["llm"] = f"LLM 失败→模板（{str(e)[:40]}）"
        lines = lines or {}
        for k in keys:
            if not lines.get(k):
                lines[k] = random.choice(T[name][k]).format_map(_Safe(ctx.fmt))
                self.stats["template_lines"] += 1
        if not rec["llm"]:
            rec["llm"] = "模板"
        return lines

    def llm_lines(self, name, ctx):
        c = self.cfg
        h = self.host()
        persona = c.file_text(c.s("host", "persona")).strip() or f"你是{c.s('host', 'name')}，一个可爱的AI直播间主播。"
        desc, keys = DESC[name]
        n = c.i("idle", "line_chars")
        song = ctx.song
        song_txt = ""
        if song:
            song_txt = f"正在放：《{song['title']}》- {song['artist']}" + (f"；现在唱到：{song['lyric']}" if song.get("lyric") else "")
        fmt = _Safe(ctx.fmt)
        key_txt = "\n".join(f'- "{k}"：{v.format_map(fmt)}' for k, v in keys.items())
        extra = ""
        if name == "browse_ie":
            extra = f"你要逛的网站：{ctx.fmt.get('site', '')}。"
        if name == "game_menu":
            extra = f"打开的游戏：{ctx.fmt.get('game', '')}。"
        if name == "calc":
            extra = f"要算的式子：{ctx.fmt.get('expr', '')}。"
        sys_p = (persona + "\n\n【现在的情况】直播间没人说话，你闲着没事，自己用画面里的 Windows XP 电脑玩。观众看得到你的鼠标在动，你边做边用很短的话旁白。\n"
                 f"规则：每句不超过 {n} 个字，口语、可爱、符合你的人设；不要动作描写、不要 emoji、不要 markdown、不要网址、不要联系方式；不要点名观众（没人在说话）；"
                 "不要说“大家好”之类开场白；不聊政治色情暴力。只输出一个 JSON 对象，不要任何别的文字。")
        user = (f"这次在做的事：{desc}。{extra}\n{song_txt}\n桌面状态：\n{ctx.desk.summary() if ctx.desk else ''}\n\n"
                f"请输出 JSON，键如下（值是字符串）：\n{key_txt}")
        body = {"model": c.s("ai", "model"), "temperature": 0.9, "max_tokens": 300, "stream": False, **L._extra(c),
                "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": user}]}
        t0 = time.time()
        key = c.s("ai", "api_key")
        r = requests.post(c.s("ai", "base_url").rstrip("/") + "/chat/completions", timeout=c.f("idle", "llm_timeout"),
                          headers={"Authorization": f"Bearer {key}"} if key else {}, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}")
        d = L._loads(r.json()["choices"][0]["message"].get("content") or "") or {}
        out = {}
        for k in keys:
            v = self.clean(d.get(k), n if not k.startswith(("note", "msg")) else max(n, 30), h)
            if v:
                out[k] = v
        out["_ms"] = int((time.time() - t0) * 1000)
        return out

    @staticmethod
    def clean(v, n, host=None):
        if not isinstance(v, str):
            return ""
        v = re.sub(r"\[[^\]]*\]|（[^）]*）|\([^)]*\)|\*[^*]*\*", "", v)
        v = re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF]", "", v).strip().strip('"“”')
        v = re.sub(r"\s+", " ", v)
        if NOTE_PREFIX_RE.search(v):
            return ""
        if len(v) > n:
            cut = max(v.rfind(p, 0, n) for p in "。！？!?，,")
            v = v[:cut + 1] if cut > n * 0.5 else v[:n]
        v = v.strip("，, ")
        if host is not None and (host.bl_in(v) or host.bl_out(v)):
            return ""
        return v

    # ------------------------------------------------------------ 测试 / 状态
    def state(self):
        now = time.time()
        return {"enabled": self.on(), "why": self.why, "quiet_for": int(now - self.last_viewer), "idle_after": self.cfg.f("idle", "idle_after"),
                "next_in": max(0, int(self.next_at - now)), "running": (self.cur or {}).get("name"), "stats": self.stats,
                "weights": weights_of(self.cfg), "history": list(self.hist)[-10:]}


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


from . import perform as _pf  # noqa: E402  冷场表演：把 perf_* 注册进 ACTS
import sys as _sys  # noqa: E402
_pf.register(_sys.modules[__name__])
from . import diary_act as _da  # noqa: E402  冷场翻QQ空间日记念出来（[story]）
_da.register(_sys.modules[__name__])
