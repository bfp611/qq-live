// QQ宠物（?desk=xp）：桌面任务栏上溜达的 QQ 企鹅，有 饱腹 / 清洁 / 心情 / 精力；能喂食、洗澡、玩耍、睡觉、唱歌，会对礼物和弹幕有反应。
// 企鹅动画帧是 QQ 宠物原版素材（web/xp/qqpet/penguin.png，来源和版权见 CREDITS.md）；吃的、泡泡、皮球是 emoji 小道具（自己加的，不是原版）。
(function () {
  const Q = window.QQX; if (!Q) return;
  const { root, h, esc, DW, DH, TB } = WM;
  const SHEET = 'xp/qqpet/penguin.png', CW = 192, CH = 208, SW = 1536, SH = 1872;
  const ROWS = { idle: [0, 6, 170], left: [1, 8, 95], right: [2, 8, 95], sing: [3, 4, 200], hi: [4, 5, 150], lie: [5, 8, 240], sleep: [6, 6, 320], pant: [7, 6, 150], work: [8, 8, 210] };
  const FOODS = { apple: ['🍎', '苹果', 18, 2], fish: ['🐟', '小鱼干', 26, 4], cake: ['🍰', '蛋糕', 34, 12], drumstick: ['🍗', '大鸡腿', 42, 6] };
  const TOYS = { ball: ['⚽', '皮球'], music: ['🎤', '唱卡拉OK'] };
  const css = document.createElement('style'); css.textContent = `#qqx-pet { position:absolute; z-index:8500; cursor:pointer; user-select:none; touch-action:none; } #qqx-pet .sp { position:absolute; inset:0; background:url(${SHEET}) 0 0 no-repeat; image-rendering:auto; filter:drop-shadow(0 2px 1px rgba(0,0,0,.35)); }
    #qqx-pet .em { position:absolute; left:50%; top:-8px; font-size:30px; line-height:1; pointer-events:none; text-shadow:0 1px 2px rgba(0,0,0,.3); } #qqx-pet .bub { position:absolute; left:50%; bottom:100%; transform:translateX(-50%); margin-bottom:2px; white-space:nowrap; font:12px var(--xpfont); background:#ffffe1; border:1px solid #333; border-radius:6px; padding:2px 7px; pointer-events:none; box-shadow:2px 2px 2px rgba(0,0,0,.25); opacity:0; transition:opacity .2s; max-width:230px; overflow:hidden; text-overflow:ellipsis; }
    #qqx-pet .bub.on { opacity:1; } #qqx-pet .bub:after { content:''; position:absolute; left:50%; bottom:-5px; margin-left:-4px; width:7px; height:7px; background:#ffffe1; border-right:1px solid #333; border-bottom:1px solid #333; transform:rotate(45deg); }
    @keyframes qpfly { 0% { transform:translate(-50%,-30px) scale(.6); opacity:0 } 25% { opacity:1 } 100% { transform:translate(-50%,36px) scale(1); opacity:0 } } @keyframes qpbub { 0% { transform:translate(-50%,0) scale(.5); opacity:0 } 30% { opacity:.95 } 100% { transform:translate(calc(-50% + var(--dx,0px)),-46px) scale(1.2); opacity:0 } } @keyframes qpbounce { 0%,100% { transform:translate(-50%,10px) } 50% { transform:translate(-50%,-34px) } } @keyframes qpjig { 0%,100% { transform:translateX(0) } 25% { transform:translateX(-4px) rotate(-3deg) } 75% { transform:translateX(4px) rotate(3deg) } }
    #qqx-pet.jig .sp { animation:qpjig .25s linear infinite; }
    .qp { display:flex; flex-direction:column; height:100%; font:12px var(--xpfont); background:#e6f1ff; } .qp .tp { display:flex; flex:none; gap:10px; padding:10px; } .qp .view { position:relative; width:150px; height:170px; border:2px inset #fff; background:linear-gradient(#bfe0ff,#e9f6ff 68%,#8fd36a 69%,#6ab84a); flex:none; overflow:hidden; } .qp .view .sp { position:absolute; left:50%; bottom:6px; margin-left:-72px; width:144px; height:156px; background:url(${SHEET}) 0 0 no-repeat; }
    .qp .inf { flex:1; display:flex; flex-direction:column; gap:5px; } .qp .inf h3 { margin:0; font:700 14px var(--xpfont); color:#0b3d91; } .qp .bar { display:flex; align-items:center; gap:6px; } .qp .bar label { width:34px; color:#333; } .qp .bar .tr { flex:1; height:12px; border:1px solid #6b8cc0; background:#fff; border-radius:2px; overflow:hidden; } .qp .bar .tr i { display:block; height:100%; background:linear-gradient(#9be36a,#46b01e); } .qp .bar .tr i.lo { background:linear-gradient(#ffb36a,#e8501e); } .qp .bar span { width:30px; text-align:right; color:#444; }
    .qp .ops { display:flex; flex-wrap:wrap; gap:6px; padding:0 10px 6px; align-items:center; } .qp .ops select { font:12px var(--xpfont); } .qp .lg { flex:1; margin:0 10px 8px; background:#fff; border:1px solid #7f9db9; overflow:auto; padding:4px 6px; line-height:1.55; color:#333; } .qp .lg p { margin:0; } .qp .lg p b { color:#0b3d91; }`;
  document.head.appendChild(css);
  // ---------- 状态 ----------
  const nowM = () => Date.now() / 60000;
  const P = Object.assign({ name: '', hunger: 72, clean: 80, mood: 85, energy: 90, exp: 0, born: Date.now(), t: nowM(), log: [] }, Q.store.get('pet', {}));
  const clamp = v => Math.max(0, Math.min(100, v)), save = () => { P.t = nowM(); Q.store.set('pet', P); };
  const rate = { hunger: 1.1, clean: .7, mood: .8, energy: .35 };
  function decay(mins) { mins = Math.min(mins, 240); const k = mins * Q.cfg.pet_decay; P.hunger = clamp(P.hunger - rate.hunger * k); P.clean = clamp(P.clean - rate.clean * k); P.energy = clamp(P.energy - rate.energy * k * (P.sleeping ? -6 : 1));
    P.mood = clamp(P.mood - rate.mood * k * (P.hunger < 25 || P.clean < 25 ? 2 : 1)); }
  const nm = () => P.name || Q.cfg.pet_name || '球球';
  const level = () => 1 + Math.floor(Math.sqrt(P.exp));
  const status = () => P.sleeping ? '睡觉中 💤' : Math.min(P.hunger, P.clean, P.mood) < 8 ? '快撑不住了…' : P.hunger < 25 ? '饿坏了' : P.clean < 25 ? '脏兮兮' : P.mood < 30 ? '闷闷不乐' : P.mood > 75 ? '很开心' : '还不错';
  // ---------- 精灵 ----------
  let SC = .5, W = CW * SC, H = CH * SC;
  const el = h('div', { id: 'qqx-pet', title: '', style: `width:${W}px;height:${H}px` }); const sp = h('div', { class: 'sp' }), bub = h('div', { class: 'bub' }); el.append(sp, bub);
  const groundY = () => DH - TB - H + 7;
  const M = { x: Q.store.get('pet_x', 160), y: 0, mode: 'idle', until: 0, dir: 1, frame: 0, ft: 0, drag: false, fall: 0 };
  function place() { el.style.left = Math.round(M.x) + 'px'; el.style.top = Math.round(M.y) + 'px'; }
  M.y = groundY();
  let anim = 'idle', fi = 0, fT = 0;
  function setAnim(a) { if (a === anim) return; anim = a; fi = 0; frame(); }
  function frame() { const [r, n] = ROWS[anim]; sp.style.backgroundSize = (SW * SC) + 'px ' + (SH * SC) + 'px'; sp.style.backgroundPosition = (-(fi % n) * CW * SC) + 'px ' + (-r * CH * SC) + 'px'; }
  function tickAnim() { const [, n, ms] = ROWS[anim]; fi = (fi + 1) % n; frame(); fT = setTimeout(tickAnim, ms); } 
  // ---------- 说话泡泡 / 小道具 ----------
  let bt = 0;
  function say(t, ms) { if (!Q.on('pet_bubbles') || !t) return; bub.textContent = t; bub.classList.add('on'); clearTimeout(bt); bt = setTimeout(() => bub.classList.remove('on'), ms || 3200); }
  function prop(emoji, kind, ms) { const e = h('div', { class: 'em', text: emoji }); e.style.animation = kind === 'bubble' ? `qpbub ${ms || 1.4}s ease-out forwards` : kind === 'bounce' ? `qpbounce .5s ease-in-out ${Math.round((ms || 2) / .5)}` : `qpfly ${ms || 1.1}s ease-in forwards`; e.style.setProperty('--dx', (Math.random() * 30 - 15) + 'px'); el.appendChild(e); setTimeout(() => e.remove(), (ms || 1.4) * 1000 + 100); }
  const logAdd = (who, text) => { P.log.push({ at: Date.now(), who: who || '', text }); if (P.log.length > 30) P.log.shift(); };
  // ---------- 行为 ----------
  function hold(mode, secs) { M.mode = mode; M.until = Date.now() + secs * 1000; }
  function auto() {
    const t = Date.now(); if (M.drag || M.fall) return;
    if (P.sleeping) { if (t > P.sleeping && P.energy >= 70 || t > P.sleeping + 20000) { P.sleeping = 0; say('睡得真香～', 2200); save(); } else { setAnim('sleep'); return; } }
    if (t < M.until && M.mode !== 'idle' && M.mode !== 'walk') { setAnim({ eat: 'idle', bath: 'hi', play: 'right', sing: 'sing', hi: 'hi', work: 'work' }[M.mode] || 'idle'); return; }
    const low = Math.min(P.hunger, P.clean, P.mood);
    if (low < 8) { setAnim('lie'); return; }
    if (P.hunger < 25) { setAnim('pant'); if (Math.random() < .004) say('我饿了…谁给我点吃的？'); return; }
    if (M.mode === 'walk' && t < M.until && Q.on('pet_wander')) { setAnim(M.dir > 0 ? 'right' : 'left'); return; }
    M.mode = 'idle'; setAnim('idle');
    if (t > (M.next || 0)) { M.next = t + 3500 + Math.random() * 6500; const r = Math.random(); if (r < .5 && Q.on('pet_wander')) { M.dir = M.x > DW / 2 ? -1 : 1; if (Math.random() < .35) M.dir *= -1; hold('walk', 2 + Math.random() * 4); } else if (r < .62 && P.mood > 55) { hold('sing', 2.5); } else if (r < .72) { hold('hi', 1.6); } }
  }
  function move(dt) { if (M.mode === 'walk' && !P.sleeping && !M.drag && Q.on('pet_wander') && (anim === 'left' || anim === 'right')) { M.x += M.dir * 34 * dt; if (M.x < 6) { M.x = 6; M.dir = 1; } if (M.x > DW - W - 6) { M.x = DW - W - 6; M.dir = -1; } place(); } 
    if (M.mode === 'play' && Date.now() < M.until) { M.x += M.dir * 70 * dt; if (M.x < 6 || M.x > DW - W - 6) M.dir *= -1; M.x = Math.max(6, Math.min(DW - W - 6, M.x)); place(); } }
  let lt = performance.now();
  setInterval(() => { const n = performance.now(), dt = Math.min(.2, (n - lt) / 1000); lt = n; auto(); move(dt); if (!M.drag && !M.fall && M.y !== groundY()) { M.y = groundY(); place(); } }, 100);
  setInterval(() => { decay(5 / 60); save(); updatePanel(); }, 5000);
  function care(what, o) {
    o = o || {}; const who = o.who || ''; let ok = true;
    if (!Q.on('pet')) return false;
    if (P.sleeping && what !== 'wake') { if (what === 'sleep') return true; P.sleeping = 0; }
    if (what === 'feed') { const key = FOODS[o.food] ? o.food : Object.keys(FOODS)[Math.floor(Math.random() * 4)], f = FOODS[key]; P.hunger = clamp(P.hunger + f[2]); P.mood = clamp(P.mood + f[3]); prop(f[0], 'fly', 1.1); hold('eat', 2.4); say(P.hunger >= 90 ? '吃得好饱呀～' : '好吃！谢谢' + (who || '主人') + '～'); logAdd(who, '喂了 ' + f[1]); if (window.XP && XP.snd) XP.snd('notify', 'qq'); }
    else if (what === 'bath') { P.clean = clamp(P.clean + 45); P.mood = clamp(P.mood + 5); for (let i = 0; i < 4; i++) setTimeout(() => prop(i % 2 ? '🧼' : '💧', 'bubble', 1.5), i * 260); hold('bath', 2.6); el.classList.add('jig'); setTimeout(() => el.classList.remove('jig'), 2400); say('洗澡澡，香喷喷！'); logAdd(who, '给它洗了澡'); if (window.XP && XP.snd) XP.snd('balloon', 'qq'); }
    else if (what === 'play') { const t = TOYS[o.toy] ? o.toy : 'ball'; P.mood = clamp(P.mood + 25); P.hunger = clamp(P.hunger - 5); P.energy = clamp(P.energy - 8); prop(TOYS[t][0], 'bounce', 2.5); M.dir = Math.random() < .5 ? -1 : 1; hold(t === 'music' ? 'sing' : 'play', 3); say(t === 'music' ? '啦啦啦～' : '来玩球！'); logAdd(who, '陪它玩了' + TOYS[t][1]); }
    else if (what === 'sleep') { P.sleeping = Date.now() + 12000; say('Zzz…晚安'); logAdd(who, '哄它睡觉'); }
    else if (what === 'sing') { P.mood = clamp(P.mood + 8); hold('sing', 3.5); say('♪ 我是一只快乐的小企鹅 ♪'); logAdd(who, '听它唱了歌'); }
    else if (what === 'hi') { hold('hi', 2); say(o.text || '你好呀～'); }
    else if (what === 'work') { hold('work', 4); say('送信去咯～'); }
    else ok = false;
    if (ok && ['feed', 'bath', 'play', 'sleep', 'sing'].includes(what)) P.exp += 1; save(); updatePanel(); document.dispatchEvent(new CustomEvent('qqpet', { detail: { what, who } })); return ok;
  }
  // ---------- 事件 / 礼物 ----------
  Q.actions.pet = (arg, ev) => { const [what, x] = String(arg || 'play').split(':'); const o = { who: ev && ev.name, food: x, toy: x }; if (what === 'panel') { WM.open('qqpet'); return true; } if (what === 'name') { P.name = (x || '').slice(0, 8) || P.name; save(); updatePanel(); return true; } if (what === 'random') return care(['feed', 'bath', 'play', 'sing'][Math.floor(Math.random() * 4)], o); return care(what, o); };
  Q.sub('chat', ev => { if (!Q.on('pet') || P.sleeping) return; const t = ev.text || ''; if (t.includes(nm())) { hold('hi', 2); say('叫我干嘛呀？@' + (ev.name || '').slice(0, 6)); } else if (Math.random() < .08 && M.mode === 'idle') { hold('hi', 1.4); } });
  Q.sub('follow', ev => { if (!Q.on('pet') || P.sleeping) return; hold('sing', 3); say('欢迎 ' + (ev.name || '新朋友').slice(0, 8) + '！'); P.mood = clamp(P.mood + 3); save(); });
  // ---------- 交互：点 / 双击 / 右键 / 拖动 ----------
  const menu = (x, y) => WM.menu([{ t: nm() + '  Lv.' + level(), dis: true }, '-', { t: '喂食', sub: Object.entries(FOODS).map(([k, f]) => ({ t: f[0] + ' ' + f[1], on: () => care('feed', { food: k, who: '你' }) })) }, { t: '洗澡', on: () => care('bath', { who: '你' }) },
    { t: '玩耍', sub: Object.entries(TOYS).map(([k, f]) => ({ t: f[0] + ' ' + f[1], on: () => care('play', { toy: k, who: '你' }) })) }, { t: '睡觉', on: () => care('sleep', { who: '你' }) }, { t: '唱歌', on: () => care('sing', { who: '你' }) }, '-', { t: '宠物状态…', bold: true, on: () => WM.open('qqpet') },
    { t: Q.cfg.pet_wander ? '站着别动' : '到处溜达', on: () => { Q.cfg.pet_wander = !Q.cfg.pet_wander; } }], x, y);
  el.addEventListener('contextmenu', e => { e.preventDefault(); e.stopPropagation(); const p = WM.toRoot(e); menu(p.x - 10, p.y - 150); });
  el.addEventListener('dblclick', e => { e.stopPropagation(); WM.open('qqpet'); });
  let dr = null;
  el.addEventListener('pointerdown', e => { if (e.button !== 0) return; e.stopPropagation(); const p = WM.toRoot(e); dr = { dx: p.x - M.x, dy: p.y - M.y, moved: false, x0: p.x, y0: p.y }; try { el.setPointerCapture(e.pointerId); } catch (er) {} });
  el.addEventListener('pointermove', e => { if (!dr) return; const p = WM.toRoot(e); if (!dr.moved && Math.hypot(p.x - dr.x0, p.y - dr.y0) < 5) return; dr.moved = true; M.drag = true; M.x = Math.max(0, Math.min(DW - W, p.x - dr.dx)); M.y = Math.max(0, Math.min(groundY(), p.y - dr.dy)); setAnim('hi'); place(); });
  el.addEventListener('pointerup', e => { if (!dr) return; const was = dr.moved; dr = null; try { el.releasePointerCapture(e.pointerId); } catch (er) {} if (was) { M.drag = false; M.fall = 1; const t0 = performance.now(), y0 = M.y; const f = n => { const k = Math.min(1, (n - t0) / 380); M.y = y0 + (groundY() - y0) * k * k; place(); if (k < 1) requestAnimationFrame(f); else { M.fall = 0; Q.store.set('pet_x', M.x); say('哎呀，吓我一跳！'); } }; requestAnimationFrame(f); }
    else { const lines = ['摸摸头～', '你好呀！我是' + nm() + '～', P.hunger < 40 ? '肚子咕咕叫了…' : '今天过得怎么样？', '双击我看看状态哦']; hold('hi', 1.6); say(lines[Math.floor(Math.random() * lines.length)]); } });
  // ---------- 状态窗口 ----------
  let pv = null;
  const bar = (k, label) => { const i = h('i'), s = h('span'); return { k, row: h('div', { class: 'bar', 'data-bar': k }, [h('label', { text: label }), h('div', { class: 'tr' }, [i]), s]), upd: () => { const v = Math.round(P[k]); i.style.width = v + '%'; i.className = v < 30 ? 'lo' : ''; s.textContent = v + '%'; } }; };
  function updatePanel() { if (!pv || !pv.win || pv.win.closed) { pv = null; return; } pv.bars.forEach(b => b.upd()); pv.title.textContent = nm() + '  Lv.' + level(); pv.stat.textContent = '状态：' + status() + '　年龄：' + Math.max(1, Math.ceil((Date.now() - P.born) / 86400000)) + ' 天　经验：' + P.exp;
    pv.lg.innerHTML = P.log.slice(-8).reverse().map(l => '<p>' + new Date(l.at).toTimeString().slice(0, 8) + ' ' + (l.who ? '<b>' + esc(l.who) + '</b> ' : '') + esc(l.text) + '</p>').join('') || '<p>还没有人照顾过它…</p>'; const [r, n] = ROWS[anim]; pv.sp.style.backgroundSize = (SW * .75) + 'px ' + (SH * .75) + 'px'; pv.sp.style.backgroundPosition = (-(fi % n) * CW * .75) + 'px ' + (-r * CH * .75) + 'px'; }
  setInterval(() => { if (pv) updatePanel(); }, 250);
  function panel() {
    return WM.create({ id: 'qqpet', title: 'QQ宠物 - ' + nm(), icon: 'xp/ui/qq16.png', w: 430, h: 400, minW: 380, minH: 340, content: win => {
      const sp2 = h('div', { class: 'sp' }), view = h('div', { class: 'view' }, [sp2]), title = h('h3'), stat = h('div', { style: 'color:#444' }), bars = [bar('hunger', '饱腹'), bar('clean', '清洁'), bar('mood', '心情'), bar('energy', '精力')], lg = h('div', { class: 'lg' });
      const food = h('select', { 'data-sel': 'food' }, Object.entries(FOODS).map(([k, f]) => h('option', { value: k, text: f[0] + ' ' + f[1] }))), toy = h('select', { 'data-sel': 'toy' }, Object.entries(TOYS).map(([k, f]) => h('option', { value: k, text: f[0] + ' ' + f[1] })));
      const b = (t, a, fn) => h('button', { class: 'xbtn', 'data-act': a, text: t, onclick: fn });
      const ops = h('div', { class: 'ops' }, [b('喂食', 'feed', () => care('feed', { food: food.value, who: '你' })), food, b('洗澡', 'bath', () => care('bath', { who: '你' })), b('玩耍', 'play', () => care('play', { toy: toy.value, who: '你' })), toy, b('睡觉', 'sleep', () => care('sleep', { who: '你' })), b('唱歌', 'sing', () => care('sing', { who: '你' })),
        b('改名', 'rename', () => WM.prompt('给宠物改名', '新名字（最多 8 个字）：', nm(), v => { if (v) { P.name = v.slice(0, 8); save(); win.setTitle('QQ宠物 - ' + nm()); updatePanel(); } }))]);
      pv = { win, sp: sp2, title, stat, bars, lg }; setTimeout(updatePanel, 0);
      return h('div', { class: 'qp' }, [h('div', { class: 'tp' }, [view, h('div', { class: 'inf' }, [title, stat].concat(bars.map(x => x.row)))]), ops, lg]);
    } });
  }
  WM.register('qqpet', { open: () => Q.on('pet') ? panel() : WM.alert('QQ宠物', 'QQ宠物没有开启（[qq] pet）。', { kind: 'info' }) });
  Q.pet = { care, say, el, state: () => ({ name: nm(), hunger: Math.round(P.hunger), clean: Math.round(P.clean), mood: Math.round(P.mood), energy: Math.round(P.energy), level: level(), exp: P.exp, anim, mode: M.mode, sleeping: !!P.sleeping, x: Math.round(M.x), status: status() }), set: o => { Object.assign(P, o); save(); updatePanel(); }, FOODS, TOYS };
  Q.mods.pet = { state: () => Q.pet.state() };
  Q.ready.then(() => {
    if (!Q.on('pet')) return; decay((nowM() - (P.t || nowM())) * .5);   // 离线的时候也会饿，不过只算一半
    const px = parseFloat(Q.cfg.pet_x); if (!isNaN(px)) M.x = px; else if (!Q.store.get('pet_x', null)) M.x = 200 + Math.random() * 500;
    root.appendChild(el); place(); frame(); tickAnim(); if (Q.cfg.pet_panel_open) WM.open('qqpet'); setTimeout(() => say('大家好，我是' + nm() + '！', 3000), 1200);
  });
})();
