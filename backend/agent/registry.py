# -*- coding: utf-8 -*-
"""动作注册表：桌面支持的所有动作、参数、别名、危险等级。LLM 的工具 schema、规则解析、校验都从这里派生。

约定
  - 动作名全小写英文；args 是扁平 dict。
  - target = 窗口：窗口 id（快照里有）/ 应用名（红警、记事本…）/ active / chat / blocking / all
  - cat：window 窗口  desk 桌面  music 音乐（后端真的控制播放器）  app 软件内操作  game 游戏  text 往里打字  meta 其它
  - danger：0 普通  1 可能影响直播画面（默认允许，可禁用）  2 破坏性 / 会黑屏（默认写进 deny_actions）
"""
import re

# ---------------------------------------------------------------- 应用
# id：WM.open(id) 用的名字；label：中文名；alias：弹幕里常见的叫法（小写，最长匹配优先）
APPS = {
    "qq": ("腾讯QQ", ["腾讯qq", "qq登录", "qq软件", "企鹅", "扣扣"]),
    "ttplayer": ("千千静听", ["千千静听", "千千", "音乐播放器", "播放器"]),
    "baofeng": ("暴风影音", ["暴风影音", "暴风", "影音", "视频播放器"]),
    "kugou": ("酷狗音乐", ["酷狗音乐", "酷狗"]),
    "xunlei": ("迅雷", ["迅雷", "下载器"]),
    "qqgame": ("QQ游戏", ["qq游戏", "游戏大厅"]),
    "ie": ("Internet Explorer", ["internetexplorer", "ie浏览器", "ie", "浏览器", "上网"]),
    "cs": ("Counter-Strike", ["counter-strike", "counterstrike", "反恐精英", "cs1.6", "csol", "cs"]),
    "vc": ("罪恶都市", ["侠盗猎车手", "罪恶都市", "gta", "vc"]),
    "war3": ("魔兽争霸III", ["魔兽争霸3", "魔兽争霸", "魔兽", "war3", "warcraft"]),
    "ra2": ("红色警戒2", ["红色警戒2", "红色警戒", "红警2", "红警", "ra2"]),
    "mir2": ("热血传奇", ["热血传奇", "传奇", "mir2"]),
    "audition": ("劲舞团", ["劲舞团", "跳舞游戏", "跳舞"]),
    "notepad": ("记事本", ["记事本", "notepad"]),
    "calc": ("计算器", ["计算器", "calc"]),
    "cmd": ("命令提示符", ["命令提示符", "黑框框", "黑框", "cmd", "dos", "终端", "控制台"]),
    "minesweeper": ("扫雷", ["扫雷", "minesweeper", "winmine"]),
    "solitaire": ("纸牌", ["纸牌", "solitaire", "klondike"]),
    "freecell": ("空当接龙", ["空当接龙", "freecell"]),
    "mycomputer": ("我的电脑", ["我的电脑", "资源管理器", "此电脑"]),
    "mydocs": ("我的文档", ["我的文档", "文档"]),
    "mypics": ("我的图片", ["我的图片", "图片收藏", "图片文件夹"]),
    "mymusic": ("我的音乐", ["我的音乐", "音乐文件夹"]),
    "recycle": ("回收站", ["回收站"]),
    "control": ("控制面板", ["控制面板"]),
    "display": ("显示属性", ["显示属性", "显示设置", "屏幕属性", "桌面属性"]),
    "taskmgr": ("任务管理器", ["任务管理器"]),
    "run": ("运行", ["运行对话框", "运行窗口"]),
    "datetime": ("日期和时间", ["日期和时间", "时间设置", "日期时间"]),
    "paint": ("画图", ["画图", "mspaint"]),
    "sndcpl": ("声音和音频设备", ["声音和音频设备", "声音设置", "声音属性", "音频设备", "声音方案"]),
    "mousecpl": ("鼠标属性", ["鼠标属性", "鼠标设置", "指针速度", "指针踪迹"]),
    "help": ("帮助和支持", ["帮助和支持", "帮助中心"]),
    "qzone": ("QQ空间", ["qq空间", "qzone", "我的空间", "群空间", "空间"]),
    "qqpet": ("QQ宠物", ["qq宠物", "企鹅宠物", "宠物"]),
    "qqshow": ("QQ秀商城", ["qq秀商城", "qq秀", "装扮商城", "换装商城"]),
    "qqfiles": ("群共享", ["群共享", "群文件", "共享文件", "文件共享"]),
    "rank": ("QQ积分排行榜", ["qq积分排行榜", "积分排行榜", "积分榜", "排行榜", "日榜", "总榜"]),
    "vote": ("投票窗口", ["投票窗口", "投票结果"]),
    "outlook": ("Outlook Express", ["outlookexpress", "outlook", "电子邮件", "邮件"]),
}
# 这几个 app 其实是“explorer + path”
EXPLORER_PATHS = {"mycomputer": "mycomputer", "mydocs": "mydocs", "mypics": "mypics", "mymusic": "mymusic", "recycle": "recycle"}   # 控制面板现在是独立的 control 应用
# 窗口 id → 应用（页面也会给 app 字段，这里是兜底）
WIN_APP = {"qqchat": "qqchat", "ttplayer": "ttplayer", "ttplaylist": "ttplayer", "game-cs": "cs", "game-vc": "vc", "game-war3": "war3", "game-ra2": "ra2",
           "game-mir2": "mir2", "game-au": "audition"}
