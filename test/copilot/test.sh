#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export TEXT_CLI_COPILOT_URL="${TEXT_CLI_COPILOT_URL:-http://localhost:20260}"
export TEXT_CLI_PACKAGE_SOURCE_DIRS="${TEXT_CLI_PACKAGE_SOURCE_DIRS:-${SCRIPT_DIR}/../mock}"
exec python3 "${SCRIPT_DIR}/test.py"
