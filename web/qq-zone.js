// QQ空间（?desk=xp）：2007 年风格的个人空间窗口 —— 日志 / 相册 / 留言板 / 音乐盒 / 最近访客。
//  · 留言板：直播间弹幕会变成“留言”（[qq] zone_msgs = off / keyword / sample / all）
//  · 最近访客：真实观众（发过弹幕 / 送过礼物 / 关注过的人，来自 QQX.viewers）
//  · 背景音乐小部件：显示千千静听里当前网易云正在播放的歌
//  · 日志：几篇老日志 + 自己写的（AI 冷场时也会写）；相册：猪猪侠姿势图 + 怀旧壁纸
// 界面是自制的仿制品（没有用腾讯 QQ空间的原版素材），数据存在浏览器 localStorage。
(function () {
  const Q = window.QQX; if (!Q) return;
  const { h, esc } = WM;
  const hash = s => { let x = 5381; for (let i = 0; i < s.length; i++) x = ((x << 5) + x + s.charCodeAt(i)) >>> 0; return x; };
  const avatarOf = uid => 'img/avatar/' + (hash('a' + uid) % 117 + 1) + '.png', qqnum = uid => String(10000 + hash('q' + uid) % 2000000000 + (hash(uid) % 7) * 1000).slice(0, 10);
  const WALLS = ['bliss', 'autumn', 'azul', 'ascent', 'blue_hills'];
  const ALBUMS = [{ id: 'gg', name: '猪猪侠的日常', desc: '18 张表情包', photos: Array.from({ length: 18 }, (_, i) => ({ src: 'gg/p' + String(i).padStart(2, '0') + '.webp', cap: ['开心', '写日记', '吃糖', '吹喇叭', '生气', '委屈', '困了', '睡着了', '站军姿', '打招呼', '犯困', '吃饼干', '大喊', '不爽', '害羞', '耶！', '比心', '睡懒觉'][i] })), cover: 'gg/p00.webp', fit: 'contain' },
    { id: 'wall', name: '怀旧壁纸', desc: 'XP 经典壁纸', photos: null, cover: 'xp/wall/bliss.jpg', fit: 'cover' }];
  let WALL_LIST = null;
  const SEED_BLOGS = [
    { title: '今天终于把空当接龙第 617 号通关啦！', text: '熬了一晚上，终于解出来了！\n看着最后那一串牌飞到右上角，心里那个爽啊～\n明天继续挑战 11982 号（听说那个是无解的，不信邪）。', reads: 128, t: Date.UTC(2007, 5, 12, 13, 20) },
    { title: '转：十条让你的QQ空间更漂亮的小技巧', text: '1. 换个好看的背景音乐\n2. 装扮里选个自己喜欢的皮肤\n3. 相册里放几张自己的照片\n4. 日志别总写“无题”\n……（转载自网络，转载请保留出处）', reads: 342, t: Date.UTC(2007, 3, 3, 8, 5) },
    { title: '超级棒棒糖测评', text: '今天试吃了新口味的棒棒糖，草莓味的最好吃，甜而不腻！\n五颗星，推荐给各位小伙伴～\n（备注：正义的猪猪侠不会吃太多糖，会长蛀牙。）', reads: 96, t: Date.UTC(2007, 1, 14, 10, 40) },
  ];
  const D = Object.assign({ blogs: SEED_BLOGS.map((b, i) => Object.assign({ id: i + 1 }, b)), msgs: [], visits: 5230 + Math.floor(Math.random() * 400), next: 10, dids: [] }, Q.store.get('zone', {}));
  const save = () => { D.blogs = D.blogs.slice(-40); D.msgs = D.msgs.slice(-120); Q.store.set('zone', D); };
  const ST = () => window.STORY && window.STORY.on && window.STORY.zone ? window.STORY : null;      // 连续剧情（story.js）：QQ空间里的日期跟着剧情日期走
  const shown = o => o.st || (o.id < 10 && !o.by && ST() ? ST().seed(o.id) : o.t);                   // 显示用的时间：写的时候的剧情日期；原有的几篇老日志排在剧情开始之前
  const owner = () => Q.cfg.zone_owner || Q.host || '猪猪侠';
  const fmt = t => { const d = new Date(t), p = n => String(n).padStart(2, '0'); return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes()); };
  const ago = t => { const s = Math.max(1, Math.round((Date.now() - t) / 1000)); return s < 60 ? s + ' 秒前' : s < 3600 ? Math.round(s / 60) + ' 分钟前' : Math.round(s / 3600) + ' 小时前'; };
  const css = document.createElement('style'); css.textContent = `.qz { display:flex; flex-direction:column; height:100%; background:#d7ecff; font:12px/1.55 var(--xpfont); color:#333; } .qz .bn { height:64px; flex:none; display:flex; align-items:center; gap:12px; padding:0 14px; background:linear-gradient(#6fc0ff,#bfe5ff 75%,#e5f4ff); border-bottom:2px solid #f5a623; position:relative; overflow:hidden; }
    .qz .bn:before { content:''; position:absolute; right:60px; top:6px; width:60px; height:22px; border-radius:20px; background:#fff; opacity:.8; box-shadow:24px 8px 0 4px #fff, -30px 10px 0 -2px #fff; } .qz .bn .lg { font:italic 700 24px 'Arial Black',var(--xpfont); color:#ff8a00; text-shadow:2px 2px 0 #fff; letter-spacing:1px; } .qz .bn .own { font:700 15px var(--xpfont); color:#0b4a8f; } .qz .bn .vs { margin-left:auto; color:#0b4a8f; z-index:1; }
    .qz .nv { height:26px; flex:none; display:flex; gap:2px; padding:0 10px; background:#f7fbff; border-bottom:1px solid #8fbce8; align-items:flex-end; } .qz .nv b { padding:3px 13px; cursor:pointer; color:#0b4a8f; font-weight:400; border:1px solid transparent; border-bottom:0; } .qz .nv b:hover { background:#e4f1ff; } .qz .nv b.on { background:#fff; border-color:#8fbce8; font-weight:700; color:#d96c00; position:relative; top:1px; }
    .qz .mn { flex:1; min-height:0; display:flex; gap:8px; padding:8px; } .qz .lf { width:172px; flex:none; display:flex; flex-direction:column; gap:8px; overflow:auto; } .qz .box { background:#fff; border:1px solid #9ec8f0; border-radius:3px; } .qz .box > h4 { margin:0; padding:3px 8px; font-size:12px; background:linear-gradient(#e8f4ff,#cfe6fb); border-bottom:1px solid #9ec8f0; color:#0b4a8f; }
    .qz .pf { padding:8px; text-align:center; } .qz .pf img { width:84px; height:84px; border:1px solid #9ec8f0; padding:2px; background:#fff; } .qz .pf div { margin-top:3px; } .qz .vl { padding:4px 6px; max-height:260px; overflow:auto; } .qz .vl div { display:flex; align-items:center; gap:5px; padding:2px 0; } .qz .vl img { width:24px; height:24px; border:1px solid #cfe0f2; } .qz .vl span { color:#888; font-size:10px; margin-left:auto; white-space:nowrap; } .qz .vl i { font-style:normal; max-width:70px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .qz .ct { flex:1; min-width:0; overflow:auto; display:flex; flex-direction:column; gap:8px; } .qz .post { padding:8px 10px; border-bottom:1px dashed #cfe0f2; } .qz .post h5 { margin:0 0 3px; font-size:13px; color:#0b4a8f; cursor:pointer; } .qz .post h5:hover { text-decoration:underline; } .qz .post .mt { color:#999; font-size:11px; } .qz .post p { margin:4px 0 0; white-space:pre-wrap; }
    .qz .msg { display:flex; gap:8px; padding:7px 10px; border-bottom:1px dashed #cfe0f2; } .qz .msg img { width:40px; height:40px; border:1px solid #9ec8f0; flex:none; } .qz .msg .bd { flex:1; min-width:0; } .qz .msg .nm { color:#0b4a8f; font-weight:700; } .qz .msg .nm small { color:#999; font-weight:400; margin-left:6px; } .qz .msg .rp { margin-top:3px; background:#fff8e1; border-left:3px solid #f5a623; padding:2px 6px; color:#7a5a00; } .qz .msg.new { animation: qzflash 1.4s ease-out; } @keyframes qzflash { from { background:#fff3b0 } to { background:transparent } }
    .qz .alb { display:grid; grid-template-columns:repeat(auto-fill,minmax(116px,1fr)); gap:8px; padding:8px; } .qz .alb .ph { text-align:center; cursor:pointer; } .qz .alb .ph div { height:90px; background:#f2f8ff; border:1px solid #9ec8f0; padding:3px; display:flex; align-items:center; justify-content:center; } .qz .alb .ph img { max-width:100%; max-height:100%; object-fit:contain; } .qz .alb .ph.cv img { width:100%; height:100%; object-fit:cover; } .qz .alb .ph span { display:block; margin-top:2px; }
    .qz form, .qz .fm { padding:8px 10px; display:flex; flex-direction:column; gap:5px; } .qz textarea, .qz input[type=text] { font:12px var(--xpfont); border:1px solid #7f9db9; padding:3px; } .qz textarea { height:56px; resize:none; }
    .qz .mu { height:30px; flex:none; display:flex; align-items:center; gap:8px; padding:0 10px; background:linear-gradient(#ffe9b8,#ffd37a); border-top:1px solid #e0a93a; color:#7a4a00; overflow:hidden; } .qz .mu .ic { font-size:15px; } .qz .mu .tt { flex:1; overflow:hidden; white-space:nowrap; } .qz .mu .tt span { display:inline-block; } .qz .mu .pb { width:90px; height:6px; background:#fff; border:1px solid #c88a1a; border-radius:3px; overflow:hidden; } .qz .mu .pb i { display:block; height:100%; background:#f5a623; } .qz .mu.off { opacity:.6; }
    .qz .ft2 { text-align:center; color:#888; font-size:11px; padding:2px; flex:none; background:#d7ecff; }`;
  document.head.appendChild(css);
  // ---------- 数据操作 ----------
  const REPLY = ['谢谢你的留言～', '哈哈，欢迎常来玩！', '收到！回访你的空间～', '嘿嘿，感谢支持！', '好哒好哒～', '你也要开心哦！'];
  function addMsg(name, text, o) {
    o = o || {}; const m = { id: D.next++, t: Date.now(), name: String(name || '路人').slice(0, 14), uid: o.uid || ('n' + name), text: String(text || '').slice(0, 80) }; if (Math.random() < .3 && !o.noreply) m.reply = REPLY[Math.floor(Math.random() * REPLY.length)];
    if (ST()) m.st = ST().stamp(); D.msgs.push(m); D.visits += 1; save(); document.dispatchEvent(new CustomEvent('qqzone', { detail: { kind: 'msg', msg: m } }));
    if (!(WM.byId.qzone && !WM.byId.qzone.closed) && Date.now() - (addMsg.lb || 0) > 20000 && window.XP && XP.balloon) { addMsg.lb = Date.now(); XP.balloon({ title: 'QQ空间：新留言', text: m.name + '：' + m.text.slice(0, 22), icon: 'xp/ui/qq16.png', ev: 'qq', sound: false, onclick: () => WM.open('qzone', { tab: 'msg' }) }); }
    return m;
  }
  function addBlog(title, text, o) { const b = { id: D.next++, t: Date.now(), title: String(title || '无题').slice(0, 40), text: String(text || '').slice(0, 600), reads: 1, by: o && o.by || '' }; if (ST()) b.st = (o && o.st) || ST().stamp(); if (o && o.diary) b.diary = o.diary; D.blogs.push(b); save(); document.dispatchEvent(new CustomEvent('qqzone', { detail: { kind: 'blog', blog: b } })); return b; }
  const mode = () => Q.on('zone') ? Q.cfg.zone_msgs : 'off';
  let chatN = 0;
  Q.sub('chat', ev => {
    const m = mode(); if (m === 'off' || !ev.text) return; const t = String(ev.text).trim(); let put = null;
    if (m === 'all') put = t; else if (m === 'sample') { if (++chatN % Math.max(1, Q.cfg.zone_msg_sample) === 0) put = t; }
    else { const kws = Q.list(Q.cfg.zone_msg_keywords); const k = kws.find(x => t.startsWith(x) || t.includes(x)); if (k) { put = t.replace(k, '').replace(/^[\s:：,，!！~～]+/, '') || t; } }
    if (put) addMsg(ev.name, put, { uid: ev.uid });
  });
  Q.sub('follow', ev => { if (Q.on('zone')) D.visits += 1; });
  // ---------- 窗口 ----------
  const TABS = [['home', '主页'], ['blog', '日志'], ['album', '相册'], ['msg', '留言板'], ['music', '音乐盒']];
  function open(args) {
    return WM.create({ id: 'qzone', title: owner() + ' 的QQ空间 - QQ空间', icon: 'xp/ui/qq16.png', w: 760, h: 520, minW: 560, minH: 360, content: win => {
      const S = { tab: (args && args.tab) || 'home', album: null, blog: null };
      const ct = h('div', { class: 'ct' }), vl = h('div', { class: 'vl' }), vis = h('b'), nv = h('div', { class: 'nv' }), mu = h('div', { class: 'mu' }), pf = h('div', { class: 'pf' });
      const music = () => (window.DESK && DESK.music && DESK.music.S) || null;
      const empty = t => h('div', { style: 'padding:24px;text-align:center;color:#888', text: t });
      const msgEl = (m, fresh) => h('div', { class: 'msg' + (fresh ? ' new' : ''), 'data-msg': m.id }, [h('img', { src: avatarOf(m.uid) }), h('div', { class: 'bd' }, [h('div', { class: 'nm' }, [h('span', { text: m.name }), h('small', { text: fmt(shown(m)) })]), h('div', { text: m.text }), m.reply ? h('div', { class: 'rp', text: owner() + ' 回复：' + m.reply }) : null].filter(Boolean))]);
      const blogEl = (b, full) => h('div', Object.assign({ class: 'post', 'data-blog': b.id }, b.diary ? { 'data-diary': b.diary } : {}), [h('h5', { text: b.title, onclick: () => { b.reads++; save(); S.blog = b.id; draw(); } }), h('div', { class: 'mt', text: fmt(shown(b)) + ' · 阅读(' + b.reads + ')' + (b.by ? ' · ' + b.by : '') }), h('p', { text: full ? b.text : b.text.split('\n')[0].slice(0, 60) + (b.text.length > 60 || b.text.includes('\n') ? '……' : '') })]);
      const wallList = () => WALL_LIST || (WALL_LIST = ['ascent', 'autumn', 'azul', 'bliss', 'blue_hills', 'crystal', 'follow', 'friend', 'home', 'ripple', 'wind', 'winter'].map(n => ({ src: 'xp/wall/' + n + '.jpg', cap: n })));
      function drawAlbum() {
        ct.innerHTML = ''; const bx = h('div', { class: 'box' }); ct.appendChild(bx);
        if (!S.album) { bx.appendChild(h('h4', { text: owner() + ' 的相册' })); bx.appendChild(h('div', { class: 'alb' }, ALBUMS.map(a => h('div', { class: 'ph cv', 'data-album': a.id, onclick: () => { S.album = a.id; draw(); } }, [h('div', {}, [h('img', { src: a.cover, style: a.fit === 'contain' ? 'object-fit:contain' : '' })]), h('span', { html: '<b>' + esc(a.name) + '</b><br>' + esc(a.desc) })])))); return; }
        const a = ALBUMS.find(x => x.id === S.album), ph = a.photos || wallList();
        bx.appendChild(h('h4', {}, [h('span', { text: '‹ 返回相册列表', style: 'cursor:pointer;margin-right:10px;text-decoration:underline', 'data-act': 'albumback', onclick: () => { S.album = null; draw(); } }), h('span', { text: a.name + '（' + ph.length + ' 张）' })]));
        bx.appendChild(h('div', { class: 'alb' }, ph.map((p, i) => h('div', { class: 'ph', 'data-photo': i, onclick: () => viewPhoto(p, a) }, [h('div', {}, [h('img', { src: p.src, loading: 'lazy' })]), h('span', { text: p.cap })]))));
      }
      function viewPhoto(p, a) { WM.create({ id: 'qzone-photo', title: p.cap + ' - ' + a.name, icon: 'xp/ui/qq16.png', w: 520, h: 420, minW: 280, minH: 220, content: () => h('div', { style: 'height:100%;background:#222;display:flex;align-items:center;justify-content:center' }, [h('img', { src: p.src, style: 'max-width:100%;max-height:100%;object-fit:contain' })]) }); }
      function draw() {
        nv.querySelectorAll('b').forEach(b => b.classList.toggle('on', b.dataset.tab === S.tab)); ct.innerHTML = '';
        if (S.tab === 'album') drawAlbum();
        else if (S.tab === 'blog') {
          const bx = h('div', { class: 'box' }); ct.appendChild(bx);
          if (S.blog === 'new') { const ti = h('input', { type: 'text', class: 'qz-title', placeholder: '日志标题' }), bo = h('textarea', { class: 'qz-body', style: 'height:150px', placeholder: '写点什么吧…' });
            bx.appendChild(h('h4', { text: '写日志' })); bx.appendChild(h('div', { class: 'fm' }, [ti, bo, h('div', {}, [h('button', { class: 'xbtn', 'data-act': 'publish', text: '发表', onclick: () => { if (!ti.value.trim() && !bo.value.trim()) return; const b = addBlog(ti.value.trim() || '无题', bo.value, { by: '' }); S.blog = b.id; draw(); } }), h('button', { class: 'xbtn', text: '取消', style: 'margin-left:6px', onclick: () => { S.blog = null; draw(); } })])])); ti.addEventListener('keydown', e => e.stopPropagation()); bo.addEventListener('keydown', e => e.stopPropagation()); return; }
          const cur = S.blog && D.blogs.find(b => b.id === S.blog);
          if (cur) { bx.appendChild(h('h4', {}, [h('span', { text: '‹ 返回日志列表', style: 'cursor:pointer;text-decoration:underline', 'data-act': 'blogback', onclick: () => { S.blog = null; draw(); } })])); bx.appendChild(blogEl(cur, true)); return; }
          bx.appendChild(h('h4', {}, [h('span', { text: '日志（' + D.blogs.length + '）' }), h('span', { text: '写日志', 'data-act': 'newblog', style: 'float:right;cursor:pointer;text-decoration:underline', onclick: () => { S.blog = 'new'; draw(); } })]));
          D.blogs.slice().sort((a, b) => b.t - a.t).forEach(b => bx.appendChild(blogEl(b)));
        } else if (S.tab === 'msg') {
          const bx = h('div', { class: 'box' }), ta = h('textarea', { class: 'qz-msg', placeholder: '给 ' + owner() + ' 留言…' }); ct.appendChild(bx); ta.addEventListener('keydown', e => e.stopPropagation());
          bx.appendChild(h('h4', { text: '留言板（' + D.msgs.length + '）' + (mode() !== 'off' ? '　· 直播间弹幕会变成留言' + (mode() === 'keyword' ? '（以“' + Q.list(Q.cfg.zone_msg_keywords)[0] + '”等开头的弹幕）' : mode() === 'sample' ? '（每 ' + Q.cfg.zone_msg_sample + ' 条弹幕抽一条）' : '') : '') }));
          bx.appendChild(h('div', { class: 'fm' }, [ta, h('div', {}, [h('button', { class: 'xbtn', 'data-act': 'postmsg', text: '留言', onclick: () => { const v = ta.value.trim(); if (!v) return; addMsg('我', v, { uid: 'me', noreply: true }); ta.value = ''; } })])]));
          if (!D.msgs.length) bx.appendChild(empty('还没有人留言，快来抢沙发！')); D.msgs.slice().reverse().slice(0, 40).forEach(m => bx.appendChild(msgEl(m)));
        } else if (S.tab === 'music') {
          const s = music(), bx = h('div', { class: 'box' }); ct.appendChild(bx); bx.appendChild(h('h4', { text: '音乐盒' }));
          bx.appendChild(h('div', { class: 'fm' }, [h('div', { text: s && s.on ? '♪ 正在播放：' + (s.title || '') + (s.artist ? ' - ' + s.artist : '') : '现在没有在播放音乐（网易云没开 / 没有播放）' }), h('div', { style: 'color:#888', text: '空间背景音乐 = 直播间里千千静听正在播放的歌（来自网易云音乐的「正在播放」）。' })]));
        } else {
          const b1 = h('div', { class: 'box' }), b2 = h('div', { class: 'box' }), b3 = h('div', { class: 'box' }); ct.append(b1, b2, b3);
          b1.appendChild(h('h4', { text: '最新日志' })); D.blogs.slice().sort((a, b) => b.t - a.t).slice(0, 2).forEach(b => b1.appendChild(blogEl(b)));
          b2.appendChild(h('h4', { text: '最新留言' })); if (!D.msgs.length) b2.appendChild(empty('还没有人留言')); D.msgs.slice().reverse().slice(0, 3).forEach(m => b2.appendChild(msgEl(m)));
          b3.appendChild(h('h4', { text: '相册精选' })); b3.appendChild(h('div', { class: 'alb' }, ALBUMS[0].photos.slice(0, 6).map(p => h('div', { class: 'ph' }, [h('div', {}, [h('img', { src: p.src })]), h('span', { text: p.cap })]))));
        }
      }
      function side() {
        pf.innerHTML = '<img src="gg/head8.png" alt=""><div><b>' + esc(owner()) + '</b></div><div style="color:#888">QQ: 10086</div><div style="color:#d96c00">🔶 黄钻 Lv.3</div><div style="color:#666;font-size:11px">个性签名：正义的伙伴，吃糖使我快乐</div>';
        vis.textContent = '访问量：' + D.visits;
        const vs = Q.visitors(Q.cfg.zone_visitors); vl.innerHTML = ''; if (!vs.length) vl.appendChild(h('div', { style: 'color:#888;padding:4px', text: '暂时还没有访客' })); vs.slice(0, 14).forEach(v => vl.appendChild(h('div', { 'data-visitor': v.uid }, [h('img', { src: avatarOf(v.uid) }), h('i', { text: v.name }), h('span', { text: ago(v.last) })])));
      }
      function musicBar() { if (!Q.on('zone_music')) { mu.style.display = 'none'; return; } const s = music(); mu.classList.toggle('off', !(s && s.on)); const pos = s && s.on && DESK.music.nowPos ? DESK.music.nowPos() : 0, pc = s && s.duration ? Math.min(100, pos / s.duration * 100) : 0;
        mu.innerHTML = '<span class="ic">♪</span><div class="tt"><span>' + (s && s.on ? '背景音乐：' + esc(s.title || '') + (s.artist ? ' - ' + esc(s.artist) : '') + (s.playing ? '' : '（已暂停）') : '背景音乐：暂无（网易云没在播放）') + '</span></div><div class="pb"><i style="width:' + pc + '%"></i></div>'; }
      TABS.forEach(([k, t]) => nv.appendChild(h('b', { 'data-tab': k, text: t, onclick: () => { S.tab = k; S.album = null; S.blog = null; draw(); } })));
      const refresh = () => { if (win.closed) return; side(); musicBar(); }; const iv = setInterval(refresh, 1000);
      const onz = e => { if (win.closed) return document.removeEventListener('qqzone', onz); if (e.detail.kind === 'msg' && (S.tab === 'msg' || S.tab === 'home')) { draw(); const f = ct.querySelector('[data-msg="' + e.detail.msg.id + '"]'); f && f.classList.add('new'); } else if (e.detail.kind === 'blog' && S.tab !== 'blog') { /* 不打断 */ } side(); };
      document.addEventListener('qqzone', onz); win.o.onclose = () => { clearInterval(iv); document.removeEventListener('qqzone', onz); };
      D.visits += 1; save(); side(); musicBar(); draw();
      win.qz = { tab: t => { S.tab = t; S.album = null; S.blog = null; draw(); }, state: () => ({ tab: S.tab, album: S.album, blog: S.blog, msgs: D.msgs.length, blogs: D.blogs.length, visitors: Q.visitors().length }), draw };
      return h('div', { class: 'qz' }, [h('div', { class: 'bn' }, [h('span', { class: 'lg', text: '☀ QQ空间' }), h('span', { class: 'own', text: owner() + ' 的空间' }), h('span', { class: 'vs' }, [vis])]), nv, h('div', { class: 'mn' }, [h('div', { class: 'lf' }, [h('div', { class: 'box' }, [h('h4', { text: '个人档' }), pf]), h('div', { class: 'box' }, [h('h4', { text: '最近访客' }), vl])]), ct]), mu, h('div', { class: 'ft2', text: 'Copyright © 2007 QQ空间（怀旧仿制版，数据只存在你的浏览器里）' })]);
    } });
  }
  WM.register('qzone', { open: a => Q.on('zone') ? open(a) : WM.alert('QQ空间', 'QQ空间没有开启（[qq] zone）。', { kind: 'info' }) });
  Q.actions.zone = (arg, ev) => { const [what, ...r] = String(arg || 'open').split(':'); if (what === 'open') { WM.open('qzone', { tab: r[0] }); return true; } if (what === 'msg') { addMsg(ev && ev.name || '路人', r.join(':') || '路过留个言', { uid: ev && ev.uid }); return true; } return false; };
  // 连续剧情：下播后写好、下次开播发表的日记，从 /story.json 同步成一篇篇日志（已经有的不重复）
  function syncDiaries() {
    const S = window.STORY; if (!S || !S.on || !S.diaries) return; let n = 0;
    S.diaries.forEach(d => { if (D.dids.includes(d.id) || D.blogs.some(b => b.diary === d.id)) return; D.dids.push(d.id); D.dids = D.dids.slice(-60); addBlog(d.title, d.text, { by: '日记', diary: d.id, st: S.at(d.date, d.hm) }); n++; });
    return n;
  }
  if (window.STORY) { window.STORY.subs.push(syncDiaries); syncDiaries(); }
  Q.zone = { addMsg, addBlog, syncDiaries, state: () => ({ msgs: D.msgs.length, blogs: D.blogs.length, visits: D.visits, mode: mode() }), data: D };
  Q.mods.zone = { state: () => Q.zone.state() };
})();
