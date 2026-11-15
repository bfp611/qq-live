// 怀旧 QQ 直播间 前端：URL 参数见 README
(function () {
  const Q = new URLSearchParams(location.search);
  const num = (k, d) => { const v = parseFloat(Q.get(k)); return isNaN(v) ? d : v; };
  const bool = (k, d) => { const v = Q.get(k); return v === null ? d : !(v === '0' || v === 'false' || v === 'no'); };
  const str = (k, d) => (Q.get(k) !== null && Q.get(k) !== '' ? Q.get(k) : d);

  const P = {
    room: str('room', ''), demo: bool('demo', false),
    scale: num('scale', 1), max: Math.max(5, num('max', 80)), rate: Math.max(1, num('rate', 6)),
    gifts: bool('gifts', true), follows: bool('follows', true), enters: bool('enters', false), likes: bool('likes', false),
    side: bool('side', true), emoji: bool('emoji', true), sound: bool('sound', false),
    show: bool('show', true), voice: bool('voice', true), volume: Math.min(1, Math.max(0, num('volume', 1))),
    fs: num('fs', 12), bg: str('bg', ''), font: str('font', ''),
    title: str('title', ''), notice: str('notice', ''), input: str('input', '欢迎来到直播间，发条弹幕和大家聊聊吧~'),
  };
  P.host = bool('host', P.show);   // 是否让服务器端的 AI 主播上班（show=0&host=1 = 只有声音和群聊消息，没有 QQ 秀）
  P.avatar = bool('avatar', false);   // 消息行内小头像（默认关；右侧成员栏里本来就有头像）

  const $ = id => document.getElementById(id);
  const win = $('win'), list = $('list');
  document.body.classList.add(P.bg === 'none' ? 'bg-none' : P.bg === 'xp' ? 'bg-xp' : 'x');
  if (P.bg && P.bg !== 'none' && P.bg !== 'xp') document.body.style.background = P.bg.startsWith('#') || /^[a-z]+$/i.test(P.bg) ? P.bg : '#' + P.bg;
  if (P.font) document.documentElement.style.setProperty('--font', P.font);
  document.documentElement.style.setProperty('--fs', P.fs + 'px');
  list.style.fontSize = P.fs + 'px';

  // ---- 尺寸：width/height 是窗口的“逻辑像素”，scale 整体放大；不给就铺满页面 ----
  function layout() {
    const s = P.scale;
    const D = window.DESK && window.DESK.on ? window.DESK.rect : null;   // ?desk=xp：窗口放在 XP 桌面上
    const w = Math.round(num('width', D ? D.w / s : window.innerWidth / s)), h = Math.round(num('height', D ? D.h / s : window.innerHeight / s));
    win.style.width = w + 'px'; win.style.height = h + 'px';
    win.style.transform = s === 1 ? '' : `scale(${s})`;
    win.style.left = num('x', D ? D.x : 0) + 'px'; win.style.top = num('y', D ? D.y : 0) + 'px';
    // 右侧栏：QQ秀 + 群成员。窗口太窄(<400)时默认只留 QQ秀，没有 QQ秀 就整栏隐藏（显式写 side=1 则保留成员栏）
    const narrow = w < 400;
    const wantMembers = P.side && !(narrow && Q.get('side') === null);
    const sideOn = wantMembers || P.show;
    const sd = $('side');
    sd.classList.toggle('hide', !sideOn);
    sd.classList.toggle('hasshow', P.show);
    sd.classList.toggle('noshow', !P.show);
    sd.classList.toggle('nomembers', !wantMembers);
    sideVisible = wantMembers;
    trim();
  }
  let sideVisible = true;
  window.addEventListener('resize', layout);

  // ---- 状态 ----
  const state = { botName: '猪猪侠', anchor: str('anchor', ''), roomTitle: '', online: null, total: null, chats: 0, gifts: 0, members: new Map() };
  function setTitle() {
    const t = P.title || ((state.anchor ? state.anchor + ' 的直播间' : '怀旧QQ直播间') + ' - 群聊');
    $('title').textContent = t + (state.online ? ' (' + state.online + '人)' : '');
    document.title = t;
    $('notice').textContent = '群公告：' + (P.notice || (state.roomTitle ? state.roomTitle + ' —— 欢迎大家发弹幕，文明聊天~' : '欢迎来到直播间，文明聊天，禁止刷屏~'));
    $('mcount').textContent = '群成员(' + (state.online || state.members.size) + ')';
  }
  const inputEl = $('input');
  inputEl.innerHTML = '<span class="ph"></span><span class="caret"></span>';
  inputEl.firstChild.textContent = P.input;

  // ---- 工具 ----
  const hash = s => { let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h; };
  const avatarOf = uid => 'img/avatar/' + (hash('a' + uid) % 117 + 1) + '.png';
  const qqnum = uid => String(10000 + hash('q' + uid) % 2000000000 + (hash(uid) % 7) * 1000).slice(0, 10);
  const pad = n => String(n).padStart(2, '0');
  const clock = ts => { const d = new Date(ts); return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()); };
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const EMO = { '微笑': '😊', '笑哭': '😂', '捂脸': '🤦', '赞': '👍', '鼓掌': '👏', '比心': '💗', '玫瑰': '🌹', '大笑': '😄', '呲牙': '😁',
    '流泪': '😭', '色': '😍', '害羞': '😳', '酷': '😎', '憨笑': '😅', '发呆': '😐', '惊讶': '😲', '偷笑': '🤭', '惊恐': '😱', '白眼': '🙄',
    '抱抱': '🤗', '再见': '👋', '握手': '🤝', 'ok': '👌', 'OK': '👌', '胜利': '✌️', '强': '💪', '拳头': '✊', '爱心': '❤️', '心碎': '💔',
    '蛋糕': '🎂', '礼物': '🎁', '干杯': '🍻', '吃瓜': '🍉', '奋斗': '💪', '玫瑰花': '🌹', '汗': '😓', '委屈': '🥺', '生气': '😠', '亲亲': '😘',
    '坏笑': '😏', '思考': '🤔', '睡': '😴', '晕': '😵', '尬笑': '😅', '哭': '😭', '送心': '💗', '感谢': '🙏', '祈祷': '🙏', '碰拳': '🤜' };
  function fmtText(t) {
    let s = esc(t);
    if (P.emoji) s = s.replace(/\[([^\[\]\s]{1,6})\]/g, (m, k) => EMO[k] || m);
    return s;
  }
  function wrapUser(ev) { return (window.PLAYX ? PLAYX.badge(ev.uid) : '') + esc(ev.name || '神秘人'); }   // 名字前面的 QQ 等级图标（play-core.js）

  // ---- 渲染 ----
  function addLi(cls, html) {
    const li = document.createElement('li');
    li.className = cls + ' new'; li.innerHTML = html; list.appendChild(li);
    trim(); list.scrollTop = list.scrollHeight;
    if (P.sound) { try { const a = $('snd'); a.currentTime = 0; a.play().catch(() => {}); } catch (e) {} }
    return li;
  }
  function trim() {
    while (list.children.length > P.max) list.removeChild(list.firstChild);
    // 保证只保留“放得下”的行，避免顶部出现被截断的半条消息
    list.scrollTop = list.scrollHeight;
  }
  function renderMembers() {
    $('mcount').textContent = '群成员(' + (state.online || state.members.size + 1) + ')';
    if (!sideVisible) return;
    const ul = $('mlist'); ul.innerHTML = '';
    if (state.anchor) { const a = document.createElement('li'); a.className = 'anchor'; a.innerHTML = '<img src="img/avatar/97.png">' + esc(state.anchor) + '(群主)'; ul.appendChild(a); }
    const bot = document.createElement('li'); bot.className = 'bot'; bot.innerHTML = '<img src="gg/head8.png">' + esc(state.botName) + '(AI)'; ul.appendChild(bot);
    [...state.members.entries()].reverse().forEach(([uid, name]) => {
      const li = document.createElement('li');
      li.innerHTML = '<img src="' + avatarOf(uid) + '">' + (window.PLAYX ? PLAYX.badge(uid, true) : '') + esc(name); ul.appendChild(li);
    });
  }
  window.QQRM = renderMembers;
  function touchMember(ev) {
    if (!ev.uid) return;
    state.members.delete(ev.uid);
    state.members.set(ev.uid, ev.name || '神秘人');
    while (state.members.size > 60) state.members.delete(state.members.keys().next().value);
    renderMembers();
  }
  const handlers = {
    chat(ev) {
      state.chats++; $('s-chats').textContent = state.chats;
      const my = state.anchor && ev.name === state.anchor;
      const ava = P.avatar ? '<img class="ava" src="' + avatarOf(ev.uid) + '">' : '';
      addLi(my ? 'my' : '', '<p>' + ava + wrapUser(ev) + '(' + qqnum(ev.uid) + ')<span>' + clock(ev.ts || Date.now()) + '</span></p><p>' + fmtText(ev.text) + '</p>');
      touchMember(ev);
    },
    gift(ev) {
      state.gifts += (ev.count || 1); $('s-gifts').textContent = state.gifts;
      if (P.gifts) addLi('gift', '<p class="sysline">【系统消息】<b>' + wrapUser(ev) + '</b> 送出了 ' + esc(ev.gift) + (ev.count > 1 ? ' ×' + ev.count : '') + '<span class="t">' + clock(ev.ts || Date.now()) + '</span></p>');
      touchMember(ev);
    },
    follow(ev) { if (P.follows) addLi('follow', '<p class="sysline">【系统消息】<b>' + wrapUser(ev) + '</b> 关注了群主，成为了新的群成员<span class="t">' + clock(ev.ts || Date.now()) + '</span></p>'); },
    member(ev) { if (P.enters) addLi('enter', '<p class="sysline">【系统消息】' + wrapUser(ev) + ' 加入了本群<span class="t">' + clock(ev.ts || Date.now()) + '</span></p>'); touchMember(ev); },
    like(ev) { if (P.likes) addLi('like', '<p class="sysline">【系统消息】' + wrapUser(ev) + ' 为群主点了 ' + ev.count + ' 个赞<span class="t">' + clock(ev.ts || Date.now()) + '</span></p>'); },
    sys(ev) { addLi('notice', '<p class="sysline">【系统消息】' + esc(ev.text) + '</p>'); },
    end() { addLi('notice', '<p class="sysline">【系统消息】群主已下线，本群聊天结束（直播已结束）</p>'); },
    stat(ev) { state.online = ev.online; state.total = ev.total; $('s-online').textContent = ev.online; $('s-total').textContent = ev.total; setTitle(); },
    room(ev) { state.anchor = str('anchor', '') || ev.anchor || state.anchor; state.roomTitle = ev.title || ''; if (ev.online) { state.online = ev.online; $('s-online').textContent = ev.online; } setTitle(); },
    say(ev) { enqueueSay(ev); },
    status(ev) { if (ev.level === 'error' || ev.level === 'warn') addLi('notice', '<p class="sysline">【系统提示】' + esc(ev.text) + '</p>'); },
  };


  // ================= QQ秀 / AI 主播（猪猪侠）：语音队列 + 动作 + 口型 =================
  const bubble = $('bubble'), btext = $('btext'), pigEl = $('pig'), pigMo = $('pigmotion'), pigPop = $('pigpop'), pigTalk = $('pigtalk'), zzz = $('zzz');
  const imgs = [$('poseA'), $('poseB')];
  const SP = { q: [], busy: false, ctx: null, analyser: null, buf: null, audio: null, hideT: null, typeT: null, flapUntil: 0 };
  const STALE_MS = 25000;
  // --- 姿势表（编号 = 素材文件 gg/pNN.webp，按原素材排序）---
  const POSE_MO = { 0: 'jump', 1: 'sleepy', 2: 'chomp', 3: 'pop', 4: 'shake', 5: 'droop', 6: 'sleep', 7: 'sleep', 8: 'idle', 9: 'wave', 10: 'sleepy', 11: 'chomp', 12: 'pop', 13: 'shake', 14: 'droop', 15: 'pump', 16: 'jump', 17: 'sleep' };
  const SLEEP_POSES = [6, 7, 17];
  const EMO_POSES = {            // AI 情绪标签 → 候选姿势
    '平静': [8, 15], '开心': [16, 0], '兴奋': [0, 16], '得意': [15, 16], '害羞': [5, 14], '难过': [14, 5],
    '生气': [13, 4], '惊讶': [3, 12], '挥手': [9], '吃': [11, 2], '困': [1, 10] };
  const KIND_POSES = { gift: [0, 2], follow: [16], welcome: [9], idle: [8, 15, 16] };
  const FOOD_RE = /吃|饿|糖|饭|零食|饼干|token|Token|好香|馋/;
  const PIG = { cur: -1, layer: 0, asleep: false, lastAct: Date.now(), nextIdle: Date.now() + 5000, nextSleepSwap: 0, talk: 0, holdUntil: 0 };
  const sleepAfter = num('sleep', 75) * 1000;     // 多少秒没动静就睡着；0=不睡
  const poseUrl = i => 'gg/p' + String(i).padStart(2, '0') + '.webp';
  for (let i = 0; i < 18; i++) { const im = new Image(); im.src = poseUrl(i); }    // 预加载，切换不闪
  const pick = (arr, avoid) => { const c = arr.filter(x => x !== avoid); const a = c.length ? c : arr; return a[Math.floor(Math.random() * a.length)]; };
  function setPose(i, force) {
    if (i === PIG.cur && !force) return;
    const nxt = imgs[1 - PIG.layer], old = imgs[PIG.layer];
    nxt.src = poseUrl(i); nxt.classList.add('on'); old.classList.remove('on'); PIG.layer = 1 - PIG.layer;
    const mo = POSE_MO[i] || 'idle';
    pigMo.style.animation = 'none'; void pigMo.offsetWidth; pigMo.style.animation = '';   // 重启该姿势的动作
    pigMo.setAttribute('data-mo', mo);
    pigPop.classList.remove('pop'); void pigPop.offsetWidth; pigPop.classList.add('pop');
    zzz.classList.toggle('on', SLEEP_POSES.includes(i) && i !== 6 || i === 10);
    PIG.cur = i;
  }
  function poseFor(ev) {
    const t = ev.text || '', emo = ev.emotion || '平静';
    if (ev.blocked) return pick(EMO_POSES['生气'], PIG.cur);
    if (ev.kind === 'gift') return /糖/.test(ev.text + (ev.gift || '')) ? 2 : pick(KIND_POSES.gift, PIG.cur);
    if (ev.kind === 'follow') return 16;
    if (ev.kind === 'welcome') return 9;
    if (emo !== '平静' && EMO_POSES[emo]) return pick(EMO_POSES[emo], PIG.cur);
    if (FOOD_RE.test(t)) return pick(EMO_POSES['吃'], PIG.cur);
    if (ev.kind === 'reply' && ev.hot) return pick([15, 8], PIG.cur);
    return pick(KIND_POSES[ev.kind] || EMO_POSES['平静'], PIG.cur);
  }
  function markActivity() {
    PIG.lastAct = Date.now();
    if (PIG.asleep) wake();
  }
  function wake() {            // 被吵醒：先“被戳鼻子”一惊，再回到待机
    PIG.asleep = false; setPose(Math.random() < 0.6 ? 3 : 0, true);
    PIG.holdUntil = Date.now() + 1700; PIG.nextIdle = Date.now() + 1800;
  }
  function fallAsleep() {
    PIG.asleep = true; setPose(pick([10, 1], PIG.cur)); PIG.nextSleepSwap = Date.now() + 5500;
  }
  setInterval(() => {         // 待机调度：随机小动作 / 犯困 / 睡着
    if (SP.busy) return;
    const now = Date.now();
    if (now < PIG.holdUntil) return;
    if (PIG.asleep) {
      if (now > PIG.nextSleepSwap) { setPose(pick(SLEEP_POSES, PIG.cur)); PIG.nextSleepSwap = now + 14000 + Math.random() * 8000; }
      return;
    }
    if (sleepAfter > 0 && now - PIG.lastAct > sleepAfter) return fallAsleep();
    if (now > PIG.nextIdle) {
      if (PIG.cur !== 8) { setPose(8); PIG.nextIdle = now + 4000 + Math.random() * 5000; }
      else { setPose(pick([15, 16, 1, 10, 9], 8)); PIG.nextIdle = now + 3500 + Math.random() * 3500; }
    }
  }, 700);
  window.QQPig = { setPose, markActivity, wake, fallAsleep, poseFor };   // 调试/截图用

  function ensureCtx() {
    if (SP.ctx) return;
    try { SP.ctx = new (window.AudioContext || window.webkitAudioContext)(); SP.analyser = SP.ctx.createAnalyser(); SP.analyser.fftSize = 512; SP.buf = new Uint8Array(SP.analyser.fftSize); SP.analyser.connect(SP.ctx.destination); } catch (e) { SP.ctx = null; }
  }
  (function talkLoop() {          // 没有嘴部帧：用声音音量驱动身体弹跳/缩放
    let open = 0;
    if (SP.busy) {
      if (SP.audio && SP.analyser && !SP.audio.paused) {
        SP.analyser.getByteTimeDomainData(SP.buf);
        let sum = 0; for (let i = 0; i < SP.buf.length; i++) { const v = (SP.buf[i] - 128) / 128; sum += v * v; }
        open = Math.min(1, Math.sqrt(sum / SP.buf.length) * 5 / Math.max(0.15, P.volume));
      } else if (performance.now() < SP.flapUntil) {
        open = 0.2 + Math.abs(Math.sin(performance.now() / 95)) * 0.55 * (0.6 + 0.4 * Math.sin(performance.now() / 430));
      }
    }
    PIG.talk += (open - PIG.talk) * 0.45;
    pigTalk.style.setProperty('--talk', PIG.talk < 0.02 ? 0 : PIG.talk.toFixed(3));
    requestAnimationFrame(talkLoop);
  })();

  function enqueueSay(ev) {
    SP.q.push(ev);
    const now = Date.now();
    SP.q = SP.q.filter(x => x === ev || x.prio >= 70 || now - (x.ts || now) < STALE_MS);
    SP.q.sort((a, b) => b.prio - a.prio || a.ts - b.ts);
    while (SP.q.length > 6) SP.q.pop();          // 丢最低优先级
    kick();
  }
  function kick() { if (!SP.busy && SP.q.length) play(SP.q.shift()); }
  function showBubble(text, dur) {
    clearTimeout(SP.hideT); clearInterval(SP.typeT);
    bubble.classList.add('on');
    const chars = [...text]; let i = 0;
    const step = Math.max(40, Math.min(160, (dur * 850) / chars.length));
    btext.textContent = '';
    SP.typeT = setInterval(() => { i = Math.min(chars.length, i + 1); btext.textContent = chars.slice(0, i).join(''); if (i >= chars.length) clearInterval(SP.typeT); }, step);
  }
  function finish(ev) {
    SP.busy = false; SP.audio = null;
    clearInterval(SP.typeT); btext.textContent = ev.text;
    PIG.holdUntil = Date.now() + 1500; PIG.nextIdle = Date.now() + 2600;
    SP.hideT = setTimeout(() => { if (!SP.busy) bubble.classList.remove('on'); }, 1800);
    setTimeout(kick, 350);
  }
  function play(ev) {
    SP.busy = true; PIG.lastAct = Date.now();
    state.botName = ev.name || state.botName;
    const wasAsleep = PIG.asleep; PIG.asleep = false;
    if (wasAsleep) setPose(3, true);                       // 先被惊醒
    const p1 = poseFor(ev);
    setTimeout(() => setPose(p1), wasAsleep ? 650 : 0);
    if ((ev.dur || 0) > 4.2) {                              // 长句说到一半换个动作，不呆板
      const alt = pick(EMO_POSES[ev.emotion] || EMO_POSES['平静'], p1);
      setTimeout(() => { if (SP.busy && alt !== PIG.cur) setPose(alt); }, (wasAsleep ? 650 : 0) + ev.dur * 520);
    }
    // 同步进群聊：开口的同时，群里出现一条主播的消息
    addLi('my', '<p>' + esc(state.botName) + '(' + qqnum('bot') + ')<span>' + clock(Date.now()) + '</span></p><p>' + fmtText(ev.text) + '</p>');
    if (P.show) showBubble(ev.text, ev.dur || 3);
    let done = false; const end = () => { if (!done) { done = true; finish(ev); } };
    const fallback = ms => { SP.flapUntil = performance.now() + ms; setTimeout(end, ms); };
    if (ev.audio && P.voice) {
      ensureCtx();
      const a = new Audio(ev.audio); a.volume = P.volume; SP.audio = a;
      try { if (SP.ctx) { SP.ctx.resume(); SP.ctx.createMediaElementSource(a).connect(SP.analyser); } } catch (e) {}
      a.onended = end; a.onerror = () => fallback((ev.dur || 3) * 1000);
      a.play().then(() => { $('soundhint').classList.add('hide'); }).catch(() => {
        SP.audio = null; $('soundhint').classList.remove('hide'); fallback((ev.dur || 3) * 1000);
      });
      setTimeout(end, ((ev.dur || 3) + 6) * 1000);   // 兜底：音频卡死也不会堵住队列
    } else if (ev.browser_tts && P.voice && window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(ev.text); u.lang = 'zh-CN'; u.volume = P.volume;
      u.onstart = () => { SP.flapUntil = performance.now() + 60000; }; u.onend = end; u.onerror = end;
      speechSynthesis.speak(u); setTimeout(end, ((ev.dur || 3) + 8) * 1000);
    } else fallback((ev.dur || Math.max(1.8, ev.text.length * 0.28)) * 1000);
  }
  document.addEventListener('click', () => { $('soundhint').classList.add('hide'); if (SP.ctx) SP.ctx.resume(); });
  if (!P.show) { $('stage').parentNode.classList.add('hide'); }
  setPose(8, true);

  // ---- 队列限速：弹幕爆发时匀速上屏，积压过多丢最旧的 ----
  const queue = [];
  function push(ev) {
    try { document.dispatchEvent(new CustomEvent('qqev', { detail: ev })); } catch (e) {}   // qq-core.js 的事件总线（礼物 → 效果、QQ空间留言…）
    if (['chat', 'gift', 'follow', 'member'].includes(ev.t)) markActivity();
    if (P.demo && wsRef && wsRef.readyState === 1 && ev.t !== 'say' && ev.t !== 'play' && !ev.play) { try { wsRef.send(JSON.stringify({ ev })); } catch (e) {} }
    if (ev.t === 'chat' || ev.t === 'gift' || ev.t === 'follow' || ev.t === 'member' || ev.t === 'like') {
      queue.push(ev);
      if (queue.length > 120) queue.splice(0, queue.length - 60);
    } else if (handlers[ev.t]) handlers[ev.t](ev);
  }
  setInterval(() => {
    // 积压越多出得越快，但每个 tick 最多 3 条
    const n = Math.min(queue.length, queue.length > 40 ? 3 : queue.length > 15 ? 2 : 1);
    for (let i = 0; i < n; i++) { const ev = queue.shift(); handlers[ev.t](ev); }
  }, 1000 / P.rate);

  // ---- 数据源 ----
  function startDemo() {
    const names = ['痴情梦丶', 'メ乖乖女ソ', '☆﹏雨后彩虹', '冷月无声', '小丑@鱼', '︵ˊ悠悠_ㄣ', '蓝色の忧郁', '﹏吥﹏离呮ゝ伱', '~*流星雨*~', '孤独de狼', '┈━═☆小可爱', '＠_＠偶是MM', '阿杰', '暗夜精灵', 'ゞ旧情人ゞ', '坏小孩', '花样年华', '◆无名小卒◆', '宝贝ㄟ天使', 'Mr.Right', '糖果屋', '随风飘逝', '灬浪子灬', '☆彡幸运草', '大头鬼', '清风徐来', '三好学生', '凉凉'];
    const lines = ['有人在吗？', '沙发！！', '前排围观~', '主播好人一生平安', '求黄钻，谁有送我一个呗', '哈哈哈哈哈哈', '顶一个', '88，我先去吃饭了', '楼上的是MM还是GG？', '斑竹加精！', '5555555~~', '晕~', '主播唱得真好听[赞]', '大家晚上好呀', '今天太阳升级了耶', '我也是90后！', '回复楼上：BS你', '这首歌我QQ空间也设成背景音乐了', '来了来了~', '偶像！', '[捂脸][捂脸]', '好怀念啊，当年天天挂Q', '[鼓掌][鼓掌][鼓掌]', '主播看我看我', '有没有人一起斗地主', '签到签到', '[比心]', '我QQ号被盗了，555', '别刷屏啊，会被踢的', '同学们好！', '笑死我了，LOL', '在这个年代还有人用QQ，感动', '下一首唱《暗号》吧', '666666', '挂机等太阳，各位随意', '谁能教我怎么装修Q-Zone啊', '好听！加我QQ交个朋友', 'GG们都去哪了', '哇，这就是传说中的青春吗', '路过，顺便踩踩'];
    const gifts = ['玫瑰花', '小心心', '啤酒', '嘉年华', '加油鸭', '飞吻'];
    let n = 0;
    handlers.room({ anchor: str('anchor', 'GG-Bond'), title: 'QQ聊天室', live: true });
    let online = 2368;
    const tick = () => {
      const r = Math.random(), u = Math.floor(Math.random() * names.length), uid = 'd' + u;
      const nm = names[u];
      if (r < 0.77) push({ t: 'chat', uid, name: nm, text: lines[Math.floor(Math.random() * lines.length)], ts: Date.now() });
      else if (r < 0.81) push({ t: 'gift', uid, name: nm, gift: gifts[Math.floor(Math.random() * gifts.length)], count: 1 + Math.floor(Math.random() * 5), ts: Date.now() });
      else if (r < 0.88) push({ t: 'follow', uid, name: nm, ts: Date.now() });
      else if (r < 0.95) push({ t: 'member', uid, name: nm, ts: Date.now() });
      else push({ t: 'like', uid, name: nm, count: 1 + Math.floor(Math.random() * 30), ts: Date.now() });
      if (++n % 8 === 0) { online += Math.floor(Math.random() * 21) - 8; push({ t: 'stat', online, total: (online * 7 / 10000).toFixed(1) + '万' }); }
      setTimeout(tick, 400 + Math.random() * 1400);
    };
    if (bool('demoquiet', false)) return;   // demoquiet=1：演示房间不放假弹幕（测试“冷场时猪猪侠自己玩电脑”用）
    tick();
  }
  let wsRef = null;
  function startWS(room) {
    const url = str('ws', (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
    let retry = 1000;
    const connect = () => {
      const ws = new WebSocket(url);
      ws.onopen = () => { retry = 1000; wsRef = ws; ws.send(JSON.stringify({ sub: room, host: P.host })); };
      ws.onmessage = e => { try { const ev = JSON.parse(e.data); if (ev.t === 'reload') return location.reload(); if (ev.t === 'autoclose_cfg') { window.AC && AC.setCfg(ev.cfg); return; } if (ev.t === 'switch' && room !== 'demo' && ev.room) { const u = new URL(location.href); if (u.searchParams.has('room')) { u.searchParams.set('room', ev.room); location.href = u.toString(); } else location.reload(); return; } if (room === 'demo' && ev.t !== 'say' && ev.t !== 'play' && !(ev.t === 'sys' && ev.play)) return; push(ev); } catch (err) {} };
      ws.onclose = () => { wsRef = null; setTimeout(connect, retry); retry = Math.min(retry * 2, 10000); };
    };
    connect();
  }

  layout(); setTitle(); renderMembers();
  fetch('config.json').then(r => r.json()).then(c => {
    state.botName = c.host_name || state.botName; $('hostlabel').textContent = str('label', c.host_label || 'AI虚拟主播');
    $('showname').textContent = state.botName + '的QQ秀'; renderMembers();
  }).catch(() => { $('hostlabel').textContent = str('label', 'AI虚拟主播'); });
  if (P.demo) { if (P.host) startWS('demo'); startDemo(); }
  else if (P.room) startWS(P.room);
  else fetch('config.json').then(r => r.json()).then(c => {
    if (c.host_name) state.botName = c.host_name;
    if (c.room) startWS(c.room);
    else addLi('notice', '<p class="sysline">【系统提示】没有指定直播间：请用 ?room=直播间号 或 ?demo=1 查看演示</p>');
  }).catch(() => startDemo());
})();
