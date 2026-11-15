// ?desk=xp：Windows XP 桌面（真实 Bliss 壁纸 + 原版 XP 图标 + Luna 任务栏）。QQ 窗口(#win)被放进这个桌面里。
// 桌面按 1280×720 设计（XP 的图标/任务栏本来就是为这种分辨率做的），整体等比放大到页面大小（1920×1080 = 1.5 倍）。
// 可用 ?deskw= ?deskh= 改设计尺寸，?wx= ?wy= ?ww= ?wh= 改 QQ 窗口位置大小（设计像素）
// 另外：网易云音乐的「正在播放」会被伪装成桌面上的 千千静听 播放器 + 底部 KTV 式桌面歌词（数据来自服务端 backend/music.py，
// ?music=0 关闭；?musicdemo=1 用假歌曲演示；?lyricoffset=秒 微调歌词快慢；?ttx= ?tty= 改千千静听位置）
(function () {
  const Q = new URLSearchParams(location.search);
  const mode = Q.get('desk');
  if (!mode || mode === '0' || mode === 'off' || mode === 'false') { window.DESK = { on: false }; return; }
  const num = (k, d) => { const v = parseFloat(Q.get(k)); return isNaN(v) ? d : v; };
  const DW = num('deskw', 1280), DH = num('deskh', 720), TB = 30;
  const rect = { x: num('wx', 478), y: num('wy', 18), w: num('ww', 700), h: num('wh', 512) };
  window.DESK = { on: true, rect };
  document.body.classList.add('desk');

  const ICONS = [
    ['我的电脑', 'mycomputer'], ['我的文档', 'mydocs'], ['回收站', 'recycle'], ['Internet Explorer', 'ie'],
    ['千千静听', 'ttplayer'], ['暴风影音', 'baofeng'], ['酷狗音乐', 'kugou'], ['迅雷', 'xunlei'],
    ['腾讯QQ', 'qq'], ['QQ游戏', 'qqgame'], ['Counter-Strike 1.6', 'cs'], ['侠盗猎车手 罪恶都市', 'vc'],
    ['魔兽争霸III', 'war3'], ['红色警戒2', 'ra2'], ['热血传奇', 'mir2'], ['劲舞团', 'audition'],
  ];
  const root = document.createElement('div'); root.id = 'deskroot';
  root.style.width = DW + 'px'; root.style.height = DH + 'px';
  root.innerHTML = `<div id="icons">${ICONS.map(([t, f]) => `<div class="dicon"><img src="xp/icons/${f}.png" alt=""><span>${t}</span></div>`).join('')}</div>
    <div id="taskbar"><div class="left"><div id="start"><img src="xp/ui/start.png" alt="开始"></div>
      <div class="tbtn act"><img src="xp/ui/qq16.png" alt=""><span id="tb-qqt">怀旧QQ群</span></div>
      <div class="tbtn" id="tb-tt" style="display:none"><img src="xp/ui/ttp16.png" alt=""><span id="tb-ttt">千千静听</span></div>
      <div class="tbtn"><img src="xp/ui/bf16.png" alt=""><span>暴风影音</span></div></div>
      <div id="tray"><img src="xp/ui/690.png" alt=""><img src="xp/ui/394.png" alt=""><img src="xp/ui/229.png" alt=""><span id="clk">0:00</span></div></div>`;
  root.insertAdjacentHTML('beforeend', `<div id="tt" class="off" style="left:${num('ttx', 178)}px;top:${num('tty', 22)}px">
      <img class="skin" src="xp/tt/player_skin.png" alt="">
      <canvas id="tt-vis" width="136" height="48"></canvas>
      <div id="tt-led"></div><div id="tt-stereo">立体声</div><div id="tt-status">播放</div>
      <img id="tt-icon" src="xp/ui/ttp16.png" alt=""><div id="tt-info"><span id="tt-infot"></span></div>
      <div id="tt-thumb"></div><div id="tt-vfill"></div><div id="tt-vthumb"></div>
      <i class="b" id="tt-play"></i>
      <i class="b" id="tt-stop"></i><i class="b" id="tt-prev"></i>
      <i class="b" id="tt-next"></i><i class="b" id="tt-mute"></i>
      <i class="b" id="tt-open"></i><i class="b" id="tt-lyric"></i>
      <i class="b" id="tt-eq"></i><i class="b" id="tt-pl"></i>
      <i class="b" id="tt-min"></i><i class="b" id="tt-exit"></i>
    </div>
    <div id="pl" class="off" style="left:${num('ttx', 178)}px;top:${num('tty', 22) + 165}px">
      <img class="skin" src="xp/tt/playlist_win.png" alt=""><img id="pl-title" src="xp/tt/playlist_title.png" alt=""><img id="pl-tool" src="xp/tt/playlist_toolbar.png" alt="">
      <div id="pl-rows"></div></div>
    <div id="ktv" class="off"><div class="kl a"><div class="kw"><span class="k0"></span><span class="k1"></span></div></div><div class="kl b"><div class="kw"><span class="k0"></span><span class="k1"></span></div></div></div>`);
  document.body.appendChild(root);
  root.insertBefore(document.getElementById('win'), document.getElementById('taskbar'));

  function fit() {
    const k = Math.min(innerWidth / DW, innerHeight / DH);
    root.style.transform = `translate(${(innerWidth - DW * k) / 2}px, ${(innerHeight - DH * k) / 2}px) scale(${k})`;
  }
  fit(); addEventListener('resize', fit);
  const clk = document.getElementById('clk');
  function tick() { const d = new Date(), p = n => String(n).padStart(2, '0'), h = d.getHours(); clk.textContent = (h < 12 ? '上午' : '下午') + (h % 12 || 12) + ':' + p(d.getMinutes()); }
  tick(); setInterval(tick, 10000);
  new MutationObserver(() => { const t = document.getElementById('title'), q = document.getElementById('tb-qqt'); if (t && q) q.textContent = t.textContent.replace(/ ?\(\d+人\)$/, ''); })
    .observe(document.getElementById('title'), { childList: true, characterData: true, subtree: true });

  // ================= 网易云音乐 → 千千静听 + KTV 桌面歌词 =================
  if (Q.get('music') !== '0') (function music() {
    const $ = id => document.getElementById(id);
    const tt = $('tt'), ktv = $('ktv'), tbtt = $('tb-tt'), tbttt = $('tb-ttt'), infot = $('tt-infot'), led = $('tt-led');
    const play = $('tt-play'), thumb = $('tt-thumb'), vis = $('tt-vis'), vctx = vis.getContext('2d');
    const loff = num('lyricoffset', 0);
    let slot = [-9, -9];           // 上、下两个位置当前显示的是第几行（-9 = 未设置）
    const S = { on: false, playing: false, key: '', title: '', artist: '', duration: 0, base: 0, at: 0, offset: 0, lines: [], found: false, loading: false, pausedAt: 0 };
    // LED 数字：number.bmp 每个字符 10×13（0-9 ，: ，-）
    led.innerHTML = '<b></b><b></b><b></b><b></b><b></b>';
    const digs = led.children;
    function setLed(sec) {
      sec = Math.max(0, Math.floor(sec)); const m = Math.floor(sec / 60), r = sec % 60;
      const t = String(Math.min(m, 99)).padStart(2, '0') + ':' + String(r).padStart(2, '0');
      for (let i = 0; i < 5; i++) digs[i].style.backgroundPosition = `-${(t[i] === ':' ? 10 : +t[i]) * 10}px 0`;
    }
    const nowPos = () => {
      if (!S.on) return 0;
      let p = S.base + (S.playing ? (performance.now() - S.at) / 1000 : 0);
      return Math.max(0, Math.min(p, S.duration || p));
    };

    // ---- 接收数据 ----
    function onMusic(m) {
      if (!m.on) { S.on = false; render(); return; }
      const predicted = nowPos(), was = S.on && S.key === m.key && S.playing;
      S.on = true; S.offset = (m.offset || 0) + loff;
      if (S.key !== m.key) { S.key = m.key; S.lines = []; S.found = false; S.loading = true; slot = [-9, -9]; }
      if (S.playing && !m.playing) S.pausedAt = performance.now();
      if (!S.playing && m.playing) S.pausedAt = 0;
      if (!m.playing && !S.pausedAt) S.pausedAt = performance.now();
      S.playing = m.playing; S.title = m.title; S.artist = m.artist; S.duration = m.duration;
      // 位置平滑：小误差只修正一部分，避免歌词条抖动；大误差（拖动进度/换歌）直接跳
      S.base = was && Math.abs(m.pos - predicted) < 0.5 ? predicted + (m.pos - predicted) * 0.3 : m.pos;
      S.at = performance.now();
      const info = (m.artist ? m.artist + ' - ' : '') + m.title;
      if (infot.textContent !== info) { infot.textContent = info; fitInfo(); }
      tbttt.textContent = '千千静听 - ' + info; document.dispatchEvent(new CustomEvent('deskmusic'));
      render();
    }
    function onLyric(m) {
      if (m.key !== S.key) return;
      S.lines = m.lines || []; S.found = !!m.found; S.loading = !!m.loading; slot = [-9, -9];
    }
    // ---- 点歌队列（播放列表窗口：第 1 行 = 正在播放的点歌，后面是排队的）----
    const pl = $('pl'), rows = $('pl-rows');
    const esc = t => String(t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
    function onJuke(m) {
      const list = (m.current ? [Object.assign({ cur: true }, m.current)] : []).concat(m.queue || []);
      pl.classList.toggle('off', !m.on || !list.length);
      let h = list.slice(0, 6).map((s, i) => `<div class="r${s.cur ? ' cur' : ''}"><b>${i + 1}.</b><span class="n">${esc(s.title)}${s.artist ? ' - ' + esc(s.artist) : ''}</span><i>${esc(s.user || '')}</i></div>`).join('');
      if (list.length < 6) h += '<div class="r hint">发弹幕「点歌 歌名」就能点歌</div>';
      rows.innerHTML = h;
    }
    function fitInfo() {
      const box = infot.parentElement, over = infot.scrollWidth - box.clientWidth;
      infot.classList.toggle('scroll', over > 2);
      infot.style.setProperty('--over', over + 'px');
      infot.style.setProperty('--dur', Math.max(6, over / 18 + 4) + 's');
    }
    function render() {
      const forced = !!window.DESK.ttForce, tw = window.DESK.ttwin, show = S.on || forced;
      tt.classList.toggle('off', !show);
      if (tw) { tw.tbHidden = !show; if (tw.tb) tw.tb.style.display = (!show || tw.closed) ? 'none' : ''; }
      play.classList.toggle('pause', S.on && S.playing);
      $('tt-status').textContent = S.on ? (S.playing ? '播放' : '暂停') : '停止';
      if (!S.on && forced && infot.textContent === '') { infot.textContent = '千千静听 5.x'; fitInfo(); }
      const lyr = S.on && (S.playing || performance.now() - S.pausedAt < 20000);
      ktv.classList.toggle('off', !lyr);
    }
    window.DESK.musicRender = render; window.DESK.music = { S, nowPos, loff };

    // ---- 连接服务端 ----
    let ws, demo = Q.get('musicdemo') === '1';
    function connect() {
      try { ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws'); } catch (e) { return setTimeout(connect, 2000); }
      ws.onopen = () => ws.send(JSON.stringify({ music: 1 }));
      ws.onmessage = e => { try { const m = JSON.parse(e.data); if (m.t === 'music') onMusic(m); else if (m.t === 'lyric') onLyric(m); else if (m.t === 'jukebox') onJuke(m); } catch (err) {} };
      ws.onclose = () => { setTimeout(connect, 1000); };
      ws.onerror = () => { try { ws.close(); } catch (e) {} };
    }
    if (demo) {
      // 演示：假歌曲 + 自编的演示歌词（不涉及任何真实歌词）
      const L = ['夕阳染红了教室的窗台', '粉笔灰在光里慢慢飘落', '那年我们把心事写在课桌', '下课铃一响就忘了烦恼', '', '电脑房里传来熟悉的歌', '千千静听放着我们的快乐', '挂着QQ等你上线说话', '头像一闪就笑得停不下'];
      const lines = []; let t = 12; L.forEach((tx, i) => { if (tx) { lines.push([t, tx, t + 4.4]); } t += tx ? 5 : 6; });
      const t0 = performance.now() - num('musicpos', 28) * 1000;
      const send = () => { const pos = (performance.now() - t0) / 1000 % 200;
        onMusic({ on: true, key: 'demo', title: '怀旧金曲（演示）', artist: 'GG-Bond', duration: 200, pos, playing: Q.get('musicpaused') !== '1', offset: 0 }); };
      send(); onLyric({ key: 'demo', lines, found: true }); setInterval(send, 1000);
      if (Q.get('jukedemo') === '1') onJuke({ on: true, current: { title: '拆东墙', artist: '许嵩', user: '☆幸运草' },
        queue: [{ title: '玫瑰花的葬礼', artist: '许嵩', user: '大头鬼' }, { title: '七秒钟的记忆', artist: '徐良', user: '随风飘逝' }, { title: '千里之外', artist: '周杰伦/费玉清', user: '花样年华' }] });
    } else connect();

    // ---- 每帧：时间/进度/频谱/歌词 ----
    const GAP = 5;
    const el = [ktv.children[0], ktv.children[1]];
    const sp = el.map(e => [e.firstChild.children[0], e.firstChild.children[1]]);
    function lineProg(i, pos) {
      const L = S.lines[i], chars = L[1].length;
      const dur = Math.max(0.6, Math.min(L[2] - L[0], chars * 0.42 + 0.6));
      return Math.max(0, Math.min(1, (pos - L[0]) / dur));
    }
    function setSlot(k, i) {
      if (slot[k] === i) return; slot[k] = i;
      const t = i >= 0 && i < S.lines.length ? S.lines[i][1] : '';
      sp[k][0].textContent = t; sp[k][1].textContent = t; sp[k][1].style.width = '0';
      el[k].style.transform = ''; el[k].dataset.t = t;
      el[k].style.visibility = t ? 'visible' : 'hidden';
      // 太长就整体缩小，保证不出屏幕
      const maxW = 1040, w = sp[k][0].offsetWidth; if (w > maxW) el[k].style.transform = `scale(${maxW / w})`;
      el[k].dataset.w = Math.min(w, maxW);
    }
    let lastIdx = 0, lastFrame = 0;
    const bars = new Array(34).fill(0), peaks = new Array(34).fill(0), grad = vctx.createLinearGradient(0, 0, 0, 48);
    grad.addColorStop(0, '#ff0080'); grad.addColorStop(.5, '#ffff00'); grad.addColorStop(1, '#0080ff');
    function frame(ts) {
      requestAnimationFrame(frame);
      if (!S.on) return;
      if (ts - lastFrame < 33) return; lastFrame = ts;
      const pos = nowPos(), lp = pos + S.offset;
      setLed(pos);
      const p = S.duration ? pos / S.duration : 0;
      thumb.style.left = (18 + p * (230 - 23)) + 'px';
      // 频谱（读不到系统音频，用节拍感随机数模拟；暂停时回落）
      vctx.clearRect(0, 0, 136, 48);
      for (let i = 0; i < bars.length; i++) {
        const tgt = S.playing ? Math.max(2, (Math.random() * .55 + .3 * Math.sin(ts / 260 + i * .5) ** 2 + .15 * Math.random()) * 48 * (1 - i / bars.length * .55)) : 0;
        bars[i] += (tgt - bars[i]) * (tgt > bars[i] ? .55 : .2);
        peaks[i] = Math.max(bars[i], peaks[i] - .5);
        vctx.fillStyle = grad; vctx.fillRect(i * 4, 48 - bars[i], 3, bars[i]);
        vctx.fillStyle = '#fff'; vctx.fillRect(i * 4, 47 - peaks[i], 3, 1);
      }
      // KTV 歌词
      const n = S.lines.length;
      if (!n) {
        // 没有歌词：第一行放歌名，第二行放歌手/状态
        if (slot[0] !== 'x' + S.key + S.loading) {
          slot = ['x' + S.key + S.loading, 'x'];
          [S.title, S.loading ? '歌词加载中…' : (S.artist ? S.artist + ' · 暂无歌词' : '暂无歌词')].forEach((t, k) => {
            sp[k][0].textContent = t; sp[k][1].textContent = t; sp[k][1].style.width = '100%'; el[k].style.visibility = 'visible'; el[k].style.transform = '';
            const w = sp[k][0].offsetWidth; if (w > 1040) el[k].style.transform = `scale(${1040 / w})`; el[k].dataset.w = Math.min(w, 1040);
          });
        }
        return;
      }
      let i = lastIdx; if (i >= n || S.lines[i][0] > lp) i = 0;
      while (i + 1 < n && S.lines[i + 1][0] <= lp) i++;
      lastIdx = i;
      const started = S.lines[0][0] <= lp;
      const cur = started ? i : -1;                    // 当前正在唱的行；还没开始唱时 -1
      const a = started ? i : 0, b = a + 1;             // 要显示的两行（偶数位在上、奇数位在下，轮流）
      const top = a % 2 === 0 ? a : b, bot = a % 2 === 0 ? b : a;
      setSlot(0, top); setSlot(1, bot);
      for (let k = 0; k < 2; k++) {
        const idx = slot[k], pr = idx === cur ? lineProg(idx, lp) : (cur >= 0 && idx < cur ? 1 : 0);
        sp[k][1].style.width = (pr * 100) + '%';
      }
    }
    requestAnimationFrame(frame);
  })();
})();
