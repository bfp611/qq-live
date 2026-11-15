# -*- coding: utf-8 -*-
"""读取 config.ini（stdlib configparser，带注释），环境变量可覆盖。"""
import configparser
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULTS = {
    "host": {"enabled": "true", "name": "猪猪侠", "filter_reply_adlaw": "false", "persona": "persona.md", "blocklist": "blocklist.txt",
             "label": "AI虚拟主播"},
    "ai": {"base_url": "", "api_key": "", "model": "", "temperature": "0.9", "max_tokens": "200", "timeout": "20"},
    "behavior": {"chat_interval": "8", "welcome_interval": "25", "idle_interval": "45", "max_chars": "50",
                 "batch_size": "8", "reply_chat": "true", "welcome_enters": "true", "thanks_gifts": "true",
                 "thanks_follows": "true", "proactive": "true", "llm_for_events": "false",
                 "history_turns": "6", "stale_seconds": "25"},
    "music": {"enabled": "true", "bundle": "com.netease.163music", "player": "", "interval": "1.0", "lyric_offset": "0",
              "jukebox": "true", "app_name": "NeteaseMusic", "max_queue": "10", "user_cooldown": "30", "max_per_user": "2",
              "allow_vip": "true", "first_immediate": "true", "near_end": "1.3", "verify_timeout": "12", "ack": "true"},
    "agent": {"enabled": "true", "who": "everyone", "anchor_names": "", "allow_users": "", "deny_users": "",
              "rules": "true", "llm": "true", "llm_mode": "json", "llm_gate": "keywords", "llm_timeout": "12", "llm_max_tokens": "400",
              "llm_thinking": "auto", "allow_actions": "*", "deny_actions": "shutdown,logoff,empty_trash,delete_icon",
              "max_actions": "4", "max_text": "40", "user_cooldown": "3", "user_per_min": "8", "global_cooldown": "1", "global_per_min": "40",
              "dedupe_seconds": "8", "queue_max": "6", "reply": "true", "say_unknown": "true", "qq_send_prefix": "{name}说：",
              "cursor_speed": "900", "click_delay": "0.18", "typing_cps": "9", "step_pause": "0.25", "show_who": "true",
              "cursor_idle_hide": "6", "protect": "qqchat", "restore_secs": "20", "undo": "true", "song_visual": "true", "test_endpoints": "true"},
    "idle": {"enabled": "true", "idle_after": "45", "startup_delay": "30", "min_interval": "60", "max_interval": "180", "max_per_hour": "20",
             "weights": "browse_ie:3,play_minesweeper:3,comment_song:3,notepad_write:2,qq_chat:2,game_menu:1,arrange_icons:1,change_wallpaper:1,calc:1",
             "allow_activities": "*", "deny_activities": "", "repeat_gap": "300", "max_duration": "75",
             "speak": "true", "llm": "true", "llm_timeout": "8", "line_chars": "28", "stop_on_chat": "true", "gifts_reset_quiet": "true",
             "wait_host_quiet": "true", "wait_jukebox": "true", "wait_agent": "true",
             "avoid_cover": "true", "cleanup": "true", "allow_music_control": "false", "cursor_speed": "0.75", "who_label": "",
             "sites": "www.hao123.com,www.baidu.com,www.sina.com.cn,www.163.com,www.sohu.com,www.4399.com,www.taobao.com,www.youku.com",
             "weights_new": "play_solitaire:2,play_freecell:2,paint_draw:2,tweak_sound:1,qq_pet_care:2,qq_zone_visit:2,qq_show_change:1,qq_files_download:1,qq_shake:0.5,play_vote:1.5,play_rank:1,ai_game:1,ai_screen:1", "mine_steps": "10", "cards_steps": "14", "friend": "", "test_endpoints": "true"},
    "perform": {"enabled": "true", "weights": "", "gap": "240", "heavy_gap": "600", "tip": "true", "builtin": "true", "items": ""},
    "autoclose": {"enabled": "true", "default_secs": "40", "check_secs": "2", "anim": "true",
                  "paint": "25", "notepad": "35", "calc": "30", "cmd": "35", "control": "40", "explorer": "40", "ie": "40", "qq": "40", "dialog": "30", "media": "40",
                  "minesweeper": "45", "solitaire": "45", "freecell": "45", "videogame": "45", "max_game": "150", "max_media": "180", "max_any": "0",
                  "keep": "qqchat,ttplayer,ttplaylist,lyrics,qq-panel,qqx-pet,report,shutdown,logoff,shutter,xpscr", "skip": "vote,skipvote,game"},
    "xp": {"enabled": "true",
           "boot": "true", "boot_secs": "4.5", "welcome": "true", "welcome_secs": "3.5", "boot_cooldown": "900", "boot_edition": "pro", "user": "",
           "shutdown_screens": "true", "shutdown_restart": "true", "restart_after": "5",
           "sounds": "true", "volume": "0.5", "mute": "false", "sound_events": "*", "sound_deny": "",
           "bsod": "true", "bsod_per_hour": "0.3", "bsod_secs": "6", "setup_secs": "12",
           "balloons": "true", "balloon_events": "hardware,qq,music,tip", "balloon_secs": "7", "balloon_hardware_every": "1500",
           "qq_sounds": "true", "qq_online_every": "300", "qq_flash": "true", "qq_system_sound": "true",
           "apps": "true"},
    "qq": {"enabled": "true",
           "commands": "true", "shake": "true", "shake_secs": "1.2", "shake_cooldown": "6", "shake_sound": "true",
           "show": "true", "outfit": "default", "outfit_revert": "90", "show_scene": "true",
           "pet": "true", "pet_name": "球球", "pet_wander": "true", "pet_decay": "1.0", "pet_bubbles": "true", "pet_x": "", "pet_panel_open": "false",
           "zone": "true", "zone_owner": "", "zone_msgs": "keyword", "zone_msg_keywords": "留言,空间留言,踩踩,沙发,顶", "zone_msg_sample": "10", "zone_visitors": "30", "zone_music": "true", "zone_blog": "true",
           "files": "true", "files_names": "",
           "gift_map": "玫瑰花=pet:feed,小心心=pet:play,啤酒=shake,加油鸭=outfit:next,飞吻=pet:bath,嘉年华=outfit:party",
           "gift_value_map": "1=pet:play,10=pet:feed,52=outfit:next,99=shake,199=outfit:random,520=outfit:party",
           "gift_default": "pet:play", "gift_effects": "true", "gift_cooldown": "2"},
    "play": {"enabled": "true", "commands": "true", "ai_say": "true",
             "points": "true", "chat_points": "1", "chat_min_len": "2", "chat_gap": "3", "dup_secs": "30", "max_per_min": "6", "daily_cap": "300",
             "like_points": "1", "like_per": "10", "follow_points": "20", "gift_points": "5", "gift_value_pts": "0.5", "gift_max_pts": "5000", "enter_points": "0",
             "level_base": "10", "levelup_msg": "true", "points_cmd": "true", "badges": "true", "data_file": "data/play.json", "keep_days": "60",
             "vote": "true", "vote_who": "anchor", "vote_starters": "", "vote_secs": "60", "vote_min_votes": "1", "vote_tie": "random", "vote_nobody": "skip",
             "vote_change": "true", "vote_max_options": "6", "vote_points": "2", "vote_execute": "true", "vote_window": "true", "vote_close_secs": "12",
             "vote_idle": "false", "vote_idle_options": "玩红警,换壁纸,玩扫雷,画个太阳,下一首", "vote_idle_secs": "45", "vote_idle_min_viewers": "2",
             "skip_vote": "true", "skip_words": "切歌,下一首,换歌,换一首,跳过,skip,不好听", "skip_mode": "count", "skip_count": "3", "skip_percent": "30", "skip_min": "2",
             "skip_window": "90", "skip_active_secs": "300", "skip_cooldown": "20", "skip_anchor_instant": "true", "skip_panel": "true",
             "fx": "true", "fx_secs": "6", "fx_emoji": "🎉,✨,💗,🌹,🎁", "fx_virus_secs": "8", "fx_cooldown": "8", "fx_bsod_cooldown": "120",
             "gift_map": "烟花=fireworks,流星雨=meteor,熊猫=virus:panda,蓝屏=bsod,玫瑰花=pet:feed+emoji:🌹,小心心=pet:play+emoji:💗",
             "gift_value_map": "88=emoji:🎉,199=outfit:random+emoji:✨,520=outfit:party+fireworks,1000=meteor,2000=fireworks+shake,3000=bsod"},
    "tips": {"enabled": "true", "idle_secs": "40", "interval": "150", "min_gap": "90", "startup_delay": "60",
             "demo": "true", "demo_chance": "0.35", "menu": "true", "menu_interval": "480", "menu_size": "6", "menu_items": "",
             "use_tts": "true", "builtin": "true", "custom": "", "prefix": "💡 玩法提示：", "state_file": "data/tips_state.json"},
    "welcome": {"enabled": "true", "merge_secs": "10", "user_gap": "1800", "max_names": "2", "max_per_min": "6", "pending_max": "12",
                "speak": "quiet", "quiet_secs": "60", "recommend": "true", "cmds": "song,bsod,fw,meteor,virus,shake,pet,wall,mine,paint,rank,sol,idiom,songgame,riddle",
                "tpl_new": "", "tpl_back": "", "tpl_friend": "", "tpl_group": "", "tail": ""},
    "giftfx": {"enabled": "true", "t1": "true", "t2": "true", "t3": "true", "tier1": "1", "tier2": "10", "tier3": "100", "merge_secs": "3", "ask_secs": "30",
               "queue_max": "4", "gap_secs": "3", "big_scene": "random", "likes": "true", "like_step": "300", "follow": "true", "speak": "true"},
    "clips": {"enabled": "true", "mode": "live", "ffmpeg": "auto", "fps": "20", "max_width": "1280", "bitrate": "3500", "encoder": "auto", "audio": "BlackHole 2ch",
              "window_owner": "Google Chrome", "window_title": "直播间", "region": "", "inset": "0,0,0,0", "seg_secs": "2", "keep_secs": "45", "pre": "10", "post": "15", "min_gap": "20",
              "events": "perf_bsod,perf_restart,perf_virus,perf_fireworks,perf_meteor,gift_big,viewer", "viewer_cmd": "true", "viewer_kw": "高光|切片|剪辑|clip", "viewer_gap": "120", "reply": "true",
              "max_clips": "80", "out_dir": "data/clips", "vertical": "true", "out_w": "1080", "out_h": "1920", "out_bitrate": "5000", "bark": "false", "bark_text": "切到一个高光",
              "relocate_secs": "30", "retry_secs": "20", "test_source": ""},
    "story": {"enabled": "true", "start_date": "2005-09-01", "advance": "true", "clock": "true", "zone": "true",
              "diary": "true", "diary_min_secs": "600", "diary_min_events": "5", "end_wait": "180", "llm": "true", "diary_chars": "220", "max_diaries": "30",
              "read_aloud": "true", "read_weight": "2.0", "read_gap": "1500",
              "memory": "true", "quotes_max": "3", "quote_min": "5", "quote_max": "20", "quote_sample": "0.08", "recall": "true", "recall_p": "0.5", "reply_memory": "true",
              "file": "data/story.json"},
    "guard": {"enabled": "true", "bark": "true", "bark_key_file": "data/bark_key.txt", "bark_server": "https://api.day.app", "bark_group": "qq-live",
              "bark_title": "GG-Bond 直播", "bark_level": "critical", "bark_timeout": "8",
              "sound": "true", "sound_file": "/System/Library/Sounds/Sosumi.aiff", "sound_repeat": "4", "sound_device": "auto",
              "log_watch": "true", "log_dir": "auto", "log_poll": "1", "catchup_secs": "1800", "extra_patterns": "",
              "window_watch": "auto", "interval": "10", "window_owners": "抖音直播伴侣,Douyin Webcast Mate,直播伴侣",
              "cooldown": "60", "remind_at": "50,90", "drop_alert": "true", "drop_grace": "15", "drop_quiet": "60", "state_file": "data/guard_state.json"},
    "ops": {"enabled": "true", "default_room": "", "detect_room": "true", "window": "true", "health": "true",
            "watch": "true", "live_gate": "true", "live_poll_secs": "30", "live_recheck_secs": "30", "live_recheck_need": "3", "live_recheck_span": "90", "live_recheck_quiet": "90", "autoswitch": "true", "keep_room": "true",
            "backoff_min": "3", "backoff_max": "60", "stale_secs": "60", "sup_delay": "3", "sup_max_crashes": "8",
            "log": "true", "log_dir": "data/logs", "log_max_mb": "10", "log_files": "5", "log_keep_days": "30", "log_members": "false", "log_text_chars": "200", "session_gap": "1800", "end_grace": "60",
            "report": "true", "report_dir": "data/reports", "report_on_end": "true", "report_llm": "true", "report_min_secs": "60", "diamond_rmb": "0.1", "report_top": "5",
            "panel": "true", "panel_lan": "true", "panel_token": "", "panel_token_file": "data/ops_token.txt", "panel_recent": "60", "panel_say_max": "60", "panel_fail_lock": "60",
            "qr": "true", "overrides_file": "data/ops_overrides.json"},
    "ai_plus": {"enabled": "true",
                "memory": "true", "memory_file": "data/memory.json", "memory_max_viewers": "2000", "memory_keep_days": "90", "memory_topics": "5", "memory_topic_chars": "30",
                "memory_songs": "5", "memory_session_gap": "1800", "memory_greet": "true", "memory_greet_min_visits": "2", "memory_greet_gap": "20", "memory_greet_llm": "true",
                "memory_in_replies": "true", "memory_cmd": "true",
                "screen": "true", "screen_interval": "150", "screen_min_gap": "60", "screen_quiet_secs": "20", "screen_events": "true", "screen_chars": "40",
                "screen_vision": "auto", "screen_vision_model": "", "screen_vision_timeout": "25", "screen_cmd": "true",
                "game": "true", "game_who": "anyone", "game_timeout": "45", "game_points": "5", "game_win_points": "10", "game_cooldown": "30", "game_window": "true",
                "game_close_secs": "10", "game_say": "true", "game_idle": "false", "game_idle_min_viewers": "2", "game_idle_list": "idiom,riddle,song",
                "idiom_rounds": "8", "idiom_homophone": "true", "idiom_host_plays": "true", "idiom_file": "",
                "song_game_source": "both", "song_game_rounds": "3", "song_game_file": "", "riddle_rounds": "3", "riddle_file": "",
                "voices": "narrator=edge:zh-CN-YunjianNeural,quiz=edge:zh-CN-XiaoxiaoNeural", "voice_ctx": "vote:narrator,skip:narrator,game:quiz,screen:host,songc:host",
                "voice_names": "narrator=旁白,quiz=出题官",
                "song_comment": "true", "song_comment_chance": "0.5", "song_comment_gap": "240", "song_comment_delay": "6", "song_comment_wait": "30",
                "song_comment_chars": "40", "song_comment_llm": "true", "song_comment_requests": "false", "song_comment_min_secs": "60"},
    "tts": {"backend": "edge", "voice": "zh-CN-YunxiNeural", "rate": "+6%", "pitch": "+0Hz", "volume": "+0%",
            "openai_base_url": "", "openai_api_key": "", "openai_model": "tts-1", "openai_voice": "alloy",
            "volc_appid": "", "volc_token": "", "volc_cluster": "volcano_tts", "volc_voice": "zh_female_vv_uranus_bigtts",
            "sovits_url": "http://127.0.0.1:9880/tts", "sovits_ref_audio": "", "sovits_prompt_text": "",
            "custom_url": "", "custom_body": '{"text": "{text}"}',
            "fallback": "edge",
            "fish_url": "https://api.fish.audio/v1/tts",
            "fish_model": "s2.1-pro-free",
            "fish_reference_id": "074b3a7300f64cd28e398470c51f05fb",
            "fish_latency": "balanced",
            "fish_timeout": "20"},
}

