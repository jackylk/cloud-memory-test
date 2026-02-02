#!/bin/bash
# 测试 Docker 构建（本地验证）

echo "🐳 测试 Docker 构建..."
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    echo "   请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查是否有报告文件
REPORT_COUNT=$(ls -1 reports/*.html 2>/dev/null | wc -l | tr -d ' ')
echo "📊 报告文件: $REPORT_COUNT 个"

if [ "$REPORT_COUNT" -eq "0" ]; then
    echo "⚠️  警告: 没有找到报告文件"
    echo "   运行: ./prepare_deploy.sh 来准备报告"
    echo ""
fi

# 构建 Docker 镜像
echo "🏗️  开始构建 Docker 镜像..."
docker build -t cloud-memory-test-web:test .

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Docker 构建失败"
    exit 1
fi

echo ""
echo "✅ Docker 镜像构建成功！"
echo ""
echo "🧪 测试运行容器..."

# 停止可能存在的旧容器
docker stop cloud-memory-test-web-test 2>/dev/null
docker rm cloud-memory-test-web-test 2>/dev/null

# 运行容器
docker run -d \
    --name cloud-memory-test-web-test \
    -p 8080:5000 \
    -e PORT=5000 \
    cloud-memory-test-web:test

if [ $? -ne 0 ]; then
    echo "❌ 容器启动失败"
    exit 1
fi

echo "⏳ 等待应用启动..."
sleep 3

# 测试健康检查
echo "🔍 测试健康检查端点..."
HEALTH_RESPONSE=$(curl -s http://localhost:8080/health)

if echo "$HEALTH_RESPONSE" | grep -q '"status": "ok"'; then
    echo "✅ 健康检查通过！"
    echo ""
    echo "🎉 Docker 构建测试成功！"
    echo ""
    echo "📍 访问地址:"
    echo "   http://localhost:8080"
    echo ""
    echo "🛑 停止测试容器:"
    echo "   docker stop cloud-memory-test-web-test"
    echo "   docker rm cloud-memory-test-web-test"
else
    echo "❌ 健康检查失败"
    echo "响应: $HEALTH_RESPONSE"

    echo ""
    echo "查看日志:"
    docker logs cloud-memory-test-web-test

    # 清理
    docker stop cloud-memory-test-web-test
    docker rm cloud-memory-test-web-test
    exit 1
fi
