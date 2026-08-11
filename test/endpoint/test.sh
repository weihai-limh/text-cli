#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export TEXT_CLI_ENDPOINT_URL="${TEXT_CLI_ENDPOINT_URL:-http://localhost:29050}"
export TEXT_CLI_ACCESS_TOKEN="${TEXT_CLI_ACCESS_TOKEN:-}"
exec python3 "${SCRIPT_DIR}/test.py"
