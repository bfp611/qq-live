/* 连续剧情（[story]）的页面部分：XP 里的「今天」是哪一天（2005 年起，每个开播日往后走一天）
 *   window.STORY = { on, clock, zone, y, m, d, wd, day, diaries[], long(), stamp(), at(date, hm), seed(id), sync(), subs[] }
 *   - 任务栏时钟：悬停提示显示剧情日期；点一下弹出「日期和时间 属性」风格的小日历（纯 CSS，XP 配色）
 *   - QQ空间（qq-zone.js）用 STORY.stamp() 给新日志 / 留言盖剧情日期，用 STORY.seed() 给原有的几篇老日志排到剧情开始之前，
 *     用 STORY.diaries（下播后写好、开播时发表的日记）同步成日志
 *   数据来自 /story.json（服务端 backend/story.py），开播 / 发表 / 日期变化时服务端推 {t:'story'}，另外每分钟校一次 */
(function () {
  'use strict';
  const S = window.STORY = { on: false, clock: true, zone: true, y: 0, m: 0, d: 0, wd: '', day: 0, start: '', diaries: [], subs: [] };
  const p2 = n => String(n).padStart(2, '0');
  S.long = () => S.y + '年' + S.m + '月' + S.d + '日 ' + S.wd;
  S.stamp = () => { const n = new Date(); return new Date(S.y, S.m - 1, S.d, n.getHours(), n.getMinutes(), n.getSeconds()).getTime(); };
  S.at = (date, hm) => { const [y, m, d] = String(date).split('-').map(Number), [h, mi] = String(hm || '21:00').split(':').map(Number); return new Date(y, m - 1, d, h || 0, mi || 0).getTime(); };
  S.seed = id => { const [y, m, d] = String(S.start || (S.y + '-' + S.m + '-' + S.d)).split('-').map(Number); return new Date(y, m - 1, d - (id * 17 + 3), 21, 30).getTime(); };   // 老日志：开播前 20 / 37 / 54 天
  const apply = j => {
    const was = S.long();
    if (!j || !j.on) { S.on = false; } else { Object.assign(S, { on: true, clock: j.clock !== false, zone: j.zone !== false, y: j.y, m: j.m, d: j.d, wd: j.wd, day: j.day, start: j.start, diaries: j.diaries || [] }); }
    tickClock(); S.subs.forEach(f => { try { f(); } catch (e) { console.error('story', e); } });
    if (S.long() !== was) document.dispatchEvent(new CustomEvent('storydate', { detail: { date: S.long() } }));
  };
  S.sync = () => fetch('story.json').then(r => r.json()).then(apply).catch(() => {});
  const clk = () => document.getElementById('clk');
  function tickClock() { const c = clk(); if (!c) return; c.title = S.on && S.clock ? S.long() : ''; c.style.cursor = S.on && S.clock ? 'pointer' : ''; }
  // ---- 点任务栏时钟：日期和时间 属性（小日历）----
  const st = document.createElement('style');
  st.textContent = `#story-cal { position:absolute; right:6px; bottom:44px; z-index:1300400; width:236px; border:2px solid #0831d9; border-radius:8px 8px 3px 3px; background:#ece9d8; box-shadow:3px 4px 12px rgba(0,0,0,.4); font:12px Tahoma,"Microsoft YaHei",sans-serif; color:#000; user-select:none; }
    #story-cal .tb { background:linear-gradient(#3b8cf5,#0a5fe8 12%,#0842c9 88%,#0a37b0); color:#fff; font-weight:700; padding:3px 7px; border-radius:6px 6px 0 0; }
    #story-cal .bd { padding:8px 10px 10px; } #story-cal .hd { text-align:center; font-weight:700; margin-bottom:4px; }
    #story-cal table { width:100%; border-collapse:collapse; background:#fff; border:1px solid #7f9db9; } #story-cal th { background:#316ac5; color:#fff; font-weight:400; padding:2px 0; }
    #story-cal td { text-align:center; padding:2px 0; } #story-cal td.dim { color:#aaa; } #story-cal td.cur { background:#316ac5; color:#fff; font-weight:700; }
    #story-cal .ft { margin-top:7px; text-align:center; color:#245; } #story-cal .ft b { font-size:15px; } #story-cal .ds { margin-top:3px; text-align:center; color:#555; font-size:11px; }`;
  document.head.appendChild(st);
  function cal() {
    let el = document.getElementById('story-cal'); if (el) { el.remove(); return; }
    if (!S.on || !S.clock) return;
    const first = new Date(S.y, S.m - 1, 1), days = new Date(S.y, S.m, 0).getDate(), lead = (first.getDay() + 6) % 7, now = new Date();
    let rows = '', n = 1 - lead;
    for (let r = 0; r < 6 && n <= days; r++) { rows += '<tr>'; for (let c = 0; c < 7; c++, n++) { const out = n < 1 || n > days, dd = new Date(S.y, S.m - 1, n).getDate(); rows += '<td class="' + (out ? 'dim' : n === S.d ? 'cur' : '') + '">' + dd + '</td>'; } rows += '</tr>'; }
    el = document.createElement('div'); el.id = 'story-cal';
    const h = now.getHours();
    el.innerHTML = '<div class="tb">日期和时间 属性</div><div class="bd"><div class="hd">' + S.y + '年 ' + S.m + '月</div><table><tr>' + '一二三四五六日'.split('').map(x => '<th>' + x + '</th>').join('') + '</tr>' + rows + '</table>'
      + '<div class="ft"><b>' + p2(h) + ':' + p2(now.getMinutes()) + '</b></div><div class="ds">' + S.long() + (S.day ? '　· 第 ' + (S.day + 1) + ' 个直播日' : '') + '</div></div>';
    (window.WM && WM.root || document.body).appendChild(el);
  }
  S.cal = cal;
  document.addEventListener('click', e => {                  // 点时钟开 / 关；点日历以外的地方收起（桌面会拦掉 mousedown，所以认 click）
    const c = clk(), el = document.getElementById('story-cal');
    if (c && (e.target === c || c.contains(e.target))) cal(); else if (el && !el.contains(e.target)) el.remove();
  }, true);
  document.addEventListener('qqev', e => { const ev = e.detail || {}; if (ev.t === 'story') S.sync(); });
  S.sync(); setInterval(S.sync, 60000); setInterval(tickClock, 5000);
})();
