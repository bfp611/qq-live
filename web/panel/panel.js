// 手机控制面板（XP / QQ 风格）。令牌：登录后存在 localStorage；二维码里的令牌放在 # 后面（不会发给服务器），读到就存起来并把地址栏清掉。
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const h = (tag, p, kids) => { const e = document.createElement(tag); for (const k in (p || {})) { const v = p[k]; if (k === 'text') e.textContent = v; else if (k === 'class') e.className = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v != null && v !== false) e.setAttribute(k, v === true ? '' : v); } (kids || []).forEach(c => c != null && e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c)); return e; };
  let TOKEN = '', S = null, tab = 'home', busy = false, fails = 0;
  const KEY = 'qqlive.panel.token';
  try { const m = /(?:^#|&)token=([^&]+)/.exec(location.hash); if (m) { localStorage.setItem(KEY, decodeURIComponent(m[1])); history.replaceState(null, '', location.pathname + location.search); } TOKEN = localStorage.getItem(KEY) || ''; } catch (e) {}

  async function api(path, body) {
    const o = { headers: { 'X-Token': TOKEN } };
    if (body !== undefined) { o.method = 'POST'; o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(body); }
    const r = await fetch('/ops/api/' + path, o);
    if (r.status === 401) { showLogin('令牌不对'); throw new Error('401'); }
    if (r.status === 429) { toast('错误次数太多，稍后再试', 1); throw new Error('429'); }
    return r.json();
  }
  function toast(t, bad) { const e = $('toast'); e.textContent = t; e.className = 'toast' + (bad ? ' bad' : ''); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.add('hide'), 2600); }
  function showLogin(msg) { $('login').classList.remove('hide'); $('main').classList.add('hide'); $('bar').classList.add('hide'); $('lerr').textContent = msg || ''; setChip('off', '未登录'); }
  function setChip(c, t) { const e = $('chip'); e.className = 'chip ' + c; e.textContent = t; }
  $('go').onclick = async () => { TOKEN = $('tok').value.trim(); try { localStorage.setItem(KEY, TOKEN); } catch (e) {} fails = 0; try { await refresh(); } catch (e) {} };
  $('tok').addEventListener('keydown', e => { if (e.key === 'Enter') $('go').click(); });
  document.querySelectorAll('#bar button').forEach(b => b.onclick = () => go(b.dataset.t));
  function go(t) { tab = t; document.querySelectorAll('#bar button').forEach(b => b.classList.toggle('on', b.dataset.t === t)); document.querySelectorAll('.tab').forEach(s => s.classList.toggle('hide', s.id !== 't-' + t)); render(); }

  const fmtDur = s => { s = Math.max(0, Math.floor(s)); const hh = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60); return (hh ? hh + ' 小时 ' : '') + m + ' 分 ' + (s % 60) + ' 秒'; };
  const clock = ts => { const d = new Date(ts * 1000), p = n => String(n).padStart(2, '0'); return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()); };
  const stBox = (n, l) => h('div', { class: 'st' }, [h('b', { text: String(n == null ? '—' : n) }), h('span', { text: l })]);
  const grp = (t, kids) => h('div', { class: 'grp' }, [h('h4', { text: t })].concat(kids));
  const kv = rows => h('dl', { class: 'kv' }, rows.flatMap(r => [h('dt', { text: r[0] }), h('dd', { text: String(r[1] == null || r[1] === '' ? '—' : r[1]) })]));
  const act = (label, body, o) => h('button', { class: 'btn' + (o && o.cls ? ' ' + o.cls : ''), text: label, onclick: () => doIt(label, body, o) });
  async function doIt(label, body, o) {
    o = o || {}; if (o.confirm && !confirm(o.confirm)) return;
    try { const r = await api(o.path || 'do', body); toast(r.ok ? (o.done || label + ' ✓') : (label + ' 失败：' + (r.error || '')), !r.ok); if (r.ok && o.after) o.after(r); refresh(); } catch (e) { if (String(e.message) !== '401') toast(label + ' 出错：' + e.message, 1); }
  }

  // ---------- 真人验证守护：红色提醒条 + 状态 ----------
  function renderAlarm() {
    const el = $('alarm'), g = S && S.guard, a = g && g.alert;
    if (!a) { el.classList.add('hide'); el.replaceChildren(); return; }
    el.classList.remove('hide'); el.classList.toggle('test', !!a.test);
    const left = a.left != null && a.left > 0 ? '（倒计时约 ' + a.left + ' 秒）' : '';
    el.replaceChildren(h('b', { text: (a.test ? '测试：' : '') + a.body + left }),
      h('small', { text: clock(a.at) + ' · ' + (a.push || '') }),
      h('button', { text: a.test ? '知道了' : '我已处理 / 静音提醒', onclick: async () => { try { await api('do', { action: 'guard_ack' }); } catch (e) {} refresh(); } }));
  }
  function guardGrp() {
    const g = S.guard || {};
    return grp('真人验证守护', [kv([['状态', g.enabled ? '开（只通知，不碰直播伴侣）' : '关'], ['盯日志', g.log_watch ? '是：' + (g.log_file || '') : '否'], ['窗口兜底', g.window_watch ? '启用' : '没启用（日志可用时不需要）'],
      ['Bark 推送', g.bark ? (g.bark_key ? '开，密钥已配置' : '开，但没有密钥文件') : '关'], ['Mac 提示音', g.sound ? '开' : '关'],
      ['最近提醒', (g.history && g.history[0]) ? clock(g.history[0].at) + ' ' + g.history[0].kind + '：' + g.history[0].push : '还没有']])]);
  }

  function tipsGrp() {
    const t = S.tips || {}, wl = S.welcome || {}, gf = S.giftfx || {};
    return grp('玩法提示', [kv([['状态', t.enabled ? '开（' + (t.why || '') + '）' : '关'], ['下一条提示', t.enabled ? (t.next_tip_in > 0 ? t.next_tip_in + ' 秒后（要安静才发）' : '随时（等观众安静）') : '—'],
      ['下一次菜单', t.next_menu_in == null ? '没开' : t.next_menu_in + ' 秒后'], ['已发', t.stats ? '提示 ' + t.stats.tips + ' · 演示 ' + t.stats.demos + ' · 菜单 ' + t.stats.menus + ' · 表演 ' + (t.stats.performs || 0) : ''],
      ['最近一条', t.last ? clock(t.last.at) + ' ' + t.last.text : '还没有']]),
      kv(wl.stats ? [['进场接待', wl.enabled ? '开' : '关'], ['接待统计', '进场 ' + wl.stats.enters + ' · 欢迎 ' + wl.stats.lines + '（合并 ' + wl.stats.merged + '，念出来 ' + wl.stats.spoken + '）· 推荐口令 ' + wl.stats.recs],
        ['最近欢迎', wl.last ? clock(wl.last.at) + ' ' + wl.last.text : '还没有']] : []),
      kv(gf.stats ? [['礼物联动', gf.enabled ? '开（队列 ' + gf.queue + (gf.busy ? '，正在放' : '') + '）' : '关'], ['统计', '礼物 ' + gf.stats.gifts + ' · 小烟花 ' + gf.stats.t1 + ' · 表演 ' + gf.stats.t2 + '（点的 ' + gf.stats.requested + '）· 大场面 ' + gf.stats.t3 + ' · 点赞 ' + gf.stats.likes + ' · 新好友 ' + gf.stats.follows],
        ['本场赞', gf.likes + '（下一次 ' + (gf.next_like || '—') + '）· 好友 ' + gf.friends], ['最近一次', gf.last ? clock(gf.last.at) + ' 档' + gf.last.tier + ' ' + (gf.last.who || '') + ' → ' + gf.last.result : '还没有']] : [])]);
  }

  // ---------- 概览 ----------
  function renderHome(el) {
    const s = S, c = s.counts || {}, f = s.fetcher || {}, se = s.session || {};
    el.replaceChildren(
      grp('直播间', [kv([['主播', s.anchor], ['标题', s.title], ['房间', s.room], ['状态', s.live === true ? '直播中' : s.live === false ? '未开播（每 ' + '30' + ' 秒查一次，开播自动连）' : '未知'], ['弹幕连接', f.state + (f.connected ? '（已连上）' : '')],
        ['本场时长', se.active ? fmtDur(se.dur) : '没有进行中的一场'], ['重连次数', f.reconnects], ['最近错误', f.last_error]])]),
      guardGrp(),
      tipsGrp(),
      grp('本场数据', [h('div', { class: 'stats' }, [stBox(s.online, '在线'), stBox(s.total, '累计观看'), stBox(c.chat, '弹幕'), stBox(c.gift, '礼物'), stBox(c.diamonds, '抖币标价'), stBox(c.follow, '关注'), stBox(c.like, '点赞'), stBox(c.member, '进场'), stBox(s.pages, '直播页面')])]),
      grp('系统', [kv([['服务已运行', fmtDur(s.uptime)], ['看门狗', s.supervised ? '有（崩溃自动重启）' : '没有（用 ./live.sh 启动才有）'], ['AI 主播', s.host ? '在线' : '没启动（要有页面连着）'], ['桌面 agent 页面', s.agent_clients], ['冷场玩电脑', (s.idle && s.idle.cur) || '空闲'],
        ['面板改过的开关', s.overrides + ' 个'], ['日志写入错误', s.errors]])]),
      grp('复盘', [h('p', { class: 'muted', text: s.report.last ? '最近：' + s.report.last.sid + '（共 ' + s.report.count + ' 份）' : '下播后自动生成（共 ' + s.report.count + ' 份）' }),
        h('div', { class: 'row' }, [act(s.report.busy ? '生成中…' : '现在生成复盘', {}, { path: 'report', done: '已生成', after: () => {} }), h('a', { class: 'btn', href: '/ops/api/report/latest.html?token=' + encodeURIComponent(TOKEN), target: '_blank', text: '打开最近一份' })])]));
  }

  // ---------- 弹幕 ----------
  async function renderChat(el) {
    let d; try { d = await api('recent?n=80'); } catch (e) { return; }
    const ul = h('ul', { class: 'chat' }, d.items.map(x => h('li', {}, [h('time', { text: clock(x.ts) }),
      x.k === 'gift' ? h('span', { class: 'g' }, [x.name + ' 送出 ' + x.text + (x.count > 1 ? '×' + x.count : '')]) : x.k === 'follow' ? h('span', { class: 'f' }, [x.name + ' 关注了主播']) : h('span', {}, [h('span', { class: 'n', text: x.name + '：' }), x.text])])));
    el.replaceChildren(grp('最近弹幕（新的在上）', [d.items.length ? ul : h('p', { class: 'muted', text: '还没有弹幕（没开播或没人说话）' })]));
  }

  // ---------- 开关 ----------
  function renderSw(el) {
    const kids = S.switches.map(g => grp(g.title, g.items.map(it => {
      const inp = h('input', { type: 'checkbox', onchange: async () => { try { const r = await api('toggle', { key: it.key, on: inp.checked }); toast(r.ok ? (it.label + (inp.checked ? ' 已开' : ' 已关') + (r.reload ? '（要刷新直播页面才生效）' : '')) : r.error, !r.ok); } catch (e) { inp.checked = !inp.checked; } refresh(); } });
      inp.checked = it.on;
      return h('div', { class: 'sw' }, [h('label', {}, [it.label, it.reload ? h('small', { text: '需刷新页面' }) : null, it.changed ? h('em', { text: '已改' }) : null]), h('span', { class: 'tg' }, [inp, h('i')])]);
    })));
    kids.push(grp('页面 / 重置', [h('p', { class: 'muted', text: '开关改的是运行中的服务（并记在 data/ops_overrides.json，下次启动还在），不会改 config.ini。标「需刷新页面」的，改完点下面的按钮。' }),
      h('div', { class: 'row' }, [act('刷新直播页面', {}, { path: 'reload', done: '已通知直播页面刷新' }), act('还原为 config.ini', {}, { path: 'reset', confirm: '把面板改过的开关全部还原成 config.ini 里的值？', done: '已还原' })])]));
    if (!el.dataset.k || el.dataset.k !== JSON.stringify(S.switches)) { el.dataset.k = JSON.stringify(S.switches); el.replaceChildren(...kids); }
  }

  // ---------- 控制 ----------
  let formState = { say: '', emo: '平静', vt: '', vo: '', vs: '60', name: '' };
  function renderDo(el) {
    if (el.dataset.built) return; el.dataset.built = 1;
    const inp = (k, type, ph) => { const i = h(type === 'textarea' ? 'textarea' : 'input', { type: type === 'textarea' ? null : (type || 'text'), placeholder: ph, oninput: () => { formState[k] = i.value; } }); i.value = formState[k]; return i; };
    const emo = h('select', { onchange: e => { formState.emo = e.target.value; } }, ['平静', '开心', '兴奋', '得意', '害羞', '惊讶', '难过', '生气', '挥手'].map(x => h('option', { value: x, text: x })));
    el.replaceChildren(
      grp('让主播说话', [inp('say', 'text', '想让猪猪侠说的话（会走 TTS）'), h('div', { class: 'row' }, [emo, h('button', { class: 'btn pri', text: '说！', onclick: () => doIt('主播说话', { action: 'say', text: formState.say, emotion: emo.value }, { done: '主播说话了' }) })])]),
      grp('点歌 / 音乐', [h('div', { class: 'row' }, [act('切歌', { action: 'skip_song' }), act('清空点歌队列', { action: 'clear_queue' }, { confirm: '清空点歌队列？' }), act('点评这首歌', { action: 'song_comment' })])]),
      grp('投票', [inp('vt', 'text', '标题（如：下一首唱什么）'), inp('vo', 'textarea', '选项，用 | 分开（如：晴天|七里香|夜曲）'), h('div', { class: 'row' }, [inp('vs', 'number', '秒数'), h('button', { class: 'btn pri', text: '发起投票', onclick: () => doIt('发起投票', { action: 'vote_start', title: formState.vt, options: formState.vo, secs: +formState.vs || 60 }) }), act('结束投票', { action: 'vote_end' })])]),
      grp('小游戏', [h('div', { class: 'row' }, [act('成语接龙', { action: 'game_start', game: 'idiom' }), act('猜歌名', { action: 'game_start', game: 'song' }), act('脑筋急转弯', { action: 'game_start', game: 'riddle' })]), h('div', { class: 'row' }, [act('结束游戏', { action: 'game_stop' }), act('点评屏幕', { action: 'screen_comment' })])]),
      grp('特效 / 彩蛋', [h('div', { class: 'row' }, [act('烟花', { action: 'fx', kind: 'fireworks' }), act('流星雨', { action: 'fx', kind: 'meteor' }), act('表情雨', { action: 'fx', kind: 'emoji' }), act('中毒（假）', { action: 'fx', kind: 'virus' })]),
        h('div', { class: 'row' }, [act('抖一抖群聊', { action: 'shake', target: 'chat' }), act('抖整个桌面', { action: 'shake', target: 'desk' }), act('蓝屏', { action: 'bsod' }, { cls: 'warn', confirm: '真的要蓝屏吗？直播画面会蓝几秒。' })])]),
      grp('观众', [inp('name', 'text', '观众昵称（让主播忘掉 TA 的记忆）'), h('button', { class: 'btn warn', text: '忘记这位观众', onclick: () => doIt('忘记观众', { name: formState.name }, { path: 'forget', confirm: '删除「' + formState.name + '」的全部记忆？', done: '已忘记' }) })]),
      grp('玩法提示（教观众怎么玩）', [h('div', { class: 'row' }, [act('发一条玩法提示', { action: 'tip_now' }, { done: '已发到群聊' }), act('发玩法菜单', { action: 'menu_now' }, { done: '已发到群聊' }), act('演示一个', { action: 'demo_now' }, { done: '猪猪侠开始演示了' }), act('来一场表演', { action: 'perform_now' }, { done: '猪猪侠开始表演了' })]),
        h('div', { class: 'row' }, [act('礼物联动·小烟花', { action: 'giftfx_test', which: '1' }, { done: '已排队' }), act('礼物联动·表演', { action: 'giftfx_test', which: '2' }, { done: '已排队（30 秒内发弹幕点表演，否则随机）' }), act('礼物联动·大场面', { action: 'giftfx_test', which: '3' }, { done: '已排队' }), act('点赞特效', { action: 'giftfx_test', which: 'like' }, { done: '已排队' })]),
        h('p', { class: 'muted', text: '观众不知道能发什么弹幕：安静时会自动往群聊里发一条玩法提示，有时猪猪侠真的演示一遍。这里可以手动触发；开关在「开关」页。演示要页面开着、现在没人在聊天。' })]),
      grp('真人验证守护', [h('div', { class: 'row' }, [act('测试推送', { action: 'guard_test' }, { done: '已发送测试推送（手机和音箱应该会响）' }), act('我已处理 / 静音提醒', { action: 'guard_ack' })]),
        h('p', { class: 'muted', text: '抖音会不定期弹「真人验证」，限时不处理就会被关播。守护只负责通知你（手机 Bark + 音箱 + 这里的红条），不会替你点任何东西。开关在「开关」页第一组。' })]),
      grp('服务', [h('div', { class: 'row' }, [act('刷新直播页面', {}, { path: 'reload', done: '已通知直播页面刷新' }), act('重启服务', {}, { path: 'restart', cls: 'warn', confirm: '重启服务？几秒钟直播画面会断一下（页面会自动重连）。', done: '正在重启，几秒后自动重连', after: () => { setChip('wait', '重启中'); } })]),
        h('p', { class: 'muted', text: '「蓝屏 / 特效 / 抖动」需要直播页面开着（?desk=xp）。重启时：有看门狗就由它拉起，没有就原地重新执行。' })]));
  }

  // ---------- 切片 ----------
  const fmtSize = n => n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB';
  const clipUrl = n => '/ops/api/clip/' + encodeURIComponent(n) + '?token=' + encodeURIComponent(TOKEN);
  function renderClips(el) {
    const c = S.clips; if (!c) { el.replaceChildren(h('p', { class: 'muted', text: '这个版本没有切片模块' })); return; }
    if (!el.dataset.built) { el.dataset.built = 1; el.replaceChildren(h('div', { id: 'cl-st' }), h('div', { id: 'cl-list' })); }
    const st = el.querySelector('#cl-st'), list = el.querySelector('#cl-list');
    const rec = c.recording, since = c.since ? fmtDur(Date.now() / 1000 - c.since) : '';
    const permBad = c.perm && c.perm.ok === false;
    st.replaceChildren(
      grp('录制状态', [kv([['录制', !c.enabled ? '模块关着（开关页）' : rec ? '录着：' + since + '（缓冲 ' + c.buffer_secs + ' 秒，' + c.segments + ' 段' + (c.encoder ? '，' + c.encoder : '') + '）' : c.want ? '正在启动…' : (c.mode === 'live' ? '没开播，不录' : '没在录')],
          ['屏幕录制权限', c.perm && c.perm.ok === true ? '已授权' : permBad ? '没授权' : '还没检测 / 不适用'], ['待剪', c.pending], ['已剪', c.stats.clips + ' 条（失败 ' + c.stats.failed + '，合并 ' + c.stats.skip_close + '）'], ['观众点的', c.stats.viewer + ' 次'],
          ['最近', c.last ? (c.last.ok ? c.last.name : '失败：' + c.last.error) : '—']]),
        permBad ? h('div', { class: 'perm bad', text: '⚠ ' + c.perm.msg }) : null, c.err && !permBad ? h('div', { class: 'perm', text: c.err }) : null,
        h('div', { class: 'row' }, [act('现在切一个', { action: 'clips_now' }, { done: '已记下，约 ' + 18 + ' 秒后剪好' }), act(c.manual ? '停止手动录制' : '开始录制', { action: 'clips_record', on: !c.manual }, { done: c.manual ? '已停止手动录制' : '已开始手动录制（下播不会自动停）' }), act('重新检测权限', { action: 'clips_check' }, { done: '检测完成' })]),
        h('p', { class: 'muted', text: '开播时自动录直播窗口，高光时刻（蓝屏 / 熊猫烧香 / 假重启 / 烟花 / 大礼 / 观众发「高光」）剪成竖屏。开关在「开关」页。' })]));
    const key = JSON.stringify(c.files.map(f => f.name));
    if (list.dataset.k !== key) {
      list.dataset.k = key;
      list.replaceChildren(grp('切片（新的在上，共 ' + c.count + ' 条，' + fmtSize(c.bytes) + '）', c.files.length ? c.files.map(f => {
        const row = h('div', { class: 'cl' });
        const th = h('div', { class: 'th', style: f.thumb ? 'background-image:url(' + clipUrl(f.name.replace(/\.mp4$/, '.jpg')) + ')' : '' });
        const play = () => { const v = h('video', { controls: true, autoplay: true, playsinline: true, src: clipUrl(f.name) }); th.replaceWith(v); row.classList.add('big'); };
        th.onclick = play;
        row.append(th, h('div', { class: 'inf' }, [h('b', { text: f.label }), h('small', { text: new Date(f.at * 1000).toLocaleString() + ' · ' + fmtSize(f.size) }), h('div', { class: 'acts' }, [
          h('button', { class: 'btn', text: '预览', onclick: play }), h('a', { class: 'btn', text: '下载', href: clipUrl(f.name), download: f.name, style: 'text-decoration:none;text-align:center' }),
          h('button', { class: 'btn warn', text: '删除', onclick: async () => { if (!confirm('删除这条切片？')) return; try { const r = await api('do', { action: 'clips_delete', name: f.name }); toast(r.ok ? '已删除' : '删除失败：' + (r.error || ''), !r.ok); if (r.ok) { list.dataset.k = ''; refresh(); } } catch (e) {} } })])]));
        return row;
      }) : [h('p', { class: 'muted', text: '还没有切片' })]));
    }
  }

  // ---------- 剧情 ----------
  function renderStory(el) {
    const s = S.story; if (!s) { el.replaceChildren(h('p', { class: 'muted', text: '这个版本没有剧情模块' })); return; }
    const se = s.sess, ls = s.last, st = s.stats;
    el.replaceChildren(
      grp('剧情日期', [kv([['模块', s.enabled ? '开着' : '关着（开关页）'], ['XP 里今天是', s.label + (s.started ? '（第 ' + (s.day + 1) + ' 个直播日）' : '（还没开过播）')],
          ['这一场', se ? (se.live ? '直播中 ' : '已下播（等写日记）') + se.minutes + ' 分钟 · 弹幕 ' + se.chats + ' · 活跃 ' + se.viewers + ' 人 · 礼物 ' + se.gifts + ' · 高光 ' + se.hl + ' · 关注 ' + se.follows : '没有（下次开播开始记）']]),
        h('div', { class: 'row' }, [act('往后走一天', { action: 'story_day' }, { done: '日期往后走了一天', confirm: '把剧情日期往后走一天？' })])]),
      grp('QQ空间日记', [kv([['日记', s.diaries + ' 篇（已发表 ' + s.published + '，待发表 ' + s.pending + '，没念过 ' + s.unread + '）'], ['正在写', s.busy || s.closing ? '是（' + s.closing + ' 场排队）' : '否'],
          ['统计', '写了 ' + st.diaries + '（LLM ' + st.diaries_llm + '），发表 ' + st.published + '，念过 ' + st.reads + '，太短跳过 ' + st.skipped]]),
        ls ? h('div', { class: 'perm' }, [h('b', { text: '《' + ls.title + '》 ' + ls.date + (ls.published ? '' : '（待发表）') + (ls.how ? ' · ' + ls.how : '') }), h('div', { text: ls.text })]) : h('p', { class: 'muted', text: '还没有日记' }),
        s.err ? h('div', { class: 'perm bad', text: s.err }) : null,
        h('div', { class: 'row' }, [act('现在写一篇', { action: 'story_diary' }, { done: '日记写好了（开播时发表，或点「现在发表」）' }), act('现在发表', { action: 'story_publish' }, { done: '已发表到 QQ空间' }), act('现在念一篇', { action: 'story_read' }, { done: '猪猪侠开始翻日记' })])]),
      grp('观众记忆', [kv([['记下的话', st.quotes + ' 句'], ['欢迎时带的记忆', st.recalls + ' 次'], ['被要求忘记', st.forgets + ' 次']]),
        h('p', { class: 'muted', text: '只记昵称 + 行为（来过几次 / 常玩的口令）+ 几句过滤后的短弹幕，存在积分存档里；观众发「忘记我」就清掉。开关在「开关」页。' })]));
  }

  // ---------- 队列 ----------
  function renderQ(el) {
    const s = S, m = s.music, jb = s.jukebox, v = s.vote, g = s.game;
    const cur = m && m.on ? '《' + m.title + '》' + m.artist + (m.playing ? '' : '（暂停）') : '没有检测到播放';
    const pct = m && m.duration ? Math.min(100, (m.pos || 0) / m.duration * 100) : 0;
    el.replaceChildren(
      grp('正在播放', [h('div', {}, [cur]), m && m.on ? h('div', { class: 'bar2' }, [h('i', { style: 'width:' + pct + '%' })]) : null, h('p', { class: 'muted', text: jb ? (jb.on ? '点歌已开启' : '点歌已关闭') : '点歌没启用（[music]）' })]),
      grp('点歌队列', [jb && jb.current ? h('p', {}, ['点歌中：《' + jb.current.title + '》' + jb.current.artist + '（' + jb.current.user + '）']) : null,
        jb && jb.queue.length ? h('ol', { class: 'q' }, jb.queue.map(x => h('li', { text: '《' + x.title + '》' + x.artist + '（' + x.user + '）' }))) : h('p', { class: 'muted', text: '队列是空的' })]),
      grp('投票', [v ? h('div', {}, [h('b', { text: v.title + (v.state === 'open' ? '（还剩 ' + Math.ceil(v.left) + ' 秒）' : '（已结束）') }), h('ol', { class: 'q' }, v.opts.map(o => h('li', { text: o.label + ' — ' + o.count + ' 票' + (v.state !== 'open' && v.winner === o.n ? '  ← 胜出' : '') })))]) : h('p', { class: 'muted', text: '没有投票' })]),
      grp('小游戏', [g ? h('div', {}, [h('b', { text: g.name + (g.state === 'done' ? '（已结束）' : '（第 ' + g.round + ' 题）') }), h('p', { text: g.prompt || '' }), h('ol', { class: 'q' }, (g.board || []).map(b => h('li', { text: b.name + ' ' + b.pts + ' 分' })))]) : h('p', { class: 'muted', text: '没有进行中的游戏' })]));
  }

  function render() {
    if (!S) return;
    const el = $('t-' + tab);
    ({ home: renderHome, chat: renderChat, sw: renderSw, do: renderDo, clips: renderClips, story: renderStory, q: renderQ })[tab](el);
  }
  async function refresh() {
    if (busy || !TOKEN) { if (!TOKEN) showLogin(''); return; }
    busy = true;
    try {
      S = await api('state');
      $('login').classList.add('hide'); $('main').classList.remove('hide'); $('bar').classList.remove('hide');
      const lv = S.live === true;
      setChip(lv ? 'live' : S.live === false ? 'off' : 'wait', lv ? '直播中' : S.live === false ? '未开播' : '连接中');
      renderAlarm(); render();
    } catch (e) { if (String(e.message) !== '401') setChip('off', '断开，重连中…'); }
    busy = false;
  }
  setInterval(() => { if (!document.hidden) refresh(); }, 2000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  refresh();
  window.PANEL = { state: () => S, go, refresh };
})();
