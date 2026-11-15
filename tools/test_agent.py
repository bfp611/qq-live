# -*- coding: utf-8 -*-
"""AI 主播操作桌面（agent）的离线测试：规则解析 + 后端校验 / 限速 / 权限 / 防注入。不联网、不需要页面。
   python tools/test_agent.py          # 全部离线测试
   端到端（真 LLM + 真页面）见 README「AI 操作桌面」一节：/agent/say?dry=0 与 tools/shoot_agent.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import sys, time, types, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from agent import rules, registry as R
from agent.core import Agent
from agent.desk import Desk
from host.config import Config

T = [
 ("把红警关掉", "close_window ra2"), ("关掉魔兽", "close_window war3"), ("帮我把记事本最小化", "minimize_window notepad"),
 ("最大化暴风影音", "maximize_window baofeng"), ("红警挡住了", "move_away ra2"), ("挡住了", "move_away"), ("挡着歌词了", "move_away"),
 ("看不到聊天了", "move_away"), ("把CS移到右边", "move_window cs right"), ("把计算器放到左上", "move_window calc topleft"),
 ("打开红警", "open_app ra2"), ("打开QQ游戏", "open_app qqgame"), ("打开记事本", "open_app notepad"), ("启动迅雷", "open_app xunlei"),
 ("下一首", "music_next"), ("切歌", "music_next"), ("换一首", "music_next"), ("上一首", "music_prev"), ("暂停", "music_pause"),
 ("继续播放", "music_play"), ("换壁纸", "change_wallpaper random"), ("换个壁纸", "change_wallpaper random"), ("壁纸换成郁金香", "change_wallpaper Tulips"),
 ("换成日落壁纸", "change_wallpaper Sunset"), ("刷新桌面", "refresh_desktop"), ("刷新", "refresh_desktop"), ("打开开始菜单", "start_menu open"),
 ("关闭开始菜单", "start_menu close"), ("显示桌面", "show_desktop"), ("全部最小化", "show_desktop"), ("关闭所有窗口", "close_all"),
 ("排列图标", "arrange_icons name"), ("按大小排列图标", "arrange_icons size"), ("整理一下桌面图标", "arrange_icons name"),
 ("在记事本里写：猪猪侠最帅", "notepad_type 猪猪侠最帅"), ("记事本输入 你好呀", "notepad_type 你好呀"), ("在群聊里发 大家好", "qq_send 大家好"),
 ("玩红警", "game_start ra2"), ("玩扫雷", "open_app minesweeper|mine_play"), ("我要玩CS", "game_start cs"), ("玩劲舞团", "game_start audition|dance"),
 ("算一下 12*34", "calc 12*34"), ("1+2等于几", "calc 1+2"), ("音量调到50", "set_volume 50"), ("静音", "set_volume mute"),
 ("撤销", "undo"), ("关闭群聊", "close_window qqchat"), ("把这个关掉", "close_window active"), ("还原记事本", "restore_window notepad"),
 ("切换到暴风影音", "focus_window baofeng"), ("扫雷点第3行第4列", "mine_click 3 4"), ("扫雷标记2行5列", "mine_flag 2 5"), ("扫雷高级", "open_app minesweeper|mine_new expert"),
 ("上淘宝", "browse taobao.com"), ("访问www.baidu.com", "browse www.baidu.com"), ("播放第2个视频暴风影音", "open_app baofeng|video_play 2"),
 ("玩纸牌", "open_app solitaire|sol_play"), ("来一把空当接龙", "open_app freecell|fc_play"), ("空当接龙第617号", "open_app freecell|fc_new 617"), ("纸牌重新发牌", "open_app solitaire|sol_new"),
 ("画个太阳", "open_app paint|paint_draw sun"), ("画一个房子", "open_app paint|paint_draw house"), ("画一朵花", "open_app paint|paint_draw flower"), ("画图清空", "open_app paint|paint_clear"), ("打开画图", "open_app paint"),
 ("打开控制面板", "open_app control"), ("打开声音设置", "control_open"), ("来个蓝屏", "bsod"), ("蓝屏", "bsod"), ("弹个气泡", "balloon hardware"), ("打开纸牌", "open_app solitaire"),
 ("喂食", "pet_care feed"), ("喂食苹果", "pet_care feed apple"), ("给宠物喂鸡腿", "pet_care feed drumstick"), ("洗澡", "pet_care bath"), ("给球球洗澡", "pet_care bath"),
 ("玩耍", "pet_care play"), ("陪宠物玩", "pet_care play"), ("宠物睡觉", "pet_care sleep"), ("宠物唱歌", "pet_care sing"),
 ("换装", "outfit_change next"), ("换成圣诞套装", "outfit_change santa"), ("穿上国王装", "outfit_change king"), ("来个随机换装", "outfit_change random"), ("换个水手服", "outfit_change sailor"),
 ("抖一下", "shake chat"), ("来个抖动", "shake chat"), ("桌面抖一下", "shake desk"), ("闪屏振动", "shake chat"),
 ("写日志：今天好开心", "zone_blog"), ("给空间留言：沙发", "zone_msg 沙发"), ("下载群共享里的表情包", "files_download 表情包"),
 ("打开QQ空间", "open_app qzone"), ("打开QQ宠物", "open_app qqpet"), ("打开QQ秀", "open_app qqshow"), ("打开群共享", "open_app qqfiles"), ("关闭QQ空间", "close_window qzone"),
 ("在命令提示符里输入 ver", "cmd_run ver"), ("平铺窗口", "tile horizontal"), ("层叠窗口", "tile cascade"),
]
NEG = ["洗澡了吗", "我喂了它", "他换装了吗", "好抖啊", "喂喂喂能听到吗", "我昨天写了日志", "我要去洗澡了", "我电脑昨天蓝屏了", "蓝屏好可怕", "画得真好看", "这画太丑了", "纸牌屋好看", "设成背景音乐", "背景音乐不错", "背景故事是什么", "壁纸好看", "主播好人一生平安", "哈哈哈哈哈", "好怀念啊", "下一首唱暗号吧", "别关红警", "不要关掉记事本", "红警怎么玩", "这歌真好听", "我也想去新疆", "来了来了", "沙发", "666", "红警", "今天太阳升级了耶", "笑死我了，LOL", "谁能教我怎么装修Q-Zone啊", "不要换壁纸"]

bad = 0
def check(cond, msg):
    global bad
    if not cond:
        bad += 1; print("FAIL", msg)

# ---------- 1. 规则解析 ----------
for t, exp in T:
    it = rules.parse(t, Desk())
    got = None
    if it and not it.skip:
        got = "|".join(" ".join(str(v) for v in [a["action"], *[a[k] for k in a if k != "action"]]) for a in it.actions).replace("True", "mute")
    ok = got is not None and all(p in got for p in exp.replace("|", " | ").split() if p != "|") and (got.count("|") == exp.count("|"))
    check(ok, f"规则 {t!r} -> {got} 期望 {exp}")
for t in NEG:
    it = rules.parse(t, Desk())
    check(not (it and not it.skip), f"误触发 {t!r} -> {it and it.actions}")

# ---------- 2. 后端 ----------
def mk(**kv):
    cfg = Config("/nonexistent.ini")
    for k, v in kv.items():
        cfg.cp["agent"][k] = str(v)
    app = types.SimpleNamespace(any_host=lambda: None)
    return Agent(cfg, app, log=lambda *a: None)

SNAP = {"ts": 1, "wins": [{"id": "game-ra2", "app": "ra2", "title": "红色警戒", "state": "normal", "x": 300, "y": 60, "w": 640, "h": 480, "z": 0, "cover": 0.8, "blocks": ["chat"]},
                          {"id": "w1", "app": "notepad", "title": "记事本", "state": "normal", "x": 10, "y": 10, "w": 300, "h": 200, "z": 1}]}
desk = Desk(SNAP)

# 白名单 / 黑名单
a = mk()
good, errs, _ = a.validate([{"action": "shutdown"}, {"action": "rm_rf"}, {"action": "music_next"}], desk, "tester")
check([g["action"] for g in good] == ["music_next"], f"禁用动作应被拦: {good} {errs}")
a = mk(allow_actions="music_next,music_prev")
good, errs, _ = a.validate([{"action": "open_app", "app": "notepad"}, {"action": "music_prev"}], desk, "t")
check([g["action"] for g in good] == ["music_prev"], f"allow_actions 白名单: {good}")
a = mk(deny_actions="close_window")
good, _, _ = a.validate([{"action": "close_window", "target": "ra2"}, {"action": "minimize_window", "target": "ra2"}], desk, "t")
check([g["action"] for g in good] == ["minimize_window"], f"deny_actions: {good}")
a = mk(max_actions=2)
good, errs, _ = a.validate([{"action": "music_next"}] * 5, desk, "t")
check(len(good) == 2, f"max_actions: {len(good)}")
# 注入式参数
a = mk()
for bad_a in [{"action": "cmd_run", "command": "del /f /s c:"}, {"action": "cmd_run", "command": "format c:"}, {"action": "calc", "expr": "__import__('os')"},
              {"action": "browse", "url": "http://evil.example.net/x"}, {"action": "qq_send", "text": "加我微信 abc123"}, {"action": "notepad_type", "text": "http://x.com"},
              {"action": "mine_click", "row": 99, "col": 1}, {"action": "move_window", "target": "ra2", "to": "javascript:alert(1)"}]:
    good, errs, _ = a.validate([bad_a], desk, "t")
    check(not good, f"注入/越界应被拒: {bad_a} -> {good}")
good, _, _ = a.validate([{"action": "qq_send", "text": "大家好"}], desk, "小明")
check(good and good[0]["text"].startswith("小明说"), f"qq_send 前缀: {good}")
# QQ 生态口令：[qq] commands 关了观众的口令被拒，主播自己玩（viewer=False）照样可以；enabled=false 都拒
def mkq(**kv):
    a_ = mk()
    for k, v in kv.items():
        a_.cfg.cp["qq"][k] = str(v)
    return a_
good, errs, _ = mkq().validate([{"action": "pet_care", "what": "feed"}, {"action": "shake", "target": "chat"}], desk, "小明")
check([g["action"] for g in good] == ["pet_care", "shake"], f"QQ 口令默认放行: {good} {errs}")
good, errs, _ = mkq(commands="false").validate([{"action": "pet_care", "what": "feed"}], desk, "小明")
check(not good and errs, f"commands=false 拒观众口令: {good}")
good, errs, _ = mkq(commands="false").validate([{"action": "pet_care", "what": "feed"}], desk, "猪猪侠", viewer=False)
check(good, f"commands=false 不影响主播自己玩: {errs}")
good, errs, _ = mkq(enabled="false").validate([{"action": "outfit_change", "name": "santa"}], desk, "猪猪侠", viewer=False)
check(not good, "enabled=false 全拒")
good, _, _ = mkq().validate([{"action": "zone_msg", "text": "沙发"}, {"action": "zone_blog", "title": "t" * 40, "text": "加我微信 abc"}], desk, "小明")
check(len(good) == 1 and good[0]["text"].startswith("小明说"), f"zone_msg 带署名、广告被拒: {good}")
good, _, say = a.validate([{"action": "close_window", "target": "word"}], desk, "t")
check(not good and say, f"目标窗口不存在应给说明: {good} {say!r}")
good, _, say = a.validate([{"action": "move_away"}], Desk({"ts": 1, "wins": [SNAP["wins"][1]]}), "t")
check(not good and say, "没有窗口挡路 -> 说明")

# 谁能指挥
ev = lambda n, u="1": {"name": n, "uid": u}
room = types.SimpleNamespace(last={"room": {"anchor": "主播甲"}})
check(mk(who="everyone").who_ok(ev("路人"), room), "everyone")
a = mk(who="anchor")
check(a.who_ok(ev("主播甲"), room) and not a.who_ok(ev("路人"), room), "anchor 模式")
a = mk(who="list", allow_users="老王, 小李")
check(a.who_ok(ev("老王"), room) and not a.who_ok(ev("路人"), room), "list 模式")
a = mk(who="everyone", deny_users="捣蛋鬼")
check(not a.who_ok(ev("捣蛋鬼"), room) and a.who_ok(ev("路人"), room), "deny_users")

# 限速
a = mk(user_cooldown=3, user_per_min=3, global_cooldown=0, global_per_min=5, dedupe_seconds=8, queue_max=50)
t0 = time.time()
r = [a.limit_check("u1", f"下一首{i}", t0 + i * 3.1)[0] for i in range(5)]
check(r == [True, True, True, False, False], f"用户每分钟上限: {r}")
check(a.limit_check("u2", "切歌", t0 + 20)[0] and not a.limit_check("u2", "切歌", t0 + 22)[0], "同用户同文本去重/冷却")
a = mk(user_cooldown=0, user_per_min=99, global_cooldown=0, global_per_min=3, dedupe_seconds=0, queue_max=50)
r = [a.limit_check(f"u{i}", "x", t0 + i)[0] for i in range(5)]
check(r == [True, True, True, False, False], f"全局每分钟上限: {r}")
a = mk(user_cooldown=0, global_cooldown=0, dedupe_seconds=0, queue_max=2)
a.pending = {1: time.time(), 2: time.time()}
check(not a.limit_check("u", "x")[0], "页面排队上限")

# 总开关
a = mk(enabled="false"); a.clients = {object(): {}}
check(a.on_chat({"t": "chat", "text": "下一首", "name": "x"}, room) is False, "enabled=false 不处理")
a = mk()
check(a.on_chat({"t": "chat", "text": "下一首", "name": "x"}, room) is False, "没有页面连接时当普通聊天")

print("done: rules", len(T), "neg", len(NEG), "-> bad", bad)
sys.exit(1 if bad else 0)
