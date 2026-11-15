# -*- coding: utf-8 -*-
"""
抖音直播间弹幕抓取（精简改写版）

基于 saermart/DouyinLiveWebFetcher（AGPL-3.0）的协议/签名实现：
  - sign.js / a_bogus.js / ac_signature.py / protobuf/douyin.py 为上游原文件
  - 本文件 = 上游 liveMan.py 的改写：去掉 print，改成回调；加了断线重连；
    用 mini_racer（内置 V8）执行 JS，不需要安装 Node。
"""
import codecs
import gzip
import hashlib
import random
import re
import string
import threading
import time
import urllib.parse
from pathlib import Path

import requests
import websocket
from py_mini_racer import MiniRacer

from .protobuf.douyin import (PushFrame, Response, ChatMessage, GiftMessage, LikeMessage,
                              MemberMessage, SocialMessage, RoomUserSeqMessage,
                              ControlMessage, EmojiChatMessage, FansclubMessage)
from .ac_signature import get__ac_signature

HERE = Path(__file__).parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0")


def gen_ms_token(length=182):
    base = string.ascii_letters + string.digits + '-_'
    return ''.join(random.choice(base) for _ in range(length))


def gen_signature(wss: str) -> str:
    params = ("live_id,aid,version_code,webcast_sdk_version,room_id,sub_room_id,sub_channel_id,"
              "did_rule,user_unique_id,device_platform,device_type,ac,identity").split(',')
    q = urllib.parse.urlparse(wss).query.split('&')
    maps = {i.split('=')[0]: i.split('=')[-1] for i in q}
    param = ','.join(f"{i}={maps.get(i, '')}" for i in params)
    md5 = hashlib.md5(param.encode()).hexdigest()
    script = codecs.open(HERE / 'sign.js', 'r', encoding='utf8').read()
    ctx = MiniRacer()
    ctx.eval(script)
    return ctx.call("get_sign", md5)


class RoomNotLive(Exception):
    """房间页里没有 roomId：没开播 / 房间号写错。"""


