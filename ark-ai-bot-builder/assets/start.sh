#!/bin/bash
# AI Agent 統一啟動腳本（FastAPI + Bot + Schedule）
# Usage: ./start.sh [stop|restart|status|logs]

WORK_DIR="$HOME/ai-agent"
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib:$DYLD_LIBRARY_PATH"
SERVER_CMD="$WORK_DIR/.venv/bin/python -m uvicorn src.server.main:app --host 0.0.0.0 --port 3000"
PID_FILE="/tmp/ai-agent.pid"
LOG_FILE="/tmp/ai-agent.log"
PROC_PATTERN="src.server.main:app"

stop_server() {
    if [ -f "$PID_FILE" ]; then
        kill $(cat "$PID_FILE") 2>/dev/null
        rm -f "$PID_FILE"
        echo "🛑 Server 已停止"
    else
        pkill -f "$PROC_PATTERN" 2>/dev/null
        echo "🛑 Server 已停止（by pattern）"
    fi
    # 清理舊版 bot 程序
    pkill -f "src.bot.main" 2>/dev/null
}

start_server() {
    stop_server
    sleep 1
    cd "$WORK_DIR"
    nohup $SERVER_CMD > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 3
    if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo "🚀 Server 啟動成功 (PID: $(cat $PID_FILE))"
        echo "   Web:  http://localhost:3000"
        echo "   API:  http://localhost:3000/api/v1/health"
        echo "   Bot:  Telegram polling active"
        echo "📄 Log: $LOG_FILE"
    else
        echo "❌ Server 啟動失敗，查看 $LOG_FILE"
    fi
}

status_server() {
    if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo "🟢 Server 運行中 (PID: $(cat $PID_FILE))"
    else
        echo "🔴 Server 未運行"
    fi
}

case "${1:-start}" in
    stop)    stop_server ;;
    restart) stop_server; sleep 1; start_server ;;
    status)  status_server ;;
    logs)    tail -f "$LOG_FILE" ;;
    *)       start_server ;;
esac
