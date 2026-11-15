# 素材来源（桌面模式 `?desk=xp`）

这些都是**真实/原版**素材，不是自己画的；版权属于各自权利人（微软、腾讯、Valve/Rockstar、暴雪、EA、九城/久游、迅雷、酷狗、暴风等），
仅供个人怀旧直播/学习使用，**不要商用、不要二次售卖**。需要删掉哪个，直接删 `web/xp/` 里对应文件即可（页面会显示空图标）。

| 内容 | 文件 | 来源 | 许可 / 备注 |
|---|---|---|---|
| Bliss 壁纸（1920×1080） | `web/xp/ui/bliss.jpg` | 开源项目 ShizukuIchi/winXP 引用的原版 Bliss 图（https://i.imgur.com/Zk6TR5k.jpg） | 微软版权（摄影 Charles O'Rear） |
| 开始按钮（原图） | `web/xp/ui/start.png` | github.com/ShizukuIchi/winXP `src/assets/windowsIcons/start.png` | 项目 MIT；图为微软素材 |
| 任务栏 / 托盘渐变、任务栏按钮配色 | `web/desk.css` | 取自 ShizukuIchi/winXP 的 `Footer/index.js`（对原版 Luna 的 CSS 还原） | MIT |
| 托盘小图标（音量/USB/安全） | `web/xp/ui/690.png 394.png 229.png` | ShizukuIchi/winXP 的 `windowsIcons/690(16x16) 394(16x16) 229(16x16)` | 微软素材 |
| 我的电脑 / 我的文档 / 回收站 / Internet Explorer | `web/xp/icons/{mycomputer,mydocs,recycle,ie}.png` | github.com/softwarehistorysociety/XPIcons（`XP/` 目录，Windows XP 原版高清图标） | 仓库 Unlicense；图标为微软版权 |
| 千千静听 | `icons/ttplayer.png` | 中文维基百科 `File:TTPlayer icon.png`（48×48） | 合理使用（logo） |
| Counter-Strike 1.6 | `icons/cs.png` | Steam 官方应用图标 `clienticon`（app 10，游戏 exe 自带图标，32×32） | Valve 版权 |
| 侠盗猎车手 罪恶都市 | `icons/vc.png` | Steam 官方应用图标 `clienticon`（app 12110，32×32） | Rockstar/Take-Two 版权 |
| 红色警戒2 | `icons/ra2.png` | Steam 官方应用图标 `clienticon`（app 2229850 红警2 + 尤里的复仇，256×256 缩小） | EA 版权 |
| 魔兽争霸III | `icons/war3.png` | Wowpedia `War3 Icon.png`（从游戏 exe 提取，48×48） | 暴雪版权 |
| 热血传奇 | `icons/mir2.png` | 开源仓库 ufaith/mir2ei `client/Mir2Ex.ICO`（传奇2 客户端原图标 32×32，16 色） | 盛大/Wemade 版权 |
| 劲舞团 | `icons/audition.png` | 官方站 au.9you.com 的 `favicon.ico`（文件日期 2007-07-26，32×32，洋红色底已抠成透明） | 久游版权 |
| 暴风影音 | `icons/baofeng.png` | Internet Archive 存档的 baofeng.com `favicon.ico`（64×64） | 暴风版权 |
| 酷狗音乐 | `icons/kugou.png` | Wikimedia Commons `KuGou app icon.png`（300×300） | 公共领域标注 |
| 迅雷 | `icons/xunlei.png` | Wikimedia Commons `Thunder (Xunlei) logo.svg` 渲染 | 标注 GPLv3；logo 版权属迅雷 |
| 腾讯QQ（企鹅） | `icons/qq.png` | 中文维基百科 `File:Tencent QQ.svg` 渲染 | 合理使用（logo），腾讯版权 |
| QQ游戏 | `icons/qqgame.png` | 英文维基百科 `File:QQ Games (logo).png` | 合理使用（logo） |
| QQ 聊天窗口皮肤 | `web/img/*` | mengkunsoft/QQ2006（见 `THIRD_PARTY_NOTICES.md`） | 非商用，腾讯版权 |
| 千千静听 播放器窗口（含按钮、LED 数字、滑块） | `web/xp/tt/*.png` | 千千静听官方自带「经典皮肤」`~Classic.skn`（作者 nanling，http://ttplayer.com，皮肤 BMP 原图，洋红色透明色转成透明 PNG；取自存档仓库 github.com/szc126/ttplayer-skins-my-archive，转换脚本 `tools/make_tt_assets.py`）。频谱配色取自该皮肤 `Visual.xml` | 千千静听/百度版权 |
| 千千静听「播放列表」窗口 | `web/xp/tt/playlist_*.png` | 同一款「经典皮肤」的 playlist_skin/playlist_toolbar/playlist_title（纵向平铺拉高，`tools/make_tt_assets.py`） | 千千静听/百度版权 |
| 网易云「正在播放」读取 | `tools/mr/mediaremote-adapter/`（构建产物不入库） | 开源 ungive/mediaremote-adapter（BSD-3-Clause），借 /usr/bin/perl 读 macOS MediaRemote；`brew install nowplaying-cli` 作为备用 | — |
| Windows / Linux「正在播放」读取 | `backend/osmusic.py` | Windows：pywinrt（`winrt-runtime`、`winrt-Windows.Media.Control` 等，MIT）调用系统 GSMTC；Linux：外部命令 `playerctl`（LGPL-3.0）读 MPRIS。均为运行时依赖，不随项目分发 | — |

