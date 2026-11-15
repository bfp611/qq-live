// XP 加强包（?desk=xp）：配置 / 系统音效 / 托盘气泡通知 / QQ 提示音与托盘闪烁 / 随机事件（新硬件、蓝屏）
// 开机画面、欢迎、注销、关机、蓝屏的画面在 xp-screens.js。所有开关都在 config.ini 的 [xp]（/config.json 里的 xp），URL 里 ?xp_键=值 可临时覆盖（测试用）。
// 音效是 Windows XP 原版 wav（web/xp/snd/，来源见 CREDITS.md）；QQ 提示音是 QQ2006 原版 mp3（web/sound/）。
(function () {
  if (!window.WM || !WM.ready) return;
  const { root, h } = WM, Q = new URLSearchParams(location.search), $ = id => document.getElementById(id);
  const D = { enabled: true, boot: true, boot_secs: 4.5, welcome: true, welcome_secs: 3.5, boot_cooldown: 900, boot_edition: 'pro', user: '',
    shutdown_screens: true, shutdown_restart: true, restart_after: 5, sounds: true, volume: 0.5, mute: false, sound_events: '*', sound_deny: '',
    bsod: true, bsod_per_hour: 0.3, bsod_secs: 6, setup_secs: 12, balloons: true, balloon_events: 'hardware,qq,music,tip', balloon_secs: 7, balloon_hardware_every: 1500,
    qq_sounds: true, qq_online_every: 300, qq_flash: true, qq_system_sound: true, apps: true };
  const XP = window.XP = { cfg: Object.assign({}, D), played: [], balloons: [], screen: null, flashing: false };
  const typed = (k, v) => { const d = D[k]; if (typeof d === 'boolean') return /^(1|true|yes|on)$/i.test(String(v)); if (typeof d === 'number') { const n = parseFloat(v); return isNaN(n) ? d : n; } return String(v == null ? '' : v).trim(); };
  const list = s => String(s || '').split(/[,，\s]+/).filter(Boolean);
  XP.apply = c => { for (const k in D) { if (c && c[k] !== undefined) XP.cfg[k] = typed(k, c[k]); const u = Q.get('xp_' + k); if (u !== null) XP.cfg[k] = typed(k, u); } };
  XP.apply({});
  XP.busy = () => !!XP.screen;
  XP.ready = fetch('config.json').then(r => r.json()).then(c => { XP.userName = c.host_name || ''; XP.apply(c.xp || {}); }).catch(() => {}).then(() => { document.dispatchEvent(new CustomEvent('xpready')); return XP.cfg; });
  const on = k => XP.cfg.enabled && XP.cfg[k] !== false;

  // ======================= 系统音效 =======================
  const SND = { startup: 'startup.wav', logon: 'logon.wav', logoff: 'logoff.wav', shutdown: 'shutdown.wav', ding: 'ding.wav', error: 'error.wav', critical: 'critical.wav', exclamation: 'exclamation.wav',
    notify: 'notify.wav', recycle: 'recycle.wav', balloon: 'balloon.wav', menu: 'menu.wav', minimize: 'minimize.wav', restore: 'restore.wav', start: 'start.wav', hw_insert: 'hw_insert.wav',
    hw_remove: 'hw_remove.wav', hw_fail: 'hw_fail.wav', default: 'default.wav', infobar: 'infobar.wav', popup_blocked: 'popup_blocked.wav', print: 'print.wav' };
  const QQS = { qq_msg: 'sound/msg.mp3', qq_online: 'sound/Global.mp3', qq_system: 'sound/system.mp3', qq_alert: 'sound/InputAlert.mp3' };
  XP.SOUNDS = Object.keys(SND).concat(Object.keys(QQS));
  const GROUPS = ['open', 'close', 'minimize', 'restore', 'dialog', 'error', 'notify', 'balloon', 'recycle', 'hardware', 'startup', 'shutdown', 'qq', 'game'];
  XP.GROUPS = GROUPS;
  XP.allowed = g => { const al = list(XP.cfg.sound_events), dn = list(XP.cfg.sound_deny); return !dn.includes(g) && (!al.length || al.includes('*') || al.includes(g)); };
  XP.volume = () => (XP.cfg.mute || WM.mute || !XP.cfg.sounds || !XP.cfg.enabled) ? 0 : Math.max(0, Math.min(1, XP.cfg.volume * (WM.vol == null ? 1 : WM.vol / 100)));
  // 播放：name 见 SND / QQS，group 决定能不能响（sound_events / sound_deny）。force=true 忽略分组（控制面板里“测试”按钮）
  XP.snd = function (name, group, force) {
    const src = SND[name] ? 'xp/snd/' + SND[name] : QQS[name]; if (!src) return null;
    const vol = XP.volume(), rec = { name, group: group || '', vol: +vol.toFixed(2), at: Date.now(), ok: null, skipped: '' };
    if (!force && group && !XP.allowed(group)) rec.skipped = 'group';
    else if (!vol) rec.skipped = XP.cfg.mute || WM.mute ? 'mute' : 'volume';
    XP.played.push(rec); if (XP.played.length > 80) XP.played.shift();
    if (rec.skipped) return rec;
    try { const a = new Audio(src); a.volume = vol; XP.last = a; a.play().then(() => { rec.ok = true; }).catch(() => { rec.ok = false; }); a.addEventListener('ended', () => { rec.ended = true; }); } catch (e) { rec.ok = false; }
    return rec;
  };
  XP.stopSnd = () => { try { XP.last && XP.last.pause(); } catch (e) {} };
  // 窗口事件 → 音效（wm.js 的 WM.fire）
  const quiet = () => XP.screen && XP.screen !== 'bsod' && XP.screen !== 'qq';   // 开机 / 关机画面期间窗口事件不出声
  document.addEventListener('wmevent', e => {
    const { type, w } = e.detail || {}; if (!w || quiet()) return;
    const sys = ['qqchat', 'ttplayer', 'ttplaylist'].includes(w.id);
    if (type === 'open') { if (w.dialogOnly) return; if (!sys) XP.snd('restore', 'open'); }
    else if (type === 'close') { if (w.dialogOnly || sys) return; XP.snd('minimize', 'close'); }
    else if (type === 'min') XP.snd('minimize', 'minimize');
    else if (type === 'restore' || type === 'max') XP.snd('restore', 'restore');
  });
  // 对话框：错误 → error.wav；提示 / 询问 → ding.wav
  const alert0 = WM.alert; WM.alert = function (title, text, o) { o = o || {}; const k = o.kind || 'error'; if (!quiet()) { if (k === 'error') XP.snd('error', 'error'); else if (k === 'warn') XP.snd('exclamation', 'dialog'); else XP.snd('ding', 'dialog'); } return alert0.apply(this, arguments); };
  if (WM.emptyTrash) { const e0 = WM.emptyTrash; WM.emptyTrash = function () { XP.snd('recycle', 'recycle'); return e0.apply(this, arguments); }; }
  document.addEventListener('xpnav', () => XP.snd('start', 'notify'));

  // ======================= 托盘 / 气泡通知 =======================
  const tray = $('tray'), taskbar = $('taskbar');
  let trayQQ = null;
  if (tray) {
    trayQQ = h('img', { id: 'tray-qq', src: 'xp/ui/qq16.png', title: 'QQ', alt: '' });
    tray.insertBefore(trayQQ, tray.firstChild);
    trayQQ.addEventListener('click', () => { XP.flash(false); const q = WM.byId.qqchat; if (q) { if (q.closed) q.reopen(); else q.focus(); } });
  }
  XP.flash = on => {
    XP.flashing = !!on; clearInterval(XP._fi); if (!trayQQ) return;
    trayQQ.style.visibility = 'visible'; trayQQ.classList.toggle('flash', !!on);
    if (on) XP._fi = setInterval(() => { trayQQ.style.visibility = trayQQ.style.visibility === 'hidden' ? 'visible' : 'hidden'; }, 420);
  };
  let bq = [], bcur = null;
  function balloonNext() {
    if (bcur || !bq.length) return;
    const b = bq.shift(), el = h('div', { class: 'xp-balloon' }, [
      h('div', { class: 'bh' }, [b.icon ? h('img', { src: b.icon, alt: '' }) : h('span', { class: 'bi ' + (b.kind || 'info') }), h('b', { text: b.title || '' }), h('i', { class: 'bx', text: '×' })]),
      h('div', { class: 'bt', text: b.text || '' }), h('div', { class: 'tail' })]);
    root.insertBefore(el, taskbar); bcur = { el, b }; XP.balloons.push({ title: b.title, text: b.text, at: Date.now(), ev: b.ev || '' });
    if (XP.balloons.length > 40) XP.balloons.shift();
    requestAnimationFrame(() => el.classList.add('on'));
    if (b.sound !== false) XP.snd(b.sound || 'balloon', 'balloon');
    const done = () => { if (!bcur || bcur.el !== el) return; clearTimeout(bcur.t); el.classList.remove('on'); setTimeout(() => { el.remove(); }, 250); bcur = null; setTimeout(balloonNext, 400); };
    bcur.t = setTimeout(done, Math.max(2, XP.cfg.balloon_secs) * 1000);
    el.querySelector('.bx').addEventListener('click', e => { e.stopPropagation(); done(); });
    el.addEventListener('click', () => { done(); b.onclick && b.onclick(); });
    bcur.done = done;
  }
  // XP.balloon({title, text, icon, kind: 'info'|'warn'|'error', ev: 'hardware|qq|music|tip', onclick, sound})
  XP.balloon = function (b) {
    if (!XP.cfg.enabled || !XP.cfg.balloons) return false;
    if (b.ev && !list(XP.cfg.balloon_events).includes(b.ev) && !list(XP.cfg.balloon_events).includes('*')) return false;
    if (XP.screen && XP.screen !== 'qq') return false;
    if (bq.length > 4) bq.shift(); bq.push(b); balloonNext(); return true;
  };
  XP.clearBalloons = () => { bq = []; if (bcur) bcur.done(); };

  // ======================= QQ：提示音、托盘闪烁、好友上线 =======================
  const qqWin = () => WM.byId.qqchat, chatHidden = () => { const q = qqWin(); return !q || q.closed || q.state === 'min' || (window.AG && AG.chatVis && AG.chatVis() < 0.5); };
  let FRc = null; const frs = () => FRc || (FRc = (() => { try { const d = document.createElement('div'); d.innerHTML = (window.QQTPL && QQTPL.panel) || ''; return [...d.querySelectorAll('.qq-friend-item')].map(e => ({ name: (e.querySelector('.qq-friend-name') || {}).textContent || '', avatar: (e.querySelector('.qq-friend-avatar') || {}).getAttribute && e.querySelector('.qq-friend-avatar').getAttribute('src') })).filter(f => f.name); } catch (e) { return []; } })());
  Object.defineProperty(XP, 'friends', { get: frs });
  XP.qqToast = function (title, text, avatar, snd) {
    if (!XP.cfg.enabled) return;
    const el = h('div', { class: 'qq-toast' }, [h('div', { class: 'qh' }, [h('img', { src: 'xp/ui/qq16.png', alt: '' }), h('span', { text: 'QQ' }), h('i', { class: 'qx', text: '×' })]),
      h('div', { class: 'qb' }, [avatar ? h('img', { class: 'av', src: avatar, alt: '' }) : h('span'), h('div', {}, [h('b', { text: title }), h('div', { text })])])]);
    root.insertBefore(el, taskbar); requestAnimationFrame(() => el.classList.add('on'));
    const kill = () => { el.classList.remove('on'); setTimeout(() => el.remove(), 300); };
    el.querySelector('.qx').addEventListener('click', kill); setTimeout(kill, 5200);
    return el;
  };
  XP.qqOnline = function (name) {
    const FR = frs(); const f = name ? FR.find(x => x.name === name) || { name } : FR[Math.floor(Math.random() * FR.length)]; if (!f) return false;
    if (XP.cfg.qq_sounds) XP.snd('qq_online', 'qq');
    XP.qqToast(f.name, '上线了', f.avatar); return f.name;
  };
  XP.qqMsg = function (name, text, win) {   // 私聊新消息
    const w = win || WM.byId['qq-chat-' + name], hidden = !w || w.closed || w.state === 'min' || WM.active !== w;
    if (XP.cfg.qq_sounds) XP.snd('qq_msg', 'qq');
    if (hidden && XP.cfg.qq_flash) XP.flash(true);
    if (hidden) XP.balloon({ title: 'QQ 新消息', text: name + '：' + String(text || '').slice(0, 24), icon: 'xp/ui/qq16.png', ev: 'qq', sound: false, onclick: () => { XP.flash(false); const c = WM.byId['qq-chat-' + name]; if (c) c.focus(); } });
  };
  document.addEventListener('qqmsg', e => { const d = e.detail || {}; XP.qqMsg(d.friend, d.text, d.win); });
  document.addEventListener('wmevent', e => { const { type, w } = e.detail || {}; if (XP.flashing && w && (w.id === 'qqchat' || /^qq-chat-/.test(w.id)) && (type === 'restore' || type === 'open')) XP.flash(false); });
  // 群聊列表里的新消息：系统消息（送礼 / 关注 / 系统提示）→ 敲门声；群聊窗口被最小化 / 挡住时有新弹幕 → 托盘闪烁 + 气泡
  const lst = $('list'); let lastBalloonAt = 0;
  if (lst) new MutationObserver(ms => {
    for (const m of ms) for (const n of m.addedNodes) {
      if (!(n instanceof HTMLElement) || n.tagName !== 'LI' || XP.screen) continue;
      const c = n.className || '';
      if (/\b(gift|follow|notice)\b/.test(c) && XP.cfg.qq_system_sound && XP.cfg.qq_sounds) XP.snd('qq_system', 'qq');
      if (/\bchat\b|\bgift\b|\bfollow\b/.test(c) && chatHidden()) {
        if (XP.cfg.qq_flash) XP.flash(true);
        if (Date.now() - lastBalloonAt > 15000) { lastBalloonAt = Date.now(); const t = (n.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 26); XP.balloon({ title: 'QQ 群：新消息', text: t, icon: 'xp/ui/qq16.png', ev: 'qq', sound: false, onclick: () => { XP.flash(false); const q = qqWin(); if (q) { q.closed ? q.reopen() : q.focus(); } } }); }
      }
    }
  }).observe(lst, { childList: true });

  // 网易云换歌 → “网易云正在播放”
  let lastSong = '';
  document.addEventListener('deskmusic', () => {
    const t = ($('tt-infot') || {}).textContent || ''; if (!t || t === lastSong) return; const first = !lastSong; lastSong = t;
    if (first && Date.now() - XP.t0 < 12000) return;   // 刚打开页面时不弹
    XP.balloon({ title: '网易云音乐 正在播放', text: t, icon: 'xp/ui/ttp16.png', ev: 'music', sound: 'notify' });
  });
  XP.t0 = Date.now();

  // ======================= 随机事件：新硬件 / 小提示 / 好友上线 / 蓝屏 =======================
  XP.hardware = function () {
    const dev = ['USB 大容量存储设备', 'USB 鼠标', 'Logitech USB 摄像头', '索尼 MP3 播放器', 'Realtek 声卡'][Math.floor(Math.random() * 5)];
    XP.snd('hw_insert', 'hardware');
    XP.balloon({ title: '发现新硬件', text: dev, ev: 'hardware', kind: 'info', sound: false });
    setTimeout(() => { XP.balloon({ title: '新硬件已安装并可以使用了', text: dev, ev: 'hardware', kind: 'info', sound: 'balloon' }); }, 5200);
  };
  XP.tip = function () {
    XP.balloon({ title: '桌面上有未使用的图标', text: '桌面上有 3 个未使用的图标。单击此处，让“桌面清理向导”帮您清理。', ev: 'tip', kind: 'info', onclick: () => WM.open('cleanup') });
  };
  const rnd = (avg) => avg * (0.5 + Math.random());
  function schedule(fn, key, test) { const avg = () => XP.cfg[key]; const go = () => { const a = avg(); if (!(a > 0)) return setTimeout(go, 30000); setTimeout(() => { if (!XP.screen && (!test || test())) fn(); go(); }, rnd(a) * 1000); }; go(); }
  const quietNow = () => !(window.AG && (AG.running || (AG.queue && AG.queue.length)));
  XP.ready.then(() => {
    if (!XP.cfg.enabled) return;
    schedule(() => XP.cfg.balloons && XP.hardware(), 'balloon_hardware_every', quietNow);
    schedule(() => XP.cfg.balloons && XP.tip(), 'balloon_hardware_every', quietNow);
    schedule(() => { const p = WM.byId['qq-panel']; if (p && !p.closed && XP.cfg.qq_sounds) XP.qqOnline(); }, 'qq_online_every', quietNow);
    setInterval(() => { if (XP.cfg.bsod && XP.cfg.bsod_per_hour > 0 && !XP.screen && quietNow() && Math.random() < XP.cfg.bsod_per_hour / 60) XP.bsod && XP.bsod('random'); }, 60000);
  });
})();
