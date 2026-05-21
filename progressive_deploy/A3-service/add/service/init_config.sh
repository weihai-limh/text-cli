#!/bin/bash
# init_config.sh - 一键初始化 text-cli service 配置
# 将 .example.json 复制为实际配置文件（不覆盖已有文件）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"

echo "初始化 text-cli service 配置..."

for f in "$CONFIG_DIR"/*.example.json; do
    [ -f "$f" ] || continue
    target="${f%.example.json}.json"
    if [ ! -f "$target" ]; then
        cp "$f" "$target"
        echo "  ✓ $(basename "$target")"
    else
        echo "  - $(basename "$target") (已存在)"
    fi
done

echo ""
echo "配置初始化完成。请在启动前编辑配置文件中的占位值。"