## 没能找到「当年原版」的
- **迅雷、酷狗、暴风影音、腾讯QQ、QQ游戏**：找不到 2007 年桌面图标的单独文件，用的是官方/维基上能下载到的 logo（迅雷是新版小鸟，酷狗是新版 K，QQ 是维基的企鹅 logo，QQ游戏是 logo 不是桌面图标）。想换成当年的，把 `web/xp/icons/` 里同名 PNG（96×96 透明）覆盖即可（可以从旧版安装包里用 Resource Hacker / IconsExtract 提取）。
- Counter-Strike / 罪恶都市 / 传奇 / 魔兽 / 劲舞团 的图标都是 32–48 像素的原版小图，已按整数倍放大再缩放，所以略带像素感，这是原版分辨率。

---

# 桌面「软件」窗口新增素材（`?desk=xp` 第二批）

| 内容 | 文件 | 来源 | 许可 / 备注 |
|---|---|---|---|
| Luna 窗口外观、开始菜单、资源管理器版式、对话框控件 CSS | `web/wm.css` `web/desk.css` `web/apps-*.js` 内的样式 | 对 ShizukuIchi/winXP（MIT）里 Luna 样式的移植/改写 | MIT |
| XP 原版小图标（16/32/48 像素，`xp/ico/*`） | `web/xp/ico/NNN_16.png` 等 | ShizukuIchi/winXP `src/assets/windowsIcons/`；其中 21 个缺失的 16 像素版本由对应 32 像素图缩小生成 | 项目 MIT；图为微软素材 |
| 扫雷素材（数字、旗、笑脸、雷） | `web/xp/mine/*` | ShizukuIchi/winXP 的扫雷素材，逻辑 `apps-mine.js` 为本项目重写 | 项目 MIT；图为微软素材 |
| 24 张 XP 原版壁纸（Bliss、Autumn、Azul、Crystal、Follow、Friend、Home、Ripple、Wind、Windows XP、Winter…） | `web/xp/wall/*.jpg` | Internet Archive 上的 `windows-xp_20220726`、`winter_20240420`（Windows XP 安装包壁纸合集） | 微软版权 |
| 错误提示音 | `web/xp/error.wav` | Windows XP 系统错误提示音 | 微软版权 |
| QQ2006 主面板 / 聊天窗口 / 登录窗口的标记、样式和皮肤图 | `web/apps-qq-tpl.js` `web/qqpanel.css` `web/img/*` | mengkunsoft/QQ2006 的 `index.html` 与 `img/`（原版 QQ2006 安装包素材）；`apps-qq-tpl.js` 由脚本切片生成 | 非商用，腾讯版权 |
| 游戏短视频（约 1 MB / 28–30 秒，640 宽转码） | `web/xp/video/{cs,vc,war3,ra2}.mp4` + `.jpg` 海报 | 见 `THIRD_PARTY_NOTICES.md` §6 | **画面版权属于上传者与游戏权利人，仅个人怀旧展示** |
| 热血传奇游戏画面 | `web/xp/game/mir2.png` | 维基百科 Legend of Mir 2 游戏截图（合理使用，低分辨率） | 盛大/Wemade 版权 |
| 劲舞团（可玩节奏游戏） | `web/apps-games.js` | **自制重现**，没有使用原游戏任何素材（找不到可用的原版视频） | 原创 |
| 暴风影音 / 酷狗 / 迅雷 / QQ游戏大厅 窗口 | `web/apps-media.js` | **用 CSS 还原的外观**（配真实图标），不是原版位图 | 原创 |
| Internet Explorer 里的网页 | `web/xp/ie/*.html` | **自制** 2007 风格的导航站 / 搜索页 / QQ 门户 / 错误页，没有抓取任何真实站点 | 原创 |

