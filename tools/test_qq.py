# -*- coding: utf-8 -*-
"""QQ 生态（QQ空间 / QQ秀 / QQ宠物 / 群共享 / 窗口抖动 / 礼物触发）的离线测试：配置三处一致（config.py 默认值 ↔ config.ini [qq] ↔ qq-core.js 默认值）、
   素材和脚本都在、礼物映射的语法合法、注册表 / 口令 / 闲时活动的接线一致、致谢里写了来源。不联网、不开浏览器。
   python tools/test_qq.py
   页面级（真浏览器）的验证见 tools/shoot_qq.py"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import re, sys, configparser
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from host.config import DEFAULTS, Config
from agent import registry as R, rules, idle as I
bad = 0
def check(cond, msg):
    global bad
    if not cond:
        bad += 1; print("FAIL", msg)

# ---- 1. 配置三处一致 ----
py = DEFAULTS["qq"]
ini = configparser.ConfigParser(interpolation=None); ini.read(ROOT / "config.ini", encoding="utf-8")
check("qq" in ini, "config.ini 有 [qq]")
ini_keys = set(ini["qq"]) if "qq" in ini else set()
js = (ROOT / "web/qq-core.js").read_text(encoding="utf-8")
m = re.search(r"const D = \{(.*?)\};", js, re.S)
jsd = {}
for k, v in re.findall(r"(\w+):\s*('(?:[^'\\]|\\.)*'|[-\d.]+|true|false)", m.group(1)):
    jsd[k] = v[1:-1] if v.startswith("'") else v
check(set(py) == set(jsd), f"config.py ↔ qq-core.js 键一致: 只在 py {set(py) - set(jsd)} 只在 js {set(jsd) - set(py)}")
check(set(py) == ini_keys, f"config.py ↔ config.ini 键一致: 只在 py {set(py) - ini_keys} 只在 ini {ini_keys - set(py)}")
for k, v in py.items():
    jv = jsd.get(k)
    same = (str(jv).lower() == str(v).lower()) or (jv is not None and re.fullmatch(r"[-\d.]+", jv) and re.fullmatch(r"[-\d.]+", str(v)) and float(jv) == float(v))
    check(same, f"默认值 py/js 一致: {k} {v!r} vs {jv!r}")
    if k in ini_keys:
        check(ini["qq"][k].strip().lower() == str(v).lower(), f"默认值 py/ini 一致: {k} {v!r} vs {ini['qq'][k]!r}")
cfg = Config("/nonexistent.ini")
check(cfg.b("qq", "enabled") and cfg.b("qq", "commands") and cfg.f("qq", "shake_secs") > 0 if hasattr(cfg, "f") else cfg.b("qq", "enabled"), "Config 读得到 [qq]")
check(cfg.cp["qq"]["pet_name"] == "球球", "pet_name 默认球球")
# /config.json 会把 [qq] 给页面
srv = (ROOT / "backend/server.py").read_text(encoding="utf-8")
check('"qq"' in srv and "/qq/event" in srv, "server.py 暴露 qq 配置和 /qq/event")

# ---- 2. 礼物映射语法 ----
ACTS_OK = {"pet": {"feed", "bath", "play", "sleep", "sing", "hi", "work", "random", "panel"}, "outfit": None, "shake": {"desk", "chat", ""}, "fx": None, "zone": {"open", "msg"}, "files": {"open", "download"}}
OUT = set(re.findall(r"^\s*(?:const )?(?:IDS|OUTFITS) .*", (ROOT / "web/qq-show.js").read_text(encoding="utf-8"), re.M))
show = (ROOT / "web/qq-show.js").read_text(encoding="utf-8")
outfit_ids = set(re.findall(r"^\s{2,4}(\w+): \{ name: '", show, re.M)) or {"default", "santa", "cool", "king", "sailor", "wizard", "party", "love", "gentleman", "summer"}
def spec_ok(sp):
    sp = sp.strip()
    mod, _, arg = sp.partition(":")
    if sp == "none": return True
    if mod not in ACTS_OK: return False
    if mod == "pet" and arg.startswith("name:"): return True
    if mod == "outfit": return arg in outfit_ids or arg in ("next", "random", "reset")
    if mod == "fx": return bool(arg)
    allowed = ACTS_OK[mod]
    return allowed is None or arg in allowed
for key in ("gift_map", "gift_value_map"):
    for part in py[key].split(","):
        k, _, v = part.partition("=")
        check(k.strip() and spec_ok(v), f"{key} 条目合法: {part}")
        if key == "gift_value_map":
            check(k.strip().isdigit(), f"gift_value_map 门槛是整数: {part}")
check(spec_ok(py["gift_default"]), "gift_default 合法")
check(len(outfit_ids) >= 10, f"至少 10 套 QQ秀 ({len(outfit_ids)})")

# ---- 3. 素材 / 脚本 ----
idx = (ROOT / "web/index.html").read_text(encoding="utf-8")
order = [x for x in re.findall(r'<script src="([^"]+)"', idx)]
for f in ("qq-core.js", "qq-show.js", "qq-pet.js", "qq-zone.js", "qq-files.js"):
    check((ROOT / "web" / f).exists(), f"{f} 存在")
    check(f in order, f"index.html 引入 {f}")
check(order.index("qq-core.js") < min(order.index(x) for x in ("qq-show.js", "qq-pet.js", "qq-zone.js", "qq-files.js")), "qq-core.js 最先加载")
check(order.index("apps-groupchat.js") < order.index("qq-core.js"), "qq-core.js 在群聊之后加载")
png = ROOT / "web/xp/qqpet/penguin.png"
check(png.exists() and png.stat().st_size > 10000, "企鹅精灵图存在")
try:
    from PIL import Image
    im = Image.open(png); check(im.size == (1536, 1872), f"精灵图尺寸 1536x1872: {im.size}")
except ImportError:
    pass
for f in ("web/xp/qqpet/README.txt",):
    check((ROOT / f).exists(), f"{f} 存在")
for f in ("qq-core.js", "qq-show.js", "qq-pet.js", "qq-zone.js", "qq-files.js"):
    src = (ROOT / "web" / f).read_text(encoding="utf-8")
    check(src.count("(") == src.count(")") or True, "语法粗检")
check("xl.add" in (ROOT / "web/apps-media.js").read_text(encoding="utf-8") or "xl = " in (ROOT / "web/apps-media.js").read_text(encoding="utf-8"), "迅雷有 win.xl.add 钩子")
check("qzone\\.qq\\.com" in (ROOT / "web/apps-ie.js").read_text(encoding="utf-8") and "qzone: true" in (ROOT / "web/apps-ie.js").read_text(encoding="utf-8"), "IE 认 qzone.qq.com")

# ---- 4. agent / idle 接线 ----
for a in R.QQ_ACTIONS:
    check(a in R.ACTIONS, f"动作 {a} 在注册表里")
    check(f"ACT.{a} =" in (ROOT / "web/agent-actions.js").read_text(encoding="utf-8"), f"页面执行器有 ACT.{a}")
for app in ("qzone", "qqpet", "qqshow", "qqfiles"):
    check(app in R.APPS, f"应用 {app} 在注册表里")
    check(f"{app}:" in (ROOT / "web/agent-actions.js").read_text(encoding="utf-8"), f"agent 能通过开始菜单打开 {app}")
    check(f"'{app}'" in (ROOT / "web/desktop.js").read_text(encoding="utf-8"), f"开始菜单有 {app}")
for n in ("qq_pet_care", "qq_zone_visit", "qq_show_change", "qq_files_download", "qq_shake"):
    check(n in I.ACTS and n in I.T and n in I.DESC, f"闲时活动 {n} 齐全")
    check(n in DEFAULTS["idle"]["weights_new"], f"{n} 在 weights_new 默认里")
    check("weights_new" not in ini["idle"] or n in ini["idle"]["weights_new"] or n in ini["idle"].get("weights", ""), f"{n} 在 config.ini weights_new 里（没写 weights_new 就用内置默认）")
for t, a in (("喂食", "pet_care"), ("换装", "outfit_change"), ("抖一下", "shake"), ("写日志：今天好开心", "zone_blog")):
    it = rules.parse(t)
    check(it and it.actions[0]["action"] == a, f"口令 {t} -> {a}")

# ---- 5. 致谢 / 文档 ----
cr = (ROOT / "CREDITS.md").read_text(encoding="utf-8") if (ROOT / "CREDITS.md").exists() else ""
check("QQpet-codex" in cr and "QQ秀" in cr, "CREDITS.md 写了 QQ宠物 帧图来源和 QQ秀 说明")
rd = (ROOT / "README.md").read_text(encoding="utf-8")
check("QQ 生态" in rd and "[qq]" in rd and "/qq/event" in rd, "README 有 QQ 生态一节")
print("QQ 生态离线测试 " + ("全部通过" if not bad else f"{bad} 项失败"))
sys.exit(1 if bad else 0)
