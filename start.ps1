# 一键启动（Windows）：.\start.ps1 <直播间号或链接> [端口]
#   .\start.ps1 889896824783
#   .\start.ps1                （不带房间号：只启动页面，用 ?demo=1 看假数据，或 URL 里自己写 ?room=）
# 第一次运行会自动调用 install.ps1（建 .venv、装依赖）。双击请用 start.bat。
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUTF8 = "1"
$room = ""; $port = if ($env:PORT) { $env:PORT } else { "8765" }
$pos = @($args | Where-Object { $_ -notlike "-*" })
if ($pos.Count -ge 1) { $room = [string]$pos[0] }
if ($pos.Count -ge 2) { $port = [string]$pos[1] }

$IsWin = ($PSVersionTable.PSEdition -eq "Desktop") -or ($null -ne (Get-Variable IsWindows -ErrorAction SilentlyContinue) -and $IsWindows)
$venvPy = if ($IsWin) { Join-Path $PSScriptRoot ".venv\Scripts\python.exe" } else { Join-Path $PSScriptRoot ".venv/bin/python" }
& (Join-Path $PSScriptRoot "install.ps1") -Quiet          # 依赖没变就是瞬间返回
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$argv = @("backend/server.py"); if ($room) { $argv += $room }; $argv += @("--port", $port)
& $venvPy @argv
exit $LASTEXITCODE