# 特殊窗口：群聊窗口不是 WM.open 的普通应用
CHAT_ALIASES = ["群聊", "聊天窗口", "聊天框", "弹幕窗口", "弹幕", "直播间窗口", "qq群", "群窗口", "聊天室"]
GAME_APPS = ["cs", "vc", "war3", "ra2", "mir2", "audition"]
GAME_LABEL = {a: APPS[a][0] for a in GAME_APPS}

# 壁纸：显示名（与 apps-core.js WALLS 一致）→ 弹幕里的叫法
WALLPAPERS = {
    "Ascent": ["ascent", "上升"], "Autumn": ["autumn", "秋天", "秋"], "Azul": ["azul", "蓝色"], "Bliss": ["bliss", "草原", "绿草", "默认", "经典", "xp默认"],
    "Crystal": ["crystal", "水晶"], "Follow": ["follow"], "Friend": ["friend", "朋友"], "Home": ["home", "家"],
    "Moon flower": ["moonflower", "月亮花", "月花"], "Peace": ["peace", "和平"], "Power": ["power", "力量"], "Purple flower": ["purpleflower", "紫花", "紫色花"],
    "Radiance": ["radiance", "光辉"], "Red moon desert": ["redmoondesert", "红月", "沙漠", "红月沙漠"], "Ripple": ["ripple", "涟漪", "水波"],
    "Stonehenge": ["stonehenge", "巨石阵", "巨石"], "Tulips": ["tulips", "郁金香"], "Vortec space": ["vortecspace", "太空", "宇宙", "星空"],
    "Wind": ["wind", "风"], "Windows XP": ["windowsxp", "xp"], "Blue hills": ["bluehills", "蓝山", "山"], "Sunset": ["sunset", "日落", "夕阳", "黄昏"],
    "Water lilies": ["waterlilies", "睡莲", "荷花"], "Winter": ["winter", "冬天", "雪", "冬"],
}

ICON_ALIASES = {"mycomputer": "我的电脑", "mydocs": "我的文档", "recycle": "回收站", "ie": "Internet Explorer"}  # 其余图标用 APPS 的 label


def app_label(a):
    if a == "qqchat":
        return "群聊窗口"
    return APPS.get(a, (a,))[0]


def norm(s):
    """弹幕/名字归一：小写、去空白和标点。"""
    return re.sub(r"[\s，。,.!！?？~～、:：;；\"'“”‘’()（）\[\]【】]+", "", str(s or "").lower())


_ALIAS = None


def alias_table():
    """[(alias, app_id)] 按 alias 长度从长到短。含 qqchat。"""
    global _ALIAS
    if _ALIAS is None:
        t = []
        for aid, (label, al) in APPS.items():
            for x in al + [label.lower()]:
                t.append((norm(x), aid))
        for x in CHAT_ALIASES:
            t.append((norm(x), "qqchat"))
        t.sort(key=lambda p: -len(p[0]))
        _ALIAS = t
    return _ALIAS


def find_app(text):
    """文本里提到的应用 id（最长匹配）；没有返回 None。"""
    n = norm(text)
    for a, aid in alias_table():
        if a and a in n:
            return aid
    return None


def find_all_apps(text):
    n = norm(text)
    out = []
    for a, aid in alias_table():
        if a and a in n and aid not in out:
            out.append(aid)
            n = n.replace(a, "·")
    return out


