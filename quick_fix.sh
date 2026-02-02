#!/bin/bash
# 快速修复 Railway 健康检查问题

set -e

echo "==================================="
echo "Railway 健康检查修复"
echo "==================================="
echo ""

echo "📝 检查修改的文件..."
echo ""
ls -lh Dockerfile web/start.sh .dockerignore 2>/dev/null || echo "文件检查完成"
echo ""

echo "✅ 已修复的内容："
echo "  1. 创建了 web/start.sh 启动脚本"
echo "  2. 更新了 Dockerfile 使用启动脚本"
echo "  3. 设置了默认 PORT=5000"
echo "  4. 更新了 .dockerignore"
echo ""

echo "➕ 添加修改的文件到 Git..."
git add Dockerfile web/start.sh .dockerignore RAILWAY_HEALTHCHECK_FIX.md
echo ""

echo "💾 创建提交..."
git commit -m "Fix Railway healthcheck - add proper startup script

- Create web/start.sh to handle PORT environment variable
- Update Dockerfile to use startup script
- Set default PORT=5000 as fallback
- Update .dockerignore to include start.sh
- Add detailed logging (access-log and error-log)

This fixes the healthcheck failure:
'service unavailable' due to incorrect port binding
" || echo "⚠️  没有需要提交的更改"
echo ""

echo "📤 推送到远程仓库..."
echo "这会触发 Railway 自动重新部署"
echo ""

read -p "是否推送？(y/N): " confirm

if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
    git push
    echo ""
    echo "==================================="
    echo "✅ 已推送！"
    echo "==================================="
    echo ""
    echo "Railway 正在重新部署..."
    echo ""
    echo "查看部署日志："
    echo "  railway logs -f"
    echo ""
    echo "预期日志输出："
    echo "  'Starting application on port XXXX...'"
    echo "  '[INFO] Starting gunicorn'"
    echo "  '[INFO] Listening at: http://0.0.0.0:XXXX'"
    echo ""
    echo "健康检查应该在 2-3 分钟内通过 ✅"
else
    echo ""
    echo "取消推送。你可以稍后手动推送："
    echo "  git push"
fi
