# -*- coding: utf-8 -*-
"""Bark / 提示音的硬禁用测试：测试 / 假房间（QQ_NO_FETCH=1、QQ_NO_BARK=1、tools/test_*.py / shoot_*.py 进程）里，不管 config 怎么写、环境里有没有 BARK_KEY、密钥文件在不在，
   都不会发出任何 Bark 请求、也不会响提示音。用的全是假密钥 + 假的 requests.get（计数，绝不联网）。
   python tools/test_nobark.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")
import os, sys, tempfile, time, types
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import requests
from host.config import Config, ENV
from ops import guard as G
from ops import Ops

bad = 0; total = 0
def check(c, m):
    global bad, total
    total += 1
    if not c:
        bad += 1; print("FAIL", m)

FAKE = "FakeKey0123456789abcdef"                      # 假密钥（不是真的）
calls = []
real_get = requests.get
requests.get = lambda url, **k: (calls.append(1), (_ for _ in ()).throw(AssertionError("不该有 Bark 请求")))[1]
T = Path(tempfile.mkdtemp(prefix="nobark-")); (T / "key.txt").write_text(FAKE)
os.environ["BARK_KEY"] = FAKE
def cfg(**kv):
    c = Config(str(ROOT / "config.ini"))
    c.cp["guard"].update({"enabled": "true", "bark": "true", "sound": "true", "bark_key_file": str(T / "key.txt"), "drop_grace": "0", "cooldown": "0", "state_file": str(T / "st.json"), "log_watch": "false", "window_watch": "false"})
    c.cp["guard"].update({k: str(v) for k, v in kv.items()})
    c.cp["ops"]["log"] = "false"
    return c

# 1. 配置不会从环境变量拿 Bark 密钥
check(not any("BARK" in k for k in ENV), "config.ENV 里没有任何 BARK 相关的环境变量映射")
c = cfg(); check(FAKE not in " ".join(str(v) for sec in c.cp.values() for v in sec.values()), "BARK_KEY 环境变量不会进配置")

# 2. 各种「测试环境」判定下 bark_push 直接拒绝（连请求都不发）
for how in ("QQ_NO_FETCH", "QQ_NO_BARK", "argv"):
    saved = {k: os.environ.pop(k, None) for k in ("QQ_NO_FETCH", "QQ_NO_BARK")}; a0 = sys.argv[0]
    if how == "argv": sys.argv[0] = "/x/tools/test_something.py"
    else: os.environ[how] = "1"
    ok, m = G.bark_push(cfg(), "t", "b")
    check(ok is False and "硬禁用" in m and not calls and FAKE not in m, f"{how}：bark_push 被硬禁用，没有请求，说明里没有密钥：{m}")
    os.environ.pop(how, None); sys.argv[0] = a0
    for k, v in saved.items():
        if v is not None: os.environ[k] = v
ok, m = G.play_alarm(cfg(), outputs=[]); check(ok is False and "硬禁用" in m, f"提示音同样硬禁用：{m}")

# 3. 假 Bark 服务器（本机回环）才放行——测试里测 Bark 请求形状用
sent = []
ok, m = G.bark_push(cfg(bark_server="http://127.0.0.1:9"), "t", "b", http_get=lambda url, t: sent.append(url) or types.SimpleNamespace(status_code=200, json=lambda: {"code": 200}))
check(ok and len(sent) == 1, "显式传入假 http_get（测试替身）仍可用")

# 4. 把当年出事的场景整个重放：真 config.ini 的 Ops + Guard，开播 → 下播，宽限 0 秒，Bark / 提示音都开着、密钥文件在、BARK_KEY 在环境里
class FApp:
    def __init__(self, c): self.default_room, self.rooms, self.cfg = "111", {}, c
    def get_room(self, rid): self.rooms.setdefault(rid, types.SimpleNamespace(fetcher=None, clients=set())); return self.rooms[rid]
c = cfg(); o = Ops(c, FApp(c), lambda *a: None)
o.on_event({"t": "live", "live": True}, None); o.on_event({"t": "live", "live": False}, None)
t0 = time.time()
while time.time() - t0 < 6 and not (o.guard.history and "硬禁用" in o.guard.history[0].get("push", "")):
    time.sleep(0.2)
h = o.guard.history
check(h and h[0]["kind"] == "drop", f"下播提醒确实触发了（走到了推送那一步）：{h[:1] and h[0]['kind']}")
check(h and "硬禁用" in h[0]["push"] and not calls, f"但 Bark 被硬禁用、没有任何请求：{h and h[0]['push']}")
check(h and FAKE not in h[0]["push"], "面板 / 日志里没有密钥")
# 5. 面板「测试推送」同样被拦
o.guard.test_push(); time.sleep(1.0)
check(not calls, "guard.test_push 也不会发请求")

# 6. 真服务（没有这些标记）不会被误伤：QQ_NO_FETCH 没设、进程名是 server.py、服务器不是回环 → 照常发（这里用假 requests.get 返回 200，不联网）
saved = {k: os.environ.pop(k, None) for k in ("QQ_NO_FETCH", "QQ_NO_BARK")}; a0 = sys.argv[0]; sys.argv[0] = "/x/backend/server.py"
fake_calls = []
requests.get = lambda url, **k: (fake_calls.append(url), types.SimpleNamespace(status_code=200, json=lambda: {"code": 200}))[1]
ok, m = G.bark_push(cfg(), "t", "b")
check(ok and len(fake_calls) == 1 and "api.day.app" in fake_calls[0], f"真服务里照常发（假 requests.get）：{m}")
sys.argv[0] = a0
for k, v in saved.items():
    if v is not None: os.environ[k] = v
requests.get = real_get
print(f"Bark 硬禁用测试（{total} 项断言）" + ("全部通过" if not bad else f"失败 {bad} 项"))
sys.exit(1 if bad else 0)
