// AI 加强包（[ai_plus]，?desk=xp）的页面部分：趣味小游戏窗口（成语接龙 / 猜歌名 / 脑筋急转弯）。题目、判分、积分都在服务端（backend/ai6/games.py），
// 这里只显示服务端推来的 {t:"play",k:"game",game:{…}} 快照：题目、倒计时、提示、答题记录、得分榜。
//   AIX.cfg      从 /config.json 的 ai_plus 读到的页面配置
//   AIX.game     最近一次游戏快照
//   AIX.sub(fn)  订阅快照
(function () {
  const UQ = new URLSearchParams(location.search);
  const A = window.AIX = { cfg: { enabled: true, game: true, game_window: true, game_close_secs: 10 }, game: null, subs: [] };
  A.sub = fn => A.subs.push(fn);
  A.ready = fetch('config.json').then(r => r.json()).then(c => { const a = c.ai_plus || {}; for (const k in a) { const d = A.cfg[k]; A.cfg[k] = typeof d === 'boolean' ? /^(1|true|yes|on)$/i.test(String(a[k])) : typeof d === 'number' ? (parseFloat(a[k]) || d) : a[k]; } }).catch(() => {});
  A.on = k => A.cfg.enabled && A.cfg[k] !== false;
  document.addEventListener('qqev', e => { const ev = e.detail || {}; if (ev.t === 'play' && ev.k === 'game') { A.game = ev.game; A.subs.forEach(f => { try { f(ev.game); } catch (er) { console.error('aix', er); } }); } });

  // ================= 画面截取（给视觉模型看；服务端发 {t:"vision_req"} 来要，回 {vision:{id,img}}）=================
  // 页面里没法直接截屏（getDisplayMedia 要用户点同意），所以把桌面 DOM 序列化成 SVG foreignObject 再画到 canvas：样式表、<img>、CSS 背景图都内联成 data: URL
  // （同源文件，单个超过 MAXB 的跳过；结果缓存），去掉 script / iframe / video / canvas。尽力而为：失败就返回空，服务端退回只看文字快照。
  const MAXB = 350 * 1024, dcache = new Map();
  const blobData = b => new Promise(ok => { const f = new FileReader(); f.onload = () => ok(f.result); f.onerror = () => ok(''); f.readAsDataURL(b); });
  async function toData(u) {
    if (dcache.has(u)) return dcache.get(u);
    let r = '';
    try { if (!/^data:/.test(u)) { const res = await fetch(u); if (res.ok) { const b = await res.blob(); if (b.size <= MAXB) r = await blobData(b); } } else r = u; } catch (e) {}
    dcache.set(u, r); return r;
  }
  async function inlineUrls(text, base) {
    const re = /url\(\s*(['"]?)([^'")]+)\1\s*\)/g, urls = new Set(); let m;
    while ((m = re.exec(text))) { if (!/^(data:|#)/.test(m[2])) urls.add(m[2]); }
    const map = {}; await Promise.all([...urls].map(async u => { let abs; try { abs = new URL(u, base).href; } catch (e) { return; } map[u] = await toData(abs); }));
    return text.replace(re, (all, q, u) => (u in map ? (map[u] ? 'url("' + map[u] + '")' : 'none') : all));
  }
  let cssCache = { n: -1, text: '' };
  async function allCss() {
    const sheets = [...document.styleSheets]; if (cssCache.n === sheets.length && cssCache.text) return cssCache.text;
    let out = '';
    for (const sh of sheets) { let t = ''; try { t = [...sh.cssRules].filter(r => r.type !== CSSRule.IMPORT_RULE && r.type !== CSSRule.FONT_FACE_RULE).map(r => r.cssText).join('\n'); } catch (e) { continue; } out += await inlineUrls(t, sh.href || document.baseURI) + '\n'; }
    cssCache = { n: sheets.length, text: out }; return out;
  }
  A.capture = async function (req) {
    const t0 = performance.now(), W = innerWidth, H = innerHeight, mw = Math.max(320, Math.min(1280, (req && req.w) || 768)), sc = Math.min(1, mw / W);
    const css = await allCss(), root = document.body.cloneNode(true);
    root.querySelectorAll('script,iframe,video,audio,canvas,noscript,link').forEach(e => e.remove());
    const imgs = [...root.querySelectorAll('img')];
    await Promise.all(imgs.map(async im => { const u = im.getAttribute('src'); if (!u) return; const d = await toData(new URL(u, document.baseURI).href); if (d) im.setAttribute('src', d); else im.removeAttribute('src'); }));
    await Promise.all([...root.querySelectorAll('[style*="url("]')].map(async e => { e.setAttribute('style', await inlineUrls(e.getAttribute('style'), document.baseURI)); }));
    const bcs = getComputedStyle(document.body), bg = bcs.backgroundColor;
    const wrap = document.createElement('div'); wrap.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml'); wrap.className = document.body.className; wrap.id = 'aixcap';
    wrap.setAttribute('style', 'position:relative;overflow:hidden;width:' + W + 'px;height:' + H + 'px;background-color:' + bg + ';font:' + bcs.font);
    while (root.firstChild) wrap.appendChild(root.firstChild);
    const bodyCss = css.replace(/(^|[\s,}])body(?![\w-])/g, '$1#aixcap').replace(/(^|[\s,}])html(?![\w-])/g, '$1#aixcap');
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '"><foreignObject width="100%" height="100%"><div xmlns="http://www.w3.org/1999/xhtml"><style>' + bodyCss.replace(/</g, '&lt;') + '</style>' + new XMLSerializer().serializeToString(wrap) + '</div></foreignObject></svg>';
    const img = new Image(); img.decoding = 'sync';
    await new Promise((ok, no) => { img.onload = ok; img.onerror = () => no(new Error('svg load')); img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg); });
    const cv = document.createElement('canvas'); cv.width = Math.round(W * sc); cv.height = Math.round(H * sc);
    const g = cv.getContext('2d'); g.fillStyle = bg || '#3a6ea5'; g.fillRect(0, 0, cv.width, cv.height); g.drawImage(img, 0, 0, cv.width, cv.height);
    const out = cv.toDataURL('image/jpeg', 0.62); A.lastCap = { ms: Math.round(performance.now() - t0), kb: Math.round(out.length / 1024), w: cv.width, h: cv.height };
    return out;
  };
  A.onVisionReq = async (m, send) => {
    let img = ''; try { img = await Promise.race([A.capture(m), new Promise((_, no) => setTimeout(() => no(new Error('timeout')), 9000))]); } catch (e) { console.warn('vision capture', e && e.message); A.lastCapErr = String(e && e.message); }
    send({ vision: { id: m.id, img, ok: !!img } });
  };
  if (!window.WM) return;
  const { h, esc } = WM;
  const css = document.createElement('style');
  css.textContent = `
    .ag { display:flex; flex-direction:column; height:100%; background:#fff; font:12px var(--xpfont); color:#000; box-sizing:border-box; }
    .ag .hd { padding:8px 12px 6px; background:linear-gradient(#f4fff0,#d8f0cf); border-bottom:1px solid #7fb98a; } .ag .hd b { font-size:14px; color:#0a5a1a; } .ag .hd .sub { color:#555; margin-top:3px; display:flex; justify-content:space-between; }
    .ag .tm { height:12px; margin:6px 12px 0; border:1px solid #686868; border-radius:2px; padding:1px; background:#fff; box-sizing:border-box; flex:none; } .ag .tm i { display:block; height:100%; background:repeating-linear-gradient(90deg,#37d12c 0 6px,#fff 6px 8px); transition:width .4s linear; }
    .ag .tm.low i { background:repeating-linear-gradient(90deg,#e23 0 6px,#fff 6px 8px); }
    .ag .pq { padding:10px 14px 4px; font-size:19px; line-height:1.35; font-weight:700; color:#0a246a; text-align:center; word-break:break-all; min-height:52px; display:flex; align-items:center; justify-content:center; }
    .ag .ps2 { padding:0 14px 4px; text-align:center; color:#444; min-height:16px; } .ag .ph { margin:2px 14px 4px; padding:3px 8px; background:#fffbe0; border:1px solid #e6d98a; border-radius:3px; color:#7a5b00; display:none; }
    .ag .bd { flex:1; display:flex; min-height:0; gap:8px; padding:4px 12px 8px; } .ag .lg, .ag .bo { flex:1; border:1px solid #7f9db9; background:#fff; overflow:auto; min-width:0; }
    .ag .lg div { padding:2px 6px; border-bottom:1px solid #f0f0f0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; } .ag .lg .ok { color:#0a7a1a; font-weight:700; } .ag .lg .no { color:#777; }
    .ag .bo .t, .ag .lg .t { background:#ece9d8; color:#444; padding:2px 6px; position:sticky; top:0; border-bottom:1px solid #d6d2c2; font-weight:400; }
    .ag .bo .r { display:flex; justify-content:space-between; padding:2px 6px; border-bottom:1px solid #f0f0f0; } .ag .bo .r:first-of-type { background:#fff4c2; } .ag .bo .r b { color:#0a246a; }
    .ag .ft { flex:none; padding:5px 12px; background:#ece9d8; border-top:1px solid #aca899; color:#444; display:flex; justify-content:space-between; }
    .ag.done .pq { color:#0a5a1a; }`;
  document.head.appendChild(css);
  const ICO = 'xp/ui/qq16.png';
  const gwin = () => { const w = WM.byId.game; return w && !w.closed ? w : null; };
  const HOWTO = { idiom: '在群里直接发四字成语接龙（同音字也算），接对加分', song: '在群里发歌名猜，可以发「提示」', riddle: '在群里发答案，可以发「提示」' };
  function render(win, g) {
    const el = win.el, q = s => el.querySelector(s), root = q('.ag');
    if (!g) { q('.hd b').textContent = '当前没有进行中的游戏'; q('.hd .sub').innerHTML = '<span>在群里发「玩成语接龙 / 猜歌名 / 脑筋急转弯」开始</span><span></span>'; q('.pq').textContent = '—'; q('.ps2').textContent = ''; q('.ph').style.display = 'none'; q('.tm i').style.width = '0'; q('.lg').innerHTML = '<div class="t">答题记录</div>'; q('.bo').innerHTML = '<div class="t">得分榜</div>'; q('.ft span:first-child').textContent = '——'; q('.ft span:last-child').textContent = '空闲'; return; }
    const done = g.state === 'done';
    root.classList.toggle('done', done);
    q('.hd b').textContent = g.name + (g.rounds > 1 && g.kind !== 'idiom' ? '　第 ' + g.round + ' / ' + g.rounds + ' 题' : g.kind === 'idiom' ? '　已接 ' + g.round + ' / ' + g.rounds : '');
    q('.hd .sub').innerHTML = '<span>' + (g.by ? esc(g.by) + ' 发起' : 'AI 主播发起') + '</span><span></span>';
    q('.pq').textContent = done ? (g.winner ? '🏆 ' + g.winner : '游戏结束') : g.prompt;
    q('.ps2').textContent = g.sub || '';
    const ph = q('.ph'); ph.style.display = g.hint && !done ? 'block' : 'none'; ph.textContent = '💡 提示：' + (g.hint || '');
    const tm = q('.tm'), pct = g.state === 'open' ? Math.max(0, Math.min(100, g.left * 100 / g.secs)) : 0;
    q('.tm i').style.width = pct + '%'; tm.classList.toggle('low', g.state === 'open' && g.left < g.secs * 0.25);
    q('.lg').innerHTML = '<div class="t">答题记录</div>' + (g.log || []).slice().reverse().map(x => '<div class="' + (x.ok ? 'ok' : 'no') + '">' + (x.ok ? '✔ ' : '✘ ') + esc(x.name) + '：' + esc(x.text) + '</div>').join('');
    q('.bo').innerHTML = '<div class="t">得分榜</div>' + (g.board || []).map(x => '<div class="r"><span>' + esc(x.name) + '</span><b>' + x.pts + ' 分</b></div>').join('');
    q('.ft span:first-child').textContent = done ? (g.note || '游戏结束') : g.state === 'open' ? (HOWTO[g.kind] + '（剩余 ' + Math.ceil(g.left) + ' 秒）') : '下一题马上开始…';
    q('.ft span:last-child').textContent = done ? '已结束' : '进行中';
  }
  let autoOpened = false, closeT = 0, tickT = 0;
  function openGame() {
    return WM.create({ id: 'game', title: '趣味小游戏 - GG-Bond 的直播间', icon: ICO, w: 400, h: 380, minW: 320, minH: 300, x: 520, y: 70, content: win => {
      const root = h('div', { class: 'ag' }, [h('div', { class: 'hd' }, [h('b'), h('div', { class: 'sub' })]), h('div', { class: 'tm' }, [h('i')]), h('div', { class: 'pq' }), h('div', { class: 'ps2' }), h('div', { class: 'ph' }),
        h('div', { class: 'bd' }, [h('div', { class: 'lg' }), h('div', { class: 'bo' })]), h('div', { class: 'ft' }, [h('span'), h('span')])]);
      win.pv = { render: g => render(win, g), state: () => ({ game: A.game, prompt: win.el.querySelector('.pq').textContent, rows: win.el.querySelectorAll('.bo .r').length, log: win.el.querySelectorAll('.lg div').length - 1 }) };
      setTimeout(() => render(win, A.game), 0);
      const iv = setInterval(() => { if (win.closed) return clearInterval(iv); const g = A.game; if (g && g.state === 'open') { g.left = Math.max(0, g.left - 0.5); render(win, g); } }, 500);
      win.o.onclose = () => { clearInterval(iv); autoOpened = false; };
      return root;
    } });
  }
  WM.register('game', { open: () => A.on('game') ? openGame() : WM.alert('趣味小游戏', '小游戏没有开启（[ai_plus] game）。', { kind: 'info' }) });
  A.sub(g => {
    if (!g || !A.on('game')) return;
    if (g.state !== 'done' && A.cfg.game_window && !gwin() && !UQ.get('nogamewin')) { autoOpened = true; clearTimeout(closeT); WM.open('game'); if (window.XP && XP.snd) XP.snd('notify', 'qq'); }
    const w = gwin(); if (w) w.pv.render(g);
    if (g.state === 'done' && autoOpened && w) { clearTimeout(closeT); closeT = setTimeout(() => { const w2 = gwin(); if (w2 && autoOpened) w2.close(); }, Math.max(3, A.cfg.game_close_secs) * 1000); }
  });
})();
