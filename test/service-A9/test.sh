#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ──────────────────────────────────────────────────────────
# text-cli service-A9 chain verification
#
# Two modes, distinguished by env var:
#
#   Mode 1 — external runtime (default):
#     Service already running. User started it via start.bat or manually.
#     Just runs tests against TEXT_CLI_BASE_URL.
#       bash test.sh
#
#   Mode 2 — layer test:
#     Auto-start deploy/A9-advanced, run tests, auto-stop.
#     Injects TEXT_CLI_PACKAGE_SOURCE_DIRS → test/mock/.
#       TEXT_CLI_LAYER_TEST=A9 bash test.sh
# ──────────────────────────────────────────────────────────

# --- layer test mode: auto-start deploy layer, auto-stop after tests ---
if [ "${TEXT_CLI_LAYER_TEST:-}" != "" ]; then
    LAYER="$TEXT_CLI_LAYER_TEST"

    # Map layer name to deploy directory
    case "$LAYER" in
        A3) DEPLOY_LAYER_DIR="A3-service" ;;
        A4) DEPLOY_LAYER_DIR="A4-paths" ;;
        A6) DEPLOY_LAYER_DIR="A6-sql" ;;
        A7) DEPLOY_LAYER_DIR="A7-mcp" ;;
        A8) DEPLOY_LAYER_DIR="A8-discovery" ;;
        A9) DEPLOY_LAYER_DIR="A9-advanced" ;;
        *)
            echo "[ERR] unknown layer: $LAYER"
            echo "      supported: A3 | A4 | A6 | A7 | A8 | A9"
            exit 1
            ;;
    esac

    DEPLOY_DIR="$PROJECT_ROOT/deploy/$DEPLOY_LAYER_DIR"
    SERVICE_MAIN="$DEPLOY_DIR/service/main.py"

    if [ ! -f "$SERVICE_MAIN" ]; then
        echo "[ERR] $SERVICE_MAIN not found."
        echo "      Run build-all.py first: python scripts/build-all.py"
        exit 1
    fi

    # --- inject layer-test environment ---
    export TEXT_CLI_HOME="$DEPLOY_DIR"
    export TEXT_CLI_PACKAGE_SOURCE_DIRS="${TEXT_CLI_PACKAGE_SOURCE_DIRS:-$SCRIPT_DIR/../mock}"
    export TEXT_CLI_BASE_URL="${TEXT_CLI_BASE_URL:-http://localhost:28050}"

    echo "========================================"
    echo "  text-cli layer test — $LAYER"
    echo "========================================"
    echo "  deploy dir : $DEPLOY_DIR"
    echo "  service    : $SERVICE_MAIN"
    echo "  mock dir   : $TEXT_CLI_PACKAGE_SOURCE_DIRS"
    echo "  base url   : $TEXT_CLI_BASE_URL"
    echo "========================================"
    echo ""

    # Check port not already in use
    if netstat -ano 2>/dev/null | grep -q ":28050.*LISTENING"; then
        echo "[ERR] port 28050 is already in use. Stop the existing service first."
        exit 1
    fi

    # Copy path test fixtures to deploy dir (path engine looks in $TEXT_CLI_HOME/paths/)
    if [ -d "$SCRIPT_DIR/paths" ]; then
        mkdir -p "$DEPLOY_DIR/paths"
        cp "$SCRIPT_DIR"/paths/*.json "$DEPLOY_DIR/paths/" 2>/dev/null || true
        echo "[LAYER TEST] Copied path fixtures to $DEPLOY_DIR/paths/"
    fi

    # Start deploy-layer service in background
    echo "[LAYER TEST] Starting deploy/$DEPLOY_LAYER_DIR/service/main.py ..."
    python "$SERVICE_MAIN" &
    SERVICE_PID=$!

    # Wait for health check
    HEALTHY=0
    for i in $(seq 1 30); do
        if curl -s http://localhost:28050/text-cli/health > /dev/null 2>&1; then
            echo "[LAYER TEST] Service healthy (PID=$SERVICE_PID, ${i}s)"
            HEALTHY=1
            break
        fi
        sleep 1
    done

    if [ "$HEALTHY" -eq 0 ]; then
        echo "[ERR] Service failed to start within 30s."
        kill "$SERVICE_PID" 2>/dev/null || true
        exit 1
    fi

    # Run tests (prefer python over python3 — Windows Git Bash python3 may be a Store stub)
    echo ""
    if command -v python3 >/dev/null 2>&1 && python3 -c "print(1)" >/dev/null 2>&1; then
        PYTHON=python3
    elif command -v python >/dev/null 2>&1; then
        PYTHON=python
    else
        echo "[ERR] neither python3 nor python is available"
        kill "$SERVICE_PID" 2>/dev/null || true
        exit 1
    fi
    $PYTHON "$SCRIPT_DIR/test.py"
    TEST_EXIT=$?

    # Stop service
    echo ""
    echo "[LAYER TEST] Stopping service (PID=$SERVICE_PID)..."
    kill "$SERVICE_PID" 2>/dev/null || true
    wait "$SERVICE_PID" 2>/dev/null || true

    # Clean up any child processes on the port
    if netstat -ano 2>/dev/null | grep -q ":28050.*LISTENING"; then
        echo "[LAYER TEST] Force-killing remaining process on :28050..."
        PID=$(netstat -ano 2>/dev/null | grep ":28050.*LISTENING" | awk '{print $NF}')
        if [ -n "$PID" ]; then
            taskkill //PID "$PID" //F 2>/dev/null || true
        fi
    fi

    echo "[LAYER TEST] Done."
    exit $TEST_EXIT
fi

# --- default mode: external runtime (user started the service) ---
export TEXT_CLI_BASE_URL="${TEXT_CLI_BASE_URL:-http://localhost:28050}"
export TEXT_CLI_PACKAGE_SOURCE_DIRS="${TEXT_CLI_PACKAGE_SOURCE_DIRS:-$SCRIPT_DIR/../mock}"

# Detect working Python (Windows Git Bash python3 may be a Store stub)
if command -v python3 >/dev/null 2>&1 && python3 -c "print(1)" >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "[ERR] neither python3 nor python is available"
    exit 1
fi
exec $PYTHON "$SCRIPT_DIR/test.py"
