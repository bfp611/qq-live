#!/bin/bash
# macOS 双击一键开播（Finder 里双击；第一次如果提示「无法打开」：右键 → 打开）。关掉这个终端窗口 = 停止服务。
cd "$(dirname "$0")" || exit 1
./live.sh "$@"
code=$?
echo
echo "服务已停止（退出码 $code）。按任意键关闭窗口 …"
read -n 1 -s
