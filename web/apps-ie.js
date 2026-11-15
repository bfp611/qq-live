// Internet Explorer 6：本地假网页（xp/ie/*.html，自制的 2007 风格 hao123 / 百度 / 腾讯网），地址栏、前进后退、收藏夹、历史、搜索
(function () {
  if (!window.WM || !WM.ready) return;
  const { h, ICO } = WM;
  const HOME = 'http://www.hao123.com/';
  const SITES = ['sina.com.cn', 'sohu.com', '163.com', 'taobao.com', 'google.cn', 'google.com', 'youku.com', '4399.com', 'xunlei.com', 'joy.cn', 'ctrip.com', '58.com', '17173.com', 'tianya.cn', 'tudou.com', 'kugou.com', 'ttplayer.com', 'baofeng.com', 'xinhuanet.com', 'people.com.cn', 'cctv.com', 'paipai.com', 'joyo.com', 'dangdang.com', '360buy.com', 'xiaonei.com', 'kaixin001.com', 'ganji.com', '12306.cn', 'weather.com.cn', '2144.cn', 'wowchina.com', 'the9.com', '9you.com', 'sogou.com', '5sing.com'];
  function route(u) {
    u = (u || '').trim(); if (!u || u === 'about:blank') return { url: 'about:blank', src: 'about:blank', title: '空白页' };
    if (!/^[a-z]+:\/\//i.test(u)) { if (/\s/.test(u) || !/\./.test(u)) return route('http://www.baidu.com/s?wd=' + encodeURIComponent(u)); u = 'http://' + u; }
    let a; try { a = new URL(u); } catch (e) { return { url: u, src: 'xp/ie/error.html', title: '无法显示该页' }; }
    const host = a.hostname.replace(/^www\./, '');
    if (host === 'hao123.com') return { url: a.href, src: 'xp/ie/home.html' + a.search, title: 'hao123_上网从这里开始' };
    if (host === 'baidu.com' || host === 'mp3.baidu.com' || host === 'tieba.baidu.com' || host === 'music.baidu.com' || host === 'baike.baidu.com' || host === 'map.baidu.com') { if (a.searchParams.get('wd') != null || a.pathname === '/s') return { url: a.href, src: 'xp/ie/results.html' + a.search, title: (a.searchParams.get('wd') || '') + '_百度搜索' }; return { url: a.href, src: host === 'baidu.com' ? 'xp/ie/baidu.html' : 'xp/ie/generic.html?h=' + encodeURIComponent(a.hostname), title: host === 'baidu.com' ? '百度一下，你就知道' : a.hostname }; }
    if (/^(user\.|www\.)?qzone\.qq\.com$|^space\.qq\.com$/.test(host)) return { url: a.href, src: 'xp/ie/generic.html?h=' + encodeURIComponent(a.hostname), title: 'QQ空间', qzone: true };   // → 打开 QQ空间 窗口（qq-zone.js）
    if (host === 'qq.com' || host.endsWith('.qq.com')) return { url: a.href, src: host === 'qq.com' ? 'xp/ie/qq.html' : 'xp/ie/generic.html?h=' + encodeURIComponent(a.hostname), title: host === 'qq.com' ? '腾讯网' : a.hostname };
    if (SITES.some(s => host === s || host.endsWith('.' + s))) return { url: a.href, src: 'xp/ie/generic.html?h=' + encodeURIComponent(a.hostname), title: a.hostname };
    return { url: a.href, src: 'xp/ie/error.html', title: '无法显示该页' };
  }
  const dec = u => { try { return decodeURI(u); } catch (e) { return u; } };
  const FAV = [['hao123_上网从这里开始', 'http://www.hao123.com/'], ['百度一下，你就知道', 'http://www.baidu.com/'], ['腾讯网', 'http://www.qq.com/'], ['新浪', 'http://www.sina.com.cn/'], ['网易', 'http://www.163.com/'], ['淘宝网', 'http://www.taobao.com/'], ['17173 游戏门户', 'http://www.17173.com/'], ['迅雷', 'http://www.xunlei.com/']];
  const st = document.createElement('style'); st.textContent = `
  .ie { position:absolute; inset:0; display:flex; flex-direction:column; background:#ece9d8; font:12px var(--xpfont); }
  .ie .tbar { flex:none; display:flex; align-items:center; height:38px; padding:0 4px; border-bottom:1px solid #d0cfc0; box-shadow:0 1px 0 #fff; position:relative; }
  .ie .tb { display:flex; align-items:center; height:34px; padding:0 4px; border:1px solid transparent; border-radius:3px; margin-right:1px; } .ie .tb:hover:not(.dis) { border-color:#9a9a9a; background:linear-gradient(#fff,#e8e5d6); } .ie .tb img { width:26px; height:26px; margin-right:3px; } .ie .tb.dis { opacity:.45; } .ie .tb.on { border-color:#7a7a7a; background:#e0ddcc; }
  .ie .tsep { width:1px; height:28px; background:#c0bfb0; margin:0 4px; border-right:1px solid #fff; }
  .ie .throb { position:absolute; right:2px; top:0; width:44px; height:36px; background:#fff; border-left:1px solid #aca899; display:flex; align-items:center; justify-content:center; } .ie .throb img { width:32px; height:19px; } .ie .throb.run img { animation:throb .7s steps(4) infinite; } @keyframes throb { 0%{filter:hue-rotate(0)} 100%{filter:hue-rotate(360deg)} }
  .ie .addr { flex:none; display:flex; align-items:center; height:26px; padding:0 4px; border-bottom:1px solid #aca899; }
  .ie .addr .box { flex:1; display:flex; align-items:center; height:20px; background:#fff; border:1px solid #7f9db9; padding:0 2px; margin:0 6px; } .ie .addr input { flex:1; border:0; outline:0; font:12px var(--xpfont); height:16px; background:transparent; }
  .ie .addr .go { display:flex; align-items:center; padding:0 4px; } .ie .addr .go img { width:16px; height:16px; margin-right:3px; }
  .ie .body { flex:1; display:flex; min-height:0; background:#fff; border-top:1px solid #fff; }
  .ie .fav { width:190px; flex:none; background:#fff; border-right:1px solid #aca899; display:flex; flex-direction:column; } .ie .fav .fh { background:#ece9d8; height:22px; display:flex; align-items:center; padding:0 6px; border-bottom:1px solid #aca899; } .ie .fav .fh b { flex:1; font-weight:700; } .ie .fav .fl { flex:1; overflow:auto; padding:4px; } .ie .fav .fl div { display:flex; align-items:center; height:20px; white-space:nowrap; } .ie .fav .fl div:hover { text-decoration:underline; color:#00c; } .ie .fav img { width:16px; height:16px; margin-right:4px; }
  .ie iframe { flex:1; border:0; background:#fff; min-width:0; }
  .ie .status { flex:none; height:21px; display:flex; align-items:center; border-top:1px solid #fff; padding:0 4px; } .ie .status .msg { flex:1; padding:0 6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; } .ie .status .pg { width:100px; height:12px; border:1px solid #888; background:#fff; margin-right:6px; display:none; } .ie .status .pg i { display:block; height:100%; width:0; background:repeating-linear-gradient(90deg,#2a6be0 0 6px,#fff 6px 8px); } .ie .status .zone { width:110px; border-left:1px solid #aca899; padding-left:6px; display:flex; align-items:center; } .ie .status .zone img { width:16px; height:16px; margin-right:4px; }
  `; document.head.appendChild(st);
  WM.register('ie', { open: a => {
    a = a || {}; const S = { hist: [], idx: -1, side: null, loading: false, cur: null };
    const addrIn = h('input', { spellcheck: false, value: '' }), msg = h('div', { class: 'msg', text: '完毕' }), pgb = h('i'), pg = h('div', { class: 'status pg' }), throb = h('div', { class: 'throb' }, [h('img', { src: 'xp/ico/windows.png' })]);
    const ifr = h('iframe', { src: 'about:blank' }); let w, timer;
    const sideEl = h('div', { class: 'fav', style: 'display:none' }), fl = h('div', { class: 'fl' }), fh = h('div', { class: 'fh' });
    sideEl.append(fh, fl);
    function showSide(kind) { if (S.side === kind) { S.side = null; sideEl.style.display = 'none'; upd(); return; } S.side = kind; sideEl.style.display = ''; fh.innerHTML = ''; fh.append(h('b', { text: kind === 'fav' ? '收藏夹' : kind === 'hist' ? '历史记录' : '搜索' }), h('span', { text: '×', style: 'padding:0 4px', onclick: () => showSide(kind) })); fl.innerHTML = '';
      const rows = kind === 'fav' ? FAV : kind === 'hist' ? S.hist.map(x => [x.title, x.url]).reverse() : FAV.slice(1, 3); rows.forEach(([t, u]) => fl.appendChild(h('div', { onclick: () => nav(u) }, [h('img', { src: ICO('896_16.png') }), h('span', { text: t })]))); if (!rows.length) fl.appendChild(h('div', { text: '（空）' })); upd(); }
    function load(r, push) {
      clearTimeout(timer); S.loading = true; msg.textContent = '正在打开网页 ' + r.url + '...'; pg.style.display = 'block'; pgb.style.width = '10%'; throb.classList.add('run'); w.setTitle('正在连接 - Microsoft Internet Explorer'); upd();
      let p = 10; const iv = setInterval(() => { p = Math.min(92, p + 14); pgb.style.width = p + '%'; }, 90);
      timer = setTimeout(() => { clearInterval(iv); ifr.src = r.src; if (r.src === 'about:blank') done(r); }, 420 + (r.src.includes('error') ? 600 : 0)); ifr._r = r; ifr._iv = iv;
    }
    function done(r) { clearInterval(ifr._iv); S.loading = false; pgb.style.width = '100%'; setTimeout(() => { pg.style.display = 'none'; }, 150); throb.classList.remove('run'); msg.textContent = '完毕'; let t = r.title; try { const d = ifr.contentDocument; if (d && d.title) t = d.title; } catch (e) {} r.title = t; const cur = S.hist[S.idx]; if (cur) cur.title = t; w.setTitle(t + ' - Microsoft Internet Explorer'); upd(); }
    function nav(u, replace) { document.dispatchEvent(new Event('xpnav')); const r = route(u); if (r.qzone && window.QQX && QQX.cfg.enabled && QQX.cfg.zone) setTimeout(() => WM.open('qzone'), 60); if (!replace) { S.hist = S.hist.slice(0, S.idx + 1); S.hist.push({ url: r.url, title: r.title, r }); S.idx++; } else { S.hist[S.idx] = { url: r.url, title: r.title, r }; } addrIn.value = r.url === 'about:blank' ? '' : dec(r.url); load(r); }
    const go = d => { const i = S.idx + d; if (i < 0 || i >= S.hist.length) return; S.idx = i; const e = S.hist[i]; addrIn.value = e.url === 'about:blank' ? '' : dec(e.url); load(e.r); };
    ifr.addEventListener('load', () => {
      const r = ifr._r; if (!r || ifr.src.endsWith('about:blank') && r.src !== 'about:blank') return; done(r);
      try {
        const d = ifr.contentDocument; if (!d) return; const k = () => WM.root.getBoundingClientRect().width / WM.DW;
        d.addEventListener('click', e => { const an = e.target.closest && e.target.closest('a[href]'); if (!an) return; const hr = an.getAttribute('href'); if (!hr || hr.startsWith('javascript:') || hr.startsWith('#')) return; e.preventDefault(); nav(an.href); });
        d.addEventListener('submit', e => { e.preventDefault(); const f = e.target; const q = new URLSearchParams(new FormData(f)).toString(); nav(f.action.replace(/\?.*$/, '') + '?' + q); });
        d.addEventListener('pointerdown', () => w.focus());
        d.addEventListener('contextmenu', e => { e.preventDefault(); const ir = ifr.getBoundingClientRect(), rr = WM.root.getBoundingClientRect(), kk = k(); WM.menu([{ t: '后退(B)', dis: S.idx < 1, on: () => go(-1) }, { t: '前进(F)', dis: S.idx >= S.hist.length - 1, on: () => go(1) }, '-', { t: '另存背景为(S)...', dis: true }, { t: '设置为墙纸(G)', dis: true }, '-', { t: '全选(L)', on: () => d.execCommand('selectAll') }, { t: '粘贴(P)', dis: true }, '-', { t: '添加到收藏夹(F)...', on: () => WM.alert('添加到收藏夹', '已将该页添加到收藏夹。', { kind: 'info' }) }, { t: '刷新(E)', on: () => load(r) }, { t: '属性(R)', on: () => WM.alert('属性', '协议: HyperText Transfer Protocol\n类型: HTML 文档\n地址 (URL): ' + r.url, { kind: 'info' }) }], (ir.left - rr.left + e.clientX * kk) / kk, (ir.top - rr.top + e.clientY * kk) / kk); });
        d.addEventListener('mousemove', e => { const an = e.target.closest && e.target.closest('a[href]'); if (an && !an.getAttribute('href').startsWith('javascript')) msg.textContent = an.href; else if (!S.loading) msg.textContent = '完毕'; });
      } catch (e) {}
    });
    const tb = (t, ic, f, id) => { const b = h('div', { class: 'tb', onclick: () => !b.classList.contains('dis') && f() }, [h('img', { src: 'xp/ico/' + ic }), t && h('span', { text: t })]); b._id = id; return b; };
    const bBack = tb('后退', 'back.png', () => go(-1)), bFwd = tb('', 'forward.png', () => go(1)), bStop = tb('', 'stop.png', () => { clearTimeout(timer); clearInterval(ifr._iv); S.loading = false; pg.style.display = 'none'; throb.classList.remove('run'); msg.textContent = '完毕'; upd(); }), bRef = tb('', 'refresh.png', () => { const e = S.hist[S.idx]; e && load(e.r); }), bHome = tb('', 'home.png', () => nav(HOME));
    const bSearch = tb('搜索', '299_32.png', () => nav('http://www.baidu.com/')), bFav = tb('收藏夹', '744_32.png', () => showSide('fav')), bHist = tb('', 'history.png', () => showSide('hist')), bMail = tb('', 'mail.png', () => WM.open('outlook')), bPrint = tb('', '549_32.png', () => WM.alert('打印', '没有安装打印机。', { kind: 'warn' }));
    function upd() { bBack.classList.toggle('dis', S.idx < 1); bFwd.classList.toggle('dis', S.idx >= S.hist.length - 1); bStop.classList.toggle('dis', !S.loading); bFav.classList.toggle('on', S.side === 'fav'); bHist.classList.toggle('on', S.side === 'hist'); }
    const toolbar = h('div', { class: 'tbar' }, [bBack, bFwd, bStop, bRef, bHome, h('div', { class: 'tsep' }), bSearch, bFav, bHist, h('div', { class: 'tsep' }), bMail, bPrint, throb]);
    const mbar = WM.menubar([
      { t: '文件(F)', items: () => [{ t: '新建(N)', sub: [{ t: '窗口(W)', key: 'Ctrl+N', on: () => WM.open('ie', { url: HOME, multi: true }) }] }, { t: '打开(O)...', key: 'Ctrl+O', on: () => { addrIn.focus(); addrIn.select(); } }, { t: '另存为(A)...', dis: true }, '-', { t: '页面设置(U)...', dis: true }, { t: '打印(P)...', key: 'Ctrl+P', on: () => bPrint.click() }, '-', { t: '发送(E)', dis: true }, '-', { t: '关闭(C)', on: () => w.close() }] },
      { t: '编辑(E)', items: () => [{ t: '剪切(T)', dis: true }, { t: '复制(C)', dis: true }, { t: '粘贴(P)', dis: true }, '-', { t: '全选(A)', on: () => { try { ifr.contentDocument.execCommand('selectAll'); } catch (e) {} } }, '-', { t: '查找(在当前页)(F)...', dis: true }] },
      { t: '查看(V)', items: () => [{ t: '工具栏(T)', dis: true }, { t: '状态栏(B)', chk: true }, '-', { t: '转到(G)', sub: [{ t: '后退(B)', dis: S.idx < 1, on: () => go(-1) }, { t: '前进(F)', dis: S.idx >= S.hist.length - 1, on: () => go(1) }, { t: '主页(H)', on: () => nav(HOME) }] }, { t: '停止(P)', key: 'Esc', on: () => bStop.click() }, { t: '刷新(R)', key: 'F5', on: () => bRef.click() }, '-', { t: '源文件(C)', on: () => { const e = S.hist[S.idx]; WM.open('notepad', { name: '源文件', text: '<html>\r\n<!-- 本页为本地演示页面：' + (e ? e.r.src : '') + ' -->\r\n</html>' }); } }, { t: '全屏(F)', key: 'F11', on: () => w.toggleMax() }] },
      { t: '收藏(A)', items: () => [{ t: '添加到收藏夹(A)...', on: () => { const e = S.hist[S.idx]; e && !FAV.some(f => f[1] === e.url) && FAV.push([e.title, e.url]); WM.alert('添加到收藏夹', 'Internet Explorer 将把该页添加到您的收藏夹中。', { kind: 'info' }); } }, { t: '整理收藏夹(O)...', dis: true }, '-'].concat(FAV.map(f => ({ t: f[0], icon: ICO('896_16.png'), on: () => nav(f[1]) }))) },
      { t: '工具(T)', items: () => [{ t: '邮件和新闻(M)', sub: [{ t: '阅读邮件(R)', on: () => WM.open('outlook') }] }, { t: '弹出窗口阻止程序(P)', dis: true }, '-', { t: 'Internet 选项(O)...', on: () => WM.open('inetcpl') }] },
      { t: '帮助(H)', items: () => [{ t: '目录和索引(C)', on: () => WM.open('help') }, '-', { t: '关于 Internet Explorer(A)', on: () => WM.alert('关于 Internet Explorer', 'Microsoft (R) Internet Explorer\n版本: 6.0.2900.5512.xpsp.080413-2111', { kind: 'info' }) }] },
    ]);
    const addr = h('div', { class: 'addr' }, [h('span', { text: '地址(D)', style: 'color:#555' }), h('div', { class: 'box' }, [h('img', { src: ICO('896_16.png'), style: 'width:16px;height:16px' }), addrIn, h('img', { src: 'xp/ico/dropdown.png', style: 'width:15px;height:17px' })]), h('div', { class: 'go', onclick: () => nav(addrIn.value) }, [h('img', { src: 'xp/ico/back.png', style: 'transform:rotate(180deg)' }), h('span', { text: '转到' })]), h('span', { text: '链接 »', style: 'padding:0 6px;color:#555' })]);
    addrIn.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Enter') nav(addrIn.value); }); addrIn.addEventListener('focus', () => setTimeout(() => addrIn.select(), 0));
    const el = h('div', { class: 'ie' }, [mbar, toolbar, addr, h('div', { class: 'body' }, [sideEl, ifr]), h('div', { class: 'status' }, [msg, pg, h('div', { class: 'zone' }, [h('img', { src: 'xp/ico/earth.png' }), h('span', { text: 'Internet' })])])]);
    pg.className = 'pg'; pg.appendChild(pgb); const sb = el.querySelector('.status'); sb.insertBefore(pg, sb.querySelector('.zone'));
    w = WM.create({ id: a.multi ? undefined : 'ie', title: '空白页 - Microsoft Internet Explorer', icon: ICO('896_16.png'), w: 820, h: 560, minW: 420, minH: 260, content: () => el, onclose: () => { clearTimeout(timer); clearInterval(ifr._iv); } });
    nav(a.url || HOME); return w;
  } });
})();
