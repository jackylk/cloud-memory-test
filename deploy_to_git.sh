#!/bin/bash
# 一键提交部署文件到 Git

echo "🚀 准备部署到 Git..."
echo ""

# 显示将要提交的文件
echo "📝 将要提交的文件:"
git status --short web/

echo ""
read -p "确认提交这些文件? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 取消提交"
    exit 1
fi

# 添加 web 目录
git add web/

# 添加 Zeabur 配置
git add .zeabur/ 2>/dev/null || true

# 提交
echo ""
echo "📦 提交代码..."
git commit -m "Add web application with Docker for Zeabur deployment

- Add Flask web application for test reports
- Add Dockerfile for Zeabur deployment
- Use Python 3.11 to avoid compilation issues
- Include test reports in deployment
- Simplified UI: show latest reports only
- Auto-detect report paths (dev/prod)

Changes:
- web/: Complete web application
- web/Dockerfile: Docker configuration
- web/reports/: Test report files (11 reports)
- .zeabur/config.yaml: Zeabur configuration
"

if [ $? -ne 0 ]; then
    echo "❌ 提交失败"
    exit 1
fi

echo ""
echo "✅ 提交成功！"
echo ""
echo "📤 推送到远程仓库..."
git push

if [ $? -ne 0 ]; then
    echo "❌ 推送失败"
    echo "   请检查网络连接或远程仓库配置"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                 ✅ 代码已成功推送到 Git！                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🌐 下一步: 在 Zeabur 部署"
echo ""
echo "1. 访问 https://dash.zeabur.com"
echo "2. 选择你的项目或创建新项目"
echo "3. 点击 'Add Service' → 'Git'"
echo "4. 选择你的仓库"
echo "5. 设置 Root Directory 为: web"
echo "6. 点击 'Deploy'"
echo ""
echo "📖 详细指南: web/ZEABUR_DEPLOY.md"
echo ""