def find_wallpaper(text):
    n = norm(text)
    best = None
    for name, al in WALLPAPERS.items():
        for x in al + [name.lower().replace(" ", "")]:
            if x and x in n and (best is None or len(x) > best[1]):
                best = (name, len(x))
    return best[0] if best else None


# ---------------------------------------------------------------- 动作
# 参数类型：str / int / enum:a|b / text（要过屏蔽词、限长）/ app / target / bool
def A(cat, desc, args=None, danger=0, backend=False):
    return {"cat": cat, "desc": desc, "args": args or {}, "danger": danger, "backend": backend}


ACTIONS = {
    # ---- 窗口 ----
    "open_app": A("window", "打开一个软件（桌面图标 / 开始菜单）。app 填应用 id", {"app": "app!", "path": "str", "url": "str"}),
    "close_window": A("window", "关闭窗口（点右上角×）", {"target": "target!"}, danger=1),
    "minimize_window": A("window", "最小化窗口（点–）", {"target": "target!"}),
    "maximize_window": A("window", "最大化窗口（点□）", {"target": "target!"}, danger=1),
    "restore_window": A("window", "还原窗口 / 从任务栏恢复", {"target": "target!"}),
    "focus_window": A("window", "切换到窗口（点标题栏/任务栏，置顶）", {"target": "target!"}),
    "move_window": A("window", "拖动窗口到某处（to: left right top bottom center topleft topright bottomleft bottomright 或 x,y）", {"target": "target!", "to": "str", "x": "int", "y": "int"}),
    "move_away": A("window", "把挡住群聊/歌词/播放器的窗口挪开（不给 target 就自动找最挡视线的那个）", {"target": "target"}),
    "resize_window": A("window", "调整窗口大小（size: small medium large 或 w,h）", {"target": "target!", "size": "enum:small|medium|large", "w": "int", "h": "int"}),
    "show_desktop": A("window", "显示桌面（最小化全部）", {}),
    "close_all": A("window", "关闭所有窗口（群聊窗口除外，且会自动保护）", {}, danger=1),
    "tile": A("window", "平铺/层叠窗口", {"mode": "enum:cascade|horizontal|vertical"}),
    # ---- 桌面 ----
    "change_wallpaper": A("desk", "更换壁纸（右键桌面→属性→桌面→选壁纸→确定）。name 填壁纸名，或 next / random", {"name": "str"}),
    "refresh_desktop": A("desk", "刷新桌面（右键→刷新）", {}),
    "arrange_icons": A("desk", "排列桌面图标（by: name size type time group auto）", {"by": "enum:name|size|type|time|group|auto"}),
    "start_menu": A("desk", "打开/关闭开始菜单", {"state": "enum:open|close"}),
    "new_item": A("desk", "在桌面新建文件夹/文本文档（右键→新建）", {"kind": "enum:folder|text", "name": "text"}),
    "move_icon": A("desk", "把桌面图标拖到别处（icon 填图标名，to: left right top bottom center）", {"icon": "str!", "to": "str"}),
    "delete_icon": A("desk", "把桌面图标放进回收站", {"icon": "str!"}, danger=2),
    "empty_trash": A("desk", "清空回收站", {}, danger=2),
    "set_volume": A("desk", "调系统音量（托盘小喇叭；value 0-100，mute true/false）", {"value": "int", "mute": "bool"}),
    "shutdown": A("desk", "关机 / 重启 / 待机的黑屏动画（会黑屏几秒）", {"mode": "enum:shutdown|restart|standby"}, danger=2),
    "logoff": A("desk", "注销的黑屏动画", {}, danger=2),
    # ---- 音乐（后端真的控制网易云）----
    "music_next": A("music", "下一首", {}, backend=True),
    "music_prev": A("music", "上一首", {}, backend=True),
    "music_pause": A("music", "暂停播放", {}, backend=True),
    "music_play": A("music", "继续播放", {}, backend=True),
    "music_toggle": A("music", "播放/暂停切换", {}, backend=True),
    "song_request": A("music", "点歌（交给点歌系统排队）。query = 歌名或 歌手 歌名", {"query": "text!"}, backend=True),
    # ---- 软件内操作 ----
    "notepad_type": A("text", "在记事本里打字（会自动打开记事本）", {"text": "text!"}),
    "qq_send": A("text", "在 QQ 群聊窗口的输入框里打字并发送（只在画面里显示，会带上点播人昵称）", {"text": "text!"}),
    "qq_private": A("text", "在 QQ 里和一个好友私聊（会自动打开并登录 QQ，再双击好友、打字、发送）。friend 好友昵称可不填", {"friend": "str", "text": "text!"}),
    "calc": A("app", "用计算器算一个算式（只能数字和 + - * / . ）", {"expr": "str!"}),
    "cmd_run": A("text", "在命令提示符里输入命令（只允许 ver dir ipconfig date time echo help cls ping）", {"command": "str!"}),
    "browse": A("app", "用 IE 打开一个网址 / 站点", {"url": "str!"}),
    "game_start": A("game", "打开游戏并开始（点主菜单里的开始项，进入游戏画面）。app 是游戏 id", {"app": "app!"}),
    "game_back": A("game", "游戏里按 ESC 回到主菜单", {"app": "app"}),
    "mine_new": A("game", "扫雷：开新局（level: beginner intermediate expert）", {"level": "enum:beginner|intermediate|expert"}),
    "mine_click": A("game", "扫雷：点开第 row 行第 col 列（从 1 开始）", {"row": "int!", "col": "int!"}),
    "mine_flag": A("game", "扫雷：在第 row 行第 col 列插旗（右键）", {"row": "int!", "col": "int!"}),
    "mine_play": A("game", "扫雷：自动玩 steps 步（会推理，点安全的格子、插旗）", {"steps": "int"}),
    "sol_new": A("game", "纸牌：开新局（draw: 1 或 3，每次翻几张牌）", {"draw": "int"}),
    "sol_play": A("game", "纸牌：自动玩 steps 步（真的用鼠标拖牌、双击送牌、点牌堆翻牌）", {"steps": "int"}),
    "fc_new": A("game", "空当接龙：开新局（no 游戏编号 1~32000，可不填 = 随机）", {"no": "int"}),
    "fc_play": A("game", "空当接龙：自动玩 steps 步（先找一个整局解法，再用鼠标一张一张拖）", {"steps": "int"}),
    "paint_draw": A("app", "画图：用鼠标画一幅简笔画（what: smile 笑脸 house 房子 sun 太阳 flower 花 heart 爱心 star 星星 tree 树 boat 小船；color 可选颜色名）", {"what": "enum:smile|house|sun|flower|heart|star|tree|boat", "color": "str"}),
    "paint_tool": A("app", "画图：点工具箱里的工具（tool: pencil brush airbrush eraser fill pick line rect ellipse rrect poly）", {"tool": "enum:pencil|brush|airbrush|eraser|fill|pick|line|rect|ellipse|rrect|poly"}),
    "paint_color": A("app", "画图：点颜料盒里的一个颜色（color：颜色名，如 红 蓝 黄 绿 黑 白 橙 紫）", {"color": "str!"}),
    "paint_clear": A("app", "画图：清除图像（图像菜单→清除图像）", {}),
    "control_open": A("app", "控制面板：打开控制面板并点进某个类别 / 小程序（item：声音 鼠标 显示 日期时间 或类别名）", {"item": "str!"}),
    "bsod": A("meta", "蓝屏彩蛋：桌面蓝屏几秒后自动重启恢复（会影响直播画面几秒）", {}, danger=1),
    "balloon": A("meta", "托盘气泡通知（kind: hardware 发现新硬件 / tip 小提示 / qq QQ 好友上线）", {"kind": "enum:hardware|tip|qq"}),
    "video_play": A("app", "暴风影音：播放第 clip 个片段（1-4）/ 下一个", {"clip": "int"}),
    "video_toggle": A("app", "暴风影音：播放/暂停", {}),
    "mir2_chat": A("game", "热血传奇里聊天（回车→打字→回车）", {"text": "text!"}),
    "dance": A("game", "劲舞团：按几次方向键（手动模式）", {"count": "int"}),
    # ---- QQ 生态 ----
    "pet_care": A("app", "QQ宠物：照顾桌面上的企鹅宠物（what: feed 喂食 bath 洗澡 play 玩耍 sleep 睡觉 sing 唱歌；food 可选 apple fish cake drumstick）——光标真的右键点宠物、点菜单", {"what": "enum:feed|bath|play|sleep|sing", "food": "enum:apple|fish|cake|drumstick"}),
    "outfit_change": A("app", "QQ秀：给群里的猪猪侠换装（name：default santa cool king sailor wizard party love gentleman summer，或 next 下一套 / random 随机）——光标点“QQ秀”名字打开商城、点试穿", {"name": "str"}),
    "zone_open": A("app", "QQ空间：打开空间并切到某个标签（tab: home 主页 blog 日志 album 相册 msg 留言板 music 音乐盒；tab=blog 时 post=diary 会点开最新一篇日记）", {"tab": "enum:home|blog|album|msg|music", "post": "enum:diary"}),
    "zone_blog": A("text", "QQ空间：写一篇日志并发表（title 标题，text 正文）", {"title": "str!", "text": "text!"}),
    "zone_msg": A("text", "QQ空间：在留言板里留一条言", {"text": "text!"}),
    "files_download": A("app", "群共享：打开群共享、选中一个文件（name 填文件名里的几个字，可不填 = 随机一个）、点下载，由迅雷下载", {"name": "str"}),
    "shake": A("meta", "QQ窗口抖动（闪屏振动）：target chat 群聊窗口 / desk 整个桌面", {"target": "enum:chat|desk"}, danger=1),
    # ---- 观众互动（[play]）----
    "vote_start": A("meta", "发起一个弹幕投票：观众在群里回数字，到时间后得票最多的选项交给你去执行（title 标题；options 用 | 分开的选项，如 玩红警|换壁纸|扫雷，每个选项要是一句你能执行的话；secs 投票秒数）。弹出 XP 投票窗口，实时柱状图", {"title": "str", "options": "text!", "secs": "int"}, backend=True),
    "vote_end": A("meta", "提前结束当前投票并公布结果", {}, backend=True),
    "play_fx": A("meta", "放一个 XP 特效（kind: fireworks 烟花 / meteor 流星雨 / emoji 满屏表情雨 / virus 假“中毒”熊猫烧香图标，几秒后自动恢复，纯视觉无害）", {"kind": "enum:fireworks|meteor|emoji|virus"}, danger=1),
    "gift_fx": A("meta", "礼物 / 点赞联动特效（[giftfx]，只有主播自己能用，不给观众 / LLM）：kind small_fireworks 小烟花 / thanks 全屏感谢卡片 / big_thanks 流星雨+全屏感谢 / setup 假重装系统 / like 全屏点赞", {"kind": "enum:small_fireworks|thanks|big_thanks|setup|like", "name": "str", "gift": "str", "n": "int", "value": "int", "text": "text", "secs": "int"}, danger=1),
    "rank_open": A("app", "打开 QQ积分排行榜窗口（by: day 日榜 / total 总榜）", {"by": "enum:day|total"}),
    # ---- AI 加强包（[ai_plus]）：后端动作，不推给页面 ----
    "game_start": A("meta", "和观众玩一个小游戏（game: idiom 成语接龙 / song 猜歌名 / riddle 脑筋急转弯）：弹出 XP 游戏窗口，你来出题、观众在群里答，答对加 QQ 积分；一次只能有一场", {"game": "enum:idiom|song|riddle"}, backend=True),
    "game_stop": A("meta", "提前结束正在进行的小游戏并公布得分", {}, backend=True),
    "screen_comment": A("meta", "就屏幕上正在发生的事（打开的程序、游戏、歌曲、特效）随口点评一句", {}, backend=True),
    "song_comment": A("meta", "就正在播放的这首歌点评一句（歌手小知识 / 听感），不念歌词", {}, backend=True),
    # ---- 其它 ----
    "undo": A("meta", "撤销上一个桌面动作（移动/最小化/关闭/换壁纸…）", {}),
}

