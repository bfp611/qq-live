# 开发用：Playwright 无头 Chrome 打开 demo，记录 猪猪侠 的姿势切换 / 音频播放 / 说话弹跳幅度
#   python tools/test_host.py "http://localhost:8765/?demo=1&volume=0.2" 60
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import sys, json, time
from playwright.sync_api import sync_playwright
url, secs = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 45
INIT = """
window.__plays=[]; window.__poses=[]; window.__maxTalk=0; window.__says=[];
const _p=HTMLMediaElement.prototype.play;
HTMLMediaElement.prototype.play=function(){ const a=this, r={src:a.src,t:Date.now()}; window.__plays.push(r);
  a.addEventListener('ended',()=>{r.ended=true;r.dur=a.duration;r.ct=a.currentTime}); return _p.apply(this,arguments); };
document.addEventListener('DOMContentLoaded',()=>{
  new MutationObserver(m=>m.forEach(x=>{ if(x.target.classList.contains('on')) window.__poses.push({t:Date.now(),src:x.target.getAttribute('src'),mo:document.getElementById('pigmotion').dataset.mo,bubble:document.getElementById('btext').textContent.slice(0,24)}); }))
    .observe(document.getElementById('pig'),{subtree:true,attributes:true,attributeFilter:['class']});
  setInterval(()=>{window.__maxTalk=Math.max(window.__maxTalk,parseFloat(document.getElementById('pigtalk').style.getPropertyValue('--talk')||0));},30);
});
"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(viewport={"width": 760, "height": 720})
    pg.add_init_script(INIT)
    pg.on("pageerror", lambda e: print("pageerror:", e))
    pg.on("console", lambda m: m.type == "error" and print("console error:", m.text))
    pg.goto(url); pg.wait_for_timeout(secs * 1000)
    r = pg.evaluate("({plays:__plays,poses:__poses,maxTalk:__maxTalk})")
    t0 = r["poses"][0]["t"] if r["poses"] else 0
    for x in r["poses"]: print(f"+{(x['t']-t0)/1000:5.1f}s  {x['src']}  mo={x['mo']}  bubble={x['bubble']!r}")
    print("audio plays:", len(r["plays"]), "ended:", sum(1 for x in r["plays"] if x.get("ended")), [(round(x.get('dur',0),1), round(x.get('ct',0),1)) for x in r["plays"]])
    print("max --talk:", round(r["maxTalk"], 2))
    b.close()
