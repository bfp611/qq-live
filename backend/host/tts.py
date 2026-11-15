# -*- coding: utf-8 -*-
"""TTS 后端：synth(text, emotion) -> (audio_bytes, mime)。失败抛异常，由引擎降级成「只显示气泡」。

backend:
  edge     免费，微软 Edge 在线朗读（pip 包 edge-tts）。默认。
  openai   OpenAI 兼容 /audio/speech（OpenAI、以及多数 CosyVoice / 硅基流动 / 本地封装服务）
  volc     火山引擎 / 豆包语音合成 HTTP 接口（需 appid + token）
  sovits   本地 GPT-SoVITS api_v2（声音克隆）
  fish     Fish Audio HTTP TTS（社区/自有音色）；失败可回退到 fallback（默认 edge）
  custom   任意 HTTP 接口：POST JSON，返回音频字节
  browser  由浏览器 speechSynthesis 朗读（不经过服务器，OBS 不一定能采到声音）
  none     不发声，只有气泡和字幕
"""
import asyncio
import base64
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

import requests

from .config import ROOT

EMOTION_STYLE = {"开心": ("+8%", "+4Hz"), "害羞": ("-6%", "+8Hz"), "生气": ("+6%", "-4Hz"),
                 "惊讶": ("+10%", "+10Hz"), "平静": ("+0%", "+0Hz")}

FISH_URL = "https://api.fish.audio/v1/tts"
FISH_FAILS_BEFORE_COOLDOWN = 3
FISH_COOLDOWN_AUTH_SEC = 30 * 60   # 401 / 402：缺额度或 key 无效
FISH_COOLDOWN_OTHER_SEC = 2 * 60   # 超时 / 网络 / 429 / 5xx 等
_SECRET_RE = re.compile(r"(?i)(bearer\s+|api[_-]?key\s*[=:]\s*)\S+")


def _log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _redact(s: str) -> str:
    return _SECRET_RE.sub(r"\1***", s or "")


# ---------- Fish 密钥 / 断路器（进程内，不把 key 写入配置或日志）----------

class _FishGate:
    def __init__(self):
        self.lock = threading.Lock()
        self.fails = 0
        self.until = 0.0
        self.no_key_logged = False
        self.skip_logged = False

    def remaining(self) -> float:
        return max(0.0, self.until - time.time())

    def allow(self) -> bool:
        return self.remaining() <= 0

    def ok(self):
        with self.lock:
            self.fails = 0
            self.until = 0.0
            self.skip_logged = False

    def fail(self, status):
        """记录一次失败，返回冷却剩余秒数（0 表示尚未打开断路器）。"""
        with self.lock:
            if status in (401, 402):
                self.until = time.time() + FISH_COOLDOWN_AUTH_SEC
                self.fails = 0
                self.skip_logged = False
                return FISH_COOLDOWN_AUTH_SEC
            self.fails += 1
            if self.fails >= FISH_FAILS_BEFORE_COOLDOWN:
                self.until = time.time() + FISH_COOLDOWN_OTHER_SEC
                self.fails = 0
                self.skip_logged = False
                return FISH_COOLDOWN_OTHER_SEC
            return 0.0


_FISH = _FishGate()


def _fish_key():
    """优先环境变量 FISH_API_KEY，否则项目根目录 .fish_api_key。读到的内容绝不写入日志。"""
    env = os.environ.get("FISH_API_KEY", "").strip()
    if env:
        return env
    p = ROOT / ".fish_api_key"
    try:
        if p.is_file():
            key = p.read_text(encoding="utf-8").strip()
            return key or None
    except OSError:
        return None
    return None


def _fish_reason(exc, resp=None):
    if resp is not None:
        status = getattr(resp, "status_code", None)
        msg = ""
        try:
            j = resp.json()
            if isinstance(j, dict):
                msg = str(j.get("message") or j.get("reason") or "")
        except Exception:
            try:
                msg = (resp.text or "")[:160]
            except Exception:
                msg = ""
        text = f"{status} {_redact(msg)}".strip() if status else _redact(msg)
        return status, text or "unknown"
    if isinstance(exc, requests.Timeout):
        return None, "timeout"
    if isinstance(exc, requests.ConnectionError):
        return None, f"network {type(exc).__name__}"
    return None, _redact(f"{type(exc).__name__}: {exc}")[:200]


# ---------- 各后端 ----------

