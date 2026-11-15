// QQ 生态核心（?desk=xp）：[qq] 配置、弹幕/礼物事件总线、礼物 → 效果映射、窗口抖动（闪屏振动）、真实观众名单、小工具。
// 具体功能在 qq-show.js（QQ秀装扮）/ qq-pet.js（QQ宠物）/ qq-zone.js（QQ空间）/ qq-files.js（群共享）。
// 配置在 config.ini 的 [qq]（/config.json 里的 qq）；URL 里 ?qq_键=值 可临时覆盖（测试用）。
(function () {
  if (!window.DESK || !DESK.on || !window.WM || !WM.ready) return;
  const { root, h, esc } = WM, UQ = new URLSearchParams(location.search);
  const D = { enabled: true, commands: true, shake: true, shake_secs: 1.2, shake_cooldown: 6, shake_sound: true,
    show: true, outfit: 'default', outfit_revert: 90, show_scene: true,
    pet: true, pet_name: '球球', pet_wander: true, pet_decay: 1.0, pet_bubbles: true, pet_x: '', pet_panel_open: false,
    zone: true, zone_owner: '', zone_msgs: 'keyword', zone_msg_keywords: '留言,空间留言,踩踩,沙发,顶', zone_msg_sample: 10, zone_visitors: 30, zone_music: true, zone_blog: true,
    files: true, files_names: '',
    gift_map: '玫瑰花=pet:feed,小心心=pet:play,啤酒=shake,加油鸭=outfit:next,飞吻=pet:bath,嘉年华=outfit:party',
    gift_value_map: '1=pet:play,10=pet:feed,52=outfit:next,99=shake,199=outfit:random,520=outfit:party', gift_default: 'pet:play', gift_effects: true, gift_cooldown: 2 };
  const typed = (k, v) => { const d = D[k]; if (typeof d === 'boolean') return /^(1|true|yes|on)$/i.test(String(v)); if (typeof d === 'number') { const n = parseFloat(v); return isNaN(n) ? d : n; } return String(v == null ? '' : v).trim(); };
  const Q = window.QQX = { cfg: Object.assign({}, D), mods: {}, actions: {}, viewers: new Map(), log: [], fx: {} };
  Q.apply = c => { for (const k in D) { if (c && c[k] !== undefined) Q.cfg[k] = typed(k, c[k]); const u = UQ.get('qq_' + k); if (u !== null) Q.cfg[k] = typed(k, u); } };
  Q.apply({});
  Q.on = k => Q.cfg.enabled && Q.cfg[k] !== false;
  Q.list = s => String(s || '').split(/[,，]+/).map(x => x.trim()).filter(Boolean);
  Q.ready = fetch('config.json').then(r => r.json()).then(c => { Q.host = c.host_name || ''; Q.apply(c.qq || {}); }).catch(() => {}).then(() => { Q.parseMaps(); document.dispatchEvent(new CustomEvent('qqready')); return Q.cfg; });
  // ---- 存档（浏览器 localStorage；OBS 刷新不丢）----
  Q.store = { get(k, d) { try { const v = localStorage.getItem('qqx.' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem('qqx.' + k, JSON.stringify(v)); } catch (e) {} } };
  // ---- 事件总线（app.js 的 push 会派发 qqev）----
  const subs = {};
  Q.sub = (t, fn) => { (subs[t] = subs[t] || []).push(fn); };
  document.addEventListener('qqev', e => { const ev = e.detail || {}; if (!Q.cfg.enabled) return; try { if (['chat', 'gift', 'follow', 'member', 'like'].includes(ev.t)) seen(ev); (subs[ev.t] || []).concat(subs['*'] || []).forEach(f => { try { f(ev); } catch (er) { console.error('qq', er); } }); } catch (er) {} });
  // ---- 真实观众名单（QQ空间的访客列表用）----
  const nowS = () => Date.now();
  function seen(ev) {
    if (!ev.uid || ev.t === 'say') return; const v = Q.viewers.get(ev.uid) || { uid: ev.uid, name: ev.name || '神秘人', first: nowS(), chats: 0, gifts: 0, follows: 0 };
    v.name = ev.name || v.name; v.last = nowS(); if (ev.t === 'chat') v.chats++; else if (ev.t === 'gift') v.gifts += ev.count || 1; else if (ev.t === 'follow') v.follows++;
    Q.viewers.delete(ev.uid); Q.viewers.set(ev.uid, v); while (Q.viewers.size > 200) Q.viewers.delete(Q.viewers.keys().next().value);
  }
  Q.visitors = n => [...Q.viewers.values()].reverse().slice(0, n || Q.cfg.zone_visitors);
  // ---- 礼物 → 效果映射 ----
  // gift_map：礼物名=动作；gift_value_map：抖币数(≥)=动作；动作格式 模块:参数，如 pet:feed / outfit:party / shake / fx:hearts，用 + 连起来可以同时触发多个（outfit:party+fireworks）；都没匹配用 gift_default（写 none = 不触发）
  // 映射可以有多个来源：[qq] 自己的，再加 [play] 等模块用 Q.addMaps({gift_map, gift_value_map}) 叠上去（同名的后来者覆盖）——同一套引擎，不另起一套
  Q.extra = [];
  Q.addMaps = m => { Q.extra.push(m); Q.parseMaps(); };
  Q.parseMaps = () => {
    const parse = s => Q.list(s).map(x => { const i = x.indexOf('='); return i < 0 ? null : [x.slice(0, i).trim(), x.slice(i + 1).trim()]; }).filter(Boolean);
    const names = new Map(), vals = new Map();
    [{ gift_map: Q.cfg.gift_map, gift_value_map: Q.cfg.gift_value_map }].concat(Q.extra).forEach(m => { parse(m.gift_map).forEach(([k, v]) => names.set(k, v)); parse(m.gift_value_map).forEach(([k, v]) => { const n = parseFloat(k); if (!isNaN(n)) vals.set(n, v); }); });
    Q.giftNames = [...names]; Q.giftValues = [...vals].sort((a, b) => b[0] - a[0]);
  };
  Q.giftAction = ev => {
    const n = String(ev.gift || ''); const hit = (Q.giftNames || []).find(([k]) => k === n); if (hit) return hit[1];
    const v = ev.value || 0, hv = v && (Q.giftValues || []).find(([k]) => v >= k); if (hv) return hv[1];
    return Q.cfg.gift_default && Q.cfg.gift_default !== 'none' ? Q.cfg.gift_default : '';
  };
  let lastGift = 0;
  Q.run1 = (spec, ev) => {                     // 一个动作，spec 例：pet:feed outfit:party shake fx:hearts fireworks emoji:🌹
    const [m, ...rest] = String(spec || '').split(':'), arg = rest.join(':'), f = Q.actions[m.trim()];
    if (!f) return false; Q.log.push({ at: nowS(), spec, who: ev && ev.name || '' }); if (Q.log.length > 60) Q.log.shift();
    try { return f(arg, ev || {}) !== false; } catch (e) { console.error('qq action', spec, e); return false; }
  };
  Q.run = (spec, ev) => { let ok = false; String(spec || '').split('+').map(x => x.trim()).filter(Boolean).forEach(x => { if (Q.run1(x, ev)) ok = true; }); return ok; };   // a+b = 同时触发多个效果
  Q.sub('gift', ev => {
    if (!Q.on('gift_effects') || ev.giftfx) return; const t = nowS();      // ev.giftfx：服务端 [giftfx] 已按钻石档位接管这条礼物的特效，这里不再重复 if (t - lastGift < Q.cfg.gift_cooldown * 1000) return; lastGift = t;
    const a = Q.giftAction(ev); if (a) Q.run(a, ev);
  });
  Q.actions.shake = (arg, ev) => Q.shake(arg || 'chat', { by: ev && ev.name });
  // ---- 窗口抖动（闪屏振动）----
  let lastShake = 0;
  Q.shake = function (target, o) {
    o = o || {}; if (!Q.on('shake')) return false; const t = nowS();
    if (!o.force && t - lastShake < Q.cfg.shake_cooldown * 1000) return false; lastShake = t;
    const secs = o.secs || Q.cfg.shake_secs;
    if (Q.cfg.shake_sound && window.XP && XP.snd) XP.snd('qq_alert', 'qq');
    if (target === 'desk') { root.classList.add('qq-deskshake'); setTimeout(() => root.classList.remove('qq-deskshake'), secs * 1000); return true; }
    const w = target === 'chat' || !target ? WM.byId.qqchat : WM.byId[target]; if (!w || w.closed || w.state === 'min' || w.state === 'max') return false;
    const r0 = { x: w.rect.x, y: w.rect.y }, t0 = performance.now(); w._shaking = true;
    const step = now => { const k = (now - t0) / 1000; if (w.closed || k > secs) { w.rect.x = r0.x; w.rect.y = r0.y; w._apply(); w._shaking = false; return; }
      const a = 7 * (1 - k / secs * .4); w.rect.x = r0.x + Math.round(Math.sin(k * 80) * a); w.rect.y = r0.y + Math.round(Math.cos(k * 67) * a * .7); w._apply(); requestAnimationFrame(step); };
    requestAnimationFrame(step); return true;
  };
  const st = document.createElement('style'); st.textContent = `@keyframes qqdesk { 0%,100% { transform: translate(0,0) } 20% { transform: translate(-5px,3px) } 40% { transform: translate(5px,-3px) } 60% { transform: translate(-4px,-2px) } 80% { transform: translate(4px,2px) } }
    .qq-deskshake { animation: qqdesk .09s linear infinite; }
    .qqx-btn { font: 12px var(--xpfont); } .qqx-toast { position:absolute; z-index:9000; font:12px var(--xpfont); background:#ffffe1; border:1px solid #000; padding:3px 7px; border-radius:3px; box-shadow:2px 2px 3px rgba(0,0,0,.3); pointer-events:none; }`;
  document.head.appendChild(st);
  // 群聊里的“发送窗口抖动”菜单也走这里（声音 + 冷却不拦手动）
  Q.menuShake = () => Q.shake('chat', { force: true });
  // ---- 往群聊里写一行系统消息 ----
  Q.sysLine = html => { const list = document.getElementById('list'); if (!list) return; const li = document.createElement('li'); li.className = 'notice'; const d = new Date(), p = n => String(n).padStart(2, '0');
    li.innerHTML = '<p class="sysline">【系统消息】' + html + '<span class="t">' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) + '</span></p>'; list.appendChild(li); list.scrollTop = list.scrollHeight; while (list.children.length > 400) list.removeChild(list.firstChild); };
  // ---- 群聊工具栏多一个“群共享” ----
  Q.ready.then(() => { const tb = document.querySelector('.qq-im-big-toolbar'); if (!tb || !Q.on('files') || document.getElementById('qq-im-files')) return; const b = document.createElement('button'); b.id = 'qq-im-files'; b.textContent = '群共享'; b.addEventListener('click', () => WM.open('qqfiles')); tb.insertBefore(b, document.getElementById('qq-im-invite')); });
  // ---- 给 agent / 测试用：统一入口 ----
  Q.exec = (m, arg, ev) => Q.run(m + (arg ? ':' + arg : ''), ev);
  Q.state = () => ({ cfg: Q.cfg, mods: Object.keys(Q.mods), viewers: Q.viewers.size, log: Q.log.slice(-10), outfit: Q.mods.show && Q.mods.show.state && Q.mods.show.state(), pet: Q.mods.pet && Q.mods.pet.state && Q.mods.pet.state() });
})();