class DouyinFetcher:
    """emit(event: dict) 会在后台线程被调用。

    opts（来自 config.ini [ops]）：
      live_gate    True = 房间没开播就不连 WebSocket，每 poll 秒查一次，开播了自动连（False = 老行为：不管开没开播都连）
      poll         未开播时的轮询间隔（秒）
      backoff_min / backoff_max   断线 / 出错后的重连退避（秒，指数 + 抖动；连上并稳定 30 秒后重置）
      stale_secs   已连接但这么久没收到任何帧（含心跳回应）就当断了，主动重连；0 = 不检测
      recheck      已连接时每隔这么多秒再查一次「还在直播吗」；0 = 不查。要同时满足才当下播（平台强制关播 / 没收到下播消息时靠它发现）：
                   接口明确说「已结束」连续 recheck_need（3）次、第一次到最后一次相隔 ≥ recheck_span（90）秒、这期间 recheck_quiet（90）秒内没收到任何消息。
                   接口出错 / 返回空 / 没有 room_status 都算「不知道」，不算已结束，并让连续计数清零
    对外状态：state（init/preparing/offline/connecting/connected/backoff/stopped）、live（None 未知 / True / False）、info、connects / reconnects、last_error。
    live 变化时 emit {"t":"live","live":bool,...}。
    """

    def __init__(self, live_id: str, emit, log=print, opts=None):
        self.live_id = str(live_id)
        self.emit = emit
        self.log = log
        o = opts or {}
        self.live_gate = bool(o.get("live_gate", True))
        self.poll = max(1.0, float(o.get("poll", 30)))
        self.bo_min = max(1.0, float(o.get("backoff_min", 3)))
        self.bo_max = max(self.bo_min, float(o.get("backoff_max", 60)))
        self.stale = float(o.get("stale_secs", 60))
        self.recheck = float(o.get("recheck", 0))
        self.rc_need = max(2, int(float(o.get("recheck_need", 3))))          # 连续几次「已结束」
        self.rc_span = max(0.0, float(o.get("recheck_span", 90)))            # 并且第一次到最后一次至少隔这么久（秒）
        self.rc_quiet = max(0.0, float(o.get("recheck_quiet", 90)))          # 并且这么久没有任何弹幕 / 进场 / 点赞消息
        self._rc_first = 0.0
        self._rc_at = 0.0
        self._rc_off = 0
        self._rc_busy = False
        self.session = requests.Session()
        self.ttwid = None
        self.room_id = None
        self.ws = None
        self._stop = threading.Event()
        self._thread = None
        self.connected = False
        self.last_msg_ts = 0.0
        self.last_rx = 0.0
        self.msg_count = 0
        self.state = "init"
        self.live = None
        self.info = {}
        self.connects = 0
        self.reconnects = 0
        self.last_error = ""
        self.connected_at = 0.0
        self.ended_at = 0.0
        self.unknown_polls = 0
        self.fresh = False

    # ---------- 生命周期 ----------
    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"dy-{self.live_id}")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.state = "stopped"
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass

    def snapshot(self):
        return {"room": self.live_id, "room_id": self.room_id, "state": self.state, "live": self.live, "connected": self.connected, "anchor": self.info.get("anchor", ""),
                "title": self.info.get("title", ""), "msgs": self.msg_count, "connects": self.connects, "reconnects": self.reconnects, "last_error": self.last_error,
                "connected_for": int(time.time() - self.connected_at) if self.connected else 0, "last_rx_ago": int(time.time() - self.last_rx) if self.last_rx else None,
                "last_msg_ago": int(time.time() - self.last_msg_ts) if self.last_msg_ts else None}

    def _status(self, msg, level="info"):
        self.log(f"[{self.live_id}] {msg}")
        self.emit({"t": "status", "level": level, "text": msg})

    def _set_live(self, live, info=None):
        """live 变化才发事件（None = 不知道，不当成变化）。"""
        if info:
            self.info = info
        if live is None or live == self.live:
            return
        self.live = live
        self.emit({"t": "live", "live": live, "room": self.live_id, "room_id": self.room_id, "anchor": self.info.get("anchor", ""), "title": self.info.get("title", "")})

    def _run(self):
        backoff = self.bo_min
        while not self._stop.is_set():
            loop_start = time.time()
            try:
                self.state = "preparing"
                self.ttwid = self.room_id = None
                self.session = requests.Session()
                try:
                    self._prepare()
                except RoomNotLive as e:
                    if not self.live_gate:
                        raise RuntimeError(str(e))
                    self._set_live(False)
                    self._status(f"{e}（每 {int(self.poll)} 秒检查一次，开播后自动连接）", "warn")
                if self.live_gate and self.live is False:
                    if not self._offline_wait():
                        break
                    backoff = self.bo_min
                    continue                      # 开播了：重新取一次（新场次 room_id 会变）
                self.state = "connecting"
                self._connect()                   # 阻塞直到断开
                if self.live_gate and self.ended_at and time.time() - self.ended_at < 10:
                    if not self._offline_wait():  # 刚下播：回到“等开播”，不立刻重连
                        break
                    backoff = self.bo_min
                    continue
            except Exception as e:                # noqa
                self.last_error = repr(e)[:200]
                self._status(f"出错：{e!r}", "error")
            self.connected = False
            if self._stop.is_set():
                break
            if self.connected_at > loop_start and time.time() - self.connected_at > 30:
                backoff = self.bo_min             # 上一次连得挺久：不是网络抖得厉害，重新从最短间隔开始
            self.reconnects += 1
            wait = backoff * random.uniform(0.8, 1.25)
            self.state = "backoff"
            self._status(f"{wait:.0f}s 后重连…", "warn")
            self._stop.wait(wait)
            backoff = min(backoff * 2, self.bo_max)
        self.state = "stopped"

    def _offline_wait(self):
        """未开播：轮询到开播。返回 True = 开播了（或查不到状态，试着连），False = 被停止。"""
        self.state = "offline"
        if self.ended_at and time.time() - self.ended_at < self.poll:          # 刚收到下播信号：先等一轮，免得状态没刷新又连回去
            self._stop.wait(self.poll)
        while not self._stop.is_set():
            live = self._poll_live()
            if live:
                self._status("直播间开播了，开始连接", "ok")
                return True
            if live is None:
                self.unknown_polls += 1
                if self.unknown_polls >= 3:   # 状态一直查不到：别傻等，连上试试（和老行为一致）
                    self.unknown_polls = 0
                    self.live = None
                    return True
            else:
                self.unknown_polls = 0
            self._stop.wait(self.poll)
        return False

    def _poll_live(self):
        """True / False / None（没查到）。只发请求，不连 WebSocket。"""
        try:
            self.session = requests.Session()
            self._prepare()
        except RoomNotLive:
            self._set_live(False)
            return False
        except Exception as e:  # noqa
            self.last_error = repr(e)[:200]
            self.log(f"[{self.live_id}] 开播状态查询失败：{e!r}")
            return None
        return self.live if self.fresh else None

    # ---------- 准备：ttwid / room_id ----------
    def _prepare(self):
        r = self.session.get("https://live.douyin.com/", headers={"User-Agent": UA}, timeout=15)
        self.ttwid = r.cookies.get('ttwid') or self.session.cookies.get('ttwid')
        if not self.ttwid:
            raise RuntimeError("拿不到 ttwid（可能被抖音风控/网络不通）")
        headers = {"User-Agent": UA,
                   "cookie": f"ttwid={self.ttwid}&msToken={gen_ms_token()}; __ac_nonce=0123407cc00a9e438deb4"}
        r = self.session.get(f"https://live.douyin.com/{self.live_id}", headers=headers, timeout=15)
        m = re.search(r'roomId\\":\\"(\d+)\\"', r.text)
        if not m:
            raise RoomNotLive("找不到 roomId：主播没在直播，或直播间号写错了（请填 live.douyin.com/ 后面的数字）")
        self.room_id = m.group(1)
        info = self._room_info()
        self.fresh = bool(info)
        if info:
            self.emit({"t": "room", **info})
            was = self.info.get("title")
            if was != info.get("title") or self.state != "offline":
                self._status(f"直播间：{info.get('anchor','?')} / {info.get('title','')}  状态：{info.get('live') and '直播中' or '未开播/已结束'}")
            self._set_live(bool(info.get("live")), info)
            if not info.get("live") and not self.live_gate:
                self._status("提示：该直播间当前未开播，连上也收不到弹幕", "warn")

    def _room_info(self, tries=4):
        """尽力而为：取主播昵称/标题/是否开播。失败不影响主流程。

        以前这里有两种“取房间信息失败”：
          1. TypeError 'NoneType' object is not iterable —— __ac_nonce 只在会话第一次访问 www.douyin.com 时下发，重试时拿到 None（已修）；
          2. JSONDecodeError —— 抖音对 a_bogus 签名偶发返回空内容（风控，大约三成），所以这里换新的 msToken 重试几次，最后失败才记一条日志。"""
        last = ""
        for k in range(tries):
            try:
                ms = gen_ms_token()
                resp = self.session.get("https://www.douyin.com/", headers={"User-Agent": UA}, timeout=15)
                # __ac_nonce 只在「这个会话第一次访问 www.douyin.com」时由 Set-Cookie 下发；第二次起响应里没有
                nonce = resp.cookies.get("__ac_nonce") or self.session.cookies.get("__ac_nonce") or "".join(random.choice("0123456789abcdef") for _ in range(21))
                sig = get__ac_signature("www.douyin.com", nonce, UA)
                url = ('https://live.douyin.com/webcast/room/web/enter/?aid=6383'
                       '&app_name=douyin_web&live_id=1&device_platform=web&language=zh-CN&enter_from=page_refresh'
                       '&cookie_enabled=true&screen_width=1920&screen_height=1080&browser_language=zh-CN&browser_platform=Win32'
                       '&browser_name=Edge&browser_version=140.0.0.0'
                       f'&web_rid={self.live_id}&room_id_str={self.room_id}'
                       '&enter_source=&is_need_double_stream=false&insert_task_id=&live_reason=&msToken=' + ms)
                qs = urllib.parse.urlparse(url).query
                ctx = MiniRacer()
                ctx.eval((HERE / 'a_bogus.js').read_text(encoding='utf8'))
                params = dict(i.split('=', 1) for i in qs.split('&'))
                ab = ctx.call("get_ab", urllib.parse.urlencode(params), UA)
                url += f"&a_bogus={ab}"
                hdr = {"User-Agent": UA, "Referer": f"https://live.douyin.com/{self.live_id}",
                       "Cookie": f"ttwid={self.ttwid};__ac_nonce={nonce}; __ac_signature={sig}"}
                resp = self.session.get(url, headers=hdr, timeout=15)
                if not resp.content.strip():
                    last = f"接口返回空内容(HTTP {resp.status_code})，a_bogus 被风控偶发拦截"
                    self._stop.wait(0.4 * (k + 1))
                    continue
                data = resp.json().get("data") or {}
                rooms = data.get("data") or []
                room = rooms[0] if rooms else {}
                user = data.get("user") or room.get("owner") or {}
                rs = data.get("room_status")
                return {"anchor": user.get("nickname", ""), "title": room.get("title", ""),
                        "live": rs == 0, "status": rs,              # status None = 接口没给（限流 / 风控的空壳 JSON），不是「已结束」
                        "online": (room.get("room_view_stats") or {}).get("display_value")}
            except Exception as e:  # noqa
                last = repr(e)
                self._stop.wait(0.4 * (k + 1))
        self.log(f"[{self.live_id}] 取房间信息失败(不影响弹幕，已重试 {tries} 次): {last}")
        return None

    # ---------- WebSocket ----------
    def _connect(self):
        rid = self.room_id
        wss = ("wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/?app_name=douyin_web"
               "&version_code=180800&webcast_sdk_version=1.0.14-beta.0"
               "&update_version_code=1.0.14-beta.0&compress=gzip&device_platform=web&cookie_enabled=true"
               "&screen_width=1536&screen_height=864&browser_language=zh-CN&browser_platform=Win32"
               "&browser_name=Mozilla"
               "&browser_version=5.0%20(Windows%20NT%2010.0;%20Win64;%20x64)%20AppleWebKit/537.36%20(KHTML,"
               "%20like%20Gecko)%20Chrome/126.0.0.0%20Safari/537.36"
               "&browser_online=true&tz_name=Asia/Shanghai"
               "&cursor=d-1_u-1_fh-7392091211001140287_t-1721106114633_r-1"
               f"&internal_ext=internal_src:dim|wss_push_room_id:{rid}|wss_push_did:7319483754668557238"
               "|first_req_ms:1721106114541|fetch_time:1721106114633|seq:1|wss_info:0-1721106114633-0-0|"
               "wrds_v:7392094459690748497"
               "&host=https://live.douyin.com&aid=6383&live_id=1&did_rule=3&endpoint=live_pc&support_wrds=1"
               "&user_unique_id=7319483754668557238&im_path=/webcast/im/fetch/&identity=audience"
               f"&need_persist_msg_count=15&insert_task_id=&live_reason=&room_id={rid}&heartbeatDuration=0")
        wss += f"&signature={gen_signature(wss)}"
        hb_stop = threading.Event()

        def on_open(ws):
            self.connected = True
            self.state = "connected"
            self.connects += 1
            self.connected_at = self.last_rx = time.time()
            self._status("WebSocket 已连接，等待弹幕…", "ok")
            threading.Thread(target=self._heartbeat, args=(ws, hb_stop), daemon=True).start()

        def on_error(ws, err):
            self.log(f"[{self.live_id}] ws error: {err!r}")

        def on_close(ws, *a):
            hb_stop.set()
            self.connected = False
            self._status("WebSocket 已断开", "warn")

        def on_rx(ws, *a):
            self.last_rx = time.time()

        self.ws = websocket.WebSocketApp(
            wss, header={"cookie": f"ttwid={self.ttwid}", "user-agent": UA},
            on_open=on_open, on_message=self._on_message, on_error=on_error, on_close=on_close, on_pong=on_rx, on_ping=on_rx)
        self.ws.run_forever(ping_interval=0)

    def _recheck_live(self, ws):
        """连着的时候也定期查一次房间状态：抖音强制关播（比如真人验证没通过）时，WebSocket 不一定收到下播消息，
        连接还「活着」只是再没有数据——只靠 stale 检测发现不了。
        只有强信号一起成立才算下播：接口**明确**说结束（room_status 有值且不是 0）连续 rc_need 次、跨度 ≥ rc_span 秒、
        这段时间内一条消息都没收到。接口出错 / 空内容 / 没给状态 = 不知道，计数清零；只要还在收到弹幕 / 进场消息，就当没下播。"""
        try:
            if self.live is False:
                return
            info = self._room_info(tries=2)
            if not info or self._stop.is_set() or self.live is False:
                self._rc_off = 0                                # 查不到 = 不知道，不算已结束，也不累计
                return
            st = info.get("status")
            if info.get("live") or st is None or st == 0:
                self._rc_off = 0
                return
            now = time.time()
            if now - self.last_msg_ts < self.rc_quiet:
                self._rc_off = 0                                # 还在收消息：接口说结束也不信
                return
            if self._rc_off == 0:
                self._rc_first = now
            self._rc_off += 1
            if self._rc_off < self.rc_need or now - self._rc_first < self.rc_span:
                return
            self._status(f"复查：直播间连续 {self._rc_off} 次查到已结束（room_status={st}，{int(now - self._rc_first)} 秒内没收到任何消息，多半是平台关了播）", "warn")
            self.ended_at = time.time()
            self.emit({"t": "end", "reason": "recheck", "ts": int(time.time() * 1000)})
            self._set_live(False)
            try:
                ws.close()
            except Exception:
                pass
        finally:
            self._rc_busy = False

    def _heartbeat(self, ws, stop):
        self._rc_at = time.time()
        self._rc_off = 0
        while not stop.wait(5):
            if self.recheck and not self._rc_busy and time.time() - self._rc_at >= self.recheck and self.live is not False:
                self._rc_at = time.time()
                self._rc_busy = True
                threading.Thread(target=self._recheck_live, args=(ws,), daemon=True, name="dy-recheck").start()
            if self.stale and self.last_rx and time.time() - self.last_rx > self.stale:
                self._status(f"{int(time.time() - self.last_rx)} 秒没收到任何数据，连接可能已死，重连", "warn")
                try:
                    ws.close()
                except Exception:
                    pass
                break
            try:
                ws.send(PushFrame(payload_type='hb').SerializeToString(), websocket.ABNF.OPCODE_PING)
            except Exception:
                break

    def _on_message(self, ws, message):
        self.last_rx = time.time()
        try:
            package = PushFrame().parse(message)
            response = Response().parse(gzip.decompress(package.payload))
        except Exception as e:  # noqa
            self.log(f"parse error {e!r}")
            return
        if response.need_ack:
            ack = PushFrame(log_id=package.log_id, payload_type='ack',
                            payload=response.internal_ext.encode('utf-8')).SerializeToString()
            ws.send(ack, websocket.ABNF.OPCODE_BINARY)
        for msg in response.messages_list:
            fn = self._HANDLERS.get(msg.method)
            if not fn:
                continue
            try:
                ev = fn(self, msg.payload)
            except Exception:
                continue
            if ev:
                self.msg_count += 1
                self.last_msg_ts = time.time()
                ev.setdefault("ts", int(time.time() * 1000))
                self.emit(ev)
                if ev.get("t") == "end":                      # 主播下播：断开，回到“等开播”
                    self.ended_at = time.time()
                    self._set_live(False)
                    self._status("主播已下播", "warn")
                    try:
                        ws.close()
                    except Exception:
                        pass

    # ---------- 各类消息 -> 统一事件 ----------
    @staticmethod
    def _u(user):
        return {"uid": str(user.id), "name": user.nick_name or "神秘人",
                "gender": {1: "m", 2: "f"}.get(user.gender, "")}

    def _chat(self, p):
        m = ChatMessage().parse(p)
        return {"t": "chat", **self._u(m.user), "text": m.content}

    def _emoji_chat(self, p):
        m = EmojiChatMessage().parse(p)
        return {"t": "chat", **self._u(m.user), "text": m.default_content or "[表情]"}

    def _gift(self, p):
        m = GiftMessage().parse(p)
        return {"t": "gift", **self._u(m.user), "gift": m.gift.name, "count": m.combo_count or 1, "value": int(getattr(m.gift, "diamond_count", 0) or 0)}

    def _like(self, p):
        m = LikeMessage().parse(p)
        return {"t": "like", **self._u(m.user), "count": m.count}

    def _member(self, p):
        m = MemberMessage().parse(p)
        return {"t": "member", **self._u(m.user)}

    def _social(self, p):
        m = SocialMessage().parse(p)
        return {"t": "follow", **self._u(m.user)}

    def _stat(self, p):
        m = RoomUserSeqMessage().parse(p)
        return {"t": "stat", "online": m.total, "total": m.total_pv_for_anchor}

    def _fans(self, p):
        m = FansclubMessage().parse(p)
        return {"t": "sys", "text": m.content} if m.content else None

    def _control(self, p):
        m = ControlMessage().parse(p)
        if m.status == 3:
            return {"t": "end"}
        return None

    _HANDLERS = {
        'WebcastChatMessage': _chat,
        'WebcastEmojiChatMessage': _emoji_chat,
        'WebcastGiftMessage': _gift,
        'WebcastLikeMessage': _like,
        'WebcastMemberMessage': _member,
        'WebcastSocialMessage': _social,
        'WebcastRoomUserSeqMessage': _stat,
        'WebcastFansclubMessage': _fans,
        'WebcastControlMessage': _control,
    }
