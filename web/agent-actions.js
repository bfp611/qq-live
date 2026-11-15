// ?desk=xp：桌面 Agent 的全部动作（依赖 agent.js 的光标原语）。每个动作都是“像人一样”操作：
// 光标移到目标 → 点按钮 / 拖标题栏 / 右键菜单 / 开始菜单 / 键盘打字；做不到（目标被盖住等）才退而直接调窗口 API，并在返回的 note 里说明。
(function () {
  const AG = window.AG; if (!AG || !window.WM) return;
  const { root, DW, DH, TB, h } = WM, $ = id => document.getElementById(id);
  const { move, click, dblclick, rclick, drag, press, typeText, sleep, clickEl, hoverEl, waitFor, livePoint, designPt, shown, elAt, drect, winVisible, findWins, targetRects, coverOf, key } = AG;
  const ACT = AG.ACT, S = WM.S, USE_H = DH - TB;
  const txt = el => (el.textContent || '').trim();
  const fail = m => { throw new Error(m); };

  // ================= 菜单 / 空白处 =================
  const menuEls = () => [...root.querySelectorAll('.xpm')];
  function menuItem(t) { for (const m of menuEls().reverse()) for (const it of m.children) if (it.classList.contains('mi') && it.textContent.includes(t)) return it; return null; }
  // 先水平“走进”这一层菜单（别斜着穿过开始菜单的别的项，否则“所有程序”飞出菜单会被关掉）
  async function enterMenu(it) {
    const m = it.parentElement; if (!m || !m.classList.contains('xpm')) return;
    if (AG.hover && m.contains(AG.hover)) return;
    const mr = drect(m); await move(mr.x + 12, Math.max(mr.y + 8, Math.min(mr.y + mr.h - 8, AG.pos.y)), { speed: 1400 });
  }
  async function menuPath(path) {
    for (let i = 0; i < path.length; i++) {
      const it = await waitFor(() => menuItem(path[i]), 2000); if (!it) fail('菜单里找不到：' + path[i]);
      await enterMenu(it);
      if (i < path.length - 1) {
        const n0 = menuEls().length; await hoverEl(it); await waitFor(() => menuEls().length > n0, 1200, 30); await sleep(120);
        const r = drect(it), sub = menuEls().pop(); if (sub) { const sr = drect(sub); await move(Math.min(r.x + r.w - 6, sr.x + 8), r.y + r.h / 2, { speed: 1500 }); }
      } else {
        const r = drect(it), top = elAt(r.x + r.w / 2, r.y + r.h / 2);   // 安全：目标项被别的菜单盖住就不点，免得点错
        if (top && top !== it && !it.contains(top)) fail('菜单项被遮挡：' + path[i]);
        await clickEl(it);
      }
    }
  }
  function emptyDeskPoint() {
    const pts = []; for (let x = 330; x < DW - 30; x += 50) for (let y = 40; y < DH - TB - 30; y += 50) pts.push([x, y]);
    pts.sort((a, b) => Math.hypot(a[0] - AG.pos.x, a[1] - AG.pos.y) - Math.hypot(b[0] - AG.pos.x, b[1] - AG.pos.y));
    for (const [x, y] of pts) { const e = elAt(x, y); if (e && (e === root || e.id === 'icons')) return { x, y }; }
    return null;
  }
  function emptyTaskbarPoint() {
    const y = DH - TB / 2;
    for (let x = 700; x > 260; x -= 40) { const e = elAt(x, y); if (e && (e.id === 'taskbar' || e.id === 'taskbtns' || (e.classList && e.classList.contains('left')))) return { x, y }; }
    for (let x = 700; x < DW - 200; x += 40) { const e = elAt(x, y); if (e && (e.id === 'taskbar' || e.id === 'taskbtns' || (e.classList && e.classList.contains('left')))) return { x, y }; }
    const clk = $('clk'); if (clk && shown(clk)) { const r = drect(clk); return { x: r.x + 6, y: r.y + r.h / 2 }; }   // 任务栏被按钮占满：右键托盘区同样弹出任务栏菜单
    return null;
  }
  async function deskMenu(path) { const p = emptyDeskPoint(); if (!p) return false; await rclick(p.x, p.y); await menuPath(path); return true; }
  async function taskbarMenu(path) { const p = emptyTaskbarPoint(); if (!p) return false; await rclick(p.x, p.y); await menuPath(path); return true; }
  async function dialogButton(titleRe, label, ms) {
    const w = await waitFor(() => WM.wins.find(x => x.dialogOnly && !x.closed && titleRe.test(x.title + ' ' + txt(x.el))), ms || 1500); if (!w) return false;
    await sleep(120); const b = [...w.el.querySelectorAll('button')].find(x => txt(x).startsWith(label)); if (!b) return false;
    await clickEl(b); return true;
  }

  // ================= 窗口辅助 =================
  const SYS_APPS = new Set(['qqchat', 'ttplayer']);
  const labelOf = w => (w.title || w.id);
  function btnEl(w, k) { // k: mn | mx | cl
    if (w.o && w.o.adopted) { const s = w.o.btns && w.o.btns[{ mn: 'min', mx: 'max', cl: 'close' }[k]]; return s ? w.el.querySelector(s) : null; }
    return w.el.querySelector('.xpw-btns .xb.' + (k === 'mx' ? 'mx,.xpw-btns .xb.rs' : k));
  }
  function grabPoint(w, side) { // side: 'left' | 'right' | undefined（中间）：往左拖抓右端、往右拖抓左端，光标才够得着
    const R = drect(w.el), left = side === 'left', right = side === 'right';
    if (!(w.o && w.o.adopted)) {
      const bar = w.el.querySelector('.xpw-bar'); if (!bar) return null; const r = drect(bar);
      const fs = []; for (let f = 0.06; f <= 0.9; f += 0.04) fs.push(f);
      if (right) fs.reverse(); else if (!left) fs.sort((a, b) => Math.abs(a - 0.4) - Math.abs(b - 0.4));
      for (const fx of fs) { const x = r.x + r.w * fx, y = r.y + r.h / 2; if (x < r.x + 26 || x < 3 || x > DW - 3) continue; const e = elAt(x, y); if (e && w.el.contains(e) && !e.closest('.xb') && (bar === e || bar.contains(e))) return { x, y }; }
      return null;
    }
    const xs = []; for (let x = R.x + 30; x < R.x + R.w - 30; x += 10) xs.push(x);
    if (right) xs.reverse(); else if (!left) xs.sort((a, b) => Math.abs(a - (R.x + R.w * .4)) - Math.abs(b - (R.x + R.w * .4)));
    for (let y = R.y + 4; y < R.y + 40; y += 6) for (const x of xs) {
      if (x < 3 || x > DW - 3) continue; const e = elAt(x, y); if (!e || !w.el.contains(e)) continue; const c = AG.client(x, y);
      let ok = false; try { ok = w.o.handle({ target: e, clientX: c.x, clientY: c.y, button: 0 }); } catch (err) {}
      if (ok) return { x, y };
    }
    return null;
  }
  async function clickTb(w) {
    if (w.tb && shown(w.tb)) return clickEl(w.tb);
    const g = grabPoint(w); if (g) return click(g.x, g.y); fail('没有任务栏按钮也找不到标题栏');
  }
  async function raise(w) {
    if (w.closed) fail('窗口已关闭');
    if (w.state === 'min') { await clickTb(w); await waitFor(() => w.state !== 'min', 800); return; }
    if (WM.active === w && winVisible(w)) { const g = grabPoint(w); if (g) return; }
    const g = grabPoint(w);
    if (g) { await click(g.x, g.y); return; }
    if (WM.active !== w && w.tb && shown(w.tb)) { await clickTb(w); return; }
    w.focus();
  }
  const wins1 = t => { const w = findWins(t).filter(x => !x.dialogOnly || t === 'all' || true)[0]; return w; };
  const need = (t, label) => { const w = wins1(t); if (!w) fail((label || '窗口') + '没找到：' + t); return w; };
  const rectOf = w => AG.rectOfWin(w);

  async function winMin(w) {
    if (w.state === 'min') return '已经最小化了';
    await raise(w); const b = btnEl(w, 'mn');
    if (b && livePoint(b)) await clickEl(b); else { const g = grabPoint(w); if (g) await move(g.x, g.y); w.min(); return '没有最小化按钮，直接最小化'; }
    return '';
  }
  async function dismissSave(w) {
    await sleep(260);
    if (!w.closed) { const d = WM.wins.find(x => x.dialogOnly && !x.closed && /记事本|保存|确认/.test(x.title + txt(x.el))); if (d) { const b = [...d.el.querySelectorAll('button')].find(x => /^否/.test(txt(x))); if (b) { await clickEl(b); await sleep(200); } } }
  }
  async function winClose(w) {
    await raise(w); const b = btnEl(w, 'cl');
    let note = '';
    if (b && livePoint(b)) await clickEl(b); else { const g = grabPoint(w); if (g) await move(g.x, g.y); w.close(); note = '没有可点的关闭按钮，直接关闭'; }
    await dismissSave(w);
    return note;
  }
  function undoClose(w) {
    const app = AG.appOf(w), id = w.id, adopted = w.o && w.o.adopted, rect = Object.assign({}, w.rect), args = w.o && w.o._args;
    AG.pushUndo('关闭 ' + labelOf(w), async () => {
      if (adopted) { if (w.closed) w.reopen(); return; }
      if (app && WM.apps[app]) { const nw = WM.open(app, args); if (nw && nw.rect && !nw.dialogOnly) { nw.rect = rect; nw._apply(); } }
    });
  }

  ACT.close_window = async a => {
    const ws = findWins(a.target); if (!ws.length) fail('没有这个窗口：' + a.target);
    const w = ws[0]; undoClose(w); const n = await winClose(w); return n || '已关闭 ' + labelOf(w);
  };
  ACT.minimize_window = async a => {
    const w = need(a.target); const was = w.state; const n = await winMin(w);
    if (was !== 'min') AG.pushUndo('最小化 ' + labelOf(w), async () => { if (w.state === 'min') await clickTb(w).catch(() => w.restore()); });
    return n || '已最小化 ' + labelOf(w);
  };
  ACT.maximize_window = async a => {
    const w = need(a.target); if (w.state === 'max') return '已经是最大化';
    if (w.state === 'min') await raise(w);
    const b = btnEl(w, 'mx'); if (!b || (w.o && (w.o.resizable === false || w.nomax)) || b.classList.contains('dis')) fail(labelOf(w) + ' 不能最大化');
    const prev = Object.assign({}, w.rect); await raise(w); await clickEl(b);
    AG.pushUndo('最大化 ' + labelOf(w), async () => { if (w.state === 'max') { const bb = btnEl(w, 'mx'); if (bb && livePoint(bb)) await clickEl(bb); else w.restore(); } });
    return '已最大化 ' + labelOf(w);
  };
  ACT.restore_window = async a => {
    const w = need(a.target);
    if (w.state === 'min') { await clickTb(w); return '已从任务栏恢复'; }
    if (w.state === 'max') { const b = btnEl(w, 'mx'); if (b && livePoint(b)) { await raise(w); await clickEl(b); } else w.restore(); return '已还原'; }
    await raise(w); return '本来就是正常大小，已切到前面';
  };
  ACT.focus_window = async a => { const w = need(a.target); await raise(w); return '已切换到 ' + labelOf(w); };

  const POS = (to, w, usable) => {
    const r = w.rect, W = r.w, Hh = r.h, m = { left: [0, null], right: [DW - W, null], top: [null, 0], bottom: [null, usable - Hh], center: [(DW - W) / 2, (usable - Hh) / 2],
      topleft: [0, 0], topright: [DW - W, 0], bottomleft: [0, usable - Hh], bottomright: [DW - W, usable - Hh] }[to];
    return m ? { x: m[0] == null ? r.x : m[0], y: m[1] == null ? r.y : m[1] } : null;
  };
  const clampPos = (w, x, y) => ({ x: Math.round(Math.max(-w.rect.w + 100, Math.min(DW - 70, x))), y: Math.round(Math.max(0, Math.min(USE_H - 26, y))) });
  async function dragWindowTo(w, nx, ny) {
    if (w.state === 'max') { const b = btnEl(w, 'mx'); if (b && livePoint(b)) await clickEl(b); else w.restore(); await sleep(150); }
    await raise(w);
    const t = clampPos(w, nx, ny), r0 = Object.assign({}, w.rect);
    if (Math.abs(t.x - r0.x) < 4 && Math.abs(t.y - r0.y) < 4) return 'noop';
    let how = 'drag';
    for (let k = 0; k < 4; k++) {            // 光标出不了屏幕：一次拖不到位就松手再抓一次
      const dx = t.x - w.rect.x, dy = t.y - w.rect.y; if (Math.abs(dx) < 4 && Math.abs(dy) < 4) break;
      const g = grabPoint(w, dx < 0 ? 'right' : 'left'); if (!g) { how = 'direct'; break; }
      const ex = Math.max(6, Math.min(DW - 6, g.x + dx)), ey = Math.max(6, Math.min(DH - 6, g.y + dy)), before = { x: w.rect.x, y: w.rect.y };
      await drag(g.x, g.y, ex, ey);
      if (Math.hypot(w.rect.x - before.x, w.rect.y - before.y) < 3) { how = 'direct'; break; }
    }
    if (Math.abs(w.rect.x - t.x) > 6 || Math.abs(w.rect.y - t.y) > 6) { w.rect.x = t.x; w.rect.y = t.y; w._apply(); if (how === 'drag') how = 'direct'; }
    AG.pushUndo('移动 ' + labelOf(w), async () => { w.rect.x = r0.x; w.rect.y = r0.y; w._apply(); });
    return how;
  }
  ACT.move_window = async a => {
    const w = need(a.target); if (a.to === 'away') return ACT.move_away({ target: w.id });
    let p;
    if (a.x != null && a.y != null) p = { x: a.x, y: a.y };
    else { const m = /^(-?\d+)\s*,\s*(-?\d+)$/.exec(a.to || ''); p = m ? { x: +m[1], y: +m[2] } : POS((a.to || 'center').toLowerCase(), w, USE_H); }
    if (!p) fail('不认识的位置：' + a.to);
    const how = await dragWindowTo(w, p.x, p.y);
    return how === 'noop' ? '已经在那里了' : how === 'direct' ? '标题栏被盖住，直接移动' : '已拖到 ' + (a.to || (p.x + ',' + p.y));
  };

  // ---- 挪开挡路的窗口 ----
  function bestSpot(w, T, ww0, hh0) {
    const ww = ww0 || w.rect.w, hh = hh0 || w.rect.h; let best = null;
    const xs = [], ys = [];
    for (let x = -ww + 150; x <= DW - 150; x += 40) xs.push(x); for (let y = 0; y <= USE_H - 30; y += 30) ys.push(y);
    for (const t of T) { if (t.id === w.id) continue; xs.push(t.r.x - ww - 2, t.r.x + t.r.w + 2); ys.push(t.r.y - hh - 2, t.r.y + t.r.h + 2); }   // 贴着群聊 / 播放器 / 歌词的边放，不压它们
    xs.push(0, DW - ww); ys.push(Math.max(0, USE_H - hh));
    for (const x of xs) for (const y of ys) {
      if (x < -ww + 150 || x > DW - 150 || y < 0 || y > USE_H - 30) continue;
      const r = { x, y, w: ww, h: hh }; let ov = 0;
      for (const t of T) { if (t.id === w.id) continue; const area = t.r.w * t.r.h; if (area > 0) ov += Math.max(0, Math.min(r.x + r.w, t.r.x + t.r.w) - Math.max(r.x, t.r.x)) * Math.max(0, Math.min(r.y + r.h, t.r.y + t.r.h) - Math.max(r.y, t.r.y)) / area; }
      const vis = Math.max(0, Math.min(x + ww, DW) - Math.max(x, 0)) * Math.max(0, Math.min(y + hh, USE_H) - Math.max(y, 0)) / (ww * hh);
      const score = ov * 5000 + (1 - vis) * 400 + Math.hypot(x - w.rect.x, y - w.rect.y) * 0.3;
      if (!best || score < best.score) best = { x, y, ov, score, vis };
    }
    return best;
  }
  ACT.move_away = async a => {
    const done = [];
    for (let round = 0; round < 3; round++) {
      let w = a.target && round === 0 ? need(a.target) : findWins('blocking')[0];
      if (!w) break;
      const T = targetRects();
      if (w.state === 'max') { await winMin(w); done.push('最小化 ' + labelOf(w)); AG.pushUndo('最小化 ' + labelOf(w), async () => { if (w.state === 'min') await clickTb(w).catch(() => w.restore()); }); continue; }
      const best = bestSpot(w, T);
      if (!best || best.ov > 0.3) { await winMin(w); done.push('太大挪不开，最小化 ' + labelOf(w)); AG.pushUndo('最小化 ' + labelOf(w), async () => { if (w.state === 'min') await clickTb(w).catch(() => w.restore()); }); continue; }
      const how = await dragWindowTo(w, best.x, best.y); done.push('挪开 ' + labelOf(w) + (how === 'direct' ? '（直接）' : ''));
      if (a.target) break;
    }
    if (!done.length) return '没有窗口挡着';
    return done.join('；');
  };
  ACT.resize_window = async a => {
    const w = need(a.target); if (w.o && (w.o.resizable === false || w.nomax)) fail(labelOf(w) + ' 不能调整大小');
    if (w.state !== 'normal') { const b = btnEl(w, 'mx'); if (w.state === 'max' && b) await clickEl(b); else await raise(w); }
    const P = { small: [480, 320], medium: [640, 440], large: [860, 560] }; const sz = a.size ? P[a.size] : [a.w, a.h];
    if (!sz || !sz[0]) fail('没给大小');
    const nw = Math.max(w.o.minW || 220, Math.min(DW, sz[0])), nh = Math.max(w.o.minH || 120, Math.min(USE_H, sz[1])), r0 = Object.assign({}, w.rect);
    await raise(w);
    const hd = w.el.querySelector('.rz-se'); const dx = nw - w.rect.w, dy = nh - w.rect.h;
    if (hd && livePoint(hd)) { const p = livePoint(hd); await drag(p.x, p.y, p.x + dx, p.y + dy); }
    else { w.rect.w = nw; w.rect.h = nh; w._apply(); }
    AG.pushUndo('调整大小 ' + labelOf(w), async () => { w.rect = r0; w._apply(); });
    return '大小 ' + Math.round(w.rect.w) + '×' + Math.round(w.rect.h);
  };
  ACT.show_desktop = async () => {
    const before = WM.visible().length;
    if (!(await taskbarMenu(['显示桌面(S)']))) { const q = $('quick'); await sleep(200); WM.showDesktop(); return '任务栏没有空位，直接显示桌面'; }
    AG.pushUndo('显示桌面', async () => { WM.showDesktop(); }); return before + ' 个窗口收起';
  };
  ACT.close_all = async () => {
    AG.fast = true; const ws = findWins('all').slice(0, 8), n = [];
    for (const w of ws) { try { undoClose(w); await winClose(w); n.push(labelOf(w)); } catch (e) { /* 继续 */ } }
    return n.length ? '关闭了 ' + n.join('、') : '没有可关的窗口';
  };
  ACT.tile = async a => {
    const label = { cascade: '层叠窗口', horizontal: '横向平铺窗口', vertical: '纵向平铺窗口' }[a.mode || 'cascade'];
    const snap = WM.wins.filter(w => !w.closed && w.state !== 'min').map(w => [w, Object.assign({}, w.rect), w.state]);
    if (!(await taskbarMenu([label]))) fail('任务栏上没有空位可以右键');
    AG.pushUndo('排列窗口', async () => { snap.forEach(([w, r, st]) => { if (!w.closed) { w.state = st === 'max' ? 'max' : 'normal'; w.rect = r; w._apply(); } }); });
    return label;
  };

  // ================= 开始菜单 / 打开应用 =================
  const sm = () => $('startmenu');
  const startShown = () => sm().classList.contains('show');
  async function openStart() { if (startShown()) return; await clickEl($('start')); await waitFor(startShown, 1200); await sleep(100); }
  async function closeStart() { if (!startShown()) return; WM.closeMenus(); await clickEl($('start')); await waitFor(() => !startShown(), 800); }
  async function startItem(t) { await openStart(); const it = [...sm().querySelectorAll('.it:not(.allp)')].find(e => e.textContent.includes(t)); if (!it) fail('开始菜单里没有：' + t);
    if (it.parentElement && it.parentElement.classList.contains('r')) { const ft = sm().querySelector('footer') || sm(), fr = drect(ft), cr = drect(it.parentElement); await move(cr.x + cr.w / 2, fr.y + fr.h / 2, { speed: 1400 }); }   // 右列的项：先走“页脚”再上去，别从“所有程序”上经过（它的飞出菜单会盖住右列）
    await clickEl(it); }
  async function startFlyout(path) {
    await openStart(); const ap = sm().querySelector('.it.allp'); if (!ap) fail('没有“所有程序”');
    await hoverEl(ap); await waitFor(() => $('allprogs'), 1200); await sleep(150);
    await menuPath(path);
  }
  const ICON_APPS = new Set(['mycomputer', 'mydocs', 'recycle', 'ie', 'ttplayer', 'baofeng', 'kugou', 'xunlei', 'qq', 'qqgame', 'cs', 'vc', 'war3', 'ra2', 'mir2', 'audition']);
  const START_L = { ie: 'Internet', outlook: '电子邮件', qq: '腾讯QQ', ttplayer: '千千静听', baofeng: '暴风影音', xunlei: '迅雷', notepad: '记事本', minesweeper: '扫雷' };
  const START_R = { mydocs: '我的文档', mypics: '我的图片', mymusic: '我的音乐', mycomputer: '我的电脑', control: '控制面板', help: '帮助和支持', run: '运行(R)' };
  const ALLP = { rank: ['QQ积分排行榜'], vote: ['投票'], qzone: ['QQ空间'], qqpet: ['QQ宠物'], qqshow: ['QQ秀商城'], qqfiles: ['群共享'], calc: ['附件', '计算器'], cmd: ['附件', '命令提示符'], explorer: ['附件', 'Windows 资源管理器'], paint: ['附件', '画图'], solitaire: ['游戏', '纸牌'], freecell: ['游戏', '空当接龙'] };
  const iconEl = id => root.querySelector('#icons .dicon[data-id="' + id + '"]');
  const appWin = app => findWins(app).find(w => !w.dialogOnly) || (['display', 'taskmgr', 'datetime', 'run', 'help', 'sndcpl', 'mousecpl'].includes(app) ? findWins(app)[0] : null);
  async function openApp(app, a) {
    a = a || {};
    if (app === 'qqchat') {
      const q = WM.byId.qqchat; if (!q) fail('没有群聊窗口');
      if (q.closed) { const p = emptyTaskbarPoint() || { x: 600, y: DH - 14 }; await move(p.x, p.y); q.reopen(); await sleep(250); return q; }
      await raise(q); return q;
    }
    const ex = appWin(app); if (ex && !a.fresh) { await raise(ex); return ex; }
    const before = new Set(WM.wins); let route = '';
    const fin = () => appWin(app) || WM.wins.find(w => !before.has(w) && !w.dialogOnly);
    const ic = ICON_APPS.has(app) ? iconEl(app) : null;
    if (ic && shown(ic) && livePoint(ic, .5, .4)) { route = '图标'; const p = livePoint(ic, .5, .4); await dblclick(p.x, p.y); }
    else if (START_L[app]) { route = '开始菜单'; await startItem(START_L[app]); }
    else if (START_R[app]) { route = '开始菜单'; await startItem(START_R[app]); }
    else if (ALLP[app]) { route = '所有程序'; await startFlyout(ALLP[app]); }
    else if (app === 'sndcpl' || app === 'mousecpl') { route = '控制面板'; await ACT.control_open({ item: app === 'sndcpl' ? '声音' : '鼠标', openOnly: true }); }
    else if (app === 'display') { route = '桌面右键'; if (!(await deskMenu(['属性(R)']))) { WM.open('display'); route = '直接'; } }
    else if (app === 'taskmgr') { route = '任务栏右键'; if (!(await taskbarMenu(['任务管理器(K)']))) { WM.open('taskmgr'); route = '直接'; } }
    else if (app === 'datetime') { route = '双击时钟'; await dblclick(...Object.values(designPt($('clk')))); }
    else { route = '直接'; await openStartMove(); WM.open(app, a.path ? { path: a.path } : a.url ? { url: a.url } : undefined); }
    let w = await waitFor(fin, 3000);
    if (!w && route !== '直接') { WM.open(app, a.path ? { path: a.path } : undefined); w = await waitFor(fin, 1500); route += '→直接'; }
    if (startShown()) { await press('Escape'); await waitFor(() => !startShown(), 600); }
    if (!w) fail('没能打开 ' + app);
    if (!w.app && !w.dialogOnly) w.app = app;
    await sleep(160);
    w._route = route; if (w.o) w.o._args = a.path ? { path: a.path } : undefined;
    return w;
  }
  async function openStartMove() { const b = $('start'); if (b) await hoverEl(b); }
  ACT.open_app = async a => {
    if (a.app === 'ie' && a.url) { const w = await openApp('ie'); return ACT.browse({ url: a.url }); }
    const w = await openApp(a.app, a); if (a.path && a.app === 'explorer') { /* 路径由 app 参数决定 */ }
    return (w._route ? '通过' + w._route + '打开 ' : '已打开 ') + labelOf(w);
  };
  ACT.start_menu = async a => {
    const st = a.state || (startShown() ? 'close' : 'open');
    if (st === 'open') { await openStart(); return '开始菜单已打开'; } await closeStart(); return '开始菜单已关闭';
  };

  // ================= 桌面 =================
  const WALLS = () => WM.WALLS || [];
  async function ensureDisplay() {
    let w = WM.byId.display && !WM.byId.display.closed ? WM.byId.display : null;
    if (!w) { const ok = await deskMenu(['属性(R)']); if (!ok) WM.open('display'); w = await waitFor(() => WM.byId.display && !WM.byId.display.closed && WM.byId.display, 2000); }
    if (!w) fail('没能打开显示属性');
    const tab = [...w.el.querySelectorAll('.xtabs .tb')].find(t => txt(t) === '桌面'); if (tab && !tab.classList.contains('on')) await clickEl(tab);
    return w;
  }
  ACT.change_wallpaper = async a => {
    const list = WALLS(); if (!list.length) fail('页面没有壁纸列表');
    const cur = list.findIndex(x => x[1] === S.wall); let want = (a.name || 'next').trim(), pick;
    const low = want.toLowerCase().replace(/\s+/g, '');
    if (low === 'next' || low === '下一张' || low === '换一张') pick = list[(cur + 1) % list.length];
    else if (low === 'random' || low === '随机') { const c = list.filter(x => x[1] && x[1] !== S.wall); pick = c[Math.floor(Math.random() * c.length)]; }
    else pick = list.find(x => x[0] === want) || list.find(x => x[0].toLowerCase().replace(/\s+/g, '') === low) || list.find(x => x[0].toLowerCase().replace(/\s+/g, '').includes(low));
    if (!pick) fail('没有这张壁纸：' + want);
    if (pick[1] === S.wall) return '已经是 ' + pick[0];
    const prev = { wall: S.wall, mode: S.wallMode, bg: S.bg };
    const w = await ensureDisplay(); await sleep(150);
    const lst = [...w.el.querySelectorAll('[data-f]')], item = lst.find(e => e.dataset.f === pick[1]); if (!item) fail('对话框里没有 ' + pick[0]);
    const box = item.parentElement; box.scrollTop = Math.max(0, item.offsetTop - 40); await sleep(80);
    await clickEl(item); await sleep(260);
    const ok = [...w.el.querySelectorAll('button')].find(b => txt(b) === '确定'); if (!ok) fail('找不到确定按钮');
    await clickEl(ok); await waitFor(() => w.closed, 1500); await sleep(120);
    AG.pushUndo('换壁纸', async () => { S.wall = prev.wall; S.wallMode = prev.mode; S.bg = prev.bg; WM.save(); WM.applyWall(); });
    return '壁纸换成 ' + pick[0];
  };
  ACT.refresh_desktop = async () => { if (!(await deskMenu(['刷新(E)']))) { WM.refreshDesktop(); return '桌面没有空位，直接刷新'; } await sleep(350); return '已刷新'; };
  ACT.arrange_icons = async a => {
    const L = { name: '名称(N)', size: '大小(S)', type: '类型(T)', time: '修改时间(M)', group: '按组排列(G)', auto: '自动排列(A)' }[a.by || 'name'];
    const prev = { pos: JSON.parse(JSON.stringify(S.pos)), sort: S.sort, auto: S.auto };
    if (!(await deskMenu(['排列图标(I)', L]))) fail('桌面没有空位可以右键');
    await sleep(200);
    AG.pushUndo('排列图标', async () => { S.pos = prev.pos; S.sort = prev.sort; S.auto = prev.auto; WM.save(); WM.refreshDesktop(); });
    return '按 ' + L + ' 排列';
  };
  ACT.new_item = async a => {
    const kind = a.kind || 'folder', L = kind === 'text' ? '文本文档' : '文件夹(F)', n0 = S.extra.length;
    if (!(await deskMenu(['新建(W)', L]))) fail('桌面没有空位可以右键');
    const inp = await waitFor(() => root.querySelector('#icons input.ren'), 1500);
    if (inp) { const p = livePoint(inp); if (a.name) { await typeText(inp, a.name); } await sleep(150); AG.key('keydown', 'Enter', inp); await sleep(200); }
    const id = S.extra.length > n0 ? S.extra[S.extra.length - 1].id : null;
    if (id) AG.pushUndo('新建 ' + (a.name || L), async () => { S.extra = S.extra.filter(e => e.id !== id); delete S.pos[id]; WM.save(); WM.refreshDesktop(); });
    return '新建了 ' + (a.name || L.replace(/\(.*\)/, ''));
  };
  const iconByName = nm => { const n = String(nm).toLowerCase().replace(/\s+/g, ''); return [...root.querySelectorAll('#icons .dicon')].find(e => (e.dataset.id || '').toLowerCase() === n || txt(e).toLowerCase().replace(/\s+/g, '').includes(n)); };
  ACT.move_icon = async a => {
    const ic = iconByName(a.icon); if (!ic) fail('桌面上没有图标：' + a.icon);
    const r = drect(ic), id = ic.dataset.id, old = (S.pos[id] || []).slice(), to = (a.to || 'center').toLowerCase();
    const D = { left: [90, r.y + 40], right: [DW - 50, r.y + 40], top: [r.x + 38, 40], bottom: [r.x + 38, DH - TB - 48], center: [DW / 2, DH / 2 - 20] }[to] || [DW / 2, DH / 2];
    const p = livePoint(ic, .5, .35) || fail('图标被窗口盖住了'); const dx = D[0] - (r.x + 38), dy = D[1] - (r.y + 40);
    await drag(p.x, p.y, p.x + dx, p.y + dy); await sleep(150);
    AG.pushUndo('移动图标', async () => { if (old.length) { S.pos[id] = old; WM.save(); WM.refreshDesktop(); } });
    return '图标 ' + txt(ic) + ' 已拖到' + to;
  };
  ACT.delete_icon = async a => {
    const ic = iconByName(a.icon); if (!ic) fail('桌面上没有图标：' + a.icon);
    const p = livePoint(ic, .5, .35) || fail('图标被盖住了'); await rclick(p.x, p.y); await menuPath(['删除(D)']);
    if (!(await dialogButton(/确认|删除/, '是'))) fail('没出现确认框'); return '已放入回收站';
  };
  ACT.empty_trash = async () => {
    const ic = iconByName('recycle'); if (!ic) fail('桌面上没有回收站'); const p = livePoint(ic, .5, .35) || fail('回收站被盖住了');
    await rclick(p.x, p.y); await menuPath(['清空回收站(B)']); if (!(await dialogButton(/确认|删除/, '是'))) fail('没出现确认框'); return '回收站已清空';
  };
  ACT.set_volume = async a => {
    const tray = $('tray').querySelector('img'); const prevV = WM.vol == null ? 70 : WM.vol, prevM = !!WM.mute;
    await clickEl(tray); const pop = await waitFor(() => $('volpop'), 1000); if (!pop) fail('没弹出音量条');
    const sl = pop.querySelector('input[type=range]'), r = drect(sl);
    const setV = v => { sl.value = v; sl.dispatchEvent(new Event('input', { bubbles: true })); };
    if (a.value != null) {
      const yOf = v => r.y + r.h - 6 - (r.h - 12) * v / 100, v0 = +sl.value;
      await move(r.x + r.w / 2, yOf(v0)); const e = elAt(r.x + r.w / 2, yOf(v0)); if (e) { mev('pointerdown', e, r.x + r.w / 2, yOf(v0), { buttons: 1 }); }
      AG.onMove = (x, y) => { const v = Math.round(Math.max(0, Math.min(100, (r.y + r.h - 6 - y) / (r.h - 12) * 100))); setV(v); };
      try { await move(r.x + r.w / 2, yOf(a.value), { speed: 260 }); } finally { AG.onMove = null; }
      setV(a.value); mev('pointerup', elAt(r.x + r.w / 2, yOf(a.value)) || document.body, r.x + r.w / 2, yOf(a.value), {});
      await sleep(200);
    }
    if (a.mute != null) { const cb = pop.querySelector('input[type=checkbox]'); if (cb && cb.checked !== !!a.mute) await clickEl(cb); }
    const q = emptyDeskPoint(); if (q) await click(q.x, q.y); else $('volpop') && $('volpop').remove();
    AG.pushUndo('音量', async () => { WM.vol = prevV; WM.mute = prevM; document.dispatchEvent(new CustomEvent('sysvol', { detail: prevV / 100 })); document.dispatchEvent(new CustomEvent('sysmute', { detail: prevM })); });
    return '音量 ' + (WM.vol == null ? 70 : WM.vol) + (WM.mute ? '（静音）' : '');
  };
  const mev = AG.mev;
  ACT.shutdown = async a => {
    await openStart(); const fi = [...sm().querySelectorAll('.fi')].find(e => /关闭/.test(txt(e))); await clickEl(fi);
    const L = { shutdown: '关闭(T)', restart: '重新启动(R)', standby: '待机(S)' }[a.mode || 'shutdown'];
    const d = await waitFor(() => WM.byId.shutdown && !WM.byId.shutdown.closed && WM.byId.shutdown, 1500); if (!d) fail('没弹出关机对话框');
    const lab = [...d.el.querySelectorAll('div')].find(e => txt(e) === L && !e.children.length); if (!lab) fail('找不到按钮'); await clickEl(lab.previousElementSibling); return L;
  };
  ACT.logoff = async () => {
    await openStart(); const fi = [...sm().querySelectorAll('.fi')].find(e => /注销/.test(txt(e))); await clickEl(fi);
    const d = await waitFor(() => WM.byId.logoff && !WM.byId.logoff.closed && WM.byId.logoff, 1500); if (!d) fail('没弹出注销对话框');
    const it = [...d.el.querySelectorAll('div')].find(e => /^注销\(L\)$/.test(txt(e))); if (it) await clickEl(it.previousElementSibling || it); return '注销';
  };

  // ================= 音乐（后端真的切歌；这里演“点千千静听按钮”）=================
  const MB = { music_next: ['tt-next', '下一首'], music_prev: ['tt-prev', '上一首'], music_pause: ['tt-play', '暂停'], music_play: ['tt-play', '播放'], music_toggle: ['tt-play', '播放/暂停'] };
  Object.keys(MB).forEach(k => {
    ACT[k] = async () => {
      const t = WM.byId.ttplayer, el = $(MB[k][0]);
      if (!(winVisible(t) && shown(el))) { const q = emptyDeskPoint(); if (q) await move(q.x, q.y); return MB[k][1] + '（播放器窗口没显示，只在后台操作）'; }
      if (WM.active !== t) { await raise(t).catch(() => {}); }
      await clickEl(el); return '点了千千静听的 ' + MB[k][1];
    };
  });
  ACT.song_request = async a => {
    const t = WM.byId.ttplayer, rows = $('pl-rows');
    if (winVisible(t) && rows && shown(rows)) { await hoverEl(rows); await sleep(500); return '看了一眼千千静听的播放列表（点歌已进队）'; }
    return '点歌已进队（播放器没显示）';
  };

  // ================= 软件里的操作 =================
  ACT.notepad_type = async a => {
    let w = findWins('notepad').find(x => !x.dialogOnly) || await openApp('notepad'); await raise(w);
    const ta = w.el.querySelector('textarea'); if (!ta) fail('记事本没有输入区');
    await clickEl(ta); const old = ta.value; ta.setSelectionRange(old.length, old.length);
    if (old && !old.endsWith('\n')) { document.execCommand('insertText', false, '\n'); }
    await typeText(ta, a.text); const nv = ta.value;
    AG.pushUndo('记事本打字', async () => { if (ta.isConnected) { ta.value = old; ta.dispatchEvent(new Event('input', { bubbles: true })); } });
    return '写入 ' + a.text.length + ' 个字';
  };
  async function chatReady() {
    const q = WM.byId.qqchat; if (!q) fail('没有群聊窗口');
    if (q.closed || q.state === 'min' || AG.chatVis() < 0.5) {
      if (q.closed) await openApp('qqchat'); else if (q.state === 'min') await raise(q); else { if (findWins('blocking').length) await ACT.move_away({}); await raise(q); }
    } else if (WM.active !== q) await raise(q);
    return q;
  }
  ACT.qq_send = async a => {
    const q = await chatReady(); const ta = q.el.querySelector('#input textarea'); if (!ta) fail('群聊没有输入框');
    await clickEl(ta); await typeText(ta, a.text); await sleep(200);
    const btn = [...q.el.querySelectorAll('.qq-im-btns .qq-btn')].find(b => /发送/.test(txt(b)));
    if (btn && livePoint(btn)) await clickEl(btn); else AG.key('keydown', 'Enter', ta);
    await sleep(150); return '群聊里发了：' + a.text.slice(0, 20);
  };
  ACT.cmd_run = async a => {
    let w = findWins('cmd').find(x => !x.dialogOnly) || await openApp('cmd'); await raise(w);
    const out = w.el.querySelector('[tabindex]'); if (!out) fail('命令提示符没有输入区');
    await clickEl(out); await typeText(out, a.command); await sleep(120); await press('Enter', out); await sleep(200); return '运行 ' + a.command;
  };
  ACT.calc = async a => {
    let w = findWins('calc').find(x => !x.dialogOnly) || await openApp('calc'); await raise(w);
    AG.fast = true; let e = String(a.expr).replace(/\s/g, ''); if (/^[+\-*/]/.test(e)) e = '0' + e;
    const btn = ch => [...w.el.querySelectorAll('button.xbtn')].find(b => txt(b) === ch);
    const clr = btn('C'); if (clr) await clickEl(clr);
    for (const ch of e.slice(0, 30)) { const b = btn(ch); if (!b) continue; await clickEl(b); }
    const eq = btn('='); if (eq) await clickEl(eq);
    const disp = w.el.querySelector('.xpd > div:nth-child(2)'); return '算出 ' + (disp ? txt(disp) : '');
  };
  ACT.browse = async a => {
    let w = findWins('ie').find(x => !x.dialogOnly) || await openApp('ie'); await raise(w);
    const inp = w.el.querySelector('.addr input'); if (!inp) fail('IE 没有地址栏');
    await clickEl(inp); inp.select(); await typeText(inp, a.url.replace(/^https?:\/\//, '')); await sleep(150); AG.key('keydown', 'Enter', inp); await sleep(300);
    return '访问 ' + a.url;
  };
  ACT.video_play = async a => {
    const w = await openApp('baofeng'); await raise(w);
    const rows = await waitFor(() => { const r = [...w.el.querySelectorAll('.pl .pi')]; return r.length ? r : null; }, 1500); if (!rows) fail('没有播放列表');
    let i = a.clip ? a.clip - 1 : ((rows.findIndex(r => r.classList.contains('on')) + 1) % rows.length);
    i = Math.max(0, Math.min(rows.length - 1, i)); await clickEl(rows[i], { dbl: true }); await sleep(300); return '播放第 ' + (i + 1) + ' 个';
  };
  ACT.video_toggle = async () => {
    const w = await openApp('baofeng'); await raise(w); const b = w.el.querySelector('.ctl .cb'); if (!b) fail('没有播放键'); await clickEl(b); return '点了播放/暂停';
  };

  // ================= 游戏 =================
  const GMENU = { cs: '新游戏', vc: '开始新游戏', war3: '单人游戏', ra2: '遭遇战' };
  const gameWin = app => findWins(app).find(w => !w.dialogOnly);
  ACT.game_start = async a => {
    const app = a.app; if (!(app in GMENU) && app !== 'mir2' && app !== 'audition') fail(app + ' 不是游戏');
    let w = gameWin(app) || await openApp(app); await raise(w);
    if (app === 'audition') { await sleep(300); for (let i = 0; i < 4; i++) { await press(['ArrowLeft', 'ArrowDown', 'ArrowUp', 'ArrowRight'][i], document.body); await sleep(110); } return '劲舞团开跳（方向键）'; }
    if (app === 'mir2') {
      const g = w.el.querySelector('.gm'); const login = await waitFor(() => [...w.el.querySelectorAll('.dlg button')].find(b => txt(b) === '登录'), 3000);
      if (login) { await clickEl(login); const ent = await waitFor(() => [...w.el.querySelectorAll('.dlg button')].find(b => txt(b) === '进入游戏'), 1500); if (ent) await clickEl(ent); }
      await waitFor(() => w.el.querySelector('.bar2'), 1500); return '进入热血传奇游戏画面';
    }
    const vid = w.el.querySelector('video'); if (vid && vid.style.display !== 'none') return '已经在游戏画面里';
    const mi = await waitFor(() => { const m = w.el.querySelector('.gm .menu'); if (!m || m.style.display === 'none' || !shown(m)) return null; return [...m.querySelectorAll('.mi')].find(e => txt(e) === GMENU[app]); }, 6000);
    if (!mi) fail('游戏菜单没出来'); await clickEl(mi); await sleep(400); return '点了「' + GMENU[app] + '」，进入游戏画面';
  };
  ACT.game_back = async a => {
    let w = a.app ? gameWin(a.app) : findWins('active').concat(WM.wins.filter(x => /^game-/.test(x.id) && !x.closed))[0];
    if (!w || !/^game-/.test(w.id)) fail('没有游戏窗口'); await raise(w); await press('Escape', document.body); await sleep(250); return '按 ESC 回主菜单';
  };
  ACT.mir2_chat = async a => {
    let w = gameWin('mir2'); if (!w || !w.el.querySelector('.bar2')) { await ACT.game_start({ app: 'mir2' }); w = gameWin('mir2'); }
    await raise(w); await press('Enter', document.body); const inp = await waitFor(() => { const c = w.el.querySelector('.cin'); return c && c.style.display === 'block' && c.firstChild; }, 800);
    if (!inp) fail('聊天框没出来'); await typeText(inp, a.text); await sleep(100); await press('Enter', inp); return '游戏里说了：' + a.text.slice(0, 20);
  };
  ACT.dance = async a => {
    let w = gameWin('audition') || await openApp('audition'); await raise(w);
    const keys = ['ArrowLeft', 'ArrowDown', 'ArrowUp', 'ArrowRight']; const n = Math.max(1, Math.min(20, a.count || 8));
    for (let i = 0; i < n; i++) { await press(keys[Math.floor(Math.random() * 4)], document.body); await sleep(120); } return '按了 ' + n + ' 次方向键';
  };

  // ---- 扫雷 ----
  async function mineWin() { const w = await openApp('minesweeper'); await raise(w); if (!w.mine) fail('扫雷窗口没有接口'); return w; }
  const cellEl = (w, r, c) => { const st = w.mine.state(); if (r < 1 || c < 1 || r > st.H || c > st.W) fail('扫雷这一局只有 ' + st.H + ' 行 ' + st.W + ' 列'); return w.mine.bd.children[(r - 1) * st.W + (c - 1)]; };
  ACT.mine_new = async a => {
    const w = await mineWin(), st = w.mine.state();
    if (a.level && a.level !== st.lv) {
      const mb = [...w.el.querySelectorAll('.xp-menubar .mb')].find(b => /游戏/.test(txt(b))); await clickEl(mb);
      await menuPath([{ beginner: '初级(B)', intermediate: '中级(I)', expert: '高级(E)' }[a.level]]); await sleep(200); return '新局：' + a.level;
    }
    await clickEl(w.el.querySelector('.face')); await sleep(150); return '新开一局';
  };
  ACT.mine_click = async a => { const w = await mineWin(); await clickEl(cellEl(w, a.row, a.col)); return '点开 ' + a.row + ',' + a.col; };
  ACT.mine_flag = async a => { const w = await mineWin(); const e = cellEl(w, a.row, a.col); const p = livePoint(e) || fail('格子被盖住'); await rclick(p.x, p.y); return '插旗 ' + a.row + ',' + a.col; };
  function minePlan(st) {
    const { W, H, cells, N } = st, n = W * H;
    if (st.first) return { k: 'open', i: Math.floor(H / 2) * W + Math.floor(W / 2), why: '开局点中间' };
    const nb = i => { const x = i % W, y = (i / W) | 0, o = []; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { if (!dx && !dy) continue; const X = x + dx, Y = y + dy; if (X >= 0 && X < W && Y >= 0 && Y < H) o.push(Y * W + X); } return o; };
    const safe = new Set(), mines = new Set(), fr = [];
    for (let i = 0; i < n; i++) { const v = cells[i]; if (v <= 0) continue; const ns = nb(i), unk = ns.filter(j => cells[j] === -1), fl = ns.filter(j => cells[j] === -2).length, rem = v - fl; if (!unk.length) continue; fr.push({ i, unk, rem }); if (rem === 0) unk.forEach(j => safe.add(j)); else if (rem === unk.length) unk.forEach(j => mines.add(j)); }
    for (const A of fr) for (const B of fr) { if (A === B || A.unk.length >= B.unk.length || !A.unk.every(j => B.unk.includes(j))) continue; const diff = B.unk.filter(j => !A.unk.includes(j)), need = B.rem - A.rem; if (need === 0) diff.forEach(j => safe.add(j)); else if (need === diff.length) diff.forEach(j => mines.add(j)); }
    for (const j of mines) safe.delete(j);
    const s = [...safe].find(j => cells[j] === -1); if (s != null) return { k: 'open', i: s, why: '推理：安全' };
    const m = [...mines].find(j => cells[j] === -1); if (m != null) return { k: 'flag', i: m, why: '推理：是雷' };
    const unkAll = []; for (let i = 0; i < n; i++) if (cells[i] === -1) unkAll.push(i);
    if (!unkAll.length) return null;
    const flags = cells.filter(v => v === -2).length, dens = Math.max(0.05, (N - flags) / unkAll.length), risk = new Map();
    fr.forEach(f => f.unk.forEach(j => risk.set(j, Math.max(risk.get(j) || 0, f.rem / f.unk.length))));
    let best = null; for (const j of unkAll) { const r = risk.has(j) ? risk.get(j) : dens; if (!best || r < best.r || (r === best.r && Math.random() < .3)) best = { j, r }; }
    return { k: 'open', i: best.j, why: '没法推理，猜一格（风险 ' + Math.round(best.r * 100) + '%）' };
  }
  ACT.mine_play = async a => {
    const w = await mineWin(), steps = Math.max(1, Math.min(30, a.steps || 10)); let done = 0, guesses = 0, notes = [];
    for (let s = 0; s < steps; s++) {
      const st = w.mine.state(); if (st.over) { notes.push('游戏结束'); break; }
      const mv = minePlan(st); if (!mv) break; if (/猜/.test(mv.why)) guesses++;
      const el = w.mine.bd.children[mv.i]; if (!el) break;
      if (mv.k === 'open') await clickEl(el); else { const p = livePoint(el) || fail('格子被盖住'); await rclick(p.x, p.y); }
      done++; AG.fast = done > 3;
    }
    const st = w.mine.state(); return '扫雷走了 ' + done + ' 步（猜了 ' + guesses + ' 次）' + (st.over ? '，这局结束了' : '');
  };

  // ================= 纸牌 / 空当接龙 / 画图 / 控制面板 / XP 彩蛋（item 3）=================
  const cancelled = () => !!(AG.cur && AG.cur.aborted);
  const cardPt = el => livePoint(el, .5, .12) || livePoint(el);
  // 用鼠标把一张牌（连带它上面的牌）拖到目标元素上：落点 = 目标左上角 + 抓牌时的偏移
  async function dragCard(el, to) {
    const p = cardPt(el) || fail('这张牌被盖住了'), er = drect(el), tr = drect(to), gx = p.x - er.x, gy = p.y - er.y;
    const isCard = to.classList && to.classList.contains('card');
    await drag(p.x, p.y, tr.x + gx, tr.y + gy + (isCard ? 16 : 6));
  }
  async function gameMenu(w, path, title) {
    const mb = [...w.el.querySelectorAll('.xp-menubar .mb')].find(b => /游戏/.test(txt(b))); await clickEl(mb); await menuPath(path); await sleep(160);
    await dialogButton(new RegExp(title), '是', 700);   // “要放弃这一局…吗？”
  }
  async function solWin() { const w = await openApp('solitaire'); await raise(w); if (!w.sol) fail('纸牌窗口没有接口'); return w; }
  async function fcWin() { const w = await openApp('freecell'); await raise(w); if (!w.fc) fail('空当接龙窗口没有接口'); return w; }
  ACT.sol_new = async a => {
    const w = await solWin(); const st = w.sol.state();
    if (a.draw && (a.draw === 3) !== st.draw3) { const mb = [...w.el.querySelectorAll('.xp-menubar .mb')].find(b => /游戏/.test(txt(b))); await clickEl(mb); await menuPath(['选项(O)']); const d = await waitFor(() => WM.byId.solopt && !WM.byId.solopt.closed && WM.byId.solopt, 1500); if (d) { const r = d.el.querySelector('input[data-v="' + (a.draw === 3 ? 1 : 0) + '"]'); if (r) await clickEl(r); const ok = [...d.el.querySelectorAll('button')].find(b => /确定/.test(txt(b))); if (ok) await clickEl(ok); await sleep(300); return '新局，每次翻 ' + a.draw + ' 张'; } w.sol.setDraw3(a.draw === 3); return '新局（直接设置）'; }
    await gameMenu(w, ['发牌(D)'], '纸牌'); return '重新发牌';
  };
  ACT.sol_play = async a => {
    const w = await solWin(), steps = Math.max(1, Math.min(40, a.steps || 12)); let done = 0, notes = [], direct = 0;
    for (let i = 0; i < steps && !cancelled(); i++) {
      const sol = w.sol, st = sol.state(); if (st.won) { notes.push('赢了！'); break; }
      const pl = sol.plan(); if (!pl) { notes.push('没路可走了'); break; }
      const m0 = st.moves;
      try { if (pl.kind === 'stock') await clickEl(pl.el); else if (pl.kind === 'dbl') { const p = cardPt(pl.el) || fail('牌被盖住'); await dblclick(p.x, p.y); } else await dragCard(pl.el, pl.to); } catch (e) { if (cancelled()) throw e; }
      await sleep(120);
      if (sol.state().moves === m0) { if (pl.kind === 'stock') sol.draw(); else sol.exec(pl.cs, pl.exec); sol.render(); direct++; }
      done++; AG.fast = done > 4;
    }
    const st = w.sol.state(); return '纸牌走了 ' + done + ' 步，基础堆 ' + st.foundTotal + '/52，分数 ' + st.score + (direct ? '（有 ' + direct + ' 步没拖成，直接放了）' : '') + (notes.length ? '，' + notes.join('、') : '');
  };
  ACT.fc_new = async a => {
    const w = await fcWin();
    if (a.no) { const mb = [...w.el.querySelectorAll('.xp-menubar .mb')].find(b => /游戏/.test(txt(b))); await clickEl(mb); await menuPath(['选择游戏']); const d = await waitFor(() => WM.byId['prompt-选择游戏'], 1500); const inp = d && d.el.querySelector('input'); if (inp) { inp.value = ''; await typeText(inp, String(a.no)); await press('Enter', inp); await sleep(300); await dialogButton(/空当接龙/, '是', 600); return '空当接龙 #' + a.no; } w.fc.newGame(a.no); return '空当接龙 #' + a.no + '（直接设置）'; }
    await gameMenu(w, ['新游戏'], '空当接龙'); return '新开一局空当接龙 #' + w.fc.state().no;
  };
  ACT.fc_play = async a => {
    const w = await fcWin(), steps = Math.max(1, Math.min(40, a.steps || 12)); let done = 0, direct = 0, notes = [];
    for (let i = 0; i < steps && !cancelled(); i++) {
      const fc = w.fc, st = fc.state(); if (st.won) { notes.push('解开了！'); break; }
      if (!w._plan || w._plan.expect !== st.moves || w._plan.no !== st.no || w._plan.i >= w._plan.moves.length) {
        const r = await fc.solve(3500); if (!r.moves.length) { notes.push('这局解不开'); break; }
        w._plan = { moves: r.moves, i: 0, expect: st.moves, no: st.no, ok: r.ok }; notes.push(r.ok ? '' : '没找到整局解，先走最接近的一段');
      }
      const P = w._plan, mv = P.moves[P.i], r = fc.resolveMove(mv); if (!r) { w._plan = null; continue; }
      const m0 = st.moves;
      try { if (r.kind === 'dbl') { const p = cardPt(r.el) || fail('牌被盖住'); await dblclick(p.x, p.y); } else await dragCard(r.el, r.to); } catch (e) { if (cancelled()) throw e; }
      await sleep(100);
      if (fc.state().moves === m0) { fc.applyMove(mv); fc.render(); direct++; }
      P.i++; P.expect = fc.state().moves; done++; AG.fast = done > 4;
    }
    const st = w.fc.state(); return '空当接龙 #' + st.no + ' 走了 ' + done + ' 步，基础堆 ' + st.foundTotal + '/52' + (direct ? '（' + direct + ' 步直接放的）' : '') + (notes.filter(Boolean).length ? '，' + notes.filter(Boolean).join('、') : '');
  };

  // ---- 画图 ----
  const PAL_NAMES = { 黑: '#000000', 灰: '#808080', 暗红: '#800000', 橄榄: '#808000', 深绿: '#008000', 青绿: '#008080', 深蓝: '#000080', 紫: '#800080', 咖啡: '#804000', 棕: '#804000', 天蓝: '#0080ff', 白: '#ffffff', 银: '#c0c0c0', 红: '#ff0000', 黄: '#ffff00', 绿: '#00ff00', 青: '#00ffff', 蓝: '#0000ff', 粉: '#ff00ff', 洋红: '#ff00ff', 玫红: '#ff0080', 橙: '#ff8040', 浅黄: '#ffff80', 浅蓝: '#80ffff', 淡紫: '#8080ff', 草绿: '#00ff80' };
  const colorHex = n => { n = String(n || '').trim(); if (/^#[0-9a-f]{6}$/i.test(n)) return n.toLowerCase(); const k = Object.keys(PAL_NAMES).sort((x, y) => y.length - x.length).find(k => n.includes(k)); return k ? PAL_NAMES[k] : null; };
  async function paintWin() { const w = await openApp('paint'); await raise(w); if (!w.paint) fail('画图窗口没有接口'); return w; }
  const pTool = async (w, t) => { if (w.paint.state().tool !== t) await clickEl(w.paint.tools[t]); };
  const pColor = async (w, hex, bg) => { const e = w.paint.swatches[hex]; if (!e) fail('颜料盒里没有 ' + hex); if (bg) { const p = livePoint(e) || fail('颜料盒被盖住'); await rclick(p.x, p.y); } else await clickEl(e); };
  const pFill = async (w, m) => { const b = w.paint.opts.querySelector('[data-fill="' + m + '"]'); if (b) await clickEl(b); };
  const pSize = async (w, n) => { const b = w.paint.opts.querySelector('[data-size="' + n + '"]'); if (b) await clickEl(b); };
  const cvPt = (w, x, y) => { const r = drect(w.paint.cv), cv = w.paint.cv; return { x: r.x + x * r.w / cv.width, y: r.y + y * r.h / cv.height }; };
  async function pStroke(w, pts) {
    const P = pts.map(q => cvPt(w, q[0], q[1])), cv = w.paint.cv; await move(P[0].x, P[0].y); AG.mev('pointerdown', cv, P[0].x, P[0].y, { buttons: 1 }); await sleep(70);
    AG.onMove = (x, y) => AG.mev('pointermove', cv, x, y, { buttons: 1 });
    try { for (const q of P.slice(1)) await move(q.x, q.y, { speed: AG.cfg.cursor_speed * (pts.length > 4 ? .55 : .9) }); } finally { AG.onMove = null; }
    AG.mev('pointerup', cv, P[P.length - 1].x, P[P.length - 1].y, {}); await sleep(90);
  }
  const arc = (cx, cy, rx, ry, a0, a1, n) => Array.from({ length: n + 1 }, (_, i) => { const a = (a0 + (a1 - a0) * i / n) * Math.PI / 180; return [Math.round(cx + rx * Math.cos(a)), Math.round(cy + ry * Math.sin(a))]; });
  const heart = (cx, cy, k) => Array.from({ length: 25 }, (_, i) => { const t = i / 24 * 2 * Math.PI; return [Math.round(cx + k * 16 * Math.pow(Math.sin(t), 3)), Math.round(cy - k * (13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)))]; });
  const starPts = (cx, cy, r) => [0, 2, 4, 1, 3, 0].map(i => { const a = (-90 + i * 72) * Math.PI / 180; return [Math.round(cx + r * Math.cos(a)), Math.round(cy + r * Math.sin(a))]; });
  // 每幅画：[{t:工具, c:前景色, f:填充方式, s:粗细, pts:[[x,y],…]}]，坐标是 480×300 画布上的位置；{fill:[x,y],c} = 用油漆桶倒色
  const DRAWS = {
    smile: c => [{ t: 'ellipse', f: 2, c: c || '#ffff00', pts: [[130, 30], [350, 250]] }, { t: 'ellipse', f: 0, c: '#000000', s: 3, pts: [[130, 30], [350, 250]] }, { t: 'ellipse', f: 2, c: '#000000', pts: [[195, 90], [220, 135]] }, { t: 'ellipse', f: 2, c: '#000000', pts: [[260, 90], [285, 135]] }, { t: 'brush', c: '#800000', s: 4, pts: arc(240, 150, 62, 55, 25, 155, 10) }],
    house: c => [{ t: 'rect', f: 2, c: '#ffff80', pts: [[140, 140], [340, 260]] }, { t: 'rect', f: 0, c: '#000000', s: 2, pts: [[140, 140], [340, 260]] }, { t: 'brush', c: c || '#ff0000', s: 4, pts: [[120, 142], [240, 60], [360, 142], [120, 142]] }, { fill: [240, 110], c: c || '#ff0000' }, { t: 'rect', f: 2, c: '#804000', pts: [[222, 190], [262, 259]] }, { t: 'rect', f: 2, c: '#80ffff', pts: [[160, 165], [200, 205]] }, { t: 'rect', f: 0, c: '#000000', s: 1, pts: [[160, 165], [200, 205]] }, { t: 'rect', f: 2, c: '#00ff00', pts: [[0, 261], [479, 299]] }],
    sun: c => [{ t: 'ellipse', f: 2, c: c || '#ffff00', pts: [[190, 90], [290, 190]] }, ...[0, 45, 90, 135, 180, 225, 270, 315].map(a => ({ t: 'line', c: '#ff8040', s: 3, pts: [[Math.round(240 + 66 * Math.cos(a * Math.PI / 180)), Math.round(140 + 66 * Math.sin(a * Math.PI / 180))], [Math.round(240 + 105 * Math.cos(a * Math.PI / 180)), Math.round(140 + 105 * Math.sin(a * Math.PI / 180))]] }))],
    flower: c => [{ t: 'line', c: '#008000', s: 4, pts: [[240, 140], [240, 275]] }, { t: 'ellipse', f: 2, c: '#00ff00', pts: [[240, 205], [290, 235]] }, ...[0, 60, 120, 180, 240, 300].map(a => ({ t: 'ellipse', f: 2, c: c || '#ff00ff', pts: [[Math.round(240 + 38 * Math.cos(a * Math.PI / 180)) - 22, Math.round(100 + 38 * Math.sin(a * Math.PI / 180)) - 22], [Math.round(240 + 38 * Math.cos(a * Math.PI / 180)) + 22, Math.round(100 + 38 * Math.sin(a * Math.PI / 180)) + 22]] })), { t: 'ellipse', f: 2, c: '#ffff00', pts: [[220, 80], [260, 120]] }],
    heart: c => [{ t: 'brush', c: c || '#ff0000', s: 4, pts: heart(240, 140, 8) }, { fill: [240, 130], c: c || '#ff0000' }],
    star: c => [{ t: 'brush', c: '#ff8040', s: 4, pts: starPts(240, 150, 110) }, { fill: [240, 150], c: c || '#ffff00' }],
    tree: c => [{ t: 'rect', f: 2, c: '#804000', pts: [[222, 170], [258, 270]] }, { t: 'ellipse', f: 2, c: c || '#008000', pts: [[150, 70], [330, 200]] }, { t: 'ellipse', f: 2, c: '#00ff00', pts: [[185, 40], [295, 140]] }, { t: 'rect', f: 2, c: '#00ff00', pts: [[0, 270], [479, 299]] }],
    boat: c => [{ t: 'rect', f: 2, c: '#0080ff', pts: [[0, 200], [479, 299]] }, { t: 'brush', c: '#804000', s: 4, pts: [[130, 190], [350, 190], [315, 235], [165, 235], [130, 190]] }, { fill: [240, 212], c: '#804000' }, { t: 'line', c: '#000000', s: 3, pts: [[240, 190], [240, 50]] }, { t: 'brush', c: c || '#ff0000', s: 4, pts: [[246, 55], [330, 170], [246, 170], [246, 55]] }, { fill: [275, 150], c: c || '#ff0000' }],
  };
  ACT.paint_tool = async a => { const w = await paintWin(); if (!w.paint.tools[a.tool]) fail('没有这个工具：' + a.tool); await pTool(w, a.tool); return '选了工具 ' + a.tool; };
  ACT.paint_color = async a => { const hex = colorHex(a.color); if (!hex) fail('不认识的颜色：' + a.color); const w = await paintWin(); await pColor(w, hex); return '选了颜色 ' + a.color; };
  ACT.paint_clear = async a => {
    const w = await paintWin(), mb = [...w.el.querySelectorAll('.xp-menubar .mb')].find(b => /图像/.test(txt(b))); await clickEl(mb); await menuPath(['清除图像']); await sleep(150); return '清除了画布';
  };
  ACT.paint_draw = async a => {
    const w = await paintWin(), what = a.what || 'smile', D = DRAWS[what] || fail('不会画：' + what), col = a.color ? colorHex(a.color) : null; let n = 0, ink0 = w.paint.state().strokes;
    for (const st of D(col)) {
      if (cancelled()) break;
      if (st.fill) { await pTool(w, 'fill'); await pColor(w, st.c); const p = cvPt(w, st.fill[0], st.fill[1]); await click(p.x, p.y); }
      else { await pTool(w, st.t); await pColor(w, st.c); if (st.f != null) await pFill(w, st.f); if (st.s && st.t === 'line') await pSize(w, Math.min(5, st.s)); else if (st.s && st.t === 'brush') await pSize(w, st.s >= 4 ? 4 : st.s); await pStroke(w, st.pts); }
      n++; AG.fast = n > 3;
    }
    if (window.AC) AC.after(w, 'paint');          // 画完了：从现在开始算闲置时间，paint 25 秒后自动收掉
    return '用画图画了「' + ({ smile: '笑脸', house: '房子', sun: '太阳', flower: '花', heart: '爱心', star: '星星', tree: '树', boat: '小船' }[what]) + '」（' + n + ' 笔）';
  };

  // ---- 控制面板 ----
  const CPL = { 声音: ['声音、语音和音频设备', 'sound', 'sndcpl'], 音频: ['声音、语音和音频设备', 'sound', 'sndcpl'], 鼠标: ['打印机和其他硬件', 'mouse', 'mousecpl'], 显示: ['外观和主题', 'display', 'display'], 日期: ['日期、时间、语言和区域设置', 'datetime', 'datetime'], 时间: ['日期、时间、语言和区域设置', 'datetime', 'datetime'] };
  ACT.control_open = async a => {
    const w = await openApp('control'); await raise(w); if (!w.cp) fail('控制面板没有接口'); const item = String(a.item || '');
    const key = Object.keys(CPL).find(k => item.includes(k)), home = () => [...w.el.querySelectorAll('.bar a')][0];
    if (w.cp.state().cat || w.cp.state().view !== 'cat') { if (w.cp.state().view !== 'cat') { const sw = w.el.querySelector('[data-act="switch"]'); if (sw) await clickEl(sw); } else if (home()) await clickEl(home()); await sleep(150); }
    const catEl = n => [...w.el.querySelectorAll('.cat')].find(e => (e.dataset.cat || '').includes(n));
    const ce = key ? catEl(CPL[key][0]) : catEl(item); if (!ce) fail('控制面板里没有：' + item); await clickEl(ce); await sleep(220);
    if (!key) return '进了控制面板的“' + ce.dataset.cat + '”';
    const ap = w.el.querySelector('[data-applet="' + CPL[key][1] + '"]'); if (!ap) fail('没找到小程序 ' + key); await clickEl(ap);
    const d = await waitFor(() => WM.byId[CPL[key][2]] && !WM.byId[CPL[key][2]].closed && WM.byId[CPL[key][2]], 1800); if (!d) fail('小程序没打开');
    await sleep(260);
    if (key === '声音' && !a.openOnly) {   // 看一眼“声音”选项卡，点一个事件，按“测试”播放真的 XP 声音
      const tab = [...d.el.querySelectorAll('.xtabs .tb')].find(t => txt(t) === '声音'); if (tab) { await clickEl(tab); await sleep(200);
        const evs = [...d.el.querySelectorAll('[data-snd]')].filter(e => ['default', 'exclamation', 'ding', 'restore', 'notify', 'recycle'].includes(e.dataset.snd)), ev = evs[Math.floor(Math.random() * evs.length)]; if (ev) { ev.scrollIntoView({ block: 'nearest' }); await sleep(80); await clickEl(ev); const tb = d.el.querySelector('[data-act="test"]'); if (tb) { await clickEl(tb); await sleep(900); } } }
    }
    return '控制面板 → ' + (CPL[key][2] === 'sndcpl' ? '声音和音频设备' : CPL[key][2] === 'mousecpl' ? '鼠标' : item);
  };

  // ---- XP 彩蛋 ----
  ACT.bsod = async () => { if (!window.XP || !XP.cfg.enabled || !XP.cfg.bsod) fail('蓝屏彩蛋没开（[xp] bsod）'); if (XP.screen) fail('现在正在放别的画面'); if (Date.now() - (AG._bsodAt || 0) < 120000) fail('刚蓝屏过，电脑还没缓过来（2 分钟冷却）'); AG._bsodAt = Date.now(); XP.bsod('agent'); await sleep(500); return '蓝屏了（' + XP.cfg.bsod_secs + ' 秒后自动重启）'; };
  ACT.balloon = async a => { if (!window.XP || !XP.cfg.enabled || !XP.cfg.balloons) fail('气泡通知没开（[xp] balloons）'); ({ hardware: XP.hardware, tip: XP.tip, qq: XP.qqOnline }[a.kind || 'hardware'] || XP.hardware)(); await sleep(400); return '托盘弹了一个气泡'; };

  // ================= 观众互动（[play]）：特效 / 排行榜（光标真的去点）；投票由服务端 backend/play 发起，窗口自己弹 =================
  ACT.play_fx = async a => {
    if (!window.PLAYX || !PLAYX.cfg.enabled || !PLAYX.cfg.fx) fail('特效没开（[play] fx）');
    if (!window.QQX || !QQX.cfg.enabled) fail('特效依赖 [qq]（enabled）');
    const k = a.kind; if (!QQX.actions[k]) fail('没有这个特效：' + k);
    const ok = QQX.run(k, { name: AG.cur && AG.cur.by || '' }); if (!ok) fail('现在不能放（冷却中？）');
    await sleep(900); return '放了特效 ' + k;
  };
  ACT.gift_fx = async a => {                 // 礼物 / 点赞联动（[giftfx]）：只有主播自己（idle / giftfx）能发，观众和 LLM 不行（registry.HOST_ONLY）
    if (!window.GFX) fail('礼物联动没加载（giftfx.js）');
    const r = GFX.run(a); if (!r) fail('现在放不了（开关 / 正在放别的画面）'); await sleep(300); return r;
  };
  ACT.rank_open = async a => {
    if (!window.PLAYX || !PLAYX.on('points')) fail('积分没开（[play] points）');
    const w = await openApp('rank'); await raise(w); const by = a.by || 'day';
    const b = w.el.querySelector('[data-by="' + by + '"]'); if (b) { await clickEl(b); await sleep(500); }
    return '打开了' + (by === 'day' ? '日榜' : '总榜');
  };

  // ================= QQ 生态：宠物 / QQ秀 / QQ空间 / 群共享 / 窗口抖动（光标真的去点） =================
  const qx = () => window.QQX && QQX.cfg.enabled ? QQX : null;
  const pickTab = async (w, tab) => { const b = w.el.querySelector('.nv b[data-tab="' + tab + '"]'); if (!b) fail('空间里没有这个标签：' + tab); await clickEl(b); await sleep(200); };
  ACT.pet_care = async a => {
    if (!qx() || !QQX.pet) fail('QQ宠物没开（[qq] pet）');
    const el = document.getElementById('qqx-pet'); if (!el || !shown(el)) fail('桌面上没有QQ宠物');
    const p = livePoint(el, .5, .55); if (!p) fail('宠物被窗口盖住了，点不到');
    const FN = { apple: '苹果', fish: '小鱼干', cake: '蛋糕', drumstick: '鸡腿' }, what = a.what || 'feed';
    const path = { feed: ['喂食', FN[a.food] || '苹果'], bath: ['洗澡'], play: ['玩耍', '皮球'], sleep: ['睡觉'], sing: ['唱歌'] }[what] || fail('宠物不会：' + what);
    await rclick(p.x, p.y); await menuPath(path); await sleep(500);
    const st = QQX.pet.state(); return '给宠物' + ({ feed: '喂食', bath: '洗澡', play: '玩耍', sleep: '哄睡', sing: '唱歌' }[what]) + '（饱食 ' + Math.round(st.hunger) + ' 清洁 ' + Math.round(st.clean) + ' 心情 ' + Math.round(st.mood) + '）';
  };
  ACT.outfit_change = async a => {
    if (!qx() || !QQX.on('show')) fail('QQ秀没开（[qq] show）');
    const id = QQX.show.resolve(a.name || 'next'); if (!id) fail('不认识的套装：' + a.name);
    await chatReady(); const nm = document.getElementById('showname'); if (!nm || !livePoint(nm)) fail('找不到QQ秀入口');
    const prev = QQX.mods.show.state().cur, had = WM.byId.qqshow && !WM.byId.qqshow.closed;
    await clickEl(nm); const w = await waitFor(() => WM.byId.qqshow && !WM.byId.qqshow.closed && WM.byId.qqshow, 1500); if (!w) fail('QQ秀商城没打开');
    await sleep(250); const card = w.el.querySelector('.cd[data-outfit="' + id + '"]'); if (!card) fail('商城里没有 ' + id);
    await clickEl(card); await sleep(200); const wb = w.el.querySelector('[data-act=wear]'); if (wb) await clickEl(wb); else QQX.show.wear(id, {});
    await sleep(900); const label = QQX.mods.show.OUTFITS[id].name;
    if (!had) { const cb = btnEl(w, 'cl'); if (cb && livePoint(cb)) await clickEl(cb); else w.close && w.close(); }
    AG.pushUndo('QQ秀换装', async () => { QQX.show.wear(prev, {}); });
    return '给猪猪侠换上「' + label + '」';
  };
  ACT.zone_open = async a => {
    if (!qx() || !QQX.on('zone')) fail('QQ空间没开（[qq] zone）');
    const w = await openApp('qzone'); await raise(w); if (a.tab && a.tab !== 'home') await pickTab(w, a.tab); else await pickTab(w, 'home');
    if (a.post === 'diary' && a.tab === 'blog') {                      // 连续剧情：点开最新一篇日记（日志列表按时间倒序，data-diary 的第一篇就是最新的）
      const t = w.el.querySelector('[data-diary] h5'); if (t && livePoint(t)) { await clickEl(t); await sleep(400); }
    }
    return '打开QQ空间' + (a.tab ? '（' + a.tab + '）' : '');
  };
  ACT.zone_blog = async a => {
    if (!qx() || !QQX.on('zone')) fail('QQ空间没开（[qq] zone）');
    const w = await openApp('qzone'); await raise(w); await pickTab(w, 'blog');
    const nb = w.el.querySelector('[data-act=newblog]'); if (!nb) fail('找不到“写日志”'); await clickEl(nb); await sleep(250);
    const ti = w.el.querySelector('.qz-title'), bo = w.el.querySelector('.qz-body'); if (!ti || !bo) fail('日志编辑框没出来');
    await clickEl(ti); await typeText(ti, a.title); await clickEl(bo); await typeText(bo, a.text); await sleep(150);
    const pb = w.el.querySelector('[data-act=publish]'); if (!pb) fail('找不到“发表”'); await clickEl(pb); await sleep(300);
    return '在QQ空间发表了日志「' + a.title + '」';
  };
  ACT.zone_msg = async a => {
    if (!qx() || !QQX.on('zone')) fail('QQ空间没开（[qq] zone）');
    const w = await openApp('qzone'); await raise(w); await pickTab(w, 'msg');
    const ta = w.el.querySelector('textarea.qz-msg'); if (!ta) fail('留言板没有输入框'); await clickEl(ta); await typeText(ta, a.text);
    const pb = w.el.querySelector('[data-act=postmsg]'); if (!pb) fail('找不到“留言”按钮'); await clickEl(pb); await sleep(250);
    return '在空间留言：' + a.text.slice(0, 20);
  };
  ACT.files_download = async a => {
    if (!qx() || !QQX.on('files')) fail('群共享没开（[qq] files）');
    const w = await openApp('qqfiles'); await raise(w); await sleep(150);
    const rows = [...w.el.querySelectorAll('tr[data-file]')]; if (!rows.length) fail('群共享里没有文件');
    const row = (a.name && rows.find(r => txt(r).includes(a.name))) || rows[Math.floor(Math.random() * rows.length)];
    await clickEl(row); await sleep(150); const nm = txt(row.querySelector('td:nth-child(1)') || row).replace(/\s+/g, ' ').slice(0, 24);
    const b = w.el.querySelector('[data-act=download]'); if (!b) fail('找不到“下载”'); await clickEl(b); await sleep(600);
    return '从群共享下载「' + nm + '」，迅雷接手' + (a.name && !txt(row).includes(a.name) ? '（没找到「' + a.name + '」，随机挑了一个）' : '');
  };
  ACT.shake = async a => {
    if (!qx() || !QQX.on('shake')) fail('窗口抖动没开（[qq] shake）');
    if (a.target === 'desk') { if (!QQX.shake('desk', { force: true })) fail('现在不能抖'); await sleep(Math.min(2500, QQX.cfg.shake_secs * 1000)); return '整个桌面抖了一下'; }
    const q = await chatReady(); if (q.state === 'max') fail('群聊窗口是最大化的，抖不起来');
    const ob = q.el.querySelector('.qq-im-chat-toolbar .im-toolbar-other'); if (!ob || !livePoint(ob)) { if (!QQX.shake('chat', { force: true })) fail('现在不能抖'); }
    else { await clickEl(ob); await menuPath(['发送窗口抖动']); }
    await sleep(Math.min(2500, QQX.cfg.shake_secs * 1000)); return '群聊窗口抖动了一下';
  };

  // ================= 撤销 / 内部 =================
  ACT.undo = async () => {
    const u = AG.undo.pop(); if (!u) return '没有可撤销的操作';
    await u.fn(); await sleep(200); return '撤销：' + u.label;
  };
  ACT._restore_chat = async () => {
    const q = WM.byId.qqchat; if (!q) return '';
    if (AG.chatOk()) return '群聊没问题';
    if (q.closed) { const p = emptyTaskbarPoint() || { x: 600, y: DH - 14 }; await move(p.x, p.y); q.reopen(); await sleep(300); }
    else if (q.state === 'min') await raise(q);
    else {
      const R = rectOf(q); if (R.x + R.w < 120 || R.x > DW - 120 || R.y > USE_H - 60) { await dragWindowTo(q, 478, 18); }
      if (findWins('blocking').length) await ACT.move_away({});
      await raise(q);
    }
    if (!AG.chatOk()) { q.focus(); }
    return '群聊窗口已自动恢复';
  };

  // ================= 自己玩电脑（idle）用的动作：_ 开头的是内部动作，观众 / 大模型调用不到 =================
  ACT._wait = async a => { await sleep(Math.max(0.2, Math.min(8, +a.secs || 1)) * 1000); return '等了 ' + (a.secs || 1) + ' 秒'; };
  ACT._idle_cleanup = async a => AG.idleCleanup(!!a.instant);
  function fitSpot(w) {   // 缩小到合适大小再放进不压群聊 / 歌词的空地（整个窗口都看得见）；放不下返回 null
    const T = targetRects(), resizable = w.state === 'normal' && !(w.o && (w.o.resizable === false || w.nomax));
    const sizes = [[w.rect.w, w.rect.h]]; if (resizable) { sizes.push([Math.min(w.rect.w, 480), Math.min(w.rect.h, 320)]); sizes.push([(w.o && w.o.minW) || 220, (w.o && w.o.minH) || 120]); }
    for (const [ww, hh] of sizes) { const b = bestSpot(w, T, ww, hh); if (b && b.ov <= 0.02 && b.vis >= 0.9) return { b, ww, hh }; }
    const T2 = T.filter(t => t.id === 'qqchat' || t.id === 'lyrics');   // 放不下就退一步：只保证不压群聊 / 歌词（可以压住千千静听）
    if (T2.length < T.length) for (const [ww, hh] of sizes) { const b = bestSpot(w, T2, ww, hh); if (b && b.ov <= 0.02 && b.vis >= 0.9) return { b, ww, hh }; }
    return null;
  }
  // 自己玩电脑时的“守卫”：它新开的窗口一冒出来（每 40ms 检查）就直接放到空地，不让它压着群聊哪怕一秒；放不下的交给 _idle_clear 慢慢挪
  AG.idleGuard = function () {
    const j = AG.cur; if (!j || !j.idle || j.aborted || AG.cfg.idle_avoid_cover === false) return;
    for (const w of findWins('blocking')) {
      if (w._guarded || w.state !== 'normal' || typeof w._apply !== 'function' || (AG.cfg.protect || []).includes(w.id) || SYS_APPS.has(AG.appOf(w)) || !AG.openedByJob(w)) continue;
      w._guarded = true;
      const fit = fitSpot(w); if (!fit) continue;
      w.rect = { x: fit.b.x, y: fit.b.y, w: fit.ww, h: fit.hh }; w._apply();
    }
  };
  ACT._idle_clear = async () => {   // 它自己打开的窗口不能挡住群聊 / 歌词：挪开，挪不开（太大）就最小化；观众自己开的窗口不碰
    if (AG.cfg.idle_avoid_cover === false) return '不处理遮挡';
    const mine = () => findWins('blocking').filter(w => AG.openedByJob(w) && !(AG.cfg.protect || []).includes(w.id) && !SYS_APPS.has(AG.appOf(w)));
    const done = [];
    for (let pass = 0; pass < 2; pass++) {
      const list = mine(); if (!list.length) break;
      for (const w of list) {
        try {
          // 先试“缩小到最小再放进空地”（整个窗口都看得见、不压任何东西）；放不下才退回 move_away（拖到屏幕边上露一截 / 最小化）
          const fit = fitSpot(w);
          if (fit) { if (Math.abs(fit.ww - w.rect.w) > 2 || Math.abs(fit.hh - w.rect.h) > 2) await ACT.resize_window({ target: w.id, w: fit.ww, h: fit.hh }); await dragWindowTo(w, fit.b.x, fit.b.y); done.push('放到空地 ' + labelOf(w)); }
          else done.push(await ACT.move_away({ target: w.id }));
        } catch (e) { if (AG.cur && AG.cur.aborted) throw e; }
      }
    }
    return done.length ? done.join('；') : '没有挡住直播画面';
  };
  ACT._hover_song = async () => {   // 光标在酷狗 / 千千静听的歌名和歌词上晃一晃，像在看歌
    const w = ['kugou', 'ttplayer'].map(k => findWins(k).find(x => !x.dialogOnly && winVisible(x))).find(Boolean); if (!w) fail('没有可看的播放器窗口');
    await raise(w);
    const cands = [...w.el.querySelectorAll('.ttl, .lrc, .lyric, .lines, #tt-title, #tt-lrc, canvas, .cover')].filter(e => shown(e) && livePoint(e));
    const tgt = cands.slice(0, 3); if (!tgt.length) { const r = drect(w.el); await move(r.x + r.w * .5, r.y + r.h * .4); return '看了看 ' + (w.title || '播放器'); }
    for (const e of tgt) { const p = livePoint(e, .5, .5); if (p) { await move(p.x, p.y); await sleep(500); } }
    return '看了看歌名和歌词';
  };
  ACT._peek_menu = async () => {   // 打开游戏后，光标在主菜单里逛一圈（不点）
    const w = WM.wins.filter(x => /^game-/.test(x.id) && !x.closed).pop(); if (!w) fail('没有游戏窗口');
    await raise(w);
    const mi = await waitFor(() => { const m = w.el.querySelector('.gm .menu'); if (!m || m.style.display === 'none' || !shown(m)) return null; const it = [...m.querySelectorAll('.mi')].filter(e => livePoint(e)); return it.length ? it : null; }, 5000);
    if (!mi) return '游戏菜单没显示出来'; const n = Math.min(3, mi.length);
    for (let i = 0; i < n; i++) { const e = mi[Math.floor(Math.random() * mi.length)]; await hoverEl(e); await sleep(450); }
    return '在游戏菜单里看了看';
  };
  ACT.qq_private = async a => {   // 打开 QQ（自动登录）→ 双击好友 → 在私聊窗口打字发送 → 等对方回
    let panel = WM.byId['qq-panel'] && !WM.byId['qq-panel'].closed ? WM.byId['qq-panel'] : null, route = '';
    if (!panel) {
      let lw = WM.byId['qq-login'] && !WM.byId['qq-login'].closed ? WM.byId['qq-login'] : null;
      if (!lw && !(WM.byId['qq-logging'] && !WM.byId['qq-logging'].closed)) { await openApp('qq'); lw = await waitFor(() => WM.byId['qq-login'] && !WM.byId['qq-login'].closed && WM.byId['qq-login'], 3000); }
      if (lw) { const b = lw.el.querySelector('#loginBtn'); if (!b) fail('QQ 登录按钮没找到'); await raise(lw).catch(() => {}); await clickEl(b); route = '登录 '; }
      panel = await waitFor(() => WM.byId['qq-panel'] && !WM.byId['qq-panel'].closed && WM.byId['qq-panel'], 6000); if (!panel) fail('QQ 没登录进去');
      await sleep(250);
    }
    const tidy = async () => { if (AG.cur && AG.cur.idle) await ACT._idle_clear(); };   // 自己玩电脑时：每开一个窗口就先让开，别压着群聊
    await tidy(); await raise(panel);   // QQ 面板在最右边，会被群聊窗口压住一部分：先拉到最上面
    const items = () => [...panel.el.querySelectorAll('.qq-friend-item')];
    let vis = items().filter(e => shown(e)); if (!vis.length) { const g = panel.el.querySelector('.qq-friend-group'); if (g) { await clickEl(g); await sleep(250); vis = items().filter(e => shown(e)); } }
    if (!vis.length) fail('QQ 好友列表是空的');
    const nm = e => txt(e.querySelector('.qq-friend-name') || e);
    let it = a.friend ? vis.find(e => nm(e).includes(a.friend)) : null; { const okv = vis.filter(e => livePoint(e, .5, .5)); const pool = okv.length ? okv : vis; it = it || pool[Math.floor(Math.random() * pool.length)]; }   // 随机挑一个没被盖住 / 没滚出去的好友
    const fname = nm(it), cid = 'qq-chat-' + fname; let cw = WM.byId[cid] && !WM.byId[cid].closed ? WM.byId[cid] : null;
    if (!cw) { const p = livePoint(it, .5, .5); if (!p) fail('好友被盖住了'); await dblclick(p.x, p.y); cw = await waitFor(() => WM.byId[cid] && !WM.byId[cid].closed && WM.byId[cid], 2500); if (!cw) fail('没能打开和 ' + fname + ' 的聊天窗口'); await tidy(); await sleep(900); }
    else await raise(cw);
    await tidy(); const ta = cw.el.querySelector('.qq-im-chat-send'), sb = cw.el.querySelector('#btn-send-msg'); if (!ta || !sb) fail('聊天窗口没有输入框');
    await clickEl(ta); await typeText(ta, a.text); await sleep(200); await clickEl(sb); await sleep(1900);
    return route + '和 ' + fname + ' 聊了：' + a.text.slice(0, 20);
  };
})();
