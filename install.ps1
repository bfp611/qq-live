# 安装 / 自检（Windows）。macOS / Linux 用 install.sh。
#   .\install.ps1                 建 .venv、装 Python 依赖（含 WinRT），并检查浏览器 / 网易云 / SMTC / 声音路由
#   .\install.ps1 -Quiet          只在需要时装依赖，不打印检查清单（start.ps1 内部用）
#   .\install.ps1 -Python C:\Python312\python.exe     指定 Python（需要 64 位 3.9 以上，推荐 3.11~3.13）
# 重复运行是安全的；依赖没变就什么也不做。右键「用 PowerShell 运行」被执行策略拦住时，用 install.bat。
param([switch]$Quiet, [string]$Python = "")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$IsWin = ($PSVersionTable.PSEdition -eq "Desktop") -or ($null -ne (Get-Variable IsWindows -ErrorAction SilentlyContinue) -and $IsWindows)

function Say($m)  { if (-not $Quiet) { Write-Host $m } }
function Ok($m)   { if (-not $Quiet) { Write-Host "  [OK] $m" -ForegroundColor Green } }
function Warn($m) { Write-Host "  [!] $m" -ForegroundColor Yellow }

# ---------- Python：找 64 位 3.9+（跳过 Microsoft Store 的假 python.exe）----------
function Get-PyInfo([string]$exe, [string[]]$pre) {
    try {
        $out = & $exe @pre -c "import sys,struct;print(sys.version_info[0],sys.version_info[1],struct.calcsize('P')*8,sys.executable)" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $out) { return $null }
        $p = ("$out").Trim().Split(" ", 4)
        if ($p.Count -lt 4) { return $null }
        return [pscustomobject]@{ Major = [int]$p[0]; Minor = [int]$p[1]; Bits = [int]$p[2]; Path = $p[3]; Cmd = $exe; Pre = $pre }
    } catch { return $null }
}
$cands = @()
if ($Python) { $cands += ,@($Python, @()) }
if ($env:PYTHON) { $cands += ,@($env:PYTHON, @()) }
if (Get-Command py -ErrorAction SilentlyContinue) { foreach ($v in "3.12", "3.13", "3.11", "3.10", "3.9") { $cands += ,@("py", @("-$v")) } }
foreach ($n in "python", "python3") { if (Get-Command $n -ErrorAction SilentlyContinue) { $cands += ,@($n, @()) } }
$py = $null; $seen = @()
foreach ($c in $cands) {
    $i = Get-PyInfo $c[0] $c[1]
    if (-not $i) { continue }
    $seen += "$($i.Major).$($i.Minor)/$($i.Bits)bit"
    if (($i.Major -gt 3 -or ($i.Major -eq 3 -and $i.Minor -ge 9)) -and ($i.Bits -eq 64 -or -not $IsWin)) { $py = $i; break }
}
if (-not $py) {
    Write-Host "找不到 64 位的 Python 3.9 或更新的版本。" -ForegroundColor Red
    if ($seen.Count) { Write-Host "  找到过但不合格的：$($seen -join ', ')（32 位 Python 装不了 mini_racer）" }
    Write-Host "  安装：winget install Python.Python.3.12     或到 https://www.python.org/downloads/ 下载（安装时勾选 Add python.exe to PATH）"
    Write-Host "  注意：Microsoft Store 里自带的 python.exe 占位程序不算；装完后重新打开 PowerShell"
    exit 1
}
Say ">>> 系统：$(if ($IsWin) { 'Windows' } else { '非 Windows（仅测试）' })   Python：$($py.Path) $($py.Major).$($py.Minor) ($($py.Bits) bit)"

