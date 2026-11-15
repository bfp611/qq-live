// 扫雷（Windows XP 经典版复刻）：素材取自 ShizukuIchi/winXP (MIT) 的 minesweeper 图片
(function () {
  if (!window.WM || !WM.ready) return;
  const { h } = WM, M = 'xp/mine/';
  const st = document.createElement('style'); st.textContent = `
  .mw { position:absolute; inset:0; background:#c0c0c0; display:flex; flex-direction:column; }
  .mw .mg { margin:6px; padding:6px; border:3px solid; border-color:#fff #808080 #808080 #fff; display:flex; flex-direction:column; gap:6px; background:#c0c0c0; }
  .mw .hd { display:flex; align-items:center; justify-content:space-between; border:2px solid; border-color:#808080 #fff #fff #808080; padding:4px 6px; height:37px; box-sizing:border-box; }
  .mw .dg { display:flex; background:#000; border:1px solid; border-color:#808080 #fff #fff #808080; } .mw .dg img { width:13px; height:23px; display:block; image-rendering:pixelated; }
  .mw .face { width:26px; height:26px; border:2px solid; border-color:#fff #808080 #808080 #fff; display:flex; align-items:center; justify-content:center; box-sizing:border-box; background:#c0c0c0; } .mw .face:active { border-color:#808080; } .mw .face img { width:17px; height:17px; image-rendering:pixelated; }
  .mw .bd { display:grid; border:3px solid; border-color:#808080 #fff #fff #808080; width:max-content; }
  .mw .c { width:16px; height:16px; box-sizing:border-box; background:#c0c0c0; border:2px solid; border-color:#fff #808080 #808080 #fff; } .mw .c.o { border:1px solid #808080; border-width:1px 0 0 1px; } .mw .c img { width:16px; height:16px; display:block; margin:-2px; image-rendering:pixelated; } .mw .c.o img { margin:-1px 0 0 -1px; } .mw .c.dn { border:1px solid #808080; border-width:1px 0 0 1px; }
  `; document.head.appendChild(st);
  const LV = { beginner: [9, 9, 10], intermediate: [16, 16, 40], expert: [30, 16, 99] };
  WM.register('minesweeper', { open: () => {
    let lv = 'beginner', W = 9, H = 9, N = 10, cells, state, over, first, flags, secs, timer, down = false;
    const bd = h('div', { class: 'bd' }), face = h('div', { class: 'face' }, [h('img', { src: M + 'smile.png' })]), dm = h('div', { class: 'dg' }), dt = h('div', { class: 'dg' });
    const digits = (el, n) => { n = Math.max(-99, Math.min(999, n)); const s = n < 0 ? '-' + String(-n).padStart(2, '0') : String(n).padStart(3, '0'); el.innerHTML = ''; [...s].forEach(c => el.appendChild(h('img', { src: M + 'digit' + (c === '-' ? '-' : c) + '.png' }))); };
    function newGame(l) { if (l) lv = l; [W, H, N] = LV[lv]; cells = Array.from({ length: W * H }, () => ({ m: false, o: false, f: 0, n: 0 })); over = false; first = true; flags = 0; secs = 0; clearInterval(timer); face.firstChild.src = M + 'smile.png'; bd.style.gridTemplateColumns = `repeat(${W},16px)`; draw(); w && w.resizeTo && 0; if (w) { const r = w.rect; r.w = W * 16 + 46; r.h = H * 16 + 138; w._apply(); } }
    const nb = i => { const x = i % W, y = (i / W) | 0, out = []; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { if (!dx && !dy) continue; const X = x + dx, Y = y + dy; if (X >= 0 && X < W && Y >= 0 && Y < H) out.push(Y * W + X); } return out; };
    function place(safe) { let k = 0; while (k < N) { const i = Math.floor(Math.random() * W * H); if (i === safe || cells[i].m || nb(safe).includes(i)) continue; cells[i].m = true; k++; } cells.forEach((c, i) => c.n = nb(i).filter(j => cells[j].m).length); }
    function open(i) { const c = cells[i]; if (c.o || c.f === 1) return; if (first) { place(i); first = false; timer = setInterval(() => { secs++; digits(dt, secs); }, 1000); } c.o = true; if (c.m) { c.boom = true; lose(); return; } if (!c.n) nb(i).forEach(open); }
    function lose() { over = true; clearInterval(timer); face.firstChild.src = M + 'dead.png'; cells.forEach(c => { if (c.m && c.f !== 1) c.o = true; }); }
    function check() { if (!over && cells.every(c => c.m || c.o)) { over = true; clearInterval(timer); face.firstChild.src = M + 'win.png'; cells.forEach(c => { if (c.m) c.f = 1; }); flags = N; } }
    function draw() { digits(dm, N - flags); digits(dt, secs); bd.innerHTML = ''; cells.forEach((c, i) => { const e = h('div', { class: 'c' + (c.o ? ' o' : '') }); let img = null; if (c.o) img = c.boom ? 'mine-death' : c.m ? 'mine-ceil' : c.n ? 'open' + c.n : null; else if (over && c.f === 1 && !c.m) img = 'misflagged'; else if (c.f === 1) img = 'flag'; else if (c.f === 2) img = 'question'; if (img) e.appendChild(h('img', { src: M + img + '.png', draggable: 'false' })); e.addEventListener('pointerdown', ev => { if (over) return; if (ev.button === 0) { face.firstChild.src = M + 'ohh.png'; down = true; } }); e.addEventListener('pointerup', ev => { face.firstChild.src = over ? face.firstChild.getAttribute('src') : M + 'smile.png'; if (over || !down) return; down = false; if (ev.button === 0) { open(i); check(); draw(); } }); e.addEventListener('contextmenu', ev => { ev.preventDefault(); ev.stopPropagation(); if (over || c.o) return; c.f = (c.f + 1) % 3; flags = cells.filter(x => x.f === 1).length; draw(); }); e.addEventListener('dblclick', () => { if (over || !c.o || !c.n) return; const ns = nb(i); if (ns.filter(j => cells[j].f === 1).length === c.n) { ns.forEach(open); check(); draw(); } }); bd.appendChild(e); }); }
    face.addEventListener('click', () => newGame());
    const mbar = WM.menubar([{ t: '游戏(G)', items: () => [{ t: '开局(N)', key: 'F2', on: () => newGame() }, '-', ...[['beginner', '初级(B)'], ['intermediate', '中级(I)'], ['expert', '高级(E)']].map(([k, t]) => ({ t, radio: true, chk: lv === k, on: () => newGame(k) })), '-', { t: '退出(X)', on: () => w.close() }] }, { t: '帮助(H)', items: () => [{ t: '关于扫雷(A)...', on: () => WM.alert('关于扫雷', 'Microsoft 扫雷 (演示复刻)', { kind: 'info' }) }] }]);
    const el = h('div', { class: 'mw' }, [mbar, h('div', { class: 'mg' }, [h('div', { class: 'hd' }, [dm, face, dt]), bd])]);
    let w = WM.create({ id: 'minesweeper', title: '扫雷', icon: M + 'mine-icon.png', w: 190, h: 282, resizable: false, content: () => el }); newGame();
    // 给桌面 Agent 的只读接口：棋盘上看得见的信息（-1 没开 / -2 旗 / 0-8 数字），不暴露雷的位置
    w.mine = { bd, state: () => ({ W, H, N, lv, over, first, flags, cells: cells.map(c => c.o ? c.n : c.f === 1 ? -2 : -1) }) };
    return w;
  } });
})();
