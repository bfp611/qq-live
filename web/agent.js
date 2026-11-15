// ?desk=xp：桌面 Agent（内核）。弹幕指令由服务端（backend/agent）解析成动作，推到这里；这里负责
//   · 一只原创 XP 光标：沿弧线移动 / 悬停 / 单击 / 右击 / 双击 / 拖拽 / 打字，都是真的事件，打在真的 DOM 上
//   · 桌面快照（窗口 id/标题/矩形/z 序/是否挡住群聊与歌词、壁纸、歌曲…）上报给服务端
//   · 动作队列、撤销栈、受保护窗口（群聊）自动恢复
// 具体动作在 agent-actions.js。配置来自 config.ini 的 [agent]（服务端通过 ws 下发）。?agent=0 关闭整个模块。
(function () {
  if (!window.WM || !WM.ready || !window.DESK || !DESK.on) return;
  const Q = new URLSearchParams(location.search);
  if (Q.get('agent') === '0') return;
  const { root, DW, DH, TB, h } = WM;
  const $ = id => document.getElementById(id);
  const sleep = ms => new Promise((res, rej) => setTimeout(() => (AG.cur && AG.cur.aborted) ? rej(new Error('abort')) : res(), ms));   // 被打断的任务：下一次 sleep 就抛出，层层退出
  const AG = window.AG = {
    cfg: { enabled: true, cursor_speed: 900, click_delay: 0.18, typing_cps: 9, step_pause: 0.25, show_who: true, cursor_idle_hide: 6, protect: ['qqchat'], restore_secs: 20, undo: true, queue_max: 6 },
    ACT: {}, undo: [], queue: [], cur: null, idleOpened: new Map(), running: false, pos: { x: 700, y: 420 }, hover: null, kind: 'arrow', log: [], fast: false, guardDue: 0, jobs: 0, sleep,
  };
  if (Q.get('cspeed')) AG.cfg.cursor_speed = +Q.get('cspeed') || 900;

  // ================= 坐标 =================
  const scale = () => root.getBoundingClientRect().width / DW;
  const client = (x, y) => { const r = root.getBoundingClientRect(), k = r.width / DW; return { x: r.left + x * k, y: r.top + y * k }; };
  const design = (cx, cy) => { const r = root.getBoundingClientRect(), k = r.width / DW; return { x: (cx - r.left) / k, y: (cy - r.top) / k }; };
  const elAt = (x, y) => { const c = client(x, y); return document.elementFromPoint(c.x, c.y); };
  const drect = el => { const r = el.getBoundingClientRect(), a = design(r.left, r.top), b = design(r.right, r.bottom); return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y }; };
  const shown = el => { if (!el || !el.isConnected) return false; const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1 && getComputedStyle(el).visibility !== 'hidden'; };
  Object.assign(AG, { scale, client, design, elAt, drect, shown });

  // ================= 光标 =================
  const cur = h('div', { id: 'ag-cur', class: 'arrow hide' }, [h('i', { class: 'ag-ic' }), h('b', { class: 'ag-who' })]);
  const ring = h('div', { id: 'ag-ring' });
  root.append(cur, ring);
  const HOT = { arrow: [1, 1], hand: [7, 1], ibeam: [5, 10] };
  function setPos(x, y) { AG.pos = { x, y }; const hs = HOT[AG.kind]; cur.style.transform = `translate(${(x - hs[0]).toFixed(1)}px,${(y - hs[1]).toFixed(1)}px)`; }
  function setKind(k) { if (k === AG.kind) return; AG.kind = k; cur.classList.remove('arrow', 'hand', 'ibeam'); cur.classList.add(k); setPos(AG.pos.x, AG.pos.y); }
  let idleT = 0;
  function show() { cur.classList.remove('hide'); clearTimeout(idleT); }
  function idleSoon() { clearTimeout(idleT); idleT = setTimeout(() => { if (!AG.running) { cur.classList.add('hide'); cur.classList.remove('who'); } }, Math.max(1, AG.cfg.cursor_idle_hide) * 1000); }
  setPos(AG.pos.x, AG.pos.y);
  function ringAt(x, y, right) { ring.style.left = x + 'px'; ring.style.top = y + 'px'; ring.classList.toggle('rc', !!right); ring.classList.remove('go'); void ring.offsetWidth; ring.classList.add('go'); }

  // ================= 合成事件 =================
  function mev(type, el, x, y, o) {
    o = o || {}; const c = client(x, y);
    const init = { bubbles: type !== 'pointerenter' && type !== 'pointerleave' && type !== 'mouseenter' && type !== 'mouseleave', cancelable: true, composed: true, view: window, clientX: c.x, clientY: c.y, screenX: c.x, screenY: c.y, button: o.button || 0, buttons: o.buttons || 0, detail: o.detail || 0, ctrlKey: !!o.ctrl };
    const ev = type.startsWith('pointer') ? new PointerEvent(type, Object.assign(init, { pointerId: 1, pointerType: 'mouse', isPrimary: true, width: 1, height: 1, pressure: o.buttons ? 0.5 : 0 })) : new MouseEvent(type, init);
    (el || document.body).dispatchEvent(ev); return ev;
  }
  const chainOf = el => { const a = []; for (let e = el; e; e = e.parentElement) a.push(e); return a; };
  function hoverTo(x, y) {
    const el = elAt(x, y);
    if (el !== AG.hover) {
      const oldC = AG.hover && AG.hover.isConnected ? chainOf(AG.hover) : [], newC = el ? chainOf(el) : [];
      const common = new Set(oldC.filter(n => newC.includes(n)));
      if (oldC.length) { mev('pointerout', oldC[0], x, y); mev('mouseout', oldC[0], x, y); oldC.filter(n => !common.has(n)).forEach(n => { mev('pointerleave', n, x, y); mev('mouseleave', n, x, y); }); }
      if (el) { mev('pointerover', el, x, y); mev('mouseover', el, x, y); newC.filter(n => !common.has(n)).reverse().forEach(n => { mev('pointerenter', n, x, y); mev('mouseenter', n, x, y); }); }
      AG.hover = el;
      if (el) { const cs = getComputedStyle(el).cursor; setKind(/pointer/.test(cs) ? 'hand' : (/text/.test(cs) || /^(INPUT|TEXTAREA)$/.test(el.tagName)) ? 'ibeam' : 'arrow'); }
    }
    return el;
  }

  // ================= 光标动作原语 =================
  async function move(x, y, o) {
    o = o || {}; show();
    x = Math.max(0, Math.min(DW - 1, x)); y = Math.max(0, Math.min(DH - 1, y));
    const sp = (o.speed || AG.cfg.cursor_speed) * (AG.fast ? 2.4 : 1) * ((AG.cur && AG.cur.speedf) || 1), x0 = AG.pos.x, y0 = AG.pos.y, d = Math.hypot(x - x0, y - y0);
    if (d < 1.5) { hoverTo(x, y); return; }
    const dur = Math.min(1500, Math.max(160, d / sp * 1000));
    AG.arc = -(AG.arc || 1);
    const nx = -(y - y0) / d, ny = (x - x0) / d, bend = Math.min(70, d * 0.12) * AG.arc;
    const cx = (x0 + x) / 2 + nx * bend, cy = (y0 + y) / 2 + ny * bend, t0 = performance.now();
    await new Promise(res => {
      const step = () => {
        const t = Math.min(1, (performance.now() - t0) / dur), e = t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2, u = 1 - e;
        const px = u * u * x0 + 2 * u * e * cx + e * e * x, py = u * u * y0 + 2 * u * e * cy + e * e * y;
        if (AG.cur && AG.cur.aborted) { res(); return; }
        setPos(px, py);
        const el = hoverTo(px, py);
        if (AG.onMove) AG.onMove(px, py, el); else if (el) { mev('pointermove', el, px, py); mev('mousemove', el, px, py); }
        if (t >= 1) res(); else setTimeout(step, 16);
      };
      step();
    });
    setPos(x, y); hoverTo(x, y);
  }
  const cd = f => Math.max(30, AG.cfg.click_delay * 1000 * (f == null ? 1 : f) * (AG.fast ? 0.4 : 1));
  const focusable = el => el && el.closest && el.closest('input,textarea,select,[tabindex],[contenteditable="true"]');
  async function click(x, y, o) {
    o = o || {}; await move(x, y, o);
    let el = elAt(x, y); if (!el) return null;
    const btn = o.right ? 2 : 0, bs = o.right ? 2 : 1;
    ringAt(x, y, o.right);
    mev('pointerdown', el, x, y, { button: btn, buttons: bs, detail: 1 }); mev('mousedown', el, x, y, { button: btn, buttons: bs, detail: 1 });
    const f = focusable(el); if (f && !o.right) { try { f.focus({ preventScroll: true }); } catch (e) {} } else if (!o.right && document.activeElement && document.activeElement !== document.body && !el.closest('.xpw,#win')) { try { document.activeElement.blur(); } catch (e) {} }
    await sleep(cd(.55));
    const el2 = el.isConnected ? el : (elAt(x, y) || document.body);
    if (o.right) { mev('contextmenu', el2, x, y, { button: 2, buttons: 2 }); mev('pointerup', el2, x, y, { button: 2 }); mev('mouseup', el2, x, y, { button: 2 }); }
    else { mev('pointerup', el2, x, y, { button: 0 }); mev('mouseup', el2, x, y, { button: 0 }); mev('click', el2, x, y, { button: 0, detail: 1 }); }
    await sleep(cd(.5));
    return el2;
  }
  async function dblclick(x, y) {
    await move(x, y); let el = elAt(x, y); if (!el) return null;
    for (let i = 1; i <= 2; i++) {
      ringAt(x, y); el = el.isConnected ? el : (elAt(x, y) || document.body);
      mev('pointerdown', el, x, y, { buttons: 1, detail: i }); mev('mousedown', el, x, y, { buttons: 1, detail: i });
      await sleep(cd(.3));
      mev('pointerup', el, x, y, {}); mev('mouseup', el, x, y, { detail: i }); mev('click', el, x, y, { detail: i });
      if (i === 1) await sleep(cd(.35));
    }
    mev('dblclick', el, x, y, { detail: 2 });
    await sleep(cd(.7)); return el;
  }
  async function drag(x0, y0, x1, y1, o) {
    o = o || {}; await move(x0, y0); const el = elAt(x0, y0); if (!el) throw new Error('拖拽起点没有元素');
    mev('pointerdown', el, x0, y0, { buttons: 1, detail: 1 }); mev('mousedown', el, x0, y0, { buttons: 1, detail: 1 });
    await sleep(cd(.7));
    AG.onMove = (x, y, e) => { const t = e || document.body; mev('pointermove', t, x, y, { buttons: 1 }); mev('mousemove', t, x, y, { buttons: 1 }); };
    try { await move(x1, y1, { speed: o.speed || AG.cfg.cursor_speed * 0.8 }); } finally { AG.onMove = null; }
    await sleep(cd(.5));
    const t = elAt(x1, y1) || document.body;
    mev('pointerup', t, x1, y1, {}); mev('mouseup', t, x1, y1, {});
    await sleep(cd(.7));
  }
  function key(type, k, target, o) {
    o = o || {}; const t = target || document.activeElement || document.body;
    const codes = { Enter: 13, Escape: 27, Backspace: 8, Delete: 46, ArrowLeft: 37, ArrowUp: 38, ArrowRight: 39, ArrowDown: 40, F5: 116, Tab: 9, ' ': 32 };
    const ev = new KeyboardEvent(type, { key: k, code: o.code || (k.length === 1 ? 'Key' + k.toUpperCase() : k), keyCode: codes[k] || (k.length === 1 ? k.toUpperCase().charCodeAt(0) : 0), bubbles: true, cancelable: true, composed: true });
    t.dispatchEvent(ev); return ev;
  }
  async function press(k, target) { key('keydown', k, target); await sleep(40); key('keyup', k, target); await sleep(60); }
  async function typeText(el, text) {
    if (!el) throw new Error('没有输入框');
    try { el.focus({ preventScroll: true }); } catch (e) {}
    const cps = Math.max(2, AG.cfg.typing_cps * (AG.fast ? 2 : 1)), base = 1000 / cps, isField = /^(INPUT|TEXTAREA)$/.test(el.tagName) || el.isContentEditable;
    setKind('ibeam');
    for (const ch of String(text)) {
      const ok = key('keydown', ch, el);
      if (!ok.defaultPrevented && isField) {
        const before = el.value;
        document.execCommand('insertText', false, ch);
        if (el.value === before && 'value' in el) { el.value += ch; el.dispatchEvent(new Event('input', { bubbles: true })); }
      }
      key('keyup', ch, el);
      await sleep(base * (0.7 + Math.random() * 0.6));
    }
  }
  Object.assign(AG, { move, click, dblclick, drag, press, typeText, mev, key, hoverTo, show, setKind });
  AG.rclick = (x, y) => click(x, y, { right: true });

  // ================= 元素 / 窗口 辅助 =================
  const designPt = (el, fx, fy) => { const r = drect(el); return { x: r.x + r.w * (fx == null ? .5 : fx), y: r.y + r.h * (fy == null ? .5 : fy) }; };
  function livePoint(el, fx, fy) {
    // 找 el 上没被别的东西盖住的点：先试给定点，再扫描
    const pts = [[fx == null ? .5 : fx, fy == null ? .5 : fy]]; for (const a of [.5, .25, .75, .1, .9]) for (const b of [.5, .25, .75, .15, .85]) pts.push([a, b]);
    for (const [a, b] of pts) { const p = designPt(el, a, b); const t = elAt(p.x, p.y); if (t && (el === t || el.contains(t))) return p; }
    return null;
  }
  async function clickEl(el, o) {
    o = o || {}; if (!shown(el)) throw new Error('元素不可见');
    const p = livePoint(el, o.fx, o.fy); if (!p) throw new Error('元素被盖住了');
    if (o.dbl) return dblclick(p.x, p.y); return click(p.x, p.y, o);
  }
  async function hoverEl(el, o) { const p = livePoint(el, o && o.fx, o && o.fy) || designPt(el); await move(p.x, p.y); return p; }
  async function waitFor(fn, ms, step) { const t0 = Date.now(); for (;;) { let v; try { v = fn(); } catch (e) { v = null; } if (v) return v; if (Date.now() - t0 > (ms || 2000)) return null; await sleep(step || 40); } }
  Object.assign(AG, { clickEl, hoverEl, waitFor, livePoint, designPt });

  const GAME_WIN = { 'game-cs': 'cs', 'game-vc': 'vc', 'game-war3': 'war3', 'game-ra2': 'ra2', 'game-mir2': 'mir2', 'game-au': 'audition', qqchat: 'qqchat', ttplayer: 'ttplayer', ttplaylist: 'ttplayer' };
  const appOf = w => w.app || GAME_WIN[w.id] || (WM.apps[w.id] ? w.id : null) || (/记事本/.test(w.title) ? 'notepad' : /Internet Explorer/.test(w.title) ? 'ie' : null);
  const prot = () => AG.cfg.protect || [];
  const rectOfWin = w => (w.state === 'max' ? { x: 0, y: 0, w: DW, h: DH - TB } : Object.assign({}, w.rect));
  const offPlayer = w => (w.id === 'ttplayer' && $('tt').classList.contains('off')) || (w.id === 'ttplaylist' && ($('pl').classList.contains('off') || $('pl').classList.contains('wm-min')));
  const winVisible = w => w && !w.closed && w.state !== 'min' && shown(w.el) && !offPlayer(w);
  function targetRects() {
    const T = []; const q = WM.byId.qqchat, t = WM.byId.ttplayer, p = WM.byId.ttplaylist, ktv = $('ktv');
    if (winVisible(q)) T.push({ id: 'qqchat', r: rectOfWin(q), z: q.z });
    if (winVisible(t)) T.push({ id: 'ttplayer', r: drect($('tt')), z: t.z });
    if (winVisible(p) && winVisible(t)) T.push({ id: 'ttplaylist', r: drect($('pl')), z: p.z });
    if (ktv && !ktv.classList.contains('off') && shown(ktv)) T.push({ id: 'lyrics', r: drect(ktv), z: -1 });
    return T;
  }
  const overlap = (a, b) => Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
  function coverOf(w, T) {
    let best = 0;
    for (const t of T) { if (t.id === w.id || (w.id === 'ttplaylist' && t.id === 'ttplayer') || (w.id === 'ttplayer' && t.id === 'ttplaylist')) continue; if (t.z >= w.z) continue; const a = t.r.w * t.r.h; if (a > 0) best = Math.max(best, overlap(rectOfWin(w), t.r) / a); }
    return best;
  }
  function chatVis() {
    const q = WM.byId.qqchat, win = $('win'); if (!winVisible(q)) return 0;
    const r = drect(win); let n = 0, tot = 0;
    for (let i = 0; i < 6; i++) for (let j = 0; j < 5; j++) { const x = r.x + r.w * (i + .5) / 6, y = r.y + r.h * (j + .5) / 5; if (x < 0 || y < 0 || x > DW || y > DH - TB) { tot++; continue; } tot++; const e = elAt(x, y); if (e && win.contains(e)) n++; }
    return n / tot;
  }
  const chatOk = () => { const q = WM.byId.qqchat; if (!q) return true; return winVisible(q) && chatVis() >= 0.5; };
  function winInfo(w, T, rank) {
    const r = rectOfWin(w), isP = prot().includes(w.id) || w.id === 'ttplaylist' || w.id === 'ttplayer';
    const cover = w.closed || w.state === 'min' || isP ? 0 : coverOf(w, T);
    return { id: w.id, app: appOf(w), title: w.title || '', state: (w.closed || offPlayer(w)) ? 'closed' : w.state, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.w), h: Math.round(r.h), z: rank, active: WM.active === w,
      dialog: !!w.dialogOnly, prot: prot().includes(w.id), blocks: cover >= 0.1, cover: +cover.toFixed(2) };
  }
  function findWins(t) {
    t = String(t == null ? '' : t); const ws = WM.wins.filter(w => !w.closed && !offPlayer(w)).sort((a, b) => b.z - a.z);
    const low = t.toLowerCase();
    if (low === 'active') return ws.filter(w => WM.active === w).concat(ws.filter(w => w.state !== 'min' && !w.dialogOnly)).slice(0, 1);
    if (low === 'chat' || low === 'qqchat') return ws.filter(w => w.id === 'qqchat');
    if (low === 'blocking') { const T = targetRects(); return ws.filter(w => !prot().includes(w.id) && w.state !== 'min' && w.id !== 'ttplayer' && w.id !== 'ttplaylist' && coverOf(w, T) >= 0.1).sort((a, b) => coverOf(b, T) - coverOf(a, T)); }
    if (low === 'all') return ws.filter(w => !prot().includes(w.id) && w.id !== 'ttplaylist');
    const byId = ws.filter(w => w.id === t); if (byId.length) return byId;
    const byApp = ws.filter(w => appOf(w) === t || (t === 'ttplayer' && w.id === 'ttplaylist')); if (byApp.length) return byApp;
    return ws.filter(w => t && (w.title || '').toLowerCase().includes(low));
  }
  Object.assign(AG, { winInfo, findWins, winVisible, chatOk, chatVis, targetRects, coverOf, appOf, rectOfWin, prot });

  // WM.open 包一层：给新开的窗口打上 app 标签（快照里要用）
  const _open = WM.open;
  WM.open = function (id, args) {
    const before = new Set(WM.wins); const w = _open.call(WM, id, args);
    const nw = (w && w.el) ? w : WM.wins.find(x => !before.has(x));
    if (nw && !nw.app && WM.apps[id] && id !== 'explorer') nw.app = id;
    if (nw && id === 'explorer' && !nw.app) nw.app = (args && args.path) || 'explorer';
    return w;
  };

  // ================= 快照 =================
  const WALL_NAME = () => { const f = WM.S.wall; const l = (WM.WALLS || []).find(x => x[1] === f); return l ? l[0] : (f ? f.split('/').pop() : '（无）'); };
  // 给 [ai_plus] 画面点评用的额外信息：特效 / 游戏 / 投票 / 蓝屏
  function aiBits() {
    const P = window.PLAYX, A = window.AIX, o = {};
    if (P && P.fxLive) { const fx = Object.keys(P.fxLive).filter(k => P.fxLive[k] > 0); if (fx.length) o.fx = fx; }
    if (A && A.game && A.game.state !== 'done') o.game = { name: A.game.name, prompt: A.game.prompt, round: A.game.round };
    if (P && P.vote && P.vote.state === 'open') o.vote = { title: P.vote.title };
    if (window.XP && XP.bsodAt && Date.now() - XP.bsodAt < 12000) o.bsod = true;
    return o;
  }
  function snapshot() {
    const T = targetRects(), all = WM.wins.filter(w => (!w.closed && !offPlayer(w)) || prot().includes(w.id)).sort((a, b) => b.z - a.z);
    const wins = all.map((w, i) => winInfo(w, T, i));
    const M = (DESK.music && DESK.music.S) || {}, mw = WM.byId.minesweeper, mine = mw && mw.mine && !mw.closed ? mw.mine.state() : null;
    const sm = $('startmenu');
    const q = WM.byId.qqchat;
    return { ts: Date.now(), wins, chat: q ? { state: q.closed ? 'closed' : q.state, vis: +chatVis().toFixed(2) } : null,
      icons: (WM.deskItems ? WM.deskItems() : []).map(i => ({ id: i.id, name: i.name })), wall: WALL_NAME(), wallMode: WM.S.wallMode,
      music: { on: !!M.on, playing: !!M.playing, title: M.title || '', artist: M.artist || '' }, start: !!(sm && sm.classList.contains('show')),
      dialogs: WM.wins.filter(w => w.dialogOnly && !w.closed).map(w => w.title), mine: mine ? { w: mine.W, h: mine.H, over: mine.over } : null,
      ai: aiBits(), vol: WM.vol == null ? 70 : WM.vol, mute: !!WM.mute, busy: AG.running, queue: AG.queue.length, xpbusy: !!(window.XP && XP.busy()) };
  }
  AG.snapshot = snapshot;

  // ================= 通信 =================
  let ws = null, retry = 1000, snapT = 0;
  const send = o => { if (ws && ws.readyState === 1) { try { ws.send(JSON.stringify(o)); } catch (e) {} } };
  function sendSnap() { clearTimeout(snapT); snapT = 0; try { send({ agent_snap: snapshot() }); } catch (e) { console.warn('agent snapshot', e); } }
  const snapSoon = () => { if (!snapT) snapT = setTimeout(sendSnap, 250); };
  document.addEventListener('wmchange', snapSoon); document.addEventListener('deskrefresh', snapSoon);
  setInterval(() => { if (ws && ws.readyState === 1) sendSnap(); }, 2500);
  function connect() {
    const url = Q.get('ws') || ((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
    ws = new WebSocket(url);
    ws.onopen = () => { retry = 1000; send({ agent: 1 }); sendSnap(); };
    ws.onmessage = e => {
      let m; try { m = JSON.parse(e.data); } catch (err) { return; }
      if (m.t === 'agent_cfg') { Object.assign(AG.cfg, m.cfg || {}); }
      else if (m.t === 'agent_do') {
        if (!AG.cfg.enabled) return send({ agent_result: { id: m.id, ok: false, results: [{ action: '*', ok: false, note: 'disabled' }], ms: 0 } });
        AG.enqueue({ id: m.id, by: m.by, text: m.text, actions: m.actions || [], idle: !!m.idle, speedf: m.speed || 0 });
      }
      else if (m.t === 'agent_abort') AG.abortIdle(m.reason);
      else if (m.t === 'vision_req') { if (window.AIX && AIX.onVisionReq) AIX.onVisionReq(m, send); else send({ vision: { id: m.id, img: '', ok: false } }); }
    };
    ws.onclose = () => { ws = null; setTimeout(connect, retry); retry = Math.min(retry * 2, 10000); };
    ws.onerror = () => {};
  }
  connect();

  // ================= 队列 / 执行 =================
  AG.enqueue = function (job) {
    if (AG.queue.length >= Math.max(1, AG.cfg.queue_max)) { reply(job.id, { id: job.id, ok: false, results: [{ action: '*', ok: false, note: 'queue full' }], ms: 0 }); return false; }
    AG.queue.push(job); AG.pump(); return true;
  };
  AG.pump = async function () {
    if (AG.running) return; AG.running = true;
    try {
      while (AG.queue.length) {
        const job = AG.queue.shift(), t0 = performance.now(), results = [];
        if (window.XP && XP.busy()) { const t1 = performance.now(); while (XP.busy() && performance.now() - t1 < 25000) await new Promise(r => setTimeout(r, 250)); }   // 开机 / 关机 / 蓝屏画面期间先等着
        AG.cur = job; job.before = winState();
        if (job.idle) { clearInterval(AG.guardT); AG.guardT = setInterval(() => { try { AG.idleGuard && AG.idleGuard(); } catch (e) {} }, 40); }
        AG.fast = AG.queue.length >= 2;
        show(); if (AG.cfg.show_who && job.by) { cur.querySelector('.ag-who').textContent = job.by; cur.classList.add('who'); }
        for (const a of job.actions) {
          if (job.aborted) { results.push({ action: a.action, ok: false, note: 'aborted', fatal: true }); break; }
          const r = await AG.runOne(a, job);
          results.push(r);
          try { await sleep(Math.max(0, AG.cfg.step_pause * 1000 * (AG.fast ? .3 : 1))); } catch (e) { break; }   // 被打断
          if (!r.ok && r.fatal) break;
        }
        if (job.idle) trackOpened(job.before);
        AG.cur = null; job.before = null;
        AG.jobs++;
        const res = { id: job.id, ok: results.every(r => r.ok), results, ms: Math.round(performance.now() - t0) };
        AG.log.push({ ts: Date.now(), by: job.by, text: job.text, results, ms: res.ms }); if (AG.log.length > 50) AG.log.shift();
        reply(job.id, res); sendSnap(); AG.checkGuard();
        cur.classList.remove('who');
      }
    } finally { clearInterval(AG.guardT); AG.running = false; AG.fast = false; AG.cur = null; idleSoon(); }
  };
  AG.runOne = async function (a, job) {
    const fn = AG.ACT[a.action];
    if (!fn) return { action: a.action, ok: false, note: '页面不支持这个动作' };
    const t0 = performance.now();
    try {
      const note = await Promise.race([fn(a, job || {}), new Promise((_, rej) => setTimeout(() => rej(new Error('动作超时')), 30000))]);
      return { action: a.action, ok: true, note: typeof note === 'string' ? note : '', ms: Math.round(performance.now() - t0) };
    } catch (e) {
      console.warn('[agent]', a.action, e);
      try { WM.closeMenus(); AG.onMove = null; } catch (e2) {}
      return { action: a.action, ok: false, note: String(e && e.message || e), ms: Math.round(performance.now() - t0), fatal: !!(job && job.aborted) };
    }
  };
  // 直接执行（测试 / 调试用）：AG.exec([{action:'close_window',target:'ra2'}], '我') → Promise<{ok,results,ms}>
  AG.localWait = {};
  AG.exec = function (actions, by) {
    return new Promise(res => { const id = 'local' + Date.now() + Math.floor(Math.random() * 99); AG.localWait[id] = res; AG.enqueue({ id, by: by || '本地', text: '', actions }); });
  };
  const reply = (id, res) => { const lw = AG.localWait[id]; if (lw) { delete AG.localWait[id]; lw(res); } else send({ agent_result: res }); };

  // ================= 自己玩电脑（idle）：打断 / 记录它打开的窗口 / 收拾 =================
  const winState = () => new Map(WM.wins.map(w => [w, { closed: !!w.closed, state: w.state }]));
  function trackOpened(before) {
    for (const w of WM.wins) {
      if ((AG.cfg.protect || []).includes(w.id)) continue;
      const b = before.get(w);
      if (!b) { if (!w.closed) AG.idleOpened.set(w, 'close'); }
      else if (b.closed && !w.closed) AG.idleOpened.set(w, 'close');
      else if (b.state === 'min' && w.state !== 'min' && !w.closed) AG.idleOpened.set(w, 'min');
    }
  }
  AG.openedByJob = w => { const j = AG.cur; if (!j || !j.idle) return true; const b = j.before && j.before.get(w); return AG.idleOpened.has(w) || !b || (b.closed && !w.closed) || (b.state === 'min' && w.state !== 'min'); };
  // 观众开口 / 来了指令：丢掉排队的 idle 任务，打断正在跑的，然后（不带动画地）收拾它打开的窗口
  AG.abortIdle = function (reason) {
    AG.queue = AG.queue.filter(j => { if (!j.idle) return true; reply(j.id, { id: j.id, ok: false, results: [{ action: '*', ok: false, note: 'aborted:' + (reason || '') }], ms: 0 }); return false; });
    if (AG.cur && AG.cur.idle) AG.cur.aborted = true;
    const dirty = AG.idleOpened.size || (AG.cur && AG.cur.idle);
    if (dirty && AG.cfg.idle_cleanup !== false) AG.queue.unshift({ id: 'idleclean' + Date.now(), by: '', text: '', actions: [{ action: '_idle_cleanup', instant: true }], internal: true });
    if (AG.running === false) AG.pump();
  };
  AG.idleCleanup = async function (instant) {
    const items = [...AG.idleOpened].reverse(); AG.idleOpened.clear(); const done = [];
    for (const [w, how] of items) {
      if (w.closed || (AG.cfg.protect || []).includes(w.id)) continue;
      try {
        if (instant) { if (how === 'min') w.min(); else { w._confirmed = true; w.close(); } }
        else if (how === 'min') await AG.ACT.minimize_window({ target: w.id });
        else { w._confirmed = true; await AG.ACT.close_window({ target: w.id }); }   // 记事本里的日记不存盘，也不弹“要保存吗”（弹窗会盖住群聊）
        done.push(w.title || w.id);
      } catch (e) { if (AG.cur && AG.cur.aborted) { try { w._confirmed = true; w.close(); } catch (e2) {} } }
    }
    try { WM.closeMenus(); } catch (e) {}
    return done.length ? '收拾了：' + done.join('、') : '没有要收拾的';
  };

  // ================= 撤销 =================
  AG.pushUndo = function (label, fn) { if (!AG.cfg.undo) return; AG.undo.push({ label, fn }); if (AG.undo.length > 20) AG.undo.shift(); };

  // ================= 受保护窗口（群聊）自动恢复 =================
  AG.checkGuard = function () {
    const ok = chatOk();
    if (ok) { AG.guardDue = 0; return; }
    if (!AG.guardDue) AG.guardDue = Date.now() + Math.max(2, AG.cfg.restore_secs) * 1000;
  };
  setInterval(() => {
    if (!AG.guardDue || AG.running || Date.now() < AG.guardDue) return;
    if (chatOk()) { AG.guardDue = 0; return; }
    AG.guardDue = 0;
    AG.enqueue({ id: 'guard' + Date.now(), by: '自动恢复', text: '群聊窗口自动恢复', actions: [{ action: '_restore_chat' }] });
  }, 1000);
})();