# 页面上执行的动作 = 非 backend 的，加上 music_* 的“光标演示”
VISUAL_MUSIC = {"music_next": "next", "music_prev": "prev", "music_pause": "play", "music_play": "play", "music_toggle": "play"}

HOST_ONLY = frozenset({"gift_fx"})        # 只有主播自己（idle / giftfx，viewer=False）能发的动作：观众弹幕 / LLM 工具里都不给
QQ_ACTIONS = ("pet_care", "outfit_change", "zone_open", "zone_blog", "zone_msg", "files_download", "shake")   # 受 [qq] commands 控制
PLAY_ACTIONS = ("vote_start", "vote_end", "play_fx", "rank_open")   # 受 [play] enabled / commands 控制
AIPLUS_ACTIONS = {"game_start": "game", "game_stop": "game", "screen_comment": "screen", "song_comment": "song_comment"}   # 受 [ai_plus] enabled + 对应开关控制
DANGER_DEFAULT_DENY = [k for k, v in ACTIONS.items() if v["danger"] >= 2]


def split_list(s):
    return [x.strip() for x in re.split(r"[,，;；\s]+", s or "") if x.strip()]


def allowed(name, allow_csv, deny_csv):
    """allow_actions / deny_actions（逗号分隔，* = 全部）。deny 优先；写分类用 cat:window / cat:music。"""
    spec = ACTIONS.get(name)
    if not spec:
        return False
    deny = split_list(deny_csv)
    if name in deny or ("cat:" + spec["cat"]) in deny:
        return False
    allow = split_list(allow_csv) or ["*"]
    return "*" in allow or name in allow or ("cat:" + spec["cat"]) in allow


