#!/bin/bash
# call.sh — text-cli 调用封装
# 通过 stdin 传递指令文本，从 conf.json 读取端点配置。
#
# 用法:
#   echo "AI:tc-datetime;now" | ./call.sh
#   echo "AI:tc-datetime;now" | ./call.sh -e http://其它端点/text-cli/cli
#   cat directive.txt | ./call.sh
#   ./call.sh --task <task_id>          # 轮询异步任务
#
# 配置（优先级: 环境变量 > conf.json > 内置默认）:
#   conf.json  — 与本脚本同目录，包含 endpoint / service_token / access_token
#   环境变量   — TEXT_CLI_ENDPOINT / TEXT_CLI_SERVICE_TOKEN / TEXT_CLI_ACCESS_TOKEN
#
# Token 在请求头中的位置:
#   access_token  → Authorization: Bearer <value>
#   service_token → Service-token: <value>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONF_FILE="${SCRIPT_DIR}/conf.json"

# ── 读取配置 ──────────────────────────────────────────

ENDPOINT=""
SERVICE_TOKEN=""
ACCESS_TOKEN=""

if [ -f "$CONF_FILE" ]; then
  CONF=$(cat "$CONF_FILE")
  ENDPOINT=$(echo "$CONF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('endpoint',''))" 2>/dev/null || true)
  SERVICE_TOKEN=$(echo "$CONF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('service_token',''))" 2>/dev/null || true)
  ACCESS_TOKEN=$(echo "$CONF" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)
fi

# 环境变量覆盖
ENDPOINT="${TEXT_CLI_ENDPOINT:-${ENDPOINT:-http://127.0.0.1:28050/text-cli/cli}}"
SERVICE_TOKEN="${TEXT_CLI_SERVICE_TOKEN:-$SERVICE_TOKEN}"
ACCESS_TOKEN="${TEXT_CLI_ACCESS_TOKEN:-$ACCESS_TOKEN}"

# ── 构建认证头（复用函数）──────────────────────────────

build_auth_headers() {
  local h=""
  if [ -n "$ACCESS_TOKEN" ]; then
    h="$h -H \"Authorization: Bearer $ACCESS_TOKEN\""
  fi
  if [ -n "$SERVICE_TOKEN" ]; then
    h="$h -H \"Service-token: $SERVICE_TOKEN\""
  fi
  echo "$h"
}

# ── 参数解析 ──────────────────────────────────────────

# 处理 -e 参数（覆盖端点）
if [ "${1:-}" = "-e" ] || [ "${1:-}" = "--endpoint" ]; then
  ENDPOINT="$2"
  shift 2
fi

# ── 轮询异步任务模式 ──────────────────────────────────

if [ "${1:-}" = "--task" ]; then
  TASK_ID="$2"
  if [ -z "$TASK_ID" ]; then
    echo "usage: $0 --task <task_id>" >&2
    exit 1
  fi

  TASK_URL="$(echo "$ENDPOINT" | sed 's|/cli$||')/tasks/${TASK_ID}"
  AUTH_HEADERS=$(build_auth_headers)

  RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X GET "$TASK_URL" \
    -H "Content-Type: application/json" \
    $AUTH_HEADERS \
    --connect-timeout 5 \
    --max-time 10)

  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | sed '$d')

  if [ "$HTTP_CODE" != "200" ]; then
    echo "[ERR] task query failed (HTTP $HTTP_CODE)" >&2
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    exit 1
  fi

  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
  exit 0
fi

# ── 从 stdin 读取指令文本 ──────────────────────────────

if [ -t 0 ]; then
  echo "usage: echo 'AI:domain;action,params' | $0" >&2
  echo "  -e, --endpoint <URL>  specify endpoint (optional)" >&2
  echo "  --task <task_id>      poll async task status" >&2
  exit 1
fi

DIRECTIVE=$(cat)

# ── 发送请求 ───────────────────────────────────────────

AUTH_HEADERS=$(build_auth_headers)

# Use python3 to safely serialize prompt as JSON — avoids shell string
# interpolation breaking on quotes, backslashes, or control characters.
BODY=$(python3 -c "import json,sys; print(json.dumps({'prompt': sys.argv[1]}))" "$DIRECTIVE")

RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  $AUTH_HEADERS \
  -d "$BODY" \
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
if data.get('status') == 'pending' and 'task_id' in data:
    print('Async task created: ' + data['task_id'] + '. Check status: ./call.sh --task ' + data['task_id'], file=sys.stderr)
if data.get('rst_data'):
    print(data['rst_data'])
" 2>/dev/null || echo "$BODY"
