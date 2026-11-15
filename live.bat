@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0live.ps1" %*
echo.
echo 服务已停止。按任意键关闭窗口 ...
pause >nul
