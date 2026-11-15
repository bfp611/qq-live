# -*- coding: utf-8 -*-
"""冷场「表演」：猪猪侠先说一句开场白（TTS + 群聊里就是主播这句话），再走 agent 管线真的做一遍（光标动、窗口开关、特效），
最后可以补一句「💡 你们也可以发『来个蓝屏』」教观众怎么玩。

它们是 idle（冷场自己玩电脑）的活动：名字叫 perf_<id>，权重在 [perform] weights，和其它活动一起随机挑；
受 idle 的所有限制管着（观众一开口立刻打断、间隔、每小时上限、主播说话时不抢话）。额外的限制：
  - [perform] enabled = false 关掉全部表演（面板「冷场表演」开关）；
  - gap：任意两场表演之间至少隔这么久（默认 240 秒）；
  - heavy_gap：蓝屏 / 重启这类「整个屏幕变样」的，两场之间至少隔这么久（默认 600 秒，蓝屏 + 重启共用）；
  - 蓝屏要 [xp] bsod 开着，重启要 [xp] shutdown_screens 开着；每个动作还要过 agent 的校验（开关 / 当前桌面状态），不满足的这次不会被选中。
重启是 **页面里的 XP 桌面假重启**（关机画面 → 开机画面 → 回桌面），不碰真实电脑。
items：自定义台词，「台词=动作」用 | 分隔，如  给大家表演一个蓝屏=bsod|电脑太卡了，我重启一下=restart；留空 = 用内置台词。"""
import random
import re
import time

from . import registry as R

# id: (台词们, 提示命令(None=观众没有对应口令), 默认权重, 重型(整屏变样), 说明)
PERFS = {
    "bsod": (["给大家表演一个蓝屏", "来，表演一个经典的 Windows 蓝屏"], "来个蓝屏", 0.4, True, "蓝屏"),
    "restart": (["电脑太卡了，我重启一下", "好卡啊，让我重启一下电脑"], None, 0.3, True, "重启（XP 开关机动画）"),
    "virus": (["给大家表演一个熊猫烧香", "来，表演一段怀旧的熊猫烧香"], "熊猫烧香", 0.5, False, "熊猫烧香（假中毒）"),
    "fireworks": (["来，放个烟花庆祝一下", "放个烟花，热闹热闹"], "放烟花", 1.0, False, "烟花"),
    "meteor": (["来个流星雨给大家看看", "看，流星雨"], "来个流星雨", 0.5, False, "流星雨"),
    "mine": (["我来扫个雷给你们看", "给你们表演一下扫雷"], "玩扫雷", 1.0, False, "扫雷"),
    "paint": (["给大家画个画", "我来画个画给你们看"], "画个{what}", 1.0, False, "画图画画（之后自动关窗）"),
    "wall": (["给大家换个新壁纸", "桌面太旧了，换个新壁纸"], "换壁纸", 0.7, False, "换壁纸"),
    "shake": (["我抖一下窗口", "来，抖一抖窗口"], "抖一下", 0.6, False, "窗口抖动"),
    "pet": (["给球球喂个饭", "球球饿了，我去喂它"], "喂食", 0.7, False, "喂 QQ 宠物"),
    "setup": (["电脑中毒太严重了，我重装个系统", "系统越用越卡，干脆重装一个"], None, 0.0, True, "重装系统（XP 安装画面，页面里的假重装；默认只在大额礼物时演，权重 0）"),
}
NAMES = {f"perf_{k}": k for k in PERFS}
HEAVY = {k for k, v in PERFS.items() if v[3]}
DEFAULT_WEIGHTS = ",".join(f"{k}:{v[2]}" for k, v in PERFS.items())
PAINT_WHAT = {"smile": "笑脸", "house": "房子", "sun": "太阳", "flower": "花", "heart": "爱心", "star": "星星", "tree": "树", "boat": "小船"}


def parse_items(s):
    """「台词=动作|台词=动作」→ {动作: [台词...]}；动作不认识的丢掉"""
    out = {}
    for part in re.split(r"[|｜\n;；]+", s or ""):
        if "=" not in part:
            continue
        txt, k = part.rsplit("=", 1)
        txt, k = txt.strip(), k.strip().lower()
        if txt and k in PERFS:
            out.setdefault(k, []).append(txt)
    return out


