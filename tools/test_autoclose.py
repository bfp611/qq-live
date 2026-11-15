# -*- coding: utf-8 -*-
"""窗口闲置自动关闭（web/autoclose.js，§11.9b）的静态 / 配置测试：代码默认值 ↔ config.ini ↔ 页面里的默认值一致、永远不关的窗口都在 keep 里、
   每个会开的窗口 id 都有归类、JS 语法、已接进页面和面板。真页面行为见 tools/shoot_autoclose.py。不联网
   python tools/test_autoclose.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from host.config import Config, DEFAULTS
bad = 0; total = 0
def check(c, m):
    global bad, total
    total += 1
    if not c: bad += 1; print("FAIL", m)
js = (ROOT / "web" / "autoclose.js").read_text(encoding="utf-8")
D = DEFAULTS["autoclose"]
# 页面里的默认值（const D = {...}）和代码默认值一致
m = re.search(r"const D = \{(.*?)\};", js, re.S); body = m.group(1)
jsd = dict(re.findall(r"(\w+): '([^']*)'", body))
check(jsd == D, f"页面里的默认值和 config.py 不一致：{ {k: (jsd.get(k), D.get(k)) for k in set(jsd) | set(D) if jsd.get(k) != D.get(k)} }")
ci = Config(str(ROOT / "config.ini"))
if "autoclose" in ci.cp:
    miss = [k for k in ci.cp["autoclose"] if k not in D]; check(not miss, f"config.ini [autoclose] 里有代码不认识的键：{miss}")
    for k, v in D.items():
        if k in ci.cp["autoclose"]: check(ci.cp["autoclose"][k] == v, f"config.ini [autoclose] {k}={ci.cp['autoclose'][k]!r} ≠ 默认 {v!r}")
else: print("（config.ini 里还没有 [autoclose]，跳过）")
# 默认值的合理性（需求里的数字）
secs = lambda k: float(D[k])
check(secs("paint") == 25 and 30 <= secs("notepad") <= 45 and 30 <= secs("calc") <= 45 and 30 <= secs("cmd") <= 45 and 30 <= secs("control") <= 45 and 30 <= secs("ie") <= 45 and 30 <= secs("explorer") <= 45 and 30 <= secs("qq") <= 45, "画图 25 秒，其它软件 30~45 秒")
check(120 <= secs("max_game") <= 180 and D["enabled"] == "true", "游戏最长 2~3 分钟，默认开")
keep = set(re.split(r"[,\s]+", D["keep"])); skip = set(re.split(r"[,\s]+", D["skip"]))
check({"qqchat", "ttplayer", "ttplaylist", "lyrics", "qq-panel", "qqx-pet"} <= keep, "群聊 / 千千静听 / 播放列表 / 桌面歌词 / QQ 面板 / QQ 宠物 在 keep 里")
check({"vote", "skipvote", "game"} <= skip, "投票 / 切歌投票 / 趣味小游戏 在 skip 里（自己会关）")
check({"shutdown", "logoff", "xpscr"} <= keep, "关机 / 注销 / 系统画面不动（蓝屏不变）")
# 每个会开的窗口 id 都有归类
idmap = dict(re.findall(r"(?:(\w+)|'([\w-]+)'): '(\w+)'", re.search(r"const ID = \{(.*?)\};", js, re.S).group(1)) and [(a or b, c) for a, b, c in re.findall(r"(?:(\w+)|'([\w-]+)'): '(\w+)'", re.search(r"const ID = \{(.*?)\};", js, re.S).group(1))])
ids = set()
for f in (ROOT / "web").glob("*.js"):
    for mm in re.finditer(r"WM\.(?:create|dialog)\(\{\s*id: '([\w-]+)'", f.read_text(encoding="utf-8")): ids.add(mm.group(1))
known_other = set()
unk = sorted(i for i in ids if i not in idmap and i not in keep and i not in skip and not i.startswith(("game-", "gc-card-", "props-", "prompt-")))
check(not unk, f"这些窗口 id 没有归类（会按 default_secs 处理，确认一下是不是想要的）：{unk}")
check(all(idmap[k] in D or idmap[k] == "dialog" for k in idmap), "归类出来的软件名都在配置里有秒数")
# 接线
check('<script src="autoclose.js"></script>' in (ROOT / "web" / "index.html").read_text(encoding="utf-8"), "index.html 加载了 autoclose.js")
check("autoclose_cfg" in (ROOT / "web" / "app.js").read_text(encoding="utf-8"), "页面收得到面板推来的 autoclose_cfg")
check("AC.after" in (ROOT / "web" / "agent-actions.js").read_text(encoding="utf-8"), "paint_draw 画完会通知 autoclose 开始计时")
check('"autoclose": dict(self.cfg.cp["autoclose"])' in (ROOT / "backend" / "server.py").read_text(encoding="utf-8"), "/config.json 带 autoclose")
check("autoclose.enabled" in (ROOT / "backend" / "ops" / "api.py").read_text(encoding="utf-8"), "面板开关里有 autoclose.enabled")
r = subprocess.run(["node", "--check", str(ROOT / "web" / "autoclose.js")], capture_output=True, text=True)
check(r.returncode == 0, "autoclose.js 语法 " + r.stderr[:200])
print(f"自动关窗静态测试（{total} 项断言）" + ("全部通过" if not bad else f" 有 {bad} 项失败")); sys.exit(1 if bad else 0)
