#!/bin/bash
# 快速提交并推送 Railway 修复

set -e

echo "==================================="
echo "Railway 部署修复 - 提交和推送"
echo "==================================="
echo ""

echo "📝 检查修改的文件..."
git status --short
echo ""

echo "➕ 添加修改的文件..."
git add Dockerfile
git add .dockerignore
git add railway.toml
git add web/Dockerfile
git add RAILWAY_FIX.md
git add web/RAILWAY_*.md
echo "✅ 文件已添加"
echo ""

echo "💾 创建提交..."
git commit -m "Fix Railway deployment - update Dockerfile path

- Create Dockerfile in project root for Railway
- Fix COPY syntax issue (remove unsupported || true)
- Update railway.toml to use root Dockerfile
- Add .dockerignore for optimized builds
- Fix web/Dockerfile as backup option

This fixes the build error:
ERROR: failed to build: failed to solve: failed to compute cache key
" || echo "⚠️  没有需要提交的更改，或已经提交"
echo ""

echo "📤 推送到远程仓库..."
read -p "是否推送到远程？这会触发 Railway 自动部署。(y/N): " confirm

if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
    git push
    echo ""
    echo "==================================="
    echo "✅ 已推送！"
    echo "==================================="
    echo ""
    echo "Railway 会自动检测到更新并开始部署。"
    echo ""
    echo "查看部署状态："
    echo "  1. 访问 Railway Dashboard"
    echo "  2. 或运行: railway logs -f"
    echo ""
else
    echo "取消推送。你可以稍后手动推送："
    echo "  git push"
fi
