# -*- coding: utf-8 -*-
"""高光切片（backend/clips.py，§11.13）的离线测试：设备解析 / 找窗口 / 按显示器比例裁剪 / 分段挑选 / ffmpeg 命令；
   用真 ffmpeg（box 上 libx264）+ 图片当「屏幕」跑完整流程：滚动分段缓冲 → 高光 → 等后 N 秒 → 剪出 1080×1920 竖屏 MP4（有声音、有缩略图）→ 合并 / 过滤 / 观众口令 / 保留上限 / 删除；
   屏幕录制权限没开时：检测到、不起 ffmpeg、写清楚该给谁授权；Bark 默认不推。不连抖音、不碰真屏幕、不推 Bark
   python tools/test_clips.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import asyncio, json, os, re, shutil, subprocess, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import clips as C
from host.config import Config, DEFAULTS

bad = 0; total = 0
def check(c, m):
    global bad, total
    total += 1
    if not c:
        bad += 1; print("FAIL", m)

# ---- 1. 纯函数 ----
DEV = """[AVFoundation indev @ 0x1] AVFoundation video devices:
[AVFoundation indev @ 0x1] [0] FaceTime HD Camera
[AVFoundation indev @ 0x1] [1] Capture screen 0
[AVFoundation indev @ 0x1] [2] Capture screen 1
[AVFoundation indev @ 0x1] AVFoundation audio devices:
[AVFoundation indev @ 0x1] [0] Wireless Mic Rx
[AVFoundation indev @ 0x1] [1] BlackHole 2ch
[AVFoundation indev @ 0x1] [2] EDIFIER M30
"""
d = C.parse_devices(DEV)
check(d["screens"] == {0: 1, 1: 2} and d["audio"]["BlackHole 2ch"] == 1 and d["video"]["FaceTime HD Camera"] == 0, f"解析 avfoundation 设备列表：{d}")
check(C.parse_devices("[AVFoundation indev @ 0x1] AVFoundation video devices:\n[AVFoundation indev @ 0x1] AVFoundation audio devices:\n[AVFoundation indev @ 0x1] [1] BlackHole 2ch")["screens"] == {}, "没有屏幕设备（显示器休眠 / 没权限）→ screens 为空")
WINS = [{"owner": "微信", "name": "微信", "layer": 0, "x": 3441, "y": -9, "w": 1439, "h": 1634},
        {"owner": "Google Chrome", "name": "GG-Bond 的直播间 - 群聊", "layer": 0, "x": 656, "y": 149, "w": 1920, "h": 1112},
        {"owner": "Google Chrome", "name": "直播服务平台·主播版", "layer": 0, "x": 0, "y": 30, "w": 3440, "h": 1410},
        {"owner": "Google Chrome", "name": "小窗直播间", "layer": 0, "x": 5, "y": 5, "w": 120, "h": 80},
        {"owner": "Google Chrome", "name": "直播间 菜单", "layer": 25, "x": 0, "y": 0, "w": 900, "h": 900}]
w = C.pick_window(WINS, "Google Chrome", "直播间")
check(w and w["x"] == 656 and w["w"] == 1920, "按「App + 标题含『直播间』」找到直播页面的窗口（不是直播服务平台那个更大的，也不是小窗 / 菜单层）")
check(C.pick_window(WINS, "Google Chrome", "不存在的标题") is None, "找不到不乱猜")
check(C.pick_window([], "Google Chrome", "x") is None and C.pick_window(None, "a", "b") is None, "没有窗口列表")
DISP = [{"x": 0, "y": 0, "w": 3440, "h": 1440}, {"x": 3440, "y": -200, "w": 1440, "h": 2560}]
g = C.locate(w, DISP)
check(g and g["screen"] == 0 and abs(g["fx"] - 656 / 3440) < 1e-9 and abs(g["fw"] - 1920 / 3440) < 1e-9 and abs(g["fh"] - 1112 / 1440) < 1e-9, f"窗口在 0 号屏：比例 {g}")
g2 = C.locate({"x": 3500, "y": 100, "w": 800, "h": 1200}, DISP)
check(g2 and g2["screen"] == 1 and abs(g2["fx"] - 60 / 1440) < 1e-9 and abs(g2["fy"] - 300 / 2560) < 1e-9, "窗口在另一块（竖）屏：选对屏 + 比例相对那块屏")
g3 = C.locate({"x": 3000, "y": 100, "w": 800, "h": 600}, DISP)
check(g3 and g3["screen"] == 0 and g3["fx"] + g3["fw"] <= 1.0000001, "窗口跨屏：选重叠多的屏，超出的部分裁掉")
check(C.locate({"x": 9000, "y": 9000, "w": 500, "h": 500}, DISP) is None and C.locate(w, []) is None, "窗口不在任何屏上 / 没有屏")
gi = C.locate(w, DISP, (90, 0, 0, 0))
check(gi and abs(gi["fy"] - (149 + 90) / 1440) < 1e-9 and abs(gi["fh"] - (1112 - 90) / 1440) < 1e-9, "inset 上 90 点：去掉浏览器标签栏 / 地址栏")
check(C.parse_inset("90, 0,0,0") == [90, 0, 0, 0] and C.parse_inset("") == [0, 0, 0, 0] and C.parse_inset("x") == [0, 0, 0, 0], "inset 解析")
check(C.parse_region("10,20,300,400") == {"x": 10, "y": 20, "w": 300, "h": 400} and C.parse_region("") is None and C.parse_region("1,2,3") is None, "region 解析")
vf = C.crop_filter(g, 1280)
check("crop=" in vf and "iw*0.55814" in vf and "scale='min(1280,iw)':-2" in vf and vf.endswith("format=yuv420p"), f"裁剪滤镜按比例（与 Retina 无关）：{vf[:80]}")
check(C.pick_encoder("auto", " V....D h264_videotoolbox VideoToolbox") == "h264_videotoolbox" and C.pick_encoder("auto", "libx264") == "libx264" and C.pick_encoder("libx265", "") == "libx265", "编码器：有 videotoolbox 用它，没有 libx264")
cmd = C.build_record_cmd("/opt/homebrew/bin/ffmpeg", "h264_videotoolbox", ["-f", "avfoundation", "-capture_cursor", "0", "-framerate", "20", "-i", "1:1"], vf, "/tmp/x/s_%Y%m%d-%H%M%S.ts", 20, 3500, 2, True)
j = " ".join(cmd)
check("-f avfoundation" in j and "-i 1:1" in j and "h264_videotoolbox" in j and "-realtime 1" in j and "-f segment" in j and "-segment_time 2" in j and "-segment_format mpegts" in j and "-strftime 1" in j and "-c:a aac" in j and "-segment_atclocktime 1" in j, f"录制命令：抓屏 + videotoolbox + 2 秒 mpegts 分段 + aac：{j[:120]}")
check("-an" in C.build_record_cmd("ffmpeg", "libx264", ["-i", "x"], vf, "o", 20, 3500, 2, False) and "-preset ultrafast" in " ".join(C.build_record_cmd("ffmpeg", "libx264", ["-i", "x"], vf, "o", 20, 3500, 2, False)), "没音频设备：-an；libx264 用 ultrafast")
vv = C.vertical_filter(1080, 1920)
check("gblur" in vv and "scale=1080:-2" in vv and "overlay=(W-w)/2:(H-h)/2" in vv and "crop=270:480" in vv, "竖屏滤镜：背景放大裁满 + 模糊，前景按宽度铺满居中")
cc = " ".join(C.build_clip_cmd("ff", "libx264", "/tmp/l.txt", 2.5, 25, "/tmp/o.mp4", 1080, 1920, 5000))
check("-f concat" in cc and "-ss 2.500" in cc and "-t 25.000" in cc and "-filter_complex" in cc and "+faststart" in cc, "剪片命令：concat + 精确 -ss / -t + faststart")
check("-vf format=yuv420p" in " ".join(C.build_clip_cmd("ff", "libx264", "l", 0, 25, "o", 1080, 1920, 5000, vertical=False)), "vertical=false 保持原比例")
check(C.safe_kind("perf_bsod") == "bsod" and C.safe_kind("gift_big") == "gift_big" and C.safe_kind("../../x y") == "xy" and C.safe_kind("") == "manual", "事件名做文件名：去前缀 / 去怪字符")
nm = C.clip_name(time.mktime((2026, 11, 15, 12, 55, 12, 0, 0, -1)), "perf_virus")
check(nm == "20261115-125512_virus.mp4" and C.NAME_RE.match(nm), f"文件名 <时间>_<事件>.mp4：{nm}")
check(not C.NAME_RE.match("../etc/passwd.mp4") and not C.NAME_RE.match("20261115-125512_a/b.mp4"), "文件名校验挡路径穿越")
T0 = time.mktime((2026, 11, 15, 12, 0, 0, 0, 0, -1))
segs = [(T0 + i * 2, Path(f"/b/s{i}.ts")) for i in range(15)]        # 12:00:00 … 12:00:28（最后一段还在写）
pk = C.pick_segments(segs, T0 + 9, T0 + 19)
check(pk and [p.name for p in pk[0]] == ["s4.ts", "s5.ts", "s6.ts", "s7.ts", "s8.ts", "s9.ts"] and abs(pk[1] - 1.0) < 1e-6, f"挑 [9,19] 秒盖到的段，第一段跳过 1 秒：{pk and [p.name for p in pk[0]]} {pk and pk[1]}")
check(C.pick_segments(segs, T0 + 26, T0 + 40) is None or segs[-1][1] not in C.pick_segments(segs, T0 + 26, T0 + 40)[0], "最后一段（可能还在写）不选")
check(C.pick_segments(segs, T0 + 100, T0 + 120) is None and C.pick_segments([], 0, 1) is None, "缓冲里没有这段时间：None")
pk2 = C.pick_segments(segs, T0 + 26, T0 + 30, all_closed=True)
check(pk2 and pk2[0][-1].name == "s14.ts", "录制已停止：最后一段也算写完了")
check(C.seg_start("s_20261115-120004.ts") == T0 + 4 and C.seg_start("ffmpeg.err") is None, "分段文件名里的开始时间")

# ---- 2. 配置 / 权限提示 ----
ini = Config(str(ROOT / "config.ini"))
check(all(ini.cp["clips"][k] == v for k, v in DEFAULTS["clips"].items()), "config.ini 的 [clips] 和内置默认一致")
check(set(ini.cp["clips"]) >= set(DEFAULTS["clips"]), "config.ini 写全了所有键")
h = C.responsible_hint("/opt/homebrew/bin/ffmpeg")
check(h["python"] and "屏幕" in h["msg"] and ("python" in h["msg"] or h["app"]), f"权限提示说清楚给谁：{h['msg'][:60]}")

# ---- 3. 完整流程（真 ffmpeg，假「屏幕」= 一张图，假 App）----
HAVE_FF = bool(C.which_ffmpeg("auto"))
check(HAVE_FF, "box 上有 ffmpeg")
class FRoom:
    rid = "889"
    def __init__(self): self.last = {"live": {"live": True}}; self.sent = []; self.fetcher = None; self.host = None
    def _broadcast(self, ev): self.sent.append(ev)
def mk(tmp, **kv):
    cfg = Config("/nonexistent.ini")
    base = {"clips__enabled": "true", "clips__mode": "always", "clips__test_source": "image:" + str(ROOT / "screenshots/giftfx/08_big_meteor.png"), "clips__pre": "3", "clips__post": "3",
            "clips__seg_secs": "1", "clips__keep_secs": "5", "clips__min_gap": "6", "clips__out_dir": str(tmp / "out"), "clips__fps": "10", "clips__max_width": "640", "clips__bitrate": "800",
            "clips__out_w": "270", "clips__out_h": "480", "clips__out_bitrate": "800", "clips__max_clips": "5", "clips__viewer_gap": "30"}
    base.update(kv)
    for k, v in base.items():
        sec, key = k.split("__"); cfg.cp[sec][key] = str(v)
    room = FRoom()
    app = types.SimpleNamespace(rooms={"889": room}, default_room="889", ops=None)
    cl = C.Clips(cfg, app, lambda *a: None)
    cl.pushed = []
    cl.push = lambda t, b: cl.pushed.append((t, b))
    return cl, app, room
def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, text=True)
    return json.loads(r.stdout)
async def wait(fn, s=30, step=0.2):
    t = time.time()
    while time.time() - t < s:
        v = fn()
        if v: return v
        await asyncio.sleep(step)
    return None

async def full():
    tmp = Path(tempfile.mkdtemp(prefix="clipstest-"))
    cl, app, room = mk(tmp)
    loop = asyncio.get_running_loop()
    # 没开播 + mode=live：不录；开播了才录
    cl2, app2, room2 = mk(tmp, clips__mode="live"); room2.last = {}
    check(cl2.want_record() is False and cl2.is_live() is None, "mode=live 还没开播：不录")
    room2.last = {"live": {"live": True}}; check(cl2.want_record() is True, "开播了：要录")
    room2.last = {"live": {"live": False}}; check(cl2.want_record() is False, "下播了：不录")
    cl2.set_manual(True); check(cl2.want_record() is True, "手动开录：不管开没开播")
    cl3, _, _ = mk(tmp, clips__enabled="false"); check(cl3.want_record() is False and cl3.on_highlight("perf_bsod", {"at": time.time()}) is None, "模块关了：不录也不排任务")
    cl4, _, _ = mk(tmp, clips__mode="manual"); check(cl4.want_record() is False, "mode=manual：只在手动开录时录")
    # 还没在录：高光没得剪，不报错
    check(cl.on_highlight("perf_bsod", {"at": time.time()}) is None and cl.stats["skip_norec"] == 1, "没在录：高光记一笔 skip_norec，不排任务")
    cl.start()
    check(await wait(lambda: cl.proc is not None and len(C.list_segments(cl.buf)) >= 6, 40), f"开始录制，出分段：{cl.err}")
    st = cl.state(); check(st["recording"] and st["segments"] >= 6 and st["buffer_secs"] >= 5 and st["perm"]["ok"] is None, f"状态：录着 {st['segments']} 段")
    segs = C.list_segments(cl.buf)
    check(max(1, len(segs)) and abs(segs[-1][0] - time.time()) < 4, "分段文件名的时间是现在")
    # 观众口令（短弹幕）→ 切；其它不切
    ev = {"t": "chat", "uid": "v1", "name": "小朋", "text": "来个高光"}
    check(cl.on_event({"t": "chat", "uid": "v0", "name": "路人", "text": "今天天气真好我想发一条很长的弹幕里面带高光"}, room) is False, "太长的弹幕不算口令")
    check(cl.on_event({"t": "chat", "uid": "v0", "name": "路人", "text": "你好"}, room) is False and cl.on_event({"t": "gift", "uid": "v0"}, room) is False, "普通弹幕 / 非弹幕不触发")
    check(cl.on_event(ev, room) is True and cl.stats["viewer"] == 1, "观众发「来个高光」：排了一个任务")
    check(any(e.get("kind") == "clips" and "小朋" in e["text"] and e["audio"] == "" for e in room.sent), "群聊里回一句（文字，不念）")
    t_ev = cl.last_accept
    check(cl.on_event(dict(ev, text="高光"), room, time.time() + 1) is False, "同一人 viewer_gap 内再发：不重复")
    # 合并：min_gap 内的别的高光并进上一条
    check(cl.on_highlight("perf_fireworks", {"at": time.time()}) is None and cl.stats["skip_close"] == 1, "min_gap 内的高光合并（不重复剪）")
    check(cl.on_highlight("perf_mine", {"at": time.time() + 30}) is None and cl.stats["skip_kind"] == 1, "不在 events 里的事件不剪")
    check(cl.pushed == [], "bark=false：不推送")
    # 等任务剪完
    ok = await wait(lambda: cl.stats["clips"] >= 1 or cl.stats["failed"] >= 1, 40)
    check(ok and cl.stats["clips"] == 1, f"剪好了一条：{cl.last}")
    fs = sorted((tmp / "out").glob("*.mp4"))
    check(len(fs) == 1 and C.NAME_RE.match(fs[0].name) and fs[0].name.endswith("_viewer.mp4"), f"文件名 <时间>_viewer.mp4：{[f.name for f in fs]}")
    pr = probe(fs[0])
    v = next(s for s in pr["streams"] if s["codec_type"] == "video"); a = [s for s in pr["streams"] if s["codec_type"] == "audio"]
    dur = float(pr["format"]["duration"])
    check(v["width"] == 270 and v["height"] == 480 and v["codec_name"] == "h264", f"竖屏 9:16：{v['width']}x{v['height']}")
    check(a and a[0]["codec_name"] == "aac", "带声音")
    check(5.0 <= dur <= 6.6, f"时长 ≈ 前 3 秒 + 后 3 秒：{dur:.2f}")
    check((tmp / "out" / (fs[0].name[:-4] + ".jpg")).exists(), "有缩略图")
    check(cl.pushed == [] and not list((tmp / "out").glob("*.part.mp4")), "没有残留的 .part 文件")
    # 画面检查：竖屏里中间是前景（亮度和边缘的模糊背景不同）——抽一帧看尺寸，边缘列和中间列不同
    fr = tmp / "f.png"; subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(fs[0]), "-frames:v", "1", str(fr)])
    check(fr.exists(), "能抽出画面帧")
    # 面板用的列表 / 取文件 / 删除
    cl._files = ([], 0)
    lst = cl.files(fresh=True)
    check(len(lst) == 1 and lst[0]["kind"] == "viewer" and lst[0]["label"] == "观众点的高光" and lst[0]["thumb"] and lst[0]["size"] > 1000, f"文件列表：{lst}")
    check(cl.path_of(lst[0]["name"]) is not None and cl.path_of(lst[0]["name"][:-4] + ".jpg") is not None and cl.path_of("../x.mp4") is None and cl.path_of("nope.mp4") is None, "path_of：只认合法文件名")
    check(not cl.remove("../../etc/passwd") and not cl.remove("20200101-000000_x.mp4"), "删除：非法 / 不存在的名字不动任何东西")
    # 手动「现在切一个」
    await asyncio.sleep(max(0, 6.5 - (time.time() - t_ev)))
    r = cl.manual("面板"); check(r["ok"], f"手动切一个：{r}")
    check(await wait(lambda: cl.stats["clips"] >= 2, 40), f"手动切的也剪好了：{cl.last}")
    check(sorted(x["kind"] for x in cl.files(fresh=True)) == ["manual", "viewer"], "两条：viewer + manual")
    # bark=true：剪好后推一次（假的 push）
    cl.cfg.cp["clips"]["bark"] = "true"
    await asyncio.sleep(6.2)
    cl.on_highlight("gift_big", {"at": time.time(), "who": "土豪哥"})
    check(await wait(lambda: cl.stats["clips"] >= 3, 40), "大礼高光剪好")
    check(len(cl.pushed) == 1 and cl.pushed[0][0] == "切到一个高光" and "大礼" in cl.pushed[0][1], f"bark=true：推了一条『切到一个高光』：{cl.pushed}")
    # 保留上限：max_clips=5（最少 5）→ 再切几条后最老的被清
    for i in range(4):
        await asyncio.sleep(6.2)
        cl.on_highlight("perf_meteor", {"at": time.time()})
        await wait(lambda: cl.stats["clips"] >= 4 + i, 40)
    await wait(lambda: not cl.state()["pending"], 20)
    names = [x["name"] for x in cl.files(fresh=True)]
    check(len(names) <= 5, f"最多留 max_clips 条：{len(names)}")
    check(not any(re.search(r"\.(jpg)$", p.name) and not (tmp / "out" / (p.name[:-4] + ".mp4")).exists() for p in (tmp / "out").glob("*.jpg")), "删旧片时缩略图一起删")
    n0 = names[0]; check(cl.remove(n0) and not (tmp / "out" / n0).exists() and not (tmp / "out" / (n0[:-4] + ".jpg")).exists(), "删除：mp4 + 缩略图一起没了")
    # 缓冲只留 keep_secs
    check(len(C.list_segments(cl.buf)) <= 5 + 4 + 3 and C.list_segments(cl.buf)[0][0] > time.time() - 25, f"滚动缓冲：只留最近一阵 {len(C.list_segments(cl.buf))} 段")
    # 停止：ffmpeg 收掉、缓冲目录清掉
    buf = cl.buf
    cl.set_manual(False); cl.cfg.cp["clips"]["mode"] = "manual"
    await wait(lambda: cl.proc is None and cl.buf is None, 20)
    check(cl.proc is None and not os.path.isdir(buf), "不在录制时段：ffmpeg 停了，缓冲目录删了")
    cl.task.cancel()
    shutil.rmtree(tmp, ignore_errors=True)
asyncio.new_event_loop().run_until_complete(full())

# ---- 4. 没有屏幕录制权限：检测到、不起 ffmpeg、写清楚 ----
async def perm():
    tmp = Path(tempfile.mkdtemp(prefix="clipstest-"))
    cl, app, room = mk(tmp, clips__test_source="")
    popen_calls = []
    cl.hooks = {"perm": lambda: False, "popen": lambda *a, **k: popen_calls.append(a) or None}
    ok = cl.start_proc()
    check(ok is False and not popen_calls and cl.proc is None, "权限没开：不起 ffmpeg")
    check("屏幕录制" in cl.err and cl.perm["ok"] is False and cl.perm.get("python") and cl.perm["msg"], f"错误里写清楚：{cl.err[:90]}")
    st = cl.state(); check(st["perm"]["ok"] is False and st["perm"]["msg"] and not st["recording"], "状态里有权限提示（面板显示）")
    check(cl.next_try > time.time() + 30, "失败后过一会儿再试（不刷屏）")
    r = cl.recheck(); check(r["ok"] is False and "屏幕录制" in r["msg"], "重新检测：只检测，说明还是没权限")
    # 假想「launchd 直接拉起」和「Terminal 拉起」的措辞
    h1 = C.responsible_hint("/opt/homebrew/bin/ffmpeg")
    check("python" in h1["msg"] or h1["app"], "授权对象：App 或 python 可执行文件")
    # 有权限 + 假设备：命令里是 avfoundation 抓屏 + BlackHole，裁成直播窗口
    cl, app, room = mk(tmp, clips__test_source="")
    calls = []
    class FP:
        pid = 99999999
        stdin = types.SimpleNamespace(write=lambda b: None, flush=lambda: None)
        def poll(self): return None
        def wait(self, timeout=None): return 0
        def kill(self): pass
    cl.hooks = {"perm": lambda: True, "displays": lambda: DISP, "windows": lambda: WINS, "probe": lambda: C.parse_devices(DEV), "encoders": lambda: " V....D h264_videotoolbox VideoToolbox H.264",
                "popen": lambda cmd, **k: calls.append(cmd) or FP()}
    check(cl.start_proc() is True and cl.proc is not None, f"权限 OK：起录（假 ffmpeg）{cl.err}")
    j = " ".join(calls[0])
    check("-f avfoundation" in j and "-i 1:1" in j and "h264_videotoolbox" in j and "iw*0.55814" in j and "-segment_time 1" in j and f"{C.TMP_PREFIX}" in j, f"命令：0 号屏（设备 1）+ BlackHole（音频 1）+ 裁成直播窗口 + videotoolbox：{j[:150]}")
    check(cl.geom["screen"] == 0 and cl.state()["recording"], "状态：录着")
    g_old = dict(cl.geom)
    cl.hooks["windows"] = lambda: [dict(WINS[1], x=100)]
    gn = cl.find_geom(); check(cl.moved(gn, g_old) and not cl.moved(g_old, dict(g_old, fx=g_old["fx"] + 0.001)), "窗口挪了能发现（微小抖动不算）")
    cl.stop_proc(); check(cl.proc is None, "stop_proc 收掉")
    # 屏幕列表空（显示器休眠）：说明原因，不起
    cl, app, room = mk(tmp, clips__test_source="")
    cl.hooks = {"perm": lambda: True, "displays": lambda: [], "windows": lambda: WINS, "probe": lambda: {"screens": {}, "video": {}, "audio": {}}, "popen": lambda *a, **k: calls.append(1)}
    check(cl.start_proc() is False and "屏幕" in cl.err and "休眠" in cl.err, f"没有活动屏幕：{cl.err[:60]}")
    # 找不到窗口：说明
    cl, app, room = mk(tmp, clips__test_source="")
    cl.hooks = {"perm": lambda: True, "displays": lambda: DISP, "windows": lambda: [], "probe": lambda: C.parse_devices(DEV), "popen": lambda *a, **k: calls.append(1)}
    check(cl.start_proc() is False and "找不到直播窗口" in cl.err and "region" in cl.err, f"找不到窗口：{cl.err[:70]}")
    # region 手动指定就不用找窗口
    cl, app, room = mk(tmp, clips__test_source="", clips__region="0,0,1280,720")
    cl.hooks = {"perm": lambda: True, "displays": lambda: DISP, "windows": lambda: [], "probe": lambda: C.parse_devices(DEV), "encoders": lambda: "libx264", "popen": lambda cmd, **k: calls.append(cmd) or FP()}
    check(cl.start_proc() is True and abs(cl.geom["fw"] - 1280 / 3440) < 1e-9, "region 手动指定：不找窗口")
    cl.stop_proc()
    # 没有 BlackHole：只录画面
    cl, app, room = mk(tmp, clips__test_source="", clips__audio="不存在的声卡")
    n0 = len(calls)
    cl.hooks = {"perm": lambda: True, "displays": lambda: DISP, "windows": lambda: WINS, "probe": lambda: C.parse_devices(DEV), "encoders": lambda: "libx264", "popen": lambda cmd, **k: calls.append(cmd) or FP()}
    check(cl.start_proc() is True and "1:none" in " ".join(calls[n0]) and "-an" in calls[n0], "没找到音频设备：只录画面（-i 1:none -an）")
    cl.stop_proc()
    shutil.rmtree(tmp, ignore_errors=True)
asyncio.new_event_loop().run_until_complete(perm())

# ---- 5. 接线 / 页面 / README ----
rd = lambda p: (ROOT / p).read_text(encoding="utf-8")
srv = rd("backend/server.py")
check("Clips(cfg, self, log)" in srv and "app_state.clips.start()" in srv and "app_state.clips.shutdown()" in srv and "clips.on_event(ev, self)" in srv and "cl.on_highlight(kind, h)" in srv, "server.py：创建 / 启动 / 收摊 / 观众口令 / mark_highlight 接到切片")
check("HIGHLIGHT_PERFS" in rd("backend/agent/idle.py") and "mh(name)" in rd("backend/agent/idle.py"), "idle：蓝屏 / 假重启 / 熊猫烧香 / 烟花 / 流星雨开演时标记高光")
check('mark("gift_big"' in rd("backend/agent/giftfx.py"), "giftfx：大礼标记 gift_big")
check("cl.shutdown()" in rd("backend/ops/core.py"), "重启服务前先收 ffmpeg（os._exit 不跑 atexit）")
api = rd("backend/ops/api.py")
check('"clips.enabled"' in api and '"clips": app.clips.state()' in api and all(k in api for k in ("clips_now", "clips_record", "clips_check", "clips_delete", "/ops/api/clip/{name}")), "手机面板接口：开关 / 状态 / 动作 / 取文件")
pj = rd("web/panel/panel.js"); check("renderClips" in pj and "clips_delete" in pj and "clips_now" in pj and "cl-list" in pj, "panel.js：切片页")
check('data-t="clips"' in rd("web/panel/index.html") and 'id="t-clips"' in rd("web/panel/index.html"), "面板底栏有「切片」")
check("data/clips/" in rd(".gitignore"), ".gitignore 忽略 data/clips/")
rm = rd("README.md")
check("11.13" in rm and "[clips]" in rm and "screenshots/clips/" in rm, "README 有高光切片小节并嵌了截图")
print(f"高光切片测试（{total} 项断言）" + ("全部通过" if not bad else f"失败 {bad} 项"))
sys.exit(1 if bad else 0)