def _edge(cfg, text, emotion):
    import edge_tts

    rate, pitch = cfg.s("tts", "rate"), cfg.s("tts", "pitch")

    async def run():
        out = b""
        comm = edge_tts.Communicate(text, cfg.s("tts", "voice"), rate=rate, pitch=pitch, volume=cfg.s("tts", "volume"))
        async for ch in comm.stream():
            if ch["type"] == "audio":
                out += ch["data"]
        return out

    data = asyncio.run(run())
    if not data:
        raise RuntimeError("edge-tts 没有返回音频（网络不通？）")
    return data, "audio/mpeg"


def _openai(cfg, text, emotion):
    base = cfg.s("tts", "openai_base_url").rstrip("/")
    if not base:
        raise RuntimeError("tts.openai_base_url 未配置")
    key = cfg.s("tts", "openai_api_key")
    r = requests.post(base + "/audio/speech", timeout=40,
                      headers={"Authorization": f"Bearer {key}"} if key else {},
                      json={"model": cfg.s("tts", "openai_model"), "voice": cfg.s("tts", "openai_voice"),
                            "input": text, "response_format": "mp3"})
    r.raise_for_status()
    return r.content, "audio/mpeg"


def _volc(cfg, text, emotion):
    body = {
        "app": {"appid": cfg.s("tts", "volc_appid"), "token": "access_token", "cluster": cfg.s("tts", "volc_cluster")},
        "user": {"uid": "qq-live"},
        "audio": {"voice_type": cfg.s("tts", "volc_voice"), "encoding": "mp3", "speed_ratio": 1.0},
        "request": {"reqid": str(uuid.uuid4()), "text": text, "operation": "query"},
    }
    r = requests.post("https://openspeech.bytedance.com/api/v1/tts", timeout=40, json=body,
                      headers={"Authorization": f"Bearer;{cfg.s('tts', 'volc_token')}"})
    r.raise_for_status()
    j = r.json()
    if "data" not in j:
        raise RuntimeError(f"火山 TTS 返回错误：{str(j)[:200]}")
    return base64.b64decode(j["data"]), "audio/mpeg"


def _sovits(cfg, text, emotion):
    r = requests.post(cfg.s("tts", "sovits_url"), timeout=90, json={
        "text": text, "text_lang": "zh", "ref_audio_path": cfg.s("tts", "sovits_ref_audio"),
        "prompt_text": cfg.s("tts", "sovits_prompt_text"), "prompt_lang": "zh", "media_type": "wav",
        "streaming_mode": False})
    r.raise_for_status()
    return r.content, "audio/wav"


def _custom(cfg, text, emotion):
    url = cfg.s("tts", "custom_url")
    if not url:
        raise RuntimeError("tts.custom_url 未配置")
    body = json.loads(cfg.s("tts", "custom_body").replace("{text}", json.dumps(text, ensure_ascii=False)[1:-1]))
    r = requests.post(url, json=body, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("content-type", "audio/mpeg").split(";")[0]


def _fish(cfg, text, emotion):
    key = _fish_key()
    if not key:
        raise RuntimeError("no-key")
    # 必须始终带 model 头，避免回落到付费的 s2.1-pro
    model = cfg.s("tts", "fish_model") or "s2.1-pro-free"
    url = cfg.s("tts", "fish_url") or FISH_URL
    latency = cfg.s("tts", "fish_latency") or "balanced"
    ref = cfg.s("tts", "fish_reference_id")
    if not ref:
        raise RuntimeError("tts.fish_reference_id 未配置")
    timeout = 20.0
    try:
        timeout = float(cfg.s("tts", "fish_timeout") or 20)
    except ValueError:
        pass
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "model": model,
    }
    body = {
        "text": text,
        "reference_id": ref,
        "format": "mp3",
        "mp3_bitrate": 64,
        "latency": latency,
    }
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    if r.status_code != 200:
        status, reason = _fish_reason(None, r)
        err = RuntimeError(reason)
        err.fish_status = status
        raise err
    if not r.content or len(r.content) < 32:
        err = RuntimeError("empty audio")
        err.fish_status = r.status_code
        raise err
    return r.content, "audio/mpeg"


BACKENDS = {"edge": _edge, "openai": _openai, "volc": _volc, "sovits": _sovits,
            "custom": _custom, "fish": _fish}


def _fallback_name(cfg, primary):
    try:
        name = (cfg.s("tts", "fallback") or "").strip().lower()
    except Exception:
        name = ""
    if not name or name in ("none", primary) or name not in BACKENDS:
        return ""
    return name


