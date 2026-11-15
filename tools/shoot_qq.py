# -*- coding: utf-8 -*-
"""QQ 生态页面级验证 + 截图（headless Chrome → screenshots/qq2/）。每一步都有断言，最后一行 PASS / FAIL，失败退出码 1。
   先起一个服务：   .venv/bin/python backend/server.py --port 8780          （不带房间号 = 只有 demo 房间，不会碰真实直播）
   然后：           python tools/shoot_qq.py --base http://localhost:8780      （需要 pip install playwright；用系统 Chrome）
   --inject         再用 /qq/event 往“真实直播间”管线灌假礼物（服务要带房间号启动；会在真直播间页面上出现假礼物，所以默认不做）
   --real BASE      同上，但页面和 /qq/event 都指向另一个服务（BASE）
   --agent          额外测一遍 agent 的 QQ 动作（/agent/do，光标真的去点；需要服务 [agent] test_endpoints=true）"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import argparse, json, sys, time, urllib.parse, urllib.request
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://localhost:8765")
ap.add_argument("--inject", action="store_true")
ap.add_argument("--real", default="")
ap.add_argument("--agent", action="store_true")
ap.add_argument("--chrome", default="")
A = ap.parse_args()
OUT = Path(__file__).resolve().parent.parent / "screenshots" / "qq2"; OUT.mkdir(parents=True, exist_ok=True)
from playwright.sync_api import sync_playwright
bad = []
def check(c, m):
    print(("ok   " if c else "FAIL ") + m)
    if not c: bad.append(m)
def get(base, p):
    with urllib.request.urlopen(base + p, timeout=60) as r: return json.loads(r.read())
def quant(path):
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB"); im.quantize(256, method=Image.MEDIANCUT, dither=Image.NONE).save(path, optimize=True)
    except Exception: pass
def shot(pg, name, **kw):
    p = OUT / name; pg.screenshot(path=str(p), **kw); quant(p); print("  →", p.relative_to(OUT.parent.parent))
Q = "?desk=xp&xp_boot=0&demo=1&demoquiet=1&host=1&musicdemo=1"
with sync_playwright() as p:
    import shutil
    exe = A.chrome or shutil.which("google-chrome") or shutil.which("chromium") or "/usr/bin/google-chrome"
    b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
    def page(extra="", real=False):
        pg = b.new_page(viewport={"width": 1280, "height": 720}); pg.errs = []
        pg.on("pageerror", lambda e: pg.errs.append(str(e))); pg.on("console", lambda m: m.type == "error" and pg.errs.append(m.text))
        pg.goto(((A.real or A.base) if real else A.base) + ("/?desk=xp&xp_boot=0&host=1&musicdemo=1" if real else Q) + extra); pg.wait_for_timeout(1800); return pg
    ev = lambda pg, d: pg.evaluate("(d)=>document.dispatchEvent(new CustomEvent('qqev',{detail:d}))", d)

    # ---- 1. 配置 + 脚本加载 ----
    pg = page("&qq_gift_cooldown=0&qq_outfit_revert=3&qq_zone_msgs=all")
    cj = get(A.base, "/config.json"); check("qq" in cj and cj["qq"].get("pet") is not None, "/config.json 带 qq 配置")
    check(pg.evaluate("!!(window.QQX&&QQX.mods.show&&QQX.mods.pet&&QQX.mods.zone&&QQX.mods.files)"), "QQX 四个模块都加载了")
    check(pg.evaluate("QQX.cfg.pet_name") == cj["qq"]["pet_name"], "页面拿到 config.ini 的 pet_name")
    # URL 参数覆盖
    check(pg.evaluate("QQX.cfg.gift_cooldown") == 0 and pg.evaluate("QQX.cfg.zone_msgs") == "all", "?qq_xxx= 能覆盖配置")

    # ---- 2. QQ秀：10 套造型的联系表 ----
    ids = pg.evaluate("QQX.show.IDS"); check(len(ids) >= 10, f"{len(ids)} 套 QQ秀")
    from PIL import Image
    pg.evaluate("QQX.cfg.outfit_revert=0"); tiles = []
    for i, oid in enumerate(ids):
        pg.evaluate(f"QQPig.setPose({[8,0,9,3,12,16,15,4,10,13][i % 10]},true)"); pg.evaluate(f"QQX.show.wear('{oid}',{{}})"); pg.wait_for_timeout(500)
        t = f"/tmp/_qs{i}.png"; pg.locator("#stage").screenshot(path=t); tiles.append(Image.open(t).convert("RGB"))
    w, h = tiles[0].size; sh = Image.new("RGB", (w * 5, h * 2))
    for i, im in enumerate(tiles): sh.paste(im, ((i % 5) * w, (i // 5) * h))
    sh.save(OUT / "show_outfits.png"); quant(OUT / "show_outfits.png"); print("  → screenshots/qq2/show_outfits.png")
    pg.evaluate("QQX.cfg.outfit_revert=3; QQX.show.wear('default',{})")
    pg.click("#showname"); pg.wait_for_timeout(500); shot(pg, "show_shop.png")
    pg.click('.qs .cd[data-outfit="cool"]'); pg.click('.qs [data-act="save"]'); pg.wait_for_timeout(400)
    check("cool" in (pg.evaluate("localStorage.getItem('qqx.outfit')") or ""), "“穿上并保存”写进 localStorage")
    pg.evaluate("QQX.show.wear('default',{perm:true}); localStorage.removeItem('qqx.outfit')"); pg.evaluate("WM.byId.qqshow && WM.byId.qqshow.close()")

    # ---- 3. 礼物映射 ----
    pg.evaluate("QQX.pet.set({hunger:30,clean:50,mood:50})")
    ev(pg, {"t": "gift", "uid": "g1", "name": "小明", "gift": "玫瑰花", "count": 1}); pg.wait_for_timeout(500)
    check(pg.evaluate("QQX.pet.state().hunger") > 30, "礼物 玫瑰花（gift_map）→ 宠物喂食，饱食度上升")
    ev(pg, {"t": "gift", "uid": "g2", "name": "小红", "gift": "加油鸭", "count": 1}); pg.wait_for_timeout(400)
    cur = pg.evaluate("QQX.state().outfit.cur"); check(cur != "default", f"礼物 加油鸭（gift_map）→ 换装（{cur}）")
    pg.wait_for_timeout(3600); check(pg.evaluate("QQX.state().outfit.cur") == "default", "outfit_revert 秒后穿回默认")
    ev(pg, {"t": "gift", "uid": "g3", "name": "阿杰", "gift": "未知礼物A", "count": 1, "value": 520}); pg.wait_for_timeout(400)
    check(pg.evaluate("QQX.state().outfit.cur") == "party", "未知礼物 value=520（gift_value_map）→ 派对装")
    pg.evaluate("QQX.show.wear('default',{})")
    r0 = pg.evaluate("[WM.byId.qqchat.rect.x,WM.byId.qqchat.rect.y]")
    ev(pg, {"t": "gift", "uid": "g4", "name": "老王", "gift": "啤酒", "count": 1}); pg.wait_for_timeout(250)
    r1 = pg.evaluate("[WM.byId.qqchat.rect.x,WM.byId.qqchat.rect.y]"); pg.wait_for_timeout(1800); r2 = pg.evaluate("[WM.byId.qqchat.rect.x,WM.byId.qqchat.rect.y]")
    check(r1 != r0 and r2 == r0, f"礼物 啤酒 → 群聊窗口抖动，抖完回到原位 {r0}→{r1}→{r2}")
    n0 = pg.evaluate("QQX.log.length"); pg.evaluate("QQX.cfg.gift_default='none'")
    ev(pg, {"t": "gift", "uid": "g5", "name": "路人", "gift": "未知礼物B", "count": 1, "value": 0}); pg.wait_for_timeout(200)
    check(pg.evaluate("QQX.log.length") == n0, "gift_default=none 时没命中就什么也不做")
    pg.evaluate("QQX.cfg.gift_default='pet:play'; QQX.cfg.gift_effects=false"); n0 = pg.evaluate("QQX.log.length")
    ev(pg, {"t": "gift", "uid": "g6", "name": "路人", "gift": "玫瑰花", "count": 1}); pg.wait_for_timeout(200)
    check(pg.evaluate("QQX.log.length") == n0, "gift_effects=false 全关")
    pg.evaluate("QQX.cfg.gift_effects=true")
    pg.evaluate("QQX.cfg.shake_cooldown=60"); pg.evaluate("QQX.shake('desk',{})")
    check(pg.evaluate("QQX.shake('desk',{})") is False, "shake_cooldown 内第二次触发被拒")
    check(pg.evaluate("QQX.shake('desk',{force:true})") is True, "force（手动菜单）不受冷却")
    pg.wait_for_timeout(1500)

    # ---- 4. QQ宠物 ----
    pg.evaluate("QQX.pet.set({hunger:70,clean:70,mood:70})"); pg.wait_for_timeout(600); clip = {"x": 0, "y": 480, "width": 1280, "height": 240}
    shot(pg, "pet_idle.png", clip=clip)
    pg.evaluate("QQX.pet.care('feed',{food:'cake',who:'小明'})"); pg.wait_for_timeout(500); shot(pg, "pet_feed.png", clip=clip)
    pg.evaluate("QQX.pet.care('bath',{who:'小红'})"); pg.wait_for_timeout(700); shot(pg, "pet_bath.png", clip=clip)
    pg.evaluate("QQX.pet.set({hunger:10})"); pg.wait_for_timeout(3200)
    check(pg.evaluate("QQX.pet.state().anim") in ("pant", "lie"), "饿了（hunger<25）气喘吁吁")
    shot(pg, "pet_hungry.png", clip=clip)
    pg.evaluate("QQX.pet.set({hunger:80,clean:80,mood:80})")
    ev(pg, {"t": "chat", "uid": "c1", "name": "小明", "text": "球球好可爱"}); pg.wait_for_timeout(500)
    pg.dblclick("#qqx-pet"); pg.wait_for_timeout(600); check(pg.evaluate("!!document.querySelector('.qp')"), "双击宠物 → 宠物面板"); shot(pg, "pet_panel.png")
    pg.click('.qp [data-act="sleep"]'); pg.wait_for_timeout(600); check(pg.evaluate("QQX.pet.state().anim") == "sleep", "面板“睡觉”→ 睡着")
    pg.click("#qqx-pet", button="right"); pg.wait_for_timeout(300); check(pg.evaluate("document.querySelectorAll('.xpm').length") >= 1, "右键宠物 → 菜单"); shot(pg, "pet_menu.png", clip={"x": 0, "y": 360, "width": 900, "height": 360})
    pg.keyboard.press("Escape"); pg.mouse.click(700, 300); pg.evaluate("WM.byId.qqpet && WM.byId.qqpet.close()")

    # ---- 5. QQ空间 ----
    for i, (n, t) in enumerate([("痴情梦丶", "沙发！！"), ("冷月无声", "主播好人一生平安"), ("阿杰", "留言：来踩踩空间")]): ev(pg, {"t": "chat", "uid": "z%d" % i, "name": n, "text": t})
    pg.wait_for_timeout(300)
    z = pg.evaluate("QQX.zone.state()"); check(z["msgs"] >= 3, f"zone_msgs=all：弹幕变成留言（{z['msgs']} 条）"); check(z["visits"] >= 1, "真实观众进了最近访客")
    pg.click("#qq-im-groupspace"); pg.wait_for_timeout(700); check(pg.evaluate("!!WM.byId.qzone"), "群聊“群空间”→ QQ空间窗口"); shot(pg, "zone_home.png")
    pg.click('.qz .nv b[data-tab="msg"]'); pg.wait_for_timeout(300); check(pg.evaluate("document.body.innerText.includes('痴情梦丶')"), "留言板里有观众的名字"); shot(pg, "zone_msgs.png")
    pg.click('.qz .nv b[data-tab="blog"]'); pg.click('.qz [data-act="newblog"]'); pg.fill(".qz-title", "今天直播好开心"); pg.fill(".qz-body", "和大家聊天，空间也热闹了。"); pg.click('.qz [data-act="publish"]'); pg.wait_for_timeout(300); shot(pg, "zone_blog.png")
    check(pg.evaluate("QQX.zone.state().blogs") >= 4, "写日志并发表")
    pg.click('.qz .nv b[data-tab="album"]'); pg.click('.qz [data-album="gg"]'); pg.wait_for_timeout(500); shot(pg, "zone_album.png")
    pg.click('.qz .nv b[data-tab="music"]'); pg.wait_for_timeout(300); shot(pg, "zone_music.png")
    pg.evaluate("WM.byId.qzone.close && WM.byId.qzone.close()")

    # ---- 6. 群共享 + 迅雷 ----
    pg.click("#qq-im-files"); pg.wait_for_timeout(500); pg.click('.qf tr[data-file="2"]'); pg.click('.qf [data-act="download"]'); pg.wait_for_timeout(2500)
    xl = pg.evaluate("WM.byId.xunlei && WM.byId.xunlei.xl && WM.byId.xunlei.xl.list().length"); check(xl and xl >= 1, "群共享“下载”→ 迅雷里出现任务"); shot(pg, "files_xunlei.png")
    for i in range(12):     # 关注时“上传文件”是随机的（概率），多关注几次
        ev(pg, {"t": "follow", "uid": "f%d" % i, "name": "新粉丝小王%d" % i}); pg.wait_for_timeout(120)
    check(pg.evaluate("QQX.files.list().some(f=>/小王/.test(JSON.stringify(f)))"), "关注事件 → 群共享里多一个“新粉丝上传”的文件")

    # ---- 7. 开始菜单 / IE ----
    pg2 = page(); pg2.click("#start"); pg2.wait_for_timeout(300); pg2.hover("#startmenu .it.allp"); pg2.wait_for_timeout(500)
    txt = pg2.evaluate("document.body.innerText"); check(all(s in txt for s in ("QQ空间", "QQ宠物", "QQ秀商城", "群共享")), "开始菜单 → 所有程序 里有 QQ空间 / QQ宠物 / QQ秀商城 / 群共享"); shot(pg2, "startmenu.png")
    check(not pg.errs and not pg2.errs, f"页面没有报错 {pg.errs[:2]} {pg2.errs[:2]}")
    pg2.close()
    pg3 = page("&qq_pet=0&qq_zone=0&qq_show=0&qq_files=0")
    check(pg3.evaluate("!document.getElementById('qqx-pet') && !document.getElementById('qq-im-files')"), "[qq] pet / files 关了就不出现"); check(pg3.evaluate("document.getElementById('qqx-outfit')===null"), "[qq] show 关了没有换装层")
    pg3.close(); pg4 = page("&qq_enabled=0"); check(pg4.evaluate("!document.getElementById('qqx-pet')"), "[qq] enabled=0 整个 QQ 生态不出现"); pg4.close()

    # ---- 8. agent 动作（可选）----
    if A.agent:
        pa = page("&qq_outfit_revert=0")
        pa.evaluate("""window.__res=[];for(const k of Object.keys(AG.ACT)){const f=AG.ACT[k];AG.ACT[k]=async a=>{try{const r=await f(a);window.__res.push(k+': '+r);return r}catch(e){window.__res.push(k+' FAIL '+e.message);throw e}}};0""")
        seq = [[{"action": "pet_care", "what": "feed", "food": "cake"}], [{"action": "outfit_change", "name": "santa"}], [{"action": "shake", "target": "chat"}],
               [{"action": "zone_blog", "title": "测试日志", "text": "测试观众说：今天很开心"}], [{"action": "zone_msg", "text": "测试观众说：沙发"}], [{"action": "files_download", "name": "表情包"}]]
        for a in seq:
            r = get(A.base, "/agent/do?a=" + urllib.parse.quote(json.dumps(a)))
            try: pa.wait_for_function("AG.running===true", timeout=3000)
            except Exception: pass
            pa.wait_for_function("!AG.running", timeout=90000); res = pa.evaluate("window.__res.splice(0)")
            check(r.get("ok") and res and "FAIL" not in res[0], f"agent {a[0]['action']}: {res[0] if res else r}")
        shot(pa, "agent_final.png"); pa.close()

    # ---- 9. /qq/event：假事件走真实直播间管线 ----
    if A.inject or A.real:
        base = A.real or A.base; pr = page("", real=True)
        pr.evaluate("QQX.cfg.gift_cooldown=0; QQX.pet.set({hunger:20})")
        r = get(base, "/qq/event?t=gift&name=" + urllib.parse.quote("测试观众") + "&gift=" + urllib.parse.quote("玫瑰花") + "&value=1")
        check(r.get("ok"), f"/qq/event 接受（{r.get('error', '')}）"); pr.wait_for_timeout(1500)
        check(pr.evaluate("QQX.pet.state().hunger") > 20, "真实管线里的假礼物 → 页面上宠物被喂")
        get(base, "/qq/event?t=chat&name=" + urllib.parse.quote("测试观众") + "&text=" + urllib.parse.quote("留言：沙发")); pr.wait_for_timeout(800)
        check(pr.evaluate("QQX.zone.state().msgs") >= 1, "真实管线里的弹幕 → QQ空间留言"); pr.close()
    b.close()
print("\n" + ("PASS" if not bad else f"FAIL ({len(bad)})")); sys.exit(1 if bad else 0)
