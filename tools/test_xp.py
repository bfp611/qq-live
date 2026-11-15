#!/usr/bin/env python3
"""XP 加强包离线测试：配置三处一致（config.py 默认值 / config.ini [xp] / xp-core.js 默认值）、资源齐全、注册表与 idle 一致、脚本都被 index.html 引用。"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import os, re, sys, configparser
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
bad = 0
def check(c, m):
    global bad
    if not c: bad += 1; print("FAIL", m)
rd = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()

from host.config import DEFAULTS, Config
from agent import registry as R, idle as I
py = DEFAULTS["xp"]
js = re.search(r"const D = \{(.*?)\};", rd("web/xp-core.js"), re.S).group(1)
jskeys = set(re.findall(r"(\w+):", js))
check(set(py) == jskeys, f"config.py 与 xp-core.js 的键一致: {set(py) ^ jskeys}")
ini = configparser.ConfigParser(inline_comment_prefixes=None, interpolation=None); ini.read(os.path.join(ROOT, "config.ini"), encoding="utf-8")
if ini.has_section("xp"):
    NEWER = {"setup_secs"}          # 之后新增的键：已有的 config.ini 里没有也行（不改用户已有的行），走代码默认值
    check(set(ini["xp"]) <= set(py) and set(py) - set(ini["xp"]) <= NEWER, f"config.ini [xp] 与默认值一致: {set(ini['xp']) ^ set(py)}")
cfg = Config("/nonexistent.ini"); check(cfg.b("xp", "enabled") and cfg.f("xp", "volume") == 0.5, "无 config.ini 时默认值可读")
# 默认值（类型）
for k, v in py.items():
    m = re.search(r"\b%s: ('[^']*'|[^,}]+)" % k, js).group(1).strip().strip("'")
    check(str(v).lower() == m.lower() or (re.match(r"^[\d.]+$", m) and float(v) == float(m)), f"{k}: py={v} js={m}")

# 资源
for f in re.findall(r"'([\w]+\.wav)'", re.search(r"const SND = \{(.*?)\};", rd("web/xp-core.js"), re.S).group(1)):
    check(os.path.exists(os.path.join(ROOT, "web/xp/snd", f)), f"音效文件 {f}")
for f in ("Global.mp3", "InputAlert.mp3", "msg.mp3", "system.mp3"): check(os.path.exists(os.path.join(ROOT, "web/sound", f)), f"QQ 音效 {f}")
for s in ("Club", "Diamond", "Heart", "Spade"):
    for i in range(13): check(os.path.exists(os.path.join(ROOT, f"web/xp/cards/{s}_{i}.png")), f"牌 {s}_{i}")
for i in range(12): check(os.path.exists(os.path.join(ROOT, f"web/xp/cards/CardBack_{i}.png")), f"牌背 {i}")
for f in ("boot_pro.png", "boot_pro_nobar.png", "boot_home_nobar.png", "logo.png"): check(os.path.exists(os.path.join(ROOT, "web/xp/boot", f)), f"开机图 {f}")
check(os.path.exists(os.path.join(ROOT, "web/xp/paint/tools.png")) and os.path.exists(os.path.join(ROOT, "web/xp/paint/LICENSE-jspaint.txt")), "画图工具图标和许可证")
html = rd("web/index.html")
for s in ("xp-core.js", "xp-screens.js", "apps-paint.js", "apps-control.js", "apps-cards.js", "xp.css"): check(s in html, f"index.html 引用 {s}")
# 许可 / 署名
cr = rd("CREDITS.md") if os.path.exists(os.path.join(ROOT, "CREDITS.md")) else ""
for w in ("DualBrain", "jspaint", "Wikimedia"): check(w in cr, f"CREDITS.md 提到 {w}")

# 注册表 / idle
new_apps = ("solitaire", "freecell", "paint", "control")
check(all(a in R.APPS for a in new_apps), "新应用在注册表里")
for a in ("sol_new", "sol_play", "fc_new", "fc_play", "paint_tool", "paint_color", "paint_clear", "paint_draw", "control_open", "bsod", "balloon"):
    check(a in R.ACTIONS, f"动作 {a} 已注册")
    check(("ACT." + a) in rd("web/agent-actions.js") or re.search(r"\b%s\s*[:(]" % a, rd("web/agent-actions.js")), f"页面执行器实现了 {a}")
for n in ("play_solitaire", "play_freecell", "paint_draw", "tweak_sound"): check(n in I.ACTS and n in I.weights_of(cfg), f"idle 活动 {n}")
check(rd("README.md").count(f"{len(R.ACTIONS)} 个动作") + rd("README.md").count(f"{len(R.ACTIONS)} 个") >= 1, f"README 提到当前动作数 {len(R.ACTIONS)}")
print("xp 离线测试 " + ("全部通过" if not bad else f"{bad} 项失败")); sys.exit(1 if bad else 0)
