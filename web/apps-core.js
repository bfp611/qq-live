// 系统对话框与小程序：显示 属性（壁纸可换）、运行、关机/注销、任务管理器、日期和时间、桌面清理向导、创建快捷方式、记事本、计算器、命令提示符、扫雷
(function () {
  if (!window.WM || !WM.ready) return;
  const { root, DW, DH, TB, h, esc, ICO } = WM, S = WM.S, $ = id => document.getElementById(id);
  const reg = WM.register;
  if (!$('shutter')) root.appendChild(h('div', { id: 'shutter' }));
  const field = (label, el, w) => h('div', { style: 'display:flex;align-items:center;margin:6px 0' }, [h('div', { style: `width:${w || 90}px`, text: label }), el]);
  const sel = (opts, val, st) => { const s = h('select', { class: 'xinput', style: st || 'width:160px' }); opts.forEach(o => s.appendChild(h('option', { text: Array.isArray(o) ? o[0] : o, value: Array.isArray(o) ? o[1] : o }))); if (val != null) s.value = val; return s; };

  // ================= 显示 属性 =================
  const WALLS = [['（无）', ''], ['Ascent', 'xp/wall/ascent.jpg'], ['Autumn', 'xp/wall/autumn.jpg'], ['Azul', 'xp/wall/azul.jpg'], ['Bliss', 'xp/ui/bliss.jpg'], ['Crystal', 'xp/wall/crystal.jpg'], ['Follow', 'xp/wall/follow.jpg'], ['Friend', 'xp/wall/friend.jpg'], ['Home', 'xp/wall/home.jpg'],
    ['Moon flower', 'xp/wall/moon_flower.jpg'], ['Peace', 'xp/wall/peace.jpg'], ['Power', 'xp/wall/power.jpg'], ['Purple flower', 'xp/wall/purple_flower.jpg'], ['Radiance', 'xp/wall/radiance.jpg'], ['Red moon desert', 'xp/wall/red_moon_desert.jpg'], ['Ripple', 'xp/wall/ripple.jpg'],
    ['Stonehenge', 'xp/wall/stonehenge.jpg'], ['Tulips', 'xp/wall/tulips.jpg'], ['Vortec space', 'xp/wall/vortec_space.jpg'], ['Wind', 'xp/wall/wind.jpg'], ['Windows XP', 'xp/wall/windows_xp.jpg'], ['Blue hills', 'xp/wall/blue_hills.jpg'], ['Sunset', 'xp/wall/sunset.jpg'], ['Water lilies', 'xp/wall/water_lilies.jpg'], ['Winter', 'xp/wall/winter.jpg']];
  WM.WALLS = WALLS;   // 桌面 Agent 要按名字找壁纸
  const COLORS = [['#245edb', '蓝色'], ['#3a6ea5', '钢蓝'], ['#004e98', '深蓝'], ['#000000', '黑色'], ['#008080', '青绿'], ['#808000', '橄榄'], ['#c0c0c0', '银色'], ['#5a6b3c', '军绿']];
  reg('display', { open: () => {
    const st = { wall: S.wall, mode: S.wallMode, bg: S.bg, dirty: false };
    let dlg;
    const monitor = () => {
      const m = h('div', { style: 'position:relative;width:170px;height:150px;margin:0 auto' });
      m.innerHTML = '<div style="position:absolute;left:0;top:0;width:170px;height:128px;border-radius:8px 8px 4px 4px;background:linear-gradient(#e9e8e0,#b8b6aa);border:1px solid #6e6c60;box-sizing:border-box"></div><div style="position:absolute;left:62px;top:128px;width:46px;height:8px;background:linear-gradient(#cfcdc2,#9d9b8f);border:1px solid #6e6c60;border-top:0;box-sizing:border-box"></div><div style="position:absolute;left:44px;top:136px;width:82px;height:8px;background:linear-gradient(#cfcdc2,#9d9b8f);border:1px solid #6e6c60;border-radius:2px;box-sizing:border-box"></div>';
      const scr = h('div', { id: 'dp-screen', style: 'position:absolute;left:14px;top:12px;width:142px;height:100px;border:1px solid #333;box-sizing:border-box;overflow:hidden' }); m.appendChild(scr);
      const upd = () => {
        scr.style.backgroundColor = st.bg; scr.style.backgroundImage = st.wall ? `url(${st.wall})` : 'none';
        scr.style.backgroundSize = st.mode === 'stretch' ? '100% 100%' : st.mode === 'center' ? '70% auto' : '36px auto';
        scr.style.backgroundRepeat = st.mode === 'tile' ? 'repeat' : 'no-repeat'; scr.style.backgroundPosition = st.mode === 'tile' ? '0 0' : 'center';
      };
      m.upd = upd; upd(); return m;
    };
    let mons = [];
    const mkMon = () => { const m = monitor(); mons.push(m); return m; };
    const pages = {
      '主题': () => h('div', {}, [field('主题(T)：', sel(['Windows XP', 'Windows 经典', '更多联机主题…'], 'Windows XP', 'width:220px'), 60), h('div', { style: 'margin:14px 0 4px;text-align:center' }, [mkMon()]), h('div', { style: 'margin-top:8px;color:#555', text: '主题是由背景加上一组声音、图标以及其它元素组成的，可以让您一键个性化您的计算机。' })]),
      '桌面': () => {
        const box = h('div', {}); box.appendChild(h('div', { style: 'margin:0 0 6px;text-align:center' }, [mkMon()]));
        box.appendChild(h('div', { text: '背景(K)：' }));
        const list = h('div', { style: 'height:112px;overflow:auto;border:1px solid #7f9db9;background:#fff;margin:2px 0 8px;width:236px;float:left;position:relative' });
        WALLS.forEach(([n, f]) => { const it = h('div', { style: 'height:16px;line-height:16px;padding:0 4px;white-space:nowrap', text: n, 'data-f': f }); it.addEventListener('click', () => { st.wall = f; st.dirty = true; mark(); mons.forEach(m => m.upd()); ap.disabled = false; }); list.appendChild(it); });
        const mark = () => [...list.children].forEach(c => { const on = c.dataset.f === st.wall; c.style.background = on ? '#316ac5' : ''; c.style.color = on ? '#fff' : ''; }); mark();
        setTimeout(() => { const on = [...list.children].find(c => c.dataset.f === st.wall); on && (list.scrollTop = Math.max(0, on.offsetTop - 40)); }, 20);
        const right = h('div', { style: 'float:right;width:80px;display:flex;flex-direction:column;gap:6px' }, [h('button', { class: 'xbtn', text: '浏览(B)…', onclick: () => WM.alert('浏览', '演示环境中只能选择内置的 Windows XP 壁纸。', { kind: 'info' }) })]);
        const modeSel = sel([['居中', 'center'], ['平铺', 'tile'], ['拉伸', 'stretch']], st.mode, 'width:84px'); modeSel.addEventListener('change', () => { st.mode = modeSel.value; mons.forEach(m => m.upd()); ap.disabled = false; });
        const colSel = sel(COLORS.map(c => [c[1], c[0]]), st.bg, 'width:84px'); colSel.addEventListener('change', () => { st.bg = colSel.value; mons.forEach(m => m.upd()); ap.disabled = false; });
        box.append(list, right, h('div', { style: 'clear:both' }), h('div', { style: 'display:flex;justify-content:space-between;align-items:center' }, [h('div', {}, [h('div', { text: '位置(P)：' }), modeSel]), h('div', {}, [h('div', { text: '颜色(C)：' }), colSel]), h('button', { class: 'xbtn', style: 'margin-top:14px', text: '自定义桌面(D)…', onclick: () => WM.open('deskitems') })]));
        return box;
      },
      '屏幕保护程序': () => h('div', {}, [h('div', { style: 'margin:0 0 8px;text-align:center' }, [mkMon()]), h('div', { class: 'xgroup' }, [h('legend', { text: '屏幕保护程序(S)' }), h('div', { style: 'display:flex;gap:6px;align-items:center' }, [sel(['(无)', '三维飞行物', '贝塞尔曲线', '空白', 'Windows XP'], '(无)', 'width:130px'), h('button', { class: 'xbtn', text: '设置(T)', style: 'min-width:60px', disabled: true }), h('button', { class: 'xbtn', text: '预览(V)', style: 'min-width:60px', onclick: () => preview() })]), h('div', { style: 'margin-top:8px' }, ['等待(W)：', h('input', { class: 'xinput', value: 10, style: 'width:36px;margin:0 4px' }), '分钟'])])]),
      '外观': () => h('div', {}, [h('div', { style: 'margin:0 0 8px;text-align:center' }, [mkMon()]), field('窗口和按钮(W)：', sel(['Windows XP 样式', 'Windows 经典样式'], 'Windows XP 样式', 'width:170px'), 110), field('色彩方案(C)：', sel(['默认(蓝)', '橄榄绿', '银色'], '默认(蓝)', 'width:170px'), 110), field('字体大小(F)：', sel(['正常', '大字体', '特大字体'], '正常', 'width:170px'), 110)]),
      '设置': () => { const lab = h('div', { text: '1280 x 720 像素', style: 'text-align:center;margin-top:4px' }); const rg = h('input', { type: 'range', min: 0, max: 4, value: 3, style: 'width:140px' }); const R = ['640 x 480', '800 x 600', '1024 x 768', '1280 x 720', '1920 x 1080']; rg.addEventListener('input', () => { lab.textContent = R[rg.value] + ' 像素'; }); return h('div', {}, [h('div', { style: 'margin:0 0 8px;text-align:center' }, [mkMon()]), h('div', { style: 'text-align:center' }, ['显示：', h('b', { text: '(默认监视器) 在 标准 VGA 图形适配器 上' })]), h('div', { style: 'display:flex;justify-content:space-around;margin-top:12px' }, [h('div', {}, [h('div', { text: '屏幕分辨率(S)' }), h('div', { style: 'display:flex;gap:4px' }, [h('span', { text: '低' }), rg, h('span', { text: '高' })]), lab]), h('div', {}, [h('div', { text: '颜色质量(C)' }), sel(['最高(32 位)', '中(16 位)'], '最高(32 位)', 'width:130px')])])]); },
    };
    let ap;
    const preview = () => { const sh = $('shutter'); sh.textContent = ''; sh.style.display = 'flex'; sh.style.cursor = 'none'; const off = () => { sh.style.display = 'none'; sh.style.cursor = ''; document.removeEventListener('pointerdown', off, true); document.removeEventListener('keydown', off, true); }; setTimeout(() => { document.addEventListener('pointerdown', off, true); document.addEventListener('keydown', off, true); }, 200); };
    dlg = WM.tabsDialog({ id: 'display', title: '显示 属性', icon: ICO('300_16.png'), w: 404, h: 470, tab: '桌面', pages,
      apply: () => { S.wall = st.wall; S.wallMode = st.mode; S.bg = st.bg; WM.save(); WM.applyWall(); }, onok: () => { S.wall = st.wall; S.wallMode = st.mode; S.bg = st.bg; WM.save(); WM.applyWall(); } });
    // 应用按钮要在改动后可点
    setTimeout(() => { ap = dlg.client.querySelector('.xpd').lastElementChild.children[2]; if (ap) { ap.disabled = true; ap.onclick = () => { S.wall = st.wall; S.wallMode = st.mode; S.bg = st.bg; WM.save(); WM.applyWall(); ap.disabled = true; }; } }, 10);
    return dlg;
  } });
  reg('deskitems', { open: () => WM.tabsDialog({ id: 'deskitems', title: '桌面项目', icon: ICO('300_16.png'), w: 380, h: 380, pages: { '常规': () => {
    const rows = [['我的文档', 'mydocs'], ['我的电脑', 'mycomputer'], ['回收站', 'recycle']].map(([n, id]) => { const c = h('input', { type: 'checkbox' }); c.checked = !S.hideSys[id]; c.addEventListener('change', () => { S.hideSys[id] = !c.checked; WM.save(); WM.refreshDesktop(); }); return h('div', { style: 'margin:4px 0' }, [c, h('label', { text: ' ' + n })]); });
    return h('div', {}, [h('div', { class: 'xgroup' }, [h('legend', { text: '桌面图标' })].concat(rows)), h('div', { class: 'xgroup', style: 'margin-top:14px' }, [h('legend', { text: '桌面清理' }), h('div', { text: '桌面清理向导会将未使用的桌面项目移到名为“未使用的桌面快捷方式”的文件夹中。' }), h('button', { class: 'xbtn', style: 'margin-top:8px', text: '现在清理桌面(C)', onclick: () => WM.open('cleanup') })])]);
  } } }) });

  // ================= 桌面清理向导 =================
  reg('cleanup', { open: () => WM.dialog({ id: 'cleanup', title: '桌面清理向导', icon: ICO('300_16.png'), w: 480, h: 360, content: w => {
    let p = 0; const box = h('div', { class: 'xpd', style: 'padding:0' }); const body = h('div', { style: 'position:absolute;left:0;right:0;top:0;bottom:46px;background:#fff;display:flex' }), bar = h('div', { style: 'position:absolute;left:0;right:0;bottom:0;height:46px;background:#ece9d8;border-top:1px solid #aca899;display:flex;justify-content:flex-end;align-items:center;gap:6px;padding-right:12px' });
    const side = h('div', { style: 'width:150px;background:linear-gradient(#0a3f9c,#3a73d6);color:#fff;display:flex;align-items:center;justify-content:center' }, [h('img', { src: ICO('300_32.png'), style: 'width:64px;height:64px;filter:drop-shadow(0 0 4px #fff)' })]);
    const pg = h('div', { style: 'flex:1;padding:16px 18px;line-height:20px' }); body.append(side, pg);
    const back = h('button', { class: 'xbtn', text: '< 上一步(B)' }), next = h('button', { class: 'xbtn def', text: '下一步(N) >' }), cancel = h('button', { class: 'xbtn', text: '取消', onclick: () => w.close() }); bar.append(back, next, cancel);
    const unused = ['Counter-Strike 1.6', '热血传奇', '劲舞团', '魔兽争霸III'];
    const show = () => {
      back.disabled = p === 0; next.textContent = p === 2 ? '完成' : '下一步(N) >';
      pg.innerHTML = p === 0 ? '<div style="font:700 16px var(--xpfont);margin-bottom:14px">欢迎使用桌面清理向导</div>此向导可以帮助您清理桌面上长时间未使用的快捷方式，让桌面保持整洁。<br><br>要继续，请单击“下一步”。'
        : p === 1 ? '<div style="font:700 13px var(--xpfont);margin-bottom:8px">快捷方式</div>请选择要移到“未使用的桌面快捷方式”文件夹的项目：<div style="height:140px;overflow:auto;border:1px solid #7f9db9;margin-top:8px;padding:4px">' + unused.map(n => `<div><input type="checkbox" checked> ${n}</div>`).join('') + '</div>'
        : '<div style="font:700 16px var(--xpfont);margin-bottom:14px">正在完成桌面清理向导</div>已完成桌面清理向导。<br>（演示环境：桌面上的快捷方式不会被真正移动。）<br><br>要关闭此向导，请单击“完成”。';
    };
    back.onclick = () => { p--; show(); }; next.onclick = () => { if (p === 2) w.close(); else { p++; show(); } }; show(); box.append(body, bar); return box;
  } }) });
  reg('mkshortcut', { open: () => WM.prompt('创建快捷方式', '请键入项目的位置(T)：', 'C:\\Program Files\\', v => { if (!v) return; const base = v.split(/[\\/]/).filter(Boolean).pop() || '快捷方式'; WM.S.extra.push({ id: 'x' + Date.now().toString(36), kind: 'link', name: base.replace(/\.[a-z]+$/i, '') + ' - 快捷方式', mtime: new Date().toISOString().slice(0, 16).replace('T', ' ') }); WM.save(); WM.refreshDesktop(); }) });

  // ================= 运行 / 注销 / 关机 =================
  reg('run', { open: () => WM.dialog({ id: 'run', title: '运行', icon: ICO('743_16.png'), w: 380, h: 190, content: w => {
    const inp = h('input', { class: 'xinput', style: 'width:270px' }); const go = () => {
      const v = inp.value.trim().toLowerCase().replace(/\.exe$/, ''); w.close();
      const map = { notepad: 'notepad', iexplore: 'ie', cmd: 'cmd', calc: 'calc', explorer: 'explorer', taskmgr: 'taskmgr', winmine: 'minesweeper', control: 'control', qq: 'qq', ttplayer: 'ttplayer', thunder: 'xunlei', kugou: 'kugou', storm: 'baofeng', mspaint: 'paint', sol: 'solitaire', freecell: 'freecell', dxdiag: 'dxdiag', msconfig: 'taskmgr', regedit: 'regedit', 'cs': 'cs', 'war3': 'war3' };
      if (/^(https?:\/\/|www\.)/.test(v)) return WM.open('ie', { url: /^www\./.test(v) ? 'http://' + v : v });
      if (/^[a-z]:/.test(v) || v === '.') return WM.open('explorer', { path: v === '.' ? 'mydocs' : 'c:' });
      if (window.XP && XP.cfg.enabled && XP.cfg.apps === false && ['control', 'paint', 'solitaire', 'freecell'].includes(map[v])) return map[v] === 'control' ? WM.open('explorer', { path: 'control' }) : WM.alert(v, 'Windows 找不到文件“' + v + '”。请确定文件名是否正确后，再试一次。', {});   // [xp] apps = false：新增的软件不存在
      if (map[v]) return WM.open(map[v], map[v] === 'explorer' ? { path: 'mydocs' } : {});
      if (!v) return; WM.alert(v, 'Windows 找不到文件“' + v + '”。请确定文件名是否正确后，再试一次。', {});
    };
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') go(); }); setTimeout(() => inp.focus(), 30);
    return h('div', { class: 'xpd' }, [h('div', { style: 'display:flex;gap:10px;margin-top:2px' }, [h('img', { src: ICO('743_32.png'), style: 'width:32px;height:32px' }), h('div', { text: '请键入程序、文件夹、文档或 Internet 资源的名称，Windows 将为您打开它。' })]), h('div', { style: 'margin:14px 0 0 0;display:flex;align-items:center' }, [h('span', { text: '打开(O)：', style: 'width:60px' }), inp]), h('div', { class: 'msgbtns', style: 'justify-content:flex-end;padding-right:12px' }, [h('button', { class: 'xbtn def', text: '确定', onclick: go }), h('button', { class: 'xbtn', text: '取消', onclick: () => w.close() }), h('button', { class: 'xbtn', text: '浏览(B)…', onclick: () => WM.open('explorer', { path: 'mydocs' }) })])]);
  } }) });
  const pw = (mode, old) => (window.XP && XP.cfg.enabled && XP.cfg.shutdown_screens ? XP.power(mode) : old());   // xp-screens.js 的 XP 关机 / 注销画面（[xp] shutdown_screens 关了就用老的黑屏）
  function blackout(text, ms, sub) {
    const sh = $('shutter'); sh.style.flexDirection = 'column'; sh.innerHTML = '<div>' + text + '</div>' + (sub ? '<div style="font-size:13px;color:#aaa;margin-top:14px">' + sub + '</div>' : ''); sh.style.display = 'flex'; sh.style.opacity = 0; sh.style.transition = 'opacity .5s';
    requestAnimationFrame(() => { sh.style.opacity = 1; });
    setTimeout(() => { sh.style.opacity = 0; setTimeout(() => { sh.style.display = 'none'; sh.style.transition = ''; }, 500); }, ms);
  }
  reg('shutdown', { open: () => {
    root.style.filter = 'grayscale(1) brightness(.75)'; const fin = () => { root.style.filter = ''; };
    return WM.dialog({ id: 'shutdown', title: '关闭 Windows', icon: ICO('310_16.png'), w: 330, h: 190, modal: true, onclose: fin, content: w => {
      const btn = (t, ic, f) => h('div', { style: 'text-align:center;width:80px' }, [h('div', { style: 'width:46px;height:46px;margin:0 auto;border:2px solid transparent;border-radius:5px;display:flex;align-items:center;justify-content:center', onpointerenter: e => e.currentTarget.style.borderColor = '#e0e0e0', onpointerleave: e => e.currentTarget.style.borderColor = 'transparent', onclick: f }, [h('img', { src: ic, style: 'width:32px;height:32px' })]), h('div', { text: t, style: 'color:#fff;margin-top:4px' })]);
      return h('div', { style: 'width:100%;height:100%;background:#1e4fb5;color:#fff;position:relative;font:12px var(--xpfont)' }, [
        h('div', { style: 'height:42px;background:linear-gradient(#003bb3,#2a6fe0);display:flex;align-items:center;padding-left:12px;font:700 20px var(--xpfont);border-bottom:2px solid #ff8c00' }, ['Windows ', h('span', { style: 'font-size:14px;margin-left:6px;font-style:italic', text: 'xp' })]),
        h('div', { style: 'text-align:center;margin:14px 0 6px', text: '关闭计算机' }),
        h('div', { style: 'display:flex;justify-content:center;gap:16px;margin-top:6px' }, [btn('待机(S)', ICO('restore.ico'), () => { w.close(); pw('standby', () => blackout('', 1800)); }), btn('关闭(T)', ICO('310_32.png'), () => { w.close(); pw('shutdown', () => blackout('Windows 正在关机…', 2600, '（演示环境：不会真的关机）')); }), btn('重新启动(R)', ICO('restart.ico'), () => { w.close(); pw('restart', () => blackout('Windows XP', 3000, '正在启动 Windows…')); })]),
        h('div', { style: 'position:absolute;right:10px;bottom:8px' }, [h('button', { class: 'xbtn', text: '取消(C)', onclick: () => w.close() })])]);
    } });
  } });
  reg('logoff', { open: () => WM.dialog({ id: 'logoff', title: '注销 Windows', icon: ICO('546_16.png'), w: 340, h: 170, modal: true, content: w => h('div', { class: 'xpd', style: 'background:#1e4fb5;color:#fff' }, [h('div', { style: 'font:700 14px var(--xpfont);margin:6px 0 14px', text: '注销 Windows' }), h('div', { style: 'display:flex;justify-content:center;gap:24px' }, [['切换用户(S)', '546_32.png', () => { w.close(); pw('logoff', () => blackout('欢迎使用', 1400)); }], ['注销(L)', '310_32.png', () => { w.close(); pw('logoff', () => blackout('正在保存个人设置…', 1800)); }]].map(([t, i, f]) => h('div', { style: 'text-align:center;width:90px', onclick: f }, [h('img', { src: ICO(i), style: 'width:32px;height:32px' }), h('div', { text: t, style: 'margin-top:4px' })]))), h('div', { style: 'position:absolute;right:10px;bottom:8px' }, [h('button', { class: 'xbtn', text: '取消(C)', onclick: () => w.close() })])]) }) });

  // ================= 任务管理器 =================
  reg('taskmgr', { open: () => WM.dialog({ id: 'taskmgr', title: 'Windows 任务管理器', icon: ICO('669_16.png'), w: 420, h: 440, dlg: false, content: w => {
    const list = h('div', { style: 'height:290px;overflow:auto;border:1px solid #7f9db9;background:#fff' }); let selw = null;
    const ref = () => { list.innerHTML = '<div style="display:flex;background:#ece9d8;border-bottom:1px solid #aca899"><div style="width:280px;padding:2px 6px;border-right:1px solid #aca899">任务</div><div style="padding:2px 6px">状态</div></div>'; WM.wins.filter(x => !x.closed && !x.tbHidden && !(x.o.notask && !x.o.tbEl && !x.dialogOnly)).forEach(x => { const r = h('div', { style: 'display:flex;height:18px;line-height:18px;' + (selw === x ? 'background:#316ac5;color:#fff' : ''), onclick: () => { selw = x; ref(); } }, [h('div', { style: 'width:280px;padding:0 6px;display:flex;align-items:center', html: `<img src="${x.icon || ICO('318_16.png')}" style="width:16px;height:16px;margin-right:4px">${esc(x.title)}` }), h('div', { style: 'padding:0 6px', text: '正在运行' })]); list.appendChild(r); }); };
    ref(); const t = setInterval(() => { if (w.closed) clearInterval(t); else ref(); }, 1500);
    const tabs = h('div', { class: 'xtabs' }, ['应用程序', '进程', '性能', '联网', '用户'].map((n, i) => h('div', { class: 'tb' + (i === 0 ? ' on' : ''), text: n })));
    const bars = h('div', { style: 'position:absolute;left:12px;right:12px;bottom:34px;display:flex;justify-content:flex-end;gap:6px' }, [h('button', { class: 'xbtn', text: '结束任务(E)', onclick: () => { selw && selw.close(); ref(); } }), h('button', { class: 'xbtn', text: '切换至(S)', onclick: () => { selw && selw.focus(); } }), h('button', { class: 'xbtn', text: '新任务(N)…', onclick: () => WM.open('run') })]);
    const st = h('div', { class: 'xp-status', style: 'position:absolute;left:0;right:0;bottom:0' }, [h('div', { text: '进程数: ' + (WM.wins.length + 28) }), h('div', { text: 'CPU 使用: 3%' }), h('div', { text: '提交更改: 212M / 1961M', style: 'border:0' })]);
    return h('div', { class: 'xpd', style: 'padding:8px 10px' }, [tabs, h('div', { class: 'xpanel', style: 'position:absolute;left:10px;right:10px;top:34px;bottom:70px;padding:6px' }, [list]), bars, st]);
  } }) });
  reg('taskbarprops', { open: () => WM.tabsDialog({ id: 'tbp', title: '任务栏和「开始」菜单属性', icon: ICO('300_16.png'), w: 400, h: 420, pages: { '任务栏': () => h('div', {}, ['锁定任务栏(L)', '自动隐藏任务栏(U)', '将任务栏保持在其它窗口的前端(P)', '分组相似任务栏按钮(G)', '显示快速启动(Q)', '显示时钟(K)', '隐藏不活动的图标(H)'].map((t, i) => h('div', { style: 'margin:6px 0' }, [h('input', { type: 'checkbox', checked: [0, 2, 3, 4, 5].includes(i) }), h('label', { text: ' ' + t })]))), '「开始」菜单': () => h('div', { text: '「开始」菜单：以 Windows XP 样式显示。' }) } }) });

  // ================= 日期和时间 =================
  reg('datetime', { open: () => WM.tabsDialog({ id: 'datetime', title: '日期和时间 属性', icon: ICO('301_16.png'), w: 420, h: 400, pages: { '日期和时间': () => {
    const now = new Date(); let y = now.getFullYear(), m = now.getMonth();
    const cal = h('div', { style: 'width:190px;border:1px solid #7f9db9;background:#fff;padding:4px' }), time = h('div', { style: 'font:700 22px var(--xpfont);text-align:center;margin-top:30px' });
    const draw = () => { cal.innerHTML = ''; const head = h('div', { style: 'display:flex;gap:4px;margin-bottom:4px' }, [sel(Array.from({ length: 12 }, (_, i) => [(i + 1) + '月', i]), m, 'width:60px'), h('input', { class: 'xinput', type: 'number', value: y, style: 'width:60px' })]); head.children[0].onchange = e => { m = +e.target.value; draw(); }; head.children[1].onchange = e => { y = +e.target.value || y; draw(); }; cal.appendChild(head);
      const g = h('div', { style: 'display:grid;grid-template-columns:repeat(7,1fr);text-align:center;line-height:20px' }); '日一二三四五六'.split('').forEach(d => g.appendChild(h('div', { text: d, style: 'color:#0046d5;border-bottom:1px solid #7f9db9' }))); const f = new Date(y, m, 1).getDay(), n = new Date(y, m + 1, 0).getDate(); for (let i = 0; i < f; i++) g.appendChild(h('div')); for (let d = 1; d <= n; d++) { const c = y === now.getFullYear() && m === now.getMonth() && d === now.getDate(); g.appendChild(h('div', { text: d, style: c ? 'background:#316ac5;color:#fff' : '' })); } cal.appendChild(g); };
    draw(); const tick = () => { const t = new Date(); time.textContent = t.toLocaleTimeString('zh-CN', { hour12: false }); }; tick(); const iv = setInterval(() => { if (!time.isConnected) clearInterval(iv); else tick(); }, 1000);
    return h('div', { style: 'display:flex;gap:16px' }, [h('div', {}, [h('div', { class: 'xgroup', style: 'margin-top:0' }, [h('legend', { text: '日期' }), cal])]), h('div', { style: 'flex:1' }, [h('div', { class: 'xgroup', style: 'margin-top:0;height:110px' }, [h('legend', { text: '时间' }), time])])]);
  }, '时区': () => h('div', { text: '(GMT+08:00) 北京，重庆，香港特别行政区，乌鲁木齐' }), 'Internet 时间': () => h('div', { text: '自动与 Internet 时间服务器同步(A)：time.windows.com' }) } }) });

  // ================= 其它小窗口 =================
  const simple = (id, title, icon, text, w, hh) => reg(id, { open: () => WM.dialog({ id, title, icon: ICO(icon), w, h: hh, content: win => h('div', { class: 'xpd' }, [h('div', { style: 'white-space:pre-wrap;line-height:18px', text }), h('div', { class: 'msgbtns', style: 'justify-content:flex-end;padding-right:12px' }, [h('button', { class: 'xbtn def', text: '确定', onclick: () => win.close() })])]) }) });
  simple('outlook', 'Outlook Express', '887_16.png', '没有找到默认的电子邮件账户。\n\n请使用“Internet 账户向导”添加一个账户。', 360, 170);
  simple('help', '帮助和支持中心', '747_16.png', '帮助和支持中心\n\n— 选择一个帮助主题\n— 要求某人协助\n— 使用工具查看您的计算机信息\n\n（演示环境：帮助内容不可用）', 380, 220);
  simple('inetcpl', 'Internet 属性', '300_16.png', '主页：http://www.hao123.com/\n\nInternet 临时文件、历史记录、Cookie 可在此清理。', 380, 200);
  simple('regedit', '注册表编辑器', '300_16.png', '注册表编辑器已被系统管理员禁用。', 340, 150);
  simple('dxdiag', 'DirectX 诊断工具', '300_16.png', 'DirectX 版本: DirectX 9.0c (4.09.0000.0904)\n显示设备: 标准 VGA 图形适配器\n声音设备: Realtek AC97 Audio', 380, 190);

  // ================= 记事本 =================
  reg('notepad', { open: a => {
    a = a || {}; const key = a.id ? 'np-' + a.id : null; const init = a.text != null ? a.text : (key ? (S.texts[a.id] || '') : '');
    let dirty = false, fname = a.name || '无标题';
    const ta = h('textarea', { spellcheck: false, style: 'position:absolute;inset:0;width:100%;height:100%;resize:none;border:0;outline:0;padding:2px 4px;font:16px/18px "SimSun","宋体","Songti SC",monospace;box-sizing:border-box;background:#fff;color:#000;white-space:pre;overflow:auto' });
    ta.value = init; let w;
    const doSave = () => { if (a.id) { S.texts[a.id] = ta.value; WM.save(); dirty = false; w.setTitle(fname + ' - 记事本'); } else saveAs(); };
    const saveAs = () => WM.prompt('另存为', '文件名(N)：', 'untitled.txt', n => { if (!n) return; const id = 'x' + Date.now().toString(36); S.extra.push({ id, kind: 'text', name: n, mtime: new Date().toISOString().slice(0, 16).replace('T', ' ') }); S.texts[id] = ta.value; a.id = id; fname = n; WM.save(); WM.refreshDesktop(); dirty = false; w.setTitle(fname + ' - 记事本'); });
    const menu = WM.menubar([{ t: '文件(F)', items: () => [{ t: '新建(N)', key: 'Ctrl+N', on: () => { ta.value = ''; } }, { t: '打开(O)...', key: 'Ctrl+O', dis: true }, { t: '保存(S)', key: 'Ctrl+S', on: doSave }, { t: '另存为(A)...', on: saveAs }, '-', { t: '页面设置(U)...', dis: true }, { t: '打印(P)...', key: 'Ctrl+P', dis: true }, '-', { t: '退出(X)', on: () => w.close() }] },
      { t: '编辑(E)', items: () => [{ t: '撤消(U)', key: 'Ctrl+Z', on: () => document.execCommand('undo') }, '-', { t: '剪切(T)', key: 'Ctrl+X', on: () => { ta.focus(); document.execCommand('cut'); } }, { t: '复制(C)', key: 'Ctrl+C', on: () => { ta.focus(); document.execCommand('copy'); } }, { t: '粘贴(P)', key: 'Ctrl+V', dis: true }, { t: '删除(L)', key: 'Del', on: () => document.execCommand('delete') }, '-', { t: '全选(A)', key: 'Ctrl+A', on: () => { ta.focus(); ta.select(); } }, { t: '时间/日期(D)', key: 'F5', on: () => { ta.focus(); document.execCommand('insertText', false, new Date().toLocaleString('zh-CN')); } }] },
      { t: '格式(O)', items: () => [{ t: '自动换行(W)', chk: ta.style.whiteSpace === 'pre-wrap', on: () => { ta.style.whiteSpace = ta.style.whiteSpace === 'pre-wrap' ? 'pre' : 'pre-wrap'; } }, { t: '字体(F)...', dis: true }] },
      { t: '查看(V)', items: () => [{ t: '状态栏(S)', chk: false, dis: true }] }, { t: '帮助(H)', items: () => [{ t: '帮助主题(H)', on: () => WM.open('help') }, '-', { t: '关于记事本(A)', on: () => WM.alert('关于记事本', 'Microsoft (R) Windows (R) 记事本\n版本 5.1 (内部版本号 2600.xpsp.080413-2111: Service Pack 3)', { kind: 'info' }) }] }]);
    ta.addEventListener('input', () => { if (!dirty) { dirty = true; w.setTitle('*' + fname + ' - 记事本'); } });
    ta.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); doSave(); } });
    w = WM.create({ id: key || undefined, title: fname + ' - 记事本', icon: ICO('327_16.png'), w: 560, h: 380, minW: 260, minH: 140,
      onclose: ww => { if (dirty && !ww._confirmed) { WM.confirm('记事本', '文件“' + fname + '”中的文字已改变。\n\n想保存文件吗？', () => { doSave(); ww._confirmed = true; ww.close(); }, () => { ww._confirmed = true; ww.close(); }, ['是(Y)', '否(N)']); return false; } },
      content: () => h('div', { style: 'position:absolute;inset:0;display:flex;flex-direction:column;background:#fff' }, [menu, h('div', { style: 'position:relative;flex:1;border:1px solid #7f9db9;margin:0' }, [ta])]) });
    setTimeout(() => ta.focus(), 50); return w;
  } });

  // ================= 计算器 =================
  reg('calc', { open: () => WM.create({ id: 'calc', title: '计算器', icon: ICO('74_16.png'), w: 262, h: 262, resizable: false, content: () => {
    let cur = '0', acc = null, op = null, fresh = true, mem = 0; const disp = h('div', { style: 'height:24px;margin:6px 8px;background:#fff;border:1px solid #7f9db9;text-align:right;font:16px/22px var(--xpfont);padding:0 4px;overflow:hidden', text: '0' });
    const show = () => { disp.textContent = cur.length > 14 ? (+cur).toExponential(6) : cur; };
    const calc = (a, b, o) => ({ '+': a + b, '-': a - b, '*': a * b, '/': b === 0 ? NaN : a / b }[o]);
    const press = k => {
      if (/^\d$/.test(k)) { cur = fresh || cur === '0' ? k : cur + k; fresh = false; }
      else if (k === '.') { if (fresh) { cur = '0.'; fresh = false; } else if (!cur.includes('.')) cur += '.'; }
      else if ('+-*/'.includes(k) || k === '=') { const v = parseFloat(cur); if (op && !fresh) { acc = calc(acc, v, op); cur = isNaN(acc) ? '无效输入' : String(+acc.toPrecision(12)); } else acc = v; op = k === '=' ? null : k; fresh = true; }
      else if (k === 'C') { cur = '0'; acc = null; op = null; fresh = true; } else if (k === 'CE') { cur = '0'; fresh = true; }
      else if (k === '←') { cur = cur.length > 1 ? cur.slice(0, -1) : '0'; }
      else if (k === '±') { cur = String(-parseFloat(cur)); } else if (k === 'sqrt') { cur = String(+Math.sqrt(parseFloat(cur)).toPrecision(12)); fresh = true; } else if (k === '1/x') { cur = String(+(1 / parseFloat(cur)).toPrecision(12)); fresh = true; } else if (k === '%') { cur = String(parseFloat(cur) * (acc || 0) / 100); }
      else if (k === 'MC') mem = 0; else if (k === 'MR') { cur = String(mem); fresh = true; } else if (k === 'MS') mem = parseFloat(cur); else if (k === 'M+') mem += parseFloat(cur);
      show();
    };
    const rows = [['MC', '7', '8', '9', '/', 'sqrt'], ['MR', '4', '5', '6', '*', '%'], ['MS', '1', '2', '3', '-', '1/x'], ['M+', '0', '±', '.', '+', '=']];
    const grid = h('div', { style: 'display:grid;grid-template-columns:repeat(6,1fr);gap:4px;padding:0 8px' });
    const red = new Set(['/', '*', '-', '+', '=', 'sqrt', '%', '1/x']);
    h('div'); const top = h('div', { style: 'display:flex;gap:4px;padding:0 8px 4px;justify-content:flex-end' }, ['←', 'CE', 'C'].map(k => h('button', { class: 'xbtn', style: 'width:54px;color:#c00;min-width:0', text: k, onclick: () => press(k) })));
    rows.forEach(r => r.forEach(k => grid.appendChild(h('button', { class: 'xbtn', style: `min-width:0;padding:0;height:28px;color:${/^\d|\.|±$/.test(k) ? '#0000d0' : red.has(k) ? '#c00' : '#c00'}`, text: k === 'sqrt' ? '√' : k, onclick: () => press(k) }))));
    const box = h('div', { class: 'xpd', style: 'padding:0' }, [h('div', { class: 'xp-menubar' }, ['编辑(E)', '查看(V)', '帮助(H)'].map(t => h('div', { class: 'mb', text: t }))), disp, top, grid]);
    document.addEventListener('keydown', e => { if (!box.isConnected || !box.closest('.xpw') || box.closest('.xpw').classList.contains('inactive')) return; if (/^[0-9.+\-*/]$/.test(e.key)) press(e.key); else if (e.key === 'Enter') press('='); else if (e.key === 'Backspace') press('←'); else if (e.key === 'Escape') press('C'); });
    return box;
  } }) });

  // ================= 命令提示符 =================
  reg('cmd', { open: () => WM.create({ id: 'cmd', title: '命令提示符', icon: ICO('56_16.png'), w: 640, h: 380, minW: 300, content: () => {
    const out = h('div', { style: 'position:absolute;inset:0;background:#000;color:#c0c0c0;font:16px/18px "SimSun","宋体",monospace;padding:2px 4px;overflow:auto;white-space:pre-wrap;word-break:break-all' });
    let cwd = 'C:\\Documents and Settings\\Administrator';
    const print = t => { out.insertBefore(document.createTextNode(t + '\n'), line); };
    const line = h('span'), input = h('span', { style: 'outline:0' }), caret = h('span', { style: 'background:#c0c0c0;display:inline-block;width:9px;height:16px;vertical-align:-2px;animation:blink 1s steps(2) infinite' });
    const prompt = h('span'); line.append(prompt, input, caret); out.appendChild(line); let buf = '';
    const sync = () => { prompt.textContent = cwd + '>'; input.textContent = buf; out.scrollTop = out.scrollHeight; };
    print('Microsoft Windows XP [版本 5.1.2600]\n(C) 版权所有 1985-2001 Microsoft Corp.\n'); sync();
    const FS = { 'C:\\': ['<DIR>          Documents and Settings', '<DIR>          Program Files', '<DIR>          WINDOWS', '<DIR>          Games', '       211 AUTOEXEC.BAT', '         0 CONFIG.SYS'] };
    const run = c => { const [cmd, ...rest] = c.trim().split(/\s+/); const a = rest.join(' '); switch ((cmd || '').toLowerCase()) {
      case '': break; case 'ver': print('\nMicrosoft Windows XP [版本 5.1.2600]\n'); break; case 'cls': [...out.childNodes].forEach(n => n !== line && n.remove()); break;
      case 'echo': print(a); break; case 'date': print('当前日期: ' + new Date().toLocaleDateString('zh-CN')); break; case 'time': print('当前时间: ' + new Date().toLocaleTimeString('zh-CN')); break;
      case 'dir': print(' 驱动器 C 中的卷是 WINXP\n 卷的序列号是 5A3C-91E2\n\n ' + cwd + ' 的目录\n'); (FS[cwd] || FS['C:\\']).forEach(l => print('2007-06-30  08:00    ' + l)); print('               2 个文件            211 字节\n'); break;
      case 'cd': if (!a) print(cwd); else if (a === '..') cwd = cwd.includes('\\') && cwd.length > 3 ? (cwd.replace(/\\[^\\]*$/, '') || 'C:\\') : cwd; else if (a === '\\') cwd = 'C:\\'; else cwd = (cwd.endsWith('\\') ? cwd : cwd + '\\') + a; break;
      case 'ipconfig': print('\nWindows IP Configuration\n\nEthernet adapter 本地连接:\n\n        Connection-specific DNS Suffix  . :\n        IP Address. . . . . . . . . . . . : 192.168.1.101\n        Subnet Mask . . . . . . . . . . . : 255.255.255.0\n        Default Gateway . . . . . . . . . : 192.168.1.1\n'); break;
      case 'ping': print('\nPinging ' + (a || 'localhost') + ' with 32 bytes of data:\n\nReply from ' + (a || '127.0.0.1') + ': bytes=32 time=12ms TTL=56\nReply from ' + (a || '127.0.0.1') + ': bytes=32 time=11ms TTL=56\nReply from ' + (a || '127.0.0.1') + ': bytes=32 time=13ms TTL=56\n'); break;
      case 'help': print('有关某个命令的详细信息，请键入 HELP 命令名\nCD  CLS  DATE  DIR  ECHO  EXIT  IPCONFIG  PING  TIME  VER\n'); break; case 'exit': WM.byId.cmd && WM.byId.cmd.close(); break; case 'notepad': WM.open('notepad'); break; case 'calc': WM.open('calc'); break;
      default: print("'" + cmd + "' 不是内部或外部命令，也不是可运行的程序\n或批处理文件。\n"); } };
    out.tabIndex = 0; out.style.outline = 'none';
    out.addEventListener('keydown', e => { if (e.key === 'Enter') { print(cwd + '>' + buf); const c = buf; buf = ''; run(c); } else if (e.key === 'Backspace') buf = buf.slice(0, -1); else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) buf += e.key; else return; e.preventDefault(); sync(); });
    out.addEventListener('pointerdown', () => setTimeout(() => out.focus(), 0)); setTimeout(() => out.focus(), 80);
    return out;
  } }) });
  const st = document.createElement('style'); st.textContent = '@keyframes blink{0%{opacity:1}50%{opacity:0}}'; document.head.appendChild(st);
})();