# ---------- venv + 依赖 ----------
$venvPy = if ($IsWin) { Join-Path $PSScriptRoot ".venv\Scripts\python.exe" } else { Join-Path $PSScriptRoot ".venv/bin/python" }
$reqFiles = @("requirements.txt"); if ($IsWin) { $reqFiles += "requirements-win.txt" }
$sha = [System.Security.Cryptography.SHA256]::Create()
$bytes = [System.Text.Encoding]::UTF8.GetBytes(($reqFiles | ForEach-Object { Get-Content -Raw -LiteralPath $_ }) -join "`n")
$want = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "")
$readyFile = Join-Path (Join-Path $PSScriptRoot ".venv") ".ready"
$have = if (Test-Path -LiteralPath $readyFile) { (Get-Content -Raw -LiteralPath $readyFile).Trim() } else { "" }
if ($have -ne $want -or -not (Test-Path -LiteralPath $venvPy)) {
    Write-Host ">>> 安装/更新依赖（第一次约 1~2 分钟，之后不会再装）"
    if (-not (Test-Path -LiteralPath $venvPy)) {
        & $py.Cmd @($py.Pre) -m venv .venv
        if ($LASTEXITCODE -ne 0) { Write-Host "创建虚拟环境失败" -ForegroundColor Red; exit 1 }
    }
    $ErrorActionPreference = "Continue"      # pip 的警告写在 stderr，别当成错误
    & $venvPy -m pip install -q --upgrade pip
    $pipArgs = @("-m", "pip", "install", "-q"); foreach ($f in $reqFiles) { $pipArgs += @("-r", $f) }
    & $venvPy @pipArgs
    $pipRc = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($pipRc -ne 0) { Write-Host "pip 安装失败（网络？可以设置镜像：pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple）" -ForegroundColor Red; exit 1 }
    Set-Content -LiteralPath $readyFile -Value $want -Encoding ASCII
}
$imports = "import aiohttp, requests, websocket, betterproto, py_mini_racer, edge_tts"
if ($IsWin) { $imports += "; import winrt.windows.media.control" }
& $venvPy -c $imports 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "依赖导入失败：删掉 .venv 文件夹再运行 install.ps1" -ForegroundColor Red; exit 1 }
if ($Quiet) { exit 0 }
Ok "Python 依赖就绪（.venv，含 WinRT）"
if (-not $IsWin) { Say "（不是 Windows：以下检查跳过）"; exit 0 }

# ---------- 浏览器 ----------
Say ">>> 检查浏览器（open-live-window.ps1 要用 Chrome / Edge 的 --app 窗口）"
$pf = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA) | Where-Object { $_ }
$browser = $null
foreach ($rel in "Google\Chrome\Application\chrome.exe", "Microsoft\Edge\Application\msedge.exe", "Chromium\Application\chrome.exe", "BraveSoftware\Brave-Browser\Application\brave.exe") {
    foreach ($b in $pf) { $p = Join-Path $b $rel; if (Test-Path -LiteralPath $p) { $browser = $p; break } }
    if ($browser) { break }
}
if ($browser) { Ok "浏览器：$browser" } else { Warn "没找到 Chrome / Edge。Windows 10/11 自带 Edge，通常在 C:\Program Files (x86)\Microsoft\Edge\Application\。也可以设置环境变量 BROWSER_BIN 指向浏览器 exe" }

# ---------- 网易云 / SMTC ----------
Say ">>> 检查网易云音乐客户端（千千静听 / 歌词 / 点歌）"
$ncm = @("$env:LOCALAPPDATA\NetEase\CloudMusic\cloudmusic.exe", "${env:ProgramFiles(x86)}\Netease\CloudMusic\cloudmusic.exe", "$env:ProgramFiles\Netease\CloudMusic\cloudmusic.exe") | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($ncm) { Ok "网易云音乐：$ncm" } else { Warn "没找到网易云音乐客户端（点歌需要它）。官网下载安装后，在 设置 → 常规 → 系统 里勾选「开启SMTC」，否则读不到正在播放" }
if (Test-Path -LiteralPath "Registry::HKEY_CLASSES_ROOT\orpheus") { Ok "orpheus:// 协议已注册（点歌靠它启动播放）" } else { Warn "系统里没有注册 orpheus:// 协议（装了网易云才有）：点歌会失败" }
Say "  · 网易云要开 设置 → 常规 → 系统 → 「开启SMTC」；有的版本不上报播放进度，歌词会按切歌时刻自己计时（可能有一点偏差）"

# ---------- 声音路由 ----------
Say ">>> 检查声音路由（让猪猪侠的声音 / 音乐进直播）"
$cable = $null
try { $cable = Get-CimInstance Win32_SoundDevice -ErrorAction Stop | Where-Object { $_.Name -match "CABLE|VB-Audio|Voicemeeter" } | Select-Object -First 1 } catch {}
if ($cable) { Ok "虚拟声卡：$($cable.Name)" } else { Say "  · 没检测到 VB-CABLE。直播伴侣在 Windows 上可以直接采集「桌面声音」，不一定需要它；要把声音单独路由时装 VB-CABLE（https://vb-audio.com/Cable/）" }
$mate = Test-Path -LiteralPath (Join-Path $env:APPDATA "webcast_mate")
if ($mate) { Ok "检测到抖音直播伴侣的数据目录（%APPDATA%\webcast_mate；find_room.py --webcast-mate 的 Windows 路径没验证过）" }
Say ""
Say "完成。下一步：  .\start.ps1 房间号     然后     .\open-live-window.ps1 房间号      （或双击 start.bat / open-live-window.bat）"
