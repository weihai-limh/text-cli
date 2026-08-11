#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
export TEXT_CLI_HOME="${TEXT_CLI_HOME:-$DIR}"

echo "========================================"
echo "  text-cli A3+ v0.1.1 - Linux"
echo "========================================"
echo ""
echo "[OK] TEXT_CLI_HOME = $TEXT_CLI_HOME"

# python check
if ! command -v python3 &>/dev/null; then
    echo "[ERR] python3 not installed or not in PATH"
    exit 1
fi

# config (text_cli.yaml)
CONFIG_YAML="$TEXT_CLI_HOME/service/config/text_cli.yaml"
if [ -f "$CONFIG_YAML" ]; then
    echo "[config] text_cli.yaml found at: service/config/text_cli.yaml"
elif [ -f "$TEXT_CLI_HOME/service/config/text_cli.example.yaml" ]; then
    echo "[config] text_cli.example.yaml found; rename to text_cli.yaml or start will auto-init"
fi
echo "[config] env vars override YAML settings (see docs/user-manual_zh.md 1.5)"

# Package source directory (default: sibling packages/ next to extracted archive)
if [ -z "$TEXT_CLI_PACKAGE_SOURCE_DIRS" ]; then
    export TEXT_CLI_PACKAGE_SOURCE_DIRS="$TEXT_CLI_HOME/../packages"
fi
if [ -d "$TEXT_CLI_PACKAGE_SOURCE_DIRS" ]; then
    echo "[OK] TEXT_CLI_PACKAGE_SOURCE_DIRS = $TEXT_CLI_PACKAGE_SOURCE_DIRS"
else
    echo "[WARN] Package source directory not found: $TEXT_CLI_PACKAGE_SOURCE_DIRS"
    echo "       To install packages, place them in this directory or set"
    echo "       TEXT_CLI_PACKAGE_SOURCE_DIRS to your package source location."
fi
# venv deps (isolated from global pip)
VENV_PYTHON="$TEXT_CLI_HOME/.venv/bin/python"
if [ -x "$VENV_PYTHON" ]; then
    "$VENV_PYTHON" -c "import fastapi,uvicorn,pydantic,httpx" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "[OK] deps ready (venv)"
        VENV_READY=1
    fi
fi
if [ -z "$VENV_READY" ]; then
    echo "[INFO] installing Python deps to .venv..."
    if [ ! -d "$TEXT_CLI_HOME/.venv" ]; then
        python3 -m venv "$TEXT_CLI_HOME/.venv"
        if [ $? -ne 0 ]; then
            echo "[ERR] failed to create venv"
            echo "       On Debian/Ubuntu, install it with: sudo apt install python3-venv"
            exit 1
        fi
    fi
    "$VENV_PYTHON" -m pip install -r "$TEXT_CLI_HOME/service/requirements.txt" --quiet
    if [ $? -ne 0 ]; then
        echo "[ERR] pip install failed"
        exit 1
    fi
    echo "[OK] deps ready"
fi

# config init
if [ ! -f "$TEXT_CLI_HOME/copilot/auxiliary_config.json" ]; then
    if [ -f "$TEXT_CLI_HOME/copilot/auxiliary_config.example.json" ]; then
        cp "$TEXT_CLI_HOME/copilot/auxiliary_config.example.json" "$TEXT_CLI_HOME/copilot/auxiliary_config.json"
        echo "[OK] copilot config initialized"
    fi
fi
if [ ! -f "$TEXT_CLI_HOME/service/config/text_cli.yaml" ]; then
    if [ -f "$TEXT_CLI_HOME/service/config/text_cli.example.yaml" ]; then
        cp "$TEXT_CLI_HOME/service/config/text_cli.example.yaml" "$TEXT_CLI_HOME/service/config/text_cli.yaml"
        echo "[OK] text_cli.yaml initialized"
    fi
fi
# start copilot (127.0.0.1:20260)
# A2 (copilot-only) has no SERVICE_SETUP; fall back to system python3.
if [ -z "${VENV_PYTHON:-}" ] || [ ! -x "$VENV_PYTHON" ]; then
    VENV_PYTHON="$(command -v python3)"
fi
echo ""
echo "[INFO] starting copilot (http://127.0.0.1:20260)..."
"$VENV_PYTHON" "$TEXT_CLI_HOME/copilot/text-cli-copilot.py" &
COPILOT_PID=$!
sleep 3
echo "[OK] copilot started (PID=$COPILOT_PID)" 
# start service (0.0.0.0:28050)
echo "[INFO] starting service (http://0.0.0.0:28050)..."
"$VENV_PYTHON" "$TEXT_CLI_HOME/service/main.py" &
SERVICE_PID=$!
sleep 5
# health check
echo ""
echo "[INFO] health check..."
if curl -s http://localhost:28050/text-cli/health >/dev/null 2>&1; then
    echo ""
    echo "[OK] text-cli A3+ v0.1.1 deployed!"
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
