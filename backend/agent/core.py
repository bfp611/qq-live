# -*- coding: utf-8 -*-
"""Agent：弹幕 → 指令 → 页面执行。

流程（on_chat）：
  谁能指挥(who/deny_users) → 限速(用户冷却/每分钟/全局) → 规则解析（毫秒级）→ 没解析出来且像指令 → LLM（线程里，带桌面快照）
  → 校验（注册表/允许表/限额/屏蔽词/目标是否存在）→ 后端动作（切歌、点歌）直接做 + 页面动作 agent_do 推给页面 → 猪猪侠说一句
没处理的弹幕（普通聊天）原样交给 AI 主播闲聊；被当作指令的弹幕不再重复闲聊。
"""
import asyncio
import random
import re
import time
from collections import deque

from . import registry as R, rules, llm
from .desk import Desk

TEMPLATES = {
    "close": ["好嘞{who}，把{t}关掉啦", "收到！{t}说关就关", "{t}？拜拜了您嘞", "行，{t}关了"],
    "min": ["好的，把{t}缩下去", "{t}先收起来~", "收到，{t}最小化"],
    "max": ["好嘞，{t}拉满全屏", "{t}放到最大啦"],
    "restore": ["{t}还原回来啦", "好的，{t}恢复原样"],
    "move": ["好嘞，{t}挪过去", "{t}拖到那边啦"],
    "move_away": ["看到了看到了，{t}挪开啦", "不挡你们了，{t}让开", "收到，把{t}拖走~"],
    "open": ["好嘞，帮{who}打开{t}", "{t}来啦", "收到，{t}打开~"],
    "focus": ["好的，切到{t}", "{t}拿到前面来了"],
    "wallpaper": ["换壁纸咯~", "好嘞{who}，换个新壁纸", "给桌面换身新衣服~"],
    "wallpaper_named": ["好嘞，壁纸换成{t}", "{t}壁纸，安排上~", "{who}想要{t}，马上换"],
    "refresh": ["刷新一下桌面~", "按下F5，刷新啦"],
    "start_menu": ["好嘞，{t}来了", "{t}打开啦"],
    "show_desktop": ["全部收起来，露出桌面~", "一键显示桌面"],
    "close_all": ["好，全部关掉，清清爽爽", "窗口一扫而光"],
    "tile": ["把窗口排排整齐~", "窗口排好队啦"],
    "arrange": ["桌面图标整理一下~", "图标排排队，整齐了"],
    "music_next": ["好嘞，切下一首", "下一首来咯{who}", "这首跳过，听下一首"],
    "music_prev": ["回到上一首~", "好的，上一首"],
    "music_pause": ["好的，先暂停一下", "音乐暂停啦"],
    "music_play": ["继续放歌~", "好嘞，接着播放"],
    "notepad_type": ["好嘞，在记事本里给你写下来", "记事本交给我，马上写"],
    "qq_send": ["好，帮{who}在群里发一句", "收到，替你在群聊里发出去"],
    "cmd_run": ["在命令提示符里敲一下", "好嘞，黑框框里输入"],
    "calc": ["拿计算器给你算算", "计算器启动，这就算"],
    "game_start": ["好嘞{who}，开{t}，开打！", "{t}启动，进游戏啦", "来一把{t}，走起~"],
    "game_back": ["好的，回{t}主菜单", "退回主菜单啦"],
    "mine_play": ["扫雷我来玩，看我操作", "好，开一把扫雷，我来排雷", "{who}看好了，扫雷启动"],
    "mine_new": ["扫雷开新局~", "好嘞，重新来一局扫雷"],
    "mine_click": ["好，点这一格", "收到，扫雷点一下"],
    "mine_flag": ["好，这格插个旗", "收到，插旗标记"],
    "sol_play": ["纸牌我来玩，看我拖牌", "好嘞，来一把纸牌，{who}看好了", "发牌发牌，纸牌启动~"],
    "sol_new": ["纸牌重新发牌~", "好嘞，换一副新牌"],
    "fc_play": ["空当接龙，我来试试能不能解开", "好，来一局空当接龙，看我摆牌", "{who}看好了，空当接龙启动~"],
    "fc_new": ["空当接龙换一局新的~", "好嘞，换个编号开新局"],
    "paint_draw": ["画图打开，我来画一个", "好嘞{who}，看我画~", "画笔拿起来，开画"],
    "paint_tool": ["换个画图工具", "好，选这个工具"],
    "paint_color": ["换个颜色", "好，颜料盒里选一个"],
    "pet_feed": ["开饭啦~球球吃得好香", "好嘞，给宠物喂吃的", "{who}说喂就喂，企鹅开心坏了"],
    "pet_bath": ["洗白白~泡泡飞起来", "好嘞，给企鹅洗个澡", "{who}，洗澡中，别偷看"],
    "pet_play": ["来，陪企鹅玩一会儿", "玩耍时间到！", "好嘞，逗逗它"],
    "pet_sleep": ["嘘~企鹅要睡觉了", "好的，哄宠物睡觉"],
    "pet_sing": ["企鹅要开嗓啦~", "好嘞，让宠物唱一段"],
    "outfit_change": ["好嘞，QQ秀换一身！", "{who}点的造型，马上换", "换装时间~看我的新造型"],
    "zone_blog": ["日志写好发表啦，去空间看看", "好嘞，{who}的话我记到空间日志里了"],
    "zone_msg": ["留言已经踩在空间啦", "好的，给空间留了一条言"],
    "zone_open": ["QQ空间打开，看看有啥新鲜事", "好嘞，去空间逛逛"],
    "files_download": ["群共享里找到了，丢给迅雷下载", "好嘞，迅雷开冲"],
    "fx_fireworks": ["烟花来咯！", "砰砰砰，放烟花~", "{who}要的烟花，满屏安排"],
    "fx_meteor": ["流星雨！快许愿~", "来了来了，流星雨", "{who}点的流星雨，抬头看"],
    "fx_emoji": ["表情雨，接好了！", "撒花撒花~", "满屏表情安排"],
    "fx_virus": ["哎呀，电脑中毒啦！（别怕，几秒就好）", "熊猫烧香来咯，纯演戏哈", "检测到病毒…开玩笑的，马上恢复"],
    "game_start": ["游戏时间到！", "好嘞，{who}要玩，那就来一局", "来来来，开局开局"],
    "game_stop": ["好的，游戏到此结束", "收到，不玩了~"],
    "screen_comment": ["我来说说屏幕上的事~", "{who}想听我点评，来了"],
    "song_comment": ["这首歌嘛，我来聊两句", "好嘞，点评一下这首歌"],
    "rank_open": ["排行榜打开，看看谁是榜一", "来看看今天的积分榜~", "好嘞，排行榜给大家看看"],
    "shake": ["抖起来！", "收到，来个窗口抖动~", "{who}要的抖动，满足你"],
    "paint_clear": ["画布清空，重新来~", "好，擦干净重画"],
    "control_open": ["控制面板打开，找一下~", "好嘞，去控制面板里看看"],
    "bsod": ["哎呀，Windows 蓝屏了！", "蓝屏彩蛋，触发~"],
    "balloon": ["托盘冒个泡~", "右下角有通知啦"],
    "video_play": ["暴风影音，放起来~", "好嘞，来个视频看看"],
    "video_toggle": ["视频暂停/播放，切换啦", "好的，按一下播放键"],
    "mir2_chat": ["好，传奇里喊一句", "收到，游戏里发话"],
    "dance": ["劲舞团，我来跳一段", "按起方向键，跳起来~"],
    "volume": ["音量调好啦", "好嘞，调一下音量"],
    "mute": ["好，静音", "声音关掉啦"],
    "unmute": ["声音打开啦", "好的，取消静音"],
    "browse": ["IE 打开网页，冲浪咯", "好嘞，上网看看"],
    "undo": ["好的，撤销刚才的", "刚才那步我撤回啦"],
    "song": ["收到，{who}点的歌安排上~", "好嘞，给{who}排上"],
    "dance2": [],
}
NO_WIN = ["{t}根本没开着呀，要打开就说「打开{t}」", "{who}，{t}没在桌面上哦"]
NO_BLOCK = ["我看了一圈，没有窗口挡着呀", "{who}，没看到有东西挡着呀，是我眼花了？"]
CMD_OK = {"ver", "dir", "ipconfig", "date", "time", "echo", "help", "cls", "ping"}
SITE_OK = re.compile(r"^(?:https?://)?(?:[a-z0-9\-]+\.)*(?:hao123\.com|sina\.com\.cn|sohu\.com|163\.com|taobao\.com|google\.(?:cn|com)|youku\.com|4399\.com|xunlei\.com|joy\.cn|ctrip\.com|58\.com|17173\.com|tianya\.cn|baidu\.com|qq\.com)(?:/\S*)?$", re.I)
NICK_KEEP = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9 ·\-_.]")


