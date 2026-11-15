#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backend/osmusic.py 的单元测试（全部用假数据 / mock，任何系统上都能跑，不需要网易云、不需要 Windows）。
    python tools/test_platform.py
覆盖：系统判断、orpheus 链接格式、Windows GSMTC 的会话挑选/进度外推/缺包时的降级、Linux playerctl 输出解析/挑选、
各系统的点歌启动方式、Music/Jukebox 在「不支持」时的优雅停用。
真实的 Linux MPRIS 端到端测试见 tools/test_mpris_e2e.py（需要 dbus-run-session + playerctl + dbus-fast）。
"""
import os as _os; _os.environ.setdefault("QQ_NO_FETCH", "1")      # 测试 / 截图脚本：不连抖音，Bark / 提示音硬禁用（ops/guard.py push_blocked）
import asyncio
import base64
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import osmusic  # noqa: E402
from music import Music  # noqa: E402


def run(c):
    return asyncio.new_event_loop().run_until_complete(c)


class TestBasics(unittest.TestCase):
    def test_os_name(self):
        self.assertEqual(osmusic.os_name("darwin"), "mac")
        self.assertEqual(osmusic.os_name("win32"), "win")
        self.assertEqual(osmusic.os_name("cygwin"), "win")
        self.assertEqual(osmusic.os_name("linux"), "linux")
        self.assertEqual(osmusic.os_name("freebsd14"), "other")

    def test_orpheus_url_is_the_mac_format(self):
        u = osmusic.orpheus_url(347230)
        self.assertTrue(u.startswith("orpheus://"))
        raw = base64.b64decode(u[len("orpheus://"):]).decode()
        self.assertEqual(raw, '{"type":"song","id":"347230","cmd":"play"}')     # 紧凑 JSON、id 是字符串
        self.assertEqual(json.loads(raw)["id"], "347230")

    def test_player_regex(self):
        w = osmusic.player_regex("", "win")
        self.assertTrue(w.search("cloudmusic.exe"))
        self.assertTrue(w.search("NetEase.CloudMusic_8wekyb3d8bbwe!App"))
        self.assertFalse(w.search("chrome.exe"))
        self.assertIsNone(osmusic.player_regex("any", "linux"))
        self.assertTrue(osmusic.player_regex("spotify", "linux").search("Spotify"))
        self.assertTrue(osmusic.player_regex("", "linux").search("netease-cloud-music"))
        self.assertFalse(osmusic.player_regex("", "linux").search("firefox.instance123"))


class TestGsmtc(unittest.TestCase):
    NOW = 1_800_000_000.0

    def sess(self, **k):
        d = dict(app="cloudmusic.exe", title="晴天", artist="周杰伦", album="叶惠美", pos=30.0, start=0.0, end=269.0, updated=self.NOW - 2, status=4)
        d.update(k)
        return d

    def src(self, pattern="", **kw):
        return osmusic.GsmtcSource(osmusic.player_regex(pattern, "win"))

    def test_pick_prefers_playing_netease_over_chrome(self):
        s = self.src()
        chrome = self.sess(app="chrome.exe", title="视频", status=4)
        paused = self.sess(app="cloudmusic.exe", status=5)
        self.assertIs(s.pick([chrome, paused]), paused)                   # chrome 不在白名单里
        playing = self.sess(app="NetEase.CloudMusic!App", status=4)
        self.assertIs(s.pick([paused, playing]), playing)
        self.assertIsNone(s.pick([chrome]))
        self.assertIs(self.src("any").pick([chrome, paused]), chrome)      # player=any：谁在播用谁

    def test_convert_extrapolates_position_when_playing(self):
        d = osmusic.GsmtcSource.convert(self.sess(), now=self.NOW)
        self.assertAlmostEqual(d["pos"], 32.0, places=3)                   # 30s + 2s 过去
        self.assertTrue(d["playing"])
        self.assertEqual(d["duration"], 269.0)
        d = osmusic.GsmtcSource.convert(self.sess(status=5), now=self.NOW)
        self.assertAlmostEqual(d["pos"], 30.0)                             # 暂停：不外推
        self.assertFalse(d["playing"])

    def test_convert_without_timeline_gives_none(self):
        # 网易云有的版本不上报进度：end=0 → pos=None（Music 自己用秒表推算）
        d = osmusic.GsmtcSource.convert(self.sess(pos=0.0, end=0.0, updated=None), now=self.NOW)
        self.assertIsNone(d["pos"])
        self.assertEqual(d["duration"], 0.0)

    def test_read_now_with_fake_snapshot(self):
        s = self.src()
        snap = [self.sess(app="chrome.exe", title="别的"), dict(self.sess(), _thumb=None)]
        with mock.patch.object(s, "_snapshot", new=mock.AsyncMock(return_value=snap)):
            d = run(s.read_now())
        self.assertEqual((d["title"], d["artist"], d["bundle"]), ("晴天", "周杰伦", "cloudmusic.exe"))
        with mock.patch.object(s, "_snapshot", new=mock.AsyncMock(return_value=[self.sess(app="chrome.exe")])):
            self.assertIsNone(run(s.read_now()))
        with mock.patch.object(s, "_snapshot", new=mock.AsyncMock(return_value=[])):
            self.assertIsNone(run(s.read_now()))

    def test_next_calls_try_skip_next(self):
        s = self.src()
        sk = mock.AsyncMock(return_value=True)
        snap = [dict(self.sess(), _session=mock.Mock(try_skip_next_async=sk))]
        with mock.patch.object(s, "_snapshot", new=mock.AsyncMock(return_value=snap)):
            self.assertTrue(run(s.next()))
        sk.assert_awaited_once()

    def test_make_source_win_without_winrt_degrades(self):
        import builtins
        real = builtins.__import__

        def fake(name, *a, **k):
            if name.startswith(("winrt", "winsdk")):
                raise ImportError(name)
            return real(name, *a, **k)
        with mock.patch("builtins.__import__", side_effect=fake):
            src, why = osmusic.make_source("win")
        self.assertIsNone(src)
        self.assertIn("winrt", why)
        self.assertIn("install.ps1", why)

    def test_make_source_win_with_winrt_present(self):
        fake_mods = {n: mock.MagicMock() for n in ("winrt", "winrt.windows", "winrt.windows.media", "winrt.windows.media.control")}
        with mock.patch.dict(sys.modules, fake_mods):
            src, why = osmusic.make_source("win")
        self.assertIsInstance(src, osmusic.GsmtcSource)
        self.assertEqual(why, "")


class TestMpris(unittest.TestCase):
    S = osmusic.MprisSource.SEP

    def line(self, *f):
        return self.S.join(f)

    def src(self, pattern=""):
        return osmusic.MprisSource(osmusic.player_regex(pattern, "linux"), "/usr/bin/playerctl")

    def test_parse_pick_convert(self):
        out = "\n".join([
            self.line("firefox.instance1", "Playing", "5000000", "100000000", "油管视频", "某人", "", ""),
            self.line("netease-cloud-music", "Paused", "12000000", "269000000", "晴天", "周杰伦", "叶惠美", "file:///tmp/a.png"),
        ])
        s = self.src()
        cands = s.parse(out)
        self.assertEqual(len(cands), 2)
        c = s.pick(cands)
        self.assertEqual(c["player"], "netease-cloud-music")               # 白名单：火狐不算（虽然它在播）
        d = s.convert(c)
        self.assertEqual((d["title"], d["duration"], d["pos"], d["playing"]), ("晴天", 269.0, 12.0, False))
        self.assertIs(self.src("any").pick(cands), cands[0] if cands[0]["status"] == "Playing" else cands[1])

    def test_parse_ignores_garbage_and_no_players(self):
        s = self.src()
        self.assertEqual(s.parse("No players found\n"), [])
        self.assertEqual(s.parse(""), [])
        self.assertIsNone(s.pick([]))

    def test_position_missing(self):
        s = self.src()
        c = s.parse(self.line("netease-cloud-music", "Playing", "", "", "歌", "人", "", ""))[0]
        d = s.convert(c)
        self.assertIsNone(d["pos"])
        self.assertEqual(d["duration"], 0.0)

    def test_make_source_linux(self):
        src, why = osmusic.make_source("linux", which=lambda n: "/usr/bin/playerctl")
        self.assertIsInstance(src, osmusic.MprisSource)
        src, why = osmusic.make_source("linux", which=lambda n: None)
        self.assertIsNone(src)
        self.assertIn("apt install playerctl", why)
        src, why = osmusic.make_source("other")
        self.assertIsNone(src)
        self.assertIn("暂不支持", why)


class TestControl(unittest.TestCase):
    def test_methods_per_os(self):
        which = lambda n: "/usr/bin/xdg-open" if n == "xdg-open" else None
        c = osmusic.Control("linux", None, which=which)
        self.assertEqual([n for n, _ in c.open_methods()], ["xdg-open"])
        mp = osmusic.MprisSource(None, "/usr/bin/playerctl")
        c = osmusic.Control("linux", mp, which=which)
        self.assertEqual([n for n, _ in c.open_methods()], ["MPRIS OpenUri", "xdg-open"])
        c = osmusic.Control("linux", None, which=lambda n: None)
        self.assertFalse(c.available())
        self.assertIn("xdg-open", c.reason())
        self.assertFalse(osmusic.Control("other").available())

    def test_windows_uses_startfile_with_orpheus_url(self):
        calls = []
        with mock.patch.object(os, "startfile", lambda u: calls.append(u), create=True):
            c = osmusic.Control("win")
            self.assertTrue(c.available())
            ok = run(c._win_open(osmusic.orpheus_url(123)))
        self.assertTrue(ok)
        self.assertEqual(calls, [osmusic.orpheus_url(123)])

    def test_windows_startfile_failure_is_reported_not_raised(self):
        def boom(u):
            raise OSError("no handler")
        logs = []
        with mock.patch.object(os, "startfile", boom, create=True):
            ok = run(osmusic.Control("win", log=lambda *a: logs.append(a))._win_open("orpheus://x"))
        self.assertFalse(ok)
        self.assertTrue(logs)

    def test_mac_open_command(self):
        c = osmusic.Control("mac", app_name="NeteaseMusic")
        seen = []

        async def fake_exec(*a):
            seen.append(a)
            return 0
        with mock.patch.object(c, "_exec", fake_exec):
            self.assertTrue(run(c._mac_open("orpheus://abc")))
        self.assertEqual(seen, [("/usr/bin/open", "-a", "NeteaseMusic", "orpheus://abc")])      # 和改动前 Mac 上的命令完全一样


class TestFindRoom(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import find_room
        self.fr = find_room

    def test_windows_log_layout(self):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / "webcast_mate" / "logs"
            logs.mkdir(parents=True)
            (logs / "client-2026-11-14.log").write_text('xx "room_id":"7708002792107215666" yy\n')
            (Path(td) / "webcast_mate" / "watchdog").mkdir()
            (Path(td) / "webcast_mate" / "watchdog" / "x.log").write_text('"roomId":"1111111111111111111"')
            with mock.patch.dict(os.environ, {"APPDATA": td, "LOCALAPPDATA": td + "/none"}):
                self.assertEqual(self.fr.room_id_from_webcast_mate("Windows"), "7708002792107215666")

    def test_windows_without_logs_gives_hint(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, {"APPDATA": td, "LOCALAPPDATA": td}):
            with self.assertRaises(SystemExit) as cm:
                self.fr.room_id_from_webcast_mate("Windows")
        self.assertIn("WEBCAST_MATE_LOG_DIR", str(cm.exception))

    def test_linux_says_unsupported_and_suggests_obs(self):
        with self.assertRaises(SystemExit) as cm:
            self.fr.room_id_from_webcast_mate("Linux")
        self.assertIn("OBS", str(cm.exception))

    def test_mac_path_unchanged(self):
        g = self.fr.webcast_log_globs("Darwin", {}, "/Users/u")
        self.assertEqual(g, ["/Users/u/Library/Logs/Douyin Webcast Mate/*.log"])


class TestMprisArt(unittest.TestCase):
    def test_file_url_cover(self):
        s = osmusic.MprisSource(None, "playerctl")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\nrest")
        try:
            data, mime = run(s._fetch_art("file://" + f.name))
        finally:
            os.unlink(f.name)
        self.assertEqual(mime, "image/png")
        self.assertIsNone(run(s._fetch_art("")))
        self.assertIsNone(run(s._fetch_art("file:///nonexistent/x.png")))


class TestGracefulDisable(unittest.TestCase):
    def test_music_unsupported_logs_clear_line_and_stays_off(self):
        logs = []
        with tempfile.TemporaryDirectory() as td, mock.patch.object(osmusic, "os_name", lambda p=None: "other"):
            m = Music(td, lambda e: None, log=lambda *a: logs.append(" ".join(map(str, a))))
            m.start()
        self.assertIsNone(m.method)
        self.assertTrue(any("暂不支持" in l and "已停用" in l for l in logs), logs)

    def test_music_windows_without_winrt(self):
        logs = []
        with tempfile.TemporaryDirectory() as td, mock.patch.object(osmusic, "os_name", lambda p=None: "win"), \
                mock.patch.object(osmusic, "make_source", lambda *a, **k: (None, "没装 WinRT 包")):
            m = Music(td, lambda e: None, log=lambda *a: logs.append(" ".join(map(str, a))))
            m.start()
        self.assertTrue(any("Windows" in l and "没装 WinRT" in l for l in logs), logs)

    def test_jukebox_disables_itself_when_music_unavailable(self):
        from host.config import Config
        from jukebox import Jukebox
        logs = []

        async def go():
            with tempfile.TemporaryDirectory() as td, mock.patch.object(osmusic, "os_name", lambda p=None: "other"):
                m = Music(td, lambda e: None, log=lambda *a: None)
                jb = Jukebox(Config(ROOT / "config.ini"), m, lambda *a: logs.append(" ".join(map(str, a))), lambda *a, **k: None,
                             lambda *a, **k: None, lambda *a: None)
                jb.enabled = True
                jb.start()
                return jb
        jb = run(go())
        self.assertFalse(jb.enabled)
        self.assertTrue(any("已停用" in l for l in logs), logs)
        self.assertFalse(jb.on_chat({"text": "点歌 晴天"}))                     # 停用后点歌弹幕当普通聊天


if __name__ == "__main__":
    unittest.main(verbosity=2)
