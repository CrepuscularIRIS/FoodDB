#!/bin/bash
#
# 一键停止脚本
#

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "正在停止服务..."

# 停止后端
if [ -f "$PROJECT_DIR/logs/backend.pid" ]; then
    PID=$(cat "$PROJECT_DIR/logs/backend.pid")
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "✓ 后端服务已停止 (PID: $PID)"
    fi
    rm -f "$PROJECT_DIR/logs/backend.pid"
fi

# 停止前端
if [ -f "$PROJECT_DIR/logs/frontend.pid" ]; then
    PID=$(cat "$PROJECT_DIR/logs/frontend.pid")
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "✓ 前端服务已停止 (PID: $PID)"
    fi
    rm -f "$PROJECT_DIR/logs/frontend.pid"
fi

# 清理残留进程
pkill -f "python.*backend/api.py" 2>/dev/null || true
pkill -f "node.*next" 2>/dev/null || true

echo "✓ 所有服务已停止"
