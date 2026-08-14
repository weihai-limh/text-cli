#!/bin/bash
# text-cli A3-service 沙箱启动器入口（薄沙箱统一方案，2026-08-14 回灌）
# A3 = copilot(A2) + service(A3)，同容器融合。
#
# 容器 = 沙箱 + 启动器：代码 bake 在 /app/seed，首次运行吐到外挂点 /app/runtime。
# 代码/数据全外挂宿主机 —— 频繁装包、热更新不 rebuild。
#
# 环境变量：
#   PORT                service 端口（默认 28050）
#   RUNTIME_DIR         代码外挂点（默认 /app/runtime，docker -v 挂载）
#   SEED_DIR            镜像内代码种子（默认 /app/seed）
#   SERVICE_TOKEN       service 鉴权 token
#   COPILOT_ENABLED     是否启用 copilot（默认 true；127.0.0.1:20260）
#   LOG_LEVEL           日志级别（默认 info）

set -e

PORT="${PORT:-28050}"
RUNTIME_DIR="${RUNTIME_DIR:-/app/runtime}"
SEED_DIR="${SEED_DIR:-/app/seed}"
COPILOT_ENABLED="${COPILOT_ENABLED:-true}"

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

if [ ! -d "$RUNTIME_DIR/service" ]; then
    echo "[ERR] runtime code missing at $RUNTIME_DIR/service (seed failed or mount empty)"
    exit 1
fi

# 用外挂点设置 PYTHONPATH 与 TEXT_CLI_HOME
export PYTHONPATH="$RUNTIME_DIR/service:$RUNTIME_DIR/copilot"
export TEXT_CLI_HOME="${TEXT_CLI_HOME:-$RUNTIME_DIR}"

# ------------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------------
health_wait() {
    local url="$1"
    local label="$2"
    local max_attempts="${3:-10}"
    local attempt=0
    echo "[health] waiting for $label ($url) ..."
    until curl -sf "$url" > /dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ "$attempt" -ge "$max_attempts" ]; then
            echo "[health] FAILED: $label not ready after $max_attempts attempts"
            return 1
        fi
        sleep 2
    done
    echo "[health] OK: $label is ready"
}

cleanup() {
    echo ""
    echo "[shutdown] stopping all processes..."
    kill $(jobs -p) 2>/dev/null || true
    wait
    echo "[shutdown] all processes stopped"
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------------
# [0/2] copilot（条件启动，127.0.0.1:20260）
# ------------------------------------------------------------------
if [ "$COPILOT_ENABLED" = "true" ]; then
    echo "[0/2] starting copilot (127.0.0.1:20260)..."
    cd "$RUNTIME_DIR/copilot"
    python text-cli-copilot.py &
    COPILOT_PID=$!
    echo "[0/2] copilot started (pid $COPILOT_PID)"
    cd "$RUNTIME_DIR/service"
else
    echo "[0/2] copilot disabled (COPILOT_ENABLED=$COPILOT_ENABLED)"
fi

# ------------------------------------------------------------------
# [1/2] service（0.0.0.0:${PORT}，前台运行）
# ------------------------------------------------------------------
echo "[1/2] starting service (0.0.0.0:${PORT})..."
export PORT

# 等待 copilot 就绪（如果启用）
if [ "$COPILOT_ENABLED" = "true" ] && [ -n "$COPILOT_PID" ]; then
    health_wait "http://127.0.0.1:20260/text-cli/health" "copilot" 5 || true
fi

cd "$RUNTIME_DIR/service"
exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