# ---------- 多音色：[ai_plus] voices = 角色=后端:参数[~回退edge音色]，如 narrator=edge:zh-CN-YunjianNeural:+0%:+0Hz, vip=fish:参考音色ID~zh-CN-XiaoxiaoNeural ----------
class _Over:
    """给某个角色临时换几个 [tts] 键（音色 / 后端 / fish 参考音色…），其余照用全局配置；fish 的额度断路器和回退照样生效。"""
    def __init__(self, cfg, over):
        self._c, self._o = cfg, over

    def s(self, sec, key):
        return self._o.get((sec, key), self._c.s(sec, key))

    def __getattr__(self, n):
        return getattr(self._c, n)


def parse_voices(text):
    """-> {role: {"backend", "args": [...], "fb": 回退 edge 音色}}；坏的条目跳过。"""
    out = {}
    for part in re.split(r"[,，;；\n]+", text or ""):
        if "=" not in part:
            continue
        role, spec = part.split("=", 1)
        role, spec = role.strip(), spec.strip()
        fb = ""
        if "~" in spec:
            spec, fb = spec.split("~", 1)
        bits = [x.strip() for x in spec.split(":")]
        be = (bits[0] or "").lower()
        if not role or be not in ("edge", "fish", "openai", "volc", "default", "host"):
            continue
        out[role] = {"backend": be, "args": bits[1:], "fb": fb.strip()}
    return out


def role_cfg(cfg, role):
    """角色 → 带覆盖的配置；没配（或配成 default / host）→ None（用全局音色）。"""
    if not role or role == "host":
        return None
    try:
        sp = parse_voices(cfg.s("ai_plus", "voices")).get(role)
    except Exception:
        return None
    if not sp or sp["backend"] in ("default", "host"):
        return None
    a = sp["args"] + ["", "", ""]
    o = {("tts", "backend"): sp["backend"]}
    if sp["backend"] == "edge":
        if a[0]: o[("tts", "voice")] = a[0]
        if a[1]: o[("tts", "rate")] = a[1]
        if a[2]: o[("tts", "pitch")] = a[2]
    elif sp["backend"] == "fish":
        if a[0]: o[("tts", "fish_reference_id")] = a[0]
        if a[1]: o[("tts", "fish_model")] = a[1]
        if sp["fb"]: o[("tts", "voice")] = sp["fb"]
        o[("tts", "fallback")] = "edge"
    elif sp["backend"] == "openai":
        if a[0]: o[("tts", "openai_voice")] = a[0]
    elif sp["backend"] == "volc":
        if a[0]: o[("tts", "volc_voice")] = a[0]
    if sp["fb"] and sp["backend"] != "fish":
        o[("tts", "fallback")] = "edge"
    return _Over(cfg, o)


def synth(cfg, text, emotion="", role=""):
    oc = role_cfg(cfg, role) if role else None
    if oc is not None:
        if cfg.s("tts", "backend").lower() in ("none", "browser"):
            return None, None                      # 全局关了语音就都不出声
        return synth(oc, text, emotion)
    name = cfg.s("tts", "backend").lower()
    fn = BACKENDS.get(name)
    if not fn:
        return None, None

    if name == "fish":
        key = _fish_key()
        if not key:
            with _FISH.lock:
                if not _FISH.no_key_logged:
                    _log("[TTS] 未找到 FISH_API_KEY / .fish_api_key，使用 edge")
                    _FISH.no_key_logged = True
            return _edge(cfg, text, emotion)
        if not _FISH.allow():
            left = int(_FISH.remaining())
            with _FISH.lock:
                if not _FISH.skip_logged:
                    _log(f"[TTS] fish 冷却中（还剩 {left}s），使用 edge")
                    _FISH.skip_logged = True
            return _edge(cfg, text, emotion)
        try:
            out = fn(cfg, text, emotion)
            _FISH.ok()
            return out
        except Exception as e:
            resp = getattr(e, "response", None)
            status = getattr(e, "fish_status", None)
            if status is None and resp is not None:
                status = getattr(resp, "status_code", None)
            if status is not None:
                reason = _redact(str(e))[:200]
                # 我们自己抛的 RuntimeError("401 ...") 不必再套类型名
                if reason.startswith("RuntimeError: "):
                    reason = reason[len("RuntimeError: "):]
            else:
                _, reason = _fish_reason(e, resp)
                if not reason or reason == "unknown":
                    reason = _redact(str(e))[:200]
            cool = _FISH.fail(status)
            extra = f"，暂停 fish {int(cool)}s" if cool else ""
            _log(f"[TTS] fish 失败 → 回退 edge: {reason}{extra}")
            fb = _fallback_name(cfg, name) or "edge"
            return BACKENDS[fb](cfg, text, emotion)

    return fn(cfg, text, emotion)


