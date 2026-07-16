#!/bin/bash
# text-cli MCP Server 管理脚本
# 用法: ./manage.sh {start|stop|restart|status|logs}

PORT=9020
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.mcp-server.pid"
LOG_FILE="/tmp/text-cli-mcp-server.log"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "MCP server 已在运行 (pid $(cat $PID_FILE))"
        return
    fi
    echo "启动 text-cli MCP Server (port $PORT)..."
    cd "$DIR"
    nohup python3 server.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "✅ 启动成功, pid $(cat $PID_FILE)"
        echo "   MCP endpoint: http://localhost:$PORT/sse"
    else
        echo "❌ 启动失败, 查看日志: $LOG_FILE"
        cat "$LOG_FILE"
    fi
}

stop() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "停止 MCP server (pid $pid)..."
            kill "$pid"
            sleep 1
            echo "✅ 已停止"
        else
            echo "进程已不存在 (pid $pid)"
        fi
        rm -f "$PID_FILE"
    else
        echo "无 pid 文件"
    fi
}

restart() {
    stop
    sleep 1
    start
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "✅ MCP server 运行中 (pid $(cat $PID_FILE), port $PORT)"
        echo "   SSE: http://localhost:$PORT/sse"
    else
        echo "❌ MCP server 未运行"
    fi
}

logs() {
    tail -30 "${1:-$LOG_FILE}"
}

case "${1:-status}" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    status)  status ;;
    logs)    logs "$2" ;;
    *)       echo "用法: $0 {start|stop|restart|status|logs}" ;;
esac
