// 画图（Windows XP 画图的可用复刻）：铅笔 / 刷子 / 喷枪 / 橡皮 / 填充 / 取色 / 直线 / 矩形 / 多边形 / 椭圆 / 圆角矩形 / 文字 / 矩形选择（可拖动），
// 28 色颜料盒（左键前景、右键背景），线宽 / 填充方式选项，撤消 / 重复（Ctrl+Z / Ctrl+Y），保存为 PNG。
// 工具图标：jspaint (1j01/jspaint, MIT) 的 images/classic/tools.png（XP 画图原版工具图标的像素复刻）。
(function () {
  if (!window.WM || !WM.ready) return;
  const { h, ICO } = WM, P = 'xp/paint/';
  const st = document.createElement('style'); st.textContent = `
  .pt { position:absolute; inset:0; display:flex; flex-direction:column; background:#ece9d8; font:12px var(--xpfont); user-select:none; }
  .pt .main { flex:1; display:flex; min-height:0; }
  .pt .tools { width:56px; flex:none; padding:3px 2px; display:flex; flex-direction:column; gap:6px; }
  .pt .tgrid { display:grid; grid-template-columns:repeat(2,26px); gap:0; justify-content:center; }
  .pt .tb { width:26px; height:26px; box-sizing:border-box; border:2px solid; border-color:#fff #808080 #808080 #fff; background:#ece9d8; display:flex; align-items:center; justify-content:center; }
  .pt .tb i { width:16px; height:16px; background:url(${P}tools.png) no-repeat; }
  .pt .tb.on { border-color:#808080 #fff #fff #808080; background:repeating-conic-gradient(#fff 0 25%,#ece9d8 0 50%) 0 0/2px 2px; } .pt .tb.dis i { opacity:.35; }
  .pt .opts { width:42px; margin:0 auto; height:70px; border:2px solid; border-color:#808080 #fff #fff #808080; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; padding:2px; box-sizing:border-box; }
  .pt .opts b { width:34px; min-height:9px; display:flex; align-items:center; justify-content:center; box-sizing:border-box; } .pt .opts b.on { background:#0a246a; } .pt .opts b.on * { filter:invert(1); }
  .pt .stage { flex:1; min-width:0; background:#808080; overflow:auto; border:2px solid; border-color:#808080 #fff #fff #808080; position:relative; margin:2px 2px 0 0; }
  .pt .cvw { position:relative; margin:3px; width:max-content; height:max-content; } .pt canvas.cv { display:block; background:#fff; cursor:crosshair; image-rendering:pixelated; }
  .pt .sel { position:absolute; border:1px dashed #000; outline:1px dashed #fff; pointer-events:none; display:none; box-sizing:border-box; } .pt .float { position:absolute; display:none; cursor:move; }
  .pt .pal { height:36px; flex:none; display:flex; align-items:center; padding:0 3px; gap:6px; }
  .pt .cur { width:32px; height:32px; position:relative; border:2px solid; border-color:#808080 #fff #fff #808080; box-sizing:border-box; } .pt .cur .bg { position:absolute; right:3px; bottom:3px; width:16px; height:16px; border:1px solid #000; box-sizing:border-box; } .pt .cur .fg { position:absolute; left:3px; top:3px; width:16px; height:16px; border:1px solid #000; box-sizing:border-box; z-index:1; outline:2px solid #ece9d8; }
  .pt .sw { display:grid; grid-template-columns:repeat(14,16px); grid-auto-rows:16px; gap:0; } .pt .sw div { box-sizing:border-box; border:2px solid; border-color:#808080 #fff #fff #808080; }
  .pt .stat { height:22px; flex:none; display:flex; border-top:1px solid #aca899; font-size:12px; line-height:20px; } .pt .stat div { padding:0 6px; border-right:1px solid #aca899; white-space:nowrap; } .pt .stat div:first-child { flex:1; }
  `; document.head.appendChild(st);
  const PAL = ['#000000', '#808080', '#800000', '#808000', '#008000', '#008080', '#000080', '#800080', '#808040', '#004040', '#0080ff', '#004080', '#4000ff', '#804000',
    '#ffffff', '#c0c0c0', '#ff0000', '#ffff00', '#00ff00', '#00ffff', '#0000ff', '#ff00ff', '#ffff80', '#00ff80', '#80ffff', '#8080ff', '#ff0080', '#ff8040'];
  const TOOLS = [['freesel', '任意形状的选择'], ['select', '选定'], ['eraser', '橡皮'], ['fill', '用颜色填充'], ['pick', '取色'], ['zoom', '放大镜'], ['pencil', '铅笔'], ['brush', '刷子'],
    ['airbrush', '喷枪'], ['text', '文字'], ['line', '直线'], ['curve', '曲线'], ['rect', '矩形'], ['poly', '多边形'], ['ellipse', '椭圆'], ['rrect', '圆角矩形']];
  const DISABLED = new Set(['freesel', 'zoom', 'curve']);
  const SIZES = { eraser: [4, 6, 8, 10], brush: [1, 2, 4, 6], airbrush: [6, 10, 16], line: [1, 2, 3, 4, 5], rect: 'fill', ellipse: 'fill', rrect: 'fill', poly: 'fill' };
  const rgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));

  WM.register('paint', { open: () => {
    const CW = 480, CH = 300;
    const cv = h('canvas', { class: 'cv', width: CW, height: CH }), g = cv.getContext('2d', { willReadFrequently: true });
    const S = { tool: 'pencil', prev: 'pencil', fg: '#000000', bg: '#ffffff', size: { eraser: 6, brush: 4, airbrush: 10, line: 1 }, fill: 0, dirty: false, name: '无标题', strokes: 0, undo: [], redo: [], pts: null, sel: null, drag: null };
    g.fillStyle = '#fff'; g.fillRect(0, 0, CW, CH);
    const sizeOf = t => (t === 'line' || SIZES[t] === 'fill') ? (S.size.line || 1) : (S.size[t] || 1);
    // ---------- 界面 ----------
    const grid = h('div', { class: 'tgrid' }), tbs = {};
    TOOLS.forEach(([id, tip], i) => { const b = h('div', { class: 'tb' + (DISABLED.has(id) ? ' dis' : ''), title: tip, 'data-tool': id }, [h('i', { style: `background-position:${-16 * i}px 0` })]); b.addEventListener('click', () => { if (!DISABLED.has(id)) setTool(id); }); tbs[id] = b; grid.appendChild(b); });
    const opts = h('div', { class: 'opts' });
    const wrap = h('div', { class: 'cvw' }, [cv]), selBox = h('div', { class: 'sel' }), flt = h('canvas', { class: 'float' }); wrap.append(selBox, flt);
    const stage = h('div', { class: 'stage' }, [wrap]);
    const fgEl = h('div', { class: 'fg' }), bgEl = h('div', { class: 'bg' }), cur = h('div', { class: 'cur' }, [bgEl, fgEl]), sw = h('div', { class: 'sw' }), swEls = {};
    PAL.forEach(c => { const e = h('div', { style: 'background:' + c, title: c, 'data-color': c }); e.addEventListener('click', () => setColor('fg', c)); e.addEventListener('contextmenu', ev => { ev.preventDefault(); setColor('bg', c); }); e.addEventListener('pointerdown', ev => { if (ev.button === 2) { ev.preventDefault(); setColor('bg', c); } }); swEls[c] = e; sw.appendChild(e); });
    const stat = h('div', { class: 'stat' }, [h('div', { text: '要获得帮助，请在“帮助”菜单中，单击“帮助主题”。' }), h('div', { text: '', style: 'width:70px' }), h('div', { text: CW + 'x' + CH, style: 'width:70px;border:0' })]);
    const pal = h('div', { class: 'pal' }, [cur, sw]);
    const tools = h('div', { class: 'tools' }, [grid, opts]);
    const body = h('div', { class: 'main' }, [tools, stage]);
    const setColor = (k, c) => { S[k] = c; (k === 'fg' ? fgEl : bgEl).style.background = c; };
    setColor('fg', S.fg); setColor('bg', S.bg);
    function drawOpts() {
      opts.innerHTML = ''; const o = SIZES[S.tool]; if (!o) return;
      if (o === 'fill') { [0, 1, 2].forEach(m => { const b = h('b', { class: m === S.fill ? 'on' : '', title: ['只显示轮廓', '带填充的轮廓', '无轮廓填充'][m], 'data-fill': m }, [h('div', { style: `width:26px;height:12px;box-sizing:border-box;border:${m === 2 ? 0 : 1}px solid #000;background:${m ? '#808080' : 'transparent'}` })]); b.addEventListener('click', () => { S.fill = m; drawOpts(); }); opts.appendChild(b); });
        return; }
      o.forEach(s => { const key = S.tool === 'line' ? 'line' : S.tool; const on = (S.size[key] || 1) === s; const b = h('b', { class: on ? 'on' : '', 'data-size': s }, [S.tool === 'line' ? h('div', { style: `width:26px;height:${s}px;background:#000` }) : h('div', { style: `width:${Math.min(16, s)}px;height:${Math.min(16, s)}px;background:#000;border-radius:${S.tool === 'eraser' ? 0 : 50}%` })]);
        b.addEventListener('click', () => { S.size[key] = s; if (S.tool === 'line') S.size.line = s; drawOpts(); }); opts.appendChild(b); });
    }
    function setTool(t) { commitFloat(); finishPoly(); S.prev = S.tool === 'pick' ? S.prev : S.tool; S.tool = t; Object.entries(tbs).forEach(([k, b]) => b.classList.toggle('on', k === t)); drawOpts(); cv.style.cursor = t === 'fill' ? 'cell' : t === 'text' ? 'text' : t === 'select' ? 'crosshair' : 'crosshair'; }
    // ---------- 撤消 ----------
    const snap = () => { S.undo.push(g.getImageData(0, 0, CW, CH)); if (S.undo.length > 30) S.undo.shift(); S.redo = []; };
    const touch = () => { S.dirty = true; S.strokes++; win && win.setTitle(S.name + ' - 画图'); };
    function doUndo() { commitFloat(); const d = S.undo.pop(); if (!d) return; S.redo.push(g.getImageData(0, 0, CW, CH)); g.putImageData(d, 0, 0); }
    function doRedo() { const d = S.redo.pop(); if (!d) return; S.undo.push(g.getImageData(0, 0, CW, CH)); g.putImageData(d, 0, 0); }
    function clearAll() { commitFloat(); snap(); g.fillStyle = S.bg; g.fillRect(0, 0, CW, CH); touch(); }
    // ---------- 绘制原语 ----------
    const px = (x, y, c, s) => { g.fillStyle = c; g.fillRect(Math.round(x - (s - 1) / 2), Math.round(y - (s - 1) / 2), s, s); };
    function line(x0, y0, x1, y1, f) { x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1); const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let e = dx + dy; for (let n = 0; n < 5000; n++) { f(x0, y0); if (x0 === x1 && y0 === y1) break; const e2 = 2 * e; if (e2 >= dy) { e += dy; x0 += sx; } if (e2 <= dx) { e += dx; y0 += sy; } } }
    function dot(x, y, c, s) { if (s <= 1) return px(x, y, c, 1); g.fillStyle = c; g.beginPath(); g.arc(Math.round(x) + .5, Math.round(y) + .5, s / 2, 0, 7); g.fill(); }
    function spray(x, y, c, r) { g.fillStyle = c; for (let i = 0; i < r * 1.6; i++) { const a = Math.random() * 6.283, d = Math.sqrt(Math.random()) * r; g.fillRect(Math.round(x + Math.cos(a) * d), Math.round(y + Math.sin(a) * d), 1, 1); } }
    function flood(x0, y0, hex) {
      x0 |= 0; y0 |= 0; if (x0 < 0 || y0 < 0 || x0 >= CW || y0 >= CH) return; const im = g.getImageData(0, 0, CW, CH), a = new Uint32Array(im.data.buffer), [r, gg, b] = rgb(hex), nv = (255 << 24) | (b << 16) | (gg << 8) | r, tv = a[y0 * CW + x0]; if (tv === nv) return;
      const stack = [[x0, y0]]; while (stack.length) { let [x, y] = stack.pop(); while (x >= 0 && a[y * CW + x] === tv) x--; x++; let up = false, dn = false; while (x < CW && a[y * CW + x] === tv) { a[y * CW + x] = nv; if (y > 0) { const m = a[(y - 1) * CW + x] === tv; if (m && !up) stack.push([x, y - 1]); up = m; } if (y < CH - 1) { const m = a[(y + 1) * CW + x] === tv; if (m && !dn) stack.push([x, y + 1]); dn = m; } x++; } }
      g.putImageData(im, 0, 0);
    }
    function shape(t, x0, y0, x1, y1, fg, bg, fillMode, lw) {
      g.lineWidth = lw; g.lineJoin = 'miter'; g.strokeStyle = fillMode === 2 ? fg : fg; g.fillStyle = fillMode === 2 ? fg : bg; const o = lw % 2 ? .5 : 0;
      const x = Math.min(x0, x1) + o, y = Math.min(y0, y1) + o, w = Math.abs(x1 - x0), hh = Math.abs(y1 - y0);
      g.beginPath();
      if (t === 'line') { g.lineCap = 'butt'; g.moveTo(x0 + o, y0 + o); g.lineTo(x1 + o, y1 + o); g.stroke(); return; }
      if (t === 'rect') g.rect(x, y, w, hh); else if (t === 'ellipse') g.ellipse(x + w / 2, y + hh / 2, Math.max(.5, w / 2), Math.max(.5, hh / 2), 0, 0, 7); else if (t === 'rrect') { const r = Math.min(12, w / 2, hh / 2); g.roundRect ? g.roundRect(x, y, w, hh, r) : g.rect(x, y, w, hh); }
      if (fillMode >= 1) g.fill(); if (fillMode !== 2) g.stroke();
    }
    function polyDraw(pts, close, fg, bg, fillMode, lw) { if (pts.length < 2) return; g.lineWidth = lw; g.strokeStyle = fg; g.fillStyle = fillMode === 2 ? fg : bg; g.beginPath(); pts.forEach((p, i) => i ? g.lineTo(p[0] + .5, p[1] + .5) : g.moveTo(p[0] + .5, p[1] + .5)); if (close) g.closePath(); if (close && fillMode >= 1) g.fill(); if (!close || fillMode !== 2) g.stroke(); }
    // ---------- 选择 / 浮动选区 ----------
    function showSel() { const s = S.sel; if (!s) { selBox.style.display = 'none'; return; } Object.assign(selBox.style, { display: 'block', left: s.x + 'px', top: s.y + 'px', width: s.w + 'px', height: s.h + 'px' }); }
    function commitFloat() { const s = S.sel; if (!s) return; if (s.lifted) { g.drawImage(flt, s.x, s.y); } flt.style.display = 'none'; S.sel = null; showSel(); }
    function lift() { const s = S.sel; if (s.lifted) return; snap(); flt.width = s.w; flt.height = s.h; flt.getContext('2d').drawImage(cv, s.x, s.y, s.w, s.h, 0, 0, s.w, s.h); g.fillStyle = S.bg; g.fillRect(s.x, s.y, s.w, s.h); s.lifted = true; flt.style.display = 'block'; touch(); posFloat(); }
    function posFloat() { const s = S.sel; flt.style.left = s.x + 'px'; flt.style.top = s.y + 'px'; showSel(); }
    // ---------- 指针 ----------
    const at = e => { const r = cv.getBoundingClientRect(); return [Math.floor((e.clientX - r.left) * CW / r.width), Math.floor((e.clientY - r.top) * CH / r.height)]; };
    const poly = { pts: [] };
    function finishPoly(close) { if (S.tool !== 'poly' || poly.pts.length < 2) { poly.pts = []; return; } if (S.undo.length && S.polyBase) g.putImageData(S.polyBase, 0, 0); polyDraw(poly.pts, close !== false, S.fg, S.bg, S.fill, sizeOf('poly')); poly.pts = []; S.polyBase = null; touch(); }
    function down(e) {
      if (e.button === 1) return; const right = e.button === 2, [x, y] = at(e), t = S.tool, fg = right ? S.bg : S.fg, bg = right ? S.fg : S.bg;
      if (t === 'poly') { if (!poly.pts.length) { snap(); S.polyBase = g.getImageData(0, 0, CW, CH); } poly.pts.push([x, y]); S.drag = { t, right, fg, bg, poly: true }; e.preventDefault(); return; }
      if (S.sel && t === 'select') { const s = S.sel; if (x >= s.x && y >= s.y && x < s.x + s.w && y < s.y + s.h) { lift(); S.drag = { t: 'movesel', ox: x - s.x, oy: y - s.y }; return; } commitFloat(); }
      if (t === 'fill') { snap(); flood(x, y, fg); touch(); return; }
      if (t === 'pick') { const d = g.getImageData(x, y, 1, 1).data, hex = '#' + [d[0], d[1], d[2]].map(v => v.toString(16).padStart(2, '0')).join(''); setColor(right ? 'bg' : 'fg', hex); setTool(S.prev); return; }
      if (t === 'text') { commitFloat(); WM.prompt('文字', '在画布上输入文字：', '', v => { if (!v) return; snap(); g.fillStyle = S.fg; g.font = '16px SimSun,"宋体","Songti SC",serif'; g.textBaseline = 'top'; g.fillText(v, x, y); touch(); }); return; }
      snap(); S.drag = { t, right, fg, bg, x0: x, y0: y, lx: x, ly: y, base: null };
      if (t === 'pencil') px(x, y, fg, 1); else if (t === 'brush') dot(x, y, fg, sizeOf('brush')); else if (t === 'eraser') px(x, y, S.bg, sizeOf('eraser'));
      else if (t === 'airbrush') { const d = S.drag; d.timer = setInterval(() => spray(d.lx, d.ly, fg, sizeOf('airbrush') / 2), 25); spray(x, y, fg, sizeOf('airbrush') / 2); }
      else { S.drag.base = g.getImageData(0, 0, CW, CH); }
      e.preventDefault();
    }
    function mv(e) {
      const d = S.drag; if (!d) { const [x, y] = at(e); stat.children[1].textContent = x >= 0 && y >= 0 && x < CW && y < CH ? x + ', ' + y : ''; return; }
      let [x, y] = at(e); if (e.shiftKey && (d.t === 'line')) { if (Math.abs(x - d.x0) > Math.abs(y - d.y0) * 2) y = d.y0; else if (Math.abs(y - d.y0) > Math.abs(x - d.x0) * 2) x = d.x0; else { const m = Math.max(Math.abs(x - d.x0), Math.abs(y - d.y0)); x = d.x0 + Math.sign(x - d.x0) * m; y = d.y0 + Math.sign(y - d.y0) * m; } }
      stat.children[1].textContent = x + ', ' + y;
      if (d.poly) { g.putImageData(S.polyBase, 0, 0); polyDraw(poly.pts.concat([[x, y]]), false, d.fg, d.bg, 0, sizeOf('poly')); return; }
      if (d.t === 'movesel') { S.sel.x = x - d.ox; S.sel.y = y - d.oy; posFloat(); return; }
      if (d.t === 'pencil') line(d.lx, d.ly, x, y, (a, b) => px(a, b, d.fg, 1));
      else if (d.t === 'brush') { const s = sizeOf('brush'); line(d.lx, d.ly, x, y, (a, b) => dot(a, b, d.fg, s)); }
      else if (d.t === 'eraser') { const s = sizeOf('eraser'); line(d.lx, d.ly, x, y, (a, b) => px(a, b, S.bg, s)); }
      else if (d.t === 'airbrush') { /* 定时器负责 */ }
      else if (d.t === 'select') { const X = Math.max(0, Math.min(CW, Math.min(x, d.x0))), Y = Math.max(0, Math.min(CH, Math.min(y, d.y0))); S.sel = { x: X, y: Y, w: Math.min(CW, Math.max(x, d.x0)) - X, h: Math.min(CH, Math.max(y, d.y0)) - Y, lifted: false }; showSel(); }
      else { g.putImageData(d.base, 0, 0); shape(d.t, d.x0, d.y0, x, y, d.fg, d.bg, d.t === 'line' ? 0 : S.fill, sizeOf(d.t)); }
      d.lx = x; d.ly = y; d.moved = true;
    }
    function up() {
      const d = S.drag; if (!d) return; if (d.poly) { S.drag = null; return; } S.drag = null; if (d.timer) clearInterval(d.timer);
      if (d.t === 'select') { if (!S.sel || S.sel.w < 2 || S.sel.h < 2) { S.sel = null; showSel(); } S.undo.pop(); return; }
      if (d.t === 'movesel') return;
      if (['pencil', 'brush', 'eraser', 'airbrush', 'line', 'rect', 'ellipse', 'rrect'].includes(d.t)) touch();
    }
    cv.addEventListener('pointerdown', down); flt.addEventListener('pointerdown', down);
    cv.addEventListener('dblclick', () => { if (S.tool === 'poly' && poly.pts.length > 1) { poly.pts.pop(); finishPoly(true); } });
    cv.addEventListener('contextmenu', e => e.preventDefault());
    document.addEventListener('pointermove', mv, true); document.addEventListener('pointerup', up, true);
    const kd = e => { if (WM.active !== win || (e.target && /INPUT|TEXTAREA/.test(e.target.tagName))) return; const c = e.ctrlKey || e.metaKey, k = e.key.toLowerCase();
      if (c && k === 'z') { e.preventDefault(); doUndo(); } else if (c && k === 'y') { e.preventDefault(); doRedo(); } else if (c && k === 's') { e.preventDefault(); save(); }
      else if (k === 'delete' && S.sel) { snap(); if (!S.sel.lifted) { g.fillStyle = S.bg; g.fillRect(S.sel.x, S.sel.y, S.sel.w, S.sel.h); } flt.style.display = 'none'; S.sel = null; showSel(); touch(); }
      else if (k === 'escape') { if (poly.pts.length) { g.putImageData(S.polyBase, 0, 0); poly.pts = []; } commitFloat(); } else if (k === 'enter' && poly.pts.length) finishPoly(true); };
    document.addEventListener('keydown', kd);
    // ---------- 文件 ----------
    function save() { commitFloat(); cv.toBlob(b => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = S.name.replace(/[\\/:*?"<>|]/g, '_') + '.png'; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); S.dirty = false; win.setTitle(S.name + ' - 画图'); }); }
    const saveAs = () => WM.prompt('另存为', '文件名(N)：', S.name === '无标题' ? 'untitled' : S.name, v => { if (!v) return; S.name = v.replace(/\.(png|bmp)$/i, ''); save(); });
    const newDoc = () => { const go = () => { commitFloat(); S.undo = []; S.redo = []; g.fillStyle = '#fff'; g.fillRect(0, 0, CW, CH); S.dirty = false; S.name = '无标题'; S.strokes = 0; win.setTitle('无标题 - 画图'); }; if (S.dirty) WM.confirm('画图', '保存对 ' + S.name + ' 的更改吗？', () => { saveAs(); }, go, ['是(Y)', '否(N)']); else go(); };
    const flip = (hv) => { commitFloat(); snap(); const t = document.createElement('canvas'); t.width = CW; t.height = CH; t.getContext('2d').drawImage(cv, 0, 0); g.save(); g.translate(hv ? CW : 0, hv ? 0 : CH); g.scale(hv ? -1 : 1, hv ? 1 : -1); g.drawImage(t, 0, 0); g.restore(); touch(); };
    const invert = () => { commitFloat(); snap(); const im = g.getImageData(0, 0, CW, CH), d = im.data; for (let i = 0; i < d.length; i += 4) { d[i] = 255 - d[i]; d[i + 1] = 255 - d[i + 1]; d[i + 2] = 255 - d[i + 2]; } g.putImageData(im, 0, 0); touch(); };
    const vis = { tools: true, pal: true, stat: true };
    const mbar = WM.menubar([
      { t: '文件(F)', items: () => [{ t: '新建(N)', key: 'Ctrl+N', on: newDoc }, { t: '打开(O)...', key: 'Ctrl+O', dis: true }, { t: '保存(S)', key: 'Ctrl+S', on: save }, { t: '另存为(A)...', on: saveAs }, '-', { t: '打印预览(V)', dis: true }, { t: '页面设置(U)...', dis: true }, { t: '打印(P)...', key: 'Ctrl+P', dis: true }, '-', { t: '退出(X)', key: 'Alt+F4', on: () => win.close() }] },
      { t: '编辑(E)', items: () => [{ t: '撤消(U)', key: 'Ctrl+Z', on: doUndo, dis: !S.undo.length }, { t: '重复(R)', key: 'Ctrl+Y', on: doRedo, dis: !S.redo.length }, '-', { t: '全选(L)', key: 'Ctrl+A', on: () => { setTool('select'); S.sel = { x: 0, y: 0, w: CW, h: CH, lifted: false }; showSel(); } }, { t: '清除选定内容(L)', key: 'Del', on: () => kd({ key: 'Delete', ctrlKey: false }) }] },
      { t: '查看(V)', items: () => [{ t: '工具箱(T)', chk: vis.tools, on: () => { vis.tools = !vis.tools; tools.style.display = vis.tools ? '' : 'none'; } }, { t: '颜料盒(C)', chk: vis.pal, on: () => { vis.pal = !vis.pal; pal.style.display = vis.pal ? '' : 'none'; } }, { t: '状态栏(S)', chk: vis.stat, on: () => { vis.stat = !vis.stat; stat.style.display = vis.stat ? '' : 'none'; } }] },
      { t: '图像(I)', items: () => [{ t: '水平翻转', on: () => flip(true) }, { t: '垂直翻转', on: () => flip(false) }, { t: '反色(I)', key: 'Ctrl+I', on: invert }, '-', { t: '清除图像(C)', key: 'Ctrl+Shift+N', on: clearAll }] },
      { t: '颜色(C)', items: () => [{ t: '编辑颜色(E)...', dis: true }] },
      { t: '帮助(H)', items: () => [{ t: '帮助主题(H)', on: () => WM.open('help') }, '-', { t: '关于画图(A)', on: () => WM.alert('关于画图', 'Microsoft (R) Windows (R) 画图\n版本 5.1 (内部版本号 2600)', { kind: 'info' }) }] },
    ]);
    const root = h('div', { class: 'pt' }, [mbar, body, pal, stat]);
    let win = WM.create({ id: 'paint', title: '无标题 - 画图', icon: ICO('680_16.png'), w: 600, h: 460, minW: 360, minH: 300, content: () => root,
      onclose: w => { if (S.dirty && !w._confirmed) { WM.confirm('画图', '保存对 ' + S.name + ' 的更改吗？', () => { saveAs(); w._confirmed = true; }, () => { w._confirmed = true; w.close(); }, ['是(Y)', '否(N)']); return false; } document.removeEventListener('keydown', kd); document.removeEventListener('pointermove', mv, true); document.removeEventListener('pointerup', up, true); } });
    setTool('pencil');
    // 给桌面 Agent 的接口
    win.paint = { cv, tools: tbs, swatches: swEls, opts, state: () => ({ tool: S.tool, fg: S.fg, bg: S.bg, size: sizeOf(S.tool), fill: S.fill, strokes: S.strokes, dirty: S.dirty, w: CW, h: CH, undo: S.undo.length }), setTool, setColor, clear: clearAll, undo: doUndo, redo: doRedo, save, ink: () => { const d = g.getImageData(0, 0, CW, CH).data; let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] < 250 || d[i + 1] < 250 || d[i + 2] < 250) n++; return n; } };
    return win;
  } });
})();