---

# XP 加强包新增素材（item 3，`[xp]`，见 README §11.3）

| 内容 | 文件 | 来源 | 许可 / 备注 |
|---|---|---|---|
| XP 系统音效（启动、登录、注销、关机、叮、错误、严重错误、感叹号、通知、气泡、菜单、最小化/还原、回收站、硬件插入/移除/失败、打印…） | `web/xp/snd/*.wav` | Windows XP 原版系统音效，下载自 https://i.changeling.me/WinXPSounds/ | 微软版权，仅个人怀旧用途 |
| QQ 新消息「滴滴」、好友上线提示音 | `web/sound/Global.mp3` `web/sound/InputAlert.mp3`（另有 `msg.mp3` `system.mp3`） | mengkunsoft/QQ2006 的 `sound/`（见 `THIRD_PARTY_NOTICES.md` §1） | 非商用，腾讯版权 |
| 纸牌 / 空当接龙的牌面、牌背、空槽 | `web/xp/cards/{Club,Diamond,Heart,Spade}_0..12.png`、`CardBack_0..11.png`、`CardSlot_0..2.png` | github.com/DualBrain/Solitaire（MIT，Windows 纸牌的开源重写，使用其牌面位图）；游戏逻辑 `web/apps-cards.js` 为本项目重写 | 项目 MIT（要求保留版权声明，见 `THIRD_PARTY_NOTICES.md` §7）；牌图原作为微软素材 |
| 空当接龙发牌算法 | `web/apps-cards.js`（`msDeal`） | 微软 32000 局的公开发牌算法（线性同余），所以「第 617 号」「第 11982 号」等牌局号和原版一致 | 算法，无素材 |
| 画图工具图标（16 个 16×16） | `web/xp/paint/tools.png` | github.com/1j01/jspaint `images/classic/tools.png` | MIT（许可证原文：`web/xp/paint/LICENSE-jspaint.txt`）；画图逻辑 `web/apps-paint.js` 为本项目重写 |
| 开机画面 / 欢迎画面的 Windows XP 标志与开机图 | `web/xp/boot/*.png` | Wikimedia Commons 上的 Windows XP 开机画面截图（去掉进度条方块，由 `xp-screens.js` 按原版像素重新做动画）；`logo.png` 由同图抠出透明底的旗帜标志 | 微软版权（界面截图 / 标志，合理使用），仅个人怀旧；具体文件页没有逐一记录 |
| 控制面板、蓝屏、关机画面的图标和样式 | `web/apps-control.js` `web/xp.css` `web/xp/ico/*` | ShizukuIchi/winXP 图标（MIT）+ 本项目用 CSS 还原；蓝屏文字是按 XP 蓝屏格式自写的（错误码是假的） | 图标微软版权；其余原创 |

