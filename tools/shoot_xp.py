#!/usr/bin/env python3
"""XP 加强包截图（无头 Chrome，要 playwright）：开机 / 欢迎 / 注销 / 关机 / 蓝屏 / 气泡 / QQ 通知 / 画图 / 纸牌 / 空当接龙 / 控制面板。
用法：python tools/shoot_xp.py [http://localhost:8765] ；输出到 screenshots/xp2/"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import sys, os, json, time, urllib.request, urllib.parse
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots", "xp2"); os.makedirs(OUT, exist_ok=True)
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None)
Q = "/?desk=xp&xp_boot=0&demo=1&demoquiet=1&host=1&musicdemo=1"
def agent(acts):
    r = _agent(acts)
    try: pg.wait_for_function("AG.running===true", timeout=4000)
    except Exception: pass
    pg.wait_for_function("!AG.running", timeout=120000); return r
def _agent(acts):
    u = BASE + "/agent/do?a=" + urllib.parse.quote(json.dumps(acts)); 
    return json.loads(urllib.request.urlopen(u, timeout=120).read())
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"]) if CHROME else p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 720}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    shot = lambda n: pg.screenshot(path=f"{OUT}/{n}.png")
    pg.goto(BASE + Q + "&xp_speed=2"); pg.wait_for_timeout(1500)
    # ---- 屏幕
    pg.evaluate("void XP.boot()"); pg.wait_for_function("XP.screen==='boot'"); pg.wait_for_timeout(1300); shot("01_boot")
    pg.wait_for_function("XP.screen==='welcome'"); pg.wait_for_timeout(900); shot("02_welcome")
    pg.wait_for_function("!XP.screen", timeout=20000)
    def scr(name, fn, f, d=500):
        pg.evaluate(fn); pg.wait_for_function(f"XP.screen==='{name}'", timeout=8000); pg.wait_for_timeout(d); shot(f)
    scr("logoff", "void XP.logoff()", "03_logoff"); pg.wait_for_function("!XP.screen", timeout=20000)
    scr("shutdown", 'void XP.shutdown("shutdown")', "04_shutdown"); pg.wait_for_function("XP.screen==='off'", timeout=10000); pg.wait_for_timeout(300); shot("05_off"); pg.wait_for_function("!XP.screen", timeout=30000)
    scr("bsod", 'void XP.bsod("demo")', "06_bsod", 1500); pg.wait_for_function("!XP.screen", timeout=40000); pg.wait_for_timeout(900); shot("07_after_bsod")
    pg.evaluate("XP.hardware()"); pg.wait_for_timeout(800); shot("08_balloon")
    pg.evaluate("XP.qqOnline()"); pg.wait_for_timeout(700); shot("09_qq_toast")
    pg.wait_for_timeout(7500)
    # ---- 画图：让 AI 的光标真去画
    r = agent([{"action": "open_app", "app": "paint"}, {"action": "paint_draw", "what": "house"}]); print("paint:", r.get("ok"), r.get("rejected"))
    pg.wait_for_timeout(500); shot("10_paint_house")
    agent([{"action": "paint_clear"}, {"action": "paint_draw", "what": "sun"}]); pg.wait_for_timeout(400); shot("11_paint_sun")
    pg.evaluate("WM.byId.paint && (WM.byId.paint._confirmed = true, WM.byId.paint.close())")
    # ---- 纸牌
    agent([{"action": "open_app", "app": "solitaire"}, {"action": "sol_new"}, {"action": "sol_play", "steps": 24}]); pg.wait_for_timeout(400); shot("12_solitaire")
    won = pg.evaluate("""(async()=>{const s=WM.byId.solitaire.sol; for(let g=0;g<60;g++){ for(let i=0;i<900;i++){ if(s.state().won) return g; const p=s.plan(); if(!p) break;
        if(p.kind==='stock') s.draw(); else s.exec(p.cs,p.exec); } if(s.state().won) return g; s.newGame(); } return -1;})()""")
    print("solitaire auto-win after deals:", won)
    if won != -1: pg.wait_for_timeout(2500); shot("13_solitaire_win")
    pg.evaluate("WM.byId.solitaire && WM.byId.solitaire.close()")
    # ---- 空当接龙
    agent([{"action": "open_app", "app": "freecell"}, {"action": "fc_new", "no": 617}, {"action": "fc_play", "steps": 10}]); pg.wait_for_timeout(400); shot("14_freecell")
    ok = pg.evaluate("""(async()=>{const fc=WM.byId.freecell.fc; fc.newGame(617); const r=await fc.solve(8000); if(!r.ok) return false; for(const m of r.moves){ const x=fc.resolveMove(m); if(!x) break; fc.applyMove(m);} return fc.state().won;})()""")
    print("freecell 617 solved:", ok)
    pg.wait_for_timeout(2500); shot("15_freecell_win"); pg.evaluate("WM.byId.freecell && WM.byId.freecell.close()")
    # ---- 控制面板
    pg.evaluate("WM.open('control')"); pg.wait_for_timeout(400); shot("16_control_panel")
    pg.click('.cp .cat[data-cat="声音、语音和音频设备"]'); pg.wait_for_timeout(250); shot("17_control_sound_cat")
    pg.click('.cp [data-task="更改声音方案"]'); pg.wait_for_timeout(400); shot("18_sound_applet")
    pg.evaluate("WM.byId.sndcpl.close(); WM.open('mousecpl',{tab:'指针选项'})"); pg.wait_for_timeout(300); pg.click('[data-k="trail"]'); pg.mouse.move(300, 300); pg.mouse.move(500, 380, steps=10); shot("19_mouse_applet")
    print("errors:", errs); b.close()
    sys.exit(1 if errs else 0)
