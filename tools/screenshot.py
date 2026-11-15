# 用 Playwright + 系统 Chrome 截图：python tools/screenshot.py URL out.png W H 等待毫秒（仅开发用，不在 requirements 里）
import sys
from playwright.sync_api import sync_playwright
# usage: shoot.py URL out.png W H wait_ms
url,out,w,h,wait=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5])
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    pg=b.new_page(viewport={"width":w,"height":h})
    pg.on("console",lambda m:print("console:",m.text))
    pg.on("pageerror",lambda e:print("pageerror:",e))
    pg.goto(url); pg.wait_for_timeout(wait)
    pg.screenshot(path=out); b.close()
