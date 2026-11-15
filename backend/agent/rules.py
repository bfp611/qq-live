# -*- coding: utf-8 -*-
"""规则解析：常见的口语指令 → 动作，不用 LLM，零延迟，LLM 挂了也能用。

parse(text, desk) -> Intent | None
  Intent.actions   动作列表（还没校验；Agent 里统一 coerce / 允许表 / 限额）
  Intent.skip      True = 看起来是指令，但被否定/疑问句，别执行也别问 LLM
没把握就返回 None（交给 LLM 或当普通聊天）。
"""
import re
from dataclasses import dataclass, field

from . import registry as R


@dataclass
class Intent:
    actions: list = field(default_factory=list)
    rule: str = ""
    skip: bool = False
    t: str = ""          # 回复里用的目标名（“红警”）
    emotion: str = "开心"


NAME = "猪猪侠"
FILLER_HEAD = re.compile(r"^(?:@\S+\s*)?(?:(?:猪猪侠|主播|小猪|喂|哎|诶|嘿|那个|麻烦|请|劳驾|帮我|帮忙|帮个忙|给我|替我|你|您|能不能|可不可以|可以|能|快|赶紧|马上|现在|先|再)[，,、\s]*)+")
FILLER_TAIL = re.compile(r"(?:吧|啊|呀|哦|啦|呢|嘛|哈|噢|谢谢|谢了|拜托|好吗|行吗|可以吗|好不好|行不行|一下|下|先|看看|试试|吗|么)+[~～!！。.]*$")
NEG = re.compile(r"(别|不要|不许|不准|不能|不用|不必|千万别|不想|没让|没有让|休想|禁止|莫|勿)(?:再|要|去|给|把)?$")
QUESTION = re.compile(r"(怎么|怎样|如何|为什么|为啥|是什么|是谁|是啥|什么意思|有没有|会不会|能不能玩|多少|几个|哪个|哪里)")

OPEN_V = r"(?:打开|开启|启动|运行|开一个|开个|开下|开|来个|来一个|进入|进|点开|点击|看看|看下|看一下|找出来|调出|调出来|弄出来)"
CLOSE_V = r"(?:关闭|关掉|关了|关上|关|退出|叉掉|叉了|干掉|结束|不要了|别开了|撤掉|拿掉|去掉|删掉窗口|关一下)"
MIN_V = r"(?:最小化|缩小|收起来|收起|缩下去|缩下|藏起来|藏掉|藏一下|隐藏|放到任务栏|缩到任务栏|最小)"
MAX_V = r"(?:最大化|全屏|铺满|放到最大|放最大|最大)"
RESTORE_V = r"(?:还原|恢复|复原|取消最大化|恢复原大小|恢复窗口|复位)"
MOVE_V = r"(?:挪开|移开|挪走|移走|拖开|拖走|让开|让一让|让让|挪一下|移一下|挪到|移到|拖到|放到|摆到|移动到|移动|挪动|拖动|挪|移|拖|摆)"
FOCUS_V = r"(?:切换到|切到|切回|回到|置顶|放到最前|放前面|调到前面|显示出来|显示|拿到前面|提到前面|激活|看一下|看看)"
BLOCK_W = r"(?:挡住|挡着|挡了|遮住|遮着|遮挡|挡视线|挡到|盖住|盖着|看不到|看不见|看不清|碍事|碍眼|挡道|挡镜头|挡屏幕|遮屏幕|挡着我|挡我)"
PRON = r"(?:这个|那个|它|当前|前面|最前面|最上面|上面那个|最上层|顶上|这个窗口|那个窗口|当前窗口|上面)"

POS = [("topleft", r"左上"), ("topright", r"右上"), ("bottomleft", r"左下"), ("bottomright", r"右下"),
       ("left", r"左边|左侧|最左|左面|左"), ("right", r"右边|右侧|最右|右面|右"), ("top", r"上边|上面|顶部|最上|上方|上"),
       ("bottom", r"下边|下面|底部|最下|下方|下"), ("center", r"中间|中央|正中|居中|中心|中")]


def clean(text):
    t = str(text or "").strip()
    t = re.sub(r"\[[^\]]{1,6}\]", "", t)           # [捂脸] 之类
    t = t.replace("猪猪侠", "").replace("主播", "") if len(t) > 4 else t
    for _ in range(3):
        t2 = FILLER_HEAD.sub("", t).strip()
        if t2 == t:
            break
        t = t2
    return t.strip()


def position_of(n):
    for k, rx in POS:
        if re.search(rx, n):
            return k
    return None


def _neg_before(n, m):
    """匹配到的动词前面是否紧跟着否定词。"""
    return bool(NEG.search(n[:m.start()][-4:])) if m else False


def _sk(rule):
    return Intent(rule=rule, skip=True)


def _tname(app):
    return R.app_label(app) if app else ""


