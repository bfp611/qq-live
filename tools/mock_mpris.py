#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发/测试用：在 D-Bus 会话总线上伪造一个 MPRIS 播放器（假装是 Linux 版网易云音乐），用来测试 backend/osmusic.py 的 Linux 路径。
需要：pip install dbus-fast ；在 dbus-run-session 里跑：
    dbus-run-session -- python tools/mock_mpris.py [--name netease-cloud-music] [--log /tmp/mpris-open.log]
- 收到 OpenUri("orpheus://<base64 json>") 就把日志写到 --log，并切到对应 id 的假歌曲（找不到 id 的歌 = 假装没版权，保持原状）
- 每次 Next 切到下一首
"""
import argparse
import asyncio
import base64
import json
import time

from dbus_fast import Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, dbus_property, method, PropertyAccess

SONGS = {
    "1001": ("晴天", ["周杰伦"], "叶惠美", 269),
    "1002": ("稻香", ["周杰伦"], "魔杰座", 223),
    "1003": ("坏女孩", ["徐良", "小凌"], "不良少年", 242),
}
ORDER = list(SONGS)


class Root(ServiceInterface):
    def __init__(self, ident):
        super().__init__("org.mpris.MediaPlayer2")
        self.ident = ident

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return self.ident

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":
        return False


class Player(ServiceInterface):
    def __init__(self, a):
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.a = a
        self.sid = a.start
        self.status = "Playing"
        self.t0 = time.time()
        self.base = 0.0
        self.opened = open(a.log, "a") if a.log else None

    def pos(self):
        return self.base + ((time.time() - self.t0) if self.status == "Playing" else 0)

    def meta(self):
        t, ar, al, dur = SONGS[self.sid]
        return {"mpris:trackid": Variant("o", "/org/mock/track/" + self.sid), "mpris:length": Variant("x", dur * 1000000),
                "xesam:title": Variant("s", t), "xesam:artist": Variant("as", ar), "xesam:album": Variant("s", al),
                **({"mpris:artUrl": Variant("s", "file://" + self.a.art)} if self.a.art else {})}

    def set_song(self, sid):
        self.sid, self.base, self.t0, self.status = sid, 0.0, time.time(), "Playing"
        self.emit_properties_changed({"Metadata": self.meta(), "PlaybackStatus": self.status})

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        return self.status

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        return self.meta()

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        return int(self.pos() * 1000000)

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Rate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def Volume(self) -> "d":
        return 1.0

    @method()
    def Next(self):
        self.set_song(ORDER[(ORDER.index(self.sid) + 1) % len(ORDER)])

    @method()
    def Previous(self):
        self.set_song(ORDER[(ORDER.index(self.sid) - 1) % len(ORDER)])

    @method()
    def Play(self):
        if self.status != "Playing":
            self.t0, self.status = time.time(), "Playing"
            self.emit_properties_changed({"PlaybackStatus": self.status})

    @method()
    def Pause(self):
        if self.status == "Playing":
            self.base, self.status = self.pos(), "Paused"
            self.emit_properties_changed({"PlaybackStatus": self.status})

    @method()
    def PlayPause(self):
        self.Pause() if self.status == "Playing" else self.Play()

    @method()
    def OpenUri(self, uri: "s"):
        if self.opened:
            self.opened.write(uri + "\n")
            self.opened.flush()
        if uri.startswith("orpheus://"):
            try:
                d = json.loads(base64.b64decode(uri[len("orpheus://"):]).decode())
            except Exception:
                return
            if d.get("cmd") == "play" and str(d.get("id")) in SONGS and not self.a.ignore_open:
                self.set_song(str(d["id"]))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="netease-cloud-music")
    ap.add_argument("--log", default="")
    ap.add_argument("--start", default="1001")
    ap.add_argument("--art", default="")
    ap.add_argument("--ignore-open", action="store_true", help="假装 OpenUri 没效果（测试 xdg-open 回退）")
    a = ap.parse_args()
    bus = await MessageBus().connect()
    bus.export("/org/mpris/MediaPlayer2", Root(a.name))
    bus.export("/org/mpris/MediaPlayer2", Player(a))
    await bus.request_name("org.mpris.MediaPlayer2." + a.name)
    print("mock mpris ready:", a.name, flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
