#!/bin/bash
# text-cli A2-copilot 沙箱启动器入口（薄沙箱统一方案，2026-08-14 回灌）
#
# 容器 = 沙箱 + 启动器：代码 bake 在 /app/seed，首次运行吐到外挂点 /app/runtime。
# 红线：copilot 仅本机可达(127.0.0.1:20260)，用 --network=host，回环调用，绝不 -p 暴露。
#
# 环境变量：
#   RUNTIME_DIR         代码外挂点（默认 /app/runtime，docker -v 挂载）
#   SEED_DIR            镜像内代码种子（默认 /app/seed）
#   LOG_LEVEL           日志级别（默认 info）

set -e

RUNTIME_DIR="${RUNTIME_DIR:-/app/runtime}"
SEED_DIR="${SEED_DIR:-/app/seed}"

# ------------------------------------------------------------------
# [前置] 首次吐代码：若外挂 runtime 空，从镜像 seed 复制
# ------------------------------------------------------------------
if [ -d "$SEED_DIR" ]; then
    mkdir -p "$RUNTIME_DIR"
    if [ -z "$(ls -A "$RUNTIME_DIR")" ]; then
        echo "[seed] runtime empty — provisioning from image seed..."
        cp -a "$SEED_DIR"/* "$RUNTIME_DIR"/ 2>/dev/null || cp -a "$SEED_DIR"/* . 2>/dev/null || true
        echo "[seed] runtime provisioned from image seed: $RUNTIME_DIR"
    else
        echo "[seed] runtime already present (host-managed): $RUNTIME_DIR"
    fi
else
    echo "[seed] no seed dir ($SEED_DIR) — expect host-provided runtime at $RUNTIME_DIR"
fi

if [ ! -d "$RUNTIME_DIR/copilot" ]; then
    echo "[ERR] runtime code missing at $RUNTIME_DIR/copilot (seed failed or mount empty)"
    exit 1
fi

# 用外挂点设置 PYTHONPATH
export PYTHONPATH="$RUNTIME_DIR/copilot"

# ------------------------------------------------------------------
# [1/1] copilot（127.0.0.1:20260，前台运行）
# ------------------------------------------------------------------
echo "[1/1] starting copilot (127.0.0.1:20260)..."
cd "$RUNTIME_DIR/copilot"
exec python text-cli-copilot.py