def coerce(name, args, max_text=40):
    """按注册表校验/清理参数；返回 (args, error)。未知参数丢弃；text 限长；enum 不在范围 → 报错。"""
    spec = ACTIONS.get(name)
    if not spec:
        return None, f"没有这个动作：{name}"
    out = {}
    for k, t in spec["args"].items():
        req = t.endswith("!")
        t = t.rstrip("!")
        v = (args or {}).get(k)
        if v is None or v == "":
            if req:
                return None, f"{name} 缺少参数 {k}"
            continue
        if t in ("str", "target", "app"):
            v = str(v).strip()[:80]
            if t == "app":
                aid = v if (v in APPS or v == "qqchat") else find_app(v)
                if not aid:
                    return None, f"不认识的应用：{v}"
                v = aid
        elif t == "text":
            v = re.sub(r"[\r\n\t]+", " ", str(v)).strip()[:max_text]
            if not v and req:
                return None, f"{name} 的 {k} 是空的"
        elif t == "int":
            try:
                v = int(float(v))
            except (TypeError, ValueError):
                if req:
                    return None, f"{name} 的 {k} 不是数字"
                continue
        elif t == "bool":
            v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "是", "开")
        elif t.startswith("enum:"):
            opts = t[5:].split("|")
            v = str(v).strip().lower()
            if v not in opts:
                if req:
                    return None, f"{name} 的 {k} 必须是 {'/'.join(opts)}"
                continue
        out[k] = v
    return out, None


