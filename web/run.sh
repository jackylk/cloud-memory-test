#!/bin/bash
# 快速启动脚本

echo "🚀 启动云端测试报告网站..."
echo ""

# 检查依赖
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安装"
    exit 1
fi

# 检查是否在虚拟环境中
if [ -z "$VIRTUAL_ENV" ]; then
    echo "💡 建议：在虚拟环境中运行"
    echo "   创建虚拟环境: python3 -m venv venv"
    echo "   激活虚拟环境: source venv/bin/activate"
    echo ""
fi

# 安装依赖
echo "📦 检查依赖..."
pip3 install -q -r requirements.txt

echo ""
echo "✅ 准备就绪！"
echo ""
echo "🌐 访问地址: http://localhost:5000"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""
echo "================================================"
echo ""

# 启动应用
python3 app.py
