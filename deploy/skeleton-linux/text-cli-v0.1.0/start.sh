#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
export TEXT_CLI_HOME="${TEXT_CLI_HOME:-$DIR}"

echo "========================================"
echo "  text-cli v0.1.0 - Linux"
echo "========================================"
echo ""
echo "[OK] TEXT_CLI_HOME = $TEXT_CLI_HOME"

# python check
if ! command -v python3 &>/dev/null; then
    echo "[ERR] python3 not installed or not in PATH"
    exit 1
fi

# pip deps (one-time)
if [ ! -f "$TEXT_CLI_HOME/.deps_ok" ]; then
    echo "[INFO] installing Python deps..."
    pip3 install -r "$TEXT_CLI_HOME/service/requirements.txt" --quiet
    if [ $? -ne 0 ]; then
        echo "[ERR] pip install failed"
        exit 1
    fi
    touch "$TEXT_CLI_HOME/.deps_ok"
    echo "[OK] deps ready"
fi

# config init
if [ ! -f "$TEXT_CLI_HOME/copilot/auxiliary_config.json" ]; then
    if [ -f "$TEXT_CLI_HOME/copilot/auxiliary_config.example.json" ]; then
        cp "$TEXT_CLI_HOME/copilot/auxiliary_config.example.json" "$TEXT_CLI_HOME/copilot/auxiliary_config.json"
        echo "[OK] copilot config initialized"
    fi
fi

# start copilot (127.0.0.1:20260)
echo ""
echo "[INFO] starting copilot (http://127.0.0.1:20260)..."
python3 "$TEXT_CLI_HOME/copilot/text-cli-copilot.py" &
COPILOT_PID=$!
sleep 3
echo "[OK] copilot started (PID=$COPILOT_PID)"

# start service (0.0.0.0:28050)
echo "[INFO] starting service (http://0.0.0.0:28050)..."
python3 "$TEXT_CLI_HOME/service/main.py" &
SERVICE_PID=$!
sleep 5

# health check
echo ""
echo "[INFO] health check..."
if curl -s http://localhost:28050/text-cli/health >/dev/null 2>&1; then
    echo ""
    echo "[OK] text-cli v0.1.0 deployed!"
    echo ""
    echo "  copilot : http://127.0.0.1:20260"
    echo "  service : http://0.0.0.0:28050"
    echo ""
    echo "  test: curl -X POST http://localhost:28050/text-cli/cli -H 'Content-Type: application/json' -d '{"directive":"AI:基础应用;天气查询,北京"}'"
    echo ""
else
    echo "[WARN] health check failed - check logs"
fi
echo "  docs: docs/README_zh.md"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop all services"
wait
