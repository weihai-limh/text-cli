#!/bin/bash
# text-cli MCP Server management script
# Usage: ./manage.sh {start|stop|restart|status|logs}

PORT=9020
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/.mcp-server.pid"
LOG_FILE="/tmp/text-cli-mcp-server.log"

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "MCP server already running (pid $(cat $PID_FILE))"
        return
    fi
    echo "Starting text-cli MCP Server (port $PORT)..."
    cd "$DIR"
    nohup python3 server.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Started successfully, pid $(cat $PID_FILE)"
        echo "  MCP endpoint: http://localhost:$PORT/sse"
    else
        echo "Start failed, check log: $LOG_FILE"
        cat "$LOG_FILE"
    fi
}

stop() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping MCP server (pid $pid)..."
            kill "$pid"
            sleep 1
            echo "Stopped"
        else
            echo "Process already gone (pid $pid)"
        fi
        rm -f "$PID_FILE"
    else
        echo "No pid file found"
    fi
}

restart() {
    stop
    sleep 1
    start
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "MCP server running (pid $(cat $PID_FILE), port $PORT)"
        echo "  SSE: http://localhost:$PORT/sse"
    else
        echo "MCP server not running"
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
    *)       echo "Usage: $0 {start|stop|restart|status|logs}" ;;
esac