# ---------------------------------------------------------------- QQ 生态（QQ宠物 / QQ秀 / QQ空间 / 群共享 / 窗口抖动）
# 弹幕口令。由 [qq] commands 开关控制（core.validate 里统一拦），这里只负责“听懂”。
OUTFIT_WORDS = [("santa", r"圣诞"), ("cool", r"酷炫|墨镜|酷|潮"), ("king", r"国王|皇冠|王者|皇帝"), ("sailor", r"水手|海军"),
                ("wizard", r"魔法|巫师|法师|魔术"), ("party", r"派对|生日|聚会"), ("love", r"爱心|情侣|粉红|甜"),
                ("gentleman", r"绅士|礼帽|西装"), ("summer", r"夏日|夏天|海滩|沙滩|草帽"), ("default", r"默认|原来|本来|初始|恢复|普通")]
FOOD_WORDS = [("apple", r"苹果"), ("fish", r"小鱼干|鱼"), ("cake", r"蛋糕"), ("drumstick", r"鸡腿|烤鸡")]


def _qq_parse(raw, n, orig=None):
    n0 = R.norm(orig or raw)          # 用原话：clean() 会把句首的“喂”当语气词吃掉
    if re.search(r"吗|么|为什么|为啥|怎么|是不是|有没有|了没", n0):      # 提问不是口令
        return None
    pet = r"(?:宠物|企鹅|小企鹅|球球|我的宠物|qq宠物)"
    # 抖一下（闪屏振动）
    if re.fullmatch(r"(?:来个|来一个|发个|发一个|发条|搞个|搞一个|弄个)?(?:窗口|屏幕|桌面|全屏|整个桌面|qq)?(?:抖一下|抖动一下|抖一抖|抖动|抖屏|抖|震一下|震动|振动|闪屏振动|闪屏|窗口抖动|屏幕抖动)(?:一下|吧|呀|呗|看看)?", n0):
        tg = "desk" if re.search(r"桌面|全屏|整个|屏幕", n0) else "chat"
        return Intent([{"action": "shake", "target": tg}], "shake", t="窗口", emotion="开心")
    # QQ宠物
    if re.search(r"喂食|投喂|喂(?:一?下)?" + pet + r"|喂(?:点|个|只)?(?:吃的|东西|苹果|小鱼干|鱼|蛋糕|鸡腿)|给" + pet + r"(?:吃|喂)|" + pet + r"饿了", n0) and not re.search(r"别|不要|不许", n0):
        a = {"action": "pet_care", "what": "feed"}
        for k, w in FOOD_WORDS:
            if re.search(w, n0):
                a["food"] = k
                break
        return Intent([a], "pet_feed", t="宠物")
    if re.fullmatch(r"(?:给|帮|替)?(?:" + pet + r")?(?:洗澡|洗个澡|洗一洗|洗洗|洗白白|冲个凉)(?:吧|啦|呀|呗)?", n0) or re.search(r"给" + pet + r"洗(?:个|一个)?澡", n0):
        return Intent([{"action": "pet_care", "what": "bath"}], "pet_bath", t="宠物")
    if re.fullmatch(r"(?:陪|和|跟)?(?:" + pet + r")?(?:玩耍|玩一玩|玩玩|玩会儿?|逗一?逗|逗逗|陪它玩|陪我玩|一起玩)(?:吧|啦|呀|呗)?", n0) or re.search(r"(?:陪|逗|和|跟)" + pet + r"(?:玩|一?逗|逗逗)", n0) or re.search(pet + r"(?:玩球|玩耍)", n0):
        return Intent([{"action": "pet_care", "what": "play"}], "pet_play", t="宠物")
    if re.search(pet + r"(?:睡觉|睡吧|去睡|该睡了)|哄" + pet + r"睡|(?:让|叫)" + pet + r"睡", n0):
        return Intent([{"action": "pet_care", "what": "sleep"}], "pet_sleep", t="宠物")
    if re.search(pet + r"(?:唱歌|唱首歌|来首歌|唱一首)|(?:让|叫)" + pet + r"唱", n0):
        return Intent([{"action": "pet_care", "what": "sing"}], "pet_sing", t="宠物")
    # QQ秀换装
    ow = [k for k, w in OUTFIT_WORDS if re.search(w, n0)]
    if (ow and re.search(r"换成|换上|换个|换一?套|变成", n0) and re.search(r"装|套|造型|衣|服|帽", n0)) or re.search(r"换装|换套装|换(?:一?身|一?套|件|个)(?:衣服|装|造型|套装)?|换衣服|换个?造型|换造型|试穿|穿上|穿(?:个|一?套)|变装|qq秀换", n0) and not re.search(r"别|不要|不许|商城|打开|关闭", n0):
        name = "next"
        for k, w in OUTFIT_WORDS:
            if re.search(w, n0):
                name = k
                break
        if re.search(r"随机|随便|乱换|惊喜", n0):
            name = "random"
        return Intent([{"action": "outfit_change", "name": name}], "outfit_change", t="造型")
    # QQ空间：写日志 / 留言
    m = re.search(r"(?:写|发|发表|更新)(?:一?篇|个|条)?日志[:：，,\s]*(.{2,60})$", raw.strip())
    if m:
        body = m.group(1).strip()
        title = re.split(r"[，,。.！!？?\s]", body)[0][:14] or "今天的日志"
        return Intent([{"action": "zone_blog", "title": title, "text": body}], "zone_blog", t="QQ空间")
    m = re.search(r"(?:(?:给|在|去)?(?:qq)?空间|主页)(?:里|上)?(?:留言|留个言|踩踩|写留言)[:：，,\s]*(.{1,40})$", raw.strip(), re.I)
    if m:
        return Intent([{"action": "zone_msg", "text": m.group(1).strip()}], "zone_msg", t="QQ空间")
    # 群共享下载
    m = re.search(r"(?:下载|下一个|下个|拉取|迅雷下载|用迅雷下)(?:群共享|群文件|共享文件)?(?:里的|里面的|的)?[:：\s]*(.{0,20})$", raw.strip())
    if m and re.search(r"群共享|群文件|共享|表情包|合集|\.rar|\.zip|\.mp3|壁纸|歌", n0) and not re.search(r"别|不要|不许", n0):
        nm = re.sub(r"^(?:群共享|群文件|共享文件|文件)[:：\s]*", "", m.group(1).strip())
        return Intent([{"action": "files_download"}] if nm in ("", "文件", "东西") else [{"action": "files_download", "name": nm[:16]}], "files_download", t="群共享")
    return None


