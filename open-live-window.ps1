# 打开「怀旧 Windows XP 桌面 + QQ 群聊」直播画面（Windows 版，给直播伴侣「窗口采集」/ OBS 用）
#   .\open-live-window.ps1                 横屏 1920x1080 窗口 + 演示数据（默认）
#   .\open-live-window.ps1 房间号          横屏，接真实直播间弹幕
#   .\open-live-window.ps1 --portrait [房间号]   竖屏模式（在竖屏显示器上全屏，只有 QQ 窗口，没有桌面）
# 可调（环境变量，PowerShell 里：$env:POS="760,160"）：
#   POS=x,y 窗口位置   TITLEBAR=40 标题栏+下边框高度   EXTRA_W=16 左右边框宽度   DESK=xp|0   PORT=8765   ANCHOR=GG-Bond
#   SCALE=3 FS=13（竖屏）   BROWSER_BIN=浏览器 exe 路径（默认自动找 Chrome / Edge）
# 注意：Windows 的 --window-size 是「外框」尺寸，所以用 TITLEBAR / EXTRA_W 补上标题栏和边框，让内容区正好 1920x1080（默认值没在真机上验证，
#       不对就调这两个数；显示缩放 125%/150% 时脚本已加 --force-device-scale-factor=1，所以不受影响）。
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$portrait = $false; $room = ""
foreach ($a in $args) { if ($a -match "^-{1,2}(portrait|p)$") { $portrait = $true } else { $room = [string]$a } }
$room = ($room -split "/")[-1]
function Env($n, $d) { $v = [Environment]::GetEnvironmentVariable($n); if ($v) { $v } else { $d } }
$port = Env "PORT" "8765"; $base = "http://localhost:$port/"
$src = if ($room) { "room=$room" } else { "demo=1" }
$src += "&anchor=" + (Env "ANCHOR" "GG-Bond")

try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 -Uri $base | Out-Null }
catch { Write-Host "服务没在运行：先在另一个窗口执行 .\start.ps1（不带房间号就是演示，带房间号接真实弹幕）" -ForegroundColor Red; exit 1 }

# ---------- 找浏览器 ----------
$browser = $env:BROWSER_BIN
if (-not $browser) {
    $pf = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA) | Where-Object { $_ }
    foreach ($rel in "Google\Chrome\Application\chrome.exe", "Microsoft\Edge\Application\msedge.exe", "Chromium\Application\chrome.exe", "BraveSoftware\Brave-Browser\Application\brave.exe") {
        foreach ($b in $pf) { $p = Join-Path $b $rel; if (Test-Path -LiteralPath $p) { $browser = $p; break } }
        if ($browser) { break }
    }
}
if (-not $browser -or -not (Test-Path -LiteralPath $browser)) { Write-Host "没找到 Chrome / Edge；设置环境变量 BROWSER_BIN 指向浏览器 exe" -ForegroundColor Red; exit 1 }

# ---------- 单独的配置目录；先关掉上一次开的窗口 ----------
$profileDir = Join-Path (Env "LOCALAPPDATA" ([System.IO.Path]::GetTempPath())) "qq-live-chrome"
try {
    Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.CommandLine -and $_.CommandLine -like "*user-data-dir=*qq-live-chrome*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
} catch {}

$common = @("--user-data-dir=`"$profileDir`"", "--no-first-run", "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required", "--force-device-scale-factor=1")
if ($portrait) {
    $url = "${base}?$src&scale=$(Env 'SCALE' '3')&fs=$(Env 'FS' '13')"
    $pos = Env "POS" "3440,-501"
    $args2 = $common + @("--kiosk", "--window-position=$pos", "--app=$url")
} else {
    $url = "${base}?$src&desk=$(Env 'DESK' 'xp')"
    $tb = [int](Env "TITLEBAR" "40"); $ew = [int](Env "EXTRA_W" "16")
    $pos = Env "POS" "760,160"
    $args2 = $common + @("--window-size=$(1920 + $ew),$(1080 + $tb)", "--window-position=$pos", "--app=$url")
}
Start-Process -FilePath $browser -ArgumentList $args2
Write-Host "已打开: $url   (浏览器: $browser；退出: 点一下那个窗口按 Alt+F4)"
