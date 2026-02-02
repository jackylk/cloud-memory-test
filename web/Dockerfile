# 使用官方 Python 3.11 镜像（更稳定，避免编译问题）
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制 web 目录的依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 web 应用代码
COPY app.py .
COPY templates ./templates
COPY static ./static

# 创建报告目录（即使为空也没问题）
RUN mkdir -p reports

# 如果 reports 目录有内容，则复制；否则跳过
COPY --chown=root:root reports ./reports || true

# 暴露端口
EXPOSE 5000

# 启动命令
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120 --log-level info
