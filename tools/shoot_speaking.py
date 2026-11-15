# 等到猪猪侠正在说话（气泡出现 + 身体随声音在弹）再截图：python tools/shoot_speaking.py URL out.png W H
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import sys
from playwright.sync_api import sync_playwright
url,out,w,h=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox","--autoplay-policy=no-user-gesture-required"])
    pg=b.new_page(viewport={"width":w,"height":h})
    pg.on("pageerror",lambda e:print("pageerror:",e))
    pg.goto(url)
    pg.wait_for_function("parseFloat(document.getElementById('pigtalk').style.getPropertyValue('--talk')||0)>0.3 && document.getElementById('btext').textContent.length>8",timeout=90000)
    pg.wait_for_timeout(300)
    pg.screenshot(path=out); b.close()
