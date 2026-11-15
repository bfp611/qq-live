// 控制面板（XP 分类视图 + 经典视图）与三个可用的“小程序”：显示（沿用 apps-core.js）、声音和音频设备（连着 [xp] 音效设置）、日期和时间（沿用）、鼠标（指针速度 / 指针踪迹）
// 这里改的设置只在当前页面有效（刷新后回到 config.ini 的 [xp] / [agent] 设置）。图标全部取自 XP 原版图标集（ShizukuIchi/winXP, MIT）。
(function () {
  if (!window.WM || !WM.ready) return;
  const { h, ICO } = WM, S = WM.S, XPc = () => window.XP || { cfg: {}, GROUPS: [], allowed: () => true, snd: () => null };
  const st = document.createElement('style'); st.textContent = `
  .cp { position:absolute; inset:0; display:flex; background:#fff; font:12px var(--xpfont); user-select:none; }
  .cp .lp { width:180px; flex:none; background:linear-gradient(#7ba2e7,#6375d6); padding:12px 10px; overflow:auto; }
  .cp .box { background:#d6dff7; border-radius:6px 6px 0 0; margin-bottom:12px; overflow:hidden; } .cp .box .hd { background:linear-gradient(to right,#fff,#c6d3f7); color:#215dc6; font-weight:700; padding:4px 10px; } .cp .box .bd { padding:6px 10px 8px; display:flex; flex-direction:column; gap:5px; }
  .cp a { color:#215dc6; cursor:pointer; } .cp a:hover { color:#428eff; text-decoration:underline; }
  .cp .rp { flex:1; min-width:0; overflow:auto; background:#fff; position:relative; }
  .cp .rp .bar { height:34px; background:linear-gradient(to right,#fff,#9ebbef); display:flex; align-items:center; padding:0 14px; font:700 15px var(--xpfont); color:#fff; text-shadow:1px 1px #4a69b5; } .cp .rp .bar a { color:#fff; margin-right:8px; } .cp .rp .bar a:hover { color:#fff; }
  .cp .pick { padding:14px 16px 8px; font-size:13px; font-weight:700; color:#215dc6; }
  .cp .cats { display:grid; grid-template-columns:repeat(3,1fr); gap:14px 4px; padding:6px 10px; } .cp .cat { display:flex; flex-direction:column; align-items:center; gap:5px; padding:6px 4px; text-align:center; border:1px solid transparent; border-radius:4px; cursor:pointer; } .cp .cat:hover { background:#e8f0ff; border-color:#b8cbf0; } .cp .cat img { width:32px; height:32px; } .cp .cat span { color:#215dc6; }
  .cp .sub { padding:6px 16px; } .cp .sub h4 { margin:12px 0 6px; font:700 12px var(--xpfont); color:#215dc6; } .cp .sub .tasks { display:flex; flex-direction:column; gap:7px; padding-left:8px; } .cp .sub .appl { display:flex; flex-wrap:wrap; gap:8px; padding-left:4px; } .cp .sub .ap { display:flex; align-items:center; gap:6px; width:190px; padding:3px; border:1px solid transparent; border-radius:3px; cursor:pointer; } .cp .sub .ap:hover { background:#e8f0ff; border-color:#b8cbf0; } .cp .sub .ap img { width:32px; height:32px; }
  .cp .classic { display:grid; grid-template-columns:repeat(auto-fill,92px); gap:8px 2px; padding:10px; } .cp .classic .ap { flex-direction:column; width:auto; text-align:center; padding:4px 2px; display:flex; align-items:center; gap:4px; border:1px solid transparent; cursor:pointer; } .cp .classic .ap:hover { background:#e8f0ff; border-color:#b8cbf0; } .cp .classic img { width:32px; height:32px; }
  .cs-ev { height:96px; overflow:auto; border:1px solid #7f9db9; background:#fff; } .cs-ev div { padding:1px 6px; white-space:nowrap; cursor:default; } .cs-ev div.on { background:#316ac5; color:#fff; }
  .cs-gr { display:grid; grid-template-columns:1fr 1fr 1fr; gap:3px 8px; margin-top:4px; }
  `; document.head.appendChild(st);
  const na = (t, x) => () => WM.alert(t, x || '此控制面板项目在演示环境中不可用。', { kind: 'info' });
  const A = {   // 小程序：[名称, 图标, 动作]
    display: ['显示', '300_32.png', () => WM.open('display')], datetime: ['日期和时间', '301_32.png', () => WM.open('datetime')], sound: ['声音和音频设备', '846_32.png', () => WM.open('sndcpl')], mouse: ['鼠标', '300_32.png', () => WM.open('mousecpl')],
    taskbar: ['任务栏和「开始」菜单', '299_32.png', () => WM.open('taskbarprops')], inet: ['Internet 选项', '288_32.png', () => WM.open('inetcpl')], printers: ['打印机和传真', '549_32.png', () => WM.open('explorer', { path: 'printers' })],
    addrm: ['添加或删除程序', '358_32.png', na('添加或删除程序', '正在加载当前安装的程序列表…\n\n（演示环境：不能真正卸载程序。）')], net: ['网络连接', '309_32.png', na('网络连接', '本地连接：已连接\n速度：100.0 Mbps')], sys: ['系统', '676_32.png', () => WM.open('help')],
    users: ['用户账户', '546_32.png', na('用户账户', '计算机管理员：Administrator')], folder: ['文件夹选项', '318_32.png'], fonts: ['字体', '318_32.png'], keyboard: ['键盘', '300_32.png'], admin: ['管理工具', '300_32.png'], power: ['电源选项', '310_32.png', na('电源选项', '电源使用方案：家用/办公桌')],
    access: ['辅助功能选项', '227_32.png'], region: ['区域和语言选项', '301_32.png'],
  };
  Object.keys(A).forEach(k => { if (!A[k][2]) A[k][2] = na(A[k][0]); });
  const CATS = [
    { t: '外观和主题', ic: '300_32.png', tasks: [['更改计算机的主题', A.display[2]], ['更改桌面背景', A.display[2]], ['选择一个屏幕保护程序', A.display[2]], ['更改屏幕分辨率', A.display[2]]], ap: ['display', 'taskbar', 'folder'] },
    { t: '网络和 Internet 连接', ic: '309_32.png', tasks: [['设置或更改您的 Internet 连接', A.inet[2]], ['查看网络连接', A.net[2]]], ap: ['inet', 'net'] },
    { t: '添加或删除程序', ic: '358_32.png', tasks: [['更改或删除程序', A.addrm[2]], ['添加新程序', A.addrm[2]]], ap: ['addrm'] },
    { t: '声音、语音和音频设备', ic: '846_32.png', tasks: [['调整系统音量', () => WM.open('sndcpl', { tab: '音量' })], ['更改声音方案', () => WM.open('sndcpl', { tab: '声音' })]], ap: ['sound'] },
    { t: '性能和维护', ic: '676_32.png', tasks: [['查看关于此计算机的基本信息', A.sys[2]], ['清理桌面上的快捷方式', () => WM.open('cleanup')]], ap: ['sys', 'power', 'admin'] },
    { t: '打印机和其他硬件', ic: '549_32.png', tasks: [['查看已安装的打印机或传真打印机', A.printers[2]], ['调整鼠标指针速度', () => WM.open('mousecpl', { tab: '指针选项' })]], ap: ['printers', 'mouse', 'keyboard'] },
    { t: '用户账户', ic: '546_32.png', tasks: [['更改账户', A.users[2]]], ap: ['users'] },
    { t: '日期、时间、语言和区域设置', ic: '301_32.png', tasks: [['更改日期和时间', A.datetime[2]], ['更改数字、日期和时间的格式', A.region[2]]], ap: ['datetime', 'region'] },
    { t: '辅助功能选项', ic: '227_32.png', tasks: [['调整计算机的设置以适应视力、听力和移动能力', A.access[2]]], ap: ['access'] },
  ];
  const mkAp = k => h('div', { class: 'ap', 'data-applet': k, onclick: A[k][2] }, [h('img', { src: ICO(A[k][1]) }), h('a', { text: A[k][0] })]);
  WM.register('control', { open: a => {
    a = a || {}; let view = a.view || 'cat', cat = null;
    const rp = h('div', { class: 'rp' }), lp = h('div', { class: 'lp' });
    const side = () => { lp.innerHTML = ''; lp.append(
      h('div', { class: 'box' }, [h('div', { class: 'hd', text: '控制面板' }), h('div', { class: 'bd' }, [h('a', { text: view === 'cat' ? '切换到经典视图' : '切换到分类视图', 'data-act': 'switch', onclick: () => { view = view === 'cat' ? 'classic' : 'cat'; cat = null; draw(); } }), h('a', { text: 'Windows Update', onclick: () => WM.open('ie', { url: 'http://windowsupdate.microsoft.com/' }) })])]),
      h('div', { class: 'box' }, [h('div', { class: 'hd', text: '另请参阅' }), h('div', { class: 'bd' }, [h('a', { text: '帮助和支持', onclick: () => WM.open('help') }), h('a', { text: '桌面清理向导', onclick: () => WM.open('cleanup') })])])); };
    function draw() {
      side(); rp.innerHTML = ''; w && w.setTitle(cat ? cat.t + ' - 控制面板' : '控制面板');
      if (view === 'classic') { rp.append(h('div', { class: 'bar', text: '控制面板' }), h('div', { class: 'classic' }, Object.keys(A).map(mkAp))); return; }
      if (!cat) { rp.append(h('div', { class: 'bar', text: '控制面板' }), h('div', { class: 'pick', text: '挑选一个类别' }), h('div', { class: 'cats' }, CATS.map(c => h('div', { class: 'cat', 'data-cat': c.t, onclick: () => { cat = c; draw(); } }, [h('img', { src: ICO(c.ic) }), h('span', { text: c.t })])))); return; }
      rp.append(h('div', { class: 'bar' }, [h('a', { text: '控制面板', onclick: () => { cat = null; draw(); } }), h('span', { text: '› ' + cat.t })]),
        h('div', { class: 'sub' }, [h('h4', { text: '挑选一个任务…' }), h('div', { class: 'tasks' }, cat.tasks.map(([t, f]) => h('a', { text: t, 'data-task': t, onclick: f }))), h('h4', { text: '或选择一个控制面板图标' }), h('div', { class: 'appl' }, cat.ap.map(mkAp))]));
    }
    const w = WM.create({ id: 'control', title: '控制面板', icon: ICO('300_16.png'), w: 640, h: 440, minW: 420, minH: 280, content: () => h('div', { class: 'cp' }, [lp, rp]) });
    draw();
    w.cp = { state: () => ({ view, cat: cat && cat.t }), open: n => { cat = CATS.find(c => c.t === n || c.t.startsWith(n)) || null; view = 'cat'; draw(); return !!cat; }, cats: () => CATS.map(c => c.t) };
    return w;
  } });

  // ================= 声音和音频设备 =================
  const EVENTS = [['默认声音', 'default'], ['感叹号', 'exclamation'], ['关键性终止', 'critical'], ['询问', 'ding'], ['最小化', 'minimize'], ['还原', 'restore'], ['菜单命令', 'menu'], ['启动 Windows', 'startup'], ['登录 Windows', 'logon'], ['注销 Windows', 'logoff'], ['退出 Windows', 'shutdown'],
    ['新邮件通知', 'notify'], ['清空回收站', 'recycle'], ['气泡提示', 'balloon'], ['设备连接', 'hw_insert'], ['设备中断连接', 'hw_remove'], ['设备连接失败', 'hw_fail'], ['启动导航', 'start'], ['信息栏', 'infobar'], ['弹出窗口被阻止', 'popup_blocked'], ['打印完成', 'print'],
    ['QQ 新消息', 'qq_msg'], ['QQ 好友上线', 'qq_online'], ['QQ 系统消息', 'qq_system']];
  const GNAME = { open: '打开窗口', close: '关闭窗口', minimize: '最小化', restore: '还原 / 最大化', dialog: '提示对话框', error: '错误对话框', notify: '通知', balloon: '气泡通知', recycle: '回收站', hardware: '硬件', startup: '启动', shutdown: '关机 / 注销', qq: 'QQ 提示音', game: '游戏' };
  const slider = (v, min, max, f, step) => { const s = h('input', { type: 'range', min, max, step: step || 1, value: v, style: 'width:170px;vertical-align:middle' }); s.addEventListener('input', () => f(+s.value)); return s; };
  const chk = (label, on, f, attrs) => { const c = h('input', Object.assign({ type: 'checkbox' }, attrs || {})); c.checked = !!on; c.addEventListener('change', () => f(c.checked)); return h('div', { style: 'margin:4px 0' }, [c, h('label', { text: ' ' + label })]); };
  WM.register('sndcpl', { open: a => WM.tabsDialog({ id: 'sndcpl', title: '声音和音频设备 属性', icon: ICO('846_16.png'), w: 420, h: 480, tab: (a && a.tab) || '音量', pages: {
    '音量': () => {
      const X = XPc(), v = h('div', { style: 'width:36px;text-align:right', text: (WM.vol == null ? 70 : WM.vol) + '%' });
      const mute = chk('静音(M)', WM.mute, c => { WM.mute = c; document.dispatchEvent(new CustomEvent('sysmute', { detail: c })); }, { 'data-k': 'mute' });
      return h('div', {}, [h('div', { class: 'xgroup' }, [h('legend', { text: '设备音量' }), h('div', { style: 'display:flex;align-items:center;gap:8px;margin:6px 0' }, [h('img', { src: ICO('846_32.png'), style: 'width:32px;height:32px' }), h('div', { text: '主音量' }), slider(WM.vol == null ? 70 : WM.vol, 0, 100, n => { WM.vol = n; v.textContent = n + '%'; document.dispatchEvent(new CustomEvent('sysvol', { detail: n / 100 })); }), v]), mute]),
        h('div', { class: 'xgroup', style: 'margin-top:14px' }, [h('legend', { text: '系统音效（Windows XP 原版声音）' }), chk('启用 Windows 系统音效(E)', X.cfg.sounds, c => { X.cfg.sounds = c; }, { 'data-k': 'sounds' }), chk('静音系统音效', X.cfg.mute, c => { X.cfg.mute = c; }, { 'data-k': 'xmute' }),
          h('div', { style: 'display:flex;align-items:center;gap:8px;margin:6px 0' }, [h('div', { text: '音效音量' }), slider(Math.round((X.cfg.volume == null ? .5 : X.cfg.volume) * 100), 0, 100, n => { X.cfg.volume = n / 100; })])]),
        h('div', { style: 'margin-top:14px;color:#666', text: '提示：此处的改动只在当前页面有效，刷新后回到 config.ini 的 [xp] 设置。' })]);
    },
    '声音': () => {
      const X = XPc(); let sel = 'default';
      const ev = h('div', { class: 'cs-ev' }), draw = () => { ev.innerHTML = ''; EVENTS.forEach(([t, id]) => { const d = h('div', { class: id === sel ? 'on' : '', text: t, 'data-snd': id }); d.addEventListener('click', () => { sel = id; draw(); }); d.addEventListener('dblclick', () => X.snd(id, '', true)); ev.appendChild(d); }); }; draw();
      const al = (X.GROUPS || []).filter(g => X.allowed(g)); const gr = h('div', { class: 'cs-gr' });
      (X.GROUPS || []).forEach(g => gr.appendChild(chk(GNAME[g] || g, al.includes(g), c => { const cur = (X.GROUPS || []).filter(x => X.allowed(x)); const nx = c ? cur.concat(g) : cur.filter(x => x !== g); X.cfg.sound_events = nx.join(',') || ' '; X.cfg.sound_deny = ''; }, { 'data-grp': g })));
      return h('div', {}, [h('div', { text: '声音方案(H)：' }), h('select', { class: 'xinput', style: 'width:200px;margin:4px 0 8px', onchange: e => { const none = e.target.value === 'none'; X.cfg.sounds = !none; } }, [h('option', { value: 'win', text: 'Windows 默认' }), h('option', { value: 'none', text: '无声音' })]),
        h('div', { text: '程序事件(V)：' }), ev, h('div', { style: 'margin:8px 0;display:flex;gap:6px;align-items:center' }, [h('div', { text: '声音(S)：' }), h('button', { class: 'xbtn', text: '▶ 测试', 'data-act': 'test', onclick: () => X.snd(sel, '', true) }), h('button', { class: 'xbtn', text: '■ 停止', onclick: () => X.stopSnd && X.stopSnd() })]),
        h('div', { class: 'xgroup', style: 'margin-top:12px' }, [h('legend', { text: '哪些操作发出声音' }), gr])]);
    },
    '音频': () => h('div', {}, [h('div', { class: 'xgroup' }, [h('legend', { text: '声音播放' }), h('div', { text: '默认设备(L)：Realtek AC97 Audio' })]), h('div', { class: 'xgroup', style: 'margin-top:12px' }, [h('legend', { text: '录音' }), h('div', { text: '默认设备(D)：Realtek AC97 Audio' })])]),
  } }) });

  // ================= 鼠标 =================
  let trailOn = false, trailN = 6, trailEls = [], hist = [], trailT = null;
  function setTrail(on) {
    trailOn = on; clearInterval(trailT); trailEls.forEach(e => e.remove()); trailEls = []; hist = [];
    if (!on || !window.AG) return;
    for (let i = 0; i < trailN; i++) { const e = h('div', { class: 'ag-trail', style: `position:absolute;left:0;top:0;width:16px;height:24px;pointer-events:none;z-index:${WM.z + 900};background:url(xp/cursor/arrow.svg) no-repeat;opacity:${.6 - i * .08};display:none` }); WM.root.appendChild(e); trailEls.push(e); }
    trailT = setInterval(() => { const c = document.getElementById('ag-cur'), vis = c && !c.classList.contains('hide'); hist.unshift({ x: AG.pos.x, y: AG.pos.y }); hist = hist.slice(0, trailN * 2 + 1); trailEls.forEach((e, i) => { const p = hist[(i + 1) * 2 - 1]; if (!vis || !p || (Math.abs(p.x - AG.pos.x) + Math.abs(p.y - AG.pos.y) < 6)) { e.style.display = 'none'; return; } e.style.display = ''; e.style.transform = `translate(${p.x}px,${p.y}px)`; }); }, 30);
  }
  WM.register('mousecpl', { open: a => WM.tabsDialog({ id: 'mousecpl', title: '鼠标 属性', icon: ICO('300_16.png'), w: 400, h: 440, tab: (a && a.tab) || '按钮', pages: {
    '按钮': () => h('div', {}, [h('div', { class: 'xgroup' }, [h('legend', { text: '鼠标键配置' }), chk('切换主要和次要的按钮(S)', false, () => {})]), h('div', { class: 'xgroup', style: 'margin-top:14px' }, [h('legend', { text: '双击速度' }), h('div', { style: 'display:flex;align-items:center;gap:8px;margin:6px 0' }, [h('div', { text: '速度(D)：慢' }), slider(5, 1, 10, () => {}), h('div', { text: '快' })]), h('div', { style: 'margin:8px 0' }, ['测试区域(T)：', h('img', { src: ICO('318_32.png'), style: 'width:32px;height:32px;vertical-align:middle', ondblclick: e => { e.target.src = ICO('357_32.png'); setTimeout(() => e.target.src = ICO('318_32.png'), 600); } })])])]),
    '指针': () => h('div', {}, [h('div', { text: '方案(S)：' }), h('select', { class: 'xinput', style: 'width:240px;margin:4px 0' }, [h('option', { text: 'Windows 标准（系统方案）' })]), h('div', { class: 'xpanel', style: 'height:140px;margin-top:8px;display:flex;align-items:center;justify-content:center;gap:24px' }, ['arrow', 'hand', 'ibeam'].map(k => h('div', { style: `width:24px;height:32px;background:url(xp/cursor/${k}.svg) no-repeat center` })))]),
    '指针选项': () => { const sp = Math.round(((window.AG && AG.cfg.cursor_speed) || 900) / 100);
      return h('div', {}, [h('div', { class: 'xgroup' }, [h('legend', { text: '移动' }), h('div', { text: '选择指针移动速度(M)：' }), h('div', { style: 'display:flex;align-items:center;gap:8px;margin:8px 0' }, [h('div', { text: '慢' }), slider(sp, 2, 30, n => { if (window.AG) AG.cfg.cursor_speed = n * 100; }), h('div', { text: '快' })]), h('div', { style: 'color:#666', text: '（这个速度是桌面上 AI 操作的鼠标光标的移动速度。）' })]),
        h('div', { class: 'xgroup', style: 'margin-top:14px' }, [h('legend', { text: '可见性' }), chk('显示指针踪迹(D)', trailOn, c => setTrail(c), { 'data-k': 'trail' }), h('div', { style: 'display:flex;align-items:center;gap:8px;margin:6px 0 4px 18px' }, [h('div', { text: '短' }), slider(trailN, 2, 10, n => { trailN = n; if (trailOn) setTrail(true); }), h('div', { text: '长' })])])]); },
    '硬件': () => h('div', {}, [h('div', { text: '设备(D)：' }), h('div', { class: 'cs-ev', style: 'height:60px' }, [h('div', { text: 'PS/2 兼容鼠标' }), h('div', { text: 'HID-compliant mouse' })])]),
  } }) });
  WM.setMouseTrail = setTrail;
})();