ENV = {  # 环境变量 -> (section, key)
    "AI_BASE_URL": ("ai", "base_url"), "AI_API_KEY": ("ai", "api_key"), "AI_MODEL": ("ai", "model"),
    "TTS_BACKEND": ("tts", "backend"), "TTS_VOICE": ("tts", "voice"),
    "OPENAI_TTS_API_KEY": ("tts", "openai_api_key"), "VOLC_TTS_TOKEN": ("tts", "volc_token"),
}


class Config:
    def __init__(self, path=None):
        self.path = Path(path) if path else ROOT / "config.ini"
        cp = configparser.ConfigParser(interpolation=None)
        cp.read_dict(DEFAULTS)
        if self.path.exists():
            cp.read(self.path, encoding="utf-8")
        for env, (sec, key) in ENV.items():
            if os.environ.get(env):
                cp[sec][key] = os.environ[env]
        self.cp = cp

    def s(self, sec, key):
        return self.cp[sec][key].strip()

    def f(self, sec, key):
        try:
            return float(self.cp[sec][key])
        except ValueError:
            return float(DEFAULTS[sec][key])

    def i(self, sec, key):
        return int(self.f(sec, key))

    def b(self, sec, key):
        return self.cp[sec][key].strip().lower() in ("1", "true", "yes", "on")

    def file_text(self, name):
        p = Path(name)
        if not p.is_absolute():
            p = ROOT / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    @property
    def ai_enabled(self):
        """有 base_url 和 model 就认为配好了（本地 Ollama 不需要 key）。"""
        return bool(self.s("ai", "base_url") and self.s("ai", "model"))
