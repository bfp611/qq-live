// 运维（[ops]）的页面部分（?desk=xp）：开始菜单 → 直播复盘（下播后服务端自动生成；也可以在这里「现在生成」）。
// 窗口 = 一个带工具栏的 IE 风格页面：下拉选哪一场、生成、用记事本看 Markdown 版；内容是服务端生成的 /ops/report/<场次>.html。
//   OPSX.cfg       /config.json 的 ops 小节（report 是否开启）
//   OPSX.reports() 取 /ops/reports.json
(function () {
  if (!window.WM) return;
  const { h } = WM, ICO = 'xp/ui/qq16.png';
  const O = window.OPSX = { cfg: { report: true } };
  O.ready = fetch('config.json').then(r => r.json()).then(c => { const o = c.ops || {}; if ('report' in o) O.cfg.report = !/^(0|false|no|off)$/i.test(String(o.report)); }).catch(() => {});
  O.reports = () => fetch('/ops/reports.json').then(r => r.json());
  const fmt = (t, d) => { const x = new Date(t * 1000), p = n => String(n).padStart(2, '0'); return (x.getMonth() + 1) + '-' + p(x.getDate()) + ' ' + p(x.getHours()) + ':' + p(x.getMinutes()) + '（' + Math.round(d / 60) + ' 分钟）'; };
  function openReport(a) {
    a = a || {};
    return WM.create({ id: 'report', title: '直播复盘 - Internet Explorer', icon: ICO, w: 760, h: 560, minW: 420, minH: 300, x: 300, y: 40, content: win => {
      const sel = h('select', { style: 'min-width:220px;font:12px Tahoma,SimSun' });
      const stat = h('span', { style: 'margin-left:8px;color:#555;font-size:12px' });
      const fr = h('iframe', { style: 'flex:1;border:0;background:#fff;width:100%', title: '直播复盘' });
      const btn = (t, on) => h('button', { style: 'font:12px Tahoma,SimSun;padding:1px 10px;margin-left:6px', text: t, onclick: on });
      let list = [];
      const show = sid => { fr.src = sid ? '/ops/report/report-' + sid + '.html?_=' + Date.now() : 'about:blank'; stat.textContent = sid ? '' : '还没有复盘：下播后会自动生成，或点“现在生成”'; };
      const load = async keep => {
        let d; try { d = await O.reports(); } catch (e) { stat.textContent = '读取失败：' + e; return; }
        list = d.reports || []; sel.innerHTML = '';
        list.forEach(r => sel.appendChild(h('option', { value: r.sid, text: fmt(r.start, r.duration) + ' ' + (r.anchor || '') + ' 峰值 ' + r.peak_online })));
        if (keep && list.some(r => r.sid === keep)) sel.value = keep;
        show(sel.value || '');
        if (d.current && d.current.active) stat.textContent = '正在直播中，这一场结束后自动出复盘';
      };
      sel.onchange = () => show(sel.value);
      const make = async () => { stat.textContent = '生成中…'; try { const r = await (await fetch('/ops/report/make')).json(); if (!r.ok) { stat.textContent = r.error || '失败'; return; } await load(r.sid); stat.textContent = '已生成'; } catch (e) { stat.textContent = '生成失败：' + e; } };
      const md = async () => { if (!sel.value) return; const t = await (await fetch('/ops/report/report-' + sel.value + '.md')).text(); WM.open('notepad', { text: t, name: 'report-' + sel.value + '.md' }); };
      win.pv = { sid: () => sel.value, count: () => list.length, frame: fr };
      const bar = h('div', { style: 'padding:4px 6px;background:#ece9d8;border-bottom:1px solid #aca899;display:flex;align-items:center;flex-wrap:wrap' }, [h('span', { text: '场次：', style: 'font-size:12px' }), sel, btn('刷新', () => load(sel.value)), btn('现在生成', make), btn('记事本打开(md)', md), stat]);
      const root = h('div', { style: 'position:absolute;inset:0;display:flex;flex-direction:column' }, [bar, fr]);
      load(a.sid);
      return root;
    } });
  }
  WM.register('report', { open: openReport });
})();
