// 观众互动的窗口（?desk=xp，[play]）：投票窗口（实时柱状图）/ 切歌投票进度 / QQ积分排行榜（日榜 / 总榜）。数据全部来自服务端（backend/play/）。
(function () {
  const P = window.PLAYX; if (!P) return;
  const { h, esc } = WM;
  const css = document.createElement('style');
  css.textContent = `
    .pv, .pr, .ps { display:flex; flex-direction:column; height:100%; background:#fff; font:12px var(--xpfont); color:#000; box-sizing:border-box; }
    .pv .hd { padding:8px 12px 6px; background:linear-gradient(#f4f8ff,#d5e6fb); border-bottom:1px solid #7f9db9; } .pv .hd b { font-size:14px; color:#0a246a; } .pv .hd .sub { color:#555; margin-top:3px; display:flex; justify-content:space-between; }
    .pv .tm { height:12px; margin:6px 12px 0; border:1px solid #686868; border-radius:2px; padding:1px; background:#fff; box-sizing:border-box; } .pv .tm i { display:block; height:100%; background:repeating-linear-gradient(90deg,#37d12c 0 6px,#fff 6px 8px); transition:width .4s linear; }
    .pv .ops { flex:1; overflow:auto; padding:8px 12px; } .pv .vo { margin-bottom:9px; } .pv .vo .lb { display:flex; justify-content:space-between; margin-bottom:2px; } .pv .vo .lb span:first-child { font-weight:700; }
    .pv .vo .tr { height:18px; border:1px solid #7f9db9; background:#fff; border-radius:2px; position:relative; overflow:hidden; } .pv .vo .fl { height:100%; width:0; background:linear-gradient(#8fc0ff,#3d82e8 55%,#2a62c4); transition:width .45s ease; }
    .pv .vo .tr span { position:absolute; left:6px; top:1px; line-height:16px; color:#000; text-shadow:0 0 2px #fff, 0 0 2px #fff; } .pv .vo.win .fl { background:linear-gradient(#a6f08e,#3bbf2a 55%,#25991a); } .pv .vo.win .lb span:first-child:after { content:'  ★ 胜出'; color:#c60; } .pv .vo.lose { opacity:.7; }
    .pv .ft { flex:none; padding:5px 12px; background:#ece9d8; border-top:1px solid #aca899; color:#444; display:flex; justify-content:space-between; }
    .ps { padding:10px 14px; justify-content:center; gap:7px; } .ps .t { font-weight:700; color:#0a246a; } .ps .bar { height:16px; border:1px solid #686868; border-radius:2px; padding:1px; box-sizing:border-box; } .ps .bar i { display:block; height:100%; width:0; background:repeating-linear-gradient(90deg,#37d12c 0 6px,#fff 6px 8px); transition:width .4s; } .ps .n { color:#444; }
    .pr .tb { height:34px; flex:none; display:flex; align-items:center; gap:6px; padding:0 8px; background:linear-gradient(#f4f8ff,#d5e6fb); border-bottom:1px solid #7f9db9; } .pr .tb .xbtn.on { box-shadow: inset 0 0 0 2px #fff1d8, inset 0 0 0 3px #f8b330; font-weight:700; }
    .pr .ls { flex:1; overflow:auto; } .pr table { width:100%; border-collapse:collapse; } .pr th { text-align:left; font-weight:400; padding:3px 8px; background:#ece9d8; border:1px solid #d6d2c2; position:sticky; top:0; }
    .pr td { padding:3px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap; } .pr tr.r1 td { background:#fff4c2; } .pr tr.r2 td { background:#eef0f4; } .pr tr.r3 td { background:#fbe6d4; } .pr td.n { width:46px; text-align:center; font-weight:700; } .pr td.p { text-align:right; font-weight:700; color:#0a246a; } .pr .lvb .lvi { width:14px; height:14px; }
    .pr .sb { height:22px; flex:none; display:flex; align-items:center; gap:12px; padding:0 8px; background:#ece9d8; border-top:1px solid #aca899; color:#444; } .pr .empty { padding:40px 0; text-align:center; color:#888; }`;
  document.head.appendChild(css);
  const ICO = 'xp/ui/qq16.png';

  // ================= 投票窗口 =================
  let autoOpened = false, closeT = 0;
  function renderVote(win, v) {
    const el = win.el, q = s => el.querySelector(s);
    if (!v) { q('.hd b').textContent = '当前没有进行中的投票'; q('.hd .sub').innerHTML = '<span>主播（或 AI）发起投票后，这里会实时出柱状图</span><span></span>'; q('.ops').innerHTML = '<div style="color:#888;padding:30px 0;text-align:center">发起方式：主播在群里发「投票 下一步干啥: 1 玩红警 2 换壁纸 3 扫雷」</div>'; q('.tm i').style.width = '0'; q('.ft span:first-child').textContent = '——'; return; }
    q('.hd b').textContent = v.title; q('.hd .sub').innerHTML = '<span>' + (v.by ? esc(v.by) + ' 发起' : '') + '</span><span>共 ' + v.total + ' 票</span>';
    const ops = q('.ops'), done = v.state !== 'open';
    if (ops.children.length !== v.opts.length || ops.dataset.vid !== String(v.id)) { ops.dataset.vid = v.id; ops.innerHTML = ''; v.opts.forEach(o => ops.appendChild(h('div', { class: 'vo', 'data-n': o.n }, [h('div', { class: 'lb' }, [h('span', { text: o.n + '  ' + o.label }), h('span', { class: 'c' })]), h('div', { class: 'tr' }, [h('div', { class: 'fl' }), h('span', { class: 'pc' })])]))); }
    v.opts.forEach((o, i) => {
      const row = ops.children[i], pct = v.total ? Math.round(o.count * 100 / v.total) : 0;
      row.querySelector('.c').textContent = o.count + ' 票'; row.querySelector('.fl').style.width = pct + '%';
      row.querySelector('.pc').textContent = pct + '%'; row.classList.toggle('win', done && v.winner === o.n); row.classList.toggle('lose', done && v.winner && v.winner !== o.n);
    });
    q('.tm i').style.width = (v.state === 'open' ? Math.max(0, Math.min(100, v.left * 100 / v.secs)) : 0) + '%';
    q('.ft span:first-child').textContent = v.state === 'open' ? '在群聊里发送数字 1~' + v.opts.length + ' 参与投票（剩余 ' + Math.ceil(v.left) + ' 秒）' : v.state === 'cancelled' ? '投票已取消' : (v.winner ? '结果：' + v.winner + ' 号「' + v.opts[v.winner - 1].label + '」胜出' + (v.note ? '（' + v.note + '）' : '') : (v.note || '投票结束'));
    q('.ft span:last-child').textContent = v.state === 'open' ? '进行中' : '已结束';
  }
  const vwin = () => { const w = WM.byId.vote; return w && !w.closed ? w : null; };
  function openVote(o) {
    return WM.create({ id: 'vote', title: '投票 - GG-Bond 的直播间', icon: ICO, w: 340, h: 310, minW: 280, minH: 220, x: 130, y: 60, content: win => {
      const root = h('div', { class: 'pv' }, [h('div', { class: 'hd' }, [h('b'), h('div', { class: 'sub' })]), h('div', { class: 'tm' }, [h('i')]), h('div', { class: 'ops' }), h('div', { class: 'ft' }, [h('span'), h('span')])]);
      win.pv = { render: v => renderVote(win, v), state: () => ({ opts: win.el.querySelectorAll('.vo').length, vote: P.vote }) };
      setTimeout(() => renderVote(win, P.vote), 0);
      const iv = setInterval(() => { if (win.closed) return clearInterval(iv); const v = P.vote; if (v && v.state === 'open') { v.left = Math.max(0, v.left - 0.5); renderVote(win, v); } }, 500);
      win.o.onclose = () => { clearInterval(iv); autoOpened = false; };
      return root;
    } });
  }
  WM.register('vote', { open: () => P.on('vote') ? openVote() : WM.alert('投票', '投票没有开启（[play] vote）。', { kind: 'info' }) });
  P.sub('vote', ev => {
    const v = ev.vote; if (!v || !P.on('vote')) return;
    if (v.state === 'open' && P.cfg.vote_window && !vwin()) { autoOpened = true; clearTimeout(closeT); WM.open('vote'); if (window.XP && XP.snd) XP.snd('notify', 'qq'); }
    const w = vwin(); if (w) w.pv.render(v);
    if (v.state !== 'open' && autoOpened && w) { clearTimeout(closeT); closeT = setTimeout(() => { const w2 = vwin(); if (w2 && autoOpened) w2.close(); }, Math.max(3, P.cfg.vote_close_secs) * 1000); }
  });

  // ================= 切歌投票进度 =================
  let skipT = 0;
  const swin = () => { const w = WM.byId.skipvote; return w && !w.closed ? w : null; };
  function renderSkip(win, s) {
    const q = x => win.el.querySelector(x);
    q('.t').textContent = s.done ? '切歌投票通过，正在切歌…' : '切歌投票：' + (s.song ? '《' + s.song + '》' : '当前歌曲');
    q('.bar i').style.width = Math.min(100, s.have * 100 / Math.max(1, s.need)) + '%';
    q('.n').textContent = s.done ? (s.by ? s.by + ' 投出了关键一票' : '') : s.have + ' / ' + s.need + ' 票（在线观众 ' + s.active + ' 人，发「切歌」参与）';
  }
  P.sub('skip', ev => {
    const s = ev.skip; if (!s || !P.on('skip_vote') || !P.cfg.skip_panel) return;
    if (!swin()) WM.create({ id: 'skipvote', title: '切歌投票', icon: ICO, w: 320, h: 118, x: 140, y: 400, resizable: false, content: win => h('div', { class: 'ps' }, [h('div', { class: 't' }), h('div', { class: 'bar' }, [h('i')]), h('div', { class: 'n' })]) });
    const w = swin(); if (!w) return; renderSkip(w, s); P.mods.skipwin = w;
    clearTimeout(skipT); skipT = setTimeout(() => { const w2 = swin(); if (w2) w2.close(); }, s.done ? 4000 : Math.max(6, (s.left || 10) + 2) * 1000);
  });

  // ================= 积分排行榜 =================
  function openRank() {
    return WM.create({ id: 'rank', title: 'QQ积分排行榜 - GG-Bond 的直播间', icon: ICO, w: 420, h: 400, minW: 320, minH: 240, content: win => {
      let by = P.store.get('rank_by', 'day'), rows = [], timer = 0, scope = '';
      const tb = h('tbody'), sb = h('span'), btns = {};
      const draw = () => {
        tb.innerHTML = '';
        rows.forEach(r => tb.appendChild(h('tr', { class: r.rank <= 3 ? 'r' + r.rank : '', 'data-uid': r.uid }, [
          h('td', { class: 'n', text: r.rank === 1 ? '🥇' : r.rank === 2 ? '🥈' : r.rank === 3 ? '🥉' : String(r.rank) }),
          h('td', { html: (r.lv ? '<span class="lvb">' + P.icoHtml(r.lv) + '</span>' : '') + esc(r.name) }), h('td', { text: 'Lv.' + r.lv }), h('td', { class: 'p', text: String(r.pts) })])));
        if (!rows.length) tb.appendChild(h('tr', {}, [h('td', { colspan: 4, class: 'empty', text: by === 'day' ? '今天还没有人拿到积分——发弹幕、送礼物、点赞、关注都能涨分' : '还没有积分记录' })]));
        sb.textContent = (by === 'day' ? '日榜' : '总榜') + ' · 共 ' + rows.length + ' 人上榜 · 每 4 秒刷新 · 数据保存在本机';
        Object.keys(btns).forEach(k => btns[k].classList.toggle('on', k === by));
      };
      const load = () => fetch('play/rank.json?by=' + by + '&n=50' + (P.room ? '&room=' + encodeURIComponent(P.room) : '')).then(r => r.json()).then(d => { if (win.closed) return; rows = d.rows || []; scope = d.scope; draw(); }).catch(() => {});
      const tab = (k, t) => (btns[k] = h('button', { class: 'xbtn', 'data-by': k, text: t, onclick: () => { by = k; P.store.set('rank_by', k); draw(); load(); } }));
      const bar = h('div', { class: 'tb' }, [tab('day', '日榜'), tab('total', '总榜'), h('button', { class: 'xbtn', 'data-act': 'refresh', text: '刷新', onclick: load })]);
      timer = setInterval(() => { if (win.closed) return clearInterval(timer); load(); }, 4000); win.o.onclose = () => clearInterval(timer);
      win.pr = { by: k => { by = k; draw(); return load(); }, rows: () => rows.slice(), state: () => ({ by, n: rows.length, scope }) };
      draw(); load();
      return h('div', { class: 'pr' }, [bar, h('div', { class: 'ls' }, [h('table', {}, [h('thead', {}, [h('tr', {}, ['名次', '昵称', '等级', '积分'].map(t => h('th', { text: t })))]), tb])]), h('div', { class: 'sb' }, [sb])]);
    } });
  }
  WM.register('rank', { open: () => P.on('points') ? openRank() : WM.alert('QQ积分排行榜', '积分没有开启（[play] points）。', { kind: 'info' }) });
  P.mods.ui = { openVote, openRank };
})();