---

# QQ 生态新增素材（item 4，`[qq]`，见 README §11.4）

| 内容 | 文件 | 来源 | 许可 / 备注 |
|---|---|---|---|
| QQ宠物（企鹅）动画帧：待机 / 走路 / 唱歌 / 招手 / 躺倒 / 睡觉 / 喘气 / 送信，8 列 × 9 行 | `web/xp/qqpet/penguin.png`（说明 `web/xp/qqpet/README.txt`） | github.com/chenboos5/QQpet-codex `assets/QQpet-codex/spritesheet.png`（作者把 QQ宠物 的 SWF 动画转成 sprite sheet） | **美术版权属于腾讯**；该仓库没有标明许可证；仅供个人怀旧使用、不要商用。删掉这个文件宠物就没有图了（没有备用图），请同时 `[qq] pet = false` |
| QQ秀 换装（帽子 / 墨镜 / 围巾 / 领结 / 场景背景 / 飘落特效） | `web/qq-show.js` | **自绘**：SVG / CSS，叠在已有的猪猪侠 18 个姿势图上（姿势图来源见上文）；头部位置是本项目逐张量出来的 | 原创。**不是腾讯原版 QQ秀 美术**——没找到可用的原版素材，所以刻意做成风格化的卡通配饰，没有伪造“官方”图 |
| QQ空间 窗口 / 日志 / 相册 / 留言板 / 音乐盒 | `web/qq-zone.js` | **自制重现** 2007 风格（紫橙配色、标签页），没有抓取任何真实空间页面；相册图用本项目已有的猪猪侠图片 | 原创 |
| 群共享 面板 / 迅雷下载接线 | `web/qq-files.js` `web/apps-media.js`（`win.xl.add`） | **自制**；示例文件名是虚构的 | 原创 |
| 宠物道具（食物 / 皮球 / 肥皂泡） | `web/qq-pet.js` | 系统 emoji，不是原版道具图 | — |
| 窗口抖动提示音 | 复用 XP 加强包的 `qq_alert`（QQ 提示音） | 见上文 QQ 提示音一行 | 腾讯版权，仅个人使用 |
| QQ 等级图标（星星 / 月亮 / 太阳 / 皇冠） | `web/play-core.js`（内联 SVG data URI） | **自绘**：简单几何 SVG，不是腾讯原版等级图标 | 原创 |
| 熊猫烧香「中毒」图标（熊猫 + 三炷香） | `web/play-fx.js`（内联 SVG） | **自绘**的恶作剧图标，纯视觉，只通过 CSS 换桌面图标显示，不含也不执行任何病毒代码 | 原创 |
| 烟花 / 流星雨 / 表情雨 / 投票窗 / 排行榜窗 | `web/play-fx.js` `web/play-ui.js` | **自制**：canvas 动画与 XP 风 DOM 窗口；表情用系统 emoji | 原创 |
| 成语词库（29 497 条四字成语 + 拼音，用于成语接龙校验） | `backend/ai6/data/idioms.tsv`（许可全文 `backend/ai6/data/IDIOM_LICENSE.txt`） | pwxcoo/chinese-xinhua（github.com/pwxcoo/chinese-xinhua，`data/idiom.json`），只取词和拼音两列 | **MIT**，Copyright (c) 2018 PWXCOO |
| 猜歌名题库 / 脑筋急转弯题库 | `backend/ai6/data/songs.tsv` `backend/ai6/data/riddles.tsv` | **原创**整理：歌名只是公共事实，提示是自己写的描述，不含歌词；急转弯是常见的民间题目、自己重写 | 原创 |
| 趣味小游戏窗口 / 画面截取 | `web/ai-ui.js` | **自制**：XP 风 DOM 窗口；截取用浏览器自带的 SVG foreignObject + canvas | 原创 |
