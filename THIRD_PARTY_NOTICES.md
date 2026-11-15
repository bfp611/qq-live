# 第三方代码与素材声明

## 1. mengkunsoft/QQ2006 —— 界面素材与样式
- 来源：https://github.com/mengkunsoft/QQ2006 （作者主页 https://mkblog.cn/ ）
- 本项目 `web/img/`（im、avatar、Background*.png、bg.jpeg、qq.png）、`web/sound/`、以及 `web/qq2006.css`
  （摘自其 index.html 的样式）均来自该项目。
- 该项目 README 的条款：**「仅供学习交流，请勿用于商业用途」「尊重版权，所有素材均来自原版 QQ2006 安装包，版权归腾讯公司所有」
  「可以自由地分享和修改代码，但请保留出处」**。仓库没有单独的 LICENSE 文件。
- 因此：保留出处（本文件 + 页面里 CSS 注释），不要用于商业目的；素材本身的版权属于腾讯。
- `web/img/bg.jpeg` 是 Windows XP 经典壁纸（版权属微软），仅在 `?bg=xp` 时使用，不用可删除。

## 2. saermart/DouyinLiveWebFetcher —— 抖音弹幕协议与签名
- 来源：https://github.com/saermart/DouyinLiveWebFetcher ，许可证：**AGPL-3.0**（见 `backend/dy/LICENSE-AGPL-3.0`）
- `backend/dy/sign.js`、`a_bogus.js`、`ac_signature.py`、`protobuf/` 为上游原文件；
  `backend/dy/fetcher.py` 为基于上游 `liveMan.py` 的改写。
- 上游声明：代码仅用于学习研究交流，严禁商业谋利、破坏系统、盗取个人信息。
- AGPL-3.0 提示：自己本机使用没有任何义务；如果把这套东西改完后**对外提供网络服务或分发**，需要按 AGPL 公开对应源码。

## 3. 猪猪侠（GG-Bond）形象素材 —— 用户自备
- `web/gg/` 下的 18 张动作图（p00~p17.webp）、头像（head8/head16.png）、背景（bg.webp）由使用者提供的素材处理而来
  （抠绿幕、统一尺寸、转 WebP；脚本见 `tools/ggbond/`）。
- 「猪猪侠 / GG-Bond」是动画片《猪猪侠》的角色，**版权/商标属于其权利人（广东咏声动漫等）**。本项目未获得任何授权，
  这些素材**仅用于使用者自己的非商业娱乐**；如有带货、打赏变现、商单等商业用途，请自行取得授权或更换为原创形象。分享本压缩包前请考虑这一点。
- `persona.md`（猪猪侠人设）与 `blocklist.txt`（屏蔽词清单）为使用者在对话中拿到的文本，原样放入。

## 3.1 AI 主播实现 / 参考（仅参考，未复制代码或素材）
- 调研参考：Ikaros-521/AI-Vtuber（GPL-3.0）、zbsdsb/dafeiyu-ai-vtuber（GPL-3.0）、Open-LLM-VTuber/Open-LLM-VTuber（GitHub 未识别为标准协议）、
  guansss/pixi-live2d-display（MIT，依赖闭源的 Live2D Cubism Core）、xkk6663/dsh-live2d-mao（仓库 MIT，模型作者要求非商业使用、禁止盗用与出售）。
- 本项目中的 AI 主播代码（`backend/host/`）与动作/动效代码（`web/app.js`、`web/app.css`）为原创，没有复制上述项目的代码、模型或配音。
- 运行依赖 edge-tts（LGPL-3.0）：调用微软 Edge 在线朗读，非官方接口。

## 4. 其它
- 跨平台「正在播放」：Windows 用 pywinrt 的 `winrt-*` 包（MIT，PyPI，安装时下载，不随项目分发）读 GSMTC；Linux 调用外部命令 `playerctl`（LGPL-3.0，用户自己 `apt install`，不随项目分发）读 MPRIS。
- 点歌用的 `orpheus://` 链接格式（`{"type":"song","id":"…","cmd":"play"}` 的 base64）参考了开源项目 Seraph310/cloudmusic-desktop-mcp 的公开说明，未复制其代码。
- Windows 版直播伴侣日志位置（`find_room.py`）参考 heplex/douyin-rtmp 等公开资料，**未在真机验证**。
- 页面里的 Douyin 表情 `[捂脸]` 等会被换成系统 Emoji，不含任何第三方表情素材。
- Python 依赖（aiohttp、requests、websocket-client、betterproto、mini_racer）各自遵循其开源许可证。

## 5. 桌面模式（`?desk=xp`）素材
Windows XP 桌面素材（Bliss 壁纸、开始按钮、XP 图标）和各软件/游戏图标的出处见 `CREDITS.md`。均为微软/第三方版权素材，仅个人怀旧用途。

## 6. 桌面软件窗口（第二批）新增的第三方内容
- **ShizukuIchi/winXP（MIT）**：Luna 窗口/开始菜单/资源管理器样式的移植、`xp/ico/*` 小图标、扫雷素材。MIT 要求保留版权声明：
  “Copyright (c) ShizukuIchi — Permission is hereby granted, free of charge … to deal in the Software without restriction …”（完整条款见 https://github.com/ShizukuIchi/winXP/blob/master/LICENSE ）。
  图标/位图本身是微软素材，仅个人怀旧用途。
