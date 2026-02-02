#!/bin/bash
# 停止 Flask 服务器脚本

echo "🛑 正在停止 Flask 服务器..."

# 查找运行在 5000 端口的进程
PID=$(lsof -ti :5000)

if [ -z "$PID" ]; then
    echo "❌ 没有找到运行在端口 5000 的进程"
    exit 1
fi

echo "找到进程 ID: $PID"

# 停止进程
kill $PID

# 等待进程停止
sleep 1

# 验证进程已停止
if lsof -ti :5000 > /dev/null 2>&1; then
    echo "⚠️  进程未能正常停止，尝试强制终止..."
    kill -9 $PID
    sleep 1
fi

if lsof -ti :5000 > /dev/null 2>&1; then
    echo "❌ 无法停止服务器"
    exit 1
else
    echo "✅ 服务器已成功停止"
fi
