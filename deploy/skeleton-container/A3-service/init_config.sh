#!/bin/bash
# init_config.sh - 一键初始化 text-cli 配置
# 将各配置目录下的 *.example.json 复制为实际 *.json（不覆盖已有文件）
#
# 用法：
#   ./init_config.sh            # 自动扫描下方候选目录
#   CONFIG_DIR=/path ./init_config.sh   # 仅处理指定目录（兼容旧用法）
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 候选配置目录：自适应 服务侧 / copilot 侧 / 显式指定
if [ -n "$CONFIG_DIR" ]; then
  CANDIDATES=("$CONFIG_DIR")
else
  CANDIDATES=(
    "$SCRIPT_DIR/config"
    "$SCRIPT_DIR/service/config"
    "$SCRIPT_DIR/copilot/config"
  )
fi

echo "初始化 text-cli 配置..."

found=0
for D in "${CANDIDATES[@]}"; do
  [ -d "$D" ] || continue
  for f in "$D"/*.example.json; do
    [ -f "$f" ] || continue
    target="${f%.example.json}.json"
    if [ ! -f "$target" ]; then
      cp "$f" "$target"
      echo "  ✓ $(basename "$target")"
    else
      echo "  - $(basename "$target") (已存在)"
    fi
    found=1
  done
done

if [ "$found" -eq 0 ]; then
  echo "  未找到任何 *.example.json（配置目录可能尚未生成，请先运行 build.py）"
fi

echo ""
echo "配置初始化完成。请在启动前编辑配置文件中的占位值。"
