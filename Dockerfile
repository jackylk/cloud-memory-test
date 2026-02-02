# 使用官方 Python 3.11 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制 web 目录的依赖文件并安装
COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 web 应用代码
COPY web/app.py .
COPY web/templates ./templates
COPY web/static ./static
COPY web/reports ./reports

# 暴露端口
EXPOSE 5000

# 启动命令
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120 --log-level info