def intros_of(cfg, k):
    custom = parse_items(cfg.s("perform", "items"))
    if k in custom:
        return custom[k]
    return list(PERFS[k][0]) if cfg.b("perform", "builtin") else []


def weights(cfg):
    """perf_<id> 的权重（并进 idle 的权重表）；perform_weights 里没写的用默认值"""
    from .idle import parse_weights
    w = parse_weights(DEFAULT_WEIGHTS)
    w.update({k: v for k, v in parse_weights(cfg.s("perform", "weights")).items() if k in PERFS})
    return {f"perf_{k}": v for k, v in w.items()}


def tip_cmd(k, what=None):
    c = PERFS[k][1]
    if c is None:
        return None
    return c.format(what=what or "太阳")


def _okact(ctx, acts, trust=()):
    """这批动作现在能不能做（开关 / 桌面状态）"""
    try:
        good, errs, _ = ctx.idle.agent.validate(acts, ctx.desk, "猪猪侠", viewer=False, trust=trust)
    except Exception:
        return False
    return len(good) == len(acts) and not errs


def gate(ctx, k):
    """全局限制：开关 / 间隔 / 重型冷却。手动触发（forced）不看开关和间隔"""
    idle, c = ctx.idle, ctx.cfg
    if getattr(idle, "perf_force", None) == k:
        return True
    if not c.b("perform", "enabled"):
        return False
    now = time.time()
    if now - getattr(idle, "perf_at", 0) < c.f("perform", "gap"):
        return False
    if k in HEAVY and now - getattr(idle, "perf_heavy_at", 0) < c.f("perform", "heavy_gap"):
        return False
    return True


