#!/bin/bash
# Railway 部署前测试脚本

set -e

echo "==================================="
echo "Railway 部署前测试"
echo "==================================="
echo ""

# 检查必需文件
echo "1. 检查必需文件..."
files=("Dockerfile" "requirements.txt" "app.py" "Procfile")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file 不存在"
        exit 1
    fi
done
echo ""

# 检查配置文件
echo "2. 检查配置文件..."
if [ -f "railway.toml" ] || [ -f "../railway.toml" ] || [ -f "../railway.json" ]; then
    echo "  ✅ Railway 配置文件已找到"
else
    echo "  ⚠️  未找到 Railway 配置文件（可选）"
fi
echo ""

# 检查 Docker 是否可用
echo "3. 检查 Docker..."
if command -v docker &> /dev/null; then
    echo "  ✅ Docker 已安装"

    # 测试构建
    echo ""
    echo "  正在测试 Docker 构建..."
    if docker build -t test-railway-app . &> /dev/null; then
        echo "  ✅ Docker 构建成功"

        # 清理测试镜像
        docker rmi test-railway-app &> /dev/null || true
    else
        echo "  ❌ Docker 构建失败"
        echo "  请检查 Dockerfile 配置"
        exit 1
    fi
else
    echo "  ⚠️  Docker 未安装（可选，但建议安装以测试构建）"
fi
echo ""

# 检查依赖
echo "4. 检查 Python 依赖..."
if [ -f "requirements.txt" ]; then
    echo "  ✅ requirements.txt 存在"
    echo "  依赖列表:"
    cat requirements.txt | sed 's/^/    /'
else
    echo "  ❌ requirements.txt 不存在"
    exit 1
fi
echo ""

# 检查应用入口
echo "5. 检查应用入口..."
if grep -q "app = Flask" app.py; then
    echo "  ✅ Flask app 已定义"
else
    echo "  ❌ 未找到 Flask app 定义"
    exit 1
fi
echo ""

# 检查端口配置
echo "6. 检查端口配置..."
if grep -q "PORT" app.py || grep -q "\$PORT" Procfile; then
    echo "  ✅ PORT 环境变量已配置"
else
    echo "  ⚠️  未找到 PORT 环境变量配置"
fi
echo ""

# 检查健康检查端点
echo "7. 检查健康检查端点..."
if grep -q "/health" app.py; then
    echo "  ✅ /health 端点已定义"
else
    echo "  ⚠️  建议添加 /health 健康检查端点"
fi
echo ""

# 检查 .dockerignore
echo "8. 检查 .dockerignore..."
if [ -f ".dockerignore" ]; then
    echo "  ✅ .dockerignore 存在"
else
    echo "  ⚠️  建议创建 .dockerignore 文件"
fi
echo ""

# 检查 Railway CLI
echo "9. 检查 Railway CLI..."
if command -v railway &> /dev/null; then
    echo "  ✅ Railway CLI 已安装"
    railway --version
else
    echo "  ⚠️  Railway CLI 未安装"
    echo "  安装方法："
    echo "    npm install -g @railway/cli"
    echo "    # 或"
    echo "    brew install railway"
fi
echo ""

echo "==================================="
echo "✅ 所有检查完成！"
echo "==================================="
echo ""
echo "下一步："
echo "1. 确保已登录 Railway: railway login"
echo "2. 运行部署脚本: ./deploy_railway.sh"
echo "3. 或手动部署: railway up"
echo ""
