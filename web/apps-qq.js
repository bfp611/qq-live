// 腾讯QQ（QQ2006 复刻）：登录 → 登录中 → 主面板（好友列表）→ 双击好友打开私聊窗口（可发消息，会自动回复）
// 面板/登录/聊天窗口的标记和样式来自 mengkunsoft/QQ2006（素材取自原版 QQ2006 安装包）
(function () {
  if (!window.WM || !WM.ready || !window.QQTPL) return;
  const { h, esc, ICO, root, DW, DH, TB } = WM;
  const qs = (el, s) => el.querySelector(s), tpl = html => { const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstElementChild; };
  const taskbar = () => document.getElementById('taskbar');
  const rectOf = el => () => ({ x: parseFloat(el.style.left) || 0, y: parseFloat(el.style.top) || 0, w: el.offsetWidth, h: el.offsetHeight });
  const setRectOf = el => r => { el.style.left = r.x + 'px'; el.style.top = r.y + 'px'; el.style.width = r.w + 'px'; el.style.height = r.h + 'px'; };
  function skin(el, o) {
    el.classList.add('qqa'); el.style.position = 'absolute'; root.insertBefore(el, taskbar());
    const w = WM.adopt(el, Object.assign({ handle: e => !!e.target.closest('.qq-title') && !e.target.closest('button'), getRect: rectOf(el), setRect: setRectOf(el), taskbtn: true, destroy: true, icon: 'xp/ui/qq16.png' }, o));
    w._apply(); w.focus(); return w;
  }
  const ST = { online: ['在线', 'img/QQ_online.png'], q: ['Q我吧'], away: ['离开'], busy: ['忙碌'], dnd: ['请勿打扰'], hide: ['隐身'], off: ['离线'] };
  const me = { name: 'GG-Bond', status: '在线' };
  let loginW = null, loggingW = null, panelW = null; const chats = {};

  // ---------- 登录 ----------
  function showLogin() {
    if (loginW && !loginW.closed) return loginW.focus();
    const form = tpl(QQTPL.login); form.classList.add('qqa'); form.style.margin = '0';
    const num = qs(form, '#qq-login-num'), pw = qs(form, '#qq-login-password');
    num.value = '10086'; pw.value = '••••••';
    const go = () => { const n = num.value.trim(); if (!n) { WM.alert('QQ', '请输入 QQ 号码。', { kind: 'warn' }); return; } me.num = n; loginW.close(); showLogging(); };
    qs(form, '#loginBtn').addEventListener('click', go); pw.addEventListener('keydown', e => { if (e.key === 'Enter') go(); }); num.addEventListener('keydown', e => { if (e.key === 'Enter') pw.focus(); });
    qs(form, '#registerBtn').addEventListener('click', () => loginW.close());
    qs(form, '#qq-login-reg').addEventListener('click', () => WM.open('ie', { url: 'http://zc.qq.com/', multi: true }));
    qs(form, '#qq-login-forget').addEventListener('click', e => { e.preventDefault(); WM.open('ie', { url: 'http://aq.qq.com/', multi: true }); });
    qs(form, '#qq-login-num-select').addEventListener('click', e => { const r = e.target.getBoundingClientRect(), rr = root.getBoundingClientRect(), k = rr.width / DW; WM.menu([{ t: '10086', icon: 'xp/ui/qq16.png', on: () => { num.value = '10086'; } }, { t: '88888888', icon: 'xp/ui/qq16.png', on: () => { num.value = '88888888'; } }, '-', { t: '清除记录', on: () => { num.value = ''; } }], (r.left - rr.left) / k, (r.bottom - rr.top) / k); });
    loginW = WM.create({ id: 'qq-login', title: 'QQ用户登录', icon: 'xp/ui/qq16.png', w: 331, h: 280, x: 120, y: 190, resizable: false, content: () => form, onclose: () => { loginW = null; } });
    loginW.o.dialog = false; setTimeout(() => num.focus(), 60); return loginW;
  }
  // ---------- 登录中 ----------
  function showLogging() {
    const el = tpl(QQTPL.logging); el.style.width = '190px'; el.style.height = '260px'; el.style.left = '300px'; el.style.top = '150px';
    loggingW = skin(el, { id: 'qq-logging', title: 'QQ 2006', btns: { min: '.qq-title-btns button:nth-child(1)', close: '.qq-title-btns button:nth-child(2)' }, fixedSize: true });
    const cancel = () => { clearTimeout(t); loggingW.close(); showLogin(); };
    qs(el, '#qq-logging-cancel').addEventListener('click', cancel);
    qs(el, '.qq-title-btns button:nth-child(2)').addEventListener('click', () => clearTimeout(t));
    const t = setTimeout(() => { loggingW.close(); showPanel(); }, 1800);
  }
  // ---------- 主面板 ----------
  function showPanel() {
    if (panelW && !panelW.closed) return panelW.focus();
    const el = tpl(QQTPL.panel); el.style.left = '1070px'; el.style.top = '18px'; el.style.width = '190px'; el.style.height = '600px';
    panelW = skin(el, { id: 'qq-panel', title: 'QQ 2006', btns: { min: '#qq-min', close: '#qq-close' }, fixedSize: true, resize: ['n', 's'], minW: 190, minH: 380,
      onapply: null });
    const lab = qs(el, '#qq-num'); const setStatus = s => { me.status = s; lab.textContent = me.name + '(' + s + ')'; el.classList.toggle('qq-off', s === '离线'); }; setStatus('在线');
    qs(el, '#qq-status-btn').addEventListener('click', e => { const r = e.target.getBoundingClientRect(), rr = root.getBoundingClientRect(), k = rr.width / DW; WM.menu(['在线', 'Q我吧', '离开', '忙碌', '请勿打扰', '隐身', '离线'].map(s => ({ t: s, radio: true, chk: me.status === s, on: () => setStatus(s) })), (r.left - rr.left) / k, (r.bottom - rr.top) / k); });
    lab.addEventListener('click', () => WM.alert('我的资料', '昵称: ' + me.name + '\nQQ号码: ' + (me.num || '10086') + '\n等级: 太阳 ☀', { kind: 'info' }));
    qs(el, '#qq-status-pic').addEventListener('click', () => WM.alert('修改个人资料', '昵称: ' + me.name + '\nQQ号码: ' + (me.num || '10086'), { kind: 'info' }));
    qs(el, '#qq-mail').addEventListener('click', () => WM.open('ie', { url: 'http://mail.qq.com/', multi: true }));
    qs(el, '#qq-security').addEventListener('click', () => WM.alert('QQ安全中心', '您的帐号安全，未发现异常。', { kind: 'info' }));
    qs(el, '#qq-payment').addEventListener('click', () => WM.alert('我的钱包', 'Q币余额: 12.00 个', { kind: 'info' }));
    qs(el, '#qq-color').addEventListener('click', () => { const f = parseInt(el.dataset.hue || 0, 10); el.dataset.hue = (f + 60) % 360; el.style.filter = el.dataset.hue === '0' ? '' : `hue-rotate(${el.dataset.hue}deg)`; });
    // 面板按钮
    const pbtns = [...el.querySelectorAll('.qq-panel-bar button')]; pbtns.forEach(b => b.addEventListener('click', () => { pbtns.forEach(x => x.classList.toggle('active', x === b)); if (b.id !== 'qq-FriendButton') WM.alert('QQ', '“' + b.title + '”在演示环境中暂不可用。', { kind: 'info' }); else { /* 好友 */ } setTimeout(() => { pbtns.forEach(x => x.classList.toggle('active', x.id === 'qq-FriendButton')); }, 10); }));
    // 好友列表：分组折叠 + 双击私聊 + 右键菜单
    const list = qs(el, '.qq-friend-list');
    const kids = g => { const out = []; let n = g.nextElementSibling; while (n && !n.classList.contains('qq-friend-group')) { out.push(n); n = n.nextElementSibling; } return out; };
    const sync = () => list.querySelectorAll('.qq-friend-group').forEach(g => kids(g).forEach(k => { k.style.display = g.classList.contains('on') ? '' : 'none'; }));
    list.querySelectorAll('.qq-friend-group').forEach(g => g.addEventListener('click', () => { g.classList.toggle('on'); sync(); })); sync();
    list.querySelectorAll('.qq-friend-item').forEach(it => {
      const f = () => ({ name: qs(it, '.qq-friend-name').textContent, motto: qs(it, '.qq-friend-motto').textContent.trim(), avatar: qs(it, '.qq-friend-avatar').getAttribute('src'), vip: it.classList.contains('qq-vip') });
      it.addEventListener('click', () => { list.querySelectorAll('.qq-friend-item.sel').forEach(x => x.classList.remove('sel')); it.classList.add('sel'); it.style.background = '#c3dff7'; list.querySelectorAll('.qq-friend-item').forEach(x => { if (x !== it) x.style.background = ''; }); });
      it.addEventListener('dblclick', () => openChat(f()));
      it.addEventListener('contextmenu', ev => { ev.preventDefault(); ev.stopPropagation(); const fr = f(); WM.ctx(ev, [{ t: '发送即时消息', bold: true, on: () => openChat(fr) }, { t: '发送短信', dis: true }, { t: '查看资料', on: () => WM.alert(fr.name + ' 的资料', '昵称: ' + fr.name + '\n个性签名: ' + fr.motto, { kind: 'info' }) }, { t: '聊天记录', on: () => WM.alert('消息管理器', '与 ' + fr.name + ' 的聊天记录为空。', { kind: 'info' }) }, '-', { t: '移动联系人至', sub: [{ t: '我的好友' }, { t: '家人' }] }, { t: '删除好友', dis: true }]); });
    });
    // 底部工具栏
    const bp = (id, f) => { const b = qs(el, id); b && b.addEventListener('click', f); };
    bp('#qq-GameButton', () => WM.open('qqgame')); bp('#qq-TTButton', () => WM.open('ie', { multi: true })); bp('#qq-QQHome', () => WM.open('ie', { url: 'http://qzone.qq.com/', multi: true })); bp('#qq-QQMusicButton', () => WM.open('ttplayer')); bp('#qq-QQTVButton', () => WM.open('baofeng', { clip: 0 })); bp('#qq-Pet', () => WM.alert('QQ宠物', '您还没有领养宠物。', { kind: 'info' })); bp('#qq-MobileMsgButton', () => WM.alert('发送手机消息', '该功能需要绑定手机。', { kind: 'info' })); bp('#qq-MsgManagerButton', () => WM.alert('消息管理器', '没有聊天记录。', { kind: 'info' }));
    bp('#qq-SearchButton', () => WM.prompt('查找用户', '请输入 QQ 号码或昵称：', '', v => { v && WM.alert('查找', '没有找到“' + v + '”相关的用户。', { kind: 'info' }); }));
    qs(el, '#qq-MenuButton').addEventListener('click', e => { const r = e.currentTarget.getBoundingClientRect(), rr = root.getBoundingClientRect(), k = rr.width / DW; WM.menu([{ t: '系统设置(S)', on: () => WM.alert('系统设置', '常规 / 状态 / 安全 / 权限 / 消息 / 热键 / 网络设置', { kind: 'info' }) }, { t: '好友管理器(M)', on: () => {} }, { t: '我的QQ空间', on: () => WM.open('ie', { url: 'http://qzone.qq.com/', multi: true }) }, '-', { t: '关于QQ(A)', on: () => WM.alert('关于 QQ', 'QQ2006 (演示复刻)\n界面素材来自 mengkunsoft/QQ2006。', { kind: 'info' }) }, '-', { t: '退出(X)', on: () => panelW && panelW.close() }], (r.left - rr.left) / k, (r.top - rr.top) / k - 150); });
    return panelW;
  }
  // ---------- 私聊 ----------
  const REPLIES = ['好久不见，你还好吗？', '哈哈哈，真有意思', '你也在听歌吗？', '嗯嗯，我也这么觉得', '真的吗？', '晚上一起开黑吧？', '刚才路过直播间，歌单不错～', '在吗在吗~', '我在挂机，稍等哦', '^_^', '回不去的是青春，等不到的是旧人', '欢迎回到 2006 年'];
  const FACES = ['😊', '😄', '😆', '😉', '😍', '😘', '😎', '😜', '😢', '😭', '😡', '😱', '😴', '😋', '🤔', '👍', '👎', '👏', '🙏', '💪', '❤️', '💔', '🌹', '🎵', '☀️', '🌙', '🎁', '🎂', '🍺', '☕'];
  function openChat(f) {
    const id = 'qq-chat-' + f.name;
    if (chats[id] && !chats[id].closed) { return chats[id].state === 'min' ? chats[id].restore() : chats[id].focus(); }
    const el = tpl(QQTPL.chat); el.classList.remove('drag-parent'); el.style.cssText = ''; const off = Object.keys(chats).filter(k => chats[k] && !chats[k].closed).length;
    el.style.left = (260 + off * 28) + 'px'; el.style.top = (60 + off * 28) + 'px'; el.style.width = '500px'; el.style.height = '460px';
    qs(el, '.qq-title-text').textContent = '与 ' + f.name + ' 聊天中';
    qs(el, '.qq-im-friend-info img').src = f.avatar; qs(el, '.qq-im-friend-info p').textContent = f.name + '(' + (10000 + Math.abs([...f.name].reduce((a, c) => a * 31 + c.charCodeAt(0), 7)) % 89999) + ')：' + (f.motto || '');
    const list = qs(el, '.qq-im-chat-msg-list'); list.innerHTML = ''; const input = qs(el, '.qq-im-chat-send');
    const now = () => { const d = new Date(), p = v => String(v).padStart(2, '0'); return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()); };
    const add = (who, text, mine) => { const li = h('li', { class: mine ? 'my' : '' }, [h('p', {}, [who, h('span', { text: now() })]), h('p', { text })]); list.appendChild(li); if (!mine) document.dispatchEvent(new CustomEvent('qqmsg', { detail: { friend: f.name, text, win: chats[id] } })); const box = qs(el, '.qq-im-chat-msg'); box.scrollTop = box.scrollHeight; list.parentNode.scrollTop = list.parentNode.scrollHeight; };
    const reply = () => { const typing = qs(el, '.qq-im-friend-info p'); setTimeout(() => add(f.name, REPLIES[Math.floor(Math.random() * REPLIES.length)], false), 900 + Math.random() * 1400); };
    const send = () => { const v = input.value.trim(); if (!v) return; add(me.name, v, true); input.value = ''; reply(); };
    qs(el, '#btn-send-msg').addEventListener('click', send); input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
    const btns = el.querySelectorAll('.qq-im-btns .qq-btn'); btns[0].addEventListener('click', () => WM.alert('消息管理器', list.children.length ? '共 ' + list.children.length + ' 条消息。' : '聊天记录为空。', { kind: 'info' })); btns[1].addEventListener('click', () => WM.alert('消息模式', '消息模式：按 Enter 键发送消息。', { kind: 'info' })); btns[2].addEventListener('click', () => w.close());
    // 工具栏：表情 / 字体 / 其它
    const face = qs(el, '.im-toolbar-face'); face.addEventListener('click', e => { const r = face.getBoundingClientRect(), rr = root.getBoundingClientRect(), k = rr.width / DW; const pop = h('div', { class: 'xpm', style: `left:${(r.left - rr.left) / k}px;top:${(r.top - rr.top) / k - 124}px;width:208px;padding:4px;display:grid;grid-template-columns:repeat(8,24px);gap:2px;font-size:16px;line-height:24px;text-align:center;z-index:13000;background:#fff;border:1px solid #6b8cc0` }); FACES.forEach(c => pop.appendChild(h('div', { text: c, onclick: () => { input.value += c; input.focus(); WM.closeMenus(); } }))); WM.closeMenus(); root.appendChild(pop); setTimeout(() => { const off = ev => { if (!pop.contains(ev.target)) { pop.remove(); document.removeEventListener('pointerdown', off, true); } }; document.addEventListener('pointerdown', off, true); }, 0); });
    qs(el, '.im-toolbar-font').addEventListener('click', () => { input.style.fontWeight = input.style.fontWeight === 'bold' ? '' : 'bold'; });
    ['other', 'picture', 'catch', 'scene', 'bag', 'ptt'].forEach(k => qs(el, '.im-toolbar-' + k).addEventListener('click', () => WM.alert('QQ', '该功能在演示环境中暂不可用。', { kind: 'info' })));
    [['#qq-im-msg', '短信'], ['#qq-im-video', '视频聊天'], ['#qq-im-audio', '语音聊天'], ['#qq-im-file', '传送文件'], ['#qq-im-3d', '3D秀']].forEach(([s, t]) => qs(el, s).addEventListener('click', () => WM.alert('QQ - ' + t, '正在等待对方响应…\n对方暂时无法接收请求。', { kind: 'info' })));
    qs(el, '#qq-im-invite').addEventListener('click', () => WM.alert('邀请', '已向 ' + f.name + ' 发送邀请。', { kind: 'info' }));
    el.querySelectorAll('.qq-im-side-btn').forEach(b => b.addEventListener('click', () => b.nextElementSibling && (b.nextElementSibling.style.display = b.nextElementSibling.style.display === 'none' ? '' : 'none')));
    const w = skin(el, { id, title: '与 ' + f.name + ' 聊天中', btns: { min: '#qq-im-min', max: '#qq-im-max', close: '#qq-im-close' }, resize: ['n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se'], minW: 420, minH: 360, titleDbl: e => !!e.target.closest('.qq-title') && !e.target.closest('button'), icon: 'xp/ui/qq16.png' });
    chats[id] = w; setTimeout(() => input.focus(), 50);
    setTimeout(() => add(f.name, f.motto && f.motto.length < 24 ? f.motto : '在吗？', false), 700);
    return w;
  }
  WM.register('qq', { open: () => { if (panelW && !panelW.closed) return panelW.state === 'min' ? panelW.restore() : panelW.focus(); if (loggingW && !loggingW.closed) return loggingW.focus(); return showLogin(); } });
  WM.openChat = openChat;
})();