def plan(ctx, k):
    """返回 beats 或 None。beat 格式同 idle.B"""
    from .idle import B, clear
    c = ctx.cfg
    if not gate(ctx, k):
        return None
    intros = intros_of(c, k)
    if not intros:
        return None
    pause = {"action": "_wait", "secs": 2.2}          # 等开场白说完再动手
    beats = None
    if k == "bsod":
        if not (c.b("xp", "enabled") and c.b("xp", "bsod")) or not _okact(ctx, [{"action": "bsod"}]):
            return None
        beats = [B("intro", [pause]), B(None, [{"action": "bsod"}], "惊讶", critical=True), B(None, [{"action": "_wait", "secs": max(2.0, c.f("xp", "bsod_secs")) + 4}], "平静")]
    elif k == "restart":
        if not (c.b("xp", "enabled") and c.b("xp", "shutdown_screens")) or not _okact(ctx, [{"action": "shutdown", "mode": "restart"}], trust=("shutdown",)):
            return None
        wait = 3.6 + 0.7 + c.f("xp", "boot_secs") + (c.f("xp", "welcome_secs") if c.b("xp", "welcome") else 0) + 3
        beats = [B("intro", [pause]), B(None, [{"action": "shutdown", "mode": "restart"}], "平静", critical=True), B(None, [{"action": "_wait", "secs": wait}], "平静")]
    elif k in ("virus", "fireworks", "meteor"):
        kind = {"virus": "virus", "fireworks": "fireworks", "meteor": "meteor"}[k]
        a = {"action": "play_fx", "kind": kind}
        if not _okact(ctx, [a]):
            return None
        beats = [B("intro", [pause]), B(None, [a], "兴奋", critical=True), B(None, [{"action": "_wait", "secs": 7}], "开心")]
    elif k == "mine":
        if "minesweeper" in ctx.apps:
            return None
        n = max(4, c.i("idle", "mine_steps"))
        beats = [B("intro", [{"action": "open_app", "app": "minesweeper"}, clear(), {"action": "mine_new", "level": "beginner"}], critical=True),
                 B(None, [{"action": "mine_play", "steps": n}], "得意"), B(None, [{"action": "_wait", "secs": 1.5}], "开心")]
    elif k == "paint":
        if "paint" in ctx.apps:
            return None
        w = random.choice(list(PAINT_WHAT))
        ctx.fmt["what"] = PAINT_WHAT[w]
        d = {"action": "paint_draw", "what": w}
        if w in ("flower", "heart", "boat", "house", "tree"):
            d["color"] = random.choice(["红", "蓝", "粉", "橙", "紫", "黄"] if w != "tree" else ["深绿", "草绿"])
        beats = [B("intro", [{"action": "open_app", "app": "paint"}, clear()], "平静", critical=True), B(None, [d], "得意"), B(None, [{"action": "_wait", "secs": 2.5}], "开心")]
    elif k == "wall":
        beats = [B("intro", [pause]), B(None, [{"action": "change_wallpaper", "name": "random"}], "兴奋", critical=True), B(None, [{"action": "_wait", "secs": 2}], "开心")]
    elif k == "shake":
        if not (c.b("qq", "enabled") and c.b("qq", "shake")):
            return None
        beats = [B("intro", [pause]), B(None, [{"action": "shake", "target": "chat"}], "开心", critical=True), B(None, [{"action": "_wait", "secs": 1.5}], "开心")]
    elif k == "pet":
        if not (c.b("qq", "enabled") and c.b("qq", "pet")):
            return None
        beats = [B("intro", [pause]), B(None, [{"action": "pet_care", "what": "feed", "food": random.choice(["apple", "fish", "cake", "drumstick"])}], "开心", critical=True),
                 B(None, [{"action": "_wait", "secs": 2.5}], "开心")]
    elif k == "setup":
        if not (c.b("xp", "enabled") and c.b("xp", "shutdown_screens")) or not _okact(ctx, [{"action": "gift_fx", "kind": "setup"}]):
            return None
        wait = c.f("xp", "setup_secs") + 0.7 + c.f("xp", "boot_secs") + (c.f("xp", "welcome_secs") if c.b("xp", "welcome") else 0) + 3
        beats = [B("intro", [pause]), B(None, [{"action": "gift_fx", "kind": "setup"}], "平静", critical=True), B(None, [{"action": "_wait", "secs": wait}], "平静")]
        th = getattr(ctx.idle, "perf_thanks", None)              # 大额礼物触发的：装完再来一张全屏感谢卡片
        if th:
            beats.append(B(None, [dict(th, action="gift_fx", kind="thanks")], "兴奋"))
            beats.append(B(None, [{"action": "_wait", "secs": 5}], "开心"))
    if beats is None:
        return None
    ctx.fmt["_intro"] = (getattr(ctx.idle, "perf_prefix", "") or "") + random.choice(intros)
    ctx.fmt["_perf"] = k
    return beats


def on_start(idle, name):
    """活动真的开始跑了：记时间（间隔 / 重型冷却从这里算）"""
    k = NAMES.get(name)
    if not k:
        return
    now = time.time()
    idle.perf_at = now
    if k in HEAVY:
        idle.perf_heavy_at = now
    idle.perf_force = None


def after(idle, name, ctx_fmt):
    """做完了：补一句「你们也可以发『…』」"""
    k = NAMES.get(name)
    if not k:
        return None
    tips = getattr(idle.app, "tips", None)
    cmd = tip_cmd(k, (ctx_fmt or {}).get("what"))
    if getattr(idle, "perf_quiet", False) or tips is None or cmd is None or not idle.cfg.b("perform", "tip") or not tips.on():
        return None
    text = f"💡 你们也可以发『{cmd}』"
    tips.post(text, "perform", None, spoken=None)
    return text


def register(idle_mod):
    """把 perf_* 注册进 idle 的活动表（idle.py 末尾调用）"""
    for name, k in NAMES.items():
        def mk(k=k):
            return lambda ctx: plan(ctx, k)
        idle_mod.ACTS[name] = mk()
        idle_mod.DESC[name] = ("表演：" + PERFS[k][4], {"intro": "开场白"})
        idle_mod.T[name] = {"intro": list(PERFS[k][0])}
    idle_mod.FIXED_LINES.update(NAMES)
