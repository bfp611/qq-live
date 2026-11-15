// ?desk=xp：XP 窗口管理器（拖动 / 缩放 / 最小化到任务栏 / 最大化 / 关闭 / 焦点与 z 序）、经典菜单、对话框。
// 桌面图标 / 开始菜单 / 右键菜单在 desktop.js，各个“假应用”在 apps-*.js。窗口外框样式参考 ShizukuIchi/winXP（MIT）。
(function () {
  if (!window.DESK || !DESK.on) return;
  const root = document.getElementById('deskroot');
  const DW = parseFloat(root.style.width) || 1280, DH = parseFloat(root.style.height) || 720, TB = 30;
  const sc = () => root.getBoundingClientRect().width / DW;

  // ---------- 小工具 ----------
  function h(tag, p, kids) {
    const e = document.createElement(tag);
    if (p) for (const k in p) {
      const v = p[k];
      if (k === 'class') e.className = v; else if (k === 'style') e.style.cssText = v;
      else if (k === 'text') e.textContent = v; else if (k === 'html') e.innerHTML = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
    }
    if (kids) (Array.isArray(kids) ? kids : [kids]).forEach(c => c != null && e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
    return e;
  }
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const toRoot = ev => { const r = root.getBoundingClientRect(), k = r.width / DW; return { x: (ev.clientX - r.left) / k, y: (ev.clientY - r.top) / k }; };
  const ICO = n => 'xp/ico/' + n;
  function track(e, move, end) {
    if (e.button != null && e.button !== 0) return;
    e.preventDefault();
    const sx = e.clientX, sy = e.clientY, k = sc();
    root.classList.add('dragging');
    const mv = ev => move((ev.clientX - sx) / k, (ev.clientY - sy) / k, ev);
    const up = ev => { document.removeEventListener('pointermove', mv); document.removeEventListener('pointerup', up); document.removeEventListener('pointercancel', up); root.classList.remove('dragging'); end && end(ev); };
    document.addEventListener('pointermove', mv); document.addEventListener('pointerup', up); document.addEventListener('pointercancel', up);
  }

  const WM = window.WM = { root, DW, DH, TB, h, esc, toRoot, ICO, track, wins: [], byId: {}, z: 100, active: null, apps: {}, uid: 0 };

  // ---------- 经典菜单 ----------
  let menus = [];
  function closeMenus() { menus.forEach(m => m.remove()); menus = []; document.removeEventListener('pointerdown', outside, true); document.removeEventListener('keydown', menuKey, true); WM.onMenuClose && WM.onMenuClose(); }
  function outside(e) { if (!e.target.closest('.xpm')) { closeMenus(); } }
  function menuKey(e) { if (e.key === 'Escape') closeMenus(); }
  function buildMenu(items, x, y, opts, level, parentLeftX) {
    const m = h('div', { class: 'xpm' + (opts.all ? ' all' : '') });
    let timer = null;
    items.forEach(it => {
      if (it === '-' || it.sep) return m.appendChild(h('div', { class: 'sep' }));
      const dis = typeof it.dis === 'function' ? it.dis() : it.dis;
      const el = h('div', { class: 'mi' + (dis ? ' dis' : '') + (it.bold ? ' bold' : '') });
      if (it.chk) el.appendChild(h('span', { class: 'mk', text: '✓' }));
      if (it.radio) el.appendChild(h('span', { class: 'mk', text: '●', style: 'font-size:8px' }));
      if (it.icon) el.appendChild(h('img', { src: it.icon.includes('/') ? it.icon : ICO(it.icon) }));
      el.appendChild(h('span', { text: it.t }));
      if (it.key) el.appendChild(h('span', { class: 'sc', text: it.key }));
      if (it.sub) el.appendChild(h('span', { class: 'ar' }));
      el.addEventListener('pointerenter', () => {
        [...m.children].forEach(c => c.classList.remove('on')); el.classList.add('on');
        clearTimeout(timer);
        // 关掉比当前层更深的子菜单
        timer = setTimeout(() => {
          while (menus.length > level + 1) menus.pop().remove();
          if (it.sub && !dis) {
            const r = el.getBoundingClientRect(), k = sc(), rr = root.getBoundingClientRect();
            const sx = (r.right - rr.left) / k - 3, sy = (r.top - rr.top) / k - 3;
            buildMenu(typeof it.sub === 'function' ? it.sub() : it.sub, sx, sy, opts, level + 1, (r.left - rr.left) / k);
          }
        }, it.sub ? 120 : 0);
      });
      el.addEventListener('click', e => {
        e.stopPropagation();
        if (dis || it.sub) return;
        closeMenus(); it.on && setTimeout(() => it.on(e), 0);
      });
      m.appendChild(el);
    });
    root.appendChild(m);
    menus[level] = m;
    const w = m.offsetWidth, hh = m.offsetHeight; m._parentRightX = parentLeftX;
    if (x + w > DW) x = level ? Math.max(0, (m._parentRightX != null ? m._parentRightX : x) - w + 3) : DW - w;
    if (y + hh > DH - (opts.noTaskbar ? 0 : TB)) y = Math.max(0, DH - (opts.noTaskbar ? 0 : TB) - hh);
    m.style.left = x + 'px'; m.style.top = y + 'px';
    return m;
  }
  WM.closeMenus = closeMenus;
  WM.menu = function (items, x, y, opts) {
    opts = opts || {}; closeMenus();
    const m = buildMenu(items, x, y, opts, 0);
    setTimeout(() => { document.addEventListener('pointerdown', outside, true); document.addEventListener('keydown', menuKey, true); }, 0);
    return m;
  };
  WM.ctx = (ev, items, opts) => { ev.preventDefault(); ev.stopPropagation(); const p = toRoot(ev); return WM.menu(items, p.x, p.y, opts); };
  // 应用里的菜单栏：defs = [{t:'文件(F)', items:[...]}]
  WM.menubar = function (defs) {
    const bar = h('div', { class: 'xp-menubar' });
    let openIdx = -1;
    const show = (b, d, i) => {
      const r = b.getBoundingClientRect(), rr = root.getBoundingClientRect(), k = sc();
      WM.menu(typeof d.items === 'function' ? d.items() : d.items, (r.left - rr.left) / k, (r.bottom - rr.top) / k - 1);
      [...bar.children].forEach(c => c.classList.remove('on')); b.classList.add('on'); openIdx = i;
      WM.onMenuClose = () => { b.classList.remove('on'); openIdx = -1; WM.onMenuClose = null; };
    };
    defs.forEach((d, i) => {
      const b = h('div', { class: 'mb', text: d.t });
      b.addEventListener('pointerdown', e => { e.stopPropagation(); e.preventDefault(); if (openIdx === i) closeMenus(); else show(b, d, i); });
      b.addEventListener('pointerenter', () => { if (openIdx >= 0 && openIdx !== i) show(b, d, i); });
      bar.appendChild(b);
    });
    return bar;
  };

  // ---------- 窗口 ----------
  const tbLeft = () => document.querySelector('#taskbar .left');
  let tbBox = null;
  function tbbox() {
    if (!tbBox) {
      tbBox = h('div', { id: 'taskbtns', style: 'flex:1;display:flex;align-items:center;overflow:hidden;min-width:0;height:100%' });
      tbLeft().appendChild(tbBox);
    }
    return tbBox;
  }
  function layoutZ() {
    WM.wins.forEach(w => { w.el.style.zIndex = w.z; });
  }
  function refreshTb() {
    WM.wins.forEach(w => {
      if (w.tb) { w.tb.classList.toggle('act', WM.active === w && w.state !== 'min'); w.tb.style.display = (w.closed || w.tbHidden) ? 'none' : ''; }
      w.el.classList.toggle('inactive', WM.active !== w);
      w.el.classList.toggle('active', WM.active === w);
    });
    document.dispatchEvent(new CustomEvent('wmchange'));
  }
  function topVisible(except) {
    return WM.wins.filter(w => w !== except && w.state !== 'min' && !w.closed && !w.dialogOnly).sort((a, b) => b.z - a.z)[0] || null;
  }
  const fire = (type, w) => { try { document.dispatchEvent(new CustomEvent('wmevent', { detail: { type, w } })); } catch (e) {} };   // 给系统音效 / 气泡通知等用（xp-core.js）
  WM.fire = fire;
  const api = {
    focus() { if (this.state === 'min') return this.restore(); this.z = ++WM.z; WM.active = this; layoutZ(); refreshTb(); this.onfocus && this.onfocus(); },
    min() { if (this.state === 'min') return; this.prev = this.state; this.state = 'min'; fire('min', this); this._apply(); if (WM.active === this) WM.active = topVisible(this); refreshTb(); this.onstate && this.onstate(); },
    restore() { if (this.state === 'min') { this.state = this.prev || 'normal'; fire('restore', this); this._apply(); this.z = ++WM.z; WM.active = this; layoutZ(); refreshTb(); this.onstate && this.onstate(); return; }
      if (this.state === 'max') { this.state = 'normal'; fire('restore', this); this._apply(); this.focus(); this.onstate && this.onstate(); } },
    max() { if (this.o.resizable === false || this.nomax) return; if (this.state === 'max') return this.restore(); if (this.state === 'normal') this.saved = Object.assign({}, this.rect); this.state = 'max'; fire('max', this); this._apply(); this.focus(); this.onstate && this.onstate(); },
    toggleMax() { if (this.state === 'max') this.restore(); else this.max(); },
    close() {
      if (this.closed) return; if (this.o.onclose && this.o.onclose(this) === false) return;
      this.closed = true; this.state = 'closed'; fire('close', this);
      if (this.o.adopted && !this.o.destroy) { this.el.classList.add('wm-closed'); } else this.el.remove();
      if (this.tb && (!this.o.adopted || this.o.destroy)) this.tb.remove();
      if (!this.o.adopted || this.o.destroy) { WM.wins = WM.wins.filter(x => x !== this); if (WM.byId[this.id] === this) delete WM.byId[this.id]; }
      if (WM.active === this) WM.active = topVisible(this);
      refreshTb(); this.onstate && this.onstate();
    },
    reopen() { this.closed = false; this.state = 'normal'; fire('open', this); this.el.classList.remove('wm-closed'); this._apply(); this.focus(); this.onstate && this.onstate(); },
    setTitle(t) { this.title = t; if (this.tbText) this.tbText.textContent = t; if (this.titleEl) this.titleEl.textContent = t; },
    sysmenu(x, y) {
      const w = this;
      WM.menu([{ t: '还原(R)', dis: w.state === 'normal', on: () => w.restore() }, { t: '移动(M)', dis: true }, { t: '大小(S)', dis: true },
        { t: '最小化(N)', on: () => w.min() }, { t: '最大化(X)', dis: w.state === 'max' || w.o.resizable === false, on: () => w.max() }, '-',
        { t: '关闭(C)', key: 'Alt+F4', bold: true, on: () => w.close() }], x, y);
    },
  };
  function setupCommon(w) {
    Object.assign(w, api);
    w.z = ++WM.z; w.state = 'normal'; WM.wins.push(w); WM.byId[w.id] = w;
    w.el.addEventListener('pointerdown', () => { if (WM.active !== w) w.focus(); }, true);
    if (!w.o.notask || w.o.tbEl) {
      const tb = w.o.tbEl || h('div', { class: 'tbtn', title: w.title }, [h('img', { src: w.icon || ICO('318_16.png'), alt: '' }), h('span', { text: w.title })]);
      w.tbText = tb.querySelector('span');
      tb.addEventListener('click', () => { if (w.state === 'min') w.restore(); else if (WM.active === w) w.min(); else w.focus(); });
      tb.addEventListener('contextmenu', e => { e.preventDefault(); e.stopPropagation(); const p = toRoot(e); WM.menu([{ t: '还原(R)', dis: w.state === 'normal', on: () => w.restore() }, { t: '移动(M)', dis: true }, { t: '大小(S)', dis: true },
        { t: '最小化(N)', dis: w.state === 'min', on: () => w.min() }, { t: '最大化(X)', dis: w.state === 'max' || w.o.resizable === false || w.nomax, on: () => w.max() }, '-', { t: '关闭(C)', key: 'Alt+F4', bold: true, on: () => w.close() }], p.x, Math.min(p.y, DH - TB - 140)); });
      tbbox().appendChild(tb); w.tb = tb;
    }
  }
  function resizeHandles(w, which) {
    which.forEach(d => {
      const g = h('div', { class: 'xpw-rz rz-' + d });
      g.addEventListener('pointerdown', e => {
        if (w.state !== 'normal') return;
        const r0 = Object.assign({}, w.rect), minW = w.o.minW || 220, minH = w.o.minH || 120;
        track(e, (dx, dy) => {
          dx = Math.round(dx); dy = Math.round(dy); let { x, y, w: ww, h: hh } = r0;
          if (d.includes('e')) ww = Math.max(minW, r0.w + dx);
          if (d.includes('s')) hh = Math.max(minH, r0.h + dy);
          if (d.includes('w')) { ww = Math.max(minW, r0.w - dx); x = r0.x + r0.w - ww; }
          if (d.includes('n')) { hh = Math.max(minH, r0.h - dy); y = r0.y + r0.h - hh; if (y < 0) { hh += y; y = 0; } }
          w.rect = { x, y, w: ww, h: hh }; w._apply();
        });
      });
      w.el.appendChild(g);
    });
  }
  let cascade = 0;
  WM.create = function (o) {
    if (o.id && WM.byId[o.id] && !WM.byId[o.id].closed) { const w = WM.byId[o.id]; if (w.state === 'min') w.restore(); else w.focus(); return w; }
    const w = { id: o.id || ('w' + (++WM.uid)), o, title: o.title || '', icon: o.icon };
    const W = o.w || 640, H = o.h || 440;
    let x = o.x, y = o.y;
    if (x == null) { x = 70 + (cascade % 8) * 26; y = 30 + (cascade % 8) * 26; cascade++; if (o.dialog) { x = Math.round((DW - W) / 2); y = Math.round((DH - TB - H) / 2) - 20; } }
    w.rect = { x, y, w: W, h: H };
    const btns = h('div', { class: 'xpw-btns' });
    const mkb = (c, f) => { const b = h('button', { class: 'xb ' + c, onpointerdown: e => e.stopPropagation(), onclick: e => { e.stopPropagation(); f(); }, ondblclick: e => e.stopPropagation() }); btns.appendChild(b); return b; };
    if (!o.dialog) { mkb('mn', () => w.min()); w.mxb = mkb('mx', () => w.toggleMax()); if (o.resizable === false) w.mxb.classList.add('dis'); }
    else if (o.help) mkb('mx', () => {});
    mkb('cl', () => w.close());
    const ico = h('img', { class: 'xpw-ico', src: w.icon || ICO('318_16.png'), alt: '', draggable: 'false' });
    ico.addEventListener('pointerdown', e => { e.stopPropagation(); const r = ico.getBoundingClientRect(), rr = root.getBoundingClientRect(), k = sc(); w.sysmenu((r.left - rr.left) / k, (r.bottom - rr.top) / k); });
    ico.addEventListener('dblclick', e => { e.stopPropagation(); closeMenus(); w.close(); });
    w.titleEl = h('div', { class: 'xpw-title', text: w.title });
    const bar = h('div', { class: 'xpw-bar' }, [ico, w.titleEl, btns]);
    w.client = h('div', { class: 'xpw-client' });
    w.el = h('div', { class: 'xpw inactive' + (o.dialog ? ' dialog' : '') + (o.resizable === false ? ' fixed' : '') }, [h('div', { class: 'xpw-bg' }), bar, w.client]);
    bar.addEventListener('contextmenu', e => { e.preventDefault(); const p = toRoot(e); w.sysmenu(p.x, p.y); });
    bar.addEventListener('dblclick', () => { if (!o.dialog) w.toggleMax(); });
    bar.addEventListener('pointerdown', e => {
      if (w.state !== 'normal' || e.target.closest('.xb')) { if (w.state === 'max') e.preventDefault(); return; }
      const r0 = Object.assign({}, w.rect);
      track(e, (dx, dy) => { w.rect.x = Math.round(r0.x + dx); w.rect.y = Math.max(-2, Math.min(DH - TB - 22, Math.round(r0.y + dy))); w.rect.x = Math.max(-r0.w + 80, Math.min(DW - 60, w.rect.x)); w._apply(); });
    });
    w._apply = function () {
      const st = w.state, el = w.el;
      el.classList.toggle('min', st === 'min'); el.classList.toggle('max', st === 'max');
      if (w.mxb) { w.mxb.classList.toggle('rs', st === 'max'); w.mxb.classList.toggle('mx', st !== 'max'); }
      const r = st === 'max' ? { x: 0, y: 0, w: DW, h: DH - TB } : w.rect;
      el.style.left = r.x + 'px'; el.style.top = r.y + 'px'; el.style.width = r.w + 'px'; el.style.height = r.h + 'px';
      el.style.zIndex = w.z; w.onresize && st !== 'min' && w.onresize(r);
    };
    if (o.resizable !== false && !o.dialog) resizeHandles(w, ['n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se']);
    setupCommon(w);
    root.insertBefore(w.el, document.getElementById('taskbar'));
    if (o.content) w.client.appendChild(typeof o.content === 'function' ? o.content(w) : o.content);
    if (o.maximized) { w.saved = Object.assign({}, w.rect); w.state = 'max'; }
    w._apply(); w.focus(); fire('open', w);
    return w;
  };

  // ---------- 接管已有窗口（QQ 群聊 / 千千静听 / 播放列表）----------
  // cfg: { id, title, icon, handle(e)=>bool 是否按在可拖动区域, btns:{min,max,close}, getRect, setRect, resize: ['e','s',...], notask, minW, minH, fixedSize }
  WM.adopt = function (el, cfg) {
    const w = { id: cfg.id, o: Object.assign({ adopted: true }, cfg), title: cfg.title, icon: cfg.icon, el, client: el, nomax: cfg.fixedSize };
    w.rect = cfg.getRect(); w.o.notask = !cfg.taskbtn; w.o.tbEl = cfg.tbEl;
    w._apply = function () {
      const st = w.state;
      el.classList.toggle('wm-min', st === 'min'); el.classList.toggle('wm-max', st === 'max');
      if (st === 'max') cfg.setRect({ x: 0, y: 0, w: DW, h: DH - TB }, true);
      else if (st === 'normal') cfg.setRect(w.rect, false);
      el.style.zIndex = w.z; cfg.onapply && cfg.onapply(w);
    };
    setupCommon(w); el.classList.add('xpw-ad');
    el.addEventListener('pointerdown', e => {
      if (e.button !== 0 || w.state !== 'normal' || !cfg.handle(e)) return;
      const r0 = Object.assign({}, w.rect);
      track(e, (dx, dy) => { w.rect = { x: Math.round(r0.x + dx), y: Math.max(-2, Math.min(DH - TB - 22, Math.round(r0.y + dy))), w: r0.w, h: r0.h }; w.rect.x = Math.max(-r0.w + 80, Math.min(DW - 60, w.rect.x)); w._apply(); });
    });
    if (cfg.titleDbl) el.addEventListener('dblclick', e => { if (cfg.titleDbl(e)) w.toggleMax(); });
    if (cfg.btns) {
      const bind = (sel, f) => { const b = sel && el.querySelector(sel); if (b) b.addEventListener('click', e => { e.stopPropagation(); f(); }); };
      bind(cfg.btns.min, () => w.min()); bind(cfg.btns.max, () => w.toggleMax()); bind(cfg.btns.close, () => w.close());
    }
    if (cfg.resize) {
      const sz = ['n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se'];
      cfg.resize.forEach(d => {
        const g = h('div', { class: 'xpw-rz rz-' + d, style: 'z-index:50' });
        g.addEventListener('pointerdown', e => {
          if (w.state !== 'normal') return;
          const r0 = Object.assign({}, w.rect), minW = cfg.minW || 260, minH = cfg.minH || 160;
          track(e, (dx, dy) => {
            dx = Math.round(dx); dy = Math.round(dy); let { x, y, w: ww, h: hh } = r0;
            if (d.includes('e')) ww = Math.max(minW, r0.w + dx);
            if (d.includes('s')) hh = Math.max(minH, r0.h + dy);
            if (d.includes('w')) { ww = Math.max(minW, r0.w - dx); x = r0.x + r0.w - ww; }
            if (d.includes('n')) { hh = Math.max(minH, r0.h - dy); y = r0.y + r0.h - hh; }
            w.rect = { x, y, w: ww, h: hh }; w._apply();
          });
        });
        el.appendChild(g);
      });
    }
    w.state = cfg.startState || 'normal';
    return w;
  };

  // ---------- 对话框 ----------
  WM.dialog = function (o) {
    const content = o.content || (() => h('div'));
    if (o.modal) {
      const blk = h('div', { style: 'position:absolute;inset:0;z-index:' + (++WM.z) + ';background:transparent' });
      root.insertBefore(blk, document.getElementById('taskbar'));
      const prev = o.onclose;
      o.onclose = w => { blk.remove(); prev && prev(w); };
      blk.addEventListener('pointerdown', e => { e.stopPropagation(); const w = WM.byId[o.id]; w && w.focus(); });
    }
    const w = WM.create(Object.assign({ dialog: true, notask: true, resizable: false }, o, { content }));
    w.dialogOnly = true;
    return w;
  };
  WM.alert = function (title, text, o) {
    o = o || {};
    const kind = o.kind || 'error';
    const icon = kind === 'error' ? ICO('897_32.png') : kind === 'q' ? ICO('747_32.png') : null;
    const lines = String(text).split('\n').length + Math.floor(String(text).length / 34);
    const hgt = Math.max(118, 96 + lines * 16);
    const buttons = o.buttons || [['确定', null]];
    const w = WM.dialog({
      title, icon: o.titleIcon || ICO('897_16.png'), w: o.w || 340, h: hgt + 28, modal: o.modal !== false, id: o.id,
      content: wd => h('div', { class: 'xpd' }, [
        h('div', { class: 'msgbox' }, [icon ? h('img', { class: 'mi-ico', src: icon }) : h('div', { class: 'mi-ico', style: 'width:32px;height:32px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#8fb8ff,#1c55d8);color:#fff;font:700 22px/32px serif;text-align:center', text: kind === 'warn' ? '!' : 'i' }), h('div', { class: 'mi-t', text })]),
        h('div', { class: 'msgbtns' }, buttons.map((b, i) => h('button', { class: 'xbtn' + (i === 0 ? ' def' : ''), text: b[0], onclick: () => { wd.close(); b[1] && b[1](); } }))),
      ]),
    });
    return w;
  };
  WM.confirm = (title, text, yes, no, labels) => WM.alert(title, text, { kind: 'q', titleIcon: ICO('747_16.png'), buttons: [[(labels && labels[0]) || '是(Y)', yes], [(labels && labels[1]) || '否(N)', no]] });

  // Alt+F4 关闭当前窗口
  document.addEventListener('keydown', e => { if (e.altKey && e.key === 'F4' && WM.active) { e.preventDefault(); WM.active.close(); } });

  WM.refresh = refreshTb;
  WM.register = (id, def) => { WM.apps[id] = def; };
  WM.open = (id, args) => { const a = WM.apps[id]; if (!a) { WM.alert('Windows', 'Windows 找不到文件“' + id + '”。请确定文件名是否正确后，再试一次。'); return; } return a.open(args || {}); };
  WM.showDesktop = () => { const vis = WM.wins.filter(w => w.state !== 'min' && !w.closed && !w.dialogOnly); if (vis.length) { WM._sd = vis; vis.forEach(w => w.min()); } else if (WM._sd) { WM._sd.filter(w => !w.closed).forEach(w => w.restore()); WM._sd = null; } };
  WM.visible = () => WM.wins.filter(w => !w.closed && !w.dialogOnly && w.state !== 'min');
  WM.ready = true;
})();
