"""云端记忆与知识库性能测试报告网站"""
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, send_file, abort
from collections import defaultdict

app = Flask(__name__)

# 测试报告目录 - 支持本地开发和生产环境
# 优先使用本地开发路径，如果不存在则使用部署路径
_local_reports = Path(__file__).parent.parent / "docs" / "test-reports"
_deploy_reports = Path(__file__).parent / "reports"

if _local_reports.exists():
    REPORTS_DIR = _local_reports
elif _deploy_reports.exists():
    REPORTS_DIR = _deploy_reports
else:
    # 如果都不存在，创建部署路径
    _deploy_reports.mkdir(exist_ok=True)
    REPORTS_DIR = _deploy_reports


def get_reports():
    """获取所有报告文件，按类型和时间分组"""
    kb_reports = []
    memory_reports = []

    if not REPORTS_DIR.exists():
        return kb_reports, memory_reports

    # 扫描所有HTML报告
    for html_file in REPORTS_DIR.glob("*.html"):
        filename = html_file.name

        # 解析文件名：kb_report_20260201_001106.html
        if filename.startswith("kb_report_"):
            parts = filename.replace("kb_report_", "").replace(".html", "").split("_")
            if len(parts) >= 2:
                date_str = parts[0]  # 20260201
                time_str = parts[1]  # 001106
                try:
                    report_time = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                    kb_reports.append({
                        "filename": filename,
                        "time": report_time,
                        "display_time": report_time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                except:
                    pass

        elif filename.startswith("memory_report_"):
            parts = filename.replace("memory_report_", "").replace(".html", "").split("_")
            if len(parts) >= 2:
                date_str = parts[0]
                time_str = parts[1]
                try:
                    report_time = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                    memory_reports.append({
                        "filename": filename,
                        "time": report_time,
                        "display_time": report_time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                except:
                    pass

    # 按时间倒序排序（最新的在前）
    kb_reports.sort(key=lambda x: x["time"], reverse=True)
    memory_reports.sort(key=lambda x: x["time"], reverse=True)

    return kb_reports, memory_reports


@app.route('/')
def index():
    """首页"""
    kb_reports, memory_reports = get_reports()

    return render_template('index.html',
                         kb_count=len(kb_reports),
                         memory_count=len(memory_reports),
                         latest_kb=kb_reports[0] if kb_reports else None,
                         latest_memory=memory_reports[0] if memory_reports else None)


@app.route('/kb')
def kb_reports():
    """重定向到最新的知识库报告"""
    from flask import redirect, url_for
    kb_reports, _ = get_reports()
    if kb_reports:
        # 直接跳转到最新报告
        return redirect(url_for('view_report', filename=kb_reports[0]['filename']))
    else:
        # 没有报告时显示提示页面
        return render_template('no_reports.html', report_type='知识库')


@app.route('/memory')
def memory_reports():
    """重定向到最新的记忆系统报告"""
    from flask import redirect, url_for
    _, memory_reports = get_reports()
    if memory_reports:
        # 直接跳转到最新报告
        return redirect(url_for('view_report', filename=memory_reports[0]['filename']))
    else:
        # 没有报告时显示提示页面
        return render_template('no_reports.html', report_type='记忆系统')


@app.route('/report/<filename>')
def view_report(filename):
    """查看报告详情"""
    # 安全检查：只允许访问HTML报告
    if not filename.endswith('.html'):
        abort(404)

    if not (filename.startswith('kb_report_') or filename.startswith('memory_report_')):
        abort(404)

    report_path = REPORTS_DIR / filename

    if not report_path.exists():
        abort(404)

    # 直接返回HTML文件
    return send_file(report_path, mimetype='text/html')


@app.route('/health')
def health():
    """健康检查接口"""
    return {"status": "ok", "service": "cloud-memory-test-reports"}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
