// QQ秀装扮（?desk=xp）：群聊右上角“猪猪侠的QQ秀”面板里的形象可以换装 —— 帽子 / 眼镜 / 领饰 + 背景场景 + 飘落特效。
// 说明：这里没有、也不假装有腾讯 QQ秀的官方装扮素材（找不到可用的原版衣服素材）。所有配饰（SVG）、场景（CSS）和特效都是本项目自己画的，风格化的“贴纸式”装扮，
//       叠在猪猪侠的 18 张姿势图上（头的位置按每张图自动测出，见 HEAD 表）。QQ秀商城窗口是 2007 年风格的仿制界面。
(function () {
  const Q = window.QQX; if (!Q) return;
  const { h, esc } = WM, $ = id => document.getElementById(id), stage = $('stage'), pigtalk = $('pigtalk');
  if (!stage || !pigtalk) return;
  // 每张姿势图里脸的位置：[脸中心 x, 脸顶 y, 脸宽]（560×512 图里的像素，用肤色连通域测出来）+ 倾斜角
  const HEAD = { 0: [286, 100, 229, 0], 1: [278, 84, 245, 0], 2: [266, 88, 243, -4], 3: [306, 95, 212, 14], 4: [277, 160, 253, 0], 5: [257, 133, 239, 0], 6: [268, 156, 231, 8], 7: [263, 198, 215, 12], 8: [275, 118, 250, 0],
    9: [290, 88, 240, 0], 10: [292, 143, 244, 6], 11: [270, 129, 245, 0], 12: [301, 96, 239, 8], 13: [275, 131, 245, 0], 14: [258, 141, 217, 0], 15: [276, 97, 253, 0], 16: [283, 97, 249, 0], 17: [269, 167, 236, 8] };
  // ---------- 配饰（自绘 SVG；坐标以“脸顶中心”为原点，脸宽 = 240） ----------
  const heart = (x, y, s, c) => `<path transform="translate(${x} ${y}) scale(${s})" d="M0,10 C-26,-12 -12,-30 0,-14 C12,-30 26,-12 0,10Z" fill="${c}" stroke="#a01040" stroke-width="2"/>`;
  const PARTS = {
    hat: {
      santa: `<path d="M-105,-48 C-100,-140 -30,-185 45,-165 C70,-158 85,-140 80,-118 C60,-130 40,-125 30,-100 C60,-90 100,-70 105,-48Z" fill="#d62a2a" stroke="#8c1414" stroke-width="3"/><rect x="-114" y="-64" width="228" height="34" rx="17" fill="#f7f7f7" stroke="#cfcfcf" stroke-width="2"/><circle cx="82" cy="-120" r="18" fill="#fff" stroke="#cfcfcf" stroke-width="2"/>`,
      crown: `<path d="M-80,-50 L-92,-138 L-46,-100 L0,-152 L46,-100 L92,-138 L80,-50Z" fill="#f2c230" stroke="#a87a08" stroke-width="3"/><rect x="-82" y="-62" width="164" height="18" fill="#e0a812" stroke="#a87a08" stroke-width="2"/><circle cx="-92" cy="-138" r="8" fill="#e23a3a"/><circle cx="0" cy="-152" r="9" fill="#3a7de2"/><circle cx="92" cy="-138" r="8" fill="#e23a3a"/><circle cx="-34" cy="-53" r="5" fill="#fff"/><circle cx="0" cy="-53" r="5" fill="#e23a3a"/><circle cx="34" cy="-53" r="5" fill="#fff"/>`,
      sailor: `<path d="M-100,-50 Q-96,-122 0,-128 Q96,-122 100,-50Z" fill="#fafafa" stroke="#b9b9b9" stroke-width="3"/><rect x="-106" y="-66" width="212" height="26" rx="8" fill="#1f3d8f"/><path d="M-70,-96 L-52,-100 M-20,-112 L-6,-116" stroke="#1f3d8f" stroke-width="3"/><circle cx="0" cy="-53" r="7" fill="#f2c230"/>`,
      wizard: `<ellipse cx="0" cy="-48" rx="130" ry="20" fill="#4a2d8e" stroke="#2f1a66" stroke-width="3"/><path d="M-92,-52 Q-70,-120 -10,-205 Q30,-140 92,-52Z" fill="#5b3aa8" stroke="#2f1a66" stroke-width="3"/><rect x="-92" y="-72" width="184" height="16" fill="#f2c230"/><path transform="translate(-20,-125)" d="M0,-12 L4,-4 L13,-3 L6,3 L8,12 L0,7 L-8,12 L-6,3 L-13,-3 L-4,-4Z" fill="#ffe36a"/><circle cx="25" cy="-95" r="5" fill="#ffe36a"/>`,
      party: `<path d="M-58,-58 L0,-192 L58,-58Z" fill="#ff5fa8" stroke="#b02a6a" stroke-width="3"/><path d="M-40,-96 L38,-110 L48,-84 L-52,-70Z" fill="#ffd93a"/><circle cx="-20" cy="-75" r="6" fill="#3a9de2"/><circle cx="22" cy="-130" r="5" fill="#3a9de2"/><circle cx="0" cy="-193" r="14" fill="#ffd93a" stroke="#c9a000" stroke-width="2"/><path d="M-60,-56 Q0,-44 60,-56" stroke="#b02a6a" stroke-width="4" fill="none"/>`,
      headband: `<path d="M-95,-48 Q0,-95 95,-48" stroke="#ff7aa8" stroke-width="9" fill="none"/><path d="M-52,-72 Q-66,-110 -62,-136 M52,-72 Q66,-110 62,-136" stroke="#d6336c" stroke-width="4" fill="none"/>${heart(-62, -152, 1.2, '#ff4d8d')}${heart(62, -152, 1.2, '#ff4d8d')}`,
      tophat: `<rect x="-72" y="-172" width="144" height="116" rx="8" fill="#232323" stroke="#000" stroke-width="3"/><ellipse cx="0" cy="-54" rx="110" ry="16" fill="#232323" stroke="#000" stroke-width="3"/><rect x="-72" y="-88" width="144" height="22" fill="#b3202a"/><rect x="-14" y="-92" width="28" height="30" rx="3" fill="none" stroke="#f2c230" stroke-width="4"/>`,
      straw: `<ellipse cx="0" cy="-52" rx="138" ry="26" fill="#ecc96e" stroke="#a8842a" stroke-width="3"/><path d="M-82,-56 Q-82,-130 0,-130 Q82,-130 82,-56Z" fill="#f3d686" stroke="#a8842a" stroke-width="3"/><rect x="-82" y="-82" width="164" height="18" fill="#e0453a"/><path d="M-60,-100 L-40,-70 M-20,-118 L-10,-86 M20,-118 L10,-86 M60,-100 L40,-70" stroke="#c9a24a" stroke-width="2"/>`,
    },
    glasses: {
      shades: `<rect x="-104" y="12" width="92" height="52" rx="20" fill="#151515" stroke="#000" stroke-width="3"/><rect x="12" y="12" width="92" height="52" rx="20" fill="#151515" stroke="#000" stroke-width="3"/><path d="M-12,30 Q0,22 12,30" stroke="#000" stroke-width="5" fill="none"/><path d="M-96,22 L-60,18 M20,22 L56,18" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".55"/>`,
      monocle: `<circle cx="52" cy="38" r="34" fill="rgba(180,220,255,.25)" stroke="#d4a017" stroke-width="5"/><path d="M52,72 Q64,120 40,160" stroke="#d4a017" stroke-width="3" fill="none" stroke-dasharray="6 3"/>`,
    },
    neck: {
      scarf: `<path d="M-100,128 Q0,170 100,128 L100,152 Q0,194 -100,152Z" fill="#3aa14a" stroke="#1f6a2a" stroke-width="3"/><path d="M-80,120 Q0,150 80,120 L80,134 Q0,164 -80,134Z" fill="#e23a3a" opacity=".95"/><path d="M52,160 L84,160 L90,236 L58,236Z" fill="#3aa14a" stroke="#1f6a2a" stroke-width="3"/><path d="M56,184 L88,184 M58,208 L90,208" stroke="#e23a3a" stroke-width="7"/>`,
      bow: `<path d="M0,150 L-62,122 L-62,178Z M0,150 L62,122 L62,178Z" fill="#d93a4a" stroke="#8c1424" stroke-width="3"/><circle cx="0" cy="150" r="13" fill="#a8182b" stroke="#6a0e1a" stroke-width="2"/>`,
      chain: `<path d="M-84,126 Q0,214 84,126" stroke="#f2c230" stroke-width="9" fill="none" stroke-dasharray="1 11" stroke-linecap="round"/><circle cx="0" cy="190" r="17" fill="#f2c230" stroke="#a87a08" stroke-width="3"/><text x="0" y="197" text-anchor="middle" font-size="20" font-weight="700" fill="#a87a08">$</text>`,
      medal: `<path d="M-30,126 L0,190 L30,126" stroke="#2a62d6" stroke-width="16" fill="none"/><circle cx="0" cy="198" r="24" fill="#f2c230" stroke="#a87a08" stroke-width="4"/><path transform="translate(0 198)" d="M0,-13 L4,-4 L13,-3 L6,3 L8,12 L0,7 L-8,12 L-6,3 L-13,-3 L-4,-4Z" fill="#fff4b0"/>`,
      sailtie: `<path d="M-82,128 Q0,170 82,128 L0,206Z" fill="#1f3d8f" stroke="#102560" stroke-width="3"/><path d="M-60,138 L0,176 L60,138" stroke="#fff" stroke-width="4" fill="none"/>`,
    },
  };
  // ---------- 套装 ----------
  const OUTFITS = {
    default: { name: '默认造型', desc: '猪猪侠原来的样子', scene: '', fx: '' },
    santa: { name: '圣诞套装', desc: '圣诞帽 + 围巾，下着雪', hat: 'santa', neck: 'scarf', scene: 'snow', fx: 'snow' },
    cool: { name: '酷炫墨镜', desc: '墨镜 + 金项链，夜晚街头', glasses: 'shades', neck: 'chain', scene: 'night', fx: 'stars' },
    king: { name: '国王驾到', desc: '皇冠 + 勋章，金碧辉煌', hat: 'crown', neck: 'medal', scene: 'gold', fx: 'sparkle' },
    sailor: { name: '小水手', desc: '水手帽 + 领巾，出海啦', hat: 'sailor', neck: 'sailtie', scene: 'sea', fx: 'bubbles' },
    wizard: { name: '魔法学徒', desc: '魔法帽，星光闪闪', hat: 'wizard', scene: 'magic', fx: 'stars' },
    party: { name: '派对时间', desc: '派对帽 + 蝴蝶结，彩带飞舞', hat: 'party', neck: 'bow', scene: 'stage', fx: 'confetti' },
    love: { name: '爱心满满', desc: '爱心发箍 + 蝴蝶结', hat: 'headband', neck: 'bow', scene: 'pink', fx: 'hearts' },
    gentleman: { name: '绅士风度', desc: '礼帽 + 单片眼镜 + 领结', hat: 'tophat', glasses: 'monocle', neck: 'bow', scene: 'wood', fx: '' },
    summer: { name: '夏日海滩', desc: '草帽 + 墨镜，阳光沙滩', hat: 'straw', glasses: 'shades', scene: 'beach', fx: 'sparkle' },
  };
  const IDS = Object.keys(OUTFITS);
  // ---------- 场景（CSS，盖在 stage 背景上；default = 原来的背景图） ----------
  const SCENES = {
    snow: 'linear-gradient(#5d86c4,#c9defa 70%,#f4f9ff 71%,#fff)', night: 'radial-gradient(circle at 80% 18%,#fff6c4 0 9px,transparent 10px),linear-gradient(#0d1033,#2a2f6b 65%,#3a3a4c 66%,#2a2a35)',
    gold: 'radial-gradient(circle at 50% 38%,#fff2b8,#e8b43a 55%,#a8741a)', sea: 'linear-gradient(#8fd0ff 0,#c9ecff 48%,#2f86c8 49%,#1f5fa0)', magic: 'radial-gradient(circle at 50% 100%,#8a5de0,#3b1f78 60%,#1a0d3f)',
    stage: 'radial-gradient(ellipse at 50% 0,rgba(255,255,255,.7),transparent 55%),linear-gradient(#5b1d8a,#b0306a 70%,#4a1038)', pink: 'linear-gradient(#ffd0e4,#ff9cc4)', wood: 'linear-gradient(#6a4020,#8a5a30 60%,#4a2c14 61%,#3a2210)',
    beach: 'linear-gradient(#6ec6ff,#bfeaff 52%,#f4dc9a 53%,#e8c46a)',
  };
  // ---------- 特效（飘落的小东西） ----------
  const FX = { snow: ['❄', 16, 'fall'], hearts: ['❤', 14, 'rise'], stars: ['✦', 12, 'twinkle'], sparkle: ['✧', 12, 'twinkle'], bubbles: ['○', 12, 'rise'], confetti: ['■', 16, 'fall'] };
  const css = document.createElement('style'); css.textContent = `#qqx-outfit { position:absolute; inset:0; pointer-events:none; z-index:2; } #qqx-outfit svg { position:absolute; inset:0; width:100%; height:100%; overflow:visible; }
    #qqx-fx { position:absolute; inset:0; overflow:hidden; pointer-events:none; z-index:1; } #qqx-fx i { position:absolute; font-style:normal; line-height:1; opacity:0; text-shadow:0 0 3px rgba(255,255,255,.7); }
    @keyframes qxfall { 0% { transform:translate(0,-12px) rotate(0); opacity:0 } 10% { opacity:.95 } 100% { transform:translate(var(--dx,10px),190px) rotate(300deg); opacity:.9 } }
    @keyframes qxrise { 0% { transform:translate(0,0) scale(.6); opacity:0 } 15% { opacity:.95 } 100% { transform:translate(var(--dx,10px),-170px) scale(1.1); opacity:0 } }
    @keyframes qxtw { 0%,100% { transform:scale(.5); opacity:.1 } 50% { transform:scale(1.2); opacity:1 } }
    .stage.qx-scene { transition: background .5s; } .qx-name { position:absolute; left:4px; top:4px; z-index:4; font:11px var(--xpfont); color:#fff; background:rgba(0,0,0,.45); border-radius:3px; padding:0 5px; line-height:16px; opacity:0; transition:opacity .4s; pointer-events:none; } .qx-name.on { opacity:1; }
    .qs { display:flex; flex-direction:column; height:100%; font:12px var(--xpfont); background:#fff; } .qs .hd { height:44px; flex:none; display:flex; align-items:center; gap:10px; padding:0 12px; background:linear-gradient(#ffb4d6,#ff7eb4); color:#fff; font-size:15px; font-weight:700; text-shadow:1px 1px 1px rgba(120,0,60,.6); }
    .qs .bd { flex:1; display:flex; min-height:0; } .qs .pv { width:176px; flex:none; background:#f6f1ff; border-right:1px solid #cdb8f0; display:flex; flex-direction:column; align-items:center; padding:8px 6px; gap:6px; }
    .qs .pv .st { position:relative; width:160px; height:160px; border:1px solid #9a7ad0; background:#e9a63f url(gg/bg.webp) 50% 100%/cover; overflow:hidden; } .qs .pv .st .pg { position:absolute; left:0; right:0; bottom:0; aspect-ratio:560/512; } .qs .pv .st img { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; } .qs .pv .st svg { position:absolute; inset:0; width:100%; height:100%; overflow:visible; }
    .qs .gr { flex:1; overflow:auto; padding:8px; display:grid; grid-template-columns:repeat(auto-fill,minmax(112px,1fr)); gap:8px; align-content:start; } .qs .cd { border:1px solid #d6c9ee; border-radius:4px; background:#fff; padding:4px; text-align:center; cursor:default; } .qs .cd:hover { background:#f3ecff; } .qs .cd.sel { border-color:#d6336c; background:#ffeaf3; } .qs .cd.wear { box-shadow:0 0 0 2px #3aa14a inset; }
    .qs .cd .th { position:relative; height:64px; border-radius:3px; overflow:hidden; background:#e9a63f url(gg/bg.webp) 50% 100%/cover; } .qs .cd .th svg { position:absolute; inset:0; width:100%; height:100%; } .qs .cd b { display:block; margin-top:3px; font-size:12px; } .qs .cd span { color:#777; font-size:11px; }
    .qs .ft { height:26px; flex:none; display:flex; align-items:center; gap:8px; padding:0 8px; background:#ece9d8; border-top:1px solid #aca899; } .qs .ft .st2 { margin-left:auto; color:#555; }`;
  document.head.appendChild(css);
  // ---------- 叠加层 ----------
  const ovl = h('div', { id: 'qqx-outfit' }); pigtalk.appendChild(ovl);
  const fxl = h('div', { id: 'qqx-fx' }); stage.insertBefore(fxl, stage.firstChild);
  const nameTag = h('div', { class: 'qx-name' }); stage.appendChild(nameTag);
  const S = { cur: 'default', base: Q.store.get('outfit', null), timer: 0, pose: 8, since: Date.now() };
  const parts = o => (o.hat ? PARTS.hat[o.hat] || '' : '') + (o.glasses ? PARTS.glasses[o.glasses] || '' : '') + (o.neck ? PARTS.neck[o.neck] || '' : '');
  const svgFor = (id, pose) => {
    const o = OUTFITS[id] || OUTFITS.default, hd = HEAD[pose] || HEAD[8], k = hd[2] / 240;
    // 帽子在最外层（盖住头顶），眼镜 / 领饰跟着头倾斜
    return `<svg viewBox="0 0 560 512" preserveAspectRatio="xMidYMax meet"><g transform="translate(${hd[0]} ${hd[1]}) rotate(${hd[3]}) scale(${k})">${parts(o)}</g></svg>`;
  };
  Q.show = { OUTFITS, IDS, HEAD, svgFor };
  function poseNow() { const on = [$('poseA'), $('poseB')].find(i => i && i.classList.contains('on')); const m = on && /p(\d\d)\.webp/.exec(on.getAttribute('src') || ''); return m ? +m[1] : 8; }
  function draw() { S.pose = poseNow(); ovl.innerHTML = svgFor(S.cur, S.pose); }
  new MutationObserver(draw).observe(pigtalk, { subtree: true, attributes: true, attributeFilter: ['src', 'class'] });
  function setScene(o) { if (!Q.on('show_scene') || !o.scene) { stage.style.background = ''; stage.classList.remove('qx-scene'); return; } stage.classList.add('qx-scene'); stage.style.background = SCENES[o.scene] + ' 50% 100% / cover no-repeat'; }
  let fxT = 0;
  function setFx(kind) {
    clearInterval(fxT); fxl.innerHTML = ''; const f = FX[kind]; if (!f || !Q.on('show_scene')) return;
    const colors = kind === 'confetti' ? ['#ff5fa8', '#ffd93a', '#3a9de2', '#4cd964', '#b06ae8'] : kind === 'hearts' ? ['#ff4d8d', '#ff7aa8', '#e8336c'] : kind === 'snow' ? ['#fff'] : kind === 'bubbles' ? ['#fff'] : ['#fff6a0', '#ffffff', '#ffd93a'];
    const spawn = () => { if (fxl.children.length > 16) return; const i = h('i', { text: f[0] }); const w = stage.clientWidth || 200; i.style.left = Math.random() * (w - 14) + 'px'; i.style.top = f[2] === 'rise' ? ((stage.clientHeight || 190) - 30 - Math.random() * 40) + 'px' : (f[2] === 'twinkle' ? Math.random() * (stage.clientHeight || 190) * .8 + 'px' : '0px');
      i.style.fontSize = f[1] * (.6 + Math.random() * .7) + 'px'; i.style.color = colors[Math.floor(Math.random() * colors.length)]; i.style.setProperty('--dx', (Math.random() * 40 - 20) + 'px'); const dur = f[2] === 'twinkle' ? 1.2 + Math.random() * 1.6 : 2.6 + Math.random() * 2.2;
      i.style.animation = `${f[2] === 'fall' ? 'qxfall' : f[2] === 'rise' ? 'qxrise' : 'qxtw'} ${dur}s ${f[2] === 'twinkle' ? 'ease-in-out' : 'linear'} 1 forwards`; fxl.appendChild(i); setTimeout(() => i.remove(), dur * 1000 + 100); };
    for (let n = 0; n < 6; n++) setTimeout(spawn, n * 180); fxT = setInterval(spawn, 380);
  }
  function wear(id, o) {
    o = o || {}; if (!OUTFITS[id]) return false; if (S.timer) { clearTimeout(S.timer); S.timer = 0; }
    S.cur = id; S.since = Date.now(); const def = OUTFITS[id]; draw(); setScene(def); setFx(def.fx);
    nameTag.textContent = def.name; nameTag.classList.add('on'); setTimeout(() => nameTag.classList.remove('on'), 2600);
    if (o.perm) { S.base = id; Q.store.set('outfit', id); }
    else if (id !== base() && Q.cfg.outfit_revert > 0) S.timer = setTimeout(() => wear(base(), { revert: true }), Q.cfg.outfit_revert * 1000);
    document.dispatchEvent(new CustomEvent('qqoutfit', { detail: { id, name: def.name, perm: !!o.perm } })); return true;
  }
  const base = () => OUTFITS[S.base] ? S.base : (OUTFITS[Q.cfg.outfit] ? Q.cfg.outfit : 'default');
  Q.show.wear = wear; Q.show.base = base;
  const resolve = a => { a = String(a || '').trim(); if (OUTFITS[a]) return a; if (a === 'next' || a === '') return IDS[(IDS.indexOf(S.cur) + 1) % IDS.length]; if (a === 'random') { const c = IDS.filter(x => x !== S.cur && x !== 'default'); return c[Math.floor(Math.random() * c.length)]; } if (a === 'reset') return base();
    return IDS.find(k => OUTFITS[k].name.includes(a) || a.includes(OUTFITS[k].name) || a.includes(OUTFITS[k].name.slice(0, 2))) || null; };
  Q.show.resolve = resolve;
  Q.actions.outfit = (arg, ev) => { if (!Q.on('show')) return false; const id = resolve(arg); if (!id) return false; const ok = wear(id, {}); if (ok && ev && ev.name && Q.cfg.gift_effects && ev.t === 'gift') Q.sysLine('猪猪侠 换上了「' + esc(OUTFITS[id].name) + '」（' + esc(ev.name) + ' 送出了 ' + esc(ev.gift || '礼物') + '）'); return ok; };
  Q.actions.fx = (arg) => { setFx(arg); setTimeout(() => setFx(OUTFITS[S.cur].fx), 6000); return true; };
  // ---------- QQ秀商城窗口 ----------
  function shop() {
    return WM.create({ id: 'qqshow', title: 'QQ秀商城 - 猪猪侠的衣橱', icon: 'xp/ui/qq16.png', w: 640, h: 440, minW: 480, minH: 320, content: win => {
      let sel = S.cur; const st = h('div', { class: 'st' }), nm = h('b', { style: 'font-size:13px' }), ds = h('span', { style: 'color:#666;text-align:center;font-size:11px' }), gr = h('div', { class: 'gr' }), status = h('span', { class: 'st2' });
      const mini = id => { const hd = HEAD[8], k = hd[2] / 240; return `<svg viewBox="0 0 560 512" preserveAspectRatio="xMidYMax meet"><g transform="translate(${hd[0]} ${hd[1]}) scale(${k})">${parts(OUTFITS[id])}</g></svg>`; };
      const prev = () => { const o = OUTFITS[sel]; st.style.background = o.scene && Q.on('show_scene') ? SCENES[o.scene] + ' 50% 100%/cover' : ''; st.innerHTML = '<div class="pg"><img src="gg/p08.webp" alt="">' + mini(sel) + '</div>'; nm.textContent = o.name; ds.textContent = o.desc; };
      const cards = () => { gr.innerHTML = ''; IDS.forEach(id => { const o = OUTFITS[id]; const c = h('div', { class: 'cd' + (id === sel ? ' sel' : '') + (id === S.cur ? ' wear' : ''), 'data-outfit': id, onclick: () => { sel = id; prev(); cards(); }, ondblclick: () => put(true) }, [h('div', { class: 'th', style: o.scene && Q.on('show_scene') ? `background:${SCENES[o.scene]} 50% 100%/cover` : '', html: '<svg viewBox="0 70 560 330" preserveAspectRatio="xMidYMid meet">' + mini(id).replace(/^<svg[^>]*>|<\/svg>$/g, '') + '</svg><img src="gg/p08.webp" style="position:absolute;left:50%;bottom:0;height:100%;transform:translateX(-50%)">' }), h('b', { text: o.name }), h('span', { text: id === S.cur ? '正在穿着' : o.desc })]); gr.appendChild(c); }); };
      const put = perm => { if (wear(sel, { perm })) { status.textContent = '已穿上「' + OUTFITS[sel].name + '」' + (perm ? '（已保存，刷新后仍是它）' : '（' + (Q.cfg.outfit_revert > 0 ? Q.cfg.outfit_revert + ' 秒后换回' : '一直穿着') + '）'); cards(); } };
      const hd = h('div', { class: 'hd' }, [h('span', { text: '👗' }), h('span', { text: 'QQ秀商城' }), h('span', { text: '—— 百变随心，时尚我先！', style: 'font-weight:400;font-size:12px;opacity:.95' })]);
      const pv = h('div', { class: 'pv' }, [st, nm, ds, h('button', { class: 'xbtn', 'data-act': 'wear', text: '试穿', onclick: () => put(false) }), h('button', { class: 'xbtn', 'data-act': 'save', text: '穿上并保存', onclick: () => put(true) })]);
      const ft = h('div', { class: 'ft' }, [h('span', { text: '提示：观众送礼物 / 发“换装”指令也会换，' + (Q.cfg.outfit_revert > 0 ? Q.cfg.outfit_revert + ' 秒后自动换回。' : '换了不会自动换回。') }), status]);
      document.addEventListener('qqoutfit', () => { if (!win.closed) { cards(); } });
      prev(); cards(); win.qs = { sel: id => { sel = id; prev(); cards(); }, put, state: () => ({ sel, cur: S.cur }) };
      return h('div', { class: 'qs' }, [hd, h('div', { class: 'bd' }, [pv, gr]), ft]);
    } });
  }
  WM.register('qqshow', { open: () => Q.on('show') ? shop() : WM.alert('QQ秀', '装扮商城没有开启（[qq] show）。', { kind: 'info' }) });
  const btn = $('showname'); btn && btn.addEventListener('click', () => WM.open('qqshow'));
  Q.mods.show = { state: () => ({ cur: S.cur, base: base(), pose: S.pose, since: S.since }), wear, OUTFITS };
  Q.ready.then(() => { if (!Q.on('show')) { ovl.remove(); return; } const b = base(); if (b !== 'default') wear(b, {}); else draw(); });
})();
