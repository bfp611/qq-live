// 群共享（?desk=xp）：仿 2007 年 QQ 群「群共享」文件面板 —— 文件列表（假文件）+ 上传 / 下载 / 删除；点“下载”会在迅雷里新建任务并真的“下载”（进度条走完）。
// 新关注的观众会“上传”一个文件（[qq] files）。文件名可以在 config.ini 的 files_names 里改（逗号分隔，“名字|大小MB”）。没有任何真实文件，下载只是动画。
(function () {
  const Q = window.QQX; if (!Q) return;
  const { h, esc } = WM;
  const SEED = [['QQ2007 正式版 Beta3.exe', 21.4, '群主', 3120], ['千千静听 5.5 简体中文正式版.exe', 3.9, '群主', 2210], ['猪猪侠 表情包合集.rar', 8.6, '猪猪侠', 641], ['周杰伦 - 十一月的萧邦 [APE整轨].rar', 296.2, '冷月无声', 188], ['Counter-Strike 1.6 完整硬盘版.rar', 487.6, '孤独de狼', 972], ['红色警戒2 尤里的复仇 + 秘籍.rar', 412.3, '阿杰', 703], ['QQ秀 装扮素材包.zip', 14.6, '＠_＠偶是MM', 255], ['直播间群规.txt', 0.002, '群主', 1544]];
  const css = document.createElement('style'); css.textContent = `.qf { display:flex; flex-direction:column; height:100%; background:#fff; font:12px var(--xpfont); } .qf .tb { height:34px; flex:none; display:flex; align-items:center; gap:6px; padding:0 8px; background:linear-gradient(#f4f8ff,#d5e6fb); border-bottom:1px solid #8fb1da; } .qf .tb .sp { margin-left:auto; color:#456; }
    .qf .ls { flex:1; overflow:auto; } .qf table { width:100%; border-collapse:collapse; } .qf th { text-align:left; font-weight:400; padding:3px 8px; background:#ece9d8; border:1px solid #d6d2c2; position:sticky; top:0; } .qf td { padding:3px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap; } .qf td:first-child { max-width:300px; overflow:hidden; text-overflow:ellipsis; } .qf tr.sel td { background:#316ac5; color:#fff; } .qf tr:hover:not(.sel) td { background:#eef4ff; }
    .qf .sb { height:22px; flex:none; display:flex; align-items:center; gap:12px; padding:0 8px; background:#ece9d8; border-top:1px solid #aca899; color:#444; }`;
  document.head.appendChild(css);
  const parseNames = () => Q.list(Q.cfg.files_names).map(x => { const [n, mb] = x.split('|'); return n ? [n.trim(), parseFloat(mb) || 5, '群主', 10 + Math.floor(Math.random() * 400)] : null; }).filter(Boolean);
  const F = Q.store.get('files', null) || null; let files = null;
  const init = () => { if (files) return; const base = parseNames(); files = (F || (base.length ? base : SEED).map((a, i) => ({ n: a[0], mb: a[1], by: a[2], dl: a[3], t: Date.now() - (i + 1) * 3600e3 * (3 + i * 5) }))); };
  const save = () => Q.store.set('files', files.slice(-40));
  const size = mb => mb >= 1 ? mb.toFixed(1) + ' MB' : Math.max(1, Math.round(mb * 1024)) + ' KB';
  const pad = n => String(n).padStart(2, '0'), fmt = t => { const d = new Date(t); return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()); };
  const icon = n => /\.exe$/i.test(n) ? '74_16.png' : '318_16.png';
  function upload(name, mb, by) { init(); const f = { n: name, mb: mb || 1, by: by || '我', dl: 0, t: Date.now() }; files.push(f); save(); document.dispatchEvent(new CustomEvent('qqfiles', { detail: { kind: 'upload', file: f } })); return f; }
  function download(f, who) {
    init(); const target = typeof f === 'string' ? files.find(x => x.n.includes(f)) : f; if (!target) return null; target.dl++; save();
    const w = WM.open('xunlei'); const x = w && w.xl; let task = null;
    if (x) task = x.add(target.n, target.mb); else setTimeout(() => { const w2 = WM.byId.xunlei; w2 && w2.xl && w2.xl.add(target.n, target.mb); }, 200);
    document.dispatchEvent(new CustomEvent('qqfiles', { detail: { kind: 'download', file: target, who } })); return target;
  }
  function open() {
    init();
    return WM.create({ id: 'qqfiles', title: '群共享 - GG-Bond 的直播间', icon: 'xp/ui/qq16.png', w: 640, h: 380, minW: 440, minH: 240, content: win => {
      let sel = -1; const tb = h('tbody'), cnt = h('span');
      const draw = () => { tb.innerHTML = ''; files.forEach((f, i) => tb.appendChild(h('tr', { class: i === sel ? 'sel' : '', 'data-file': i, onclick: () => { sel = i; draw(); }, ondblclick: () => download(f, '你') }, [h('td', { html: `<img src="xp/ico/${icon(f.n)}" style="width:16px;vertical-align:-3px;margin-right:5px">${esc(f.n)}` }), h('td', { text: size(f.mb) }), h('td', { text: f.by }), h('td', { text: fmt(f.t) }), h('td', { text: f.dl })]))); cnt.textContent = '共 ' + files.length + ' 个文件，' + size(files.reduce((s, f) => s + f.mb, 0)); };
      const btn = (t, a, fn) => h('button', { class: 'xbtn', 'data-act': a, text: t, onclick: fn });
      const bar = h('div', { class: 'tb' }, [btn('上传文件', 'upload', () => WM.prompt('上传文件', '文件名：', '我的照片.jpg', v => { if (v) { upload(v, Math.round((.2 + Math.random() * 6) * 10) / 10, '我'); sel = files.length - 1; draw(); } })), btn('下载', 'download', () => { const f = files[sel]; if (f) download(f, '你'); else WM.alert('群共享', '请先选择要下载的文件。', { kind: 'info' }); }), btn('删除', 'delete', () => { if (sel >= 0 && files[sel]) WM.confirm('群共享', '确定要删除文件“' + files[sel].n + '”吗？', () => { files.splice(sel, 1); sel = -1; save(); draw(); }); }), btn('刷新', 'refresh', draw), h('span', { class: 'sp', text: '使用迅雷下载更快' })]);
      const onf = e => { if (win.closed) return document.removeEventListener('qqfiles', onf); draw(); }; document.addEventListener('qqfiles', onf); win.o.onclose = () => document.removeEventListener('qqfiles', onf);
      draw(); win.qf = { select: i => { sel = i; draw(); }, state: () => ({ sel, files: files.length }) };
      return h('div', { class: 'qf' }, [bar, h('div', { class: 'ls' }, [h('table', {}, [h('thead', {}, [h('tr', {}, ['文件名', '大小', '上传者', '上传时间', '下载次数'].map(t => h('th', { text: t })))]), tb])]), h('div', { class: 'sb' }, [cnt, h('span', { text: '剩余空间：9.2 GB', style: 'margin-left:auto' })])]);
    } });
  }
  WM.register('qqfiles', { open: () => Q.on('files') ? open() : WM.alert('群共享', '群共享没有开启（[qq] files）。', { kind: 'info' }) });
  const FOLLOW_FILES = ['的自拍.jpg', '的头像.png', '推荐的歌.mp3', '的壁纸.jpg'];
  Q.sub('follow', ev => { if (!Q.on('files') || !ev.name || Math.random() > .5) return; init(); const f = upload(String(ev.name).slice(0, 8) + FOLLOW_FILES[Math.floor(Math.random() * FOLLOW_FILES.length)], Math.round((.1 + Math.random() * 3) * 10) / 10, String(ev.name).slice(0, 8)); Q.sysLine('<b>' + esc(f.by) + '</b> 向群共享上传了文件：' + esc(f.n)); });
  Q.actions.files = (arg, ev) => { const [what, ...r] = String(arg || 'open').split(':'); if (what === 'open') { WM.open('qqfiles'); return true; } if (what === 'download') { return !!download(r.join(':') || (files && files[0]), ev && ev.name); } return false; };
  Q.files = { open, upload, download, list: () => (init(), files.map(f => f.n)) };
  Q.mods.files = { state: () => ({ count: (init(), files.length) }) };
})();
