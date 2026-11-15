# -*- coding: utf-8 -*-
"""开播前自检：音频设备 / TTS / LLM / 直播间 / 音乐 / 浏览器 / 手机面板。每项返回
   {id, label, status: ok|warn|fail|skip, detail, fix}。在服务进程里跑（用的就是服务自己的配置），/ops/health.json 和 tools/ops.py live 用。
   不会往外打印任何密钥：LLM / TTS 只报「通 / 不通」和错误原因的前 120 个字。"""
import concurrent.futures as cf
import os
import platform
import re
import shutil
import subprocess
import sys
import time


def _run(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return -1, repr(e)


def item(id_, label, status, detail="", fix=""):
    return {"id": id_, "label": label, "status": status, "detail": detail, "fix": fix}


# ---------------------------------------------------------------- 音频设备
def audio_default_output(system=None, runner=_run):
    """→ (设备名 or None, 设备列表, 错误)。system 可注入，测试用。"""
    system = system or platform.system()
    if system == "Darwin":
        if shutil.which("SwitchAudioSource"):
            rc, out = runner(["SwitchAudioSource", "-c", "-t", "output"])
            cur = out.strip() if rc == 0 else None
            rc2, lst = runner(["SwitchAudioSource", "-a", "-t", "output"])
            return cur, [x.strip() for x in lst.splitlines() if x.strip()] if rc2 == 0 else [], None if cur else "SwitchAudioSource 没读到"
        rc, out = runner(["system_profiler", "SPAudioDataType"], 20)
        if rc != 0:
            return None, [], out[:100]
        devs, cur, name = [], None, None
        for line in out.splitlines():
            m = re.match(r"^\s{8}(\S.*):\s*$", line)
            if m:
                name = m.group(1)
                devs.append(name)
            elif "Default Output Device: Yes" in line and name:
                cur = name
        return cur, devs, None if cur else "没找到默认输出设备"
    if system == "Linux":
        if not shutil.which("pactl"):
            return None, [], "没有 pactl（sudo apt install pulseaudio-utils）"
        rc, out = runner(["pactl", "get-default-sink"])
        rc2, lst = runner(["pactl", "list", "short", "sinks"])
        sinks = [l.split("\t")[1] for l in lst.splitlines() if "\t" in l] if rc2 == 0 else []
        return (out.strip() if rc == 0 and out.strip() else None), sinks, None if rc == 0 else "连不上声音服务"
    if system == "Windows":
        rc, out = runner(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_SoundDevice | ForEach-Object { $_.Name }"], 15)
        devs = [x.strip() for x in out.splitlines() if x.strip()] if rc == 0 else []
        return (devs[0] if devs else None), devs, None if devs else "没读到声音设备"
    return None, [], f"不认识的系统 {system}"


def check_audio(cfg, system=None, runner=_run):
    system = system or platform.system()
    cur, devs, err = audio_default_output(system, runner)
    names = " ".join(devs + ([cur] if cur else []))
    if system == "Darwin":
        route = bool(re.search(r"直播多输出|多输出|multi|blackhole", names, re.I))
        if cur is None:
            return item("audio", "音频设备", "warn", err or "读不到输出设备", "检查系统声音设置")
        if re.search(r"直播多输出|多输出|multi|blackhole", cur, re.I):
            return item("audio", "音频设备", "ok", f"系统输出 = {cur}（直播伴侣能采到声音）")
        return item("audio", "音频设备", "warn", f"系统输出 = {cur}；" + ("有「直播多输出 / BlackHole」但没选中" if route else "没有找到「直播多输出 / BlackHole」"),
                    "SwitchAudioSource -s \"直播多输出\" -t output（README §6.1）；只看画面可忽略")
    if system == "Linux":
        if cur is None:
            return item("audio", "音频设备", "warn", err or "没有默认输出", "安装并启动 PulseAudio / pipewire-pulse")
        if "qqlive_stream" in names:
            return item("audio", "音频设备", "ok", f"默认输出 {cur}；虚拟输出 qqlive_stream 已建好")
        return item("audio", "音频设备", "warn", f"默认输出 {cur}；没有 qqlive_stream", "tools/linux_audio_route.sh up（README §6.3）；只看画面可忽略")
    if system == "Windows":
        if cur is None:
            return item("audio", "音频设备", "warn", err or "读不到声音设备", "检查声音设置")
        if re.search(r"cable|vb-audio|virtual|立体声混音|stereo mix", names, re.I):
            return item("audio", "音频设备", "ok", f"找到虚拟声卡 / 立体声混音：{names[:80]}")
        return item("audio", "音频设备", "warn", f"只有 {names[:80]}，没有 VB-CABLE / 立体声混音", "README §6.2；只看画面可忽略")
    return item("audio", "音频设备", "skip", err or "")


# ---------------------------------------------------------------- TTS / LLM
def check_tts(cfg, synth=None):
    name = cfg.s("tts", "backend").lower()
    if name in ("none", ""):
        return item("tts", "TTS 语音", "skip", "[tts] backend=none：主播不出声")
    if name == "browser":
        return item("tts", "TTS 语音", "ok", "用浏览器自带朗读（OBS 里不一定有声音，建议换 edge / fish）")
    if synth is None:
        from host import tts as T
        synth = T.synth
    t0 = time.time()
    try:
        data, mime = synth(cfg, "开播前自检，听得到吗", "")
    except Exception as e:
        return item("tts", "TTS 语音", "fail", f"{name} 合成失败：{str(e)[:120]}", "检查网络 / [tts] 配置；失败时主播会回退 edge")
    if not data or len(data) < 500:
        return item("tts", "TTS 语音", "fail", f"{name} 没有返回音频（{len(data or b'')} 字节）", "看服务日志里的 [TTS] 行")
    return item("tts", "TTS 语音", "ok", f"{name}：{len(data) // 1024} KB {mime}，{int((time.time() - t0) * 1000)} ms")


def check_llm(cfg, chat=None):
    if not cfg.s("ai", "base_url"):
        return item("llm", "LLM", "warn", "[ai] base_url 没配置：主播用模板回复（不会聪明地聊天）", "在 config.ini [ai] 填 base_url / model / api_key")
    if chat is None:
        from host import llm
        chat = llm.chat
    t0 = time.time()
    try:
        out = chat(cfg, [{"role": "user", "content": "只回复两个字：在的"}], max_tokens=40, timeout=min(20.0, cfg.f("ai", "timeout")))
    except Exception as e:
        msg = re.sub(r"(Bearer\s+)\S+", r"\1***", str(e))[:120]
        return item("llm", "LLM", "fail", f"{cfg.s('ai', 'model')} 调用失败：{msg}", "检查 [ai] base_url / api_key / 网络；失败时主播回退模板回复")
    return item("llm", "LLM", "ok", f"{cfg.s('ai', 'model')} 回复 {out.strip()[:12]!r}，{int((time.time() - t0) * 1000)} ms")


# ---------------------------------------------------------------- 其它
def check_room(ops):
    f = ops.fetcher_of_default()
    if f is None:
        return item("room", "直播间", "warn", "没有直播间（没给房间号：只能看 ?demo=1）", "./live.sh 房间号")
    s = f.snapshot()
    who = f"{s['anchor'] or '?'}（{s['room']}）"
    if s["live"] is True and s["connected"]:
        return item("room", "直播间", "ok", f"{who} 正在直播，弹幕已连上（{s['msgs']} 条）")
    if s["live"] is True:
        return item("room", "直播间", "warn", f"{who} 正在直播，正在连接弹幕（{s['state']}）", "稍等几秒")
    if s["live"] is False:
        return item("room", "直播间", "warn", f"{who} 还没开播：服务会每 {int(f.poll)} 秒查一次，开播后自动连弹幕", "去直播伴侣点「开始直播」")
    if s["last_error"]:
        return item("room", "直播间", "fail", f"{s['state']}：{s['last_error'][:100]}", "检查网络；服务会自动重试")
    return item("room", "直播间", "warn", f"{who} 状态未知（{s['state']}）", "稍等几秒再看")


def find_browser():
    sysn = platform.system()
    if sysn == "Darwin":
        for p in ("/Applications/Google Chrome.app", "/Applications/Microsoft Edge.app", "/Applications/Chromium.app"):
            if os.path.exists(p):
                return p
        return None
    if sysn == "Windows":
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
            for rel in ("Google\\Chrome\\Application\\chrome.exe", "Microsoft\\Edge\\Application\\msedge.exe"):
                if base and os.path.exists(os.path.join(base, rel)):
                    return os.path.join(base, rel)
        return None
    for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"):
        if shutil.which(c):
            return shutil.which(c)
    return None


def check_browser():
    p = find_browser()
    return item("browser", "浏览器", "ok", p) if p else item("browser", "浏览器", "fail", "没找到 Chrome / Edge / Chromium", "安装 Chrome（直播窗口要用）")


def check_music(app):
    m = getattr(app, "music", None)
    if m is None:
        return item("music", "音乐 / 点歌", "skip", "[music] 没开")
    st = m.state or {}
    if st.get("on"):
        return item("music", "音乐 / 点歌", "ok", f"正在播放《{st.get('title', '')}》（读取方式 {m.method}）")
    return item("music", "音乐 / 点歌", "warn", f"没有检测到播放器在放歌（{m.method or '未知方式'}）", "打开网易云音乐；点歌功能需要它在运行，没放歌是正常的")


def check_panel(ops):
    if not ops.cfg.b("ops", "panel"):
        return item("panel", "手机面板", "skip", "[ops] panel=false")
    urls = ops.panel_urls()
    detail = (" / ".join(urls) or "没有局域网地址（只在本机可用）") + "；令牌文件：" + ops.token_path_display()
    return item("panel", "手机面板", "ok" if urls else "warn", detail, "" if urls else "连上 Wi-Fi / 网线后重启；或把 [ops] panel_lan=true")


def run_all(ops, which=None):
    """并行跑所有检查，按固定顺序返回。which 可传 id 列表只跑一部分。"""
    c, app = ops.cfg, ops.app
    jobs = {
        "room": lambda: check_room(ops),
        "tts": lambda: check_tts(c),
        "llm": lambda: check_llm(c),
        "audio": lambda: check_audio(c),
        "music": lambda: check_music(app),
        "browser": lambda: check_browser(),
        "panel": lambda: check_panel(ops),
    }
    order = [k for k in jobs if not which or k in which]
    out = {}
    with cf.ThreadPoolExecutor(max_workers=len(order)) as ex:
        futs = {k: ex.submit(jobs[k]) for k in order}
        for k, f in futs.items():
            try:
                out[k] = f.result(timeout=45)
            except Exception as e:
                out[k] = item(k, k, "fail", f"检查本身出错：{repr(e)[:100]}")
    return [out[k] for k in order]