- **XP 壁纸**（`web/xp/wall/`）：来自 Internet Archive `windows-xp_20220726`、`winter_20240420`，微软版权，仅个人使用。
- **QQ2006 主面板与登录窗口**：同 §1（mengkunsoft/QQ2006，非商用，腾讯版权）；`web/apps-qq-tpl.js` 是由其 `index.html` 机械切片生成的。
- **游戏视频片段**（`web/xp/video/`，各约 1 MB，经 ffmpeg 通过 HTTP Range 直接从 archive.org 截取并重新编码为 640px 宽 H.264/AAC）。
  **所有画面的版权属于上传者以及游戏权利人**；这里只是个人怀旧展示用的几十秒片段，**不得商用、不得再分发**。要删除直接删对应 mp4/jpg（游戏窗口会退回只有菜单）。
  | 文件 | archive.org 条目 | 备注 |
  |---|---|---|
  | `cs.mp4` | `eswc-2007-pgs-vs-noa-counter-strike-1.6-grand-final`（文件 “videoplayback (1).mp4”，从 1800 秒起 28 秒） | ESWC 2007 CS 1.6 决赛录像，Valve/赛事方/上传者版权 |
  | `vc.mp4` | `grand-theft-auto-vice-city-play-station-2-pal-gameplay-www.chilloutgames.co.uk`（从 60 秒起） | 条目标注 Public Domain Mark（游戏本身仍是 Rockstar/Take-Two 版权） |
  | `war3.mp4` | `g4tv.com-video15022`（G4TV《魔兽争霸III：冰封王座》PC 预览，从 128 秒起 30 秒） | G4/暴雪版权 |
  | `ra2.mp4` | `youtube-KXjStlcZQwc`（红色警戒2 尤里的复仇 Memorial City 7 vs 1 对战，从 400 秒起） | EA/上传者版权 |
- **热血传奇截图**（`web/xp/game/mir2.png`）：维基百科合理使用截图，低分辨率；版权属盛大/Wemade。
- **自制部分**：劲舞团节奏游戏、暴风影音/酷狗/迅雷/QQ游戏大厅窗口、IE 里的网页、记事本/计算器/cmd/任务管理器/显示属性等对话框逻辑均为本项目原创代码（外观参考 XP，仅用到上面列出的素材）。

## 7. XP 加强包（item 3）新增的第三方内容
- **DualBrain/Solitaire（MIT）**：`web/xp/cards/` 的纸牌牌面 / 牌背 / 空槽位图。MIT 要求保留版权声明与许可文本（完整条款见 https://github.com/DualBrain/Solitaire/blob/master/LICENSE ）。牌面图案本身源自微软 Windows 纸牌，仅个人怀旧用途。
- **1j01/jspaint（MIT）**：`web/xp/paint/tools.png`（画图工具图标），许可证原文随附 `web/xp/paint/LICENSE-jspaint.txt`。`web/apps-paint.js` 的画图逻辑是本项目自己写的，没有复制 jspaint 的代码。
- **Windows XP 系统音效**（`web/xp/snd/*.wav`）：微软版权，来自 https://i.changeling.me/WinXPSounds/ ，仅个人使用。
- **QQ 提示音**（`web/sound/Global.mp3` `InputAlert.mp3`）：同 §1（mengkunsoft/QQ2006，非商用，腾讯版权）。
- **XP 开机图**（`web/xp/boot/`）：Wikimedia Commons 上的 Windows XP 开机画面，微软版权（合理使用）。
- **空当接龙发牌算法**：微软公开的 32000 局线性同余发牌算法，仅是算法，没有代码来源。

## 8. QQ 生态（item 4）新增的第三方内容
- **chenboos5/QQpet-codex**：`web/xp/qqpet/penguin.png`，QQ宠物（企鹅）动画帧 sprite sheet（来自 https://github.com/chenboos5/QQpet-codex 的 `assets/QQpet-codex/spritesheet.png`）。该仓库未标明许可证；**美术版权属于腾讯**，这里只用于个人怀旧展示，不要商用 / 再分发；不想用就删掉这个文件。
- **QQ秀 / QQ空间 / 群共享**：配饰、场景、窗口和文件列表都是本项目自绘 / 自制的仿制品（风格化，不是腾讯原版美术，也没有抓取任何真实页面）。“QQ”“QQ秀”“QQ空间”“QQ宠物”是腾讯的商标，这里只是怀旧致敬。
- **观众互动（`[play]`）**：QQ 等级图标（星 / 月 / 日 / 冠）、熊猫烧香「中毒」图标、烟花 / 流星雨 / 表情雨特效、投票窗和排行榜窗都是本项目自绘 / 自制的仿制品（不是腾讯原版等级图标，也不包含任何真实恶意程序或其素材；「中毒」只是换桌面图标显示、几秒后自动恢复）。没有新增第三方代码或依赖。

## 9. AI 加强包（item 6）新增的第三方内容
- **pwxcoo/chinese-xinhua**（<https://github.com/pwxcoo/chinese-xinhua>，MIT License，Copyright (c) 2018 PWXCOO）：`backend/ai6/data/idioms.tsv` 由其 `data/idiom.json` 提取（只保留「词」「拼音」两列，且仅 4 字 / 4 音节的条目，共 29 497 条），用来校验成语接龙。许可全文：`backend/ai6/data/IDIOM_LICENSE.txt`。
- 猜歌名题库 `songs.tsv`、脑筋急转弯题库 `riddles.tsv`：本项目原创整理（猜歌名只写非歌词的描述）。
- 观众记忆、画面点评、小游戏窗口、多音色：自写代码；没有引入新的第三方依赖（视觉模型走你自己配置的 `[ai]` 接口）。

