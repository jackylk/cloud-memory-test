#!/bin/sh
# Railway 启动脚本

# 设置默认端口（如果 Railway 没有设置）
PORT=${PORT:-5000}

echo "Starting application on port $PORT..."

# 启动 gunicorn
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
