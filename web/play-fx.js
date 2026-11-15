/* 观众互动 · 礼物/指令特效（XP 风）。
 * 和 item 4 的 QQX 是同一套：这里只是往 QQX.actions 里再注册几个动作（fireworks / meteor / emoji / virus / bsod），
 * 于是 [qq] gift_map、[play] gift_map（通过 QQX.addMaps 叠加）、`a+b` 组合、Agent 的 play_fx 动作、/qq/event 都能直接用，不另起一套映射。
 * 全部是 pointer-events:none 的覆盖层，自动清理；“中毒”只是换桌面图标 + 一个假气泡，到时间自动恢复，不碰任何文件/系统。 */
(function () {
  'use strict';
  const P = window.PLAYX, Q = window.QQX; if (!P || !Q) return;
  const stage = () => (window.WM && WM.root) || document.getElementById('deskroot') || document.body;      // 整个桌面画布（1280×720），不是群聊里那个小舞台
  const secs = () => Math.max(2, Math.min(30, +P.cfg.fx_secs || 6));
  const last = {}; P.fxLog = []; P.fxLive = {};
  const gate = (kind, cd, ev) => {            // 开关 + 每种特效各自的冷却（强制触发/Agent 不受冷却限制）
    if (!P.cfg.enabled || !P.cfg.fx) return false;
    const t = Date.now(); if (!(ev && ev.force) && t - (last[kind] || 0) < cd * 1000) return false;
    last[kind] = t; P.fxLog.push({ kind, at: t, who: ev && ev.name || '' }); if (P.fxLog.length > 60) P.fxLog.shift(); return true;
  };
  const cd = () => Math.max(0, +P.cfg.fx_cooldown || 0);
  const layer = (cls) => {
    const st = stage(), c = document.createElement('canvas');
    c.className = 'pfx ' + cls; c.width = st.clientWidth || 1024; c.height = st.clientHeight || 768; st.appendChild(c); return c;
  };
  const run = (kind, c, frame, ms) => {      // 通用动画循环：frame(ctx, t0到现在的ms, W, H) 返回 false 提前结束
    const g = c.getContext('2d'), t0 = performance.now(); P.fxLive[kind] = (P.fxLive[kind] || 0) + 1;
    const end = () => { c.remove(); P.fxLive[kind] = Math.max(0, (P.fxLive[kind] || 1) - 1); };
    const tick = (now) => { const dt = now - t0; if (dt > ms || !c.isConnected) return end(); g.clearRect(0, 0, c.width, c.height); if (frame(g, dt, c.width, c.height) === false) return end(); requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  };

  // ---- 烟花 ----
  Q.actions.fireworks = (arg, ev) => {
    if (!gate('fireworks', cd(), ev)) return false;
    const small = arg === 'small';                                   // 礼物联动的「小烟花」：短 + 少（giftfx 1 钻档）
    const c = layer('pfx-fire'), parts = [], hues = [0, 25, 48, 120, 190, 280, 330]; let nextB = 0, lastT = 0;
    const burst = (W, H) => {
      const x = W * (.15 + Math.random() * .7), y = H * (.12 + Math.random() * .4), h = hues[Math.floor(Math.random() * hues.length)], n = (small ? 40 : 64) + Math.floor(Math.random() * 30);
      for (let i = 0; i < n; i++) { const a = Math.PI * 2 * i / n + Math.random() * .1, v = 1.6 + Math.random() * 3.2; parts.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 1, h: h + Math.random() * 30 }); }
    };
    const ms = (small ? Math.min(3.2, secs()) : secs()) * 1000;
    run('fireworks', c, (g, t, W, H) => {
      const k = Math.max(0, Math.min(1, t / 500, (ms - t) / 700));                    // 夜幕淡入淡出，烟花才看得清
      g.fillStyle = `rgba(6,8,30,${.4 * k})`; g.fillRect(0, 0, W, H);
      if (t > nextB && t < ms - 1200) { burst(W, H); if (Math.random() < .4) burst(W, H); nextB = t + 240 + Math.random() * 260; }
      g.lineCap = 'round'; const f = Math.max(.5, Math.min(4, (t - lastT) / 16.7)); lastT = t;          // 按帧间隔缩放：掉帧时速度不变
      for (const p of parts) {
        const px = p.x, py = p.y; p.x += p.vx * f; p.y += p.vy * f; p.vy += .05 * f; p.vx *= Math.pow(.985, f); p.vy *= Math.pow(.99, f); p.life -= .013 * f; if (p.life <= 0) continue;
        g.strokeStyle = `hsla(${p.h},100%,${60 + p.life * 20}%,${Math.max(0, p.life)})`; g.lineWidth = 3.4 * p.life + 1.6; g.beginPath(); g.moveTo(px, py); g.lineTo(p.x, p.y); g.stroke();
        g.fillStyle = `rgba(255,255,255,${Math.max(0, p.life) * .9})`; g.beginPath(); g.arc(p.x, p.y, 2 * p.life + .6, 0, 7); g.fill();
      }
      for (let i = parts.length - 1; i >= 0; i--) if (parts[i].life <= 0) parts.splice(i, 1);
    }, ms);
    return true;
  };

  // ---- 流星雨 ----
  Q.actions.meteor = (arg, ev) => {
    if (!gate('meteor', cd(), ev)) return false;
    const c = layer('pfx-meteor'), ms = secs() * 1000, ms_ = [], stars = Array.from({ length: 70 }, () => ({ x: Math.random(), y: Math.random() * .8, r: Math.random() * 1.4 + .4, p: Math.random() * 6 })); let next = 0;
    run('meteor', c, (g, t, W, H) => {
      const k = Math.min(1, t / 700, (ms - t) / 900);                                // 夜色淡入淡出
      g.fillStyle = `rgba(4,10,40,${.42 * Math.max(0, k)})`; g.fillRect(0, 0, W, H);
      for (const s of stars) { g.fillStyle = `rgba(255,255,255,${(.35 + .35 * Math.sin(t / 300 + s.p)) * Math.max(0, k)})`; g.fillRect(s.x * W, s.y * H, s.r, s.r); }
      if (t > next && t < ms - 900) { const n = 1 + Math.floor(Math.random() * 3); for (let i = 0; i < n; i++) ms_.push({ x: Math.random() * W * 1.1, y: -20 - Math.random() * 120, v: 9 + Math.random() * 7, l: 90 + Math.random() * 110 }); next = t + 90 + Math.random() * 160; }
      for (const m of ms_) {
        m.x -= m.v * .72; m.y += m.v * .72 * 1.1;
        const dx = .72 * m.l, dy = -.72 * 1.1 * m.l, gr = g.createLinearGradient(m.x, m.y, m.x + dx, m.y + dy);
        gr.addColorStop(0, 'rgba(255,255,255,.95)'); gr.addColorStop(.3, 'rgba(160,200,255,.55)'); gr.addColorStop(1, 'rgba(120,160,255,0)');
        g.strokeStyle = gr; g.lineWidth = 2.2; g.lineCap = 'round'; g.beginPath(); g.moveTo(m.x, m.y); g.lineTo(m.x + dx, m.y + dy); g.stroke();
        g.fillStyle = '#fff'; g.beginPath(); g.arc(m.x, m.y, 2.4, 0, 7); g.fill();
      }
      for (let i = ms_.length - 1; i >= 0; i--) if (ms_[i].y > H + 40 || ms_[i].x < -200) ms_.splice(i, 1);
    }, ms);
    return true;
  };

  // ---- 满屏表情雨 ----
  Q.actions.emoji = (arg, ev) => {
    if (!gate('emoji', cd(), ev)) return false;
    const base = String(P.cfg.fx_emoji || '🎉,✨,💗,🌹,🎁').split(/[,，\s]+/).filter(Boolean), one = String(arg || '').trim();
    const pool = one ? [one, one, one, ...base.slice(0, 2)] : base, c = layer('pfx-emoji'), ms = secs() * 1000, drops = [];
    let next = 0;
    run('emoji', c, (g, t, W, H) => {
      if (t > next && t < ms - 1800) { for (let i = 0; i < 5; i++) drops.push({ x: Math.random() * W, y: -30, v: 2.2 + Math.random() * 3.6, s: 22 + Math.random() * 26, e: pool[Math.floor(Math.random() * pool.length)], w: Math.random() * 6, r: (Math.random() - .5) * .05, a: 0 }); next = t + 70; }
      g.textAlign = 'center'; g.textBaseline = 'middle';
      for (const d of drops) { d.y += d.v; d.a += d.r; d.w += .05; g.save(); g.translate(d.x + Math.sin(d.w) * 14, d.y); g.rotate(d.a); g.font = `${d.s}px "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif`; g.fillText(d.e, 0, 0); g.restore(); }
      for (let i = drops.length - 1; i >= 0; i--) if (drops[i].y > H + 40) drops.splice(i, 1);
    }, ms);
    return true;
  };

  // ---- 蓝屏彩蛋（复用 item 3 的 XP.bsod）----
  Q.actions.bsod = (arg, ev) => {
    if (!window.XP || !XP.cfg.enabled || !XP.cfg.bsod || XP.screen) return false;
    const cdb = Math.max(0, +P.cfg.fx_bsod_cooldown || 0) * 1000;
    if (!(ev && ev.force) && (Date.now() - (XP.bsodAt || 0) < cdb || Date.now() - (last.bsod || 0) < cdb)) return false;
    if (!gate('bsod', 0, ev)) return false; XP.bsod('gift'); return true;
  };

  // ---- “中毒”恶作剧：熊猫烧香图标（自绘）。只换桌面图标 + 假气泡，到时间自动恢复 ----
  const panda = 'data:image/svg+xml;utf8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect x="9" y="2" width="1.4" height="9" fill="#a0521d"/><rect x="15.3" y="1" width="1.4" height="10" fill="#a0521d"/><rect x="21.6" y="2" width="1.4" height="9" fill="#a0521d"/>' +
    '<circle cx="9.7" cy="2" r="1.1" fill="#ff3b1f"/><circle cx="16" cy="1" r="1.1" fill="#ff3b1f"/><circle cx="22.3" cy="2" r="1.1" fill="#ff3b1f"/>' +
    '<circle cx="8" cy="15" r="3.2" fill="#222"/><circle cx="24" cy="15" r="3.2" fill="#222"/><ellipse cx="16" cy="21" rx="10.5" ry="9.2" fill="#fff" stroke="#222" stroke-width="1"/>' +
    '<ellipse cx="11.6" cy="19.4" rx="2.7" ry="3.4" fill="#222" transform="rotate(20 11.6 19.4)"/><ellipse cx="20.4" cy="19.4" rx="2.7" ry="3.4" fill="#222" transform="rotate(-20 20.4 19.4)"/>' +
    '<circle cx="11.9" cy="19.2" r="1" fill="#fff"/><circle cx="20.1" cy="19.2" r="1" fill="#fff"/><ellipse cx="16" cy="23.4" rx="1.7" ry="1.2" fill="#222"/><path d="M13.8 25.6q2.2 1.8 4.4 0" fill="none" stroke="#222" stroke-width=".9" stroke-linecap="round"/></svg>');
  const css = document.createElement('style'); css.id = 'pfx-css';
  css.textContent = `body.pfx-virus .dicon img{content:url("${panda}") !important;animation:pfxwob .5s ease-in-out infinite alternate}@keyframes pfxwob{from{transform:rotate(-6deg)}to{transform:rotate(6deg)}}.pfx{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:1300000}`; document.head.appendChild(css);
  let vtimer = 0;
  Q.actions.virus = (arg, ev) => {
    if (!gate('virus', cd(), ev)) return false;
    const ms = Math.max(2, +P.cfg.fx_virus_secs || 8) * 1000;
    document.body.classList.add('pfx-virus'); P.fxLive.virus = 1; clearTimeout(vtimer);
    if (window.XP && XP.balloon && XP.cfg.enabled && XP.cfg.balloons) XP.balloon({ title: 'Windows 安全警报', text: '检测到病毒“熊猫烧香”正在感染桌面图标……（只是个玩笑，约 ' + Math.round(ms / 1000) + ' 秒后自动恢复）', kind: 'warn', ev: 'tip', sound: 'exclamation' });
    vtimer = setTimeout(() => {
      document.body.classList.remove('pfx-virus'); P.fxLive.virus = 0;
      if (window.XP && XP.balloon && XP.cfg.enabled && XP.cfg.balloons) XP.balloon({ title: 'Windows 安全警报', text: '病毒已清除，桌面图标已恢复。', kind: 'info', ev: 'tip' });
    }, ms);
    return true;
  };
  P.fxStop = () => { clearTimeout(vtimer); document.body.classList.remove('pfx-virus'); P.fxLive.virus = 0; document.querySelectorAll('.pfx').forEach(e => e.remove()); };
  P.fx = (kind, ev) => Q.run(kind, Object.assign({ force: true }, ev || {}));
})();
