#!/bin/bash
# text-cli 融合入口：启动三运行时在同一容器内
#
# 环境变量：
#   PORT                service 端口（默认 28050）
#   MCP_PORT            MCP bridge 端口（默认 9020）
#   SERVICE_TOKEN       service 鉴权 token
#   COPILOT_ENABLED     是否启用 copilot（默认 true）
#   MCP_ENABLED         是否启用 MCP bridge（默认 true）
#   LOG_LEVEL           日志级别（默认 info）

set -e

PORT="${PORT:-28050}"
MCP_PORT="${MCP_PORT:-9020}"
COPILOT_ENABLED="${COPILOT_ENABLED:-true}"
MCP_ENABLED="${MCP_ENABLED:-true}"

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
# [0/3] copilot（条件启动，127.0.0.1:20260）
# ------------------------------------------------------------------
if [ "$COPILOT_ENABLED" = "true" ]; then
    echo "[0/3] starting copilot (127.0.0.1:20260)..."
    cd /app/copilot
    python text-cli-copilot.py &
    COPILOT_PID=$!
    echo "[0/3] copilot started (pid $COPILOT_PID)"
    cd /app/service
else
    echo "[0/3] copilot disabled (COPILOT_ENABLED=$COPILOT_ENABLED)"
fi

# ------------------------------------------------------------------
# [1/3] MCP bridge（条件启动，0.0.0.0:${MCP_PORT}）
# ------------------------------------------------------------------
if [ "$MCP_ENABLED" = "true" ]; then
    echo "[1/3] starting MCP bridge (0.0.0.0:${MCP_PORT})..."
    export MCP_PORT
    cd /app/mcp
    python server.py &
    MCP_PID=$!
    echo "[1/3] MCP bridge started (pid $MCP_PID)"
    cd /app/service
else
    echo "[1/3] MCP bridge disabled (MCP_ENABLED=$MCP_ENABLED)"
fi

# ------------------------------------------------------------------
# [2/3] service（0.0.0.0:${PORT}，始终启动，前台运行）
# ------------------------------------------------------------------
echo "[2/3] starting service (0.0.0.0:${PORT})..."
export PORT

# 等待 copilot 就绪（如果启用）
if [ "$COPILOT_ENABLED" = "true" ] && [ -n "$COPILOT_PID" ]; then
    health_wait "http://127.0.0.1:20260/text-cli/health" "copilot" 5 || true
fi

exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
