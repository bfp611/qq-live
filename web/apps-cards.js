// 纸牌（Klondike）与空当接龙（FreeCell）：可玩的 Windows XP 经典纸牌游戏复刻。
// 牌面 / 牌背 / 空位图：DualBrain/Solitaire (MIT, Cory Smith) 的 XP 风格牌组（web/xp/cards/）。空当接龙发牌用的是微软原版的 32000 副牌编号算法（游戏编号 1~32000，和真正的 FreeCell 同号同牌）。
(function () {
  if (!window.WM || !WM.ready) return;
  const { h, ICO } = WM, CD = 'xp/cards/', CW = 71, CH = 96, SU = ['Club', 'Diamond', 'Heart', 'Spade'], RK = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'], SYM = ['♣', '♦', '♥', '♠'];
  const st = document.createElement('style'); st.textContent = `
  .cg { position:absolute; inset:0; background:#008000; display:flex; flex-direction:column; font:12px var(--xpfont); user-select:none; }
  .cg .xp-menubar { background:#ece9d8; flex:none; } .cg .bd { position:relative; flex:1; overflow:hidden; touch-action:none; } .cg .sb { height:22px; flex:none; background:#ece9d8; border-top:1px solid #aca899; display:flex; line-height:20px; } .cg .sb div { padding:0 8px; border-right:1px solid #aca899; white-space:nowrap; } .cg .sb div:first-child { flex:1; }
  .cg .card, .cg .slot { position:absolute; width:${CW}px; height:${CH}px; image-rendering:auto; -webkit-user-drag:none; } .cg .card { transition:left .16s,top .16s; cursor:default; } .cg .card.drag, .cg.nodrag .card { transition:none; } .cg .slot { opacity:.9; } .cg .card.sel { filter:brightness(.6) sepia(1) hue-rotate(190deg) saturate(3); } .cg .hint { position:absolute; border:2px solid #ff0; border-radius:4px; pointer-events:none; z-index:9000; }
  .cg canvas.win { position:absolute; inset:0; z-index:9500; }
  .cg .bk { display:inline-block; width:50px; height:68px; margin:4px; border:2px solid transparent; vertical-align:top; } .cg .bk.on { border-color:#316ac5; } .cg .bk img { width:46px; height:64px; display:block; margin:0; }
  `; document.head.appendChild(st);
  const imgs = {}; const img = src => imgs[src] || (imgs[src] = Object.assign(new Image(), { src }));
  const faceSrc = (s, r) => CD + SU[s] + '_' + r + '.png';
  let BACK = 6; try { const b = parseInt(localStorage.getItem('xp.cardback')); if (b >= 0 && b < 12) BACK = b; } catch (e) {}
  const backSrc = () => CD + 'CardBack_' + BACK + '.png';
  const red = s => s === 1 || s === 2;
  const lbl = c => c ? SYM[c.s] + RK[c.r] : '';
  for (let s = 0; s < 4; s++) for (let r = 0; r < 13; r++) img(faceSrc(s, r)); img(backSrc());
  let gseq = 0;
  // ---------- 公共：牌元素、拖拽、胜利动画、牌背选择 ----------
  function mkCard(s, r) { const c = { s, r, up: false, id: s * 13 + r }; c.el = h('img', { class: 'card', draggable: 'false', 'data-id': c.id, src: backSrc() }); return c; }
  function setFace(c) { const src = c.up ? faceSrc(c.s, c.r) : backSrc(); if (c.el.getAttribute('src') !== src) c.el.src = src; c.el.setAttribute('data-up', c.up ? 1 : 0); c.el.title = c.up ? SYM[c.s] + RK[c.r] : ''; }
  function attach(bd, G) {   // 拖拽 / 点击 / 双击
    let d = null;
    const sc = () => { const r = bd.getBoundingClientRect(); return { k: r.width / (bd.offsetWidth || 1) || 1, l: r.left, t: r.top }; };
    bd.addEventListener('pointerdown', e => {
      if (e.button) return; const el = e.target.closest('.card, .slot'); if (!el || !bd.contains(el)) { G.blank && G.blank(); return; }
      const cs = el.classList.contains('card') ? G.grab(el) : null, p = sc();
      d = { el, cs, x0: e.clientX, y0: e.clientY, moved: false, p, orig: cs ? cs.map(c => [c.el.offsetLeft, c.el.offsetTop, c.el.style.zIndex]) : [] };
      if (!cs) { d.slot = el; }
    });
    document.addEventListener('pointermove', e => {
      if (!d || !d.cs) return; const dx = (e.clientX - d.x0) / d.p.k, dy = (e.clientY - d.y0) / d.p.k;
      if (!d.moved && Math.hypot(dx, dy) < 4) return; d.moved = true;
      d.cs.forEach((c, i) => { c.el.classList.add('drag'); c.el.style.left = (d.orig[i][0] + dx) + 'px'; c.el.style.top = (d.orig[i][1] + dy) + 'px'; c.el.style.zIndex = 8000 + i; });
    }, true);
    document.addEventListener('pointerup', e => {
      if (!d) return; const x = d; d = null;
      if (x.cs) x.cs.forEach(c => c.el.classList.remove('drag'));
      if (x.moved && x.cs) { const r = x.cs[0].el.getBoundingClientRect(), p = sc(); G.drop(x.cs, { x: (r.left - p.l) / p.k, y: (r.top - p.t) / p.k }); }
      else if (G.tap) G.tap(x.slot || x.el, x.cs);
      G.render();
    }, true);
    bd.addEventListener('dblclick', e => { const el = e.target.closest('.card'); if (el && G.dbl) { G.dbl(el); G.render(); } });
  }
  function hitPile(box, rects) { let best = null, ba = 0; for (const r of rects) { const w = Math.min(box.x + CW, r.x + r.w) - Math.max(box.x, r.x), hh = Math.min(box.y + CH, r.y + r.h) - Math.max(box.y, r.y); if (w > 0 && hh > 0 && w * hh > ba) { ba = w * hh; best = r; } } return ba > CW * CH * .12 ? best : null; }
  function winAnim(bd, list, done) {   // 经典的“卡牌弹跳”胜利动画：牌从基础堆里依次飞出来，落地反弹，不清屏（留下轨迹）
    const cvs = h('canvas', { class: 'win' }); cvs.width = bd.offsetWidth; cvs.height = bd.offsetHeight; bd.appendChild(cvs); const g = cvs.getContext('2d'), W = cvs.width, H = cvs.height;
    const q = list.slice(), act = []; let n = 0, raf = null, alive = true, tm = null;
    const stop = () => { if (!alive) return; alive = false; clearInterval(tm); cvs.remove(); done && done(); };
    cvs.addEventListener('pointerdown', stop);
    tm = setInterval(() => {
      if (n % 7 === 0 && q.length) { const c = q.shift(); act.push({ c, x: c.x, y: c.y, vx: (Math.random() < .5 ? -1 : 1) * (2 + Math.random() * 4), vy: -Math.random() * 4 }); } n++;
      for (let i = act.length - 1; i >= 0; i--) { const a = act[i]; a.vy += .55; a.x += a.vx; a.y += a.vy; if (a.y + CH > H) { a.y = H - CH; a.vy = -a.vy * .85; if (Math.abs(a.vy) < 1) a.vy = -1; } g.drawImage(img(faceSrc(a.c.s, a.c.r)), Math.round(a.x), Math.round(a.y)); if (a.x < -CW || a.x > W + CW) act.splice(i, 1); }
      if (!q.length && !act.length) setTimeout(stop, 400);
    }, 16);
    return stop;
  }
  function chooseBack(rerender) {
    WM.dialog({ id: 'cardback', title: '选择牌背', icon: ICO('318_16.png'), w: 340, h: 300, modal: true, content: w => {
      let sel = BACK; const box = h('div', { style: 'padding:6px' }), draw = () => { box.innerHTML = ''; for (let i = 0; i < 12; i++) { const b = h('div', { class: 'bk' + (i === sel ? ' on' : ''), 'data-back': i }, [h('img', { src: CD + 'CardBack_' + i + '.png' })]); b.addEventListener('click', () => { sel = i; draw(); }); b.addEventListener('dblclick', () => ok()); box.appendChild(b); } };
      const ok = () => { BACK = sel; try { localStorage.setItem('xp.cardback', sel); } catch (e) {} w.close(); rerender(); }; draw();
      return h('div', { class: 'xpd', style: 'background:#ece9d8' }, [h('div', { text: '请选择牌背：' }), box, h('div', { style: 'position:absolute;right:10px;bottom:10px;display:flex;gap:6px' }, [h('button', { class: 'xbtn def', text: '确定', onclick: ok }), h('button', { class: 'xbtn', text: '取消', onclick: () => w.close() })])]);
    } });
  }
  const aboutBox = t => WM.alert('关于' + t, 'Microsoft (R) Windows (R) ' + t + '\n版本 5.1 (内部版本号 2600)\n\n牌面素材：DualBrain/Solitaire (MIT)', { kind: 'info' });

  // ======================================================= 纸牌 (Klondike) =======================================================
  WM.register('solitaire', { open: () => {
    const X0 = 10, GX = 81, YT = 10, YB = 122;
    const cards = []; for (let s = 0; s < 4; s++) for (let r = 0; r < 13; r++) cards.push(mkCard(s, r));
    const O = { draw3: false, score: true, timer: true };
    let stock, waste, found, tab, score, moves, secs, timer, won, undo, wstop, bdH = 340, drawsIdle = 0;
    const bd = h('div', { class: 'bd' }), stat = h('div', { class: 'sb' }, [h('div', { text: '' }), h('div', { text: '', style: 'min-width:70px' }), h('div', { text: '', style: 'min-width:70px;border:0' })]);
    const slots = {}; const addSlot = (id, x, y, img0) => { const e = h('img', { class: 'slot', 'data-pile': id, src: CD + img0, draggable: 'false', style: `left:${x}px;top:${y}px` }); bd.appendChild(e); slots[id] = e; return e; };
    addSlot('stock', X0, YT, 'CardSlot_1.png'); addSlot('waste', X0 + GX, YT, 'CardSlot_2.png');
    for (let i = 0; i < 4; i++) addSlot('found' + i, X0 + GX * (3 + i), YT, 'CardSlot_2.png');
    for (let i = 0; i < 7; i++) addSlot('tab' + i, X0 + GX * i, YB, 'CardSlot_2.png');
    cards.forEach(c => bd.appendChild(c.el));
    const snapshot = () => JSON.stringify({ stock: stock.map(c => [c.id, c.up]), waste: waste.map(c => [c.id, c.up]), found: found.map(p => p.map(c => [c.id, c.up])), tab: tab.map(p => p.map(c => [c.id, c.up])), score, moves });
    const restore = js => { const S = JSON.parse(js), by = a => a.map(([id, up]) => { cards[id].up = up; return cards[id]; }); stock = by(S.stock); waste = by(S.waste); found = S.found.map(by); tab = S.tab.map(by); score = S.score; moves = S.moves; };
    function newGame() {
      stopWin(); const ds = cards.slice(); for (let i = ds.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [ds[i], ds[j]] = [ds[j], ds[i]]; }
      ds.forEach(c => c.up = false); tab = []; let k = 0; for (let i = 0; i < 7; i++) { tab.push(ds.slice(k, k + i + 1)); k += i + 1; tab[i][i].up = true; }
      stock = ds.slice(k); waste = []; found = [[], [], [], []]; score = 0; moves = 0; secs = 0; won = false; undo = []; drawsIdle = 0; clearInterval(timer); timer = null; sel = null; render();
      cards.forEach(c => { c.el.style.transition = 'none'; c.el.style.left = X0 + 'px'; c.el.style.top = YT + 'px'; }); void bd.offsetWidth; cards.forEach(c => { c.el.style.transition = ''; }); render();
    }
    let sel = null;
    function render() {
      bdH = bd.offsetHeight || bdH; const fs = [];
      const put = (c, x, y, z) => { setFace(c); c.el.style.left = x + 'px'; c.el.style.top = y + 'px'; c.el.style.zIndex = z; c.el.classList.toggle('sel', !!sel && sel === c); };
      stock.forEach((c, i) => put(c, X0, YT, i + 1));
      waste.forEach((c, i) => { const f = waste.length - 1 - i; put(c, X0 + GX + (O.draw3 && f < 3 ? (2 - f) * 14 : (O.draw3 ? 0 : 0)), YT, 100 + i); });
      if (O.draw3) waste.forEach((c, i) => { const f = waste.length - 1 - i; c.el.style.left = (X0 + GX + (f < 3 ? (Math.min(2, waste.length - 1) - f) * 14 : 0)) + 'px'; });
      found.forEach((p, i) => p.forEach((c, j) => put(c, X0 + GX * (3 + i), YT, 200 + j)));
      tab.forEach((p, i) => { const downs = p.filter(c => !c.up).length, ups = p.length - downs, avail = bdH - YB - CH - 8 - downs * 4, gu = ups > 1 ? Math.max(7, Math.min(17, avail / (ups - 1))) : 17; let y = YB; p.forEach((c, j) => { put(c, X0 + GX * i, y, 300 + j); y += c.up ? gu : 4; }); slots['tab' + i].dataset.bottom = y; });
      slots.stock.src = CD + (stock.length ? 'CardSlot_2.png' : waste.length ? 'CardSlot_0.png' : 'CardSlot_1.png');
      stat.children[0].textContent = won ? '恭喜，您赢了！' : ''; stat.children[1].textContent = O.score ? '分数: ' + score : ''; stat.children[2].textContent = O.timer ? '时间: ' + secs : '';
    }
    const tick = () => { if (!timer && !won) timer = setInterval(() => { secs++; stat.children[2].textContent = O.timer ? '时间: ' + secs : ''; }, 1000); };
    // ---- 规则 ----
    const pileOf = c => { if (stock.includes(c)) return ['stock', 0]; if (waste.includes(c)) return ['waste', 0]; for (let i = 0; i < 4; i++) if (found[i].includes(c)) return ['found', i]; for (let i = 0; i < 7; i++) if (tab[i].includes(c)) return ['tab', i]; return [null, 0]; };
    const canTab = (cs, i) => { const t = tab[i], c = cs[0]; if (!t.length) return c.r === 12; const top = t[t.length - 1]; return top.up && red(top.s) !== red(c.s) && top.r === c.r + 1; };
    const foundSlot = c => { let e = -1; for (let i = 0; i < 4; i++) { const p = found[i]; if (p.length ? (p[0].s === c.s && p[p.length - 1].r === c.r - 1) : (c.r === 0 && e < 0)) { if (p.length) return i; e = i; } } return e; };
    function exec(cs, to) {   // to = ['tab', i] | ['found', i]；返回是否成功
      const [pn, pi] = pileOf(cs[0]), src = pn === 'waste' ? waste : pn === 'tab' ? tab[pi] : pn === 'found' ? found[pi] : null; if (!src) return false;
      let ok = false, delta = 0;
      if (to[0] === 'tab') { if (pn === 'tab' && pi === to[1]) return false; if (!canTab(cs, to[1])) return false; ok = true; delta = pn === 'waste' ? 5 : pn === 'found' ? -15 : 0; }
      else if (to[0] === 'found') { if (cs.length !== 1 || src[src.length - 1] !== cs[0]) return false; const i = foundSlot(cs[0]); if (i < 0 || (to[1] != null && to[1] >= 0 && found[to[1]].length && to[1] !== i)) return false; to = ['found', i]; ok = true; delta = pn === 'found' ? 0 : 10; }
      if (!ok) return false;
      undo.push(snapshot()); if (undo.length > 200) undo.shift(); tick(); drawsIdle = 0;
      src.splice(src.length - cs.length, cs.length); (to[0] === 'tab' ? tab[to[1]] : found[to[1]]).push(...cs);
      if (pn === 'tab' && src.length && !src[src.length - 1].up) { src[src.length - 1].up = true; delta += 5; }
      score = Math.max(0, score + delta); moves++; sel = null; checkWin(); return true;
    }
    function draw() {
      if (won) return false; undo.push(snapshot()); tick();
      if (stock.length) { for (let n = 0; n < (O.draw3 ? 3 : 1) && stock.length; n++) { const c = stock.pop(); c.up = true; waste.push(c); } }
      else if (waste.length) { while (waste.length) { const c = waste.pop(); c.up = false; stock.push(c); } if (O.score && !O.draw3) score = Math.max(0, score - 100); }
      else { undo.pop(); return false; }
      moves++; drawsIdle++; sel = null; return true;
    }
    function checkWin() { if (won || !found.every(p => p.length === 13)) return; won = true; clearInterval(timer); timer = null; render(); const list = []; for (let j = 12; j >= 0; j--) for (let i = 3; i >= 0; i--) list.push({ s: found[i][0].s, r: found[i][j].r, x: X0 + GX * (3 + i), y: YT }); if (window.XP) XP.snd('notify', 'game'); wstop = winAnim(bd, list, () => { wstop = null; WM.confirm('纸牌', '恭喜！您赢了！\n\n再来一局吗？', newGame, () => {}); }); }
    function stopWin() { if (wstop) { const f = wstop; wstop = null; f(); } }
    const piles = () => { const r = []; for (let i = 0; i < 7; i++) r.push({ id: ['tab', i], x: X0 + GX * i, y: YB, w: CW, h: Math.max(CH, (+slots['tab' + i].dataset.bottom || YB) - YB + CH) }); for (let i = 0; i < 4; i++) r.push({ id: ['found', i], x: X0 + GX * (3 + i), y: YT, w: CW, h: CH }); return r; };
    const G = {
      grab(el) { if (won) return null; const c = cards[+el.dataset.id], [pn, pi] = pileOf(c); if (pn === 'stock') return null; if (pn === 'waste') return waste[waste.length - 1] === c ? [c] : null; if (!c.up) return null; if (pn === 'found') return found[pi][found[pi].length - 1] === c ? [c] : null; const p = tab[pi]; return p.slice(p.indexOf(c)); },
      drop(cs, pos) { const t = hitPile(pos, piles()); if (t) exec(cs, t.id); },
      tap(el, cs) { const id = el.dataset.pile; const c = el.classList.contains('card') ? cards[+el.dataset.id] : null; const pn = c ? pileOf(c)[0] : id; if (pn === 'stock') draw(); else if (c && !c.up && pileOf(c)[0] === 'tab') { const [, i] = pileOf(c); if (tab[i][tab[i].length - 1] === c) { c.up = true; score += 5; moves++; } } },
      dbl(el) { const c = cards[+el.dataset.id]; if (!c.up) return; const [pn] = pileOf(c); if (pn === 'tab' || pn === 'waste') { const src = pn === 'tab' ? tab[pileOf(c)[1]] : waste; if (src[src.length - 1] === c) exec([c], ['found', -1]); } },
      render, blank() {},
    };
    attach(bd, G);
    const doUndo = () => { if (!undo.length || won) return; restore(undo.pop()); score = Math.max(0, score - (O.score ? 0 : 0)); render(); };
    const opt = () => WM.dialog({ id: 'solopt', title: '选项', icon: ICO('318_16.png'), w: 300, h: 230, modal: true, content: w => {
      const rd = (name, labels, cur) => labels.map((t, i) => h('div', { style: 'margin:3px 0' }, [h('input', { type: 'radio', name, checked: i === cur, 'data-v': i }), h('label', { text: ' ' + t })]));
      const a = rd('dr', ['翻一张牌(1)', '翻三张牌(3)'], O.draw3 ? 1 : 0), b = rd('sc', ['标准计分(S)', '无计分(N)'], O.score ? 0 : 1);
      const tm = h('input', { type: 'checkbox', checked: O.timer }); const ok = () => { const nd = a[1].firstChild.checked; O.score = b[0].firstChild.checked; O.timer = tm.checked; if (nd !== O.draw3) { O.draw3 = nd; w.close(); newGame(); return; } w.close(); render(); };
      return h('div', { class: 'xpd' }, [h('div', { class: 'xgroup' }, [h('legend', { text: '翻牌' })].concat(a)), h('div', { class: 'xgroup', style: 'margin-top:12px' }, [h('legend', { text: '计分' })].concat(b)), h('div', { style: 'margin-top:8px' }, [tm, h('label', { text: ' 计时(T)' })]),
        h('div', { style: 'position:absolute;right:10px;bottom:8px;display:flex;gap:6px' }, [h('button', { class: 'xbtn def', text: '确定', onclick: ok }), h('button', { class: 'xbtn', text: '取消', onclick: () => w.close() })])]);
    } });
    const deal = () => { if (!moves || won) return newGame(); WM.confirm('纸牌', '要放弃这一局，开始新的一局吗？', newGame, () => {}); };
    const mbar = WM.menubar([
      { t: '游戏(G)', items: () => [{ t: '发牌(D)', key: 'F2', on: deal }, { t: '撤消(U)', key: 'Ctrl+Z', on: doUndo, dis: !undo.length }, '-', { t: '牌背(B)...', on: () => chooseBack(render) }, { t: '选项(O)...', on: opt }, '-', { t: '退出(X)', on: () => win.close() }] },
      { t: '帮助(H)', items: () => [{ t: '帮助主题(H)', on: () => WM.open('help') }, '-', { t: '关于纸牌(A)', on: () => aboutBox('纸牌') }] }]);
    const kd = e => { if (WM.active !== win) return; if (e.key === 'F2') { e.preventDefault(); deal(); } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); doUndo(); } };
    document.addEventListener('keydown', kd);
    const win = WM.create({ id: 'solitaire', title: '纸牌', icon: ICO('solitaire.png'), w: 604, h: 508, minW: 420, minH: 360, content: () => h('div', { class: 'cg' }, [mbar, bd, stat]),
      onclose: () => { clearInterval(timer); stopWin && wstop && wstop(); document.removeEventListener('keydown', kd); } });
    new ResizeObserver(() => render()).observe(bd); newGame();
    // ---- 给桌面 Agent 的接口 ----
    const slotEl = (k, i) => k === 'tab' ? (tab[i].length ? tab[i][tab[i].length - 1].el : slots['tab' + i]) : slots['found' + i];
    win.sol = {
      bd, slots, cards,
      state: () => ({ game: 'solitaire', won, score, moves, secs, draw3: O.draw3, stock: stock.length, waste: waste.length, wasteTop: lbl(waste[waste.length - 1]), found: found.map(p => p.length), tab: tab.map(p => p.map(c => c.up ? lbl(c) : '?').join(' ')), foundTotal: found.reduce((a, p) => a + p.length, 0), undo: undo.length }),
      newGame, setDraw3: v => { O.draw3 = !!v; newGame(); }, exec, draw, undo: doUndo, render,
      // 下一步建议：{kind:'stock'} | {kind:'dbl', el} | {kind:'drag', el, to, note}；没有就 null
      plan() {
        if (won) return null; const cnt = [0, 1, 2, 3].map(x => { const p = found.find(q => q.length && q[0].s === x); return p ? p.length : 0; });
        const safe = c => c.r <= 1 || [0, 1, 2, 3].filter(x => red(x) !== red(c.s)).every(x => cnt[x] >= c.r);
        const tops = [...tab.map(p => p[p.length - 1]), waste[waste.length - 1]].filter(c => c && c.up);
        for (const c of tops) if (foundSlot(c) >= 0 && safe(c)) return { kind: 'dbl', el: c.el, exec: ['found', -1], cs: [c], note: '送上基础堆 ' + lbl(c) };
        const cand = [];
        for (let i = 0; i < 7; i++) { const p = tab[i], f = p.findIndex(c => c.up); if (f < 0) continue; const cs = p.slice(f);
          for (let t = 0; t < 7; t++) { if (t === i || !canTab(cs, t)) continue; if (f === 0 && (!tab[t].length || cs[0].r === 12)) continue; cand.push({ pri: f > 0 ? (cs[0].r === 12 ? 3.5 : 3) : 1, cs, to: ['tab', t], note: '挪 ' + lbl(cs[0]) + ' 到第 ' + (t + 1) + ' 列' }); } }
        const w = waste[waste.length - 1]; if (w) for (let t = 0; t < 7; t++) if (canTab([w], t)) cand.push({ pri: w.r === 12 ? 2.6 : 2, cs: [w], to: ['tab', t], note: '废牌 ' + lbl(w) + ' 放到第 ' + (t + 1) + ' 列' });
        for (const c of tops) if (foundSlot(c) >= 0) cand.push({ pri: .9, cs: [c], dbl: true, note: '送上基础堆 ' + lbl(c) });
        if (cand.length) { cand.sort((x, y) => y.pri - x.pri); const b = cand[0]; return b.dbl ? { kind: 'dbl', el: b.cs[0].el, exec: ['found', -1], cs: b.cs, note: b.note } : { kind: 'drag', el: b.cs[0].el, to: slotEl(b.to[0], b.to[1]), exec: b.to, cs: b.cs, note: b.note }; }
        if ((stock.length || waste.length > 1) && drawsIdle <= (stock.length + waste.length) / (O.draw3 ? 3 : 1) + 2) return { kind: 'stock', el: stock.length ? stock[stock.length - 1].el : slots.stock, note: stock.length ? '翻牌堆' : '重翻牌堆' };
        return null;
      },
    };
    return win;
  } });

  // ======================================================= 空当接龙 (FreeCell) =======================================================
  function msDeal(n) {   // 微软 FreeCell 原版发牌：返回 52 个牌码（rank*4+suit，suit 顺序 梅花 方块 红桃 黑桃），按顺序依次发到 8 列
    let seed = n >>> 0, wc = 52; const cs = Array.from({ length: 52 }, (_, i) => i), out = [];
    for (let i = 0; i < 52; i++) { seed = (Math.imul(seed, 214013) + 2531011) >>> 0; const j = ((seed >>> 16) & 0x7fff) % wc; out.push(cs[j]); cs[j] = cs[--wc]; }
    return out;
  }
  WM.register('freecell', { open: () => {
    const X0 = 10, GX = 81, YT = 8, YB = 124;
    const cards = []; for (let s = 0; s < 4; s++) for (let r = 0; r < 13; r++) { const c = mkCard(s, r); c.up = true; cards.push(c); }
    let cols, cells, found, gameNo, moves, undo, won, wstop, sel = null, bdH = 380;
    const bd = h('div', { class: 'bd' }), stat = h('div', { class: 'sb' }, [h('div', { text: '' }), h('div', { text: '', style: 'min-width:90px;border:0' })]);
    const slots = {}, addSlot = (id, x, y, im) => { const e = h('img', { class: 'slot', 'data-pile': id, src: CD + im, draggable: 'false', style: `left:${x}px;top:${y}px` }); bd.appendChild(e); slots[id] = e; };
    for (let i = 0; i < 4; i++) { addSlot('cell' + i, X0 + GX * i, YT, 'CardSlot_2.png'); addSlot('found' + i, X0 + GX * (4 + i), YT, 'CardSlot_2.png'); }
    for (let i = 0; i < 8; i++) addSlot('col' + i, X0 + GX * i, YB, 'CardSlot_2.png');
    cards.forEach(c => bd.appendChild(c.el));
    const snapshot = () => JSON.stringify({ cols: cols.map(p => p.map(c => c.id)), cells: cells.map(c => c ? c.id : -1), found: found.map(p => p.map(c => c.id)), moves });
    const restore = js => { const S = JSON.parse(js); cols = S.cols.map(p => p.map(i => cards[i])); cells = S.cells.map(i => i < 0 ? null : cards[i]); found = S.found.map(p => p.map(i => cards[i])); moves = S.moves; };
    const cid = code => cards[(code & 3) * 13 + (code >> 2)];
    function newGame(n) {
      stopWin(); gameNo = n || (1 + Math.floor(Math.random() * 32000)); const dk = msDeal(gameNo); cols = Array.from({ length: 8 }, () => []); dk.forEach((code, i) => cols[i % 8].push(cid(code)));
      cells = [null, null, null, null]; found = [[], [], [], []]; moves = 0; undo = []; won = false; sel = null; win && win.setTitle('空当接龙 - 游戏 #' + gameNo);
      cards.forEach(c => { c.el.style.transition = 'none'; c.el.style.left = X0 + 'px'; c.el.style.top = YT + 'px'; }); render(); void bd.offsetWidth; cards.forEach(c => { c.el.style.transition = ''; }); render();
    }
    function render() {
      bdH = bd.offsetHeight || bdH; const put = (c, x, y, z) => { setFace(c); c.el.style.left = x + 'px'; c.el.style.top = y + 'px'; c.el.style.zIndex = z; c.el.classList.toggle('sel', !!sel && sel.includes(c)); };
      cells.forEach((c, i) => c && put(c, X0 + GX * i, YT, 10)); found.forEach((p, i) => p.forEach((c, j) => put(c, X0 + GX * (4 + i), YT, 20 + j)));
      cols.forEach((p, i) => { const gap = p.length > 1 ? Math.max(12, Math.min(24, (bdH - YB - CH - 8) / (p.length - 1))) : 24; p.forEach((c, j) => put(c, X0 + GX * i, YB + j * gap, 40 + j)); slots['col' + i].dataset.bottom = YB + Math.max(0, p.length - 1) * gap; });
      stat.children[0].textContent = won ? '恭喜，您赢了！' : '游戏 #' + gameNo; stat.children[1].textContent = '移动: ' + moves;
    }
    const where = c => { for (let i = 0; i < 4; i++) if (cells[i] === c) return ['cell', i]; for (let i = 0; i < 4; i++) if (found[i].includes(c)) return ['found', i]; for (let i = 0; i < 8; i++) if (cols[i].includes(c)) return ['col', i]; return [null, 0]; };
    const seqOk = cs => cs.every((c, i) => !i || (red(cs[i - 1].s) !== red(c.s) && cs[i - 1].r === c.r + 1));
    const nFree = () => cells.filter(c => !c).length, nEmpty = skip => cols.filter((p, i) => !p.length && i !== skip).length;
    const maxMove = (destCol) => (nFree() + 1) * Math.pow(2, nEmpty(destCol));
    const fSlot = c => { let e = -1; for (let i = 0; i < 4; i++) { const p = found[i]; if (p.length ? (p[0].s === c.s && p[p.length - 1].r === c.r - 1) : (c.r === 0 && e < 0)) { if (p.length) return i; e = i; } } return e; };
    function exec(cs, to) {
      const [pn, pi] = where(cs[0]); if (!pn || pn === 'found') return false; let ok = false;
      if (to[0] === 'col') { const d = cols[to[1]]; if (pn === 'col' && pi === to[1]) return false; if (!seqOk(cs)) return false; if (cs.length > maxMove(to[1])) return false; if (d.length) { const t = d[d.length - 1]; if (!(red(t.s) !== red(cs[0].s) && t.r === cs[0].r + 1)) return false; } ok = true; }
      else if (to[0] === 'cell') { if (cs.length !== 1) return false; let i = to[1]; if (i == null || i < 0 || cells[i]) i = cells.findIndex(c => !c); if (i < 0) return false; to = ['cell', i]; if (pn === 'cell') return false; ok = true; }
      else if (to[0] === 'found') { if (cs.length !== 1) return false; const i = fSlot(cs[0]); if (i < 0) return false; if (to[1] >= 0 && found[to[1]].length && to[1] !== i) return false; to = ['found', i]; ok = true; }
      if (!ok) return false;
      undo.push(snapshot()); if (undo.length > 300) undo.shift();
      if (pn === 'col') cols[pi].splice(cols[pi].length - cs.length, cs.length); else cells[pi] = null;
      if (to[0] === 'col') cols[to[1]].push(...cs); else if (to[0] === 'cell') cells[to[1]] = cs[0]; else found[to[1]].push(cs[0]);
      moves++; sel = null; checkWin(); return true;
    }
    function checkWin() { if (won || !found.every(p => p.length === 13)) return; won = true; render(); const list = []; for (let j = 12; j >= 0; j--) for (let i = 3; i >= 0; i--) list.push({ s: found[i][0].s, r: found[i][j].r, x: X0 + GX * (4 + i), y: YT }); if (window.XP) XP.snd('notify', 'game'); wstop = winAnim(bd, list, () => { wstop = null; WM.confirm('空当接龙', '恭喜！您赢了！\n\n再来一局吗？', () => newGame(), () => {}); }); }
    function stopWin() { if (wstop) { const f = wstop; wstop = null; f(); } }
    const rects = () => { const r = []; for (let i = 0; i < 8; i++) r.push({ id: ['col', i], x: X0 + GX * i, y: YB, w: CW, h: Math.max(CH, (+slots['col' + i].dataset.bottom || YB) - YB + CH) }); for (let i = 0; i < 4; i++) { r.push({ id: ['cell', i], x: X0 + GX * i, y: YT, w: CW, h: CH }); r.push({ id: ['found', i], x: X0 + GX * (4 + i), y: YT, w: CW, h: CH }); } return r; };
    const G = {
      grab(el) { if (won) return null; const c = cards[+el.dataset.id], [pn, pi] = where(c); if (pn === 'cell') return [c]; if (pn !== 'col') return null; const p = cols[pi], j = p.indexOf(c), cs = p.slice(j); return seqOk(cs) ? cs : [p[p.length - 1]]; },
      drop(cs, pos) { const t = hitPile(pos, rects()); if (!t) return; if (cs.length === 1 && cs[0] !== (cols[where(cs[0])[1]] || []).slice(-1)[0] && where(cs[0])[0] === 'col') return; exec(cs, t.id); },
      tap(el, cs) {   // 点牌选中 → 再点目标
        const c = el.classList.contains('card') ? cards[+el.dataset.id] : null, id = el.dataset.pile;
        if (sel) { let to = null; if (c) { const [pn, pi] = where(c); to = pn === 'col' ? ['col', pi] : pn === 'cell' ? ['cell', pi] : ['found', pi]; } else if (id) { const m = id.match(/^(col|cell|found)(\d)$/); if (m) to = [m[1], +m[2]]; } const s = sel; sel = null; if (to && !(to[0] === 'col' && where(s[0])[0] === 'col' && where(s[0])[1] === to[1])) { if (exec(s, to)) return; } if (c && cs) { sel = cs; } return; }
        if (c && cs) sel = cs;
      },
      dbl(el) { const c = cards[+el.dataset.id]; const [pn, pi] = where(c); if (pn === 'found' || !pn) return; if (pn === 'col' && cols[pi][cols[pi].length - 1] !== c) return; sel = null; if (!exec([c], ['found', -1]) && pn === 'col') exec([c], ['cell', -1]); },
      render, blank() { sel = null; render(); },
    };
    attach(bd, G);
    const doUndo = () => { if (!undo.length || won) return; restore(undo.pop()); sel = null; render(); };
    const pick = () => WM.prompt('选择游戏', '游戏编号（1 ~ 32000）：', String(gameNo), v => { const n = parseInt(v); if (n >= 1 && n <= 32000) newGame(n); else WM.alert('空当接龙', '游戏编号必须在 1 到 32000 之间。', { kind: 'warn' }); });
    const nw = () => { if (!moves || won) return newGame(); WM.confirm('空当接龙', '要放弃这一局，开始新的一局吗？', () => newGame(), () => {}); };
    const mbar = WM.menubar([
      { t: '游戏(G)', items: () => [{ t: '新游戏(N)', key: 'F2', on: nw }, { t: '选择游戏(S)...', on: pick }, { t: '重新开始本局(R)', on: () => newGame(gameNo) }, '-', { t: '撤消(U)', key: 'Ctrl+Z', on: doUndo, dis: !undo.length }, { t: '牌背(B)...', on: () => chooseBack(render) }, '-', { t: '退出(X)', on: () => win.close() }] },
      { t: '帮助(H)', items: () => [{ t: '帮助主题(H)', on: () => WM.open('help') }, '-', { t: '关于空当接龙(A)', on: () => aboutBox('空当接龙') }] }]);
    const kd = e => { if (WM.active !== win) return; if (e.key === 'F2') { e.preventDefault(); nw(); } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); doUndo(); } };
    document.addEventListener('keydown', kd);
    let win = WM.create({ id: 'freecell', title: '空当接龙', icon: ICO('freecell.png'), w: 686, h: 560, minW: 520, minH: 400, content: () => h('div', { class: 'cg' }, [mbar, bd, stat]), onclose: () => { stopWin(); document.removeEventListener('keydown', kd); } });
    new ResizeObserver(() => render()).observe(bd); newGame();
    // ---- 求解器：A* 式最佳优先搜索（单张移动，带“安全上基础堆”），在页面里分片运行不卡画面 ----
    function solve(timeMs) {
      return new Promise(resolve => {
        const t0 = performance.now(), start = { cols: cols.map(p => p.map(c => c.r * 4 + c.s)), cells: cells.map(c => c ? c.r * 4 + c.s : -1).filter(x => x >= 0), found: [0, 0, 0, 0].map((_, s) => { const p = found.find(q => q.length && q[0].s === s); return p ? p.length : 0; }) };
        const key = S => S.cols.map(c => c.join(',')).sort().join('|') + '#' + S.cells.slice().sort((a, b) => a - b).join(',') + '#' + S.found.join(',');
        const isRed = s => s === 1 || s === 2, total = S => S.found[0] + S.found[1] + S.found[2] + S.found[3];
        const hv = S => { let v = (52 - total(S)) * 4 + S.cells.length; for (let s = 0; s < 4; s++) { const need = S.found[s]; if (need >= 13) continue; for (const c of S.cols) { const k = c.findIndex(x => (x >> 2) === need && (x & 3) === s); if (k >= 0) v += (c.length - 1 - k) * 1.2; } } for (const c of S.cols) for (let i = 1; i < c.length; i++) { const a = c[i - 1], b = c[i]; if (!((a >> 2) === (b >> 2) + 1 && isRed(a & 3) !== isRed(b & 3))) v += 0.4; } return v; };
        const safe = (code, S) => { const r = code >> 2, s = code & 3; if (S.found[s] !== r) return false; if (r <= 1) return true; const o = isRed(s) ? [0, 3] : [1, 2]; return S.found[o[0]] >= r && S.found[o[1]] >= r; };
        function expand(S) {
          const out = []; const mk = (cols, cells, fnd, mv, auto) => {   // 自动上安全牌
            let ch = true; mv = mv.slice(); while (ch) { ch = false; for (let i = 0; i < cols.length; i++) { const c = cols[i]; if (c.length && safe(c[c.length - 1], { found: fnd })) { const code = c[c.length - 1]; cols = cols.map((x, k) => k === i ? x.slice(0, -1) : x); fnd = fnd.slice(); fnd[code & 3]++; mv.push([['col', i, code], ['found', code & 3]]); ch = true; } } for (let k = 0; k < cells.length; k++) if (safe(cells[k], { found: fnd })) { const code = cells[k]; cells = cells.filter((_, q) => q !== k); fnd = fnd.slice(); fnd[code & 3]++; mv.push([['cell', k, code], ['found', code & 3]]); ch = true; break; } }
            return { cols, cells, found: fnd, mv }; };
          const nfree = 4 - S.cells.length;
          for (let i = 0; i < S.cols.length; i++) { const c = S.cols[i]; if (!c.length) continue; const code = c[c.length - 1], r = code >> 2, s = code & 3;
            if (S.found[s] === r) { const nf = S.found.slice(); nf[s]++; out.push(mk(S.cols.map((x, k) => k === i ? x.slice(0, -1) : x), S.cells, nf, [[['col', i, code], ['found', s]]])); }
            const seen = new Set(); for (let t = 0; t < S.cols.length; t++) { if (t === i) continue; const d = S.cols[t]; if (!d.length) { if (seen.has('e') || c.length === 1) continue; seen.add('e'); } else { const tc = d[d.length - 1]; if (!((tc >> 2) === r + 1 && isRed(tc & 3) !== isRed(s))) continue; }
              out.push(mk(S.cols.map((x, k) => k === i ? x.slice(0, -1) : k === t ? x.concat(code) : x), S.cells, S.found, [[['col', i, code], ['col', t]]])); }
            if (nfree > 0) out.push(mk(S.cols.map((x, k) => k === i ? x.slice(0, -1) : x), S.cells.concat(code), S.found, [[['col', i, code], ['cell', -1]]])); }
          for (let k = 0; k < S.cells.length; k++) { const code = S.cells[k], r = code >> 2, s = code & 3, rest = S.cells.filter((_, q) => q !== k);
            if (S.found[s] === r) { const nf = S.found.slice(); nf[s]++; out.push(mk(S.cols, rest, nf, [[['cell', k, code], ['found', s]]])); }
            let ee = false; for (let t = 0; t < S.cols.length; t++) { const d = S.cols[t]; if (!d.length) { if (ee) continue; ee = true; } else { const tc = d[d.length - 1]; if (!((tc >> 2) === r + 1 && isRed(tc & 3) !== isRed(s))) continue; }
              out.push(mk(S.cols.map((x, q) => q === t ? x.concat(code) : x), rest, S.found, [[['cell', k, code], ['col', t]]])); } }
          return out;
        }
        const first = { S: Object.assign({}, start), mv: [], g: 0 }; const heap = [[hv(start), 0, first]]; let uid = 1; const seen = new Set([key(start)]); let nodes = 0, best = first;
        const push = it => { heap.push(it); let i = heap.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
        const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { let l = 2 * i + 1, r = l + 1, m = i; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (r < heap.length && heap[r][0] < heap[m][0]) m = r; if (m === i) break; [heap[m], heap[i]] = [heap[i], heap[m]]; i = m; } } return top; };
        (function step() {
          const tEnd = performance.now() + 14;
          while (heap.length && performance.now() < tEnd) {
            const [, , node] = pop(); nodes++; if (total(node.S) === 52) return resolve({ ok: true, moves: node.mv.map(m => m), nodes });
            if (total(node.S) > total(best.S)) best = node;
            for (const nx of expand(node.S)) { const k = key(nx); if (seen.has(k)) continue; seen.add(k); const mv = node.mv.concat(nx.mv); push([hv(nx) * 1.0 + mv.length * 0.15, uid++, { S: { cols: nx.cols, cells: nx.cells, found: nx.found }, mv }]); }
          }
          if (!heap.length || performance.now() - t0 > timeMs || nodes > 400000) return resolve({ ok: false, moves: best.mv, nodes });
          setTimeout(step, 0);
        })();
      });
    }
    const colTop = i => cols[i].length ? cols[i][cols[i].length - 1].el : slots['col' + i];
    win.fc = {
      bd, slots, cards,
      state: () => ({ game: 'freecell', no: gameNo, won, moves, free: nFree(), found: found.map(p => p.length), foundTotal: found.reduce((a, p) => a + p.length, 0), cols: cols.map(p => p.map(lbl).join(' ')), cells: cells.map(lbl), undo: undo.length }),
      newGame, exec, undo: doUndo, render, solve,
      // 把求解器给的单张移动翻译成界面元素：{el, to, exec, kind}
      resolveMove(m) {
        const [fk, fi, code] = m[0], c = cid(code); if (where(c)[0] === null) return null; const [pn, pi] = where(c);
        const to = m[1][0] === 'found' ? { kind: 'dbl', el: c.el } : m[1][0] === 'col' ? { kind: 'drag', el: c.el, to: colTop(m[1][1]), exec: ['col', m[1][1]] } : { kind: 'drag', el: c.el, to: slots['cell' + Math.max(0, cells.findIndex(x => !x))], exec: ['cell', -1] };
        to.card = c; to.note = lbl(c) + (m[1][0] === 'found' ? ' 上基础堆' : m[1][0] === 'col' ? ' 挪到第 ' + (m[1][1] + 1) + ' 列' : ' 放进空当'); return to;
      },
      // 同一个动作直接在页面里执行（agent 没法拖动时的兜底）
      applyMove(m) { const c = cid(m[0][2]); return m[1][0] === 'found' ? exec([c], ['found', -1]) : m[1][0] === 'col' ? exec([c], ['col', m[1][1]]) : exec([c], ['cell', -1]); },
    };
    return win;
  } });
})();
