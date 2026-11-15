# -*- coding: utf-8 -*-
"""真人验证守护的面板截图（headless Chrome → screenshots/ops/guard_*.png）：起一个带假直播伴侣日志目录 + 本地 Bark 桩的服务，
   往日志里写一条真实格式的验证弹窗，看手机面板顶部的红条 / 状态 / 测试按钮。python tools/shoot_guard.py（需要 playwright 的 python）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import json, os, socket, subprocess, sys, tempfile, threading, time
os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试服务绝不连真实直播间（测试里的 /qq/event 是假事件）
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots" / "ops"; OUT.mkdir(parents=True, exist_ok=True)
from playwright.sync_api import sync_playwright
bad = []
def check(c, m):
    print(("ok   " if c else "FAIL ") + m)
    if not c: bad.append(m)
def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p
class H(BaseHTTPRequestHandler):
    def do_GET(s): s.send_response(200); s.end_headers(); s.wfile.write(b'{"code":200}')
    def log_message(s, *a): pass
bp = free_port(); hs = HTTPServer(("127.0.0.1", bp), H); threading.Thread(target=hs.serve_forever, daemon=True).start()
E = Path(tempfile.mkdtemp(prefix="shootg-")); mate = E / "mate"; mate.mkdir()
log = mate / "2026-11-15-10-00-00.log"; log.write_text("x\n")
(E / "key.txt").write_text("AbCdEfGhIjKlMnOpQrStUv")
(E / "t.ini").write_text(f"""[music]
enabled = false
[tts]
backend = none
[idle]
enabled = false
[ai]
base_url =
[play]
data_file = {E}/p.json
[ai_plus]
memory_file = {E}/m.json
[ops]
log_dir = {E}/logs
report_dir = {E}/r
panel_token_file = {E}/tok.txt
overrides_file = {E}/ov.json
detect_room = false
autoswitch = false
[guard]
bark_server = http://127.0.0.1:{bp}
bark_key_file = {E}/key.txt
log_dir = {mate}
state_file = {E}/gs.json
sound = false
""")
port = free_port(); base = f"http://127.0.0.1:{port}"
PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
srv = subprocess.Popen([str(PY) if PY.exists() else sys.executable, str(ROOT / "backend/server.py"), "100000000001", "--port", str(port), "--config", str(E / "t.ini")], env=dict(os.environ, TTS_BACKEND="none", PYTHONIOENCODING="utf-8"), stdout=open(E / "srv.out", "w"), stderr=subprocess.STDOUT)
try:
    import urllib.request
    for _ in range(100):
        try: urllib.request.urlopen(base + "/config.json", timeout=2); break
        except Exception: time.sleep(0.4)
    tok = (E / "tok.txt").read_text().strip(); time.sleep(2)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 390, "height": 760}, device_scale_factor=2); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.goto(base + "/panel#token=" + tok); pg.wait_for_timeout(1800)
        check(pg.locator("#alarm.hide").count() == 1, "没有提醒时没有红条")
        txt = pg.locator("#t-home").inner_text(); check("真人验证守护" in txt and "盯日志" in txt and "是：" in txt, "概览里有守护状态（盯日志）")
        pg.screenshot(path=str(OUT / "guard_1_home.png"))
        with open(log, "a", encoding="utf-8") as f:
            f.write("[%s.197.053] [INFO] <render> [VERIFY_DECISION_MESSAGE] evt=verify-decision-message-open room_id=7708169459873139466 timeout=120 current_audience=1 check_reason=adra_punish_center\n" % time.strftime("%Y-%m-%dT%H:%M:%S"))
        pg.wait_for_selector("#alarm:not(.hide)", timeout=8000); pg.wait_for_timeout(500)
        t = pg.locator("#alarm").inner_text(); check("真人验证弹窗" in t and "倒计时" in t and "Bark" in t, "红条：" + t.replace("\n", " | ")[:90])
        pg.screenshot(path=str(OUT / "guard_2_alarm.png"))
        pg.click("#bar button[data-t=do]"); pg.wait_for_timeout(500)
        check(pg.locator("button", has_text="测试推送").count() == 1, "控制页有「测试推送」")
        pg.click("#bar button[data-t=sw]"); pg.wait_for_timeout(500)
        check("真人验证守护" in pg.locator("#t-sw").inner_text() and "Bark 推送到手机" in pg.locator("#t-sw").inner_text(), "开关页第一组是守护")
        pg.screenshot(path=str(OUT / "guard_3_switches.png"))
        pg.click("#alarm button"); pg.wait_for_timeout(2600)
        check(pg.locator("#alarm.hide").count() == 1, "点「我已处理」红条消失")
        pg.click("#bar button[data-t=do]"); pg.wait_for_timeout(300); pg.locator("button", has_text="测试推送").click(); pg.wait_for_selector("#alarm:not(.hide)", timeout=6000); pg.wait_for_timeout(400)
        check("测试" in pg.locator("#alarm").inner_text(), "测试推送 → 黄条")
        pg.screenshot(path=str(OUT / "guard_4_test.png"))
        check(not errs, f"页面没有 JS 错误 {errs}")
        b.close()
finally:
    srv.terminate(); hs.shutdown()
print("PASS" if not bad else "FAIL " + str(bad)); sys.exit(1 if bad else 0)
