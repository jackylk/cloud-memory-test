#!/bin/bash
# 准备部署：将测试报告复制到 web 目录

echo "📦 准备部署文件..."

# 创建报告目录
mkdir -p reports

# 复制测试报告
if [ -d "../docs/test-reports" ]; then
    echo "  → 复制测试报告..."
    cp ../docs/test-reports/*.html reports/ 2>/dev/null || echo "  ⚠️  没有找到 HTML 报告"

    REPORT_COUNT=$(ls -1 reports/*.html 2>/dev/null | wc -l | tr -d ' ')
    echo "  ✓ 复制了 $REPORT_COUNT 个报告文件"
else
    echo "  ⚠️  未找到测试报告目录"
fi

echo "✅ 准备完成！"
echo ""
echo "现在可以："
echo "  1. 提交代码: git add . && git commit -m 'Prepare for deployment'"
echo "  2. 推送到 Git: git push"
echo "  3. 在 Zeabur 重新部署"