def _play_parse(raw, n):
    """观众互动口令：放特效 / 看排行榜。投票数字、切歌、查积分、发起投票由 backend/play 在更前面处理，不会走到这里。"""
    n0 = R.norm(raw)
    if re.search(r"吗|么|为什么|为啥|怎么|是不是|有没有|了没", n0):
        return None
    pre = r"(?:来个|来一个|来点|来场|放个|放一个|放点|放|搞个|搞一个|整个|整一个|给我来个|给大家来个|给我放个|下一场|下个|下)?"
    for kind, w in (("fireworks", r"烟花|烟火|礼花|放炮"), ("meteor", r"流星雨|流星|星星雨"), ("emoji", r"表情雨|花瓣雨|撒花|爱心雨|红包雨"), ("virus", r"中毒|中病毒|熊猫烧香|病毒")):
        if re.fullmatch(r"(?:" + pre + r")(?:" + w + r")(?:特效|效果|一下|吧|呀|呗|看看)?", n0) or (kind == "virus" and re.fullmatch(r"(?:让电脑|电脑)(?:来个|中个)?(?:中毒|中病毒)(?:一下|吧|看看)?", n0)):
            return Intent([{"action": "play_fx", "kind": kind}], "fx_" + kind, t="特效", emotion="兴奋")
    if re.search(r"排行榜|积分榜|日榜|总榜|排行", n0) and not re.search(r"关闭|关掉|关了|别|不要", n0) and re.search(r"看|打开|开|查|显示|来个|瞧|给我|让我", n0):
        by = "total" if "总榜" in n0 else "day"
        return Intent([{"action": "open_app", "app": "rank"}, {"action": "rank_open", "by": by}], "rank_open", t="排行榜")
    return None


def _aiplus_parse(raw, n):
    """AI 加强包口令：玩小游戏 / 结束游戏 / 点评屏幕 / 点评这首歌。"""
    n0 = R.norm(raw)
    if re.search(r"吗|么|为什么|为啥|怎么|是不是|有没有|了没|怎样|如何", n0):
        return None
    pre = r"(?:我们|咱们|大家|一起|来|玩|开始|开|搞|整|再|想|想玩|要|要玩|给我|给大家|来个|来局|来场|来把|下一局|下一场|下一个|换成|换个)*(?:一局|一把|一场|一个|个|局|场|把)?"
    for g, w in (("idiom", r"成语接龙|接龙|成语游戏"), ("song", r"猜歌名|猜歌|猜歌曲|听歌猜名|猜歌游戏"), ("riddle", r"脑筋急转弯|急转弯|猜谜语|猜谜|谜语")):
        if re.fullmatch(r"(?:" + pre + r")(?:" + w + r")(?:游戏|小游戏|吧|呀|呗|一下|看看|来|玩玩)*", n0):
            return Intent([{"action": "game_start", "game": g}], "game_start", t={"idiom": "成语接龙", "song": "猜歌名", "riddle": "脑筋急转弯"}[g], emotion="兴奋")
    if re.fullmatch(r"(?:结束|停止|停掉|关掉|取消|退出|不玩|别玩|不要玩|先不玩|不想玩)(?:当前|这个|这局|本局|这场)?(?:的)?(?:小?游戏|接龙|成语接龙|猜歌名|猜歌|急转弯|脑筋急转弯)?(?:了|吧|啦|算了)*", n0) and re.search(r"游戏|接龙|猜歌|急转弯|不玩|别玩", n0):
        return Intent([{"action": "game_stop"}], "game_stop", t="游戏")
    if re.fullmatch(r"(?:帮我|给我|请)?(?:点评|评论|评价|说说|聊聊|讲讲|看看|讲一讲|说一说)(?:一下|下)?(?:这个|当前|现在的|现在|你的)?(?:屏幕|画面|桌面|电脑)(?:上|里)?(?:的东西|的内容|内容|的情况|在放什么|在干嘛)?(?:吧|呗|一下|看看)?", n0):
        return Intent([{"action": "screen_comment"}], "screen_comment", t="屏幕点评")
    if re.fullmatch(r"(?:帮我|给我|请)?(?:点评|评论|评价|说说|聊聊|讲讲|讲一讲|说一说)(?:一下|下)?(?:这首歌曲?|这首|这歌|当前的歌|现在的歌|现在这首歌|正在放的歌|这个歌)(?:吧|呗|一下|看看)?", n0):
        return Intent([{"action": "song_comment"}], "song_comment", t="歌曲点评")
    return None


