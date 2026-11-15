// ?desk=xp：QQ 群聊窗口的可操作功能（本地输入/发送、表情面板、聊天记录、工具栏、成员右键/双击私聊与资料卡）。
// 不影响直播内容：本地发送的消息只显示在这个窗口里，不会发到直播间。
(function () {
  if (!window.DESK || !DESK.on || !window.WM || !WM.ready) return;
  const { h, esc, ICO, root, DW, toRoot } = WM, $ = id => document.getElementById(id);
  const win = $('win'), list = $('list'), inputBox = $('input'), mlist = $('mlist');
  if (!win || !list || !inputBox) return;
  const pad = n => String(n).padStart(2, '0'), clock = () => { const d = new Date(); return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()); };
  const ph = (inputBox.querySelector('.ph') || {}).textContent || '';
  inputBox.innerHTML = '';
  const ta = h('textarea', { spellcheck: false, placeholder: ph, style: 'width:100%;height:100%;border:0;outline:0;resize:none;background:transparent;font:inherit;color:#000;padding:0;margin:0;overflow:auto' });
  inputBox.appendChild(ta);
  const st = document.createElement('style'); st.textContent = `#win .qq-im-chat-send textarea::placeholder { color:#9aa; } #win .qq-im-chat-send textarea { cursor:text; } #win .mlist li { cursor:default; } #win .mlist li.sel { background:#316ac5; color:#fff; }
    .gc-hist { position:absolute; inset:0; display:flex; flex-direction:column; background:#fff; font:12px var(--xpfont); } .gc-hist .hb { height:30px; display:flex; align-items:center; gap:8px; padding:0 8px; background:#ece9d8; border-bottom:1px solid #aca899; } .gc-hist .hl { flex:1; overflow:auto; padding:6px 10px; line-height:18px; } .gc-hist .hl p { margin:0; } .gc-hist .hl .hn { color:#0a4fa8; } .gc-hist .hl .hs { color:#7f7f7f; }
    .gc-card { position:absolute; inset:0; background:linear-gradient(#e8f3ff,#fff 60%); font:12px var(--xpfont); padding:12px 16px; } .gc-card img.av { width:48px; height:48px; border:1px solid #6b8cc0; float:left; margin-right:12px; } .gc-card .nm { font:700 14px var(--xpfont); margin-top:4px; } .gc-card table { margin-top:14px; border-collapse:collapse; width:100%; clear:both; } .gc-card td { padding:3px 4px; border-bottom:1px dotted #bcd; }`;
  document.head.appendChild(st);
  const self = { name: 'GG-Bond', num: '10086' };
  const hashN = s => { let x = 5381; for (let i = 0; i < s.length; i++) x = ((x << 5) + x + s.charCodeAt(i)) >>> 0; return x; };
  function addMine(text) {
    const li = document.createElement('li'); li.className = 'my new';
    li.innerHTML = '<p><img class="ava" src="img/avatar/97.png">' + esc(self.name) + '(' + self.num + ')<span>' + clock() + '</span></p><p>' + esc(text) + '</p>';
    list.appendChild(li); list.scrollTop = list.scrollHeight;
  }
  const send = () => { const v = ta.value.trim(); if (!v) return; addMine(v); ta.value = ''; };
  ta.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Enter' && !e.shiftKey && !(modeCtrl && !e.ctrlKey)) { e.preventDefault(); send(); } });
  inputBox.addEventListener('pointerdown', () => setTimeout(() => ta.focus(), 0));
  let modeCtrl = false;
  const btns = [...win.querySelectorAll('.qq-im-btns .qq-btn')]; // 记录 模式 关闭 发送 ↓
  const at = el => { const r = el.getBoundingClientRect(), rr = root.getBoundingClientRect(), k = rr.width / DW; return { x: (r.left - rr.left) / k, y: (r.top - rr.top) / k, b: (r.bottom - rr.top) / k }; };
  // ---- 聊天记录 ----
  function history() {
    const rows = [...list.children].map(li => { const ps = li.querySelectorAll('p'); return { sys: ps[0].classList.contains('sysline'), head: ps[0].textContent, body: ps[1] ? ps[1].textContent : '' }; });
    const el = h('div', { class: 'gc-hist' }), hl = h('div', { class: 'hl' }); const q = h('input', { class: 'xinput', placeholder: '搜索聊天记录', style: 'width:180px' });
    const draw = () => { hl.innerHTML = ''; const k = q.value.trim(); rows.filter(r => !k || (r.head + r.body).includes(k)).forEach(r => hl.appendChild(r.sys ? h('p', { class: 'hs', text: r.head }) : h('div', { style: 'margin-bottom:4px' }, [h('p', { class: 'hn', text: r.head }), h('p', { text: r.body })]))); hl.scrollTop = hl.scrollHeight; };
    q.addEventListener('input', draw); q.addEventListener('keydown', e => e.stopPropagation());
    el.append(h('div', { class: 'hb' }, [h('span', { text: '查找(F)：' }), q, h('span', { text: '共 ' + rows.length + ' 条', style: 'margin-left:auto;color:#555' })]), hl); draw();
    WM.create({ id: 'gc-history', title: '消息管理器 - GG-Bond 的直播间', icon: 'xp/ui/qq16.png', w: 520, h: 400, minW: 300, minH: 200, content: () => el });
  }
  btns[0].addEventListener('click', history);
  btns[1].addEventListener('click', () => { const p = at(btns[1]); WM.menu([{ t: '按 Enter 键发送消息(E)', radio: true, chk: !modeCtrl, on: () => { modeCtrl = false; } }, { t: '按 Ctrl+Enter 键发送消息(C)', radio: true, chk: modeCtrl, on: () => { modeCtrl = true; } }], p.x, p.y - 56); });
  btns[2].addEventListener('click', () => { const w = WM.byId.qqchat; w && w.close(); });
  btns[3].addEventListener('click', send);
  btns[4].addEventListener('click', () => { const p = at(btns[4]); WM.menu([{ t: '发送(S)', on: send }, { t: '清屏(L)', on: () => { list.innerHTML = ''; } }, '-', { t: '按 Enter 键发送消息', radio: true, chk: !modeCtrl, on: () => { modeCtrl = false; } }, { t: '按 Ctrl+Enter 键发送消息', radio: true, chk: modeCtrl, on: () => { modeCtrl = true; } }], p.x - 140, p.y - 98); });
  // ---- 输入工具栏 ----
  const FACES = ['😊', '😄', '😆', '😉', '😍', '😘', '😎', '😜', '😢', '😭', '😡', '😱', '😴', '😋', '🤔', '👍', '👎', '👏', '🙏', '💪', '❤️', '💔', '🌹', '🎵', '☀️', '🌙', '🎁', '🎂', '🍺', '☕', '🐷', '🎤'];
  const tbtn = c => win.querySelector('.qq-im-chat-toolbar .im-toolbar-' + c);
  tbtn('face').addEventListener('click', () => { const p = at(tbtn('face')); const pop = h('div', { class: 'xpm', style: `left:${p.x}px;top:${p.y - 128}px;width:216px;padding:4px;display:grid;grid-template-columns:repeat(8,25px);gap:2px;font-size:17px;line-height:25px;text-align:center;z-index:13000;background:#fff;border:1px solid #6b8cc0` }); FACES.forEach(c => pop.appendChild(h('div', { text: c, onclick: () => { ta.value += c; ta.focus(); pop.remove(); } }))); WM.closeMenus(); root.appendChild(pop); setTimeout(() => { const off = ev => { if (!pop.contains(ev.target)) { pop.remove(); document.removeEventListener('pointerdown', off, true); } }; document.addEventListener('pointerdown', off, true); }, 0); });
  tbtn('font').addEventListener('click', () => { const p = at(tbtn('font')); WM.menu([{ t: '粗体(B)', chk: ta.style.fontWeight === 'bold', on: () => { ta.style.fontWeight = ta.style.fontWeight === 'bold' ? '' : 'bold'; } }, { t: '斜体(I)', chk: ta.style.fontStyle === 'italic', on: () => { ta.style.fontStyle = ta.style.fontStyle === 'italic' ? '' : 'italic'; } }, '-', { t: '字号 12', radio: true, chk: !ta.style.fontSize, on: () => { ta.style.fontSize = ''; } }, { t: '字号 16', radio: true, chk: ta.style.fontSize === '16px', on: () => { ta.style.fontSize = '16px'; } }], p.x, p.y - 108); });
  tbtn('other').addEventListener('click', () => { const p = at(tbtn('other')); WM.menu([{ t: '发送窗口抖动', on: () => { if (window.QQX && QQX.cfg.enabled && QQX.cfg.shake) return QQX.menuShake(); const w = WM.byId.qqchat; if (!w) return; const r0 = Object.assign({}, w.rect); let i = 0; const iv = setInterval(() => { w.rect.x = r0.x + (i % 2 ? 6 : -6); w._apply(); if (++i > 10) { clearInterval(iv); w.rect = r0; w._apply(); } }, 40); } }, { t: '魔法表情', dis: true }, { t: '涂鸦', dis: true }], p.x, p.y - 80); });
  tbtn('picture').addEventListener('click', () => WM.open('explorer', { path: 'mypics', view: 'thumbs' }));
  tbtn('catch').addEventListener('click', () => WM.alert('屏幕捕捉', '请按住 Ctrl+Alt+A 选取要截取的区域。', { kind: 'info' }));
  tbtn('scene').addEventListener('click', () => WM.alert('QQ', '聊天场景在演示环境中暂不可用。', { kind: 'info' }));
  tbtn('bag').addEventListener('click', () => WM.alert('QQ', '您的聊天背包是空的。', { kind: 'info' }));
  tbtn('ptt').addEventListener('click', () => WM.alert('语音消息', '没有检测到麦克风设备。', { kind: 'warn' }));
  // ---- 大工具栏 ----
  const big = { 'qq-im-msg': () => WM.open('outlook'), 'qq-im-video': () => WM.open('ie', { url: 'http://qzone.qq.com/', multi: true }), 'qq-im-audio': () => WM.alert('多人语音', '正在连接语音服务器…\n连接超时，请稍后再试。', { kind: 'info' }), 'qq-im-file': () => WM.open('explorer', { path: 'mydocs' }), 'qq-im-3d': () => WM.open('ttplayer'), 'qq-im-invite': () => WM.alert('邀请', '已复制邀请链接到剪贴板。', { kind: 'info' }) };
  win.querySelectorAll('.qq-im-big-toolbar button').forEach((b, i) => { const keys = ['群邮件', '群空间', '多人语音', 'QQ直播', '音乐', '邀请']; const acts = [() => WM.open('outlook'), () => (window.QQX && QQX.cfg.enabled && QQX.cfg.zone ? WM.open('qzone') : WM.open('ie', { url: 'http://qzone.qq.com/', multi: true })), big['qq-im-audio'], () => WM.open('ie', { url: 'http://www.qq.com/', multi: true }), () => WM.open('ttplayer'), big['qq-im-invite']]; b.addEventListener('click', e => { e.stopPropagation(); acts[i] && acts[i](); }); });
  // ---- 成员列表：选中 / 双击私聊 / 右键 ----
  const info = li => { const name = li.textContent.replace(/\((群主|AI)\)$/, ''); const img = li.querySelector('img'); return { name, avatar: img ? img.getAttribute('src') : 'img/avatar/1.png', motto: li.classList.contains('anchor') ? '欢迎来到直播间' : li.classList.contains('bot') ? 'AI 虚拟主播' : '', num: String(10000 + hashN(name) % 89999999) }; };
  function card(m) {
    const el = h('div', { class: 'gc-card' }, [h('img', { class: 'av', src: m.avatar }), h('div', { class: 'nm', text: m.name }), h('div', { text: 'QQ: ' + m.num, style: 'color:#555;margin-top:2px' }),
      h('table', {}, [['昵称', m.name], ['性别', hashN(m.name) % 2 ? '男' : '女'], ['年龄', 16 + hashN(m.name) % 14], ['所在地', '广东 深圳'], ['个性签名', m.motto || '这个人很懒，什么都没写～'], ['QQ秀', '已开通']].map(([k, v]) => h('tr', {}, [h('td', { text: k, style: 'width:60px;color:#16539b' }), h('td', { text: v })]))), h('div', { style: 'position:absolute;right:12px;bottom:10px;display:flex;gap:6px' }, [h('button', { class: 'xbtn', text: '发送消息', onclick: () => WM.openChat && WM.openChat(m) }), h('button', { class: 'xbtn', text: '关闭', onclick: () => WM.byId['gc-card-' + m.name] && WM.byId['gc-card-' + m.name].close() })])]);
    WM.create({ id: 'gc-card-' + m.name, title: m.name + ' 的资料', icon: 'xp/ui/qq16.png', w: 340, h: 330, resizable: false, dialog: true, content: () => el });
  }
  const sel = li => { mlist.querySelectorAll('li.sel').forEach(x => x.classList.remove('sel')); li.classList.add('sel'); };
  const chatOf = m => WM.openChat && WM.openChat({ name: m.name, avatar: m.avatar, motto: m.motto });
  mlist.addEventListener('click', e => { const li = e.target.closest('li'); li && sel(li); });
  mlist.addEventListener('dblclick', e => { const li = e.target.closest('li'); if (li) chatOf(info(li)); });
  mlist.addEventListener('contextmenu', e => { const li = e.target.closest('li'); if (!li) return; sel(li); const m = info(li); WM.ctx(e, [{ t: '发送即时消息', bold: true, on: () => chatOf(m) }, { t: '查看资料', on: () => card(m) }, { t: '@ TA', on: () => { ta.value += '@' + m.name + ' '; ta.focus(); } }, '-', { t: '复制昵称', on: () => { try { navigator.clipboard.writeText(m.name); } catch (er) {} } }, { t: '禁言', dis: true }, { t: '移出本群', dis: true }]); });
  // ---- 其它点击 ----
  const gav = $('gavatar'); gav && gav.addEventListener('click', () => card({ name: 'GG-Bond 的直播间', avatar: gav.getAttribute('src'), motto: '群公告：QQ聊天室', num: '88888888' }));
  const mc = $('mcount'); mc && mc.addEventListener('click', () => { /* 折叠/展开由 app.js 管理 */ });
})();
