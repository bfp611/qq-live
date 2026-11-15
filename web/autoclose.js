// 窗口闲置自动关闭（[autoclose]）：猪猪侠 / 冷场活动 / 投票 / 观众指令打开的窗口，没人碰了就自动收掉，
// 别让画图、记事本之类一直盖在桌面和群聊上。
//   - 每个窗口记「最后一次互动」：打开、用户或 agent 的点击 / 按键 / 滚轮（agent 的光标点击也是真派发的事件）、agent 正在对它做动作、视频在放。
//   - 各软件有自己的闲置时间（paint 25 秒 … 见 config.ini [autoclose]）；游戏另有「最长开多久」。
//   - 永远不动：群聊 / 千千静听 / 播放列表 / 桌面歌词 / QQ 面板 / QQ 宠物（keep）；投票 / 小游戏窗口自己会关（skip）；关机 / 蓝屏等系统画面。
//   - agent 正在执行动作、有菜单开着、有模态对话框、正在放系统画面（开机 / 关机 / 蓝屏）时先等着。
//   - 关的时候放 XP 风格的收缩动画（往任务栏缩），不弹「要保存吗」，主播不说话。
(function () {
  'use strict';
  if (!window.WM || !window.DESK || !DESK.on) return;
  const AC = window.AC = { cfg: { enabled: true }, meta: new WeakMap(), closed: 0, log: [] };
  const D = { enabled: 'true', default_secs: '40', check_secs: '2', anim: 'true',
    paint: '25', notepad: '35', calc: '30', cmd: '35', control: '40', explorer: '40', ie: '40', qq: '40', dialog: '30', media: '40',
    minesweeper: '45', solitaire: '45', freecell: '45', videogame: '45', max_game: '150', max_media: '180', max_any: '0',
    keep: 'qqchat,ttplayer,ttplaylist,lyrics,qq-panel,qqx-pet,report,shutdown,logoff,shutter,xpscr', skip: 'vote,skipvote,game' };
  const num = (k, d) => { const v = parseFloat(AC.cfg[k]); return isFinite(v) ? v : d; };
  const on = () => String(AC.cfg.enabled) !== 'false';
  const lst = k => String(AC.cfg[k] || '').split(/[,，\s|]+/).filter(Boolean);
  AC.setCfg = c => { AC.cfg = Object.assign({}, D, AC.cfg, c || {}); if (c && c.enabled != null) AC.cfg.enabled = String(c.enabled); };
  AC.cfg = Object.assign({}, D);

  const ID = { paint: 'paint', calc: 'calc', cmd: 'cmd', control: 'control', sndcpl: 'control', mousecpl: 'control', explorer: 'explorer', ie: 'ie',
    qzone: 'qq', 'qzone-photo': 'qq', qqshow: 'qq', qqpet: 'qq', qqfiles: 'qq', 'qq-login': 'qq', 'qq-logging': 'qq', 'gc-history': 'qq',
    baofeng: 'media', kugou: 'media', xunlei: 'media', qqgame: 'media', minesweeper: 'minesweeper', solitaire: 'solitaire', freecell: 'freecell', rank: 'dialog',
    display: 'dialog', deskitems: 'dialog', cleanup: 'dialog', run: 'dialog', taskmgr: 'dialog', datetime: 'dialog', cardback: 'dialog', solopt: 'dialog' };
  function appOf(w) {
    const t = w.title || '';
    if (/记事本/.test(t)) return 'notepad';
    if (/Internet Explorer/.test(t) && w.id !== 'report') return 'ie';
    if (/我的文档|图片和传真查看器/.test(t)) return 'explorer';
    if (ID[w.id]) return ID[w.id];
    if (/^game-/.test(w.id || '')) return 'videogame';
    if (/^gc-card-|^props-|^prompt-/.test(w.id || '')) return /^gc-card-/.test(w.id) ? 'qq' : 'dialog';
    if (w.app && ID[w.app]) return ID[w.app];
    if (w.dialogOnly) return 'dialog';
    return 'other';
  }
  AC.appOf = appOf;
  const isKeep = w => { const id = w.id || ''; return !!(w.o && w.o.adopted) || lst('keep').includes(id) || lst('skip').includes(id); };
  AC.managed = w => !!w && !w.closed && !isKeep(w);
  AC.secsOf = w => { const a = appOf(w); const v = AC.cfg[a]; return v != null && isFinite(parseFloat(v)) ? parseFloat(v) : num('default_secs', 40); };
  const metaOf = w => { let m = AC.meta.get(w); if (!m) { m = { opened: Date.now(), last: Date.now() }; AC.meta.set(w, m); } return m; };
  AC.touch = w => { if (w) metaOf(w).last = Date.now(); };
  AC.after = (w, tag) => { AC.touch(w); };          // 某个 agent 流程做完了（比如画完画）：从现在开始计闲置时间
  AC.reset = w => { const m = metaOf(w); m.opened = m.last = Date.now(); };

  document.addEventListener('wmevent', e => { const d = e.detail || {}; if (d.w && (d.type === 'open' || d.type === 'restore')) { const m = metaOf(d.w); if (d.type === 'open') m.opened = Date.now(); m.last = Date.now(); } });
  const winOf = el => { const x = el && el.closest && el.closest('.xpw'); if (!x) return null; return WM.wins.find(w => w.el === x) || null; };
  ['pointerdown', 'keydown', 'wheel', 'click', 'dblclick', 'input'].forEach(t => document.addEventListener(t, e => { const w = winOf(e.target); if (w) AC.touch(w); }, true));

  function agentBusyOn(w) {
    const AG = window.AG; if (!AG) return false;
    if (AG.running) {
      if (WM.active === w) return true;
      const j = AG.cur; const acts = (j && j.actions) || [];
      if (acts.some(a => a && (a.target === w.id || a.app === w.id || a.app === appOf(w)))) return true;
    }
    return false;
  }
  function blocked() {
    if (window.XP && XP.screen) return true;                                  // 开机 / 关机 / 蓝屏画面
    if (document.querySelector('.xpm')) return true;                           // 有菜单开着
    if (WM.wins.some(x => !x.closed && x.dialogOnly && x.o && x.o.modal)) return true;   // 模态对话框
    return false;
  }
  function playing(w) {
    const v = w.el.querySelector('video,audio');
    return !!(v && !v.paused && !v.ended && !v.loop);
  }
  function closeNow(w, why) {
    try { WM.closeMenus(); } catch (e) {}
    w._confirmed = true;                                                       // 记事本里的日记不存盘，也不弹「要保存吗」
    w.close();
    if (!w.closed) { try { w.o.onclose = null; w.close(); } catch (e) {} }
    if (w.closed) { AC.closed++; AC.log.push({ id: w.id, app: appOf(w), why, at: Date.now() }); if (AC.log.length > 40) AC.log.shift(); }
  }
  function closeAnim(w, why) {
    if (w._acClosing) return; w._acClosing = true;
    if (String(AC.cfg.anim) === 'false' || !w.el || !w.el.isConnected) return closeNow(w, why);
    try {
      const root = document.getElementById('deskroot'), DH = (root && parseFloat(root.style.height)) || 720;
      w.el.style.setProperty('--acdy', Math.max(40, Math.round(DH - 15 - (w.el.offsetTop + w.el.offsetHeight / 2))) + 'px');
      w.el.classList.add('ac-closing');
    } catch (e) { return closeNow(w, why); }
    setTimeout(() => { if (!w.closed) closeNow(w, why); w._acClosing = false; }, 260);
  }
  AC.closeWin = (w, why) => closeAnim(w, why || 'manual');
  AC.tick = function () {
    if (!on()) return [];
    const now = Date.now(), out = [];
    const bl = blocked();
    for (const w of [...WM.wins]) {
      if (!AC.managed(w) || w.state === 'min' || w._acClosing) continue;
      const m = metaOf(w), a = appOf(w);
      if (agentBusyOn(w) || (a === 'media' && playing(w))) { m.last = now; continue; }
      if (bl) continue;
      const idle = (now - m.last) / 1000, life = (now - m.opened) / 1000;
      const maxk = a === 'videogame' || a === 'minesweeper' || a === 'solitaire' || a === 'freecell' ? num('max_game', 150) : a === 'media' ? num('max_media', 180) : num('max_any', 0);
      const secs = AC.secsOf(w);
      if (maxk > 0 && life >= maxk && !(window.AG && AG.running && WM.active === w)) { out.push(w.id); closeAnim(w, '开了太久（' + Math.round(life) + ' 秒）'); }
      else if (secs > 0 && idle >= secs) { out.push(w.id); closeAnim(w, '闲置 ' + Math.round(idle) + ' 秒'); }
    }
    return out;
  };
  AC.state = () => ({ enabled: on(), closed: AC.closed, wins: WM.wins.filter(w => !w.closed).map(w => ({ id: w.id, app: appOf(w), managed: AC.managed(w), secs: AC.secsOf(w), idle: Math.round((Date.now() - metaOf(w).last) / 1000), age: Math.round((Date.now() - metaOf(w).opened) / 1000) })), log: AC.log.slice(-10) });
  let timer = 0;
  AC.start = () => { clearInterval(timer); timer = setInterval(() => { try { AC.tick(); } catch (e) {} }, Math.max(0.3, num('check_secs', 2)) * 1000); };
  fetch('config.json').then(r => r.json()).then(c => { AC.setCfg(c.autoclose || {}); }).catch(() => {}).then(() => AC.start());
})();