def parse(text, desk=None):
    raw = clean(text)
    keep = FILLER_HEAD.sub("", str(text or "").strip()).strip()      # 打字内容要保留原话（含“猪猪侠”）
    if not raw or len(raw) > 90:
        return None
    n = R.norm(raw)
    if not n:
        return None
    n = FILLER_TAIL.sub("", n) or n
    app = R.find_app(n)

    # ---- 撤销 ----
    if re.match(r"^(?:撤销|撤回|还原刚才|恢复刚才|复原|恢复原样|undo|取消刚才|刚才的不要了|变回来|弄回去|还原回来|撤销刚才|撤销上一步|撤销操作)", n):
        return Intent([{"action": "undo"}], "undo", t="刚才的操作")

    # ---- 音乐：必须是短句，避免把「下一首唱xxx」当成切歌 ----
    mus = re.fullmatch(r"(?:切一?下一?首|下一首歌?|下首歌?|下一曲|下个歌|下一个歌|切歌|换歌|换一首歌?|换首歌|换个歌|换一首吧|跳过这首歌?|跳过|切下一首|播放下一首|放下一首|下一个|next)", n)
    if mus and not (app and app not in ("ttplayer",)):
        return Intent([{"action": "music_next"}], "music_next", t="下一首")
    if re.fullmatch(r"(?:上一首歌?|上首歌?|上一曲|前一首歌?|返回上一首|上一个歌|播放上一首|放上一首|切回上一首|prev|previous|上一个)", n):
        return Intent([{"action": "music_prev"}], "music_prev", t="上一首")
    vid = bool(re.search(r"视频|影音|暴风|电影|录像", n))
    if re.fullmatch(r"(?:暂停(?:播放|音乐|放歌|歌曲|一下)?|停一下|停止播放|别放了|不要放了|先别放|停掉|关音乐|关掉音乐|暂停歌曲|pause|先暂停|停歌|停止音乐|歌停一下)", n) and not vid and not (app and app != "ttplayer"):
        return Intent([{"action": "music_pause"}], "music_pause", t="音乐")
    if re.fullmatch(r"(?:继续播放|继续放|接着放|恢复播放|开始播放|播放音乐|放歌|放音乐|播放|play|继续放歌|继续放音乐|放首歌|放点音乐|放点歌|继续音乐|恢复音乐)", n) and not vid:
        return Intent([{"action": "music_play"}], "music_play", t="音乐")
    if vid and re.search(r"暂停|播放|继续|停", n) and not re.search(r"第[0-9一二三四]|下一个", n) and not re.search(OPEN_V, n[:2]):
        return Intent([{"action": "video_toggle"}], "video_toggle", t="视频")

    # ---- 壁纸 ----
    if (re.search(r"(?:换|改|设置?|设|变|切|更换)(?:一?个|成|为|下|一下|点)?(?:桌面)?(?:壁纸|墙纸|背景(?!音乐|乐|故事|板|图案|里|下)|桌布)", n) or re.search(r"(?:壁纸|墙纸|桌布|桌面背景).{0,4}(?:换|改)", n)
            or re.search(r"换(?:个|一个|下)?(?:桌面|背景(?!音乐|乐|故事|板))", n) or re.search(r"(?:换|设置?|改)成.{1,6}(?:的)?(?:壁纸|桌面|背景(?!音乐|乐|故事|板))", n)):
        name = R.find_wallpaper(n)
        if _neg_before(n, re.search(r"换|改|设", n)):
            return _sk("wallpaper")
        nm = name or ("next" if re.search(r"下一个|下一张|next", n) else "random")
        return Intent([{"action": "change_wallpaper", "name": nm}], "wallpaper", t=name or "壁纸")

    # ---- 开始菜单 ----
    if "开始菜单" in n:
        close = bool(re.search(r"关闭|关掉|收起|关上|关了|取消", n))
        return Intent([{"action": "start_menu", "state": "close" if close else "open"}], "start_menu", t="开始菜单")

    # ---- 刷新 / 显示桌面 / 全部关闭 / 平铺 / 图标 ----
    if re.fullmatch(r"(?:刷新|刷新一下|刷新桌面|桌面刷新|f5|按f5|刷新下|刷新一下桌面)", n) or n in ("刷新桌面", "刷新下桌面"):
        return Intent([{"action": "refresh_desktop"}], "refresh", t="桌面")
    if re.search(r"(?:显示桌面|回到桌面|露出桌面|看桌面|全部最小化|最小化(?:所有|全部)|所有窗口(?:都)?最小化|窗口(?:都|全)?(?:最小化|收起来|收起)|清屏|把窗口(?:都|全)?(?:收起来|收起|最小化))", n):
        return Intent([{"action": "show_desktop"}], "show_desktop", t="桌面")
    if re.search(r"(?:关闭|关掉|关了|清掉|关上|全部关|都关了|都关掉|全关了|全关掉)(?:所有|全部|一切)?(?:的)?(?:窗口|程序|软件)?", n) and re.search(r"(?:所有|全部|一切|都|全)", n) and re.search(r"(?:窗口|程序|软件|关掉|关了)", n) and not app:
        if not _neg_before(n, re.search(r"关", n)):
            return Intent([{"action": "close_all"}], "close_all", t="所有窗口")
    mt = re.search(r"(平铺|层叠|堆叠|排列窗口|整理窗口)", n)
    if mt:
        mode = "cascade" if re.search(r"层叠|堆叠", n) else "vertical" if re.search(r"纵向|竖向|垂直", n) else "horizontal"
        return Intent([{"action": "tile", "mode": mode}], "tile", t="窗口")
    if re.search(r"(?:排列|整理|排一?下|排序|对齐|排好).{0,3}(?:桌面)?(?:的)?图标|整理桌面|图标.{0,3}(?:排列|整理|排序|排好|乱了)|桌面.{0,2}(?:太乱|乱了)", n):
        by = "name"
        for k, rx in (("auto", r"自动"), ("size", r"大小"), ("type", r"类型"), ("time", r"时间|日期|修改"), ("group", r"分组|按组"), ("name", r"名称|名字")):
            if re.search(rx, n):
                by = k
                break
        return Intent([{"action": "arrange_icons", "by": by}], "arrange", t="图标")

    # ---- 往软件里打字（取原句，保留大小写和标点）----
    m = re.search(r"记事本[里中上内]?(?:帮我|替我)?(?:写下|写上|写|输入|打上|打|敲|记下|记|打字|输入文字)(?:一句|一行|个|下)?[:：\s]*(.+)$", keep)
    if m and m.group(1).strip():
        return Intent([{"action": "notepad_type", "text": m.group(1).strip()}], "notepad_type", t="记事本")
    m = re.search(r"(?:群聊|聊天框|聊天窗口|qq群|群里|群窗口|输入框|聊天室)[里中上内]?(?:帮我|替我)?(?:发送|发个|发一条|发|说|输入|打|喊)(?:一句|一条|个|下)?[:：\s]*(.+)$", keep, re.I)
    if m and m.group(1).strip():
        return Intent([{"action": "qq_send", "text": m.group(1).strip()}], "qq_send", t="群聊")
    m = re.search(r"(?:cmd|命令提示符|黑框框?|dos|终端|控制台)[里中上内]?(?:帮我|替我)?(?:输入|运行|执行|敲|打)[:：\s]*(.+)$", keep, re.I)
    if m and m.group(1).strip():
        return Intent([{"action": "cmd_run", "command": m.group(1).strip()}], "cmd_run", t="命令提示符")
    # 计算
    m = re.search(r"(?:算一下|算算|计算一下|计算|算下|算)[:：\s]*([0-9+\-*/xX×÷().]+)\s*(?:=|等于几|等于多少)?$", raw)
    if not m:
        m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?(?:\s*[+\-*/xX×÷]\s*[0-9]+(?:\.[0-9]+)?)+)\s*(?:=|等于几|等于多少|=几|=多少|是多少)\s*[?？]?\s*", raw)
    if m:
        return Intent([{"action": "calc", "expr": m.group(1).replace("×", "*").replace("x", "*").replace("X", "*").replace("÷", "/").replace(" ", "")}], "calc", t="计算器")

    # 疑问句（“红警怎么玩”）不是指令，也别问 LLM
    if QUESTION.search(n) and not re.search(r"能不能|可不可以|可以|帮我", str(text)) and (app or looks_like_command(raw)):
        return _sk("question")

    # ---- 扫雷 ----
    mine_open = bool(desk and "minesweeper" in desk.apps_open())
    if app == "minesweeper" or (mine_open and re.search(r"[点扫开挖踩插标]", n)):
        m = re.search(r"(?:点|扫|开|挖|踩)(?:开)?(?:第)?([0-9]{1,2})(?:行|排|,|，)(?:第)?([0-9]{1,2})(?:列|个|格)?", raw)
        if m:
            return Intent([{"action": "mine_click", "row": int(m.group(1)), "col": int(m.group(2))}], "mine_click", t="扫雷")
        m = re.search(r"(?:标记|插旗|插个旗|旗子|标旗|右键)(?:第)?([0-9]{1,2})(?:行|排|,|，)(?:第)?([0-9]{1,2})(?:列|个|格)?", raw)
        if m:
            return Intent([{"action": "mine_flag", "row": int(m.group(1)), "col": int(m.group(2))}], "mine_flag", t="扫雷")
        if re.search(r"(?:高级|专家)", n):
            return Intent([{"action": "open_app", "app": "minesweeper"}, {"action": "mine_new", "level": "expert"}], "mine_new", t="扫雷")
        if re.search(r"中级", n):
            return Intent([{"action": "open_app", "app": "minesweeper"}, {"action": "mine_new", "level": "intermediate"}], "mine_new", t="扫雷")
        if re.search(r"初级|新手", n):
            return Intent([{"action": "open_app", "app": "minesweeper"}, {"action": "mine_new", "level": "beginner"}], "mine_new", t="扫雷")
        if re.search(r"开新局|新局|重新开始|重开|再来一局|再来一把|重玩|新游戏", n):
            return Intent([{"action": "open_app", "app": "minesweeper"}, {"action": "mine_new"}], "mine_new", t="扫雷")
        if re.search(r"玩|自动|帮我扫|替我扫|ai|来一把|来一局|打一局|开始扫|扫一扫|扫几步|试试", n) and not re.search(CLOSE_V, n):
            return Intent([{"action": "open_app", "app": "minesweeper"}, {"action": "mine_play", "steps": 10}], "mine_play", t="扫雷")

    # ---- 纸牌 / 空当接龙 ----
    if app in ("solitaire", "freecell") and not re.search(CLOSE_V, n):
        pre = "sol" if app == "solitaire" else "fc"
        if app == "freecell":
            m = re.search(r"(?:第|编号|号码|#)\s*([0-9]{1,5})(?:号|局|副)?", raw) or re.search(r"([0-9]{1,5})(?:号|局|副)", raw)
            if m and 1 <= int(m.group(1)) <= 32000:
                return Intent([{"action": "open_app", "app": app}, {"action": "fc_new", "no": int(m.group(1))}], "fc_new", t="空当接龙")
        if re.search(r"开新局|新局|重新开始|重开|再来一局|再来一把|重玩|新游戏|重新发牌|换一副|发牌", n):
            d = ({"draw": 3} if re.search(r"三张|3张|翻三", n) else {}) if app == "solitaire" else {}
            return Intent([{"action": "open_app", "app": app}, dict({"action": pre + "_new"}, **d)], pre + "_new", t=_tname(app))
        if re.search(r"玩|自动|帮我|替我|ai|来一把|来一局|打一局|开始|试试|摆|拖", n):
            return Intent([{"action": "open_app", "app": app}, {"action": pre + "_play", "steps": 12}], pre + "_play", t=_tname(app))
    # ---- 画图 ----
    DRAW = {"smile": "笑脸|微笑|小脸|表情", "house": "房子|小屋|房屋|家", "sun": "太阳|日头|小太阳", "flower": "花|小花|花朵|鲜花", "heart": "爱心|心形|红心|心", "star": "星星|五角星|星", "tree": "树|大树|小树", "boat": "小船|帆船|船"}
    md = re.search(r"(?:画|绘)(?:一个|个|一幅|幅|一朵|朵|一棵|棵|一只|只|一颗|颗|一艘|艘|一座|座)?(?:[:：\s]*)(\S{1,6})$", raw.strip()) if re.search(r"画", raw) else None
    if md and not re.search(CLOSE_V, n):
        subj = md.group(1)
        for k, alts in DRAW.items():
            if re.fullmatch(r"(?:" + alts + r")(?:吧|呗|看看|给我看|来看看|给大家看)?", subj):
                return Intent([{"action": "open_app", "app": "paint"}, {"action": "paint_draw", "what": k}], "paint_draw", t="画图")
    if app == "paint" and re.search(r"清除|清空|擦掉|擦干净|重画|清屏", n) and not re.search(CLOSE_V, n):
        return Intent([{"action": "open_app", "app": "paint"}, {"action": "paint_clear"}], "paint_clear", t="画图")
    if app == "paint" and re.search(r"随便画|乱画|画一幅|画幅画|画点|画画|画个画|玩|涂鸦", n) and not re.search(CLOSE_V, n):
        return Intent([{"action": "open_app", "app": "paint"}, {"action": "paint_draw", "what": "smile"}], "paint_draw", t="画图")
    # ---- 控制面板小程序 ----
    if app in ("sndcpl", "mousecpl") and not re.search(CLOSE_V, n):
        return Intent([{"action": "control_open", "item": "声音" if app == "sndcpl" else "鼠标"}], "control_open", t=_tname(app))
    # ---- 观众互动口令 ----
    pi = _play_parse(raw, n)
    if pi:
        return pi
    ai = _aiplus_parse(raw, n)
    if ai:
        return ai
    # ---- QQ 生态口令 ----
    qi = _qq_parse(raw, n, text)
    if qi:
        return qi
    # ---- XP 彩蛋 ----
    if re.fullmatch(r"(?:来个|来一个|搞个|搞一个|整个|弄个|弄一个|给我来个|给我整个|触发|制造|让电脑)?(?:一下)?(?:蓝屏|蓝屏彩蛋|bsod)(?:吧|一下|看看|试试|彩蛋|呗)?", n):
        return Intent([{"action": "bsod"}], "bsod", t="蓝屏", emotion="开心")
    if re.fullmatch(r"(?:弹|来|冒|搞)(?:个|一个)?(?:气泡|托盘通知|新硬件|发现新硬件)(?:通知|提示)?(?:看看|吧|呗)?", n):
        return Intent([{"action": "balloon", "kind": "hardware"}], "balloon", t="气泡")

    # ---- 游戏：玩/开始 = 打开并开始；打开 = 只打开 ----
    gm = [a for a in R.find_all_apps(n) if a in R.GAME_APPS]
    if gm:
        g = gm[0]
        mchat = re.search(r"(?:里|中|上)(?:面)?(?:发|说|聊|喊)(?:一句|一条|个)?[:：\s]*(.+)$", raw)
        if g == "mir2" and mchat and mchat.group(1).strip():
            return Intent([{"action": "game_start", "app": "mir2"}, {"action": "mir2_chat", "text": mchat.group(1).strip()}], "mir2_chat", t=_tname(g))
        if re.search(r"(?:玩|开始|进入|进游戏|开局|来一把|来一局|打一把|打一局|开打|开黑|玩玩|玩一玩|开玩|启动游戏|试玩)", n) and not re.search(CLOSE_V, n):
            m0 = re.search(r"(?:玩|开始|进入|开局|来一把|来一局|打一把|打一局|开打|开黑|玩玩|玩一玩|开玩|启动游戏|试玩)", n)
            if _neg_before(n, m0):
                return _sk("game")
            acts = [{"action": "game_start", "app": g}]
            if g == "audition":
                acts.append({"action": "dance", "count": 8})
            return Intent(acts, "game_start", t=_tname(g))
        if re.search(r"(?:退出游戏|回主菜单|返回菜单|回到菜单|返回主菜单|esc|回菜单)", n) and not re.search(r"关闭|关掉", n):
            return Intent([{"action": "game_back", "app": g}], "game_back", t=_tname(g))
        if re.search(r"(?:跳舞|按方向键|打节奏|跳起来)", n) and g == "audition":
            return Intent([{"action": "game_start", "app": "audition"}, {"action": "dance", "count": 8}], "dance", t=_tname(g))
    if re.search(r"^(?:玩游戏|玩个游戏|玩点游戏|来个游戏|来点游戏|玩玩游戏)$", n):
        return Intent([{"action": "game_start", "app": "ra2"}], "game_start", t=_tname("ra2"))

    # ---- 音量 ----
    m = re.search(r"(?:音量|声音)(?:调|开|设|设置|调到|调成|开到|设成|设为|到)?(\d{1,3})", n)
    if m:
        return Intent([{"action": "set_volume", "value": min(100, int(m.group(1)))}], "volume", t="音量")
    if re.fullmatch(r"(?:静音|关掉声音|关闭声音|没声音|把声音关了|声音关了|声音关掉|打开静音)", n):
        return Intent([{"action": "set_volume", "mute": True}], "mute", t="声音")
    if re.fullmatch(r"(?:取消静音|开声音|打开声音|恢复声音|解除静音|开启声音|声音打开|声音开开)", n):
        return Intent([{"action": "set_volume", "mute": False}], "unmute", t="声音")
    if re.fullmatch(r"(?:大声点|大点声|调大(?:声音|音量)?|音量大点|音量调高|声音大点|声音调大|加大音量|大声一点)", n):
        return Intent([{"action": "set_volume", "value": 90, "mute": False}], "volume", t="音量")
    if re.fullmatch(r"(?:小声点|小点声|调小(?:声音|音量)?|音量小点|音量调低|声音小点|声音调小|降低音量|小声一点)", n):
        return Intent([{"action": "set_volume", "value": 30}], "volume", t="音量")

    # ---- 暴风影音 / 浏览器 ----
    if app == "baofeng":
        m = re.search(r"第?([1-4一二三四])(?:个|部|段)?", n)
        if m and re.search(r"播放|放|看", n) and not re.search(CLOSE_V, n):
            k = "一二三四".find(m.group(1)) + 1 or int(m.group(1))
            return Intent([{"action": "open_app", "app": "baofeng"}, {"action": "video_play", "clip": k}], "video_play", t="暴风影音")
        if re.search(r"(?:播放|放|看)(?:个)?(?:视频|电影|片|录像)", n):
            return Intent([{"action": "open_app", "app": "baofeng"}, {"action": "video_play", "clip": 1}], "video_play", t="暴风影音")
    SITES = {"淘宝": "taobao.com", "百度": "baidu.com", "新浪": "sina.com.cn", "搜狐": "sohu.com", "网易": "163.com", "优酷": "youku.com", "4399": "4399.com",
             "谷歌": "google.com", "google": "google.com", "腾讯网": "qq.com", "天涯": "tianya.cn", "迅雷": "xunlei.com", "携程": "ctrip.com", "17173": "17173.com"}
    m = re.search(r"(?:上网|打开网页|浏览|访问|去|打开|逛|上)(?:网站|一下|下)?[:：\s]*((?:https?://)?[a-z0-9][a-z0-9.\-]*\.[a-z]{2,6}(?:/\S*)?)", raw, re.I)
    if m:
        return Intent([{"action": "browse", "url": m.group(1)}], "browse", t="网页")
    if re.search(r"(?:上|逛|去|打开|访问|看看)(?:一下|下)?(" + "|".join(SITES) + ")", n) and not re.search(CLOSE_V, n):
        for k, v in SITES.items():
            if k in n:
                return Intent([{"action": "browse", "url": v}], "browse", t=k)

    # ---- 挡住了（可带目标） ----
    mv_block = re.search(BLOCK_W, n)
    # ---- 窗口动词 + 目标 ----
    verbs = [("minimize_window", MIN_V, "min"), ("maximize_window", MAX_V, "max"), ("restore_window", RESTORE_V, "restore"),
             ("close_window", CLOSE_V, "close"), ("move", MOVE_V, "move"), ("open_app", OPEN_V, "open"), ("focus_window", FOCUS_V, "focus")]
    hit = None
    for act, rx, key in verbs:
        mm = re.search(rx, n)
        if mm:
            hit = (act, key, mm)
            break
    if hit:
        act, key, mm = hit
        if _neg_before(n, mm):
            return _sk(key)
        if QUESTION.search(n) and not re.search(r"能不能|可不可以|可以", raw):
            return _sk(key)
        pron = re.search(PRON, n)
        # “把X关掉”：目标 X 取动词两侧最先出现的应用名
        tgt_app = app
        tgt = None
        if key == "move" and (mv_block or not position_of(n[mm.end():])):
            if app:
                return Intent([{"action": "move_away", "target": app}], "move_away", t=_tname(app), emotion="平静")
            return Intent([{"action": "move_away"}], "move_away", t="挡住的窗口", emotion="平静")
        if key == "move":
            to = position_of(n[mm.end():]) or position_of(n)
            if tgt_app:
                return Intent([{"action": "move_window", "target": tgt_app, "to": to or "right"}], "move", t=_tname(tgt_app), emotion="平静")
            if pron or mv_block:
                return Intent([{"action": "move_window", "target": "active", "to": to or "right"}], "move", t="这个窗口", emotion="平静")
            return None
        if key == "open":
            if tgt_app == "qqchat":
                return Intent([{"action": "open_app", "app": "qqchat"}], "open", t="群聊窗口")
            if tgt_app:
                path = R.EXPLORER_PATHS.get(tgt_app)
                return Intent([{"action": "open_app", "app": tgt_app}], "open", t=_tname(tgt_app))
            return None
        if key == "focus":
            if tgt_app:
                return Intent([{"action": "focus_window", "target": tgt_app}], "focus", t=_tname(tgt_app), emotion="平静")
            return None
        # 关闭 / 最小化 / 最大化 / 还原
        if tgt_app:
            tgt = tgt_app
        elif mv_block:
            tgt = "blocking"
        elif pron and len(n) <= 10:
            tgt = "active"
        elif key in ("close", "min") and re.fullmatch(r"(?:关闭|关掉|关了|关上|关|叉掉|干掉|最小化|缩小|收起来|收起)(?:它|这个|当前|窗口|这个窗口|当前窗口)?", n):
            tgt = "active"
        if not tgt:
            return None
        nm = {"blocking": "挡住的窗口", "active": "这个窗口"}.get(tgt) or _tname(tgt)
        return Intent([{"action": act, "target": tgt}], key, t=nm, emotion="平静" if key != "close" else "开心")
    if mv_block:
        if re.search(r"歌词|字幕|聊天|群聊|弹幕|播放器|千千|主播|猪猪侠|qq秀|画面|屏幕|视线|我", n) or len(n) <= 8:
            return Intent([{"action": "move_away", **({"target": app} if app and app != "qqchat" and app != "ttplayer" else {})}], "move_away", t="挡住的窗口", emotion="平静")
    # 只说了应用名 / 想看某个东西：“红警” 这种单词不当指令
    return None


def looks_like_command(text, name=NAME):
    """要不要问 LLM：弹幕里有操作类词汇/应用名/喊了主播名（llm_gate=keywords 时用）。"""
    t = str(text or "")
    if len(t) < 2 or len(t) > 90:
        return False
    if re.search(r"(?:打开|关闭?|最小|最大|挪|移开|挡|遮|切|换|播放|暂停|下一首|上一首|壁纸|刷新|开始菜单|桌面|窗口|玩|游戏|扫雷|记事本|计算|音量|静音|排列|整理|撤销|还原|恢复|点开|点击|打字|输入|发送|写|算|放|帮我|能不能|可以.*吗|麻烦|让开|看不到|看不见|跳舞|上网|网页|浏览)", t):
        return True
    if R.find_app(t):
        return True
    return name in t and len(t) > len(name) + 1
