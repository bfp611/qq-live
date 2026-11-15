// 游戏窗口：CS 1.6 / 罪恶都市 / 魔兽争霸III / 红色警戒2 = 启动画面 → 游戏菜单 → “开始游戏”播放真实游戏录像片段（ESC 返回）；
// 热血传奇 = 登录 → 选服 → 游戏画面（官方截图）+ 可聊天；劲舞团 = 可玩的方向键节奏小游戏（自制复刻）
(function () {
  if (!window.WM || !WM.ready) return;
  const { h, ICO } = WM;
  const st = document.createElement('style'); st.textContent = `
  .gm { position:absolute; inset:0; background:#000; overflow:hidden; font-family:Arial,"Microsoft YaHei","SimHei",sans-serif; color:#fff; user-select:none; }
  .gm .bg { position:absolute; inset:0; background-size:cover; background-position:center; filter:brightness(.55) saturate(1.1); } .gm .bg.blur { filter:blur(3px) brightness(.5); transform:scale(1.04); }
  .gm video { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; background:#000; }
  .gm .load { position:absolute; inset:0; background:#000; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; z-index:5; } .gm .load .bar { width:260px; height:10px; border:1px solid #888; padding:1px; } .gm .load .bar i { display:block; height:100%; width:0; background:linear-gradient(#ddd,#888); transition:width 1s linear; }
  .gm .hud { position:absolute; right:8px; top:8px; display:flex; gap:6px; z-index:6; opacity:0; transition:opacity .25s; } .gm.hov .hud { opacity:1; } .gm .hud b { background:rgba(0,0,0,.6); border:1px solid #888; padding:3px 8px; font:12px Arial; border-radius:2px; } .gm .hud b:hover { background:rgba(60,60,60,.85); }
  .gm .tip { position:absolute; left:0; right:0; bottom:6px; text-align:center; font:12px Arial; color:#ddd; text-shadow:0 0 3px #000; z-index:6; opacity:0; transition:opacity .4s; } .gm.hov .tip { opacity:1; }
  .gm .menu { position:absolute; z-index:4; } .gm .mi { cursor:pointer; } .gm .modal { position:absolute; inset:0; background:rgba(0,0,0,.55); z-index:8; display:flex; align-items:center; justify-content:center; }
  .gm .modal .pn { min-width:300px; background:#333; border:1px solid #aaa; padding:14px 18px 12px; box-shadow:0 0 14px #000; } .gm .modal .pn h4 { margin:0 0 8px; font:700 14px Arial; } .gm .modal .pn button { margin-top:10px; padding:2px 16px; }
  /* CS */ .gm.cs .menu { left:44px; bottom:84px; font:700 22px/38px Arial; color:#c9c9a0; text-shadow:0 0 2px #000; } .gm.cs .mi:hover { color:#fff; text-shadow:0 0 8px #ffc800; } .gm.cs .logo { position:absolute; left:40px; top:30px; font:700 46px Arial; color:#d8d890; letter-spacing:1px; text-shadow:2px 2px #000; z-index:4; } .gm.cs .logo small { display:block; font-size:14px; letter-spacing:3px; color:#bbb; }
  /* VC */ .gm.vc .logo { position:absolute; left:0; right:0; top:34px; text-align:center; z-index:4; font:italic 700 54px "Arial Black",Impact,Arial; background:linear-gradient(#ff7ccf,#ff2f9a 55%,#4cd0ff); -webkit-background-clip:text; color:transparent; filter:drop-shadow(2px 3px 0 #1a0033); } .gm.vc .logo small { display:block; font:700 18px Arial; color:#ffe; -webkit-text-fill-color:#ffe; letter-spacing:6px; } .gm.vc .menu { left:0; right:0; bottom:60px; text-align:center; font:700 22px/40px "Arial Black",Arial; letter-spacing:2px; } .gm.vc .mi { color:#ff9ad9; text-shadow:2px 2px #1a0033; } .gm.vc .mi:hover { color:#fff; }
  /* WC3 */ .gm.war3 .logo { position:absolute; left:0; right:0; top:26px; text-align:center; z-index:4; font:700 40px Georgia,"Times New Roman",serif; color:#e9c46a; text-shadow:0 0 12px #6a3b00,2px 2px #000; letter-spacing:2px; } .gm.war3 .logo small { display:block; font:italic 20px Georgia; color:#9fd0ff; letter-spacing:6px; } .gm.war3 .menu { left:50%; transform:translateX(-50%); bottom:50px; width:250px; } .gm.war3 .mi { background:linear-gradient(#3a3226,#15110b); border:2px solid #8a6d2a; border-radius:3px; margin:7px 0; padding:7px 0; text-align:center; font:700 17px Georgia; color:#e9c46a; box-shadow:inset 0 0 6px #000,0 0 6px #000; } .gm.war3 .mi:hover { color:#fff; border-color:#ffd24a; box-shadow:inset 0 0 8px #000,0 0 12px #c80; }
  /* RA2 */ .gm.ra2 .logo { position:absolute; left:34px; top:28px; z-index:4; font:italic 700 44px "Arial Black",Impact; color:#ff2a1a; text-shadow:2px 2px #000,0 0 14px #800; } .gm.ra2 .logo small { display:block; font:700 20px Arial; color:#ddd; letter-spacing:5px; font-style:normal; } .gm.ra2 .menu { right:34px; top:50%; transform:translateY(-50%); width:230px; background:linear-gradient(90deg,rgba(60,0,0,.7),rgba(10,10,10,.85)); border:2px solid #7a2a24; padding:10px; } .gm.ra2 .mi { margin:6px 0; padding:8px 0; text-align:center; background:linear-gradient(#5a5f66,#23262a); border:1px solid #a33; font:700 16px Arial; letter-spacing:1px; color:#eee; } .gm.ra2 .mi:hover { background:linear-gradient(#a02a24,#4a0f0c); color:#fff; }
  /* mir2 */ .gm.mir2 { background:#07070a; } .gm.mir2 .dlg { position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); width:300px; background:linear-gradient(#2c2418,#15110b); border:2px solid #9a7b34; padding:16px 20px; box-shadow:0 0 20px #000; color:#e8d6a0; font:14px "SimSun",serif; z-index:4; } .gm.mir2 .dlg h3 { margin:0 0 12px; text-align:center; color:#ffd36a; font:700 18px "SimHei",sans-serif; } .gm.mir2 .dlg input { width:150px; background:#000; border:1px solid #6b5628; color:#fff; padding:2px 4px; font:14px Arial; } .gm.mir2 .dlg label { display:flex; justify-content:space-between; margin:8px 0; } .gm.mir2 .dlg button { background:linear-gradient(#5b4a22,#2b2210); border:1px solid #9a7b34; color:#ffe9a8; padding:3px 18px; font:14px "SimSun",serif; margin:10px 6px 0; } .gm.mir2 .srv { padding:3px 8px; border:1px solid transparent; } .gm.mir2 .srv:hover, .gm.mir2 .srv.on { background:#4a3a14; border-color:#9a7b34; }
  .gm.mir2 .scene { position:absolute; inset:0; background:#000 url(xp/game/mir2.png) center/cover no-repeat; image-rendering:pixelated; animation:mirdrift 40s ease-in-out infinite alternate; } @keyframes mirdrift { 0% { background-position:30% 40%; transform:scale(1.02); } 100% { background-position:70% 60%; transform:scale(1.08); } } .gm.mir2 .chat { position:absolute; left:8px; bottom:70px; width:46%; font:13px/17px "SimSun",serif; text-shadow:1px 1px #000; z-index:3; max-height:150px; overflow:hidden; } .gm.mir2 .chat div.sys { color:#ffe97a; } .gm.mir2 .chat div.me { color:#fff; } .gm.mir2 .cin { position:absolute; left:8px; bottom:46px; width:46%; z-index:3; display:none; } .gm.mir2 .cin input { width:100%; background:rgba(0,0,0,.65); border:1px solid #9a7b34; color:#fff; font:13px "SimSun"; padding:2px 4px; box-sizing:border-box; }
  .gm.mir2 .bar2 { position:absolute; left:0; right:0; bottom:0; height:38px; background:linear-gradient(#2a2216,#0d0a06); border-top:2px solid #9a7b34; z-index:3; display:flex; align-items:center; padding:0 12px; gap:12px; font:12px "SimSun"; color:#ffe9a8; } .gm.mir2 .orb { width:26px; height:26px; border-radius:50%; } .gm.mir2 .hp { background:radial-gradient(circle at 35% 30%,#ff8a8a,#a00000); } .gm.mir2 .mp { background:radial-gradient(circle at 35% 30%,#8ab4ff,#0030a0); }
  .gm.au canvas { position:absolute; inset:0; width:100%; height:100%; } .gm.au .ui { position:absolute; z-index:3; font-weight:700; text-shadow:0 0 6px #f0f,1px 1px #000; pointer-events:none; }
  `; document.head.appendChild(st);

  const GAMES = {
    cs: { title: 'Counter-Strike', icon: '890_16.png', poster: 'xp/video/cs.jpg', video: 'xp/video/cs.mp4', cls: 'cs', logo: 'COUNTER-STRIKE<small>Condition Zero · 1.6</small>', menu: ['新游戏', '查找服务器', '创建服务器', '配置', '观看演示', '控制台', '退出'], play: '新游戏', note: '游戏录像：ESWC 2007 CS 1.6 总决赛（Internet Archive）' },
    vc: { title: 'Grand Theft Auto: Vice City', icon: '889_16.png', poster: 'xp/video/vc.jpg', video: 'xp/video/vc.mp4', cls: 'vc', logo: 'GRAND THEFT AUTO<small>VICE CITY</small>', menu: ['开始新游戏', '载入游戏', '简报', '选项', '退出'], play: '开始新游戏', note: '游戏录像：GTA Vice City PS2 PAL（Internet Archive，公有领域标记）' },
    war3: { title: 'Warcraft III: The Frozen Throne', icon: '891_16.png', poster: 'xp/video/war3.jpg', video: 'xp/video/war3.mp4', cls: 'war3', logo: 'WARCRAFT III<small>THE FROZEN THRONE</small>', menu: ['单人游戏', '局域网游戏', 'Battle.net', '观看录像', '选项', '退出游戏'], play: '单人游戏', note: '游戏片段：G4TV《魔兽争霸III：冰封王座》PC 预告（Internet Archive）' },
    ra2: { title: "Command & Conquer: Red Alert 2 - Yuri's Revenge", icon: '892_16.png', poster: 'xp/video/ra2.jpg', video: 'xp/video/ra2.mp4', cls: 'ra2', logo: 'RED ALERT 2<small>YURI’S REVENGE</small>', menu: ['遭遇战', '战役', '多人游戏', '载入游戏', '选项', '退出'], play: '遭遇战', note: '游戏录像：红色警戒2 尤里的复仇 对战（Internet Archive）' },
  };
  function gameWin(id) {
    const G = GAMES[id];
    return WM.create({ id: 'game-' + id, title: G.title, icon: ICO(G.icon), w: 800, h: 628, x: 240, y: 14, minW: 400, minH: 300, content: win => {
      const root = h('div', { class: 'gm ' + G.cls }), vid = h('video', { src: G.video, loop: true, muted: true, playsinline: true, preload: 'auto', style: 'display:none' }); vid.muted = true;
      const bg = h('div', { class: 'bg', style: `background-image:url(${G.poster})` });
      const menu = h('div', { class: 'menu' }), logo = h('div', { class: 'logo', html: G.logo });
      const hud = h('div', { class: 'hud' }, [h('b', { text: '🔇 声音', onclick: e => { e.stopPropagation(); vid.muted = !vid.muted; e.target.textContent = vid.muted ? '🔇 声音' : '🔊 声音'; } }), h('b', { text: '⏸ 暂停', onclick: e => { e.stopPropagation(); if (vid.paused) { vid.play(); e.target.textContent = '⏸ 暂停'; } else { vid.pause(); e.target.textContent = '▶ 继续'; } } }), h('b', { text: 'ESC 返回菜单', onclick: () => toMenu() })]);
      const tip = h('div', { class: 'tip', text: '按 ESC 返回主菜单 · ' + G.note });
      let phase = 'boot';
      const modal = (t, body) => { const m = h('div', { class: 'modal' }, [h('div', { class: 'pn' }, [h('h4', { text: t }), h('div', { text: body, style: 'font-size:13px;line-height:19px' }), h('button', { text: '确定', onclick: () => m.remove() })])]); root.appendChild(m); };
      const act = t => { if (t === G.play) return toPlay(); if (/退出/.test(t)) return win.close(); if (t === '观看演示' || t === '观看录像') return toPlay(); modal(t, '“' + t + '”在演示环境中不可用。\n请选择“' + G.play + '”观看游戏画面。'); };
      G.menu.forEach(t => menu.appendChild(h('div', { class: 'mi', text: t, onclick: () => act(t) })));
      const load = h('div', { class: 'load' }, [h('div', { text: G.title, style: 'font:700 20px Arial' }), h('div', { class: 'bar' }, [h('i')]), h('div', { text: 'Loading...', style: 'font:12px Arial;color:#aaa' })]);
      function toMenu() { phase = 'menu'; vid.pause(); vid.style.display = 'none'; bg.style.display = ''; menu.style.display = ''; logo.style.display = ''; root.classList.remove('hov'); root.querySelectorAll('.modal').forEach(m => m.remove()); tip.textContent = G.menu.length ? '单击菜单项选择 · ' + G.note : ''; }
      function toPlay() { phase = 'play'; bg.style.display = 'none'; menu.style.display = 'none'; logo.style.display = 'none'; vid.style.display = ''; vid.currentTime = 0; vid.play().catch(() => {}); tip.textContent = '按 ESC 返回主菜单 · ' + G.note; root.classList.add('hov'); setTimeout(() => phase === 'play' && root.classList.remove('hov'), 3500); }
      root.append(bg, vid, logo, menu, hud, tip, load);
      menu.style.display = 'none'; logo.style.display = 'none';
      setTimeout(() => { load.querySelector('i').style.width = '100%'; }, 30);
      setTimeout(() => { load.remove(); toMenu(); }, 1250);
      root.addEventListener('mousemove', () => { root.classList.add('hov'); clearTimeout(root._t); root._t = setTimeout(() => phase === 'play' && root.classList.remove('hov'), 2200); });
      root.addEventListener('click', () => { if (phase === 'play') { vid.paused ? vid.play() : 0; } });
      const kd = e => { if (e.key === 'Escape' && WM.active === win && phase === 'play') toMenu(); }; document.addEventListener('keydown', kd);
      win.o.onclose = () => { document.removeEventListener('keydown', kd); vid.pause(); vid.removeAttribute('src'); vid.load(); };
      win.onstate = () => { if (win.state === 'min') vid.pause(); else if (phase === 'play') vid.play().catch(() => {}); };
      return root;
    } });
  }
  Object.keys(GAMES).forEach(id => WM.register(id, { open: () => gameWin(id) }));

  // ================= 热血传奇 =================
  WM.register('mir2', { open: () => WM.create({ id: 'game-mir2', title: '热血传奇', icon: ICO('888_16.png'), w: 800, h: 628, x: 250, y: 14, minW: 400, minH: 300, content: win => {
    const root = h('div', { class: 'gm mir2' });
    const bg = h('div', { class: 'scene', style: 'filter:brightness(.35) blur(2px)' }); root.appendChild(bg);
    let phase = 'login', user = '';
    const dlg = h('div', { class: 'dlg' }); root.appendChild(dlg);
    function showLogin() { phase = 'login'; dlg.style.display = ''; dlg.innerHTML = '<h3>热 血 传 奇</h3><label>账号：<input id="m-u" value="gg_bond" maxlength="16"></label><label>密码：<input id="m-p" type="password" value="123456"></label><div style="text-align:center"></div>'; const b = dlg.lastChild; b.append(h('button', { text: '登录', onclick: () => { user = dlg.querySelector('#m-u').value || '玩家'; showServers(); } }), h('button', { text: '取消', onclick: () => win.close() }), h('button', { text: '新账号', onclick: () => modal('新账号', '请到官方网站注册新账号。') })); }
    function showServers() { phase = 'srv'; dlg.innerHTML = '<h3>选择服务器</h3>'; let sel = 0; const names = ['盛大一区 · 蓝月', '盛大二区 · 沙城', '盛大三区 · 比奇', '盛大四区 · 玛法']; const rows = names.map((n, i) => h('div', { class: 'srv' + (i === 0 ? ' on' : ''), text: n + '    （流畅）', onclick: () => { sel = i; rows.forEach((r, j) => r.classList.toggle('on', j === i)); }, ondblclick: () => start() })); rows.forEach(r => dlg.appendChild(r)); dlg.appendChild(h('div', { style: 'text-align:center;margin-top:8px' }, [h('button', { text: '进入游戏', onclick: () => start() }), h('button', { text: '返回', onclick: showLogin })])); }
    function modal(t, body) { const m = h('div', { class: 'modal' }, [h('div', { class: 'pn', style: 'background:#2c2418;border-color:#9a7b34' }, [h('h4', { text: t }), h('div', { text: body, style: 'font-size:13px' }), h('button', { text: '确定', onclick: () => m.remove() })])]); root.appendChild(m); }
    const chat = h('div', { class: 'chat' }), cin = h('div', { class: 'cin' }, [h('input', { maxlength: 60 })]);
    const bar = h('div', { class: 'bar2' }, [h('div', { class: 'orb hp' }), h('div', { class: 'orb mp' }), h('span', { text: '' }), h('span', { text: '回车: 聊天 · F1~F8 技能 · 地图: 比奇省', style: 'margin-left:auto;opacity:.8' })]);
    const say = (t, c) => { chat.appendChild(h('div', { class: c || 'sys', text: t })); while (chat.children.length > 8) chat.firstChild.remove(); };
    function start() { phase = 'game'; dlg.style.display = 'none'; bg.style.filter = ''; root.append(chat, cin, bar); bar.children[2].textContent = user + '  Lv.35 战士'; say('[系统] 欢迎来到热血传奇！'); say('[系统] 当前地图：比奇省，请注意安全。'); say('[行会] 沙巴克攻城战将在今晚 20:00 开始', 'sys'); }
    const kd = e => { if (WM.active !== win || phase !== 'game') return; const inp = cin.firstChild; if (e.key === 'Enter') { if (cin.style.display === 'block') { const v = inp.value.trim(); if (v) say(user + ': ' + v, 'me'); inp.value = ''; cin.style.display = 'none'; } else { cin.style.display = 'block'; inp.focus(); } e.preventDefault(); } else if (e.key === 'Escape') { cin.style.display = 'none'; } };
    document.addEventListener('keydown', kd); win.o.onclose = () => document.removeEventListener('keydown', kd);
    showLogin(); return root;
  } }) });

  // ================= 劲舞团（方向键节奏游戏，自制复刻）=================
  WM.register('audition', { open: () => WM.create({ id: 'game-au', title: '劲舞团', icon: ICO('894_16.png'), w: 760, h: 628, x: 260, y: 14, minW: 420, minH: 320, content: win => {
    const root = h('div', { class: 'gm au' }), cv = h('canvas'); root.appendChild(cv); const ctx = cv.getContext('2d');
    const ui = h('div', { class: 'ui', style: 'left:0;right:0;top:10px;text-align:center;font-size:20px' }); root.appendChild(ui);
    const KEYS = ['ArrowLeft', 'ArrowDown', 'ArrowUp', 'ArrowRight'], GL = ['←', '↓', '↑', '→'], COL = ['#ff4fa0', '#46d3ff', '#ffe34a', '#7dff6a'];
    let W = 760, H = 560, run = true, notes = [], t0 = performance.now(), score = 0, combo = 0, maxCombo = 0, judge = '', judgeAt = 0, gauge = 50, auto = true, bpm = 126, nextBeat = 0, hits = { PERFECT: 0, COOL: 0, GOOD: 0, BAD: 0, MISS: 0 }, flash = [0, 0, 0, 0], beatPulse = 0, started = false;
    const spd = 340, hitY = () => H - 110, noteY = n => hitY() - (n.t - now()) * spd / 1000; const now = () => performance.now() - t0;
    const pat = () => { const out = []; let b = 0; const bars = []; for (let i = 0; i < 64; i++) bars.push(i); for (const i of bars) { const beat = 60000 / bpm; const t = 2400 + i * beat * 0.5; const r = Math.sin(i * 12.9898) * 43758.5453; const lane = Math.floor((r - Math.floor(r)) * 4); if (i % 4 === 3 && i % 8 !== 7) continue; out.push({ t, lane, hit: false, miss: false }); if (i % 16 === 15) out.push({ t, lane: (lane + 2) % 4, hit: false, miss: false }); } return out; };
    const reset = () => { notes = pat(); t0 = performance.now(); score = 0; combo = 0; maxCombo = 0; gauge = 50; hits = { PERFECT: 0, COOL: 0, GOOD: 0, BAD: 0, MISS: 0 }; judge = ''; };
    reset();
    function size() { const r = root.getBoundingClientRect(), k = r.width / (root.offsetWidth || 1) || 1; W = root.offsetWidth; H = root.offsetHeight; cv.width = W; cv.height = H; } const ro = new ResizeObserver(size); ro.observe(root); size();
    function judgeNote(lane) { const n = notes.filter(x => x.lane === lane && !x.hit && !x.miss).sort((a, b) => a.t - b.t)[0]; flash[lane] = 1; if (!n) return; const d = Math.abs(n.t - now()); if (d > 190) return; n.hit = true; const j = d < 45 ? 'PERFECT' : d < 90 ? 'COOL' : d < 140 ? 'GOOD' : 'BAD'; hits[j]++; judge = j; judgeAt = now(); if (j === 'BAD') { combo = 0; gauge = Math.max(0, gauge - 2); } else { combo++; maxCombo = Math.max(maxCombo, combo); gauge = Math.min(100, gauge + 2); } score += { PERFECT: 300, COOL: 200, GOOD: 100, BAD: 20 }[j] * (1 + Math.floor(combo / 10) * 0.1) | 0; }
    const kd = e => { if (WM.active !== win) return; const l = KEYS.indexOf(e.key); if (l >= 0) { e.preventDefault(); auto = false; judgeNote(l); } else if (e.key === ' ') { e.preventDefault(); auto = !auto; } else if (e.key === 'r' || e.key === 'R') reset(); };
    document.addEventListener('keydown', kd); const dancers = [0, 1];
    let raf; const loop = () => {
      if (!run) return; raf = requestAnimationFrame(loop); const t = now(), g = ctx; g.clearRect(0, 0, W, H);
      const bg = g.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#1b0a3a'); bg.addColorStop(.6, '#5a1a7a'); bg.addColorStop(1, '#a02a8a'); g.fillStyle = bg; g.fillRect(0, 0, W, H);
      const beat = 60000 / bpm, ph = (t % beat) / beat; beatPulse = 1 - ph;
      for (let i = 0; i < 6; i++) { const a = Math.sin(t / 900 + i) * 0.5; g.save(); g.translate(W * (i + .5) / 6, 0); g.rotate(a * .5); const gr = g.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, `hsla(${(i * 60 + t / 20) % 360},90%,70%,${.30 + .25 * beatPulse})`); gr.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gr; g.beginPath(); g.moveTo(-4, 0); g.lineTo(4, 0); g.lineTo(60, H); g.lineTo(-60, H); g.fill(); g.restore(); }
      g.fillStyle = 'rgba(255,255,255,.07)'; const fy = H - 170; for (let i = 0; i < 12; i++) for (let j = 0; j < 3; j++) { g.fillStyle = (i + j + Math.floor(t / beat)) % 2 ? 'rgba(255,120,220,.20)' : 'rgba(120,200,255,.18)'; g.fillRect(i * W / 12, fy + j * 14, W / 12 - 2, 12); }
      // 舞者（火柴人）
      dancers.forEach(d => { const cx = W * (d ? .72 : .28), cy = H * .45, s = Math.sin(t / beat * Math.PI * 2 + d * 1.6); g.strokeStyle = d ? '#7dffe9' : '#ffd0f0'; g.lineWidth = 7; g.lineCap = 'round'; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + s * 8, cy + 60); g.moveTo(cx, cy + 10); g.lineTo(cx - 36 - s * 22, cy + 30 - Math.abs(s) * 30); g.moveTo(cx, cy + 10); g.lineTo(cx + 36 + s * 22, cy + 30 + s * 12); g.moveTo(cx + s * 8, cy + 60); g.lineTo(cx - 24 + s * 20, cy + 118); g.moveTo(cx + s * 8, cy + 60); g.lineTo(cx + 24 + s * 20, cy + 118); g.stroke(); g.fillStyle = g.strokeStyle; g.beginPath(); g.arc(cx + s * 3, cy - 20, 16, 0, 7); g.fill(); });
      // 轨道
      const lw = 66, lx = (W - lw * 4) / 2; g.fillStyle = 'rgba(10,0,30,.55)'; g.fillRect(lx - 6, 0, lw * 4 + 12, H); const hy = hitY();
      for (let i = 0; i < 4; i++) { flash[i] *= .86; g.fillStyle = `rgba(255,255,255,${.04 + flash[i] * .35})`; g.fillRect(lx + i * lw, 0, lw - 2, H); g.strokeStyle = COL[i]; g.globalAlpha = .5 + .5 * beatPulse; g.lineWidth = 3; g.strokeRect(lx + i * lw + 6, hy - 28, lw - 14, 56); g.globalAlpha = 1; g.fillStyle = COL[i]; g.globalAlpha = .45; g.font = '700 28px Arial'; g.textAlign = 'center'; g.fillText(GL[i], lx + i * lw + lw / 2 - 1, hy + 10); g.globalAlpha = 1; }
      for (const n of notes) {
        if (n.hit) continue; const y = noteY(n); if (!n.miss && y > hy + 28 + 40) { if (auto) { /* 自动演示 */ } n.miss = true; hits.MISS++; combo = 0; gauge = Math.max(0, gauge - 4); judge = 'MISS'; judgeAt = t; }
        if (auto && !n.hit && !n.miss && t >= n.t - 8) { n.hit = true; hits.PERFECT++; combo++; maxCombo = Math.max(maxCombo, combo); score += 300; judge = 'PERFECT'; judgeAt = t; flash[n.lane] = 1; gauge = Math.min(100, gauge + 1); continue; }
        if (y < -40 || y > H + 40) continue; const x = lx + n.lane * lw + lw / 2; g.save(); g.translate(x, y); g.rotate([Math.PI, Math.PI / 2 * 3 - Math.PI, 0, 0][0] * 0); const rot = [Math.PI, Math.PI / 2, -Math.PI / 2, 0][n.lane]; g.rotate(rot); g.fillStyle = n.miss ? '#666' : COL[n.lane]; g.strokeStyle = '#fff'; g.lineWidth = 3; g.beginPath(); g.moveTo(24, 0); g.lineTo(-4, -24); g.lineTo(-4, -10); g.lineTo(-24, -10); g.lineTo(-24, 10); g.lineTo(-4, 10); g.lineTo(-4, 24); g.closePath(); g.fill(); g.stroke(); g.restore(); }
      if (judge && t - judgeAt < 500) { g.save(); g.globalAlpha = 1 - (t - judgeAt) / 500; g.font = `700 ${34 + (500 - (t - judgeAt)) / 20}px Arial`; g.textAlign = 'center'; g.fillStyle = { PERFECT: '#ffe34a', COOL: '#6ae6ff', GOOD: '#9dff6a', BAD: '#c0a0ff', MISS: '#ff6a6a' }[judge]; g.strokeStyle = '#000'; g.lineWidth = 4; g.strokeText(judge, W / 2, hy - 90); g.fillText(judge, W / 2, hy - 90); g.restore(); }
      if (combo > 1) { g.font = '700 26px Arial'; g.textAlign = 'center'; g.fillStyle = '#fff'; g.strokeStyle = '#d0a'; g.lineWidth = 4; g.strokeText(combo + ' COMBO', W / 2, hy - 130); g.fillText(combo + ' COMBO', W / 2, hy - 130); }
      g.fillStyle = 'rgba(0,0,0,.6)'; g.fillRect(W - 32, 60, 18, H - 200); g.fillStyle = gauge > 70 ? '#ffe34a' : '#ff4fa0'; const gh = (H - 204) * gauge / 100; g.fillRect(W - 30, 60 + (H - 204) - gh + 2, 14, gh);
      const done = notes.length && notes.every(n => n.hit || n.miss) && t > notes[notes.length - 1].t + 800; if (done) { reset(); }
      ui.innerHTML = `SCORE <span style="color:#ffe34a">${String(score).padStart(7, '0')}</span> &nbsp;·&nbsp; MAX COMBO ${maxCombo}`;
      g.font = '700 13px Arial'; g.textAlign = 'left'; g.fillStyle = '#fff'; g.fillText((auto ? '自动演示中 · 按方向键 ← ↓ ↑ → 开始游戏' : '手动模式 · 空格键切换自动演示 · R 重新开始') + `   BPM ${bpm}`, 12, H - 12);
      g.textAlign = 'right'; g.fillText('PERFECT ' + hits.PERFECT + '  COOL ' + hits.COOL + '  GOOD ' + hits.GOOD + '  BAD ' + hits.BAD + '  MISS ' + hits.MISS, W - 12, H - 12);
    };
    raf = requestAnimationFrame(loop);
    win.o.onclose = () => { run = false; cancelAnimationFrame(raf); document.removeEventListener('keydown', kd); ro.disconnect(); };
    win.onstate = () => { if (win.state === 'min') { run = false; cancelAnimationFrame(raf); } else if (!run && !win.closed) { run = true; t0 = performance.now() - 2400; reset(); raf = requestAnimationFrame(loop); } };
    root.addEventListener('pointerdown', () => root.focus());
    return root;
  } }) });
})();