# ---------- 时长估算：按 mp3 帧解析，避免 48kbps 经验值把 64/128kbps 估短 ----------

# [mpeg_version][layer] -> bitrate kbps table (index 1..14); version: 3=MPEG1, 2=MPEG2, 0=MPEG2.5
_BITRATE = {
    (3, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],  # MPEG1 L3
    (3, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    (3, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    (2, 1): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
}
_BITRATE[(0, 1)] = _BITRATE[(2, 1)]
_BITRATE[(0, 2)] = _BITRATE[(2, 2)]
_BITRATE[(0, 3)] = _BITRATE[(2, 3)]
_SR = {
    3: [44100, 48000, 32000],
    2: [22050, 24000, 16000],
    0: [11025, 12000, 8000],
}


def _mp3_frame_len(hdr: bytes):
    if len(hdr) < 4 or hdr[0] != 0xFF or (hdr[1] & 0xE0) != 0xE0:
        return None
    ver = (hdr[1] >> 3) & 0x03
    layer = (hdr[1] >> 1) & 0x03
    br_i = (hdr[2] >> 4) & 0x0F
    sr_i = (hdr[2] >> 2) & 0x03
    pad = (hdr[2] >> 1) & 0x01
    if ver == 1 or layer == 0 or br_i == 0 or br_i == 15 or sr_i == 3:
        return None
    br = _BITRATE.get((ver, layer), [0] * 15)[br_i] * 1000
    sr = _SR[ver][sr_i]
    # samples per frame: MPEG1 L3=1152, MPEG2/2.5 L3=576; L2=1152; L1=384
    if layer == 3:  # Layer I
        spf, slot = 384, 4
    elif layer == 2:
        spf, slot = 1152, 1
    else:
        spf, slot = (1152 if ver == 3 else 576), 1
    flen = (12 * br // sr + pad) * slot if layer == 3 else (spf // 8 * br // sr + pad) * slot
    if flen < 4:
        return None
    return flen, spf, sr


def mp3_seconds(data: bytes) -> float:
    """根据帧头累加时长；失败则按首帧码率估算。"""
    if not data or len(data) < 4:
        return 0.0
    i = 0
    if data[:3] == b"ID3" and len(data) >= 10:
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        i = 10 + size
    end = len(data)
    if end >= 128 and data[end - 128:end - 125] == b"TAG":
        end -= 128
    samples = 0
    sr0 = None
    first_br = None
    frames = 0
    start = i
    while i + 4 <= end:
        info = _mp3_frame_len(data[i:i + 4])
        if not info:
            i += 1
            continue
        flen, spf, sr = info
        if i + flen > end + 4:  # 最后一帧可能略不齐
            if frames:
                break
            i += 1
            continue
        if first_br is None:
            first_br = (data[i + 2] >> 4) & 0x0F
            # stash bitrate from this header
            ver = (data[i + 1] >> 3) & 0x03
            layer = (data[i + 1] >> 1) & 0x03
            br_i = (data[i + 2] >> 4) & 0x0F
            try:
                first_br = _BITRATE[(ver, layer)][br_i] * 1000
            except Exception:
                first_br = 64000
        samples += spf
        sr0 = sr
        frames += 1
        i += flen
    if sr0 and samples:
        return samples / sr0
    payload = max(0, end - start)
    if first_br and payload:
        return payload * 8 / first_br
    return 0.0


def estimate_seconds(data: bytes, mime: str, text: str) -> float:
    """估算音频时长（秒）。mp3 按帧解析，wav 按 header，其余按字数。"""
    try:
        if mime == "audio/wav" and len(data) > 44:
            byte_rate = int.from_bytes(data[28:32], "little") or 32000
            return (len(data) - 44) / byte_rate
        if mime in ("audio/mpeg", "audio/mp3") and data:
            sec = mp3_seconds(data)
            if sec >= 0.3:
                return max(0.8, sec)
    except Exception:
        pass
    return max(1.5, len(text) * 0.28)
