#!/bin/bash
# Railway 快速部署脚本

set -e

echo "==================================="
echo "Railway 部署脚本"
echo "==================================="
echo ""

# 检查是否安装了 Railway CLI
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI 未安装"
    echo ""
    echo "请选择安装方式："
    echo "1. 使用 npm: npm install -g @railway/cli"
    echo "2. 使用 Homebrew (macOS): brew install railway"
    echo ""
    echo "安装后请重新运行此脚本"
    exit 1
fi

echo "✅ Railway CLI 已安装"
echo ""

# 检查是否已登录
echo "正在检查 Railway 登录状态..."
if ! railway whoami &> /dev/null; then
    echo "⚠️  未登录 Railway"
    echo "正在打开登录页面..."
    railway login
    echo ""
fi

echo "✅ 已登录 Railway"
echo ""

# 检查是否已初始化项目
if [ ! -f ".railway" ] && [ ! -d ".railway" ]; then
    echo "⚠️  尚未初始化 Railway 项目"
    echo ""
    echo "请选择："
    echo "1. 创建新项目"
    echo "2. 链接到现有项目"
    read -p "请输入选项 (1/2): " choice

    if [ "$choice" = "1" ]; then
        echo "正在创建新项目..."
        railway init
    else
        echo "正在链接到现有项目..."
        railway link
    fi
    echo ""
fi

echo "==================================="
echo "开始部署到 Railway..."
echo "==================================="
echo ""

# 部署
railway up

echo ""
echo "==================================="
echo "✅ 部署完成！"
echo "==================================="
echo ""
echo "查看日志:"
echo "  railway logs"
echo ""
echo "查看状态:"
echo "  railway status"
echo ""
echo "打开应用:"
echo "  railway open"
echo ""
echo "查看环境变量:"
echo "  railway variables"
echo ""
echo "==================================="
