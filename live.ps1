# 一键开播（Windows）：.\live.ps1 [房间号或链接] [--no-window] [--detach] …   双击请用 live.bat
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUTF8 = "1"
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& (Join-Path $PSScriptRoot "install.ps1") -Quiet          # 依赖没变就是瞬间返回
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $venvPy (Join-Path $PSScriptRoot "tools\opsctl.py") live @args
exit $LASTEXITCODE