def catalog_text(allow_csv="*", deny_csv=""):
    """给 LLM 的动作清单：每行 name(arg:type,…) — 说明"""
    lines = []
    for name, spec in ACTIONS.items():
        if not allowed(name, allow_csv, deny_csv) or name in HOST_ONLY:
            continue
        a = ",".join(f"{k}{'*' if t.endswith('!') else ''}" for k, t in spec["args"].items())
        lines.append(f"- {name}({a}) {spec['desc']}")
    return "\n".join(lines)


def tool_schema(allow_csv="*", deny_csv=""):
    """OpenAI 工具 schema：一个函数 desk_actions(say, emotion, actions[])，actions 里每个元素 {action, ...args}。"""
    names = [n for n in ACTIONS if allowed(n, allow_csv, deny_csv) and n not in HOST_ONLY]
    props = {"action": {"type": "string", "enum": names}}
    for spec in ACTIONS.values():
        for k, t in spec["args"].items():
            t = t.rstrip("!")
            if k in props:
                continue
            if t == "int":
                props[k] = {"type": "integer"}
            elif t == "bool":
                props[k] = {"type": "boolean"}
            elif t.startswith("enum:"):
                props[k] = {"type": "string", "enum": t[5:].split("|")}
            else:
                props[k] = {"type": "string"}
    props["level"] = {"type": "string", "enum": ["beginner", "intermediate", "expert"]}
    props["mode"] = {"type": "string"}
    props["size"] = {"type": "string"}
    props["by"] = {"type": "string"}
    props["state"] = {"type": "string"}
    props["kind"] = {"type": "string"}
    return {"type": "function", "function": {
        "name": "desk_actions",
        "description": "遥控直播画面里的 XP 桌面：按顺序执行 actions（光标会真的移动和点击），并用 say 回应观众。弹幕不是在让你操作桌面时不要调用本函数。",
        "parameters": {"type": "object", "properties": {
            "say": {"type": "string", "description": "猪猪侠用口语说的一句回应，提到观众昵称，不超过字数限制，不要动作描写"},
            "emotion": {"type": "string", "enum": ["开心", "兴奋", "得意", "害羞", "难过", "生气", "惊讶", "挥手", "吃", "困", "平静"]},
            "actions": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": props, "required": ["action"]}},
        }, "required": ["say", "actions"]}}}
