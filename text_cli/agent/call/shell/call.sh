#!/bin/bash
# call.sh — 最简 text-cli 调用示例
# 用法: ./call.sh "<指令文本>" [端点URL]
#
# 环境变量:
#   TEXT_CLI_TOKEN    Access Token 或 Service Token
#   TEXT_CLI_ENDPOINT 默认端点地址

set -euo pipefail

DIRECTIVE="${1:?用法: $0 \"AI:领域;动作,参数1,参数2\"（指令: 仍兼容）}"
ENDPOINT="${2:-${TEXT_CLI_ENDPOINT:-https://test.text-cli.com/cli/text_cli}}"
TOKEN="${TEXT_CLI_TOKEN:-}"

echo "→ 调用: $ENDPOINT"
echo "→ 指令: $DIRECTIVE"

if [ -n "$TOKEN" ]; then
  AUTH_HEADER="Authorization: Bearer $TOKEN"
else
  AUTH_HEADER=""
fi

RESPONSE=$(curl -s -w "\n%{http_code}" \
  -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
  -d "{\"prompt\": \"$DIRECTIVE\"}" \
  --connect-timeout 5 \
  --max-time 10)

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
  echo "✗ 调用失败 (HTTP $HTTP_CODE)"
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
  exit 1
fi

echo "✓ 调用成功"
echo "$BODY" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('rst_types') == 'text':
    print(data['rst_data']['text'])
" 2>/dev/null || echo "$BODY"
