// 资源管理器（我的电脑 / 我的文档 / 回收站 / 控制面板 / 搜索 …）：XP 经典任务窗格 + 文件夹树 + 多种视图 + 前进后退向上 + 地址栏
(function () {
  if (!window.WM || !WM.ready) return;
  const { h, esc, ICO } = WM, S = WM.S;
  S.fsx = S.fsx || {};
  const I = (n, s) => ICO(n + '_' + (s || 32) + '.png');
  const F = (type, kb, date, act) => [type, kb, date, act || 'none'];
  const TXT = {
    '读书笔记.txt': '2007年3月\r\n\r\n- 周末去图书馆还书\r\n- 高数作业第三章\r\n- 把新买的 MP3 里歌词整理一下\r\n- 晚上上 QQ 跟小伙伴开黑\r\n',
    '歌词本.txt': '《七里香》 周杰伦\r\n窗外的麻雀 在电线杆上多嘴\r\n你说这一句 很有夏天的感觉\r\n手中的铅笔 在纸上来来回回\r\n我用几行字形容你是我的谁\r\n',
    'readme.txt': 'Counter-Strike 1.6\r\n\r\n请先安装 DirectX 9.0c，并在“控制面板”中把屏幕刷新率调到 75Hz 以上。\r\n',
    'boot.ini': '[boot loader]\r\ntimeout=30\r\ndefault=multi(0)disk(0)rdisk(0)partition(1)\\WINDOWS\r\n[operating systems]\r\nmulti(0)disk(0)rdisk(0)partition(1)\\WINDOWS="Microsoft Windows XP Professional" /noexecute=optin /fastdetect\r\n',
    'AUTOEXEC.BAT': '', 'hosts': '# Copyright (c) 1993-1999 Microsoft Corp.\r\n127.0.0.1       localhost\r\n',
  };
  const pic = n => F('JPEG 图像', 60 + (n.length * 17) % 240, '2007-05-0' + (1 + n.length % 8) + ' 18:2' + (n.length % 10), 'img:xp/wall/' + n);
  const mp3 = (kb, d) => F('MP3 格式声音', kb, d, 'app:ttplayer');
  const TREE = {
    '桌面': 'desktop',
    '我的文档': {
      '我的图片': { 'Bliss.jpg': pic('bliss.jpg').slice(0, 3).concat('img:xp/ui/bliss.jpg'), 'Blue hills.jpg': pic('blue_hills.jpg'), 'Sunset.jpg': pic('sunset.jpg'), 'Water lilies.jpg': pic('water_lilies.jpg'), 'Winter.jpg': pic('winter.jpg'), 'Autumn.jpg': pic('autumn.jpg'), 'Tulips.jpg': pic('tulips.jpg') },
      '我的音乐': { '周杰伦 - 七里香.mp3': mp3(4310, '2007-03-02 20:20'), '周杰伦 - 晴天.mp3': mp3(4672, '2007-03-02 20:21'), '陈奕迅 - 十年.mp3': mp3(3905, '2007-03-11 21:08'), '王力宏 - 不可思议.mp3': mp3(4120, '2007-04-02 11:46'), '五月天 - 倔强.mp3': mp3(3988, '2007-05-19 22:31'), '孙燕姿 - 遇见.mp3': mp3(3764, '2007-06-01 09:12') },
      '我的视频': {}, 'QQ 接收的文件': {},
      '读书笔记.txt': F('文本文档', 1, '2007-03-22 21:40', 'np:读书笔记.txt'), '歌词本.txt': F('文本文档', 1, '2007-04-14 23:05', 'np:歌词本.txt'), '简历.doc': F('Microsoft Word 文档', 24, '2007-05-30 14:11'), '课程表.xls': F('Microsoft Excel 工作表', 18, '2007-02-26 08:50'),
    },
    '我的电脑': {
      '本地磁盘 (C:)': { 'Documents and Settings': { Administrator: { '「开始」菜单': {}, '桌面': 'desktop', '我的文档': {}, '收藏夹': {}, 'Cookies': {} }, 'All Users': {} },
        'Program Files': { 'Internet Explorer': { 'iexplore.exe': F('应用程序', 625, '2006-08-04 12:00', 'app:ie') }, 'Tencent': { QQ: { 'QQ.exe': F('应用程序', 7312, '2007-01-09 19:47', 'app:qq') }, QQGame: { 'QQGame.exe': F('应用程序', 3204, '2007-01-09 19:50', 'app:qqgame') } }, TTPlayer: { 'TTPlayer.exe': F('应用程序', 1068, '2007-03-02 20:14', 'app:ttplayer'), Skins: {}, Lyrics: {} }, Baofeng: { Storm: { 'Storm.exe': F('应用程序', 2812, '2007-05-18 09:41', 'app:baofeng') } }, 'Thunder Network': { Thunder: { 'Thunder.exe': F('应用程序', 4086, '2007-04-21 13:02', 'app:xunlei') } }, KuGou: { 'KuGou.exe': F('应用程序', 5120, '2007-06-07 22:30', 'app:kugou') }, 'Outlook Express': { 'msimn.exe': F('应用程序', 100, '2006-08-04 12:00', 'app:outlook') }, 'Windows Media Player': {}, 'Common Files': {}, 'WinRAR': {} },
        WINDOWS: { system32: { 'calc.exe': F('应用程序', 114, '2006-08-04 12:00', 'app:calc'), 'cmd.exe': F('应用程序', 389, '2006-08-04 12:00', 'app:cmd'), 'notepad.exe': F('应用程序', 66, '2006-08-04 12:00', 'app:notepad'), 'taskmgr.exe': F('应用程序', 1064, '2006-08-04 12:00', 'app:taskmgr'), 'winmine.exe': F('应用程序', 106, '2006-08-04 12:00', 'app:minesweeper'), drivers: {}, config: {} }, Fonts: {}, Web: { Wallpaper: { 'Bliss.bmp': pic('bliss.jpg').slice(0, 3).concat('img:xp/ui/bliss.jpg') } }, Temp: {}, 'explorer.exe': F('应用程序', 1008, '2006-08-04 12:00', 'app:explorer') },
        Games: { 'Counter-Strike 1.6': { 'hl.exe': F('应用程序', 80, '2006-10-01 15:11', 'app:cs'), 'readme.txt': F('文本文档', 1, '2006-10-01 15:11', 'np:readme.txt'), cstrike: {}, valve: {} }, 'GTA Vice City': { 'gta-vc.exe': F('应用程序', 5412, '2006-11-12 10:25', 'app:vc') }, 'Warcraft III': { 'war3.exe': F('应用程序', 440, '2006-07-23 21:55', 'app:war3') }, RA2: { 'ra2.exe': F('应用程序', 1612, '2006-05-14 14:08', 'app:ra2') }, 'Legend of Mir 2': { 'Mir2.exe': F('应用程序', 3040, '2006-03-30 20:36', 'app:mir2') } },
        'AUTOEXEC.BAT': F('MS-DOS 批处理文件', 1, '2006-08-04 12:00', 'np:AUTOEXEC.BAT'), 'boot.ini': F('配置设置', 1, '2006-08-04 12:00', 'np:boot.ini'), 'CONFIG.SYS': F('系统文件', 0, '2006-08-04 12:00'), 'pagefile.sys': F('系统文件', 1572864, '2007-06-30 08:00') },
      '本地磁盘 (D:)': { '下载': { '[迅雷下载]': {} }, '游戏': {}, '音乐': {}, '电影': {}, 'Setup.exe': F('应用程序', 1202, '2007-02-02 12:12') },
      'CD 驱动器 (E:)': 'cd',
      '控制面板': 'control',
    },
    '网上邻居': { '整个网络': 'net', '添加网上邻居': 'net' },
    '回收站': 'recycle',
  };
  const CONTROL = [['显示', '300_32.png', () => WM.open('display')], ['日期和时间', '301_32.png', () => WM.open('datetime')], ['Internet 选项', '288_32.png', () => WM.open('inetcpl')], ['任务栏和「开始」菜单', '299_32.png', () => WM.open('taskbarprops')], ['声音和音频设备', '846_32.png', () => WM.open('sndcpl')], ['鼠标', '300_32.png', () => WM.open('mousecpl')], ['键盘', '300_32.png'], ['添加或删除程序', '358_32.png'], ['打印机和传真', '549_32.png'], ['网络连接', '309_32.png'], ['系统', '676_32.png'], ['用户账户', '546_32.png'], ['文件夹选项', '318_32.png'], ['字体', '318_32.png'], ['管理工具', '300_32.png'], ['电源选项', '310_32.png']];
  const fixIc = n => { try { return n; } catch (e) { return n; } };
  const KEY = p => p.join('\\');
  const deskPath = p => p[0] === '桌面';
  function node(p) { let n = TREE; for (const k of p) { if (!n || typeof n !== 'object' || Array.isArray(n)) return undefined; n = n[k]; } return n; }
  const isDir = n => n && typeof n === 'object' && !Array.isArray(n);
  const ALIAS = { mycomputer: ['我的电脑'], mydocs: ['我的文档'], mypics: ['我的文档', '我的图片'], mymusic: ['我的文档', '我的音乐'], recycle: ['回收站'], control: ['我的电脑', '控制面板'], desktop: ['桌面'], network: ['网上邻居'], search: ['搜索结果'], 'c:': ['我的电脑', '本地磁盘 (C:)'], 'd:': ['我的电脑', '本地磁盘 (D:)'], 'e:': ['我的电脑', 'CD 驱动器 (E:)'] };
  function addrOf(p) {
    if (p[0] === '我的电脑' && p[1]) { const m = /\((.:)\)/.exec(p[1]); if (m) return [m[1].toUpperCase()].concat(p.slice(2)).join('\\') + (p.length === 2 ? '\\' : ''); }
    if (p[0] === '桌面' && p.length === 1) return '桌面';
    return p.join('\\');
  }
  function parseAddr(s) {
    s = s.trim().replace(/\//g, '\\').replace(/\\+$/, ''); if (!s) return null; const low = s.toLowerCase();
    if (ALIAS[low]) return ALIAS[low];
    const m = /^([a-z]):(\\(.*))?$/i.exec(s);
    if (m) { const drv = Object.keys(TREE['我的电脑']).find(k => k.toLowerCase().includes('(' + m[1].toLowerCase() + ':)')); if (!drv) return undefined; const rest = m[3] ? m[3].split('\\') : []; return resolveCase(['我的电脑', drv].concat(rest)); }
    return resolveCase(s.split('\\'));
  }
  function resolveCase(parts) { let n = TREE; const out = []; for (const k of parts) { if (!isDir(n)) return undefined; const key = Object.keys(n).find(x => x.toLowerCase() === k.toLowerCase()); if (!key) return undefined; out.push(key); n = n[key]; } return out; }
  const fileIcon = (name, type, act) => /\.(jpg|jpeg)$/i.test(name) ? 'xp/ico/307_32.png' : /\.mp3$/i.test(name) ? 'xp/ico/550_32.png' : /\.txt$|\.ini$|\.bat$|^hosts$/i.test(name) ? 'xp/ico/327_32.png' : /\.exe$/i.test(name) ? (act && /app:/.test(act) ? appIcon(act.slice(4)) : 'xp/ico/74_32.png') : /\.doc$|\.xls$/i.test(name) ? 'xp/ico/327_32.png' : 'xp/ico/327_32.png';
  const appIcon = id => ({ ie: 'xp/ico/ie.png', ttplayer: 'xp/icons/ttplayer.png', qq: 'xp/icons/qq.png', qqgame: 'xp/icons/qqgame.png', baofeng: 'xp/icons/baofeng.png', xunlei: 'xp/icons/xunlei.png', kugou: 'xp/icons/kugou.png', cs: 'xp/icons/cs.png', vc: 'xp/icons/vc.png', war3: 'xp/icons/war3.png', ra2: 'xp/icons/ra2.png', mir2: 'xp/icons/mir2.png', calc: 'xp/ico/74_32.png', notepad: 'xp/ico/327_32.png', cmd: 'xp/ico/56_32.png', taskmgr: 'xp/ico/669_32.png', minesweeper: 'xp/mine/mine-icon.png', outlook: 'xp/ico/887_32.png', explorer: 'xp/ico/676_32.png' }[id] || 'xp/ico/74_32.png');
  const dtext = (n, k) => k;
  const nowStr = () => { const d = new Date(), p = v => String(v).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`; };

  // 列出某路径下的项目
  function list(p, q) {
    const out = [], n = p[0] === '搜索结果' ? null : node(p), it = [];
    if (p[0] === '搜索结果') {
      const walk = (obj, path) => { if (!isDir(obj)) return; Object.keys(obj).forEach(k => { const v = obj[k], pp = path.concat(k); if (q && k.toLowerCase().includes(q.toLowerCase())) it.push({ name: k, path: pp, v }); if (isDir(v) && path.length < 7) walk(v, pp); }); };
      walk(TREE['我的文档'], ['我的文档']); walk(TREE['我的电脑']['本地磁盘 (C:)'], ['我的电脑', '本地磁盘 (C:)']);
      it.forEach(r => out.push(mk(r.name, r.v, r.path.slice(0, -1).concat(r.name), addrOf(r.path.slice(0, -1)))));
      return out;
    }
    if (p[0] === '桌面' && p.length === 1) {
      WM.deskItems().forEach(d => out.push({ name: d.name, kind: d.app === 'explorer' && !['mycomputer', 'mydocs', 'recycle'].includes(d.id) ? 'dir' : 'file', ic: d.icon, type: d.type, size: d.size || '', date: d.mtime, act: () => WM.openDeskItem(d), path: d.app === 'explorer' ? (d.args.path && ALIAS[d.args.path] ? ALIAS[d.args.path] : ['桌面', d.name]) : null }));
      return out;
    }
    if (p[0] === '桌面' && p.length > 1) { (S.fsx[KEY(p)] || []).forEach(e => out.push(mkx(e, p))); return out; }
    if (isDir(n)) {
      Object.keys(n).forEach(k => out.push(mk(k, n[k], p.concat(k))));
      (S.fsx[KEY(p)] || []).forEach(e => out.push(mkx(e, p)));
    }
    return out;
  }
  function mkx(e, p) { return e.kind === 'dir' ? { name: e.name, kind: 'dir', ic: 'xp/ico/318_32.png', type: '文件夹', size: '', date: e.date, path: p.concat(e.name), user: true } : { name: e.name, kind: 'file', ic: 'xp/ico/327_32.png', type: '文本文档', size: 0, date: e.date, act: () => WM.open('notepad', { id: e.id, name: e.name }), user: true, uid: e.id }; }
  function mk(k, v, path, loc) {
    if (isDir(v)) { const drive = /^(本地磁盘|CD)/.test(k) && path.length === 2; return { name: k, kind: 'dir', ic: drive ? (k.startsWith('CD') ? 'xp/ico/111_32.png' : 'xp/ico/334_32.png') : (k === '我的图片' ? 'xp/ico/307_32.png' : k === '我的音乐' ? 'xp/ico/550_32.png' : 'xp/ico/318_32.png'), type: drive ? (k.startsWith('CD') ? 'CD 驱动器' : '本地磁盘') : '文件夹', size: '', date: '2007-06-30 08:00', path, loc }; }
    if (Array.isArray(v)) { const [type, kb, date, act] = v; return { name: k, kind: 'file', ic: fileIcon(k, type, act), thumb: act.startsWith('img:') ? act.slice(4) : null, type, size: kb, date, act: win => openAct(act, k, win), loc }; }
    if (v === 'cd') return { name: k, kind: 'dir', ic: 'xp/ico/111_32.png', type: 'CD 驱动器', size: '', date: '', path, drive: 'cd' };
    if (v === 'recycle') return { name: k, kind: 'dir', ic: 'xp/icons/recycle.png', type: '系统文件夹', size: '', date: '', path };
    if (v === 'control') return { name: k, kind: 'dir', ic: 'xp/ico/300_32.png', type: '系统文件夹', size: '', date: '', path };
    if (v === 'desktop') return { name: k, kind: 'dir', ic: 'xp/ico/318_32.png', type: '文件夹', size: '', date: '', path: ['桌面'] };
    return { name: k, kind: 'dir', ic: 'xp/ico/693_32.png', type: '系统文件夹', size: '', date: '', path, net: true };
  }
  function openAct(act, name, win) {
    const [t, ...r] = act.split(':'), a = r.join(':');
    if (t === 'np') return WM.open('notepad', { name, text: TXT[a] != null ? TXT[a] : '' });
    if (t === 'app') return WM.open(a, a === 'explorer' ? { path: 'mydocs' } : {});
    if (t === 'img') return WM.open('imgview', { src: a, name });
    WM.alert(name, 'Windows 无法打开此文件：\n' + name + '\n\n要打开此文件，Windows 需要知道是哪个程序创建的。', { kind: 'warn' });
  }

  const css = (() => { const st = document.createElement('style'); st.textContent = `
  .ex { position:absolute; inset:0; display:flex; flex-direction:column; background:#ece9d8; font:12px var(--xpfont); color:#000; }
  .ex .tbar { flex:none; display:flex; align-items:center; height:38px; padding:0 4px; border-bottom:1px solid #d0cfc0; box-shadow:0 1px 0 #fff; }
  .ex .tb { display:flex; align-items:center; height:34px; padding:0 4px; border:1px solid transparent; border-radius:3px; margin-right:1px; }
  .ex .tb:hover:not(.dis) { border-color:#9a9a9a; background:linear-gradient(#fff,#e8e5d6); }
  .ex .tb:active:not(.dis) { background:#d9d6c5; }
  .ex .tb img { width:26px; height:26px; margin-right:4px; } .ex .tb.dis { opacity:.45; } .ex .tb.dis img { filter:grayscale(1); }
  .ex .tsep { width:1px; height:28px; background:#c0bfb0; margin:0 4px; border-right:1px solid #fff; }
  .ex .addr { flex:none; display:flex; align-items:center; height:26px; padding:0 4px; border-bottom:1px solid #d0cfc0; }
  .ex .addr .box { flex:1; display:flex; align-items:center; height:20px; background:#fff; border:1px solid #7f9db9; padding:0 2px; margin:0 6px; }
  .ex .addr input { flex:1; border:0; outline:0; font:12px var(--xpfont); height:16px; background:transparent; }
  .ex .addr .go { display:flex; align-items:center; padding:0 4px; } .ex .addr .go img { width:16px; height:16px; margin-right:3px; }
  .ex .body { flex:1; display:flex; min-height:0; background:#fff; }
  .ex .side { width:200px; flex:none; background:linear-gradient(#7ba2e7,#6375d6); overflow:auto; padding:12px 10px; box-sizing:border-box; }
  .ex .tree { width:200px; flex:none; background:#fff; overflow:auto; border-right:1px solid #aaa; }
  .ex .tree .th { display:flex; align-items:center; height:22px; padding:0 4px; background:#ece9d8; border-bottom:1px solid #aca899; } .ex .tree .th b { flex:1; font-weight:400; } .ex .tree .th .x { width:14px; text-align:center; }
  .ex .tn { display:flex; align-items:center; height:18px; white-space:nowrap; } .ex .tn .pm { width:9px; height:9px; border:1px solid #919b9c; margin:0 3px; font:9px/7px Tahoma; text-align:center; flex:none; background:#fff; } .ex .tn img { width:16px; height:16px; margin-right:3px; } .ex .tn span.l { padding:1px 2px; } .ex .tn.on span.l { background:#316ac5; color:#fff; }
  .ex .pane { margin-bottom:12px; border-radius:6px 6px 0 0; overflow:hidden; background:#d6dff7; }
  .ex .pane .ph { height:23px; display:flex; align-items:center; padding:0 6px 0 10px; background:linear-gradient(90deg,#fff,#c6d3f7); color:#215dc6; font-weight:700; }
  .ex .pane .ph b { flex:1; } .ex .pane .ph .ar { width:17px; height:17px; border-radius:50%; background:#fff; border:1px solid #fff; color:#215dc6; text-align:center; font:700 9px/17px Tahoma; }
  .ex .pane .pb { padding:6px 10px 6px 10px; background:#d6dff7; } .ex .pane.col .pb { display:none; }
  .ex .pane .lk { display:flex; align-items:center; padding:2px 0; color:#215dc6; } .ex .pane .lk:hover { color:#428eff; text-decoration:underline; } .ex .pane .lk img { width:16px; height:16px; margin-right:5px; flex:none; } .ex .pane .lk.dis { color:#8a9ac8; pointer-events:none; }
  .ex .pane .pb .dn { font-weight:700; } .ex .pane .pb .dd { color:#444; margin-top:2px; line-height:15px; }
  .ex .main { flex:1; min-width:0; position:relative; overflow:auto; background:#fff; }
  .ex .main.icons { padding:6px 8px; display:flex; flex-wrap:wrap; align-content:flex-start; }
  .ex .grp { width:100%; font:700 12px var(--xpfont); color:#0c327d; border-bottom:1px solid #aab8e8; padding:8px 0 3px 4px; margin-bottom:6px; }
  .ex .it { width:78px; min-height:66px; margin:0 2px 8px; text-align:center; padding:2px 0; box-sizing:border-box; }
  .ex .it img { width:32px; height:32px; display:block; margin:0 auto 3px; } .ex .it img.th { width:48px; height:48px; object-fit:cover; border:2px solid #fff; box-shadow:0 0 0 1px #aaa,1px 1px 3px rgba(0,0,0,.4); box-sizing:border-box; width:50px; height:50px; }
  .ex .it span { display:inline-block; max-width:76px; padding:0 2px; word-break:break-all; line-height:14px; }
  .ex .it.sel span { background:#316ac5; color:#fff; } .ex .it.sel img { opacity:.7; filter:sepia(.2) hue-rotate(190deg) saturate(2); }
  .ex .main.list .it, .ex .main.small .it { display:flex; width:200px; min-height:0; margin:0; text-align:left; align-items:center; height:18px; padding:0 2px; }
  .ex .main.list .it img, .ex .main.small .it img { width:16px; height:16px; margin:0 4px 0 0; } .ex .main.list .it span { max-width:170px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .ex .main.list { padding:6px 8px; display:flex; flex-direction:column; flex-wrap:wrap; align-content:flex-start; }
  .ex .main.tiles .it { display:flex; width:190px; min-height:0; text-align:left; height:46px; align-items:center; } .ex .main.tiles .it img { margin:0 6px 0 0; } .ex .main.tiles .it span { max-width:140px; }
  .ex .main.tiles { padding:8px; display:flex; flex-wrap:wrap; align-content:flex-start; }
  .ex table.dt { border-collapse:collapse; width:100%; } .ex table.dt th { background:linear-gradient(#fff,#ece9d8); border:1px solid #d0cfc0; border-top:0; border-left:0; font-weight:400; text-align:left; padding:2px 6px; height:18px; position:sticky; top:0; }
  .ex table.dt td { height:18px; padding:0 6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px; } .ex table.dt td img { width:16px; height:16px; vertical-align:-4px; margin-right:4px; } .ex table.dt tr.sel td { background:#316ac5; color:#fff; }
  .ex .status { flex:none; height:20px; display:flex; align-items:center; border-top:1px solid #fff; background:#ece9d8; padding:0 6px; } .ex .status div { padding:0 8px; border-right:1px solid #aca899; height:16px; line-height:16px; }
  .ex .empty { color:#777; padding:30px; text-align:center; }
  .ex .sform { padding:8px 4px; line-height:22px; } .ex .sform input { width:150px; }
  .iv { position:absolute; inset:0; background:#fff; display:flex; flex-direction:column; } .iv .vi { flex:1; display:flex; align-items:center; justify-content:center; overflow:hidden; background:#fff; } .iv .vi img { max-width:100%; max-height:100%; } .iv .vb { height:38px; flex:none; background:linear-gradient(#f4f3ee,#dad8c9); border-top:1px solid #aaa; display:flex; align-items:center; justify-content:center; gap:6px; }
  `; document.head.appendChild(st); })();

  const NAV = [['后退', 'back.png', 'back'], ['前进', 'forward.png', 'fwd']];
  function openExplorer(a) {
    a = a || {};
    let start = a.path && !Array.isArray(a.path) ? (ALIAS[a.path] || parseAddr(a.path) || (String(a.path).startsWith('desk:') ? ['桌面', (WM.deskItems().find(d => d.id === a.path.slice(5)) || {}).name || '新建文件夹'] : ['我的文档'])) : ['我的文档'];
    if (Array.isArray(a.path)) start = a.path;
    const st = { path: start, hist: [], fwd: [], sel: new Set(), view: 'icons', treeOn: false, q: '', sort: 'name', sortDir: 1, col: {}, exp: new Set(['我的电脑', '我的文档']) };
    let w; const main = h('div', { class: 'main icons' }), side = h('div', { class: 'side' }), tree = h('div', { class: 'tree', style: 'display:none' }), status = h('div', { class: 'status' });
    const addrIn = h('input', { spellcheck: false }), addrIc = h('img', { src: 'xp/ico/318_16.png', style: 'width:16px;height:16px' });
    let items = [];
    const title = p => p[0] === '搜索结果' ? '搜索结果' : p[0] === '我的电脑' && p.length === 2 ? p[1] : (p[p.length - 1] === '桌面' ? '桌面' : p[p.length - 1]);
    const icon16 = p => p[0] === '我的电脑' && p.length === 1 ? 'xp/ico/676_16.png' : p[0] === '回收站' ? 'xp/ico/360_16.png' : p[0] === '我的文档' && p.length === 1 ? 'xp/ico/308_16.png' : p[0] === '我的电脑' && p.length === 2 ? (p[1].startsWith('CD') ? 'xp/ico/111_16.png' : p[1].startsWith('控制') ? 'xp/ico/300_16.png' : 'xp/ico/334_16.png') : p[0] === '搜索结果' ? 'xp/ico/299_16.png' : 'xp/ico/318_16.png';
    const navTo = (p, push = true) => {
      if (p[0] === '我的电脑' && p[1] && TREE['我的电脑'][p[1]] === 'cd') return WM.alert('E:\\', 'E:\\ 无法访问。\n\n设备尚未就绪。', { kind: 'error', buttons: [['重试(R)'], ['取消']] });
      if (push) { st.hist.push(st.path); st.fwd = []; }
      st.path = p; st.sel.clear(); render();
    };
    const go = a => { if (a === 'back' && st.hist.length) { st.fwd.push(st.path); st.path = st.hist.pop(); st.sel.clear(); render(); } else if (a === 'fwd' && st.fwd.length) { st.hist.push(st.path); st.path = st.fwd.pop(); st.sel.clear(); render(); } else if (a === 'up') { const p = st.path; if (p.length > 1 && p[0] !== '搜索结果') navTo(p.slice(0, -1)); else if (p[0] !== '桌面' && p[0] !== '搜索结果' && p.length === 1 && p[0] !== '桌面') navTo(['桌面']); } };
    const upDis = () => st.path.length === 1 && st.path[0] === '桌面';
    const tbtn = (txt, ic, f, extra) => h('div', { class: 'tb' + (extra || ''), onclick: f }, [h('img', { src: 'xp/ico/' + ic }), txt && h('span', { text: txt })]);
    const mkToolbar = () => {
      const t = h('div', { class: 'tbar' });
      const b = tbtn('后退', 'back.png', () => go('back')), f = tbtn('', 'forward.png', () => go('fwd')), u = tbtn('', 'up.png', () => go('up'));
      b.dis = () => !st.hist.length; f.dis = () => !st.fwd.length; u.dis = upDis;
      t.append(b, f, u, h('div', { class: 'tsep' }), tbtn('搜索', '299_32.png', () => navTo(['搜索结果'])), tbtn('文件夹', '318_32.png', () => { st.treeOn = !st.treeOn; render(); }), h('div', { class: 'tsep' }),
        h('div', { class: 'tb', onclick: e => { const r = e.currentTarget.getBoundingClientRect(), rr = WM.root.getBoundingClientRect(), k = rr.width / WM.DW; viewMenu((r.left - rr.left) / k, (r.bottom - rr.top) / k); } }, [h('img', { src: 'xp/ico/676_32.png' }), h('span', { text: '查看 ▾' })]));
      t.btns = [b, f, u]; return t;
    };
    const VIEWS = [['缩略图(H)', 'thumbs'], ['平铺(S)', 'tiles'], ['图标(N)', 'icons'], ['列表(L)', 'list'], ['详细信息(D)', 'details']];
    const viewMenu = (x, y) => WM.menu(VIEWS.map(([t, v]) => ({ t, radio: true, chk: st.view === v, on: () => { st.view = v; render(); } })), x, y);
    const toolbar = mkToolbar();
    const doRefresh = () => { main.style.visibility = 'hidden'; setTimeout(() => { render(); main.style.visibility = ''; }, 90); };
    const mbDefs = [
      { t: '文件(F)', items: () => [{ t: '打开(O)', bold: true, dis: !st.sel.size, on: openSel }, { t: '新建(N)', sub: newMenu() }, '-', { t: '删除(D)', dis: !canDel(), on: delSel }, { t: '重命名(M)', dis: true }, { t: '属性(R)', dis: !st.sel.size, on: propsSel }, '-', { t: '关闭(C)', on: () => w.close() }] },
      { t: '编辑(E)', items: () => [{ t: '撤消(U)', dis: true }, '-', { t: '全选(A)', key: 'Ctrl+A', on: () => { items.forEach(i => st.sel.add(i.name)); render(true); } }, { t: '反向选择(I)', on: () => { const s = new Set(st.sel); st.sel.clear(); items.forEach(i => !s.has(i.name) && st.sel.add(i.name)); render(true); } }] },
      { t: '查看(V)', items: () => [{ t: '工具栏(T)', chk: true, dis: true }, { t: '状态栏(B)', chk: true, dis: true }, '-'].concat(VIEWS.map(([t, v]) => ({ t, radio: true, chk: st.view === v, on: () => { st.view = v; render(); } }))).concat(['-', { t: '转到(G)', sub: [{ t: '后退(B)', dis: !st.hist.length, on: () => go('back') }, { t: '前进(F)', dis: !st.fwd.length, on: () => go('fwd') }, { t: '上一级文件夹(U)', dis: upDis(), on: () => go('up') }] }, { t: '刷新(R)', key: 'F5', on: doRefresh }]) },
      { t: '收藏(A)', items: () => [{ t: '添加到收藏夹(A)...', dis: true }, '-', { t: '我的文档', icon: 'xp/ico/308_16.png', on: () => navTo(['我的文档']) }, { t: '我的电脑', icon: 'xp/ico/676_16.png', on: () => navTo(['我的电脑']) }] },
      { t: '工具(T)', items: () => [{ t: '映射网络驱动器(N)...', dis: true }, '-', { t: '文件夹选项(O)...', on: () => WM.alert('文件夹选项', '常规 / 查看 / 文件类型 / 脱机文件\n\n（演示环境：设置不会保存）', { kind: 'info' }) }] },
      { t: '帮助(H)', items: () => [{ t: '帮助和支持中心(H)', on: () => WM.open('help') }, '-', { t: '关于 Windows(A)', on: () => WM.alert('关于 Windows', 'Microsoft (R) Windows (R) XP\n版本 2002 Service Pack 3', { kind: 'info' }) }] },
    ];
    const mbar = WM.menubar(mbDefs);
    const addr = h('div', { class: 'addr' }, [h('span', { text: '地址(D)', style: 'color:#555' }), h('div', { class: 'box' }, [addrIc, addrIn, h('img', { src: 'xp/ico/dropdown.png', style: 'width:15px;height:17px' })]), h('div', { class: 'go', onclick: () => gotoAddr() }, [h('img', { src: 'xp/ico/back.png', style: 'transform:rotate(180deg)' }), h('span', { text: '转到' })])]);
    function gotoAddr() { const v = addrIn.value; const p = parseAddr(v); if (!p || (!node(p) && !['桌面', '回收站', '搜索结果'].includes(p[0]))) { if (/^https?:|^www\./i.test(v.trim())) return WM.open('ie', { url: /^www/i.test(v) ? 'http://' + v : v }); return WM.alert('Windows 资源管理器', '找不到“' + v + '”。请检查拼写是否正确，然后重试。', { kind: 'error' }); } navTo(p); }
    addrIn.addEventListener('keydown', e => { if (e.key === 'Enter') gotoAddr(); e.stopPropagation(); });
    const canDel = () => st.path[0] === '回收站' ? false : [...st.sel].some(n => (items.find(i => i.name === n) || {}).user);
    const delSel = () => { const k = KEY(st.path), arr = S.fsx[k] || []; WM.confirm('确认文件删除', '确实要删除选定的项目吗？', () => { S.fsx[k] = arr.filter(e => !st.sel.has(e.name)); WM.save(); st.sel.clear(); render(); }); };
    const propsSel = () => { const it = items.find(i => st.sel.has(i.name)); if (!it) return; WM.tabsDialog({ id: 'xp-' + it.name, title: it.name + ' 属性', icon: it.ic.replace('_32', '_16'), w: 360, h: 400, pages: { '常规': () => h('div', {}, [h('div', { style: 'display:flex;align-items:center;margin-bottom:10px' }, [h('img', { src: it.ic, style: 'width:32px;height:32px;margin-right:12px' }), h('input', { class: 'xinput', value: it.name, readonly: true, style: 'flex:1' })]), h('div', { style: 'border-top:1px solid #d0d0bf;padding-top:8px;line-height:22px' }, [['类型：', it.type], ['位置：', addrOf(st.path)], ['大小：', it.size === '' ? '' : it.size + ' KB (' + (it.size * 1024).toLocaleString() + ' 字节)'], ['修改时间：', it.date]].map(([a_, b_]) => h('div', { style: 'display:flex' }, [h('div', { style: 'width:70px', text: a_ }), h('div', { text: b_ })])))]) } }); };
    const openIt = it => {
      if (!it) return;
      if (it.recy != null) return;
      if (it.kind === 'dir') { if (it.path && it.path[0] === '桌面' && it.path.length === 2 && !node(it.path) && !S.fsx[KEY(it.path)]) { } return navTo(it.path); }
      if (it.net) return;
      it.act && it.act(w);
    };
    const openSel = () => { const l = items.filter(i => st.sel.has(i.name)); l.forEach(openIt); };
    function newMenu() { return [{ t: '文件夹(F)', icon: 'xp/ico/318_16.png', on: () => mkNew('dir') }, { t: '文本文档', icon: 'xp/ico/327_16.png', on: () => mkNew('text') }]; }
    function mkNew(kind) {
      if (['我的电脑', '回收站', '搜索结果', '网上邻居'].includes(st.path[0]) && st.path.length < 3) return WM.alert('Windows 资源管理器', '无法在此位置创建项目。', { kind: 'error' });
      const base = kind === 'dir' ? '新建文件夹' : '新建 文本文档.txt'; let nm = base, n = 2; const names = items.map(i => i.name); while (names.includes(nm)) nm = base.replace(/(\.[a-z]+)?$/, ' (' + n++ + ')$1');
      WM.prompt('重命名', '请输入名称：', nm, v => { v = (v || '').trim(); if (!v) return; const k = KEY(st.path); (S.fsx[k] = S.fsx[k] || []).push({ kind, name: v, date: nowStr(), id: 'x' + Date.now().toString(36) }); WM.save(); render(); });
    }

    // ---- 任务窗格 ----
    const pane = (title, links, col) => { const p = h('div', { class: 'pane' + (col ? ' col' : '') }, [h('div', { class: 'ph', onclick: () => p.classList.toggle('col') }, [h('b', { text: title }), h('div', { class: 'ar', text: '⌃' })]), h('div', { class: 'pb' }, links)]); return p; };
    const lk = (t, ic, f, dis) => h('div', { class: 'lk' + (dis ? ' dis' : ''), onclick: f }, [h('img', { src: 'xp/ico/' + ic }), h('span', { text: t })]);
    const others = () => [['我的电脑', '676_16.png', ['我的电脑']], ['我的文档', '308_16.png', ['我的文档']], ['共享文档', '318_16.png', ['我的文档']], ['网上邻居', '693_16.png', ['网上邻居']], ['控制面板', '300_16.png', ['我的电脑', '控制面板']]].filter(o => KEY(o[2]) !== KEY(st.path)).map(o => lk(o[0], o[1], () => navTo(o[2])));
    function renderSide() {
      side.innerHTML = ''; const p = st.path, sel = items.filter(i => st.sel.has(i.name));
      if (p[0] === '搜索结果') {
        const inp = h('input', { class: 'xinput', value: st.q, style: 'width:150px' }); inp.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Enter') { st.q = inp.value; render(); } });
        side.appendChild(h('div', { class: 'pane' }, [h('div', { class: 'ph', style: 'background:#7a95d4' }, [h('b', { text: '搜索助理' })]), h('div', { class: 'pb sform' }, [h('div', { text: '全部或部分文件名：' }), inp, h('div', { style: 'text-align:right' }, [h('button', { class: 'xbtn', text: '搜索', onclick: () => { st.q = inp.value; render(); } })])])])); return;
      }
      if (p[0] === '回收站') {
        side.appendChild(pane('回收站任务', [lk('清空回收站', '360_16.png', () => WM.emptyTrash(), !S.trash.length), lk(sel.length ? '还原此项目' : '还原所有项目', '360_16.png', () => { const idx = sel.length ? S.trash.map((t, i) => st.sel.has(t.name) ? i : -1).filter(i => i >= 0).reverse() : S.trash.map((t, i) => i).reverse(); idx.forEach(i => WM.restoreTrash(i)); }, !S.trash.length)]));
      } else if (p[0] === '我的电脑' && p.length === 1) {
        side.appendChild(pane('系统任务', [lk('查看系统信息', '747_16.png', () => WM.open('help')), lk('添加/删除程序', '302_16.png', () => WM.alert('添加或删除程序', '正在加载当前安装的程序列表…\n\n（演示环境不可用）', { kind: 'info' })), lk('更改一个设置', '300_16.png', () => navTo(['我的电脑', '控制面板']))]));
      } else if (p[0] === '我的电脑' && p[1] === '控制面板') {
        side.appendChild(pane('控制面板', [lk('切换到分类视图', '300_16.png', () => WM.open('control')), lk('另请参阅', '747_16.png', () => WM.open('help'))]));
      } else {
        side.appendChild(pane('文件和文件夹任务', [lk('创建一个新文件夹', '318_16.png', () => mkNew('dir')), lk('将这个文件夹发布到 Web', '693_16.png', () => {}, true), lk('共享此文件夹', '693_16.png', () => {}, true)].concat(canDel() ? [lk('删除所选项目', '897_16.png', delSel)] : [])));
      }
      side.appendChild(pane('其它位置', others())); 
      const dn = sel.length === 1 ? sel[0] : null;
      side.appendChild(pane('详细信息', [h('div', { class: 'dn', text: dn ? dn.name : title(p) }), h('div', { class: 'dd', text: dn ? dn.type + (dn.date ? '\n修改日期: ' + dn.date : '') : (p[0] === '回收站' ? '系统文件夹' : '文件夹') }), sel.length > 1 ? h('div', { class: 'dd', text: '选定了 ' + sel.length + ' 个对象' }) : null]));
    }
    function buildTree() {
      tree.innerHTML = ''; tree.appendChild(h('div', { class: 'th' }, [h('b', { text: '文件夹' }), h('div', { class: 'x', text: '×', onclick: () => { st.treeOn = false; render(); } })]));
      const row = (name, p, depth, ic, hasKids) => { const key = KEY(p), open = st.exp.has(key); const r = h('div', { class: 'tn' + (KEY(p) === KEY(st.path) ? ' on' : ''), style: `padding-left:${depth * 14}px` }, [hasKids ? h('div', { class: 'pm', text: open ? '-' : '+', onclick: e => { e.stopPropagation(); open ? st.exp.delete(key) : st.exp.add(key); buildTree(); } }) : h('div', { style: 'width:15px;flex:none' }), h('img', { src: ic }), h('span', { class: 'l', text: name })]); r.addEventListener('click', () => navTo(p)); tree.appendChild(r); if (open && hasKids) kids(p, depth + 1); };
      const kids = (p, d) => { const n = node(p); if (!isDir(n)) return; Object.keys(n).forEach(k => { const v = n[k]; if (isDir(v) || v === 'recycle' || v === 'control') { const pp = p.concat(k); const it = mk(k, v, pp); row(k, pp, d, it.ic.replace('_32', '_16').replace('xp/icons/recycle.png', 'xp/ico/360_16.png'), isDir(v) && Object.values(v).some(x => isDir(x))); } }); };
      row('桌面', ['桌面'], 0, 'xp/ico/318_16.png', false);
      [['我的文档', 'xp/ico/308_16.png'], ['我的电脑', 'xp/ico/676_16.png'], ['网上邻居', 'xp/ico/693_16.png'], ['回收站', 'xp/ico/360_16.png']].forEach(([n, ic]) => row(n, [n], 1, ic, n !== '回收站' && n !== '网上邻居'));
    }
    const sortFn = (a, b) => { if (a.kind !== b.kind) return a.kind === 'dir' ? -1 : 1; const k = st.sort; let r; if (k === 'size') r = (+a.size || 0) - (+b.size || 0); else if (k === 'type') r = a.type.localeCompare(b.type); else if (k === 'date') r = String(a.date).localeCompare(String(b.date)); else r = a.name.localeCompare(b.name, 'zh'); return r * st.sortDir; };
    const itemMenu = (e, it) => { if (!st.sel.has(it.name)) { st.sel.clear(); st.sel.add(it.name); render(true); }
      if (st.path[0] === '回收站') return WM.ctx(e, [{ t: '还原(E)', bold: true, on: () => { const i = S.trash.findIndex(t => t.name === it.name); i >= 0 && WM.restoreTrash(i); } }, '-', { t: '剪切(T)', dis: true }, '-', { t: '删除(D)', on: () => WM.emptyTrash() }, '-', { t: '属性(R)', on: propsSel }]);
      WM.ctx(e, [{ t: '打开(O)', bold: true, on: openSel }].concat(it.kind === 'file' && /\.txt$/.test(it.name) ? [{ t: '编辑(E)', on: openSel }] : []).concat(['-', { t: '发送到(N)', sub: [{ t: '桌面快捷方式', icon: 'xp/ico/309_16.png', on: () => {} }, { t: '我的文档', icon: 'xp/ico/308_16.png', on: () => {} }] }, '-', { t: '剪切(T)', dis: true }, { t: '复制(C)', dis: true }, '-', { t: '创建快捷方式(S)', dis: true }, { t: '删除(D)', dis: !it.user, on: delSel }, { t: '重命名(M)', dis: true }, '-', { t: '属性(R)', on: propsSel }])); };
    const bgMenu = e => WM.ctx(e, [{ t: '查看(V)', sub: VIEWS.map(([t, v]) => ({ t, radio: true, chk: st.view === v, on: () => { st.view = v; render(); } })) }, { t: '排列图标(I)', sub: [['名称(N)', 'name'], ['大小(S)', 'size'], ['类型(T)', 'type'], ['修改时间(M)', 'date']].map(([t, k]) => ({ t, radio: true, chk: st.sort === k, on: () => { st.sort = k; st.sortDir = 1; render(); } })) }, '-', { t: '刷新(E)', on: doRefresh }, '-', { t: '粘贴(P)', dis: true }, '-', { t: '新建(W)', sub: newMenu() }, '-', { t: '属性(R)', on: () => WM.alert(title(st.path) + ' 属性', '位置: ' + addrOf(st.path) + '\n包含: ' + items.length + ' 个对象', { kind: 'info' }) }]);
    function render(keep) {
      const p = st.path, isRecy = p[0] === '回收站', isCtl = p[0] === '我的电脑' && p[1] === '控制面板' && p.length === 2, isMyc = p[0] === '我的电脑' && p.length === 1;
      if (isRecy) items = S.trash.map((t, i) => ({ name: t.name, kind: 'file', ic: t.icon, type: t.type, size: '', date: t.date, recy: i, from: t.from }));
      else if (isCtl) items = CONTROL.map(c => ({ name: c[0], kind: 'file', ic: 'xp/ico/' + c[1], type: '系统文件夹', size: '', date: '', act: c[2] || (() => WM.alert(c[0], '“' + c[0] + '”在演示环境中不可用。', { kind: 'info' })) }));
      else items = list(p, st.q);
      if (isMyc) items = Object.keys(TREE['我的电脑']).map(k => mk(k, TREE['我的电脑'][k], ['我的电脑', k]));
      items.sort(sortFn);
      w.setTitle(title(p)); addrIn.value = addrOf(p); addrIc.src = icon16(p); w.icon = icon16(p); const wi = w.el.querySelector('.xpw-ico'); wi && (wi.src = w.icon); w.tb && w.tb.querySelector('img') && (w.tb.querySelector('img').src = w.icon);
      toolbar.btns.forEach(b => b.classList.toggle('dis', b.dis()));
      tree.style.display = st.treeOn ? '' : 'none'; side.style.display = st.treeOn ? 'none' : ''; if (st.treeOn) buildTree(); else renderSide();
      const v = st.view; main.className = 'main ' + (v === 'thumbs' ? 'icons' : v); main.innerHTML = '';
      const selFn = (it, e) => { if (e.ctrlKey) { st.sel.has(it.name) ? st.sel.delete(it.name) : st.sel.add(it.name); } else { st.sel.clear(); st.sel.add(it.name); } render(true); };
      if (v === 'details') {
        const cols = isRecy ? [['名称', 'name'], ['原位置', 'from'], ['删除日期', 'date'], ['类型', 'type']] : [['名称', 'name'], ['大小', 'size'], ['类型', 'type'], ['修改日期', 'date']];
        const t = h('table', { class: 'dt' }, [h('tr', {}, cols.map(c => h('th', { text: c[0], onclick: () => { st.sortDir = st.sort === c[1] ? -st.sortDir : 1; st.sort = c[1]; render(); } })))]);
        items.forEach(it => { const tr = h('tr', { class: st.sel.has(it.name) ? 'sel' : '' }, cols.map((c, i) => h('td', i === 0 ? { html: `<img src="${it.ic.replace('_32', '_16')}">${esc(it.name)}` } : { text: c[1] === 'size' ? (it.size === '' ? '' : (+it.size).toLocaleString('zh-CN') + ' KB') : c[1] === 'from' ? it.from : it[c[1]] || '', style: c[1] === 'size' ? 'text-align:right' : '' }))); tr.addEventListener('pointerdown', e => { if (e.button === 0) selFn(it, e); else if (!st.sel.has(it.name)) selFn(it, e); }); tr.addEventListener('dblclick', () => openIt(it)); tr.addEventListener('contextmenu', e => itemMenu(e, it)); t.appendChild(tr); });
        main.appendChild(t);
      } else {
        const mkIt = it => { const th = v === 'thumbs' && it.thumb; const e = h('div', { class: 'it' + (st.sel.has(it.name) ? ' sel' : ''), title: it.name }, [h('img', { src: th ? it.thumb : (v === 'list' ? it.ic.replace('_32', '_16') : it.ic), class: th ? 'th' : '', draggable: 'false' }), h('span', { text: it.name })]); e.addEventListener('pointerdown', ev => { ev.stopPropagation(); if (ev.button === 0) selFn(it, ev); else if (!st.sel.has(it.name)) selFn(it, ev); }); e.addEventListener('dblclick', () => openIt(it)); e.addEventListener('contextmenu', ev => itemMenu(ev, it)); return e; };
        if (isMyc) { [['硬盘', i => i.type === '本地磁盘'], ['有可移动存储的设备', i => i.type === 'CD 驱动器'], ['其它', i => !['本地磁盘', 'CD 驱动器'].includes(i.type)]].forEach(([g, f]) => { const l = items.filter(f); if (!l.length) return; main.appendChild(h('div', { class: 'grp', text: g })); l.forEach(i => main.appendChild(mkIt(i))); }); }
        else items.forEach(i => main.appendChild(mkIt(i)));
        if (!items.length) main.appendChild(h('div', { class: 'empty', text: isRecy ? '回收站是空的。' : p[0] === '搜索结果' ? (st.q ? '没有找到“' + st.q + '”。' : '请在左侧输入要搜索的文件名。') : '此文件夹为空。' }));
      }
      const sel = items.filter(i => st.sel.has(i.name)); const tot = sel.reduce((s, i) => s + (+i.size || 0), 0);
      status.innerHTML = ''; status.append(h('div', { text: sel.length ? '选定了 ' + sel.length + ' 个对象' : items.length + ' 个对象' }), h('div', { text: sel.length && tot ? (tot / 1024 < 1 ? tot + ' KB' : (tot / 1024).toFixed(1) + ' MB') : '', style: 'min-width:60px' }), h('div', { text: isMyc ? '我的电脑' : '我的电脑', style: 'margin-left:auto;border:0' }));
    }
    main.addEventListener('pointerdown', e => { if (e.button === 0 && e.target === main && st.sel.size) { st.sel.clear(); render(true); } });
    main.addEventListener('contextmenu', e => { if (e.target === main || e.target.classList.contains('empty') || e.target.classList.contains('grp')) bgMenu(e); });
    main.tabIndex = 0; main.style.outline = 'none';
    main.addEventListener('keydown', e => { if (e.key === 'F5') { e.preventDefault(); doRefresh(); } else if (e.key === 'Backspace') { e.preventDefault(); go('up'); } else if (e.key === 'Enter') openSel(); else if (e.key === 'Delete' && canDel()) delSel(); else if ((e.ctrlKey || e.metaKey) && e.key === 'a') { e.preventDefault(); items.forEach(i => st.sel.add(i.name)); render(true); } });
    const el = h('div', { class: 'ex' }, [mbar, toolbar, addr, h('div', { class: 'body' }, [side, tree, main]), status]);
    const onTrash = () => { if (st.path[0] === '回收站' && !w.closed) render(true); }; document.addEventListener('trashchange', onTrash);
    const onRef = () => { if (!w.closed && st.path[0] === '桌面') render(true); }; document.addEventListener('deskrefresh', onRef);
    w = WM.create({ id: a.multi === false ? 'explorer' : undefined, title: '我的文档', icon: 'xp/ico/308_16.png', w: 700, h: 480, minW: 380, minH: 240, content: () => el, onclose: () => { document.removeEventListener('trashchange', onTrash); document.removeEventListener('deskrefresh', onRef); } });
    if (st.view === 'icons' && a.view) st.view = a.view;
    render(); return w;
  }
  WM.register('explorer', { open: openExplorer });

  // ---- 图片查看器 ----
  WM.register('imgview', { open: a => WM.create({ title: a.name + ' - Windows 图片和传真查看器', icon: 'xp/ico/307_16.png', w: 620, h: 460, minW: 300, minH: 200, content: () => h('div', { class: 'iv' }, [h('div', { class: 'vi' }, [h('img', { src: a.src })]), h('div', { class: 'vb' }, ['上一张', '下一张', '放大', '缩小', '旋转'].map(t => h('button', { class: 'xbtn', text: t, style: 'min-width:50px' })))]) }) });
})();