def nick(name):
    n = NICK_KEEP.sub("", name or "").strip()[:8]
    return n or "这位朋友"


class Agent:
    def __init__(self, cfg, app, log=print):
        self.cfg, self.app, self.log = cfg, app, log
        self.clients = {}                # ws -> {"snap": dict, "at": ts}
        self.snap_ws = None
        self.user_hist = {}              # uid -> deque[ts]
        self.user_last = {}              # uid -> (norm text, ts)
        self.glob = deque()
        self.last_global = 0.0
        self.pending = {}                # job id -> ts
        self.hist = deque(maxlen=60)     # 最近处理的指令（/agent/state）
        self.seq = 0
        self.idle = None                 # 冷场自己玩电脑（idle.py），server 里挂上
        self.stats = {"rule": 0, "llm": 0, "llm_none": 0, "rejected": 0, "limited": 0, "dispatched": 0}

    # ------------------------------------------------------------ 配置
    def on(self):
        return self.cfg.b("agent", "enabled")

    def page_cfg(self):
        c = self.cfg
        return {"enabled": self.on(), "cursor_speed": c.f("agent", "cursor_speed"), "click_delay": c.f("agent", "click_delay"),
                "typing_cps": c.f("agent", "typing_cps"), "step_pause": c.f("agent", "step_pause"), "show_who": c.b("agent", "show_who"),
                "cursor_idle_hide": c.f("agent", "cursor_idle_hide"), "protect": R.split_list(c.s("agent", "protect")),
                "restore_secs": c.f("agent", "restore_secs"), "undo": c.b("agent", "undo"), "queue_max": c.i("agent", "queue_max"),
                "idle_cleanup": c.b("idle", "cleanup"), "idle_avoid_cover": c.b("idle", "avoid_cover")}

    # ------------------------------------------------------------ 页面连接
    def add_client(self, ws):
        self.clients[ws] = {"snap": None, "at": 0}
        return self.page_cfg()

    def drop_client(self, ws):
        self.clients.pop(ws, None)
        if self.snap_ws is ws:
            self.snap_ws = None

    def set_snap(self, ws, snap):
        if ws in self.clients and isinstance(snap, dict):
            self.clients[ws].update(snap=snap, at=time.time())
            self.snap_ws = ws

    def desk(self):
        c = self.clients.get(self.snap_ws)
        return Desk(c["snap"] if c else None)

    def job_done(self, res):
        if self.idle is not None:
            self.idle.on_result(res)
        self.pending.pop((res or {}).get("id"), None)
        for h in self.hist:
            if h.get("job") == (res or {}).get("id"):
                h["result"] = (res or {}).get("results")
                h["page_ms"] = (res or {}).get("ms")

    # ------------------------------------------------------------ 谁能指挥 / 限速
    def who_ok(self, ev, room=None):
        c = self.cfg
        name, uid = ev.get("name") or "", str(ev.get("uid") or "")
        deny = [R.norm(x) for x in R.split_list(c.s("agent", "deny_users"))]
        if R.norm(name) in deny or uid in deny:
            return False
        who = c.s("agent", "who").lower()
        if who == "everyone":
            return True
        names = [R.norm(x) for x in R.split_list(c.s("agent", "anchor_names"))]
        if who == "anchor":
            anchor = ((room.last.get("room") or {}).get("anchor") if room is not None and hasattr(room, "last") else "") or ""
            return bool(R.norm(name)) and (R.norm(name) == R.norm(anchor) or R.norm(name) in names or uid in names)
        if who == "list":
            allow = [R.norm(x) for x in R.split_list(c.s("agent", "allow_users"))] + names
            return R.norm(name) in allow or uid in allow
        return True

    def limit_check(self, uid, text, now=None):
        """-> (ok, reason)。通过时记账。"""
        now = now or time.time()
        c = self.cfg
        h = self.user_hist.setdefault(uid, deque())
        while h and now - h[0] > 60:
            h.popleft()
        while self.glob and now - self.glob[0] > 60:
            self.glob.popleft()
        n = R.norm(text)
        last = self.user_last.get(uid)
        if last and last[0] == n and now - last[1] < c.f("agent", "dedupe_seconds"):
            return False, "重复"
        if h and now - h[-1] < c.f("agent", "user_cooldown"):
            return False, "用户冷却"
        if len(h) >= c.i("agent", "user_per_min"):
            return False, "用户每分钟上限"
        if now - self.last_global < c.f("agent", "global_cooldown"):
            return False, "全局冷却"
        if len(self.glob) >= c.i("agent", "global_per_min"):
            return False, "全局每分钟上限"
        for k in [k for k, t in self.pending.items() if now - t > 90]:
            self.pending.pop(k, None)
        if len(self.pending) >= c.i("agent", "queue_max"):
            return False, "页面排队太多"
        h.append(now)
        self.glob.append(now)
        self.last_global = now
        self.user_last[uid] = (n, now)
        return True, ""

    # ------------------------------------------------------------ 主入口
    def on_chat(self, ev, room):
        """Room._broadcast 里调用。返回 True = 这条弹幕被当成指令处理了（别再交给 AI 主播闲聊）。"""
        if not self.on() or ev.get("t") != "chat":
            return False
        text = (ev.get("text") or "").strip()
        if not text or not self.clients:
            return False                          # 没有页面能执行，就当普通聊天
        if not self.who_ok(ev, room):
            return False
        desk = self.desk()
        it = rules.parse(text, desk) if self.cfg.b("agent", "rules") else None
        if it and it.skip:
            return False
        use_llm = False
        if it is None and self.cfg.b("agent", "llm") and self.cfg.ai_enabled:
            gate = self.cfg.s("agent", "llm_gate").lower()
            name = self.cfg.s("host", "name")
            use_llm = gate == "all" or (gate == "mention" and name in text) or (gate == "keywords" and rules.looks_like_command(text, name))
        if it is None and not use_llm:
            return False
        uid = str(ev.get("uid") or ev.get("name") or "?")
        ok, why = self.limit_check(uid, text)
        if not ok:
            self.stats["limited"] += 1
            self.log(f"[agent] 限速忽略（{why}）{nick(ev.get('name'))}：{text[:30]}")
            return True
        loop = asyncio.get_running_loop()
        loop.create_task(self._run(ev, room, text, it, desk))
        return True

    async def _run(self, ev, room, text, it, desk, dry=False, out=None):
        t0 = time.time()
        user = nick(ev.get("name"))
        via, say, emo, actions, note = "rule", "", "开心", [], ""
        try:
            if it is not None:
                actions, emo = it.actions, it.emotion
                self.stats["rule"] += 1
            else:
                via = "llm"
                r = await asyncio.get_running_loop().run_in_executor(None, lambda: llm.ask(self.cfg, desk, user, text, name=self.cfg.s("host", "name")))
                say, emo, actions = r["say"], r["emotion"], r["actions"]
                note = f"{r['mode']} {r['ms']}ms"
                if not actions:
                    self.stats["llm_none"] += 1
                    self.log(f"[agent] LLM：不是指令（{note}）{user}：{text[:30]}")
                    self._record(ev, text, via, [], "", "非指令", t0, note)
                    if out is not None:
                        out.update(via=via, actions=[], say=say, note=note, handled=False, ms=int((time.time() - t0) * 1000))
                    if not dry and room is not None and getattr(room, "host", None):
                        room.host.feed(ev)        # 当作普通聊天
                    return
                self.stats["llm"] += 1
        except Exception as e:  # noqa
            self.log(f"[agent] LLM 失败（{e!r}）{user}：{text[:30]}")
            self._record(ev, text, via, [], "", f"LLM 失败 {e!r}", t0, "")
            if out is not None:
                out.update(via=via, actions=[], say="", note=f"LLM 失败 {e!r}"[:200], handled=False, ms=int((time.time() - t0) * 1000))
            if not dry and room is not None and getattr(room, "host", None):
                room.host.feed(ev)
            return
        good, errs, say2 = self.validate(actions, desk, user, it)
        if not say and say2:
            say = say2
        if good and not say and via == "rule":
            say = self.reply_for(it, good, user)
        if via == "llm" and good and not say:
            say = self.reply_for(None, good, user)
        res = {"via": via, "actions": good, "rejected": errs, "say": say, "emotion": emo, "note": note, "handled": bool(good or say),
               "ms": int((time.time() - t0) * 1000)}
        if out is not None:
            out.update(res)
        if dry:
            return
        self._record(ev, text, via, good, say, "; ".join(errs), t0, note)
        if good:
            await self.execute(good, ev, room, text, user)
        if say and self.cfg.b("agent", "reply") and (good or via == "llm" or self.cfg.b("agent", "say_unknown")):
            self.say(room, say, emo)
        if not good and not say and room is not None and getattr(room, "host", None):
            room.host.feed(ev)

    def _record(self, ev, text, via, actions, say, note, t0, extra):
        self.seq += 1
        self.hist.append({"n": self.seq, "ts": int(time.time() * 1000), "user": nick(ev.get("name")), "text": text[:60], "via": via,
                          "actions": [a.get("action") for a in actions], "say": say[:60], "note": note[:120], "ms": int((time.time() - t0) * 1000), "extra": extra})

    # ------------------------------------------------------------ 校验
    def validate(self, actions, desk, user, it=None, viewer=True, trust=()):
        """-> (动作列表, 被拒原因列表, 想对观众说的话)。窗口目标找不到 / 没有挡路的窗口：不执行，给说明。"""
        c = self.cfg
        good, errs, say = [], [], ""
        allow, deny = c.s("agent", "allow_actions"), c.s("agent", "deny_actions")
        mx_t = c.i("agent", "max_text")
        for raw in (actions or [])[: c.i("agent", "max_actions") + 4]:
            name = str(raw.get("action") or "").strip()
            if len(good) >= c.i("agent", "max_actions"):
                errs.append("超过单次动作上限")
                break
            if name not in R.ACTIONS:
                errs.append(f"未知动作 {name}")
                continue
            if name not in trust and not R.allowed(name, allow, deny):      # trust：主播自己的表演（perform.py）可以越过 deny_actions（比如页面里的假重启）
                errs.append(f"动作 {name} 被禁用")
                continue
            if name in R.HOST_ONLY and viewer:
                errs.append(f"动作 {name} 只有主播自己能用")
                continue
            if name in R.PLAY_ACTIONS and not (c.b("play", "enabled") and (c.b("play", "commands") or not viewer)):
                errs.append(f"动作 {name} 被禁用（[play] commands 关了）" if viewer else f"动作 {name} 被禁用（[play] enabled 关了）")
                continue
            if name in R.AIPLUS_ACTIONS:
                k = R.AIPLUS_ACTIONS[name]
                if not (c.b("ai_plus", "enabled") and c.b("ai_plus", k) and (not viewer or name != "screen_comment" or c.b("ai_plus", "screen_cmd"))):
                    errs.append(f"动作 {name} 被禁用（[ai_plus] {k} 关了）")
                    continue
            if name in R.QQ_ACTIONS and not (c.b("qq", "enabled") and (c.b("qq", "commands") or not viewer)):   # 自己玩电脑（idle）不受 commands 管，只受 enabled
                errs.append(f"动作 {name} 被禁用（[qq] commands 关了）" if viewer else f"动作 {name} 被禁用（[qq] enabled 关了）")
                continue
            args, err = R.coerce(name, {k: v for k, v in raw.items() if k != "action"}, mx_t)
            if err:
                errs.append(err)
                continue
            err = self._sanitize(name, args)
            if err:
                errs.append(err)
                continue
            if name in ("qq_send", "zone_msg"):
                args["text"] = self._qq_prefix(user, args["text"])
            if name == "zone_blog":
                args["title"] = args["title"].strip()[:20] or "今天的日志"
                args["text"] = self._qq_prefix(user, args["text"])
            if name == "outfit_change":
                nm = str(args.get("name") or "next").strip()
                args["name"] = nm[:12]
            if name == "files_download" and args.get("name"):
                args["name"] = str(args["name"]).strip()[:16]
            # 目标存在性（页面没上报快照时放行，由页面再判断）
            tgt = args.get("target")
            if tgt is not None and desk.known and name in ("close_window", "minimize_window", "maximize_window", "restore_window", "focus_window", "move_window", "resize_window", "move_away"):
                found = desk.find(tgt)
                if not found and tgt not in ("all",):
                    nm = R.app_label(R.find_app(tgt)) if R.find_app(tgt) else tgt
                    if tgt == "blocking":
                        say = say or random.choice(NO_BLOCK).format(who=user)
                    else:
                        say = say or random.choice(NO_WIN).format(who=user, t=nm)
                    errs.append(f"{name}: 没有窗口 {tgt}")
                    continue
                if name != "close_window" or True:
                    args["target"] = found[0]["id"] if (found and tgt not in ("all", "blocking")) else tgt
            if name == "move_away" and desk.known and not args.get("target") and not desk.blockers():
                say = say or random.choice(NO_BLOCK).format(who=user)
                errs.append("move_away: 没有窗口挡路")
                continue
            good.append({"action": name, **args})
        return good, errs, say

    def _sanitize(self, name, args):
        host = getattr(self.app, "any_host", lambda: None)()
        for k in ("text", "name", "query"):
            v = args.get(k)
            if v and host is not None and (host.bl_in(v) or host.bl_out(v)):
                return f"{name}: 内容命中屏蔽词"
            if v and re.search(r"(https?://|www\.|\.com|微信|vx|wx|加我|私信)", v, re.I) and name in ("notepad_type", "qq_send", "mir2_chat", "qq_private", "zone_blog", "zone_msg"):
                return f"{name}: 内容像广告/联系方式"
        if name == "cmd_run":
            cmd = args["command"].strip().split()
            if not cmd or cmd[0].lower() not in CMD_OK:
                return f"cmd_run: 不允许的命令 {cmd[:1]}"
            args["command"] = " ".join(cmd)[:40]
        if name == "calc":
            e = re.sub(r"\s", "", args["expr"])
            if not re.fullmatch(r"[0-9+\-*/.()]{1,30}", e) or not re.search(r"\d", e):
                return "calc: 算式不合法"
            args["expr"] = e
        if name == "browse":
            u = args["url"].strip()
            if not SITE_OK.match(u):
                return "browse: 只允许 IE 里的常见站点"
            args["url"] = u if re.match(r"https?://", u, re.I) else "http://" + u
        if name in ("mine_click", "mine_flag"):
            if not (1 <= args["row"] <= 16 and 1 <= args["col"] <= 30):
                return f"{name}: 行列超范围"
        if name in ("mine_play", "sol_play", "fc_play"):
            args["steps"] = max(1, min(30 if name == "mine_play" else 40, args.get("steps") or 10))
        if name == "sol_new" and args.get("draw") not in (None, 1, 3):
            args["draw"] = 3 if args["draw"] > 1 else 1
        if name == "fc_new" and args.get("no") is not None and not (1 <= args["no"] <= 32000):
            args.pop("no")
        if name in ("paint_color", "control_open") and len(str(args.get("color") or args.get("item") or "")) > 12:
            return f"{name}: 参数太长"
        if name == "dance":
            args["count"] = max(1, min(20, args.get("count") or 8))
        if name == "set_volume" and "value" in args:
            args["value"] = max(0, min(100, args["value"]))
        if name == "move_window" and "to" in args and not re.fullmatch(r"(left|right|top|bottom|center|topleft|topright|bottomleft|bottomright|away|-?\d{1,4}\s*,\s*-?\d{1,4})", args["to"].lower().replace(" ", "")):
            if "x" not in args:
                return "move_window: to 不认识"
        if name == "open_app" and args.get("url") and not SITE_OK.match(args["url"]):
            args.pop("url")
        return None

    def _qq_prefix(self, user, text):
        p = self.cfg.s("agent", "qq_send_prefix")
        return (p.replace("{name}", user) + text)[: self.cfg.i("agent", "max_text") + 16] if p else text

    # ------------------------------------------------------------ 回复
    def reply_for(self, it, actions, user):
        rule = it.rule if it is not None else self._rule_of(actions[0]["action"])
        if rule == "wallpaper" and (it.t if it is not None else actions[0].get("name")) not in ("", "壁纸", "next", "random", None):
            rule = "wallpaper_named"
        tpl = TEMPLATES.get(rule) or TEMPLATES.get(rule.replace("minimize_window", "min")) or ["好嘞，办好啦"]
        t = (it.t if it is not None else "") or (actions[0].get("name") if actions[0].get("action") == "change_wallpaper" else "") or R.app_label(actions[0].get("app") or actions[0].get("target") or "") or ""
        s = random.choice(tpl).format(who=user, t=t)
        return s[: self.cfg.i("behavior", "max_chars")]

    @staticmethod
    def _rule_of(a):
        return {"close_window": "close", "minimize_window": "min", "maximize_window": "max", "restore_window": "restore", "move_window": "move",
                "open_app": "open", "focus_window": "focus", "change_wallpaper": "wallpaper", "refresh_desktop": "refresh", "arrange_icons": "arrange",
                "set_volume": "volume", "song_request": "song"}.get(a, a)

    def say(self, room, text, emotion="开心", kind="agent", role=""):
        """让猪猪侠说一句（TTS 在线程里合成）。没有 host 就只发 say 事件（页面会显示气泡/群消息）。"""
        loop = asyncio.get_running_loop()
        host = getattr(room, "host", None) if room is not None else None
        if host is None:
            host = getattr(self.app, "any_host", lambda: None)()
        if host is not None:
            loop.run_in_executor(None, lambda: host._say(kind, 65, text, emotion, role=role))
        elif room is not None:
            room._broadcast({"t": "say", "id": f"ag{int(time.time()*1000)}", "kind": kind, "prio": 65, "text": text, "emotion": emotion, "role": role,
                             "audio": "", "dur": max(1.8, len(text) * 0.28), "name": self.cfg.s("host", "name"), "ts": int(time.time() * 1000)})

    # ------------------------------------------------------------ 执行
    async def execute(self, actions, ev, room, text, user):
        """后端动作（切歌/点歌）当场做；其余整批推给页面。"""
        ops = getattr(self.app, "ops", None)
        if ops is not None:
            ops.record("agent", user=user, text=(text or "")[:60], actions=[a["action"] for a in actions if not a["action"].startswith("_")])
        page = []
        for a in actions:
            n = a["action"]
            if n.startswith("music_"):
                await self.music_cmd(n)
                page.append(a)                  # 页面里再演一遍“点千千静听的按钮”
            elif n in ("vote_start", "vote_end"):
                pl = getattr(self.app, "play", None)
                if pl is not None:
                    pl.agent_action(a, ev, room, user)
            elif n in R.AIPLUS_ACTIONS:
                pl = getattr(self.app, "plus", None)
                if pl is not None:
                    ok, msg = pl.agent_action(a, ev, room, user)
                    if not ok and msg:
                        pl.sysline(room, f"【AI】{msg}")
            elif n == "song_request":
                self.song(a["query"], ev, room)
                page.append(a)
            else:
                page.append(a)
        if not page:
            return
        if self.idle is not None:
            self.idle.note_command()           # 观众指令来了：猪猪侠自己玩电脑立刻停手
        self.stats["dispatched"] += 1
        self.seq += 1
        job = f"j{self.seq}"
        if self.hist:
            self.hist[-1]["job"] = job
        self.pending[job] = time.time()
        msg = {"t": "agent_do", "id": job, "by": user, "text": text[:40], "actions": page}
        await self.send_pages(msg)

    async def send_pages(self, msg):
        import json
        data = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.clients):
            try:
                await ws.send_str(data)
            except Exception:
                self.drop_client(ws)

    async def music_cmd(self, name):
        jb = getattr(self.app, "jukebox", None)
        if jb is None:
            self.log("[agent] 音乐没开启，忽略", name)
            return False
        cmd = {"music_next": "next", "music_prev": "previous", "music_pause": "pause", "music_play": "play", "music_toggle": "toggle"}[name]
        try:
            if cmd == "next":
                await jb.skip()
                return True
            return await jb.control.command(cmd)
        except Exception as e:  # noqa
            self.log(f"[agent] {name} 失败：{e!r}")
            return False

    def song(self, query, ev, room):
        jb = getattr(self.app, "jukebox", None)
        if jb is None:
            return
        e2 = dict(ev)
        e2["text"] = "点歌 " + query
        jb.on_chat(e2, room)

    # ------------------------------------------------------------ 测试 / 调试
    async def simulate(self, text, name="测试观众", uid="test1", dry=True, force=False, room=None, via=None):
        """给 /agent/test 用：不走限速（force），返回解析结果。dry=True 不执行不说话。via=rule|llm 强制路径。"""
        ev = {"t": "chat", "uid": uid, "name": name, "text": text, "ts": int(time.time() * 1000)}
        desk = self.desk()
        out = {"text": text}
        it = None if via == "llm" else rules.parse(text, desk)
        if it is not None and it.skip:
            out.update(via="rule", skip=True, actions=[], handled=False)
            return out
        if it is None and via == "rule":
            out.update(via="rule", actions=[], handled=False)
            return out
        if not force and not dry:
            ok, why = self.limit_check(uid, text)
            if not ok:
                out.update(via="limited", actions=[], handled=False, note=why)
                return out
        await self._run(ev, room, text, it, desk, dry=dry, out=out)
        return out

    def state(self):
        c = self.cfg
        return {"enabled": self.on(), "clients": len(self.clients), "who": c.s("agent", "who"), "stats": self.stats, "pending": len(self.pending),
                "deny_actions": c.s("agent", "deny_actions"), "allow_actions": c.s("agent", "allow_actions"), "history": list(self.hist)[-20:],
                "desk": (self.desk().s if self.snap_ws else None), "idle": (self.idle.state() if self.idle else None)}

    def song_visual(self, ev, room):
        """真实的“点歌 xxx”弹幕已由 Jukebox 处理；这里只让页面里的光标演一遍（点开千千静听播放列表）。"""
        if not self.on() or not self.clients or not self.cfg.b("agent", "song_visual") or not R.allowed("song_request", self.cfg.s("agent", "allow_actions"), self.cfg.s("agent", "deny_actions")):
            return
        if not self.who_ok(ev, room):
            return
        q = re.sub(r"^\s*(?:点歌|点播|来一首|来首|点一首|点首)\s*", "", ev.get("text") or "")[:30]
        self.seq += 1
        job = f"j{self.seq}"
        self.pending[job] = time.time()
        asyncio.get_running_loop().create_task(self.send_pages({"t": "agent_do", "id": job, "by": nick(ev.get("name")), "text": (ev.get("text") or "")[:40],
                                                                "actions": [{"action": "song_request", "query": q, "visual": True}]}))
