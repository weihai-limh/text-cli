#!/bin/bash
# call.sh — text-cli 调用封装
# 通过 stdin 传递指令文本，从 conf.json 读取端点配置。
#
# 用法:
#   echo "AI:tc-datetime;now" | ./call.sh
#   echo "AI:tc-datetime;now" | ./call.sh -e http://其它端点/cli/text_cli
#   cat directive.txt | ./call.sh
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
ENDPOINT="${TEXT_CLI_ENDPOINT:-${ENDPOINT:-https://test.text-cli.com/cli/text_cli}}"
SERVICE_TOKEN="${TEXT_CLI_SERVICE_TOKEN:-$SERVICE_TOKEN}"
ACCESS_TOKEN="${TEXT_CLI_ACCESS_TOKEN:-$ACCESS_TOKEN}"

# ── 从 stdin 读取指令文本 ──────────────────────────────

if [ -t 0 ]; then
  echo "用法: echo 'AI:域;动作,参数' | $0" >&2
  echo "  -e, --endpoint <URL>  指定端点地址（可选）" >&2
  exit 1
fi

# 处理 -e 参数（覆盖端点）
if [ "${1:-}" = "-e" ] || [ "${1:-}" = "--endpoint" ]; then
  ENDPOINT="$2"
fi

DIRECTIVE=$(cat)

# ── 构建请求头 ─────────────────────────────────────────

CONTENT_TYPE="-H Content-Type: application/json"
AUTH_HEADERS=""

if [ -n "$ACCESS_TOKEN" ]; then
  AUTH_HEADERS="$AUTH_HEADERS -H \"Authorization: Bearer $ACCESS_TOKEN\""
fi
if [ -n "$SERVICE_TOKEN" ]; then
  AUTH_HEADERS="$AUTH_HEADERS -H \"Service-token: $SERVICE_TOKEN\""
fi

# ── 发送请求 ───────────────────────────────────────────

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
  echo "✗ 调用失败 (HTTP $HTTP_CODE)" >&2
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
  exit 1
fi

echo "$BODY" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('rst_types') == 'text':
    print(data['rst_data']['text'])
" 2>/dev/null || echo "$BODY"
