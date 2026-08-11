#!/bin/bash
echo "Stopping text-cli services..."

fuser -k 20260/tcp 2>/dev/null && echo "  copilot stopped" || true
fuser -k 28050/tcp 2>/dev/null && echo "  service stopped" || true
fuser -k 9020/tcp 2>/dev/null && echo "  mcp stopped" || true

echo "Done - copilot :20260, service :28050, mcp :9020 stopped."
