// 观众互动（[play]，?desk=xp）：页面侧核心 —— 配置、等级图标（星星 / 月亮 / 太阳 / 皇冠）、服务端推来的互动事件的分发。
// 积分 / 等级 / 投票 / 切歌投票的“账”都在服务端（backend/play/，存 data/play.json）；这里只负责显示：
//   PLAYX.badge(uid) → 名字前面的等级图标 html（app.js 的群聊和群成员列表会调用）
//   PLAYX.sub('lv'|'snap'|'vote'|'skip', fn) → 订阅服务端推来的 {t:"play"} 事件
// 等级图标是本项目自绘的 SVG（金星、黄月亮、橙太阳、皇冠），不是腾讯原版图标。4 颗星 = 1 个月亮，4 个月亮 = 1 个太阳，4 个太阳 = 1 顶皇冠。
(function () {
  const UQ = new URLSearchParams(location.search);
  const D = {
  enabled: true, commands: true, ai_say: true, points: true, chat_points: 1, chat_min_len: 2, chat_gap: 3, dup_secs: 30, max_per_min: 6, daily_cap: 300,
  like_points: 1, like_per: 10, follow_points: 20, gift_points: 5, gift_value_pts: 0.5, gift_max_pts: 5000, enter_points: 0, level_base: 10,
  levelup_msg: true, points_cmd: true, badges: true, data_file: 'data/play.json', keep_days: 60, vote: true, vote_who: 'anchor', vote_starters: '',
  vote_secs: 60, vote_min_votes: 1, vote_tie: 'random', vote_nobody: 'skip', vote_change: true, vote_max_options: 6, vote_points: 2, vote_execute: true,
  vote_window: true, vote_close_secs: 12, vote_idle: false, vote_idle_options: '玩红警,换壁纸,玩扫雷,画个太阳,下一首', vote_idle_secs: 45, vote_idle_min_viewers: 2,
  skip_vote: true, skip_words: '切歌,下一首,换歌,换一首,跳过,skip,不好听', skip_mode: 'count', skip_count: 3, skip_percent: 30, skip_min: 2, skip_window: 90,
  skip_active_secs: 300, skip_cooldown: 20, skip_anchor_instant: true, skip_panel: true, fx: true, fx_secs: 6, fx_emoji: '🎉,✨,💗,🌹,🎁', fx_virus_secs: 8,
  fx_cooldown: 8, fx_bsod_cooldown: 120, gift_map: '烟花=fireworks,流星雨=meteor,熊猫=virus:panda,蓝屏=bsod,玫瑰花=pet:feed+emoji:🌹,小心心=pet:play+emoji:💗',
  gift_value_map: '88=emoji:🎉,199=outfit:random+emoji:✨,520=outfit:party+fireworks,1000=meteor,2000=fireworks+shake,3000=bsod'
  };
  const typed = (k, v) => { const d = D[k]; if (typeof d === 'boolean') return /^(1|true|yes|on)$/i.test(String(v)); if (typeof d === 'number') { const n = parseFloat(v); return isNaN(n) ? d : n; } return String(v); };
  const P = window.PLAYX = { cfg: Object.assign({}, D), lv: {}, pts: {}, mods: {}, vote: null, skip: null };
  P.apply = c => { for (const k in D) { if (c && c[k] !== undefined) P.cfg[k] = typed(k, c[k]); const u = UQ.get('play_' + k); if (u !== null) P.cfg[k] = typed(k, u); } };
  P.apply({});
  P.on = k => P.cfg.enabled && P.cfg[k] !== false;
  P.list = s => String(s || '').split(/[,，]+/).map(x => x.trim()).filter(Boolean);
  P.room = UQ.get('demo') === '1' || UQ.get('demo') === 'true' ? 'demo' : (UQ.get('room') || '');
  P.ready = fetch('config.json').then(r => r.json()).then(c => { P.apply(c.play || {}); }).catch(() => {}).then(() => {
    // 把 [play] 的礼物映射叠到 [qq] 的上面（同一套引擎：QQX.giftAction / QQX.run，不另起一套）
    if (window.QQX && QQX.addMaps) QQX.addMaps({ gift_map: P.cfg.gift_map, gift_value_map: P.cfg.gift_value_map });
    document.dispatchEvent(new CustomEvent('playready')); return P.cfg;
  });
  // ---- 事件 ----
  const subs = {};
  P.sub = (k, fn) => { (subs[k] = subs[k] || []).push(fn); };
  document.addEventListener('qqev', e => {
    const ev = e.detail || {}; if (ev.t !== 'play' || !P.cfg.enabled) return;
    if (ev.k === 'lv') { P.lv[ev.uid] = ev.lv; P.pts[ev.uid] = ev.pts; P.refresh(); }
    else if (ev.k === 'snap') { Object.assign(P.lv, ev.lv || {}); P.refresh(); }
    else if (ev.k === 'vote') P.vote = ev.vote; else if (ev.k === 'skip') P.skip = ev.skip;
    (subs[ev.k] || []).concat(subs['*'] || []).forEach(f => { try { f(ev); } catch (er) { console.error('play', er); } });
  });
  let rt = 0; P.refresh = () => { if (rt) return; rt = setTimeout(() => { rt = 0; try { window.QQRM && window.QQRM(); } catch (e) {} }, 400); };
  // ---- 等级图标 ----
  const svg = s => 'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">' + s + '</svg>');
  const ICON = {
    star: svg('<polygon points="8,1.2 10,6 15,6.2 11.1,9.4 12.4,14.5 8,11.7 3.6,14.5 4.9,9.4 1,6.2 6,6" fill="#ffc400" stroke="#c98a00" stroke-width="0.8" stroke-linejoin="round"/>'),
    moon: svg('<path d="M11.5 2.2A6.4 6.4 0 1 0 14 11.3 5.2 5.2 0 0 1 11.5 2.2z" fill="#ffd93b" stroke="#c98a00" stroke-width="0.8" stroke-linejoin="round"/>'),
    sun: svg('<g stroke="#e8710a" stroke-width="1.3" stroke-linecap="round"><path d="M8 .8v2.2M8 13v2.2M.8 8H3M13 8h2.2M2.9 2.9l1.5 1.5M11.6 11.6l1.5 1.5M13.1 2.9l-1.5 1.5M4.4 11.6l-1.5 1.5"/></g><circle cx="8" cy="8" r="3.6" fill="#ffae1a" stroke="#d35400" stroke-width="0.8"/>'),
    crown: svg('<path d="M1.5 12.5l-.6-8 3.8 3.4L8 2.6l3.3 5.3 3.8-3.4-.6 8z" fill="#ffc400" stroke="#b97a00" stroke-width="0.8" stroke-linejoin="round"/><rect x="1.6" y="12.4" width="12.8" height="1.8" rx=".4" fill="#e29b00" stroke="#b97a00" stroke-width="0.6"/><circle cx="8" cy="9.6" r="1.1" fill="#e53935"/><circle cx="4.6" cy="10.3" r=".8" fill="#2e7de0"/><circle cx="11.4" cy="10.3" r=".8" fill="#2e7de0"/>')
  };
  P.icons = ICON;
  P.parts = lv => ({ crown: Math.floor(lv / 64), sun: Math.floor((lv % 64) / 16), moon: Math.floor((lv % 16) / 4), star: lv % 4 });
  P.glyphs = lv => { const p = P.parts(lv); return '👑'.repeat(p.crown) + '☀️'.repeat(p.sun) + '🌙'.repeat(p.moon) + '⭐'.repeat(p.star); };
  P.icoHtml = (lv, max) => { const p = P.parts(lv || 0); let s = '', n = 0; for (const k of ['crown', 'sun', 'moon', 'star']) for (let i = 0; i < p[k]; i++) { if (max && n >= max) return s; s += '<img class="lvi" src="' + ICON[k] + '" alt="">'; n++; } return s; };
  P.badge = (uid, compact) => { if (!P.cfg.enabled || !P.cfg.badges) return ''; const lv = P.lv[uid]; if (!lv) return ''; return '<span class="lvb" title="Lv.' + lv + (P.pts[uid] != null ? ' · ' + P.pts[uid] + ' 分' : '') + '">' + P.icoHtml(lv, compact ? 3 : 0) + '</span>'; };
  const css = document.createElement('style');
  css.textContent = '.lvb { display:inline-block; vertical-align:-2px; margin-right:2px; white-space:nowrap; } .lvb .lvi { width:13px; height:13px; vertical-align:top; margin-right:0; }';
  document.head.appendChild(css);
  P.store = { get(k, d) { try { const v = localStorage.getItem('playx.' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem('playx.' + k, JSON.stringify(v)); } catch (e) {} } };
  P.state = () => ({ cfg: P.cfg, lv: Object.keys(P.lv).length, vote: P.vote, skip: P.skip, mods: Object.keys(P.mods) });
})();
