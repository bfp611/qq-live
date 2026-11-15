// XP 加强包：开机画面 → 欢迎画面（原版开机音）→ 桌面；注销 / 关机 / 重启画面（原版音）；蓝屏彩蛋（自动恢复）
// 画面都盖在 #deskroot 上（1280×720 设计画布）；盖着的时候 XP.busy() 为 true，桌面 Agent 会等它结束。
// 开机画面图是 Wikimedia Commons 的 Windows XP 原版开机图（去掉了进度条方块，由这里按原版像素重新动起来），见 CREDITS.md。
(function () {
  if (!window.XP || !window.WM || !WM.ready) return;
  const { root, h } = WM, Q = new URLSearchParams(location.search), $ = id => document.getElementById(id);
  const SPEED = Math.max(0.1, parseFloat(Q.get('xp_speed')) || 1);        // 测试用：xp_speed=4 把所有等待缩短 4 倍
  const wait = ms => new Promise(r => setTimeout(r, ms / SPEED));
  let scr = null;
  const setScr = (name, children, cls) => {
    if (scr) scr.remove();
    scr = h('div', { id: 'xpscr', class: cls || '' }, children); root.appendChild(scr);
    XP.screen = name; document.dispatchEvent(new CustomEvent('xpscreen', { detail: name }));
    document.activeElement && document.activeElement.blur && document.activeElement.blur();
    return scr;
  };
  const clearScr = (fade) => new Promise(res => {
    const s = scr; if (!s) { XP.screen = null; return res(); }
    const fin = () => { if (scr === s) { s.remove(); scr = null; XP.screen = null; document.dispatchEvent(new CustomEvent('xpscreen', { detail: null })); } res(); };
    if (fade) { s.classList.add('fade'); setTimeout(fin, 620 / SPEED); } else fin();
  });
  ['pointerdown', 'pointerup', 'click', 'keydown', 'contextmenu'].forEach(t => document.addEventListener(t, e => { if (XP.screen && !e.agent && e.isTrusted !== false && !(e.target && e.target.closest && e.target.closest('#ag-cur'))) { /* 画面期间不让真实鼠标键盘动桌面 */ if (scr && scr.contains(e.target)) return; e.stopPropagation(); e.preventDefault(); } }, true));
  const userName = () => XP.cfg.user || XP.userName || '猪猪侠';

  // ---------------- 各个画面 ----------------
  const bootScreen = secs => {
    const home = XP.cfg.boot_edition === 'home';
    const b = h('div', { class: 'boot' + (home ? ' home' : ''), style: `background-image:url(xp/boot/${home ? 'boot_home_nobar' : 'boot_pro_nobar'}.png)` }, [h('div', { class: 'bar' }, [h('i', {}, [h('b'), h('b'), h('b')])])]);
    setScr('boot', [b]); return wait(secs * 1000);
  };
  const lunaBase = () => [h('div', { class: 'top' }), h('div', { class: 'bot' }), h('div', { class: 'logo' }), h('div', { class: 'sep' })];
  const welcomeScreen = async (secs) => {
    const tile = h('div', { class: 'tile' }, [h('img', { src: 'xp/ico/user.png', alt: '' }), h('div', {}, [h('b', { text: userName() }), h('small', { text: '单击以登录' })])]);
    const pw = h('div', { class: 'pw' }, [h('img', { src: 'xp/ico/310_32.png', alt: '' }), h('span', { text: '关闭计算机' })]);
    const luna = h('div', { class: 'luna' }, lunaBase().concat([h('div', { class: 'hint', text: '要开始，请单击您的用户名' }), tile, pw, h('div', { class: 'tip', text: '登录后，XP 会为您加载个人设置。' })]));
    setScr('welcome', [luna]); await wait(Math.min(1100, secs * 350));
    tile.classList.add('sel'); await wait(500);
    luna.querySelectorAll('.hint,.tile,.tip,.sep').forEach(e => e.remove()); luna.appendChild(h('div', { class: 'msg', text: '欢迎使用' }));
    XP.snd('startup', 'startup');                       // 原版 Windows XP 启动音
    await wait(Math.max(600, secs * 1000 - 1600));
  };
  const messageScreen = async (text, snd, group, ms) => {
    setScr(group, [h('div', { class: 'luna' }, lunaBase().concat([h('div', { class: 'msg', text }), h('div', { class: 'pw', style: 'visibility:hidden' })]))]);
    if (snd) XP.snd(snd, group); await wait(ms);
  };
  const offScreen = async (text, sub, ms) => { setScr('off', [h('div', { class: 'off' }, [h('div', { text }), sub ? h('small', { text: sub }) : null].filter(Boolean))]); await wait(ms); };

  // ---------------- 流程 ----------------
  XP.closeUserWindows = () => {
    for (const w of WM.wins.slice()) { if (w.closed || ['qqchat', 'ttplayer', 'ttplaylist'].includes(w.id)) continue; try { w._confirmed = true; w.close(); } catch (e) {} }
    const q = WM.byId.qqchat; if (q) { if (q.closed) q.reopen(); else if (q.state === 'min') q.restore(); }
  };
  let running = null;
  const exclusive = fn => async (...a) => { if (running) return false; running = fn(...a); try { await running; } finally { running = null; } return true; };
  XP.boot = exclusive(async (o) => {
    o = o || {};
    await bootScreen(o.secs || XP.cfg.boot_secs);
    if (o.welcome !== false && XP.cfg.welcome) await welcomeScreen(o.wsecs || XP.cfg.welcome_secs); else if (o.sound !== false) XP.snd('startup', 'startup');
    await clearScr(true);
    try { localStorage.setItem('xp.boot.t', String(Date.now())); } catch (e) {}
    if (o.recovered) XP.balloon({ title: 'Windows 已从严重错误中恢复', text: 'Windows 已经在发生意外关闭后重新启动。错误报告已保存。', kind: 'warn', ev: 'tip', sound: 'exclamation' });
  });
  XP.logoff = exclusive(async () => {
    if (!XP.cfg.enabled || !XP.cfg.shutdown_screens) { XP.closeUserWindows(); return; }
    XP.clearBalloons(); XP.closeUserWindows();
    await messageScreen('正在注销…', 'logoff', 'logoff', 2400);
    await welcomeScreen(XP.cfg.welcome_secs); await clearScr(true);
  });
  XP.shutdown = exclusive(async (mode) => {
    mode = mode || 'shutdown';
    if (!XP.cfg.enabled || !XP.cfg.shutdown_screens) return;
    XP.clearBalloons(); XP.closeUserWindows();
    await messageScreen(mode === 'restart' ? 'Windows 正在重新启动…' : 'Windows 正在关机…', 'shutdown', 'shutdown', 3600);
    if (mode === 'shutdown') {
      await offScreen('现在可以安全地关闭计算机了。', XP.cfg.shutdown_restart ? '（演示环境：' + Math.round(XP.cfg.restart_after) + ' 秒后自动重新开机）' : '（演示环境）', XP.cfg.shutdown_restart ? XP.cfg.restart_after * 1000 : 3600000);
    } else await offScreen('', '', 700);
    if (!XP.cfg.shutdown_restart && mode === 'shutdown') return;     // 不自动重启：停在黑屏（刷新页面恢复）
    await bootScreen(XP.cfg.boot_secs); if (XP.cfg.welcome) await welcomeScreen(XP.cfg.welcome_secs); else XP.snd('startup', 'startup');
    await clearScr(true);
  });
  const STOPS = [['DRIVER_IRQL_NOT_LESS_OR_EQUAL', '0x000000D1 (0x0000000C,0x00000002,0x00000000,0xF86B5A89)', 'wdf01000.sys - Address F86B5A89 base at F86B5000, DateStamp 3dd991eb'],
    ['PAGE_FAULT_IN_NONPAGED_AREA', '0x00000050 (0xFD3094C2,0x00000001,0xFBFE7617,0x00000000)', 'qqprotect.sys - Address FBFE7617 base at FBFE5000, DateStamp 3d6dd67c'],
    ['IRQL_NOT_LESS_OR_EQUAL', '0x0000000A (0x00000000,0x0000001C,0x00000000,0x804F0F0B)', 'ntoskrnl.exe - Address 804F0F0B base at 804D7000, DateStamp 3b7d8a1e'],
    ['KMODE_EXCEPTION_NOT_HANDLED', '0x0000001E (0xC0000005,0xF7A3C3E1,0x00000000,0x00000000)', 'tmcomm.sys - Address F7A3C3E1 base at F7A38000, DateStamp 3e9a9bd0']];
  XP.bsod = exclusive(async (reason) => {
    if (!XP.cfg.enabled) return;
    XP.clearBalloons();
    const st = STOPS[Math.floor(Math.random() * STOPS.length)];
    const head = 'A problem has been detected and windows has been shut down to prevent damage\nto your computer.\n\n' + st[0] + '\n\nIf this is the first time you\'ve seen this Stop error screen,\nrestart your computer. If this screen appears again, follow\nthese steps:\n\nCheck to make sure any new hardware or software is properly installed.\nIf this is a new installation, ask your hardware or software manufacturer\nfor any Windows updates you might need.\n\nIf problems continue, disable or remove any newly installed hardware\nor software. Disable BIOS memory options such as caching or shadowing.\nIf you need to use Safe Mode to remove or disable components, restart\nyour computer, press F8 to select Advanced Startup Options, and then\nselect Safe Mode.\n\nTechnical information:\n\n*** STOP: ' + st[1] + '\n\n***  ' + st[2] + '\n\n';
    const t = h('div', { class: 'bsodtxt', text: head });
    setScr('bsod', [t], 'bsod'); XP.bsodAt = Date.now(); XP.bsodReason = reason || 'manual';
    XP.snd('critical', 'error');
    const total = Math.max(2, XP.cfg.bsod_secs) * 1000, steps = 10;
    await wait(total * 0.18); t.textContent = head + 'Beginning dump of physical memory';
    for (let i = 1; i <= steps; i++) { await wait(total * 0.5 / steps); t.textContent = head + 'Beginning dump of physical memory\nDumping physical memory to disk:  ' + i * 10; }
    t.textContent = head + 'Beginning dump of physical memory\nPhysical memory dump complete.\nContact your system administrator or technical support group for further assistance.';
    await wait(total * 0.32);
    await offScreen('', '', 900);
    await bootScreen(Math.min(3.2, XP.cfg.boot_secs)); if (XP.cfg.welcome) await welcomeScreen(Math.min(2.6, XP.cfg.welcome_secs)); else XP.snd('startup', 'startup');
    await clearScr(true);
    XP.balloon({ title: 'Windows 已从严重错误中恢复', text: 'Windows 已经在发生意外关闭后重新启动。错误报告已保存。', kind: 'warn', ev: 'tip', sound: 'exclamation' });
  });

  // ---- 假「重装系统」：XP 安装程序文字界面 → 图形界面 → 开机 → 欢迎 → 桌面（只在页面里演，不碰真实电脑；礼物大场面 / 冷场表演用）----
  XP.setup = exclusive(async (o) => {
    o = o || {};
    if (!XP.cfg.enabled) return;
    const total = Math.max(4, o.secs || XP.cfg.setup_secs || 12) * 1000, bar = (p, n) => '█'.repeat(Math.round(p / 100 * n)) + '░'.repeat(n - Math.round(p / 100 * n));
    XP.clearBalloons(); XP.closeUserWindows();
    const head = 'Windows XP Professional 安装程序\n══════════════════════════════════════════\n\n', tm = h('pre', { class: 'setuptxt' });
    setScr('setup', [tm], 'setup-text');
    tm.textContent = head + '  安装程序正在检查计算机的硬件配置…';
    await wait(total * 0.08);
    const t1 = total * 0.22, n1 = 10;
    for (let i = 1; i <= n1; i++) { await wait(t1 / n1); tm.textContent = head + '  安装程序正在格式化…\n\n  C: 分区 1 [NTFS]    磁盘 0 位于 ID 0 总线 0 在 atapi [MBR]\n\n  已格式化： ' + i * 10 + ' %\n  ' + bar(i * 10, 40); }
    const t2 = total * 0.3, n2 = 15;
    for (let i = 1; i <= n2; i++) { await wait(t2 / n2); const p = Math.round(i / n2 * 100); tm.textContent = head + '  请稍候，安装程序正在将文件复制到 Windows 安装文件夹中。\n  这可能要花几分钟时间。\n\n  ' + bar(p, 40) + '  ' + p + ' %\n\n  正在复制： ' + ['ntoskrnl.exe', 'hal.dll', 'win32k.sys', 'kernel32.dll', 'explorer.exe', 'qqprotect.sys', 'msimg32.dll'][i % 7]; }
    // 图形界面（左边是步骤列表，右边是剩余时间 + 进度；纯 CSS）
    const steps = ['收集信息', '动态更新', '准备安装', '安装 Windows', '最终安装'], li = steps.map((t, i) => h('li', { text: t, class: i < 3 ? 'done' : i === 3 ? 'cur' : '' }));
    const left = h('div', { class: 'sl' }, [h('div', { class: 'sh', text: 'Windows XP' }), h('ul', {}, li)]);
    const eta = h('b', { text: '39' }), fill = h('i'), tip = h('p', { class: 'stip', text: '' });
    const right = h('div', { class: 'sr' }, [h('h1', { text: '正在安装 Windows' }), h('div', { class: 'seta' }, [h('span', { text: '安装程序将在大约 ' }), eta, h('span', { text: ' 分钟后完成。' })]), h('div', { class: 'sbar' }, [fill]), tip,
      h('div', { class: 'sfoot', text: '（演示环境：并没有真的重装，几秒后自动开机）' })]);
    setScr('setup', [h('div', { class: 'sg' }, [left, right])], 'setup-gui');
    const TIPS = ['更快的启动与更好的稳定性', '全新的 Luna 视觉样式', '照片、音乐和视频，一应俱全', '更轻松地连接到 Internet', '正在安装设备…'], t3 = total * 0.4, n3 = 20;
    for (let i = 1; i <= n3; i++) {
      await wait(t3 / n3); fill.style.width = Math.round(i / n3 * 100) + '%'; eta.textContent = String(Math.max(1, Math.round(39 * (1 - i / n3)))); tip.textContent = TIPS[Math.floor(i / n3 * (TIPS.length - 0.01))];
    }
    await offScreen('', '', 700);
    await bootScreen(XP.cfg.boot_secs); if (XP.cfg.welcome) await welcomeScreen(XP.cfg.welcome_secs); else XP.snd('startup', 'startup');
    await clearScr(true);
    XP.balloon({ title: 'Windows 安装完成', text: '系统已重新安装（演示），桌面已恢复。', kind: 'info', ev: 'tip' });
  });
  XP.reboot = (o) => XP.boot(o);
  XP.power = (mode) => mode === 'logoff' ? XP.logoff() : (mode === 'standby' ? XP.standby() : XP.shutdown(mode));
  XP.standby = exclusive(async () => { if (!XP.cfg.enabled || !XP.cfg.shutdown_screens) return; await offScreen('', '', 1800); await clearScr(true); });
  XP.skipScreen = () => { if (scr) { running = null; clearScr(false); } };

  document.addEventListener('keydown', e => { if (e.ctrlKey && e.altKey && e.shiftKey && (e.key || '').toLowerCase() === 'b' && !XP.screen) XP.bsod('hotkey'); });   // 彩蛋：Ctrl+Alt+Shift+B

  // ---------------- 页面刚打开：开机 → 欢迎 ----------------
  const force = Q.get('xp_boot') === 'force', demo = Q.get('demo') === '1', off0 = Q.get('xp_boot') === '0' || Q.get('xp_do') === 'none';
  const cover = !off0 && (force || !demo);
  if (cover) setScr('boot', [], '');            // 先盖一层黑，等配置回来再决定放不放开机画面（避免闪一下桌面）
  XP.ready.then(async () => {
    let want = XP.cfg.enabled && (force || XP.cfg.boot);
    if (want && !force) { try { const t = +localStorage.getItem('xp.boot.t'); if (t && Date.now() - t < XP.cfg.boot_cooldown * 1000) want = false; } catch (e) {} }
    if (cover && !want) { await clearScr(false); }
    else if (cover || force) { await XP.boot(); }
    const d = Q.get('xp_do');
    if (d && XP.cfg.enabled) setTimeout(() => { ({ bsod: () => XP.bsod('url'), shutdown: () => XP.shutdown('shutdown'), restart: () => XP.shutdown('restart'), reboot: () => XP.boot(), logoff: () => XP.logoff() }[d] || (() => {}))(); }, 1200 / SPEED);
  });
})();
