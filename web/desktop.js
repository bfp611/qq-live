// ?desk=xp：桌面图标（选择/框选/拖动/重命名/删除/排序/新建）、桌面右键菜单、刷新、开始菜单、任务栏、托盘、接管 QQ/千千静听窗口
(function () {
  if (!window.WM || !WM.ready) return;
  const { root, DW, DH, TB, h, esc, toRoot, ICO, track } = WM;
  const $ = id => document.getElementById(id);
  const FONT = 'var(--xpfont)';

  // ================= 持久化 =================
  const LS = 'qqlive.desk.v2';
  let S = { pos: {}, extra: [], removed: [], names: {}, wall: 'xp/ui/bliss.jpg', wallMode: 'stretch', bg: '#245edb', auto: false, grid: true, hide: false, trash: [], texts: {}, sort: '', hideSys: {} };
  try { Object.assign(S, JSON.parse(localStorage.getItem(LS) || '{}')); } catch (e) {}
  const save = () => { try { localStorage.setItem(LS, JSON.stringify(S)); } catch (e) {} };
  WM.S = S; WM.save = save;

  // ================= 桌面项目 =================
  const D = (id, name, icon, app, type, size, mtime, args) => ({ id, name, icon: 'xp/icons/' + icon + '.png', app, type, size, mtime, args: args || {} });
  const DEFAULT = [
    D('mycomputer', '我的电脑', 'mycomputer', 'explorer', '系统文件夹', 0, '2006-08-11 12:03', { path: 'mycomputer' }),
    D('mydocs', '我的文档', 'mydocs', 'explorer', '系统文件夹', 0, '2006-08-11 12:03', { path: 'mydocs' }),
    D('recycle', '回收站', 'recycle', 'explorer', '系统文件夹', 0, '2006-08-11 12:03', { path: 'recycle' }),
    D('ie', 'Internet Explorer', 'ie', 'ie', '快捷方式', 1, '2006-08-11 12:03'),
    D('ttplayer', '千千静听', 'ttplayer', 'ttplayer', '快捷方式', 2, '2007-03-02 20:14'),
    D('baofeng', '暴风影音', 'baofeng', 'baofeng', '快捷方式', 2, '2007-05-18 09:41'),
    D('kugou', '酷狗音乐', 'kugou', 'kugou', '快捷方式', 2, '2007-06-07 22:30'),
    D('xunlei', '迅雷', 'xunlei', 'xunlei', '快捷方式', 2, '2007-04-21 13:02'),
    D('qq', '腾讯QQ', 'qq', 'qq', '快捷方式', 2, '2006-12-24 18:20'),
    D('qqgame', 'QQ游戏', 'qqgame', 'qqgame', '快捷方式', 2, '2007-01-09 19:47'),
    D('cs', 'Counter-Strike 1.6', 'cs', 'cs', '快捷方式', 2, '2006-10-01 15:11'),
    D('vc', '侠盗猎车手 罪恶都市', 'vc', 'vc', '快捷方式', 2, '2006-11-12 10:25'),
    D('war3', '魔兽争霸III', 'war3', 'war3', '快捷方式', 2, '2006-07-23 21:55'),
    D('ra2', '红色警戒2', 'ra2', 'ra2', '快捷方式', 2, '2006-05-14 14:08'),
    D('mir2', '热血传奇', 'mir2', 'mir2', '快捷方式', 2, '2006-03-30 20:36'),
    D('audition', '劲舞团', 'audition', 'audition', '快捷方式', 2, '2007-02-14 16:49'),
  ];
  const KINDS = {
    folder: { icon: 'xp/ico/318_32.png', type: '文件夹', base: '新建文件夹', app: 'explorer' },
    link: { icon: 'xp/ico/309_32.png', type: '快捷方式', base: '新建快捷方式', app: 'link' },
    brief: { icon: 'xp/ico/57_32.png', type: '公文包', base: '新建公文包', app: 'explorer' },
    bmp: { icon: 'xp/ico/680_32.png', type: 'BMP 图像', base: '新建 BMP 图像.bmp', app: 'bmp' },
    text: { icon: 'xp/ico/327_32.png', type: '文本文档', base: '新建 文本文档.txt', app: 'notepad' },
  };
  const items = () => DEFAULT.filter(d => !S.removed.includes(d.id) && !S.hideSys[d.id]).map(d => Object.assign({}, d, { name: S.names[d.id] || d.name }))
    .concat(S.extra.map(e => Object.assign({}, KINDS[e.kind], e, { args: { id: e.id, name: e.name, kind: e.kind, path: 'desk:' + e.id }, size: e.kind === 'text' ? 0 : 0, mtime: e.mtime || '2007-06-30 08:00' })));
  const find = id => items().find(i => i.id === id);
  WM.deskItems = items;

  // ================= 壁纸 =================
  function applyWall() {
    const m = S.wallMode, f = S.wall;
    root.style.backgroundColor = S.bg;
    if (!f) { root.style.backgroundImage = 'none'; return; }
    root.style.backgroundImage = `url(${f})`;
    if (m === 'tile') { root.style.backgroundSize = 'auto'; root.style.backgroundRepeat = 'repeat'; root.style.backgroundPosition = '0 0'; }
    else if (m === 'center') { root.style.backgroundSize = 'auto'; root.style.backgroundRepeat = 'no-repeat'; root.style.backgroundPosition = 'center'; }
    else { root.style.backgroundSize = '100% 100%'; root.style.backgroundRepeat = 'no-repeat'; root.style.backgroundPosition = 'center'; }
  }
  WM.applyWall = applyWall; applyWall();

  // ================= 图标层 =================
  const layer = $('icons'); layer.innerHTML = '';
  const CW = 76, CH = 80, OX = 6, OY = 6, ROWS = Math.floor((DH - TB - OY) / CH);
  let sel = new Set(), deskFocus = false, anchorId = null;
  const rubber = h('div', { id: 'rubber' }); root.appendChild(rubber);
  const cellOf = (x, y) => [Math.round((x - OX) / CW), Math.round((y - OY) / CH)];
  const posOf = (c, r) => [OX + c * CW, OY + r * CH];

  function autoPlace(list) {
    list.forEach((it, i) => { S.pos[it.id] = posOf(Math.floor(i / ROWS), i % ROWS); });
  }
  function ensurePos(list) {
    if (S.auto) return autoPlace(list);
    const taken = new Set(list.filter(i => S.pos[i.id]).map(i => S.pos[i.id].join(',')));
    list.forEach(it => {
      if (S.pos[it.id]) return;
      for (let c = 0; c < 20; c++) for (let r = 0; r < ROWS; r++) { const p = posOf(c, r); if (!taken.has(p.join(','))) { S.pos[it.id] = p; taken.add(p.join(',')); c = 99; break; } }
    });
  }
  function render() {
    const list = items();
    if (S.sort) sortList(list, S.sort);
    ensurePos(list);
    layer.innerHTML = '';
    list.forEach(it => {
      const p = S.pos[it.id] || [OX, OY];
      const el = h('div', { class: 'dicon' + (sel.has(it.id) ? ' sel' : '') + (WM.clip && WM.clip.cut && WM.clip.ids.includes(it.id) ? ' cut' : ''), 'data-id': it.id, style: `left:${p[0]}px;top:${p[1]}px` },
        [h('img', { src: it.icon, alt: '', draggable: 'false' }), h('span', { text: it.name })]);
      if (it.type === '快捷方式' && !it.sys) el.appendChild(h('i', { style: 'position:absolute;left:' + 24 + 'px;top:' + 24 + 'px;width:10px;height:10px;background:#fff;border:1px solid #666;box-sizing:border-box;display:none' }));
      layer.appendChild(el);
    });
    layer.classList.toggle('hidden', S.hide);
  }
  function sortList(list, by) {
    const cmp = { name: (a, b) => a.name.localeCompare(b.name, 'zh'), size: (a, b) => a.size - b.size || a.name.localeCompare(b.name, 'zh'),
      type: (a, b) => a.type.localeCompare(b.type, 'zh') || a.name.localeCompare(b.name, 'zh'), mtime: (a, b) => a.mtime.localeCompare(b.mtime) || a.name.localeCompare(b.name, 'zh'),
      group: (a, b) => (a.sys ? 0 : 1) - (b.sys ? 0 : 1) || a.type.localeCompare(b.type, 'zh') || a.name.localeCompare(b.name, 'zh') }[by];
    list.sort(cmp);
  }
  function arrangeBy(by) {
    S.sort = ''; const list = items(); sortList(list, by);
    // 系统图标（我的电脑/我的文档/回收站）总是排在最前面（XP 行为）
    const sys = ['mycomputer', 'mydocs', 'recycle']; list.sort((a, b) => (sys.includes(b.id) ? 1 : 0) - (sys.includes(a.id) ? 1 : 0) || 0);
    const first = list.filter(i => sys.includes(i.id)).sort((a, b) => sys.indexOf(a.id) - sys.indexOf(b.id)); const rest = list.filter(i => !sys.includes(i.id));
    autoPlace(first.concat(rest)); save(); render();
  }
  WM.refreshDesktop = function () {
    // 经典 XP 刷新：图标消失一瞬再重画；重新读取状态（回收站、壁纸、排序、图标）
    layer.style.visibility = 'hidden';
    setTimeout(() => { applyWall(); sel.clear(); render(); layer.style.visibility = 'hidden'; setTimeout(() => { layer.style.visibility = ''; }, 60); document.dispatchEvent(new CustomEvent('deskrefresh')); }, 120);
  };
  render();

  const iconEl = id => layer.querySelector(`.dicon[data-id="${id}"]`);
  function select(ids, add) {
    if (!add) sel.clear(); ids.forEach(i => sel.add(i));
    layer.querySelectorAll('.dicon').forEach(e => e.classList.toggle('sel', sel.has(e.dataset.id)));
  }
  function openItem(it) {
    if (it.id === 'ttplayer') return WM.open('ttplayer');
    if (it.app === 'link') return WM.alert('快捷方式', '快捷方式“' + it.name + '”指向的项目不可用。\n\n请检查快捷方式的目标，再试一次。', {});
    if (it.app === 'bmp') return WM.alert(it.name, 'Windows 无法打开此文件：\n' + it.name, { kind: 'error' });
    WM.open(it.app, it.args);
  }
  WM.openDeskItem = openItem;

  // 重命名
  function rename(id) {
    const el = iconEl(id); if (!el) return; const it = find(id); if (!it) return;
    const span = el.querySelector('span'), inp = h('input', { class: 'ren', value: it.name });
    span.replaceWith(inp); inp.focus(); inp.select();
    let done = false;
    const fin = ok => {
      if (done) return; done = true; const v = inp.value.trim();
      if (ok && v && v !== it.name) { const ex = S.extra.find(e => e.id === id); if (ex) ex.name = v; else S.names[id] = v; save(); }
      render(); select([id]);
    };
    inp.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Enter') fin(true); else if (e.key === 'Escape') fin(false); });
    inp.addEventListener('blur', () => fin(true));
    inp.addEventListener('pointerdown', e => e.stopPropagation());
  }
  WM.renameDeskItem = rename;

  function newItem(kind, name) {
    const k = KINDS[kind]; const id = 'x' + Date.now().toString(36) + Math.floor(Math.random() * 99);
    let base = name || k.base, nm = base, n = 2; const names = items().map(i => i.name);
    while (names.includes(nm)) { nm = base.replace(/(\.[a-z]+)?$/, ' (' + (n++) + ')$1'); }
    const d = new Date(), p = v => String(v).padStart(2, '0');
    S.extra.push({ id, kind, name: nm, mtime: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}` });
    S.pos[id] = null; delete S.pos[id]; save(); render(); select([id]); return id;
  }
  function del(ids) {
    const list = items().filter(i => ids.includes(i.id)).filter(i => !(i.sys && false));
    if (!list.length) return;
    const msg = list.length === 1 ? '确实要把“' + list[0].name + '”放入回收站吗？' : '确实要把这 ' + list.length + ' 项都放入回收站吗？';
    WM.confirm('确认文件删除', msg, () => {
      list.forEach(it => {
        S.trash.push({ id: it.id, name: it.name, icon: it.icon, type: it.type, from: '桌面', date: new Date().toLocaleDateString('zh-CN') + ' ' + new Date().toTimeString().slice(0, 5), extra: S.extra.find(e => e.id === it.id) || null, def: DEFAULT.some(d => d.id === it.id) });
        S.extra = S.extra.filter(e => e.id !== it.id); if (DEFAULT.some(d => d.id === it.id)) S.removed.push(it.id); delete S.pos[it.id];
      });
      sel.clear(); save(); render(); document.dispatchEvent(new CustomEvent('trashchange'));
    });
  }
  WM.restoreTrash = function (idx) {
    const t = S.trash[idx]; if (!t) return;
    if (t.def) S.removed = S.removed.filter(x => x !== t.id); else if (t.extra) S.extra.push(t.extra);
    S.trash.splice(idx, 1); save(); render(); document.dispatchEvent(new CustomEvent('trashchange'));
  };
  WM.emptyTrash = function () {
    WM.confirm('确认删除多个文件', '确实要删除回收站中的这 ' + S.trash.length + ' 项吗？', () => { S.trash = []; save(); document.dispatchEvent(new CustomEvent('trashchange')); });
  };
  function copy(ids, cut) { WM.clip = { ids, cut }; render(); }
  function paste(asLink) {
    if (!WM.clip) return;
    WM.clip.ids.forEach(id => {
      const it = find(id); if (!it) return;
      if (WM.clip.cut) return; // 剪切后粘贴在同一桌面 = 原地不动
      const k = it.app === 'explorer' && !it.sys ? 'folder' : 'link';
      const nid = newItem(k, (asLink ? '' : '') + (asLink ? it.name + ' - 快捷方式' : '复件 ' + it.name)); void nid;
    });
    WM.clip = null; render();
  }
  function sysItem(it) { return ['mycomputer', 'mydocs', 'recycle'].includes(it.id); }

  // ---- 图标右键菜单 ----
  function iconMenu(ev, it) {
    const ids = sel.has(it.id) ? [...sel] : [it.id];
    const items_ = [{ t: '打开(O)', bold: true, on: () => openItem(it) }];
    if (it.app === 'explorer') items_.push({ t: '资源管理器(X)', on: () => openItem(it) }, { t: '搜索(E)...', on: () => WM.open('explorer', { path: 'search' }) });
    if (it.id === 'mycomputer') items_.push('-', { t: '管理(G)', on: () => WM.alert('计算机管理', '你没有足够的权限执行此操作。\n\n请联系系统管理员。', {}) }, { t: '映射网络驱动器(N)...', on: () => WM.alert('映射网络驱动器', '没有可用的网络。', { kind: 'warn' }) }, { t: '断开网络驱动器(I)...', dis: true });
    if (it.id === 'recycle') items_.push('-', { t: '清空回收站(B)', dis: !S.trash.length, on: () => WM.emptyTrash() });
    if (it.id === 'ie') items_.push('-', { t: '属性(R)', on: () => WM.open('inetcpl') });
    if (!sysItem(it) && it.app !== 'explorer') items_.push({ t: '以其他用户身份运行(U)...', dis: true });
    if (!sysItem(it)) items_.push('-', { t: '发送到(N)', sub: [{ t: '桌面快捷方式', icon: 'xp/ico/309_16.png', on: () => newItem('link', it.name + ' - 快捷方式') }, { t: '邮件收件人', icon: 'xp/ico/887_16.png', on: () => WM.alert('Windows', '没有找到默认的邮件客户端。', { kind: 'warn' }) }, { t: '我的文档', icon: 'xp/ico/308_16.png', on: () => {} }] });
    items_.push('-', { t: '剪切(T)', dis: sysItem(it), on: () => copy(ids, true) }, { t: '复制(C)', dis: sysItem(it), on: () => copy(ids, false) });
    items_.push('-', { t: '创建快捷方式(S)', on: () => newItem('link', it.name + ' - 快捷方式') }, { t: '删除(D)', dis: it.id === 'mycomputer' || it.id === 'mydocs', on: () => del(ids) }, { t: '重命名(M)', dis: false, on: () => rename(it.id) });
    items_.push('-', { t: '属性(R)', on: () => props(it) });
    WM.ctx(ev, items_);
  }
  function props(it) {
    const link = it.type === '快捷方式';
    const tgt = { ie: 'C:\\Program Files\\Internet Explorer\\iexplore.exe', ttplayer: 'C:\\Program Files\\TTPlayer\\TTPlayer.exe', baofeng: 'C:\\Program Files\\Baofeng\\Storm\\Storm.exe', kugou: 'C:\\Program Files\\KuGou\\KuGou.exe', xunlei: 'C:\\Program Files\\Thunder Network\\Thunder\\Thunder.exe', qq: 'C:\\Program Files\\Tencent\\QQ\\QQ.exe', qqgame: 'C:\\Program Files\\Tencent\\QQGame\\QQGame.exe', cs: 'C:\\Games\\Counter-Strike 1.6\\hl.exe -game cstrike', vc: 'C:\\Games\\GTA Vice City\\gta-vc.exe', war3: 'C:\\Games\\Warcraft III\\war3.exe', ra2: 'C:\\Games\\RA2\\ra2.exe', mir2: 'C:\\Games\\Legend of Mir 2\\Mir2.exe', audition: 'C:\\Program Files\\Audition\\Audition.exe' }[it.id] || 'C:\\WINDOWS\\explorer.exe';
    const pages = { 常规: () => h('div', {}, [
      h('div', { style: 'display:flex;align-items:center;margin-bottom:8px' }, [h('img', { src: it.icon, style: 'width:32px;height:32px;margin-right:12px' }), h('input', { class: 'xinput', value: it.name, style: 'flex:1', readonly: true })]),
      h('div', { style: 'border-top:1px solid #d0d0bf;padding-top:8px;line-height:22px' }, [
        ['文件类型：', it.type], ['描述：', it.name], ['位置：', 'C:\\Documents and Settings\\Administrator\\桌面'], ['大小：', it.size ? it.size + ' KB (' + it.size * 1024 + ' 字节)' : '0 字节'], ['修改时间：', it.mtime]]
        .map(([a, b]) => h('div', { style: 'display:flex' }, [h('div', { style: 'width:80px;color:#000', text: a }), h('div', { style: 'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: b })]))),
    ]) };
    if (link) pages['快捷方式'] = () => h('div', { style: 'line-height:26px' }, [
      ['目标类型：', '应用程序'], ['目标位置：', tgt.replace(/\\[^\\]*$/, '').split('\\').pop()]].map(([a, b]) => h('div', { style: 'display:flex' }, [h('div', { style: 'width:80px', text: a }), h('div', { text: b })])).concat([
      h('div', { style: 'display:flex' }, [h('div', { style: 'width:80px', text: '目标(T)：' }), h('input', { class: 'xinput', value: tgt, style: 'flex:1' })]),
      h('div', { style: 'display:flex' }, [h('div', { style: 'width:80px', text: '起始位置(S)：' }), h('input', { class: 'xinput', value: tgt.replace(/\\[^\\]*$/, ''), style: 'flex:1' })]),
      h('div', { style: 'display:flex' }, [h('div', { style: 'width:80px', text: '快捷键(K)：' }), h('input', { class: 'xinput', value: '无', style: 'width:150px' })]),
      h('div', { style: 'display:flex' }, [h('div', { style: 'width:80px', text: '运行方式(R)：' }), h('select', { class: 'xinput', style: 'width:150px' }, [h('option', { text: '常规窗口' })])]),
    ]));
    WM.tabsDialog({ id: 'props-' + it.id, title: it.name + ' 属性', icon: it.icon, w: 370, h: 440, pages, ok: true });
  }
  WM.itemProps = props;

  // ---- 通用标签页对话框 ----
  WM.tabsDialog = function (o) {
    const names = Object.keys(o.pages); let cur = o.tab || names[0];
    return WM.dialog({
      id: o.id, title: o.title, icon: o.icon || ICO('318_16.png'), w: o.w, h: o.h,
      content: w => {
        const box = h('div', { class: 'xpd', style: 'padding:8px 10px' });
        const tabs = h('div', { class: 'xtabs' }), panel = h('div', { class: 'xpanel', style: `position:absolute;left:10px;right:10px;top:36px;bottom:46px;overflow:auto;margin:0` });
        const show = n => { cur = n; [...tabs.children].forEach(t => t.classList.toggle('on', t.textContent === n)); panel.innerHTML = ''; panel.appendChild(o.pages[n](w)); };
        names.forEach(n => tabs.appendChild(h('div', { class: 'tb', text: n, onclick: () => show(n) })));
        const bar = h('div', { style: 'position:absolute;right:10px;bottom:10px;display:flex;gap:6px' }, [
          h('button', { class: 'xbtn def', text: '确定', onclick: () => { o.onok && o.onok(w); w.close(); } }),
          h('button', { class: 'xbtn', text: '取消', onclick: () => w.close() }),
          h('button', { class: 'xbtn', text: '应用(A)', disabled: !o.apply, onclick: () => o.apply && o.apply(w) }),
        ]);
        box.append(tabs, panel, bar); show(cur); return box;
      },
    });
  };
  WM.prompt = function (title, label, def, cb) {
    return WM.dialog({ id: 'prompt-' + title, title, icon: ICO('318_16.png'), w: 340, h: 150, modal: true, content: w => {
      const inp = h('input', { class: 'xinput', value: def || '', style: 'width:300px;display:block;margin:6px 0 0' });
      const ok = () => { w.close(); cb(inp.value); };
      inp.addEventListener('keydown', e => { if (e.key === 'Enter') ok(); });
      setTimeout(() => { inp.focus(); inp.select(); }, 30);
      return h('div', { class: 'xpd' }, [h('div', { text: label, style: 'margin-top:4px' }), inp, h('div', { class: 'msgbtns' }, [h('button', { class: 'xbtn def', text: '确定', onclick: ok }), h('button', { class: 'xbtn', text: '取消', onclick: () => w.close() })])]);
    } });
  };

  // ---- 桌面右键菜单 ----
  function deskMenu(ev) {
    const arr = by => ({ t: { name: '名称(N)', size: '大小(S)', type: '类型(T)', mtime: '修改时间(M)' }[by], on: () => arrangeBy(by) });
    WM.ctx(ev, [
      { t: '排列图标(I)', sub: [arr('name'), arr('size'), arr('type'), arr('mtime'), '-',
        { t: '按组排列(G)', on: () => arrangeBy('group') },
        { t: '自动排列(A)', chk: S.auto, on: () => { S.auto = !S.auto; if (S.auto) arrangeBy('name'); else { save(); render(); } } },
        { t: '对齐到网格(L)', chk: S.grid, on: () => { S.grid = !S.grid; save(); } }, '-',
        { t: '显示桌面图标(D)', chk: !S.hide, on: () => { S.hide = !S.hide; save(); render(); } },
        { t: '锁定 Web 项目(W)', dis: true }, '-', { t: '运行桌面清理向导(R)', on: () => WM.open('cleanup') }] },
      { t: '刷新(E)', on: () => WM.refreshDesktop() }, '-',
      { t: '粘贴(P)', dis: () => !WM.clip, on: () => paste(false) }, { t: '粘贴快捷方式(S)', dis: () => !WM.clip, on: () => paste(true) }, '-',
      { t: '新建(W)', sub: [
        { t: '文件夹(F)', icon: 'xp/ico/318_16.png', on: () => { const id = newItem('folder'); setTimeout(() => rename(id), 30); } },
        { t: '快捷方式(S)', icon: 'xp/ico/309_16.png', on: () => WM.open('mkshortcut') }, '-',
        { t: '公文包', icon: 'xp/ico/57_16.png', on: () => { const id = newItem('brief'); setTimeout(() => rename(id), 30); } },
        { t: 'BMP 图像', icon: 'xp/ico/680_16.png', on: () => { const id = newItem('bmp'); setTimeout(() => rename(id), 30); } },
        { t: '文本文档', icon: 'xp/ico/327_16.png', on: () => { const id = newItem('text'); setTimeout(() => rename(id), 30); } }] },
      '-', { t: '属性(R)', on: () => WM.open('display') },
    ]);
  }

  // ---- 桌面事件 ----
  root.addEventListener('pointerdown', e => {
    const onIcon = e.target.closest('.dicon');
    const inWin = e.target.closest('.xpw, #win, #tt, #pl, #taskbar, #startmenu, .xpm');
    if (!inWin) { deskFocus = true; if (WM.active) { WM.active = null; WM.refresh(); } } else if (!e.target.closest('.dicon')) deskFocus = false;
    if (e.target.closest('input,textarea')) return;
    if (onIcon && layer.contains(onIcon)) {
      if (e.button === 2 && sel.has(onIcon.dataset.id)) return;
      const id = onIcon.dataset.id;
      if (e.ctrlKey || e.metaKey) { sel.has(id) ? sel.delete(id) : sel.add(id); select([], true); return; }
      if (!sel.has(id)) select([id]);
      anchorId = id;
      if (e.button !== 0) return;
      // 拖动图标
      const ids = [...sel], start = ids.map(i => [i, ...(S.pos[i] || [0, 0])]); let moved = false;
      track(e, (dx, dy) => {
        if (!moved && Math.hypot(dx, dy) < 4) return; moved = true;
        start.forEach(([i, x, y]) => { const el = iconEl(i); if (el) { el.style.left = x + dx + 'px'; el.style.top = y + dy + 'px'; el.style.zIndex = 5; } });
      }, () => {
        if (!moved) return;
        if (S.auto) { render(); return; }
        const taken = new Set(Object.entries(S.pos).filter(([k]) => !ids.includes(k)).map(([, v]) => v && v.join(',')));
        start.forEach(([i]) => {
          const el = iconEl(i); let x = parseFloat(el.style.left), y = parseFloat(el.style.top);
          x = Math.max(0, Math.min(DW - CW, x)); y = Math.max(0, Math.min(DH - TB - CH, y));
          if (S.grid) {
            let [c, r] = cellOf(x, y); c = Math.max(0, c); r = Math.max(0, Math.min(ROWS - 1, r));
            let best = null, bd = 1e9;
            for (let cc = 0; cc < 16; cc++) for (let rr = 0; rr < ROWS; rr++) { const p = posOf(cc, rr); if (taken.has(p.join(','))) continue; const d = Math.hypot(cc - c, rr - r); if (d < bd) { bd = d; best = p; } }
            [x, y] = best || posOf(c, r);
          }
          S.pos[i] = [x, y]; taken.add(S.pos[i].join(','));
        });
        S.sort = ''; save(); render();
      });
      return;
    }
    if (!inWin && (e.target === root || e.target === layer || e.target.id === 'icons')) {
      if (e.button === 0) {
        select([]); const p0 = toRoot(e);
        track(e, (dx, dy) => {
          const x = Math.min(p0.x, p0.x + dx), y = Math.min(p0.y, p0.y + dy), w = Math.abs(dx), hh = Math.abs(dy);
          if (w < 3 && hh < 3) return;
          Object.assign(rubber.style, { display: 'block', left: x + 'px', top: y + 'px', width: w + 'px', height: hh + 'px' });
          const ids = [...layer.querySelectorAll('.dicon')].filter(el => { const l = parseFloat(el.style.left), t = parseFloat(el.style.top); return l < x + w && l + 56 > x && t < y + hh && t + 60 > y; }).map(el => el.dataset.id);
          select(ids);
        }, () => { rubber.style.display = 'none'; });
      }
    }
  });
  root.addEventListener('dblclick', e => { const el = e.target.closest('.dicon'); if (el && layer.contains(el)) { const it = find(el.dataset.id); it && openItem(it); } });
  root.addEventListener('contextmenu', e => {
    if (e.target.closest('.xpw, #win, #tt, #pl, #startmenu, .xpm, #tray, .tbtn, #start, #quick')) { if (!e.target.closest('input,textarea')) e.preventDefault(); return; }
    const el = e.target.closest('.dicon');
    if (el && layer.contains(el)) { const it = find(el.dataset.id); if (!sel.has(it.id)) select([it.id]); return iconMenu(e, it); }
    if (e.target.closest('#taskbar')) return taskbarMenu(e);
    if (e.target === root || e.target === layer || e.target.id === 'icons') deskMenu(e);
    else e.preventDefault();
  });
  document.addEventListener('keydown', e => {
    if (!deskFocus || e.target.closest('input,textarea')) return;
    const ids = [...sel];
    if (e.key === 'F5') { e.preventDefault(); WM.refreshDesktop(); }
    else if (e.key === 'F2' && ids.length === 1) rename(ids[0]);
    else if (e.key === 'Enter' && ids.length) ids.forEach(i => openItem(find(i)));
    else if (e.key === 'Delete' && ids.length) del(ids);
    else if ((e.ctrlKey || e.metaKey) && e.key === 'a') { e.preventDefault(); select(items().map(i => i.id)); }
    else if ((e.ctrlKey || e.metaKey) && e.key === 'c' && ids.length) copy(ids, false);
    else if ((e.ctrlKey || e.metaKey) && e.key === 'x' && ids.length) copy(ids, true);
    else if ((e.ctrlKey || e.metaKey) && e.key === 'v') paste(false);
  });

  // ================= 任务栏 =================
  const tbar = $('taskbar'), left = tbar.querySelector('.left'), startBtn = $('start');
  // 删除原来的假按钮（暴风影音），QQ/千千静听按钮由窗口接管
  [...left.querySelectorAll('.tbtn')].forEach(b => { if (!b.querySelector('#tb-qqt') && b.id !== 'tb-tt') b.remove(); });
  const qqTb = left.querySelector('#tb-qqt').parentElement; qqTb.classList.remove('act');
  const quick = h('div', { id: 'quick' }); startBtn.after(quick);
  [['Internet Explorer', 'xp/ico/896_16.png', () => WM.open('ie')], ['腾讯QQ', 'xp/ui/qq16.png', () => WM.open('qq')], ['千千静听', 'xp/ui/ttp16.png', () => WM.open('ttplayer')], ['暴风影音', 'xp/ui/bf16.png', () => WM.open('baofeng')]]
    .forEach(([t, src, f]) => quick.appendChild(h('img', { src, title: t, onclick: f })));
  function taskbarMenu(ev) {
    WM.ctx(ev, [{ t: '工具栏(T)', sub: [{ t: '地址(A)', dis: true }, { t: '链接(L)', dis: true }, { t: '桌面(D)', dis: true }, { t: '快速启动(Q)', chk: true }] }, '-',
      { t: '层叠窗口(D)', on: () => tile('cascade') }, { t: '横向平铺窗口(H)', on: () => tile('h') }, { t: '纵向平铺窗口(V)', on: () => tile('v') }, { t: '显示桌面(S)', on: () => WM.showDesktop() }, '-',
      { t: '任务管理器(K)', on: () => WM.open('taskmgr') }, '-', { t: '锁定任务栏(L)', chk: true }, { t: '属性(R)', on: () => WM.open('taskbarprops') }], { noTaskbar: false });
  }
  function tile(mode) {
    const ws = WM.visible().filter(w => !w.o.adopted || w.id === 'qqchat'); if (!ws.length) return;
    const H = DH - TB, n = ws.length;
    ws.forEach((w, i) => {
      if (w.state === 'max') w.state = 'normal';
      if (mode === 'cascade') w.rect = { x: 20 + i * 28, y: 14 + i * 28, w: Math.min(720, DW - 100), h: Math.min(460, H - 60) };
      else if (mode === 'h') { const rows = Math.ceil(Math.sqrt(n)), cols = Math.ceil(n / rows), r = Math.floor(i / cols), c = i % cols; w.rect = { x: c * DW / cols, y: r * H / rows, w: DW / cols, h: H / rows }; }
      else { const cols = Math.ceil(Math.sqrt(n)), rows = Math.ceil(n / cols), c = Math.floor(i / rows), r = i % rows; w.rect = { x: c * DW / cols, y: r * H / rows, w: DW / cols, h: H / rows }; }
      w._apply(); w.focus();
    });
  }
  tbar.addEventListener('contextmenu', e => { if (e.target.closest('.tbtn')) return; e.preventDefault(); e.stopPropagation(); taskbarMenu(e); });
  // 托盘
  const tray = $('tray'), tIcons = tray.querySelectorAll('img');
  tIcons[0].title = '音量'; tIcons[1].title = '本地连接 已连接'; tIcons[2].title = 'Windows 安全中心';
  tIcons[0].addEventListener('click', e => { e.stopPropagation(); volumePopup(); });
  tIcons[1].addEventListener('dblclick', () => WM.alert('本地连接 状态', '连接状态：已连接\n速度：100.0 Mbps\n持续时间：03:21:47', { kind: 'info' }));
  tIcons[2].addEventListener('dblclick', () => WM.alert('Windows 安全中心', '防火墙：启用\n自动更新：启用\n病毒防护：未找到', { kind: 'info' }));
  const clk = $('clk'); clk.title = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
  clk.addEventListener('dblclick', () => WM.open('datetime'));
  function volumePopup() {
    WM.closeMenus(); const old = $('volpop'); if (old) return old.remove();
    const v = WM.vol == null ? 70 : WM.vol;
    const pop = h('div', { id: 'volpop', style: 'position:absolute;right:62px;bottom:32px;width:78px;height:128px;z-index:12000;background:#ece9d8;border:1px solid #aca899;box-shadow:2px 2px 3px rgba(0,0,0,.4);font:12px var(--xpfont);padding:6px;box-sizing:border-box;text-align:center' });
    const sl = h('input', { type: 'range', min: 0, max: 100, value: v, style: 'writing-mode:vertical-lr;direction:rtl;height:72px;margin:2px 0' });
    sl.addEventListener('input', () => { WM.vol = +sl.value; document.dispatchEvent(new CustomEvent('sysvol', { detail: WM.vol / 100 })); });
    const mute = h('input', { type: 'checkbox' }); mute.checked = !!WM.mute; mute.addEventListener('change', () => { WM.mute = mute.checked; document.dispatchEvent(new CustomEvent('sysmute', { detail: WM.mute })); });
    pop.append(h('div', { text: '音量' }), sl, h('div', {}, [mute, h('label', { text: '静音' })]));
    root.appendChild(pop);
    const off = ev => { if (!pop.contains(ev.target)) { pop.remove(); document.removeEventListener('pointerdown', off, true); } };
    setTimeout(() => document.addEventListener('pointerdown', off, true), 0);
  }

  // ================= 开始菜单 =================
  const sm = h('div', { id: 'startmenu' }); root.appendChild(sm);
  const I = (src, size) => src.includes('/') ? src : 'xp/ico/' + src;
  const open = (id, args) => () => { closeStart(); WM.open(id, args); };
  const mk = (t, icon, f, extra) => h('div', { class: 'it' + (extra && extra.bold ? ' bold' : ''), onclick: f }, [h('img', { src: I(icon) }), h('div', { class: 'tx' }, [h('span', { text: t })].concat(extra && extra.sub ? [h('small', { text: extra.sub })] : []))]);
  function startItems(list) { return list.map(i => i === '-' ? h('div', { class: 'sp' }) : mk(i[0], i[1], i[2], i[3])); }
  const xa = () => !(window.XP && XP.cfg.enabled && XP.cfg.apps === false);   // [xp] apps：新增的 纸牌 / 空当接龙 / 画图 / 控制面板 开始菜单项
  const prog = (t, icon, id, args) => ({ t, icon, on: () => WM.open(id, args) });
  const qqa = () => { const Q = window.QQX; if (!Q || !Q.cfg.enabled) return []; const o = []; if (Q.cfg.zone) o.push(prog('QQ空间', 'xp/ui/qq16.png', 'qzone')); if (Q.cfg.pet) o.push(prog('QQ宠物', 'xp/ui/qq16.png', 'qqpet')); if (Q.cfg.show) o.push(prog('QQ秀商城', 'xp/ui/qq16.png', 'qqshow')); if (Q.cfg.files) o.push(prog('群共享', 'xp/ui/qq16.png', 'qqfiles')); return o; };   // qq-core.js：QQ 生态的开始菜单入口
  const playa = () => { const P = window.PLAYX; if (!P || !P.cfg.enabled) return []; const o = []; if (P.cfg.points) o.push(prog('QQ积分排行榜', 'xp/ui/qq16.png', 'rank')); if (P.cfg.vote) o.push(prog('投票', 'xp/ui/qq16.png', 'vote')); return o; };
  const aixa = () => { const A = window.AIX; return A && A.on('game') ? [prog('趣味小游戏', 'xp/ui/qq16.png', 'game')] : []; };   // ai-ui.js：AI 加强包的开始菜单入口   // play-core.js：观众互动的开始菜单入口
  const opsa = () => (window.OPSX && OPSX.cfg.report ? [prog('直播复盘', 'xp/ui/qq16.png', 'report')] : []);   // ops-ui.js：下播复盘
  function allPrograms() {
    return [{ t: '设定程序访问和默认值', icon: '227_16.png', on: () => WM.alert('设定程序访问和默认值', '此功能在演示环境中不可用。', { kind: 'info' }) }, { t: 'Windows Catalog', icon: '392_16.png', on: () => WM.open('ie', { url: 'http://www.microsoft.com/' }) }, { t: 'Windows Update', icon: '322_16.png', on: () => WM.open('ie', { url: 'http://windowsupdate.microsoft.com/' }) }, '-',
      { t: '附件', icon: '358_16.png', sub: [prog('记事本', '327_16.png', 'notepad'), prog('计算器', '74_16.png', 'calc'), prog('命令提示符', '56_16.png', 'cmd'), prog('Windows 资源管理器', '156_16.png', 'explorer', { path: 'mydocs' }), ...(xa() ? [prog('画图', '680_16.png', 'paint')] : [])] },
      { t: '游戏', icon: '358_16.png', sub: [...(xa() ? [prog('空当接龙', 'freecell.png', 'freecell'), prog('纸牌', 'solitaire.png', 'solitaire')] : []), prog('扫雷', 'xp/mine/mine-icon.png', 'minesweeper')] },
      { t: '启动', icon: '358_16.png', sub: [{ t: '(空)', dis: true }] },
      prog('Internet Explorer', '896_16.png', 'ie'), prog('Outlook Express', '887_16.png', 'outlook'), prog('Windows Media Player', '846_16.png', 'baofeng'), '-',
      prog('腾讯QQ', 'xp/ui/qq16.png', 'qq'), prog('QQ游戏', 'xp/icons/qqgame.png', 'qqgame'), ...qqa(), ...playa(), ...aixa(), ...opsa(), prog('千千静听', 'xp/ui/ttp16.png', 'ttplayer'), prog('暴风影音', 'xp/ui/bf16.png', 'baofeng'), prog('酷狗音乐', 'xp/icons/kugou.png', 'kugou'), prog('迅雷', 'xp/icons/xunlei.png', 'xunlei'), '-',
      prog('Counter-Strike 1.6', 'xp/icons/cs.png', 'cs'), prog('侠盗猎车手 罪恶都市', 'xp/icons/vc.png', 'vc'), prog('魔兽争霸III', 'xp/icons/war3.png', 'war3'), prog('红色警戒2', 'xp/icons/ra2.png', 'ra2'), prog('热血传奇', 'xp/icons/mir2.png', 'mir2'), prog('劲舞团', 'xp/icons/audition.png', 'audition'),
    ].map(x => { if (typeof x !== 'object') return x; if (x.icon && !x.icon.includes('/')) x.icon = 'xp/ico/' + x.icon; if (x.sub) x.sub = x.sub.map(y => { if (y.icon && !y.icon.includes('/')) y.icon = 'xp/ico/' + y.icon; return y; }); return x; });
  }
  function buildStart() {
    sm.innerHTML = '';
    sm.append(h('header', {}, [h('img', { class: 'uimg', src: 'xp/ico/user.png' }), h('span', { class: 'uname', text: 'Administrator' })]));
    const L = h('div', { class: 'col l' }), R = h('div', { class: 'col r' });
    startItems([['Internet', 'ie.png', open('ie'), { bold: true, sub: 'Internet Explorer' }], ['电子邮件', '887_32.png', open('outlook'), { bold: true, sub: 'Outlook Express' }], '-',
      ['腾讯QQ', 'xp/icons/qq.png', open('qq')], ['千千静听', 'xp/icons/ttplayer.png', open('ttplayer')], ['暴风影音', 'xp/icons/baofeng.png', open('baofeng')], ['迅雷', 'xp/icons/xunlei.png', open('xunlei')], ['记事本', '327_32.png', open('notepad')], ['扫雷', 'xp/mine/mine-icon.png', open('minesweeper')]]).forEach(e => L.appendChild(e));
    L.appendChild(h('div', { class: 'grow' })); L.appendChild(h('div', { class: 'sp' }));
    const ap = h('div', { class: 'it allp' }, [h('div', { class: 'tx', style: 'flex-direction:row;align-items:center;gap:6px' }, [h('span', { text: '所有程序(P)' }), h('img', { src: 'xp/ico/all-programs.ico', style: 'width:18px;height:18px;margin:0' })])]);
    ap.addEventListener('pointerenter', () => { const r = ap.getBoundingClientRect(), rr = root.getBoundingClientRect(), k = WM.root.getBoundingClientRect().width / DW; if (!$('allprogs')) { const m = WM.menu(allPrograms(), (r.right - rr.left) / k - 2, (r.bottom - rr.top) / k - 8, { all: true }); m.id = 'allprogs'; m.style.zIndex = 12000; } });
    ap.addEventListener('click', () => ap.dispatchEvent(new Event('pointerenter')));
    L.appendChild(ap);
    startItems([['我的文档', '308_32.png', open('explorer', { path: 'mydocs' }), { bold: true }], ['我最近的文档', '301_32.png', () => {}, { bold: true }], ['我的图片', '307_32.png', open('explorer', { path: 'mypics' }), { bold: true }], ['我的音乐', '550_32.png', open('explorer', { path: 'mymusic' }), { bold: true }], ['我的电脑', '676_32.png', open('explorer', { path: 'mycomputer' }), { bold: true }], '-',
      ['控制面板', '300_32.png', open(xa() ? 'control' : 'explorer', xa() ? undefined : { path: 'control' })], ['设定程序访问和默认值', '227_32.png', () => { closeStart(); WM.alert('设定程序访问和默认值', '此功能在演示环境中不可用。', { kind: 'info' }); }], ['连接到', '309_32.png', () => {}], ['打印机和传真', '549_32.png', open('explorer', { path: 'printers' }), {}], '-',
      ['帮助和支持', '747_32.png', open('help')], ['搜索', '299_32.png', open('explorer', { path: 'search' })], ['运行(R)...', '743_32.png', open('run')]]).forEach(e => R.appendChild(e));
    [...R.children].forEach(c => { const t = c.textContent; if (t === '我最近的文档' || t === '连接到') c.appendChild(h('span', { class: 'ar' })); });
    sm.append(h('div', { class: 'body' }, [L, R]));
    sm.append(h('footer', {}, [h('div', { class: 'fi', onclick: () => { closeStart(); WM.open('logoff'); } }, [h('img', { src: 'xp/ico/546_32.png' }), h('span', { text: '注销(L)' })]), h('div', { class: 'fi', onclick: () => { closeStart(); WM.open('shutdown'); } }, [h('img', { src: 'xp/ico/310_32.png' }), h('span', { text: '关闭计算机(U)' })])]));
  }
  function closeStart() { sm.classList.remove('show'); startBtn.classList.remove('pressed'); const a = $('allprogs'); if (a) WM.closeMenus(); }
  startBtn.addEventListener('pointerdown', e => {
    e.stopPropagation();
    if (sm.classList.contains('show')) return closeStart();
    WM.closeMenus(); buildStart(); sm.classList.add('show'); startBtn.classList.add('pressed');
  });
  document.addEventListener('pointerdown', e => { if (sm.classList.contains('show') && !e.target.closest('#startmenu, #start, .xpm')) closeStart(); }, true);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && sm.classList.contains('show')) closeStart(); });
  sm.addEventListener('pointerenter', () => {}, true);
  // 鼠标移到其它项时收起“所有程序”
  sm.addEventListener('pointerover', e => { const it = e.target.closest('.it'); if (it && !it.classList.contains('allp') && $('allprogs')) WM.closeMenus(); });

  // ================= 接管：QQ 群聊 / 千千静听 / 播放列表 =================
  const win = $('win'), tt = $('tt'), pl = $('pl');
  const rectQ = DESK.rect;
  const qqw = WM.adopt(win, {
    id: 'qqchat', title: '怀旧QQ群', icon: 'xp/ui/qq16.png', tbEl: qqTb, minW: 420, minH: 330,
    handle: e => !!e.target.closest('.qq-title') && !e.target.closest('button'), titleDbl: e => !!e.target.closest('.qq-title') && !e.target.closest('button'),
    btns: { min: '#qq-im-min', max: '#qq-im-max', close: '#qq-im-close' }, resize: ['n', 's', 'e', 'w', 'nw', 'ne', 'sw', 'se'],
    getRect: () => ({ x: rectQ.x, y: rectQ.y, w: rectQ.w, h: rectQ.h }),
    setRect: (r, max) => { if (!max) Object.assign(rectQ, r); Object.assign(win.style, { left: r.x + 'px', top: r.y + 'px', width: r.w + 'px', height: r.h + 'px' }); },
    onapply: () => document.dispatchEvent(new Event('qqresize')),
  });
  // 标题随群名变化
  new MutationObserver(() => { qqw.setTitle(($('title').textContent || '').replace(/ ?\(\d+人\)$/, '')); }).observe($('title'), { childList: true, characterData: true, subtree: true });
  WM.register('qqchat', { open: () => { if (qqw.closed) qqw.reopen(); else if (qqw.state === 'min') qqw.restore(); else qqw.focus(); return qqw; } });
  win.addEventListener('pointerdown', () => { win.classList.remove('inactive'); }, true);
  document.addEventListener('wmchange', () => { win.classList.toggle('inactive', WM.active !== qqw); });

  const ttX = parseFloat(tt.style.left), ttY = parseFloat(tt.style.top);
  let plDocked = true;
  const ttw = WM.adopt(tt, {
    id: 'ttplayer', title: '千千静听', icon: 'xp/ui/ttp16.png', tbEl: $('tb-tt'), fixedSize: true,
    handle: e => !e.target.closest('.b, #tt-thumb, #tt-vthumb, #tt-vfill, canvas, #tt-info') || (!!e.target.closest('canvas') && false),
    btns: { min: '#tt-min', close: '#tt-exit' },
    getRect: () => ({ x: ttX, y: ttY, w: 268, h: 165 }),
    setRect: r => { tt.style.left = r.x + 'px'; tt.style.top = r.y + 'px'; if (plDocked) { pl.style.left = r.x + 'px'; pl.style.top = (r.y + 165) + 'px'; plw.rect.x = r.x; plw.rect.y = r.y + 165; } },
    onapply: () => DESK.musicRender && DESK.musicRender(),
  });
  const PLH0 = 146;
  const plw = WM.adopt(pl, {
    id: 'ttplaylist', title: '千千静听 - 播放列表', icon: 'xp/ui/ttp16.png', fixedSize: true, minW: 268, minH: 90,
    handle: e => { const r = pl.getBoundingClientRect(); return (e.clientY - r.top) / (r.height / pl.offsetHeight) < 26 && !e.target.closest('#pl-tool'); },
    resize: ['s'],
    getRect: () => ({ x: parseFloat(pl.style.left), y: parseFloat(pl.style.top), w: 268, h: PLH0 }),
    setRect: r => { pl.style.left = r.x + 'px'; pl.style.top = r.y + 'px'; pl.style.height = r.h + 'px'; pl.querySelector('.skin').style.height = r.h + 'px'; $('pl-rows').style.height = (r.h - 62) + 'px'; },
  });
  plw.o.notask = true;
  pl.addEventListener('pointerdown', e => { if (plw.o.handle && plDocked && plw.o.handle) { const r = pl.getBoundingClientRect(); if ((e.clientY - r.top) / (r.height / pl.offsetHeight) < 26) plDocked = false; } }, true);
  DESK.ttwin = ttw; DESK.plwin = plw; DESK.ttForce = false;
  WM.register('ttplayer', { open: () => { DESK.ttForce = true; if (ttw.closed) ttw.reopen(); else if (ttw.state === 'min') ttw.restore(); else ttw.focus(); DESK.musicRender && DESK.musicRender(); return ttw; } });
  ttw.tbHidden = true; plw.tbHidden = true;
  document.addEventListener('wmchange', () => { const off = ttw.closed || ttw.state === 'min'; pl.classList.toggle('wm-min', off); DESK.musicRender && DESK.musicRender(); });
  ttw.onstate = () => { if (ttw.closed) { DESK.ttForce = false; } document.dispatchEvent(new Event('wmchange')); };

  // 初始
  WM.refresh();
  window.addEventListener('beforeunload', save);
})();
