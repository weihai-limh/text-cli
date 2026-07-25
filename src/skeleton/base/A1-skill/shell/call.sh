#!/bin/bash
# call.sh — text-cli invocation wrapper
# Pass the directive text via stdin; read endpoint config from conf.json.
#
# Usage:
#   echo "AI:tc-datetime;now" | ./call.sh
#   echo "AI:tc-datetime;now" | ./call.sh -e http://other-endpoint/cli/text_cli
#   cat directive.txt | ./call.sh
#
# Config (priority: env var > conf.json > built-in default):
#   conf.json  — same dir as this script; contains endpoint / service_token / access_token
#   env vars   — TEXT_CLI_ENDPOINT / TEXT_CLI_SERVICE_TOKEN / TEXT_CLI_ACCESS_TOKEN
#
# Token placement in request headers:
#   access_token  → Authorization: Bearer <value>
#   service_token → Service-token: <value>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONF_FILE="${SCRIPT_DIR}/conf.json"

# ── Read config ──────────────────────────────────────

ENDPOINT=""
SERVICE_TOKEN=""
ACCESS_TOKEN=""

if [ -f "$CONF_FILE" ]; then
  CONF=$(cat "$CONF_FILE")
  ENDPOINT=$(echo "$CONF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('endpoint',''))" 2>/dev/null || true)
  SERVICE_TOKEN=$(echo "$CONF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('service_token',''))" 2>/dev/null || true)
  ACCESS_TOKEN=$(echo "$CONF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
fi

# Env var override
ENDPOINT="${TEXT_CLI_ENDPOINT:-${ENDPOINT:-https://test.text-cli.com/text-cli/cli}}"  # 默认指向 demo 示范端点，可覆盖
SERVICE_TOKEN="${TEXT_CLI_SERVICE_TOKEN:-$SERVICE_TOKEN}"
ACCESS_TOKEN="${TEXT_CLI_ACCESS_TOKEN:-$ACCESS_TOKEN}"

# ── Read directive text from stdin ───────────────────

if [ -t 0 ]; then
  echo "usage: echo 'AI:domain;action,params' | $0" >&2
  echo "  -e, --endpoint <URL>  specify endpoint (optional)" >&2
  exit 1
fi

# Handle -e argument (override endpoint)
if [ "${1:-}" = "-e" ] || [ "${1:-}" = "--endpoint" ]; then
  ENDPOINT="$2"
fi

DIRECTIVE=$(cat)

# ── Build request headers ────────────────────────────

CONTENT_TYPE="-H Content-Type: application/json"
AUTH_HEADERS=""

if [ -n "$ACCESS_TOKEN" ]; then
  AUTH_HEADERS="$AUTH_HEADERS -H \"Authorization: Bearer $ACCESS_TOKEN\""
fi
if [ -n "$SERVICE_TOKEN" ]; then
  AUTH_HEADERS="$AUTH_HEADERS -H \"Service-token: $SERVICE_TOKEN\""
fi

# ── Send request ─────────────────────────────────────

RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "$ENDPOINT" \
  $CONTENT_TYPE \
  $AUTH_HEADERS \
  -d "{\"prompt\": \"$DIRECTIVE\"}" \
  --connect-timeout 5 \
  --max-time 10)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
  echo "[ERR] call failed (HTTP $HTTP_CODE)" >&2
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
  exit 1
fi

echo "$BODY" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('rst_types') == 'text':
    print(data['rst_data']['text'])
" 2>/dev/null || echo "$BODY"
