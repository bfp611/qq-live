"""冷场活动 diary_read：翻开 QQ空间日志，把下播后写的那篇日记念出来（[story] read_aloud）。

台词固定（走 idle.FIXED_LINES，不过大模型）：日记正文就是要念的内容，开头一句「翻到我的空间日志《标题》」。
条件：story 开着、read_aloud 开着、有已发表没念过的日记、离上次朗读够久、QQ空间开着。念完（开始念时）标记已读，不会反复念同一篇。
"""
import random
import time

INTROS = ["翻到我昨天的空间日志《{title}》，念给你们听——{text}", "我在QQ空间写了篇日志《{title}》，大家听听——{text}", "闲着翻翻自己的空间，这篇《{title}》——{text}"]


def _story(ctx):
    return getattr(ctx.idle.app, "story", None)


def plan(ctx):
    from .idle import B, clear
    sy = _story(ctx)
    c = ctx.cfg
    if sy is None or not c.b("qq", "enabled") or not c.b("qq", "zone") or "qzone" in ctx.apps:
        return None
    d = sy.next_unread(time.time())
    if d is None:
        return None
    ctx.fmt["_diary_id"] = d["id"]
    ctx.fmt["title"] = d["title"]
    text = d["text"].replace("\n", " ")
    ctx.fmt["_intro"] = random.choice(INTROS).format(title=d["title"], text=text)
    wait = max(8.0, min(45.0, len(text) * 0.3 + 4))
    return [B("intro", [{"action": "open_app", "app": "qzone"}, clear(), {"action": "zone_open", "tab": "blog", "post": "diary"}], "平静", critical=True),
            B(None, [{"action": "_wait", "secs": round(wait, 1)}], "平静")]


def register(idle_mod):
    idle_mod.ACTS["diary_read"] = plan
    idle_mod.DESC["diary_read"] = ("翻QQ空间日志，把下播后写的日记念出来", {"intro": "开场白（含日记）"})
    idle_mod.T["diary_read"] = {"intro": ["翻到我的空间日志，念给你们听"]}
    idle_mod.FIXED_LINES["diary_read"] = "diary"


def read_now(app):
    """面板「现在就念」：不看朗读间隔 / 安静计时，其余条件照旧（猪猪侠没在忙、有页面连着、桌面快照够新、有没念过的日记）"""
    from .idle import Ctx
    idl, sy = getattr(app, "idle", None), getattr(app, "story", None)
    if sy is None or not sy.on():
        return {"ok": False, "error": "连续剧情没开（[story] enabled）"}
    if idl is None or not idl.on():
        return {"ok": False, "error": "冷场玩电脑没开（[idle] enabled）"}
    if idl.task and not idl.task.done():
        return {"ok": False, "error": "猪猪侠正在忙别的"}
    ag = idl.agent
    if not ag.clients:
        return {"ok": False, "error": "没有页面连着"}
    desk = ag.desk()
    if not desk.known or time.time() - (ag.clients.get(ag.snap_ws) or {}).get("at", 0) > 15:
        return {"ok": False, "error": "桌面快照太旧（页面刚连上，等几秒）"}
    if not sy.unread():
        return {"ok": False, "error": "没有没念过的日记（先「现在写一篇」并发表）"}
    last, sy.data["last_read"] = sy.data.get("last_read", 0), 0
    try:
        ok = plan(Ctx(idl, desk, idl.song(desk))) is not None
    finally:
        sy.data["last_read"] = last
    if not ok:
        return {"ok": False, "error": "现在念不了（QQ空间没开 / 已经开着）"}
    sy.data["last_read"] = 0
    idl.begin("diary_read", force=True)
    return {"ok": True, "text": "开始翻日记念"}
