# -*- coding: utf-8 -*-
"""手机控制面板的安全部分：令牌（自动生成到本地文件，不进日志）、局域网地址、终端二维码、失败锁定。接口和页面见 web.py / web/panel/。"""
import hmac
import ipaddress
import os
import secrets
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def token_path(cfg, root=ROOT):
    p = Path(cfg.s("ops", "panel_token_file") or "data/ops_token.txt")
    return p if p.is_absolute() else root / p


def ensure_token(cfg, root=ROOT, log=print):
    """令牌：[ops] panel_token 非空就用它；否则读 panel_token_file；都没有就生成一个写进去（权限 600）。绝不把令牌打进日志，只提示文件在哪。"""
    t = cfg.s("ops", "panel_token").strip()
    if t:
        return t
    p = token_path(cfg, root)
    try:
        t = p.read_text(encoding="utf-8").strip()
        if t:
            return t
    except FileNotFoundError:
        pass
    except Exception as e:
        log("[ops] 读令牌文件出错：", repr(e)[:80])
    t = secrets.token_urlsafe(18)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(t + "\n")
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
    log(f"[ops] 手机面板令牌是第一次生成，保存在 {p}（不会打印在日志里；换令牌就删掉这个文件重启）")
    return t


def check_token(given, token):
    if not given or not token:
        return False
    return hmac.compare_digest(str(given).encode("utf-8"), str(token).encode("utf-8"))


def is_loopback(addr):
    if not addr:
        return True
    try:
        ip = ipaddress.ip_address(addr.split("%")[0])
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        return ip.is_loopback
    except ValueError:
        return False


def lan_ips():
    """本机局域网 IPv4（私有地址优先；没有联网返回 []）"""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("10.255.255.255", 1))        # UDP connect 不发包，只是让系统选出口网卡
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except Exception:
        pass
    out = []
    for ip in ips:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.is_loopback or a.is_link_local or ip in out:
            continue
        out.append(ip)
    return sorted(out, key=lambda x: not ipaddress.ip_address(x).is_private)


def qr_lines(text, try_install=False):
    """终端二维码（半块字符，每行 2 个模块高）。没有 qrcode 包：try_install 时 pip 装一次（装不上返回 None，调用方只打印网址）"""
    try:
        import qrcode
    except ImportError:
        if not try_install:
            return None
        import shutil
        import subprocess
        tries = [[sys.executable, "-m", "pip", "install", "-q", "qrcode"],
                 [sys.executable, "-m", "ensurepip", "--upgrade"] , [sys.executable, "-m", "pip", "install", "-q", "qrcode"]]
        if shutil.which("uv"):
            tries.append(["uv", "pip", "install", "-q", "--python", sys.executable, "qrcode"])
        for cmd in tries:
            try:
                subprocess.run(cmd, check=True, timeout=120, capture_output=True)
                import importlib
                importlib.invalidate_caches()
                import qrcode
                break
            except Exception:
                continue
        else:
            return None
    q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_L)
    q.add_data(text)
    q.make(fit=True)
    m = q.get_matrix()
    if len(m) % 2:
        m.append([False] * len(m[0]))
    rows = []
    for y in range(0, len(m), 2):
        rows.append("".join(("█" if m[y][x] and m[y + 1][x] else "▀" if m[y][x] else "▄" if m[y + 1][x] else " ") for x in range(len(m[0]))))
    # 终端深色背景：上面的编码是「深=亮块」，反色后手机更好扫
    inv = {"█": " ", " ": "█", "▀": "▄", "▄": "▀"}
    return ["".join(inv[ch] for ch in r) for r in rows]


class Lockout:
    """令牌连续错误 5 次的来源 IP 锁定 panel_fail_lock 秒（防暴力猜；令牌本身 144 位随机，这是第二道）"""
    def __init__(self, secs=60, limit=5):
        self.secs, self.limit, self.fails = secs, limit, {}

    def blocked(self, ip):
        n, until = self.fails.get(ip, (0, 0))
        return until > time.time()

    def fail(self, ip):
        n, until = self.fails.get(ip, (0, 0))
        n = 0 if until and until <= time.time() else n
        n += 1
        self.fails[ip] = (n, time.time() + self.secs if n >= self.limit else 0)
        if len(self.fails) > 500:
            self.fails.clear()

    def ok(self, ip):
        self.fails.pop(ip, None)
