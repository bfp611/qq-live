/* 礼物 / 点赞联动（[giftfx]）的页面部分：服务端 backend/agent/giftfx.py 按钻石档位决定放什么，用 agent 动作 gift_fx 推到这里。
 * 全是 CSS + 现成特效（烟花 / 流星雨 / 表情雨 / XP 开关机画面），没有自绘素材；全屏「感谢」卡片是 XP 窗口配色的 CSS 卡片。
 *   GFX.run({kind, name, gift, n, value, text, secs})：
 *     small_fireworks  小烟花（1 钻档）
 *     thanks           全屏感谢卡片（谁送了什么、多少钻）
 *     big_thanks       流星雨 + 全屏感谢卡片（100 钻档的一种大场面）
 *     setup            假「重装系统」（XP.setup：安装程序 → 开机 → 欢迎 → 桌面）
 *     like             全屏点赞特效（表情雨 + 「已收到 N 个赞」）
 */
(function () {
  'use strict';
  if (!window.WM || !window.QQX || !window.XP) return;
  const { root, h } = WM, Q = window.QQX, GFX = window.GFX = { live: 0, log: [] };
  const clip = (v, n) => String(v == null ? '' : v).replace(/[\r\n]+/g, ' ').slice(0, n);
  const st = document.createElement('style');
  st.textContent = `.gfx { position:absolute; inset:0; z-index:1300500; pointer-events:none; display:flex; align-items:center; justify-content:center; background:radial-gradient(ellipse at center, rgba(0,20,70,.30), rgba(0,10,40,.62)); backdrop-filter:blur(2px); animation:gfxin .45s ease-out both; font-family:Tahoma,"Microsoft YaHei",sans-serif; }
    .gfx.out { animation:gfxout .7s ease-in both; }
    .gfx .card { min-width:560px; max-width:900px; border:2px solid #0831d9; border-radius:9px 9px 3px 3px; background:#ece9d8; box-shadow:6px 8px 22px rgba(0,0,0,.55); overflow:hidden; transform-origin:50% 60%; animation:gfxpop .55s cubic-bezier(.2,1.4,.4,1) both; }
    .gfx .card .tb { background:linear-gradient(#3b8cf5,#0a5fe8 12%,#0842c9 88%,#0a37b0); color:#fff; font:700 17px Tahoma,"Microsoft YaHei",sans-serif; padding:6px 12px; text-shadow:1px 1px 1px rgba(0,0,0,.5); }
    .gfx .card .bd { padding:26px 44px 30px; text-align:center; color:#10244a; }
    .gfx .card .big { font:700 56px/1.15 "Microsoft YaHei",Tahoma,sans-serif; color:#0a3a8c; text-shadow:2px 2px 0 #fff, 4px 4px 6px rgba(0,0,0,.25); word-break:break-all; }
    .gfx .card .sub { margin-top:12px; font-size:26px; color:#244; } .gfx .card .sub b { color:#c1272d; font-size:32px; }
    .gfx .card .msg { margin-top:14px; font-size:22px; color:#456; }
    @keyframes gfxin { from { opacity:0 } to { opacity:1 } } @keyframes gfxout { from { opacity:1 } to { opacity:0 } }
    @keyframes gfxpop { 0% { transform:scale(.55) rotate(-3deg); opacity:0 } 100% { transform:scale(1) rotate(0); opacity:1 } }`;
  document.head.appendChild(st);
  const card = (title, big, sub, msg, secs) => {
    const el = h('div', { class: 'gfx' }, [h('div', { class: 'card' }, [h('div', { class: 'tb', text: title }), h('div', { class: 'bd' }, [h('div', { class: 'big', text: big }), sub ? h('div', { class: 'sub', html: sub }) : null, msg ? h('div', { class: 'msg', text: msg }) : null].filter(Boolean))])]);
    root.appendChild(el); GFX.live++;
    setTimeout(() => el.classList.add('out'), Math.max(1500, secs * 1000 - 700));
    setTimeout(() => { el.remove(); GFX.live = Math.max(0, GFX.live - 1); }, Math.max(2200, secs * 1000));
    return el;
  };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  GFX.run = a => {
    a = a || {}; const kind = a.kind, name = clip(a.name || '朋友', 10), gift = clip(a.gift || '礼物', 12), secs = Math.max(2, Math.min(15, +a.secs || 6));
    GFX.log.push({ at: Date.now(), kind, name }); if (GFX.log.length > 40) GFX.log.shift();
    const fx = (spec) => { try { return Q.run1(spec, { force: true, name }); } catch (e) { return false; } };
    if (kind === 'small_fireworks') { fx('fireworks:small'); return '放了小烟花'; }
    if (kind === 'thanks') { card('🎁 感谢礼物', '感谢 ' + name, '送出的 <b>' + esc(gift) + '</b>' + (+a.n > 1 ? ' × ' + (+a.n) : '') + (+a.value ? '（' + (+a.value) + ' 钻）' : ''), clip(a.text, 30), secs); fx('emoji:🎁'); return '全屏感谢卡片'; }
    if (kind === 'big_thanks') { fx('meteor'); card('🌠 感谢大礼', '感谢 ' + name + '！', '送出的 <b>' + esc(gift) + '</b>' + (+a.n > 1 ? ' × ' + (+a.n) : '') + (+a.value ? '（' + (+a.value) + ' 钻）' : ''), clip(a.text, 30), Math.max(secs, 7)); return '流星雨 + 全屏感谢'; }
    if (kind === 'like') { card('👍 点赞', '已收到 ' + (+a.n || 0) + ' 个赞', '谢谢大家的 <b>赞</b>', clip(a.text, 30), Math.min(secs, 5)); fx('emoji:💗'); return '全屏点赞特效'; }
    if (kind === 'setup') { if (XP.screen || !XP.cfg.enabled || !XP.cfg.shutdown_screens) return null; XP.setup({}); return '假重装系统'; }
    return null;
  };
})();
