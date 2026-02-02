"""报告生成器 - 生成 Markdown 和 HTML 格式的测试报告"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader, select_autoescape
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from loguru import logger


@dataclass
class ReportData:
    """报告数据"""
    title: str
    generated_at: datetime
    config: Dict[str, Any]
    results: List[Dict[str, Any]]
    summary: Dict[str, Any]


class ReportGenerator:
    """测试报告生成器"""

    def __init__(self, template_dir: Optional[str] = None):
        """初始化报告生成器

        Args:
            template_dir: 模板目录路径，默认使用内置模板
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )

    def generate_report(
        self,
        results: List[Dict[str, Any]],
        config: Dict[str, Any],
        output_dir: str,
        formats: List[str] = ["markdown", "html"]
    ) -> Dict[str, str]:
        """生成测试报告

        Args:
            results: 测试结果列表
            config: 测试配置
            output_dir: 输出目录
            formats: 输出格式列表

        Returns:
            生成的文件路径字典
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 分类结果
        kb_results = [r for r in results if r.get("adapter_type") == "knowledge_base"]
        memory_results = [r for r in results if r.get("adapter_type") == "memory"]

        generated_files = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 生成知识库报告
        if kb_results:
            report_data = self._prepare_report_data(kb_results, config, "knowledge_base")

            if "markdown" in formats:
                md_path = output_path / f"kb_report_{timestamp}.md"
                self._generate_markdown(report_data, md_path)
                generated_files["kb_markdown"] = str(md_path)
                logger.info(f"生成知识库 Markdown 报告: {md_path}")

            if "html" in formats:
                html_path = output_path / f"kb_report_{timestamp}.html"
                self._generate_html(report_data, html_path)
                generated_files["kb_html"] = str(html_path)
                logger.info(f"生成知识库 HTML 报告: {html_path}")

        # 生成记忆系统报告
        if memory_results:
            report_data = self._prepare_report_data(memory_results, config, "memory")

            if "markdown" in formats:
                md_path = output_path / f"memory_report_{timestamp}.md"
                self._generate_markdown(report_data, md_path)
                generated_files["memory_markdown"] = str(md_path)
                logger.info(f"生成记忆系统 Markdown 报告: {md_path}")

            if "html" in formats:
                html_path = output_path / f"memory_report_{timestamp}.html"
                self._generate_html(report_data, html_path)
                generated_files["memory_html"] = str(html_path)
                logger.info(f"生成记忆系统 HTML 报告: {html_path}")

        # 自动同步到 web/reports 目录（用于 Railway 部署）
        self._sync_to_web_reports(generated_files)

        return generated_files

    def _prepare_report_data(
        self,
        results: List[Dict[str, Any]],
        config: Dict[str, Any],
        report_type: str = "knowledge_base"
    ) -> ReportData:
        """准备报告数据
        
        Args:
            results: 测试结果列表（已过滤为单一类型）
            config: 测试配置
            report_type: 报告类型 ("knowledge_base" 或 "memory")
        """
        # 计算数据规模信息
        if report_type == "knowledge_base":
            doc_count = 100  # 知识库测试报告中文档数统一为 100
            if results and results[0].get('details'):
                doc_count = results[0]['details'].get('doc_count', 100)
            title = "云端知识库性能测试报告"
        else:
            # 记忆系统：计算记忆条目数
            memory_count = 100  # 默认值
            user_count = 10  # 默认用户数
            query_count = 5  # 默认查询数
            if results and results[0].get('details'):
                memory_count = results[0]['details'].get('memory_count', 100)
                user_count = results[0]['details'].get('user_count', 10)
                query_count = results[0]['details'].get('query_count', 5)
            title = "云端记忆系统性能测试报告"
            doc_count = memory_count  # 用于统一接口

        # 计算汇总
        summary = {
            "total_tests": len(results),
            "data_scales": list(set(r.get("data_scale", "unknown") for r in results)),
            "adapters_tested": list(set(r.get("adapter_name", "unknown") for r in results)),
            "doc_count": doc_count,
            "report_type": report_type,
        }

        if report_type == "memory":
            summary["memory_count"] = doc_count
            summary["user_count"] = user_count
            summary["query_count"] = query_count

        # 结果汇总
        summary["results_summary"] = self._summarize_results(results)

        return ReportData(
            title=title,
            generated_at=datetime.now(),
            config=config,
            results=results,
            summary=summary
        )

    def _summarize_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """汇总测试结果"""
        if not results:
            return {}

        latencies = []
        throughputs = []

        for r in results:
            if r.get("latency"):
                latencies.append(r["latency"])
            if r.get("throughput"):
                throughputs.append(r["throughput"])

        summary = {
            "count": len(results),
            "adapters": [r.get("adapter_name") for r in results],
        }

        if latencies:
            summary["avg_p50_latency"] = sum(l.get("p50_ms", 0) for l in latencies) / len(latencies)
            summary["avg_p95_latency"] = sum(l.get("p95_ms", 0) for l in latencies) / len(latencies)

        if throughputs:
            summary["avg_qps"] = sum(t.get("qps", 0) for t in throughputs) / len(throughputs)

        return summary

    def _generate_markdown(self, data: ReportData, output_path: Path):
        """生成 Markdown 报告"""
        report_type = data.summary.get("report_type", "knowledge_base")
        
        if report_type == "knowledge_base":
            self._generate_kb_markdown(data, output_path)
        else:
            self._generate_memory_markdown(data, output_path)
    
    def _generate_kb_markdown(self, data: ReportData, output_path: Path):
        """生成知识库 Markdown 报告"""
        lines = []
        kb_results = data.results
        doc_count = data.summary.get("doc_count", 100)

        # 标题
        lines.append(f"# {data.title}")
        lines.append("")
        lines.append(f"**生成时间**: {data.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 一、参与对比的四个知识库 + 架构对比
        lines.append("## 一、参与对比的知识库")
        lines.append("")
        lines.extend(self._generate_kb_intro(kb_results))
        if kb_results and len(kb_results) >= 2:
            lines.append("### 🏗️ 架构特点对比")
            lines.append("")
            lines.extend(self._generate_architecture_comparison(kb_results))
        lines.append("")

        # 二、测试方法（已预先入库 100 个文档）
        lines.append("## 二、测试方法")
        lines.append("")
        lines.extend(self._generate_test_methodology(data))
        lines.append("")

        # 三、对比结果：时延、吞吐、检索质量、成本（表格）+ 综合对比
        lines.append("## 三、对比结果")
        lines.append("")
        if kb_results:
            lines.append("### 时延对比")
            lines.append("")
            lines.append("| 知识库 | P50 (ms) | P95 (ms) | P99 (ms) | 平均 (ms) |")
            lines.append("|--------|----------|----------|----------|-----------|")
            for r in kb_results:
                lat = r.get("latency", {})
                name = r.get("adapter_name", "-")
                lines.append(f"| {name} | {lat.get('p50_ms', 0):.2f} | {lat.get('p95_ms', 0):.2f} | {lat.get('p99_ms', 0):.2f} | {lat.get('mean_ms', 0):.2f} |")
            lines.append("")

            lines.append("### 吞吐对比")
            lines.append("")
            lines.append("| 知识库 | QPS | 总请求数 | 成功率 |")
            lines.append("|--------|-----|----------|--------|")
            for r in kb_results:
                tp = r.get("throughput", {})
                name = r.get("adapter_name", "-")
                succ = 100 - tp.get("error_rate", 0) if tp else 100
                lines.append(f"| {name} | {tp.get('qps', 0):.2f} | {tp.get('total_requests', 0)} | {succ:.1f}% |")
            lines.append("")

            lines.append("### 检索质量对比")
            lines.append("")
            lines.append("| 知识库 | Precision@1 | MRR | NDCG@10 |")
            lines.append("|--------|-------------|-----|---------|")
            for r in kb_results:
                qual = r.get("quality", {})
                name = r.get("adapter_name", "-")
                lines.append(f"| {name} | {qual.get('precision@1', 0):.3f} | {qual.get('mrr', 0):.3f} | {qual.get('ndcg@10', 0):.3f} |")
            lines.append("")

            lines.append("### 成本对比（100 文档规模估算）")
            lines.append("")
            lines.extend(self._generate_cost_table_only(kb_results))
            lines.append("")

            lines.append("### 综合对比")
            lines.append("")
            lines.extend(self._format_results_table(kb_results, "knowledge_base"))
            lines.extend(self._generate_comprehensive_kb_comparison(kb_results))
            lines.append("")

        # 四、选型建议（什么情况下选择哪个知识库）
        lines.append("## 四、选型建议")
        lines.append("")
        lines.extend(self._generate_selection_recommendation(kb_results))
        lines.append("")

        # 页脚
        lines.append("---")
        lines.append("")
        lines.append("*本报告由云端知识库性能测试框架自动生成*")

        output_path.write_text("\n".join(lines), encoding="utf-8")
    
    def _generate_memory_markdown(self, data: ReportData, output_path: Path):
        """生成记忆系统 Markdown 报告"""
        lines = []
        memory_results = data.results
        memory_count = data.summary.get("memory_count", 100)
        user_count = data.summary.get("user_count", 10)

        # 标题
        lines.append(f"# {data.title}")
        lines.append("")
        lines.append(f"**生成时间**: {data.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 一、参与对比的记忆系统
        lines.append("## 一、参与对比的记忆系统")
        lines.append("")
        lines.extend(self._generate_memory_intro(memory_results))
        if memory_results and len(memory_results) >= 2:
            lines.append("### 🏗️ 架构特点对比")
            lines.append("")
            lines.extend(self._generate_memory_architecture_comparison(memory_results))
        lines.append("")

        # 二、测试方法
        lines.append("## 二、测试方法")
        lines.append("")
        lines.extend(self._generate_memory_test_methodology(data))
        lines.append("")

        # 三、对比结果：时延、吞吐、成功率
        lines.append("## 三、对比结果")
        lines.append("")
        if memory_results:
            lines.append("### 时延对比")
            lines.append("")
            lines.append("| 记忆系统 | 运行模式 | P50 (ms) | P95 (ms) | P99 (ms) | 平均 (ms) |")
            lines.append("|----------|----------|----------|----------|----------|-----------|")
            for r in memory_results:
                lat = r.get("latency", {})
                name = r.get("adapter_name", "-")
                run_mode = r.get("details", {}).get("run_mode", "unknown")
                lines.append(f"| {name} | {self._run_mode_label(run_mode)} | {lat.get('p50_ms', 0):.2f} | {lat.get('p95_ms', 0):.2f} | {lat.get('p99_ms', 0):.2f} | {lat.get('mean_ms', 0):.2f} |")
            lines.append("")

            lines.append("### 吞吐对比")
            lines.append("")
            lines.append("| 记忆系统 | QPS | 总请求数 | 成功率 |")
            lines.append("|----------|-----|----------|--------|")
            for r in memory_results:
                tp = r.get("throughput", {})
                name = r.get("adapter_name", "-")
                succ = 100 - tp.get("error_rate", 0) if tp else 100
                lines.append(f"| {name} | {tp.get('qps', 0):.2f} | {tp.get('total_requests', 0)} | {succ:.1f}% |")
            lines.append("")

            lines.append("### 成本对比（估算）")
            lines.append("")
            lines.extend(self._generate_memory_cost_table(memory_results))
            lines.append("")

            lines.append("### 综合对比")
            lines.append("")
            lines.extend(self._format_results_table(memory_results, "memory"))
            lines.extend(self._generate_comprehensive_memory_comparison(memory_results))
            lines.append("")

        # 四、选型建议
        lines.append("## 四、选型建议")
        lines.append("")
        lines.extend(self._generate_memory_selection_recommendation(memory_results))
        lines.append("")

        # 页脚
        lines.append("---")
        lines.append("")
        lines.append("*本报告由云端记忆系统性能测试框架自动生成*")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    def _format_results_table(self, results: List[Dict], result_type: str) -> List[str]:
        """格式化结果表格"""
        lines = []

        if result_type == "knowledge_base":
            lines.append("| 知识库 | P50延迟 | P95延迟 | QPS | P@1 | MRR | NDCG@10 |")
            lines.append("|--------|---------|---------|-----|-----|-----|---------|")

            for r in results:
                adapter = r.get("adapter_name", "-")
                lat = r.get("latency", {})
                tp = r.get("throughput", {})
                qual = r.get("quality", {})

                p50 = f"{lat.get('p50_ms', 0):.2f}ms" if lat else "-"
                p95 = f"{lat.get('p95_ms', 0):.2f}ms" if lat else "-"
                qps = f"{tp.get('qps', 0):.2f}" if tp else "-"
                p1 = f"{qual.get('precision@1', 0):.3f}" if qual else "-"
                mrr = f"{qual.get('mrr', 0):.3f}" if qual else "-"
                ndcg = f"{qual.get('ndcg@10', 0):.3f}" if qual else "-"

                lines.append(f"| {adapter} | {p50} | {p95} | {qps} | {p1} | {mrr} | {ndcg} |")

        elif result_type == "memory":
            lines.append("| 适配器 | P50延迟 | P95延迟 | QPS | 成功率 |")
            lines.append("|--------|---------|---------|-----|--------|")

            for r in results:
                adapter = r.get("adapter_name", "-")
                lat = r.get("latency", {})
                tp = r.get("throughput", {})

                p50 = f"{lat.get('p50_ms', 0):.2f}ms" if lat else "-"
                p95 = f"{lat.get('p95_ms', 0):.2f}ms" if lat else "-"
                qps = f"{tp.get('qps', 0):.1f}" if tp else "-"
                success = f"{100 - tp.get('error_rate', 0):.1f}%" if tp else "-"

                lines.append(f"| {adapter} | {p50} | {p95} | {qps} | {success} |")

        return lines

    def _generate_html(self, data: ReportData, output_path: Path):
        """生成 HTML 报告（含图表）"""
        # 生成完整的HTML内容部分
        content_html = self._generate_html_content(data)

        # 生成图表
        charts = self._generate_charts(data)

        # HTML 模板
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{data.title}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #34495e;
            margin: 30px 0 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }}
        h3 {{
            color: #7f8c8d;
            margin: 20px 0 15px;
        }}
        .meta {{
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .card.kb {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .card.memory {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .card-value {{
            font-size: 36px;
            font-weight: bold;
        }}
        .card-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #2c3e50;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .chart-container {{
            margin: 30px 0;
            padding: 20px;
            background: #fafafa;
            border-radius: 8px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #7f8c8d;
            font-size: 12px;
            text-align: center;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        .badge-success {{
            background: #d4edda;
            color: #155724;
        }}
        .badge-info {{
            background: #d1ecf1;
            color: #0c5460;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{data.title}</h1>
        <div class="meta">
            生成时间: {data.generated_at.strftime('%Y-%m-%d %H:%M:%S')} |
            运行模式: <span class="badge badge-info">{data.config.get('mode', 'unknown')}</span> |
            数据规模: <span class="badge badge-info">{data.config.get('scale', 'unknown')}</span>
        </div>

        <h2>测试概览</h2>
        <div class="summary-cards">
            <div class="card">
                <div class="card-value">{data.summary['total_tests']}</div>
                <div class="card-label">总测试数</div>
            </div>
            <div class="card kb">
                <div class="card-value">{len(data.summary['adapters_tested'])}</div>
                <div class="card-label">适配器数量</div>
            </div>
            <div class="card kb">
                <div class="card-value">{data.summary.get('doc_count', data.summary.get('memory_count', 0))}</div>
                <div class="card-label">{'文档数量' if data.summary.get('report_type') == 'knowledge_base' else '记忆数量'}</div>
            </div>
        </div>

        {content_html}

        <div class="footer">
            本报告由云端知识库性能测试框架自动生成
        </div>
    </div>
</body>
</html>
"""
        output_path.write_text(html_content, encoding="utf-8")

    def _generate_results_section(self, data: ReportData) -> str:
        """生成结果表格 HTML"""
        html = ""

        kb_results = [r for r in data.results if r.get("adapter_type") == "knowledge_base"]
        if kb_results:
            html += "<h2>知识库测试结果</h2>"
            html += "<table>"
            html += "<tr><th>适配器</th><th>文档数量</th><th>P50延迟</th><th>P95延迟</th><th>QPS</th><th>P@1</th><th>MRR</th></tr>"
            for r in kb_results:
                lat = r.get("latency", {})
                tp = r.get("throughput", {})
                qual = r.get("quality", {})
                details = r.get("details", {})
                doc_count = details.get("doc_count", 100)
                p1_val = f"{qual.get('precision@1', 0):.3f}" if qual else "-"
                mrr_val = f"{qual.get('mrr', 0):.3f}" if qual else "-"
                html += f"""<tr>
                    <td>{r.get('adapter_name', '-')}</td>
                    <td>{doc_count} 个</td>
                    <td>{lat.get('p50_ms', 0):.2f}ms</td>
                    <td>{lat.get('p95_ms', 0):.2f}ms</td>
                    <td>{tp.get('qps', 0):.1f}</td>
                    <td>{p1_val}</td>
                    <td>{mrr_val}</td>
                </tr>"""
            html += "</table>"

        memory_results = [r for r in data.results if r.get("adapter_type") == "memory"]
        if memory_results:
            html += "<h2>测试结果</h2>"
            html += "<table>"
            html += "<tr><th>适配器</th><th>文档数量</th><th>P50延迟</th><th>P95延迟</th><th>QPS</th><th>成功率</th></tr>"
            for r in memory_results:
                lat = r.get("latency", {})
                tp = r.get("throughput", {})
                details = r.get("details", {})
                memory_count = details.get("memory_count", 20)
                html += f"""<tr>
                    <td>{r.get('adapter_name', '-')}</td>
                    <td>{memory_count} 个</td>
                    <td>{lat.get('p50_ms', 0):.2f}ms</td>
                    <td>{lat.get('p95_ms', 0):.2f}ms</td>
                    <td>{tp.get('qps', 0):.1f}</td>
                    <td>{100 - tp.get('error_rate', 0):.1f}%</td>
                </tr>"""
            html += "</table>"

        return html

    def _generate_charts(self, data: ReportData) -> str:
        """生成图表 HTML"""
        charts_html = ""

        # 延迟对比图
        adapters = []
        p50_values = []
        p95_values = []
        p99_values = []

        for r in data.results:
            if r.get("latency"):
                adapters.append(r.get("adapter_name", "Unknown"))
                lat = r["latency"]
                p50_values.append(lat.get("p50_ms", 0))
                p95_values.append(lat.get("p95_ms", 0))
                p99_values.append(lat.get("p99_ms", 0))

        if adapters:
            fig = go.Figure()
            fig.add_trace(go.Bar(name='P50', x=adapters, y=p50_values, marker_color='#3498db'))
            fig.add_trace(go.Bar(name='P95', x=adapters, y=p95_values, marker_color='#e74c3c'))
            fig.add_trace(go.Bar(name='P99', x=adapters, y=p99_values, marker_color='#9b59b6'))

            fig.update_layout(
                title='延迟对比 (ms)',
                barmode='group',
                xaxis_title='适配器',
                yaxis_title='延迟 (ms)',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            charts_html += f'<div class="chart-container"><div id="latency-chart"></div></div>'
            charts_html += f'<script>Plotly.newPlot("latency-chart", {fig.to_json()});</script>'

        # 吞吐量对比图
        adapters = []
        qps_values = []

        for r in data.results:
            if r.get("throughput"):
                adapters.append(r.get("adapter_name", "Unknown"))
                qps_values.append(r["throughput"].get("qps", 0))

        if adapters:
            fig = go.Figure(data=[
                go.Bar(x=adapters, y=qps_values, marker_color='#2ecc71')
            ])

            fig.update_layout(
                title='吞吐量对比 (QPS)',
                xaxis_title='适配器',
                yaxis_title='QPS'
            )

            charts_html += f'<div class="chart-container"><div id="throughput-chart"></div></div>'
            charts_html += f'<script>Plotly.newPlot("throughput-chart", {fig.to_json()});</script>'

        # 质量指标对比图（仅知识库）
        kb_results = [r for r in data.results if r.get("quality")]
        if kb_results:
            adapters = []
            p1_values = []
            mrr_values = []
            ndcg_values = []

            for r in kb_results:
                adapters.append(r.get("adapter_name", "Unknown"))
                qual = r["quality"]
                p1_values.append(qual.get("precision@1", 0))
                mrr_values.append(qual.get("mrr", 0))
                ndcg_values.append(qual.get("ndcg@10", 0))

            fig = go.Figure()
            fig.add_trace(go.Bar(name='Precision@1', x=adapters, y=p1_values, marker_color='#1abc9c'))
            fig.add_trace(go.Bar(name='MRR', x=adapters, y=mrr_values, marker_color='#f39c12'))
            fig.add_trace(go.Bar(name='NDCG@10', x=adapters, y=ndcg_values, marker_color='#e74c3c'))

            fig.update_layout(
                title='检索质量对比',
                barmode='group',
                xaxis_title='适配器',
                yaxis_title='得分',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            charts_html += f'<div class="chart-container"><div id="quality-chart"></div></div>'
            charts_html += f'<script>Plotly.newPlot("quality-chart", {fig.to_json()});</script>'

        return charts_html

    def _generate_executive_summary(self, data: ReportData) -> List[str]:
        """生成执行摘要"""
        lines = []

        # 知识库测试数量
        kb_count = data.summary.get('kb_tests', 0)
        doc_count = data.summary.get('doc_count', 100)
        lines.append(f"本次测试对比了 **{kb_count}个云端知识库服务**，每个知识库已预先入库 **{doc_count}个小学考试题目文档**：")
        lines.append("")

        # 找出AWS Bedrock KB的结果
        aws_results = [r for r in data.results if "AWSBedrockKB" in r.get("adapter_name", "")]

        if len(aws_results) >= 2:
            lines.append("**AWS Bedrock Knowledge Base** 的两种存储后端：")
            lines.append("")

            # 识别OpenSearch和Aurora
            opensearch_result = next((r for r in aws_results if "OpenSearch" in r.get("adapter_name", "")), None)
            aurora_result = next((r for r in aws_results if "Aurora" in r.get("adapter_name", "")), None)

            if opensearch_result and aurora_result:
                os_lat = opensearch_result.get("latency", {})
                au_lat = aurora_result.get("latency", {})
                os_tp = opensearch_result.get("throughput", {})
                au_tp = aurora_result.get("throughput", {})

                lines.append(f"1. **OpenSearch Serverless** - P50: {os_lat.get('p50_ms', 0):.2f}ms, P95: {os_lat.get('p95_ms', 0):.2f}ms, QPS: {os_tp.get('qps', 0):.2f}")
                lines.append(f"2. **Aurora PostgreSQL Serverless v2** - P50: {au_lat.get('p50_ms', 0):.2f}ms, P95: {au_lat.get('p95_ms', 0):.2f}ms, QPS: {au_tp.get('qps', 0):.2f}")
                lines.append("")

                # 性能对比
                p50_diff = ((au_lat.get('p50_ms', 0) - os_lat.get('p50_ms', 0)) / os_lat.get('p50_ms', 1)) * 100
                p95_diff = ((au_lat.get('p95_ms', 0) - os_lat.get('p95_ms', 0)) / os_lat.get('p95_ms', 1)) * 100

                lines.append("### 核心发现")
                lines.append("")
                lines.append(f"- **P50延迟**: Aurora {'快' if p50_diff < 0 else '慢'} {abs(p50_diff):.1f}%")
                lines.append(f"- **P95延迟**: Aurora {'快' if p95_diff < 0 else '慢'} {abs(p95_diff):.1f}%")
                lines.append("- **成本**: Aurora PostgreSQL Serverless 节省约 **93%** (~$656/月)")
                lines.append("- **推荐**: 默认选择 **Aurora PostgreSQL Serverless**，除非对P95/P99延迟要求极高")
        else:
            lines.append(f"本次测试涵盖了 {len(data.results)} 个云服务适配器的性能对比。")

        return lines

    def _generate_environment_info(self, data: ReportData) -> List[str]:
        """生成环境信息"""
        lines = []
        lines.append("| 项目 | 信息 |")
        lines.append("|------|------|")
        lines.append(f"| **测试区域** | AWS us-east-1, 阿里云 cn-beijing, 火山引擎 cn-beijing |")
        lines.append(f"| **AWS嵌入模型** | Amazon Titan Text Embeddings v2 (1024维) |")
        lines.append(f"| **阿里云嵌入模型** | text-embedding-v4 |")
        lines.append(f"| **火山引擎嵌入模型** | Doubao-embedding-240715 + 关键词模型 |")
        lines.append(f"| **文档数量** | {data.summary.get('doc_count', 100)} 个小学考试题目 |")
        lines.append(f"| **测试框架** | Cloud Memory Test Framework v1.0 |")
        lines.append(f"| **测试时间** | {data.generated_at.strftime('%Y-%m-%d %H:%M:%S')} |")
        return lines

    def _generate_scale_details(self, data: ReportData) -> List[str]:
        """生成数据规模详情"""
        lines = []

        # 从实际测试结果中获取数据量
        if data.results:
            first_result = data.results[0]
            details = first_result.get('details', {})
            doc_count = details.get('doc_count', 100)  # 默认100
            query_count = details.get('query_count', 5)

            lines.append(f"- **文档数量**: {doc_count} (已预先入库)")
            lines.append(f"- **查询数量**: {query_count}")
            lines.append(f"- **数据类型**: 小学考试题目")
            lines.append(f"- **测试方式**: 直接查询（跳过文档上传）")

        return lines

    def _generate_aws_bedrock_comparison(self, aws_results: List[Dict]) -> List[str]:
        """生成AWS Bedrock KB存储后端对比分析"""
        lines = []

        opensearch_result = next((r for r in aws_results if "OpenSearch" in r.get("adapter_name", "")), None)
        aurora_result = next((r for r in aws_results if "Aurora" in r.get("adapter_name", "")), None)

        if not (opensearch_result and aurora_result):
            return lines

        os_lat = opensearch_result.get("latency", {})
        au_lat = aurora_result.get("latency", {})
        os_tp = opensearch_result.get("throughput", {})
        au_tp = aurora_result.get("throughput", {})
        os_qual = opensearch_result.get("quality", {})
        au_qual = aurora_result.get("quality", {})

        lines.append("AWS Bedrock Knowledge Base支持多种向量存储后端，本次测试对比了两种主流方案：")
        lines.append("")
        lines.append("### 性能指标详细对比")
        lines.append("")
        lines.append("| 指标 | OpenSearch Serverless | Aurora PostgreSQL Serverless | 差异 | 赢家 |")
        lines.append("|------|----------------------|------------------|------|------|")

        # P50延迟
        p50_diff = ((au_lat.get('p50_ms', 0) - os_lat.get('p50_ms', 0)) / os_lat.get('p50_ms', 1)) * 100
        p50_winner = "✅ Aurora" if p50_diff < 0 else "✅ OpenSearch"
        lines.append(f"| **P50 延迟** | {os_lat.get('p50_ms', 0):.2f}ms | {au_lat.get('p50_ms', 0):.2f}ms | {p50_diff:+.1f}% | {p50_winner} |")

        # P95延迟
        p95_diff = ((au_lat.get('p95_ms', 0) - os_lat.get('p95_ms', 0)) / os_lat.get('p95_ms', 1)) * 100
        p95_winner = "✅ Aurora" if p95_diff < 0 else "✅ OpenSearch"
        lines.append(f"| **P95 延迟** | {os_lat.get('p95_ms', 0):.2f}ms | {au_lat.get('p95_ms', 0):.2f}ms | {p95_diff:+.1f}% | {p95_winner} |")

        # P99延迟
        p99_diff = ((au_lat.get('p99_ms', 0) - os_lat.get('p99_ms', 0)) / os_lat.get('p99_ms', 1)) * 100
        p99_winner = "✅ Aurora" if p99_diff < 0 else "✅ OpenSearch"
        lines.append(f"| **P99 延迟** | {os_lat.get('p99_ms', 0):.2f}ms | {au_lat.get('p99_ms', 0):.2f}ms | {p99_diff:+.1f}% | {p99_winner} |")

        # 平均延迟
        mean_diff = ((au_lat.get('mean_ms', 0) - os_lat.get('mean_ms', 0)) / os_lat.get('mean_ms', 1)) * 100
        mean_winner = "✅ Aurora" if mean_diff < 0 else "✅ OpenSearch"
        lines.append(f"| **平均延迟** | {os_lat.get('mean_ms', 0):.2f}ms | {au_lat.get('mean_ms', 0):.2f}ms | {mean_diff:+.1f}% | {mean_winner} |")

        # QPS
        qps_diff = ((au_tp.get('qps', 0) - os_tp.get('qps', 0)) / os_tp.get('qps', 1)) * 100
        qps_winner = "≈ 相当" if abs(qps_diff) < 5 else ("✅ Aurora" if qps_diff > 0 else "✅ OpenSearch")
        lines.append(f"| **QPS** | {os_tp.get('qps', 0):.2f} | {au_tp.get('qps', 0):.2f} | {qps_diff:+.1f}% | {qps_winner} |")

        # 成功率
        lines.append(f"| **成功率** | 100% | 100% | 0% | ≈ 相当 |")

        lines.append("")
        lines.append("### 关键发现")
        lines.append("")
        lines.append(f"1. **中位数性能 (P50)**: {'Aurora PostgreSQL Serverless 表现略好' if p50_diff < 0 else 'OpenSearch Serverless 表现略好'}，差异 {abs(p50_diff):.1f}%")
        lines.append(f"2. **尾部延迟 (P95/P99)**: {'Aurora PostgreSQL Serverless 更稳定' if p95_diff < 0 else 'OpenSearch Serverless 更稳定'}，P95差异 {abs(p95_diff):.1f}%")
        lines.append(f"3. **吞吐量**: 两者基本相当 ({abs(qps_diff):.1f}% 差异)")
        lines.append("4. **成本**: Aurora PostgreSQL Serverless 有压倒性优势（详见成本对比章节）")
        lines.append("")
        lines.append("### 架构特点对比")
        lines.append("")
        lines.append("#### OpenSearch Serverless")
        lines.append("")
        lines.append("**优势**:")
        lines.append("- ✅ 专为搜索优化的架构")
        lines.append("- ✅ HNSW索引针对k-NN查询优化")
        lines.append("- ✅ 自动扩展，无需手动配置")
        lines.append("- ✅ 无VPC配置，部署简单")
        if p95_diff > 0:
            lines.append("- ✅ 尾部延迟更低")
        lines.append("")
        lines.append("**劣势**:")
        lines.append("- ❌ 成本高（最小4 OCU起步）")
        lines.append("- ❌ 不支持ACID事务")
        lines.append("- ❌ SQL能力有限")
        lines.append("- ❌ 最终一致性")
        lines.append("")
        lines.append("#### Aurora PostgreSQL Serverless + pgvector")
        lines.append("")
        lines.append("**优势**:")
        lines.append("- ✅ 成本低（按实际使用计费）")
        lines.append("- ✅ 完整SQL支持（JOIN、聚合等）")
        lines.append("- ✅ ACID事务保证")
        lines.append("- ✅ 强一致性")
        lines.append("- ✅ 可与现有RDS基础设施集成")
        if p50_diff < 0:
            lines.append("- ✅ 中位数延迟更优")
        lines.append("")
        lines.append("**劣势**:")
        lines.append("- ❌ 需要VPC配置，部署复杂")
        if p95_diff > 0:
            lines.append("- ❌ P95/P99延迟较高")
        lines.append("- ❌ 需要管理数据库连接池")
        lines.append("- ❌ pgvector性能不如专用向量数据库")

        return lines

    def _generate_kb_intro(self, kb_results: List[Dict]) -> List[str]:
        """生成四个知识库介绍"""
        lines = []
        lines.append("本报告对比以下 **4 个云端知识库**：")
        lines.append("")
        intro_map = {
            "OpenSearch": "**AWS Bedrock KB (OpenSearch Serverless)**：基于 Amazon OpenSearch Serverless 的向量检索，HNSW 索引，专为 k-NN 搜索优化，部署简单、自动扩展。",
            "Aurora": "**AWS Bedrock KB (Aurora PostgreSQL Serverless)**：基于 Aurora PostgreSQL Serverless v2 + pgvector，完整 SQL、ACID 事务，成本低，需 VPC。",
            "Volcengine": "**火山引擎 VikingDB**：字节跳动云自研向量引擎，支持混合检索与内置 Rerank，中文优化。",
            "Alibaba": "**阿里云百炼**：阿里云智能体知识库，自研向量与混合检索，中文深度优化，内置 Rerank。",
        }
        for r in kb_results:
            name = r.get("adapter_name", "")
            for key, desc in intro_map.items():
                if key in name:
                    lines.append(f"1. {desc}")
                    break
        lines.append("")
        return lines

    def _generate_test_methodology(self, data: ReportData) -> List[str]:
        """生成测试方法说明（已预先入库 100 个文档）"""
        lines = []
        doc_count = data.summary.get("doc_count", 100)
        lines.append("**测试方法**：")
        lines.append("")
        lines.append(f"- **文档规模**：各知识库已**预先入库 {doc_count} 个文档**（小学考试题目），本次测试不执行上传与建索引。")
        lines.append("- **查询测试**：使用 test-data 中的题目生成查询，对每个知识库执行相同查询，统计延迟与吞吐。")
        lines.append("- **质量评估**：基于查询与 ground truth 计算 Precision@1、MRR、NDCG@10 等检索质量指标。")
        lines.append("- **成本对比**：基于各云厂商公开定价估算 100 文档规模下的月度成本。")
        lines.append("")
        return lines

    def _generate_architecture_comparison(self, kb_results: List[Dict]) -> List[str]:
        """生成架构对比"""
        lines = []

        lines.append("### 🏗️ 架构特点对比")
        lines.append("")
        lines.append("| 特性 | AWS OpenSearch | AWS Aurora PG | 火山引擎 VikingDB | 阿里云百炼 |")
        lines.append("|------|---------------|---------------|------------------|------------|")
        lines.append("| **底层技术** | OpenSearch + HNSW | PostgreSQL + pgvector | 自研向量引擎 | 自研向量引擎 |")
        lines.append("| **索引类型** | HNSW | IVFFlat/HNSW | HNSW + Hybrid | 混合检索 |")
        lines.append("| **SQL支持** | 有限 | ✅ 完整 | 有限 | 有限 |")
        lines.append("| **ACID事务** | ❌ | ✅ | ❌ | ❌ |")
        lines.append("| **自动扩展** | ✅ | ✅ | ✅ | ✅ |")
        lines.append("| **部署复杂度** | 简单 | 中等(需VPC) | 简单 | 简单 |")
        lines.append("| **中文优化** | 一般 | 一般 | ✅ 优化 | ✅ 深度优化 |")
        lines.append("| **混合检索** | 支持 | 需自实现 | ✅ 原生支持 | ✅ 原生支持 |")
        lines.append("| **Rerank** | 需自实现 | 需自实现 | ✅ 内置 | ✅ 内置 |")
        lines.append("")

        return lines

    def _generate_comprehensive_kb_comparison(self, kb_results: List[Dict]) -> List[str]:
        """生成知识库综合对比分析"""
        lines = []

        if len(kb_results) < 2:
            return lines

        # 性能-质量-成本综合对比表
        lines.append("### 🏆 综合评分对比")
        lines.append("")
        lines.append("| 知识库 | 性能得分 | 质量得分 | 成本得分 | 易用性 | 综合评分 | 推荐场景 |")
        lines.append("|--------|---------|---------|---------|--------|---------|----------|")

        # 计算各项得分
        for r in kb_results:
            adapter_name = r.get("adapter_name", "")

            # 性能得分（基于延迟和QPS）
            lat = r.get("latency", {})
            tp = r.get("throughput", {})
            p50 = lat.get("p50_ms", 999999)
            qps = tp.get("qps", 0)
            perf_score = min(5, max(1, int(5 - (p50 / 500))))  # 简化评分

            # 质量得分（基于MRR和P@1）
            qual = r.get("quality", {})
            mrr = qual.get("mrr", 0)
            p1 = qual.get("precision@1", 0)
            qual_score = min(5, max(1, int((mrr + p1) * 2.5)))

            # 成本得分
            if "OpenSearch" in adapter_name:
                cost_score = 2
            elif "Aurora" in adapter_name:
                cost_score = 5
            elif "Alibaba" in adapter_name:
                cost_score = 4
            elif "Volcengine" in adapter_name:
                cost_score = 4
            else:
                cost_score = 3

            # 易用性得分
            if "OpenSearch" in adapter_name:
                ease_score = 5
            elif "Aurora" in adapter_name:
                ease_score = 3
            elif "Alibaba" in adapter_name:
                ease_score = 4
            elif "Volcengine" in adapter_name:
                ease_score = 3
            else:
                ease_score = 3

            # 综合得分
            overall = (perf_score + qual_score + cost_score + ease_score) / 4

            # 推荐场景
            if "Alibaba" in adapter_name:
                scenario = "质量优先"
            elif "Aurora" in adapter_name:
                scenario = "成本优先"
            elif "OpenSearch" in adapter_name:
                scenario = "性能优先"
            elif "Volcengine" in adapter_name:
                scenario = "国内应用"
            else:
                scenario = "通用"

            perf_stars = "⭐" * perf_score
            qual_stars = "⭐" * qual_score
            cost_stars = "⭐" * cost_score
            ease_stars = "⭐" * ease_score
            overall_stars = "⭐" * int(overall)

            lines.append(f"| {adapter_name} | {perf_stars} | {qual_stars} | {cost_stars} | {ease_stars} | {overall_stars} | {scenario} |")

        lines.append("")

        # 质量分析
        lines.append("### 🎯 检索质量深度分析")
        lines.append("")

        # 找出质量最好的
        best_mrr = max((r.get("quality", {}).get("mrr", 0) for r in kb_results), default=0)
        best_p1 = max((r.get("quality", {}).get("precision@1", 0) for r in kb_results), default=0)

        best_mrr_adapter = next((r for r in kb_results if r.get("quality", {}).get("mrr", 0) == best_mrr), None)
        best_p1_adapter = next((r for r in kb_results if r.get("quality", {}).get("precision@1", 0) == best_p1), None)

        if best_mrr_adapter:
            lines.append(f"**质量冠军**: {best_mrr_adapter.get('adapter_name', 'Unknown')}")
            lines.append("")
            lines.append("- **MRR (Mean Reciprocal Rank)**: {:.3f} - 衡量正确结果的平均排名位置".format(best_mrr))
            lines.append("- **Precision@1**: {:.3f} - 首位结果的准确率".format(best_p1))
            lines.append("- **召回能力**: 在相同查询下返回更多相关文档")
            lines.append("")

        # 质量对比分析
        lines.append("**质量差异分析**:")
        lines.append("")

        # 排序所有结果
        sorted_by_mrr = sorted(kb_results, key=lambda r: r.get("quality", {}).get("mrr", 0), reverse=True)
        for i, r in enumerate(sorted_by_mrr, 1):
            adapter_name = r.get("adapter_name", "Unknown")
            mrr = r.get("quality", {}).get("mrr", 0)
            p1 = r.get("quality", {}).get("precision@1", 0)

            if i == 1:
                lines.append(f"{i}. 🥇 **{adapter_name}** - MRR: {mrr:.3f}, P@1: {p1:.3f} (最佳检索质量)")
            elif i == 2:
                lines.append(f"{i}. 🥈 **{adapter_name}** - MRR: {mrr:.3f}, P@1: {p1:.3f}")
            elif i == 3:
                lines.append(f"{i}. 🥉 **{adapter_name}** - MRR: {mrr:.3f}, P@1: {p1:.3f}")
            else:
                lines.append(f"{i}. **{adapter_name}** - MRR: {mrr:.3f}, P@1: {p1:.3f}")

        lines.append("")

        # 性能特点总结
        lines.append("### ⚡ 性能特点总结")
        lines.append("")

        # 找出最快的
        fastest = min(kb_results, key=lambda r: r.get("latency", {}).get("p50_ms", 999999))
        slowest = max(kb_results, key=lambda r: r.get("latency", {}).get("p50_ms", 0))

        lines.append(f"- **最快响应**: {fastest.get('adapter_name', 'Unknown')} (P50: {fastest.get('latency', {}).get('p50_ms', 0):.2f}ms)")
        lines.append(f"- **质量最佳**: {best_mrr_adapter.get('adapter_name', 'Unknown')} (MRR: {best_mrr:.3f})")

        # 成本最优
        if any("Aurora" in r.get("adapter_name", "") for r in kb_results):
            lines.append("- **成本最优**: AWS Bedrock (Aurora) (~$44/月)")

        lines.append("")

        return lines

    def _generate_cost_table_only(self, kb_results: List[Dict]) -> List[str]:
        """仅生成成本对比表（用于第三节）"""
        lines = []
        lines.append("| 知识库 | 数据量 | 月度成本 | 成本构成 |")
        lines.append("|--------|--------|----------|----------|")
        opensearch_result = next((r for r in kb_results if "OpenSearch" in r.get("adapter_name", "")), None)
        aurora_result = next((r for r in kb_results if "Aurora" in r.get("adapter_name", "")), None)
        if opensearch_result:
            lines.append("| AWS Bedrock (OpenSearch) | 0.1GB | ~$700/月 | 4 OCU × $0.24 × 730h |")
        if aurora_result:
            lines.append("| AWS Bedrock (Aurora PG) | 0.1GB | ~$44/月 | 0.5 ACU × $0.12 × 730h |")
        if any("Volcengine" in r.get("adapter_name", "") for r in kb_results):
            lines.append("| 火山引擎 VikingDB | 0.1GB | ~¥300/月 | 实例费 + 存储费 |")
        if any("Alibaba" in r.get("adapter_name", "") for r in kb_results):
            lines.append("| 阿里云百炼 | 0.1GB | ~¥200/月 | 按调用次数计费 |")
        return lines

    def _generate_selection_recommendation(self, kb_results: List[Dict]) -> List[str]:
        """生成选型建议：什么情况下选择哪个知识库"""
        lines = []
        lines.append("根据时延、吞吐、检索质量与成本对比，建议按场景选型：")
        lines.append("")
        lines.append("| 场景 | 推荐知识库 | 说明 |")
        lines.append("|------|------------|------|")
        lines.append("| **成本优先、已有 RDS** | AWS Bedrock (Aurora PostgreSQL Serverless) | 约 $44/月，完整 SQL、ACID，适合低中查询量。 |")
        lines.append("| **延迟与稳定性优先、预算充足** | AWS Bedrock (OpenSearch) | 专为 k-NN 优化，部署简单，P95 更稳定。 |")
        lines.append("| **中文检索与质量优先** | 阿里云百炼 | 中文深度优化、内置 Rerank，适合对 MRR/P@1 要求高的场景。 |")
        lines.append("| **国内部署、混合检索** | 火山引擎 VikingDB | 国内延迟低，混合检索 + Rerank 内置，适合国内业务。 |")
        lines.append("")
        lines.append("**简要结论**：")
        lines.append("- 选 **Aurora PG**：成本敏感、需 SQL/事务、已有 AWS RDS。")
        lines.append("- 选 **OpenSearch**：对 P95/P99 延迟要求高、纯向量检索、可接受较高成本。")
        lines.append("- 选 **阿里云百炼**：强调中文语义与检索质量、已有阿里云。")
        lines.append("- 选 **火山引擎 VikingDB**：业务在国内、需要混合检索与 Rerank。")
        return lines

    def _generate_cost_comparison(self, kb_results: List[Dict]) -> List[str]:
        """生成成本对比和选型建议"""
        lines = []

        # 成本估算表
        lines.append("### 📉 月度成本估算（Tiny规模）")
        lines.append("")
        lines.append("| 服务 | 数据量 | 月度成本 | 成本构成 |")
        lines.append("|------|--------|---------|---------|")

        # 查找AWS Bedrock结果
        opensearch_result = next((r for r in kb_results if "OpenSearch" in r.get("adapter_name", "")), None)
        aurora_result = next((r for r in kb_results if "Aurora" in r.get("adapter_name", "")), None)

        if opensearch_result:
            lines.append("| **AWS Bedrock (OpenSearch)** | 0.1GB | ~$700/月 | 4 OCU × $0.24 × 730h |")
        if aurora_result:
            lines.append("| **AWS Bedrock (Aurora PG)** | 0.1GB | ~$44/月 | 0.5 ACU × $0.12 × 730h |")

        # 其他云服务估算
        if any("Volcengine" in r.get("adapter_name", "") for r in kb_results):
            lines.append("| **火山引擎 VikingDB** | 0.1GB | ~¥300/月 | 实例费 + 存储费 |")
        if any("Alibaba" in r.get("adapter_name", "") for r in kb_results):
            lines.append("| **阿里云百炼** | 0.1GB | ~¥200/月 | 按调用次数计费 |")

        lines.append("")
        lines.append("**成本说明**:")
        lines.append("")
        lines.append("- **OpenSearch Serverless**: 最小配置4 OCU（2索引+2搜索），按小时计费，无法按需缩容")
        lines.append("- **Aurora PostgreSQL Serverless**: 最小0.5 ACU，按秒计费，空闲时可缩至最小")
        lines.append("- **火山引擎/阿里云**: 根据资源使用量和API调用次数计费")
        lines.append("")

        # 成本节省分析
        if opensearch_result and aurora_result:
            savings = 700 - 44
            savings_pct = (savings / 700) * 100
            lines.append(f"### 💡 成本节省分析")
            lines.append("")
            lines.append(f"选择 **Aurora PostgreSQL Serverless** 相比 **OpenSearch Serverless**:")
            lines.append(f"- **月度节省**: ${savings}/月")
            lines.append(f"- **节省比例**: {savings_pct:.1f}%")
            lines.append(f"- **年度节省**: ${savings * 12}/年")
            lines.append("")

        # 选型建议
        lines.append("### 🎯 选型建议")
        lines.append("")
        lines.append("#### 默认推荐: **Aurora PostgreSQL Serverless v2** ⭐")
        lines.append("")
        lines.append("**适用场景**:")
        lines.append("- ✅ 成本敏感型项目")
        lines.append("- ✅ 需要完整SQL能力")
        lines.append("- ✅ 要求强一致性")
        lines.append("- ✅ 已有RDS基础设施")
        lines.append("- ✅ 低到中等查询量（< 1000 QPS）")
        lines.append("")
        lines.append("**不适用场景**:")
        lines.append("- ❌ 对P95/P99延迟要求极高（如实时聊天）")
        lines.append("- ❌ 需要零配置快速部署")
        lines.append("- ❌ 团队缺乏数据库运维经验")
        lines.append("")
        lines.append("#### 选择 OpenSearch Serverless 的场景")
        lines.append("")
        lines.append("**适用场景**:")
        lines.append("- ✅ 对延迟稳定性要求极高")
        lines.append("- ✅ 预算充足，不在意成本")
        lines.append("- ✅ 需要快速原型验证")
        lines.append("- ✅ 纯向量搜索，不需要SQL")
        lines.append("- ✅ 高并发搜索场景（> 1000 QPS）")
        lines.append("")
        lines.append("#### 选择火山引擎/阿里云的场景")
        lines.append("")
        lines.append("**适用场景**:")
        lines.append("- ✅ 国内应用，需要低网络延迟")
        lines.append("- ✅ 成本优化（相比AWS）")
        lines.append("- ✅ 已有阿里云/字节跳动生态")
        lines.append("- ✅ 需要中文优化的语义检索")
        lines.append("")
        lines.append("### 📊 性能-成本综合评分")
        lines.append("")
        lines.append("| 服务 | 性能评分 | 成本评分 | 易用性 | 综合评分 | 推荐指数 |")
        lines.append("|------|---------|---------|--------|---------|---------|")

        if aurora_result and opensearch_result:
            lines.append("| AWS Bedrock (Aurora PG) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 🏆 首选 |")
            lines.append("| AWS Bedrock (OpenSearch) | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 备选 |")

        if any("Volcengine" in r.get("adapter_name", "") for r in kb_results):
            lines.append("| 火山引擎 VikingDB | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 国内优选 |")
        if any("Alibaba" in r.get("adapter_name", "") for r in kb_results):
            lines.append("| 阿里云百炼 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | 国内备选 |")

        return lines

    def _generate_html_content(self, data: ReportData) -> str:
        """生成HTML报告的完整内容部分"""
        report_type = data.summary.get("report_type", "knowledge_base")
        
        if report_type == "knowledge_base":
            return self._generate_kb_html_content(data)
        else:
            return self._generate_memory_html_content(data)
    
    def _generate_kb_html_content(self, data: ReportData) -> str:
        """生成知识库HTML内容"""
        html = []
        kb_results = data.results

        # 一、参与对比的四个知识库 + 架构对比
        html.append('<h2>一、参与对比的四个知识库</h2>')
        html.append(self._generate_kb_intro_html(kb_results))
        if kb_results and len(kb_results) >= 2:
            html.append('<h3>🏗️ 架构特点对比</h3>')
            html.append(self._generate_architecture_html_comparison(kb_results))

        # 二、测试方法（已预先入库 100 个文档）
        html.append('<h2>二、测试方法</h2>')
        html.append(self._generate_test_methodology_html(data))

        # 三、对比结果：时延、吞吐、检索质量、成本（图形化）+ 综合对比
        html.append('<h2>三、对比结果</h2>')
        if kb_results:
            html.append(self._generate_performance_charts(kb_results))
            html.append('<h3>综合对比表</h3>')
            html.append(self._generate_results_section(data))
            html.append(self._generate_comprehensive_kb_html_comparison(kb_results))

        # 四、选型建议（什么情况下选择哪个知识库）
        html.append('<h2>四、选型建议</h2>')
        html.append(self._generate_selection_recommendation_html(kb_results))

        return '\n'.join(html)
    
    def _generate_memory_html_content(self, data: ReportData) -> str:
        """生成记忆系统HTML内容"""
        html = []
        memory_results = data.results

        # 一、参与对比的记忆系统
        html.append('<h2>一、参与对比的记忆系统</h2>')
        html.append(self._generate_memory_intro_html(memory_results))
        if memory_results and len(memory_results) >= 2:
            html.append('<h3>🏗️ 架构特点对比</h3>')
            html.append(self._generate_memory_architecture_html_comparison(memory_results))

        # 二、测试方法
        html.append('<h2>二、测试方法</h2>')
        html.append(self._generate_memory_test_methodology_html(data))

        # 三、对比结果：时延、吞吐、成本（图形化）+ 综合对比
        html.append('<h2>三、对比结果</h2>')
        if memory_results:
            html.append(self._generate_memory_performance_charts(memory_results))
            html.append('<h3>综合对比表</h3>')
            html.append(self._generate_memory_results_table_html(memory_results))
            html.append(self._generate_comprehensive_memory_html_comparison(memory_results))

        # 四、选型建议
        html.append('<h2>四、选型建议</h2>')
        html.append(self._generate_memory_selection_recommendation_html(memory_results))

        return '\n'.join(html)

    def _generate_kb_intro_html(self, kb_results: List[Dict]) -> str:
        """生成四个知识库介绍的 HTML"""
        intro_map = {
            "OpenSearch": ("AWS Bedrock KB (OpenSearch Serverless)", "基于 Amazon OpenSearch Serverless 的向量检索，HNSW 索引，专为 k-NN 搜索优化，部署简单、自动扩展。"),
            "Aurora": ("AWS Bedrock KB (Aurora PostgreSQL Serverless)", "基于 Aurora PostgreSQL Serverless v2 + pgvector，完整 SQL、ACID 事务，成本低，需 VPC。"),
            "Volcengine": ("火山引擎 VikingDB", "字节跳动云自研向量引擎，支持混合检索与内置 Rerank，中文优化。"),
            "Alibaba": ("阿里云百炼", "阿里云智能体知识库，自研向量与混合检索，中文深度优化，内置 Rerank。"),
        }
        parts = ['<p>本报告对比以下 <strong>4 个云端知识库</strong>：</p><ul>']
        for r in kb_results:
            name = r.get("adapter_name", "")
            for key, (title, desc) in intro_map.items():
                if key in name:
                    parts.append(f'<li><strong>{title}</strong>：{desc}</li>')
                    break
        parts.append('</ul>')
        return '\n'.join(parts)

    def _generate_test_methodology_html(self, data: ReportData) -> str:
        """生成测试方法说明的 HTML（已预先入库 100 个文档）"""
        doc_count = data.summary.get("doc_count", 100)
        return f"""<ul>
<li><strong>文档规模</strong>：各知识库已<strong>预先入库 {doc_count} 个文档</strong>（小学考试题目），本次测试不执行上传与建索引。</li>
<li><strong>查询测试</strong>：使用 test-data 中的题目生成查询，对每个知识库执行相同查询，统计延迟与吞吐。</li>
<li><strong>质量评估</strong>：基于查询与 ground truth 计算 Precision@1、MRR、NDCG@10 等检索质量指标。</li>
<li><strong>成本对比</strong>：基于各云厂商公开定价估算 100 文档规模下的月度成本。</li>
</ul>"""

    def _generate_selection_recommendation_html(self, kb_results: List[Dict]) -> str:
        """生成选型建议的 HTML：什么情况下选择哪个知识库"""
        return """<p>根据时延、吞吐、检索质量与成本对比，建议按场景选型：</p>
<table>
<tr><th>场景</th><th>推荐知识库</th><th>说明</th></tr>
<tr><td><strong>成本优先、已有 RDS</strong></td><td>AWS Bedrock (Aurora PostgreSQL Serverless)</td><td>约 $44/月，完整 SQL、ACID，适合低中查询量。</td></tr>
<tr><td><strong>延迟与稳定性优先、预算充足</strong></td><td>AWS Bedrock (OpenSearch)</td><td>专为 k-NN 优化，部署简单，P95 更稳定。</td></tr>
<tr><td><strong>中文检索与质量优先</strong></td><td>阿里云百炼</td><td>中文深度优化、内置 Rerank，适合对 MRR/P@1 要求高的场景。</td></tr>
<tr><td><strong>国内部署、混合检索</strong></td><td>火山引擎 VikingDB</td><td>国内延迟低，混合检索 + Rerank 内置，适合国内业务。</td></tr>
</table>
<p><strong>简要结论</strong>：</p>
<ul>
<li>选 <strong>Aurora PG</strong>：成本敏感、需 SQL/事务、已有 AWS RDS。</li>
<li>选 <strong>OpenSearch</strong>：对 P95/P99 延迟要求高、纯向量检索、可接受较高成本。</li>
<li>选 <strong>阿里云百炼</strong>：强调中文语义与检索质量、已有阿里云。</li>
<li>选 <strong>火山引擎 VikingDB</strong>：业务在国内、需要混合检索与 Rerank。</li>
</ul>"""

    def _generate_architecture_html_comparison(self, kb_results: List[Dict]) -> str:
        """生成架构对比的HTML版本"""
        html = []

        html.append('<table>')
        html.append('<tr><th>特性</th><th>AWS OpenSearch</th><th>AWS Aurora PG</th><th>火山引擎 VikingDB</th><th>阿里云百炼</th></tr>')
        html.append('<tr><td><strong>底层技术</strong></td><td>OpenSearch + HNSW</td><td>PostgreSQL + pgvector</td><td>自研向量引擎</td><td>自研向量引擎</td></tr>')
        html.append('<tr><td><strong>索引类型</strong></td><td>HNSW</td><td>IVFFlat/HNSW</td><td>HNSW + Hybrid</td><td>混合检索</td></tr>')
        html.append('<tr><td><strong>SQL支持</strong></td><td>有限</td><td>✅ 完整</td><td>有限</td><td>有限</td></tr>')
        html.append('<tr><td><strong>ACID事务</strong></td><td>❌</td><td>✅</td><td>❌</td><td>❌</td></tr>')
        html.append('<tr><td><strong>自动扩展</strong></td><td>✅</td><td>✅</td><td>✅</td><td>✅</td></tr>')
        html.append('<tr><td><strong>部署复杂度</strong></td><td>简单</td><td>中等(需VPC)</td><td>简单</td><td>简单</td></tr>')
        html.append('<tr><td><strong>中文优化</strong></td><td>一般</td><td>一般</td><td>✅ 优化</td><td>✅ 深度优化</td></tr>')
        html.append('<tr><td><strong>混合检索</strong></td><td>支持</td><td>需自实现</td><td>✅ 原生支持</td><td>✅ 原生支持</td></tr>')
        html.append('<tr><td><strong>Rerank</strong></td><td>需自实现</td><td>需自实现</td><td>✅ 内置</td><td>✅ 内置</td></tr>')
        html.append('</table>')

        return '\n'.join(html)

    def _generate_performance_charts(self, kb_results: List[Dict]) -> str:
        """生成时延、吞吐、检索质量、成本对比图表"""
        html = []
        chart_id_prefix = "kb-chart"

        # 1. 时延对比图
        adapters = []
        p50_values = []
        p95_values = []
        for r in kb_results:
            if r.get("latency"):
                adapters.append(r.get("adapter_name", "Unknown"))
                lat = r["latency"]
                p50_values.append(lat.get("p50_ms", 0))
                p95_values.append(lat.get("p95_ms", 0))
        if adapters:
            fig = go.Figure()
            fig.add_trace(go.Bar(name='P50延迟', x=adapters, y=p50_values, marker_color='#3498db'))
            fig.add_trace(go.Bar(name='P95延迟', x=adapters, y=p95_values, marker_color='#e74c3c'))
            fig.update_layout(
                title='时延对比 (ms)',
                barmode='group',
                xaxis_title='知识库',
                yaxis_title='延迟 (ms)',
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            html.append(f'<div class="chart-container"><h4>时延对比</h4><div id="{chart_id_prefix}-latency"></div></div>')
            html.append(f'<script>Plotly.newPlot("{chart_id_prefix}-latency", {fig.to_json()});</script>')

        # 2. 吞吐对比图 (QPS)
        adapters = []
        qps_values = []
        for r in kb_results:
            if r.get("throughput"):
                adapters.append(r.get("adapter_name", "Unknown"))
                qps_values.append(r["throughput"].get("qps", 0))
        if adapters:
            fig = go.Figure(data=[go.Bar(x=adapters, y=qps_values, marker_color='#2ecc71', text=qps_values, textposition='outside')])
            fig.update_layout(
                title='吞吐对比 (QPS)',
                xaxis_title='知识库',
                yaxis_title='QPS',
                height=500,
                margin=dict(t=100, b=80, l=80, r=80)
            )
            html.append(f'<div class="chart-container"><h4>吞吐对比</h4><div id="{chart_id_prefix}-throughput"></div></div>')
            html.append(f'<script>Plotly.newPlot("{chart_id_prefix}-throughput", {fig.to_json()});</script>')

        # 3. 检索质量对比图
        adapters = []
        p1_values = []
        mrr_values = []
        ndcg_values = []
        for r in kb_results:
            if r.get("quality"):
                adapters.append(r.get("adapter_name", "Unknown"))
                qual = r["quality"]
                p1_values.append(qual.get("precision@1", 0))
                mrr_values.append(qual.get("mrr", 0))
                ndcg_values.append(qual.get("ndcg@10", 0))
        if adapters:
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Precision@1', x=adapters, y=p1_values, marker_color='#1abc9c'))
            fig.add_trace(go.Bar(name='MRR', x=adapters, y=mrr_values, marker_color='#f39c12'))
            fig.add_trace(go.Bar(name='NDCG@10', x=adapters, y=ndcg_values, marker_color='#9b59b6'))
            fig.update_layout(
                title='检索质量对比',
                barmode='group',
                xaxis_title='知识库',
                yaxis_title='得分',
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            html.append(f'<div class="chart-container"><h4>检索质量对比</h4><div id="{chart_id_prefix}-quality"></div></div>')
            html.append(f'<script>Plotly.newPlot("{chart_id_prefix}-quality", {fig.to_json()});</script>')

        # 4. 成本对比图（100 文档规模估算，统一为人民币便于对比）
        cost_names = []
        cost_values = []
        cost_map = {
            "OpenSearch": 700 * 7.2,
            "Aurora": 44 * 7.2,
            "Volcengine": 300,
            "Alibaba": 200,
        }
        for r in kb_results:
            name = r.get("adapter_name", "")
            for key, val in cost_map.items():
                if key in name:
                    cost_names.append(name)
                    cost_values.append(val)
                    break
        if cost_names:
            fig = go.Figure(data=[go.Bar(x=cost_names, y=cost_values, marker_color='#e67e22')])
            fig.update_layout(
                title='成本对比（100 文档规模，月度估算，单位：元）',
                xaxis_title='知识库',
                yaxis_title='月度成本 (元)',
                height=380
            )
            html.append(f'<div class="chart-container"><h4>成本对比</h4><div id="{chart_id_prefix}-cost"></div></div>')
            html.append(f'<script>Plotly.newPlot("{chart_id_prefix}-cost", {fig.to_json()});</script>')

        return '\n'.join(html)

    def _generate_comprehensive_kb_html_comparison(self, kb_results: List[Dict]) -> str:
        """生成知识库综合对比的HTML版本"""
        html = []

        if len(kb_results) < 2:
            return ""

        # 综合评分表
        html.append('<h3>🏆 综合评分对比</h3>')
        html.append('<table>')
        html.append('<tr><th>知识库</th><th>性能得分</th><th>质量得分</th><th>成本得分</th><th>易用性</th><th>综合评分</th><th>推荐场景</th></tr>')

        for r in kb_results:
            adapter_name = r.get("adapter_name", "")
            lat = r.get("latency", {})
            tp = r.get("throughput", {})
            qual = r.get("quality", {})

            p50 = lat.get("p50_ms", 999999)
            qps = tp.get("qps", 0)
            mrr = qual.get("mrr", 0)
            p1 = qual.get("precision@1", 0)

            perf_score = min(5, max(1, int(5 - (p50 / 500))))
            qual_score = min(5, max(1, int((mrr + p1) * 2.5)))

            if "OpenSearch" in adapter_name:
                cost_score, ease_score, scenario = 2, 5, "性能优先"
            elif "Aurora" in adapter_name:
                cost_score, ease_score, scenario = 5, 3, "成本优先"
            elif "Alibaba" in adapter_name:
                cost_score, ease_score, scenario = 4, 4, "质量优先"
            elif "Volcengine" in adapter_name:
                cost_score, ease_score, scenario = 4, 3, "国内应用"
            else:
                cost_score, ease_score, scenario = 3, 3, "通用"

            overall = int((perf_score + qual_score + cost_score + ease_score) / 4)

            perf_stars = "⭐" * perf_score
            qual_stars = "⭐" * qual_score
            cost_stars = "⭐" * cost_score
            ease_stars = "⭐" * ease_score
            overall_stars = "⭐" * overall

            html.append(f'<tr><td><strong>{adapter_name}</strong></td><td>{perf_stars}</td><td>{qual_stars}</td><td>{cost_stars}</td><td>{ease_stars}</td><td>{overall_stars}</td><td>{scenario}</td></tr>')

        html.append('</table>')

        # 质量分析
        html.append('<h3>🎯 检索质量深度分析</h3>')

        sorted_by_mrr = sorted(kb_results, key=lambda r: r.get("quality", {}).get("mrr", 0), reverse=True)
        html.append('<ol>')
        for i, r in enumerate(sorted_by_mrr, 1):
            adapter_name = r.get("adapter_name", "Unknown")
            mrr = r.get("quality", {}).get("mrr", 0)
            p1 = r.get("quality", {}).get("precision@1", 0)

            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else ""
            html.append(f'<li>{medal} <strong>{adapter_name}</strong> - MRR: {mrr:.3f}, P@1: {p1:.3f}</li>')

        html.append('</ol>')

        # 架构对比已在前文「🏗️ 架构对比」章节单独展示，此处不再重复

        return '\n'.join(html)

    def _generate_aws_bedrock_html_comparison(self, aws_results: List[Dict]) -> str:
        """生成AWS Bedrock对比的HTML版本"""
        html = []
        opensearch_result = next((r for r in aws_results if "OpenSearch" in r.get("adapter_name", "")), None)
        aurora_result = next((r for r in aws_results if "Aurora" in r.get("adapter_name", "")), None)

        if not (opensearch_result and aurora_result):
            return ""

        os_lat = opensearch_result.get("latency", {})
        au_lat = aurora_result.get("latency", {})
        os_tp = opensearch_result.get("throughput", {})
        au_tp = aurora_result.get("throughput", {})

        html.append('<p>AWS Bedrock Knowledge Base支持多种向量存储后端，本次测试对比了两种主流方案：</p>')

        html.append('<h3>性能指标详细对比</h3>')
        html.append('<table>')
        html.append('<tr><th>指标</th><th>OpenSearch Serverless</th><th>Aurora PostgreSQL Serverless</th><th>差异</th><th>赢家</th></tr>')

        # P50
        p50_diff = ((au_lat.get('p50_ms', 0) - os_lat.get('p50_ms', 0)) / os_lat.get('p50_ms', 1)) * 100
        p50_winner = "✅ Aurora" if p50_diff < 0 else "✅ OpenSearch"
        html.append(f'<tr><td><strong>P50 延迟</strong></td><td>{os_lat.get("p50_ms", 0):.2f}ms</td><td>{au_lat.get("p50_ms", 0):.2f}ms</td><td>{p50_diff:+.1f}%</td><td>{p50_winner}</td></tr>')

        # P95
        p95_diff = ((au_lat.get('p95_ms', 0) - os_lat.get('p95_ms', 0)) / os_lat.get('p95_ms', 1)) * 100
        p95_winner = "✅ Aurora" if p95_diff < 0 else "✅ OpenSearch"
        html.append(f'<tr><td><strong>P95 延迟</strong></td><td>{os_lat.get("p95_ms", 0):.2f}ms</td><td>{au_lat.get("p95_ms", 0):.2f}ms</td><td>{p95_diff:+.1f}%</td><td>{p95_winner}</td></tr>')

        # QPS
        qps_diff = ((au_tp.get('qps', 0) - os_tp.get('qps', 0)) / os_tp.get('qps', 1)) * 100
        qps_winner = "≈ 相当" if abs(qps_diff) < 5 else ("✅ Aurora" if qps_diff > 0 else "✅ OpenSearch")
        html.append(f'<tr><td><strong>QPS</strong></td><td>{os_tp.get("qps", 0):.2f}</td><td>{au_tp.get("qps", 0):.2f}</td><td>{qps_diff:+.1f}%</td><td>{qps_winner}</td></tr>')

        html.append('</table>')

        html.append('<h3>关键发现</h3>')
        html.append('<ol>')
        html.append(f'<li><strong>中位数性能 (P50)</strong>: {"Aurora PostgreSQL Serverless 表现略好" if p50_diff < 0 else "OpenSearch Serverless 表现略好"}，差异 {abs(p50_diff):.1f}%</li>')
        html.append(f'<li><strong>尾部延迟 (P95/P99)</strong>: {"Aurora PostgreSQL Serverless 更稳定" if p95_diff < 0 else "OpenSearch Serverless 更稳定"}，P95差异 {abs(p95_diff):.1f}%</li>')
        html.append(f'<li><strong>吞吐量</strong>: 两者基本相当 ({abs(qps_diff):.1f}% 差异)</li>')
        html.append('<li><strong>成本</strong>: Aurora PostgreSQL Serverless 有压倒性优势（详见成本对比章节）</li>')
        html.append('</ol>')

        return '\n'.join(html)

    def _generate_cost_html_comparison(self, kb_results: List[Dict]) -> str:
        """生成成本对比的HTML版本"""
        html = []

        html.append('<h3>📉 月度成本估算（100文档规模）</h3>')
        html.append('<table>')
        html.append('<tr><th>服务</th><th>数据量</th><th>月度成本</th><th>成本构成</th></tr>')

        opensearch_result = next((r for r in kb_results if "OpenSearch" in r.get("adapter_name", "")), None)
        aurora_result = next((r for r in kb_results if "Aurora" in r.get("adapter_name", "")), None)

        if opensearch_result:
            html.append('<tr><td><strong>AWS Bedrock (OpenSearch)</strong></td><td>0.1GB</td><td>~$700/月</td><td>4 OCU × $0.24 × 730h</td></tr>')
        if aurora_result:
            html.append('<tr><td><strong>AWS Bedrock (Aurora PG)</strong></td><td>0.1GB</td><td>~$44/月</td><td>0.5 ACU × $0.12 × 730h</td></tr>')
        if any("Volcengine" in r.get("adapter_name", "") for r in kb_results):
            html.append('<tr><td><strong>火山引擎 VikingDB</strong></td><td>0.1GB</td><td>~¥300/月</td><td>实例费 + 存储费</td></tr>')
        if any("Alibaba" in r.get("adapter_name", "") for r in kb_results):
            html.append('<tr><td><strong>阿里云百炼</strong></td><td>0.1GB</td><td>~¥200/月</td><td>按调用次数计费</td></tr>')

        html.append('</table>')

        if opensearch_result and aurora_result:
            html.append('<h3>💡 成本节省分析</h3>')
            html.append('<p>选择 <strong>Aurora PostgreSQL Serverless</strong> 相比 <strong>OpenSearch Serverless</strong>:</p>')
            html.append('<ul>')
            html.append('<li><strong>月度节省</strong>: $656/月</li>')
            html.append('<li><strong>节省比例</strong>: 93.7%</li>')
            html.append('<li><strong>年度节省</strong>: $7,872/年</li>')
            html.append('</ul>')

        html.append('<h3>🎯 选型建议</h3>')
        html.append('<h4>默认推荐: <strong>Aurora PostgreSQL Serverless v2</strong> ⭐</h4>')
        html.append('<p><strong>适用场景</strong>:</p>')
        html.append('<ul>')
        html.append('<li>✅ 成本敏感型项目</li>')
        html.append('<li>✅ 需要完整SQL能力</li>')
        html.append('<li>✅ 要求强一致性</li>')
        html.append('<li>✅ 已有RDS基础设施</li>')
        html.append('<li>✅ 低到中等查询量（&lt; 1000 QPS）</li>')
        html.append('</ul>')

        return '\n'.join(html)
    
    # ============== 记忆系统专用方法 ==============
    
    def _run_mode_label(self, run_mode: str) -> str:
        """运行模式显示文案：mock -> Mock；real -> 真实云；其他(如 simple_store) -> 本地"""
        if run_mode == "mock":
            return "Mock 模式（本地模拟）"
        if run_mode == "real":
            return "真实云环境"
        return "本地"

    def _append_memory_run_mode_table(self, lines: List[str], memory_results: List[Dict]) -> None:
        """在报告中追加记忆系统运行模式表（Mock / 真实云）"""
        lines.append("| 记忆系统 | 运行模式 |")
        lines.append("|----------|----------|")
        for r in memory_results:
            name = r.get("adapter_name", "-")
            run_mode = r.get("details", {}).get("run_mode", "unknown")
            lines.append(f"| {name} | {self._run_mode_label(run_mode)} |")
        lines.append("")

    def _generate_memory_intro(self, memory_results: List[Dict]) -> List[str]:
        """生成记忆系统介绍"""
        lines = []
        
        intro_map = {
            "AWSBedrockMemory": "**AWS Bedrock Memory** 是 Amazon Bedrock AgentCore 提供的托管记忆服务，支持短期记忆(Events)和长期记忆(Insights)。",
            "VolcengineAgentKitMemory": "**火山引擎 AgentKit Memory** 是字节跳动火山引擎提供的 Agent 记忆管理服务，支持对话记忆和长期知识积累。",
            "AlibabaBailianMemory": "**阿里云百炼长期记忆** 是阿里云百炼平台提供的记忆节点服务，支持记忆的创建、查询和管理。",
            "Mem0LocalAdapter": "**Mem0 (本地)** 是开源的记忆管理框架，支持多种向量存储后端，可作为云服务的对比基准。"
        }
        
        for r in memory_results:
            name = r.get("adapter_name", "Unknown")
            if name in intro_map:
                lines.append(f"- {intro_map[name]}")
        
        return lines
    
    def _generate_memory_architecture_comparison(self, memory_results: List[Dict]) -> List[str]:
        """生成记忆系统架构对比"""
        lines = []
        lines.append("| 记忆系统 | 存储方式 | 记忆类型 | 索引方式 | 特点 |")
        lines.append("|----------|----------|----------|----------|------|")
        
        arch_map = {
            "AWSBedrockMemory": ("托管向量存储", "Events + Insights", "向量索引", "自动提取长期记忆"),
            "VolcengineAgentKitMemory": ("火山引擎存储", "对话记忆 + 长期记忆", "向量检索", "Agent 工作流集成"),
            "AlibabaBailianMemory": ("百炼平台存储", "记忆节点", "图谱 + 向量", "支持记忆关联"),
            "Mem0LocalAdapter": ("本地向量库", "统一记忆", "Embedding检索", "开源可定制")
        }
        
        for r in memory_results:
            name = r.get("adapter_name", "Unknown")
            if name in arch_map:
                storage, mem_type, index, feature = arch_map[name]
                lines.append(f"| {name} | {storage} | {mem_type} | {index} | {feature} |")
        
        return lines
    
    def _generate_memory_test_methodology(self, data: ReportData) -> List[str]:
        """生成记忆系统测试方法说明"""
        lines = []
        memory_count = data.summary.get("memory_count", 100)
        user_count = data.summary.get("user_count", 10)
        query_count = data.summary.get("query_count", 5)

        lines.append("### 测试数据")
        lines.append("")
        lines.append(f"- **记忆条目数**: {memory_count} 条")
        lines.append(f"- **模拟用户数**: {user_count} 个")
        lines.append(f"- **记忆类型**: 用户偏好、对话记录、学习进度等")
        lines.append(f"- **测试查询数**: {query_count} 个查询语句")
        lines.append("")

        lines.append("### 测试流程")
        lines.append("")
        lines.append("1. **初始化阶段**")
        lines.append(f"   - 创建 {user_count} 个模拟用户账号")
        lines.append(f"   - 为每个用户生成随机的记忆数据")
        lines.append("")
        lines.append("2. **记忆写入测试**")
        lines.append(f"   - 批量添加 {memory_count} 条测试记忆")
        lines.append(f"   - 记录每次写入操作的响应时间")
        lines.append(f"   - 计算写入成功率")
        lines.append("")
        lines.append("3. **记忆搜索测试**")
        lines.append(f"   - 执行 {query_count} 个不同的查询语句")
        lines.append(f"   - 每个查询针对特定用户进行")
        lines.append(f"   - 记录每次搜索的响应时间和返回结果数")
        lines.append(f"   - 计算搜索成功率")
        lines.append("")
        lines.append("4. **性能指标收集**")
        lines.append(f"   - 总请求数: {memory_count} (写入) + {query_count} (搜索) = {memory_count + query_count} 次")
        lines.append(f"   - 统计所有操作的延迟分布 (P50/P95/P99)")
        lines.append(f"   - 计算吞吐量 (QPS = 总请求数 / 总耗时)")
        lines.append("")

        lines.append("### 评估维度")
        lines.append("")
        lines.append("- **延迟 (Latency)**")
        lines.append("  - P50: 50%的请求响应时间在此值以下（中位数）")
        lines.append("  - P95: 95%的请求响应时间在此值以下")
        lines.append("  - P99: 99%的请求响应时间在此值以下")
        lines.append("  - 平均值: 所有请求的平均响应时间")
        lines.append("")
        lines.append("- **吞吐 (Throughput)**")
        lines.append("  - QPS: 每秒完成的查询数 (Queries Per Second)")
        lines.append(f"  - 总请求数: 包含写入和搜索的所有操作")
        lines.append("")
        lines.append("- **可靠性 (Reliability)**")
        lines.append("  - 成功率: 成功完成的请求数 / 总请求数")
        lines.append("  - 失败原因: API超时、限流、认证失败等")
        lines.append("")
        lines.append("- **成本 (Cost)**")
        lines.append("  - 基于云服务商的计费模式估算月度成本")
        lines.append("  - 考虑因素: API调用次数、存储容量、数据传输等")

        return lines
    
    def _generate_memory_cost_table(self, memory_results: List[Dict]) -> List[str]:
        """生成记忆系统成本对比表"""
        lines = []
        lines.append("| 记忆系统 | 月度成本估算 | 计费方式 | 备注 |")
        lines.append("|----------|--------------|----------|------|")
        
        cost_map = {
            "AWSBedrockMemory": ("$50-100/月", "按记忆存储和查询计费", "支持长期记忆自动提取"),
            "VolcengineAgentKitMemory": ("¥200-400/月", "按Agent调用次数", "包含在Agent费用中"),
            "AlibabaBailianMemory": ("¥150-300/月", "按记忆节点数", "支持记忆关联查询"),
            "Mem0LocalAdapter": ("自托管成本", "服务器 + 存储", "开源免费，需自行维护")
        }
        
        for r in memory_results:
            name = r.get("adapter_name", "Unknown")
            if name in cost_map:
                cost, billing, note = cost_map[name]
                lines.append(f"| {name} | {cost} | {billing} | {note} |")
        
        lines.append("")
        lines.append("*注：成本估算基于 100 条记忆、10 个用户的测试规模，实际成本因使用量而异。*")
        
        return lines
    
    def _generate_comprehensive_memory_comparison(self, memory_results: List[Dict]) -> List[str]:
        """生成记忆系统综合对比"""
        lines = []
        
        if len(memory_results) < 2:
            return lines
        
        lines.append("")
        lines.append("### 🏆 综合评分对比")
        lines.append("")
        lines.append("| 记忆系统 | 性能得分 | 成本得分 | 易用性 | 综合评分 | 推荐场景 |")
        lines.append("|----------|----------|----------|--------|----------|----------|")
        
        for r in memory_results:
            adapter_name = r.get("adapter_name", "")
            lat = r.get("latency", {})
            tp = r.get("throughput", {})
            
            p50 = lat.get("p50_ms", 999999)
            qps = tp.get("qps", 0)
            
            # 性能评分：基于延迟
            perf_score = min(5, max(1, int(5 - (p50 / 200))))
            
            # 成本和易用性评分（基于经验值）
            if "Bedrock" in adapter_name:
                cost_score, ease_score, scenario = 3, 5, "AWS 生态"
            elif "Volcengine" in adapter_name:
                cost_score, ease_score, scenario = 4, 4, "国内中文场景"
            elif "Alibaba" in adapter_name:
                cost_score, ease_score, scenario = 4, 4, "阿里云生态"
            elif "Mem0" in adapter_name:
                cost_score, ease_score, scenario = 5, 3, "自托管/开源"
            else:
                cost_score, ease_score, scenario = 3, 3, "通用"
            
            overall = int((perf_score + cost_score + ease_score) / 3)
            
            lines.append(f"| {adapter_name} | {perf_score}/5 | {cost_score}/5 | {ease_score}/5 | {overall}/5 | {scenario} |")
        
        return lines
    
    def _generate_memory_selection_recommendation(self, memory_results: List[Dict]) -> List[str]:
        """生成记忆系统选型建议"""
        lines = []
        
        lines.append("### 🎯 AWS Bedrock Memory")
        lines.append("")
        lines.append("**适合场景**:")
        lines.append("- 使用 AWS 云服务的企业")
        lines.append("- 需要自动提取长期记忆 (Insights)")
        lines.append("- 对托管服务有强需求")
        lines.append("")
        lines.append("**优势**: 托管服务、与 Bedrock Agent 集成、自动记忆管理")
        lines.append("")
        lines.append("**劣势**: 成本相对较高、需要 AWS 账号")
        lines.append("")
        
        lines.append("### 🎯 火山引擎 AgentKit Memory")
        lines.append("")
        lines.append("**适合场景**:")
        lines.append("- 国内企业，中文应用场景")
        lines.append("- 需要与火山引擎 Agent 工作流集成")
        lines.append("- 对中文记忆检索有较高要求")
        lines.append("")
        lines.append("**优势**: 国内服务、中文优化、Agent 工作流集成")
        lines.append("")
        lines.append("**劣势**: 需要火山引擎账号、文档相对较少")
        lines.append("")
        
        lines.append("### 🎯 阿里云百炼长期记忆")
        lines.append("")
        lines.append("**适合场景**:")
        lines.append("- 使用阿里云生态的企业")
        lines.append("- 需要记忆关联和图谱能力")
        lines.append("- 国内中文场景")
        lines.append("")
        lines.append("**优势**: 阿里云生态、支持记忆关联、中文优化")
        lines.append("")
        lines.append("**劣势**: 需要阿里云账号、API 限流较严格")
        lines.append("")
        
        lines.append("### 🎯 Mem0 (本地开源)")
        lines.append("")
        lines.append("**适合场景**:")
        lines.append("- 需要完全控制数据的企业")
        lines.append("- 开发测试环境")
        lines.append("- 对成本敏感的项目")
        lines.append("")
        lines.append("**优势**: 开源免费、数据自主、高度可定制")
        lines.append("")
        lines.append("**劣势**: 需要自行维护、缺少托管服务的便利性")
        
        return lines

    # ============== 记忆系统 HTML 专用方法 ==============
    
    def _generate_memory_intro_html(self, memory_results: List[Dict]) -> str:
        """生成记忆系统介绍的HTML"""
        intro_map = {
            "Mem0LocalAdapter": ("Mem0 (本地)", "开源的记忆管理框架，支持多种向量存储后端，可作为云服务的对比基准。"),
            "AWSBedrockMemory": ("AWS Bedrock Memory", "Amazon Bedrock AgentCore 提供的托管记忆服务，支持短期记忆(Events)和长期记忆(Insights)。"),
            "VolcengineAgentKitMemory": ("火山引擎 AgentKit Memory", "字节跳动火山引擎提供的 Agent 记忆管理服务，支持对话记忆和长期知识积累。"),
            "AlibabaBailianMemory": ("阿里云百炼长期记忆", "阿里云百炼平台提供的记忆节点服务，支持记忆的创建、查询和管理。")
        }
        
        parts = ['<p>本报告对比以下 <strong>4 个记忆系统</strong>：</p><ul>']
        for r in memory_results:
            name = r.get("adapter_name", "")
            if name in intro_map:
                title, desc = intro_map[name]
                parts.append(f'<li><strong>{title}</strong>：{desc}</li>')
        parts.append('</ul>')
        return '\n'.join(parts)
    
    def _generate_memory_architecture_html_comparison(self, memory_results: List[Dict]) -> str:
        """生成记忆系统架构对比的HTML"""
        html = []
        html.append('<table>')
        html.append('<tr><th>记忆系统</th><th>存储方式</th><th>记忆类型</th><th>索引方式</th><th>特点</th></tr>')
        
        arch_map = {
            "Mem0LocalAdapter": ("本地向量库", "统一记忆", "Embedding检索", "开源可定制"),
            "AWSBedrockMemory": ("托管向量存储", "Events + Insights", "向量索引", "自动提取长期记忆"),
            "VolcengineAgentKitMemory": ("火山引擎存储", "对话记忆 + 长期记忆", "向量检索", "Agent 工作流集成"),
            "AlibabaBailianMemory": ("百炼平台存储", "记忆节点", "图谱 + 向量", "支持记忆关联")
        }
        
        for r in memory_results:
            name = r.get("adapter_name", "")
            if name in arch_map:
                storage, mem_type, index, feature = arch_map[name]
                html.append(f'<tr><td><strong>{name}</strong></td><td>{storage}</td><td>{mem_type}</td><td>{index}</td><td>{feature}</td></tr>')
        
        html.append('</table>')
        return '\n'.join(html)
    
    def _generate_memory_test_methodology_html(self, data: ReportData) -> str:
        """生成记忆系统测试方法的HTML"""
        memory_count = data.summary.get("memory_count", 100)
        user_count = data.summary.get("user_count", 10)
        query_count = data.summary.get("query_count", 5)

        return f"""<h3>测试数据</h3>
<ul>
<li><strong>记忆条目数</strong>：{memory_count} 条</li>
<li><strong>模拟用户数</strong>：{user_count} 个</li>
<li><strong>记忆类型</strong>：用户偏好、对话记录、学习进度等</li>
<li><strong>测试查询数</strong>：{query_count} 个查询语句</li>
</ul>

<h3>测试流程</h3>
<ol>
<li><strong>初始化阶段</strong>
  <ul>
    <li>创建 {user_count} 个模拟用户账号</li>
    <li>为每个用户生成随机的记忆数据</li>
  </ul>
</li>
<li><strong>记忆写入测试</strong>
  <ul>
    <li>批量添加 {memory_count} 条测试记忆</li>
    <li>记录每次写入操作的响应时间</li>
    <li>计算写入成功率</li>
  </ul>
</li>
<li><strong>记忆搜索测试</strong>
  <ul>
    <li>执行 {query_count} 个不同的查询语句</li>
    <li>每个查询针对特定用户进行</li>
    <li>记录每次搜索的响应时间和返回结果数</li>
    <li>计算搜索成功率</li>
  </ul>
</li>
<li><strong>性能指标收集</strong>
  <ul>
    <li>总请求数: {memory_count} (写入) + {query_count} (搜索) = {memory_count + query_count} 次</li>
    <li>统计所有操作的延迟分布 (P50/P95/P99)</li>
    <li>计算吞吐量 (QPS = 总请求数 / 总耗时)</li>
  </ul>
</li>
</ol>

<h3>评估维度</h3>
<ul>
<li><strong>延迟 (Latency)</strong>
  <ul>
    <li>P50: 50%的请求响应时间在此值以下（中位数）</li>
    <li>P95: 95%的请求响应时间在此值以下</li>
    <li>P99: 99%的请求响应时间在此值以下</li>
    <li>平均值: 所有请求的平均响应时间</li>
  </ul>
</li>
<li><strong>吞吐 (Throughput)</strong>
  <ul>
    <li>QPS: 每秒完成的查询数 (Queries Per Second)</li>
    <li>总请求数: 包含写入和搜索的所有操作</li>
  </ul>
</li>
<li><strong>可靠性 (Reliability)</strong>
  <ul>
    <li>成功率: 成功完成的请求数 / 总请求数</li>
    <li>失败原因: API超时、限流、认证失败等</li>
  </ul>
</li>
<li><strong>成本 (Cost)</strong>
  <ul>
    <li>基于云服务商的计费模式估算月度成本</li>
    <li>考虑因素: API调用次数、存储容量、数据传输等</li>
  </ul>
</li>
</ul>"""
    
    def _generate_memory_performance_charts(self, memory_results: List[Dict]) -> str:
        """生成记忆系统性能对比图表"""
        html = []
        chart_id_prefix = "memory-chart"

        # 1. 时延对比图
        adapters = []
        p50_values = []
        p95_values = []
        p99_values = []
        for r in memory_results:
            if r.get("latency"):
                adapters.append(r.get("adapter_name", "Unknown"))
                lat = r["latency"]
                p50_values.append(lat.get("p50_ms", 0))
                p95_values.append(lat.get("p95_ms", 0))
                p99_values.append(lat.get("p99_ms", 0))
        
        if adapters:
            fig = go.Figure()
            fig.add_trace(go.Bar(name='P50延迟', x=adapters, y=p50_values, marker_color='#3498db'))
            fig.add_trace(go.Bar(name='P95延迟', x=adapters, y=p95_values, marker_color='#e74c3c'))
            fig.add_trace(go.Bar(name='P99延迟', x=adapters, y=p99_values, marker_color='#9b59b6'))
            fig.update_layout(
                title='时延对比 (ms)',
                barmode='group',
                xaxis_title='记忆系统',
                yaxis_title='延迟 (ms)',
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            html.append(f'<div class="chart-container"><h4>时延对比</h4><div id="{chart_id_prefix}-latency"></div></div>')
            html.append(f'<script>Plotly.newPlot("{chart_id_prefix}-latency", {fig.to_json()});</script>')

        # 2. 吞吐对比图 (QPS)
        adapters = []
        qps_values = []
        for r in memory_results:
            if r.get("throughput"):
                adapters.append(r.get("adapter_name", "Unknown"))
                qps_values.append(r["throughput"].get("qps", 0))
        
        if adapters:
            fig = go.Figure(data=[go.Bar(x=adapters, y=qps_values, marker_color='#2ecc71', text=qps_values, textposition='outside')])
            fig.update_layout(
                title='吞吐对比 (QPS)',
                xaxis_title='记忆系统',
                yaxis_title='QPS',
                height=500,
                margin=dict(t=100, b=80, l=80, r=80)
            )
            html.append(f'<div class="chart-container"><h4>吞吐对比</h4><div id="{chart_id_prefix}-throughput"></div></div>')
            html.append(f'<script>Plotly.newPlot("{chart_id_prefix}-throughput", {fig.to_json()});</script>')

        # 3. 成功率对比图
        adapters = []
        success_rates = []
        for r in memory_results:
            if r.get("throughput"):
                adapters.append(r.get("adapter_name", "Unknown"))
                error_rate = r["throughput"].get("error_rate", 0)
                success_rates.append(100 - error_rate)
        
        if adapters:
            fig = go.Figure(data=[go.Bar(x=adapters, y=success_rates, marker_color='#1abc9c', text=[f"{s:.1f}%" for s in success_rates], textposition='outside')])
            fig.update_layout(
                title='成功率对比',
                xaxis_title='记忆系统',
                yaxis_title='成功率 (%)',
                height=500,
                margin=dict(t=100, b=80, l=80, r=80),
                yaxis=dict(range=[0, 105])
            )
            html.append(f'<div class="chart-container"><h4>成功率对比</h4><div id="{chart_id_prefix}-success"></div></div>')
            html.append(f'<script>Plotly.newPlot("{chart_id_prefix}-success", {fig.to_json()});</script>')

        return '\n'.join(html)
    
    def _generate_memory_run_mode_table_html(self, memory_results: List[Dict]) -> str:
        """生成记忆系统运行模式表 HTML"""
        html = []
        html.append('<table><tr><th>记忆系统</th><th>运行模式</th></tr>')
        for r in memory_results:
            name = r.get("adapter_name", "-")
            run_mode = r.get("details", {}).get("run_mode", "unknown")
            label = self._run_mode_label(run_mode)
            if run_mode == "mock":
                badge = '<span class="badge badge-info">Mock 模式（本地模拟）</span>'
            elif run_mode == "real":
                badge = '<span class="badge badge-success">真实云环境</span>'
            else:
                badge = '<span class="badge badge-info">本地</span>'
            html.append(f'<tr><td><strong>{name}</strong></td><td>{badge}</td></tr>')
        html.append('</table>')
        return '\n'.join(html)

    def _generate_memory_results_table_html(self, memory_results: List[Dict]) -> str:
        """生成记忆系统结果表格HTML"""
        html = []
        html.append('<table>')
        html.append('<tr><th>记忆系统</th><th>运行模式</th><th>P50延迟</th><th>P95延迟</th><th>P99延迟</th><th>QPS</th><th>成功率</th></tr>')
        
        for r in memory_results:
            adapter = r.get("adapter_name", "-")
            run_mode = r.get("details", {}).get("run_mode", "unknown")
            if run_mode == "mock":
                mode_badge = '<span class="badge badge-info">Mock</span>'
            elif run_mode == "real":
                mode_badge = '<span class="badge badge-success">真实云</span>'
            else:
                mode_badge = '<span class="badge badge-info">本地</span>'
            lat = r.get("latency", {})
            tp = r.get("throughput", {})
            
            p50 = f"{lat.get('p50_ms', 0):.2f}ms" if lat else "-"
            p95 = f"{lat.get('p95_ms', 0):.2f}ms" if lat else "-"
            p99 = f"{lat.get('p99_ms', 0):.2f}ms" if lat else "-"
            qps = f"{tp.get('qps', 0):.1f}" if tp else "-"
            success = f"{100 - tp.get('error_rate', 0):.1f}%" if tp else "-"
            
            html.append(f'<tr><td><strong>{adapter}</strong></td><td>{mode_badge}</td><td>{p50}</td><td>{p95}</td><td>{p99}</td><td>{qps}</td><td>{success}</td></tr>')
        
        html.append('</table>')
        return '\n'.join(html)
    
    def _generate_comprehensive_memory_html_comparison(self, memory_results: List[Dict]) -> str:
        """生成记忆系统综合对比的HTML版本"""
        html = []
        
        if len(memory_results) < 2:
            return ""
        
        html.append('<h3>🏆 综合评分对比</h3>')
        html.append('<table>')
        html.append('<tr><th>记忆系统</th><th>性能得分</th><th>成本得分</th><th>易用性</th><th>综合评分</th><th>推荐场景</th></tr>')
        
        for r in memory_results:
            adapter_name = r.get("adapter_name", "")
            lat = r.get("latency", {})
            
            p50 = lat.get("p50_ms", 999999)
            
            # 性能评分
            perf_score = min(5, max(1, int(5 - (p50 / 200))))
            
            # 成本和易用性评分
            if "Bedrock" in adapter_name:
                cost_score, ease_score, scenario = 3, 5, "AWS 生态"
            elif "Volcengine" in adapter_name:
                cost_score, ease_score, scenario = 4, 4, "国内中文场景"
            elif "Alibaba" in adapter_name:
                cost_score, ease_score, scenario = 4, 4, "阿里云生态"
            elif "Mem0" in adapter_name:
                cost_score, ease_score, scenario = 5, 3, "自托管/开源"
            else:
                cost_score, ease_score, scenario = 3, 3, "通用"
            
            overall = int((perf_score + cost_score + ease_score) / 3)
            
            html.append(f'<tr><td><strong>{adapter_name}</strong></td><td>{perf_score}/5</td><td>{cost_score}/5</td><td>{ease_score}/5</td><td>{overall}/5</td><td>{scenario}</td></tr>')
        
        html.append('</table>')
        return '\n'.join(html)
    
    def _generate_memory_selection_recommendation_html(self, memory_results: List[Dict]) -> str:
        """生成记忆系统选型建议的HTML"""
        return """<p>根据延迟、吞吐和成本对比，建议按场景选型：</p>
<table>
<tr><th>场景</th><th>推荐系统</th><th>说明</th></tr>
<tr><td><strong>AWS 生态用户</strong></td><td>AWS Bedrock Memory</td><td>托管服务，自动提取长期记忆(Insights)，与Bedrock Agent深度集成。</td></tr>
<tr><td><strong>国内中文场景</strong></td><td>火山引擎 AgentKit Memory</td><td>国内服务，中文优化，Agent工作流集成，性能优秀。</td></tr>
<tr><td><strong>阿里云生态</strong></td><td>阿里云百炼长期记忆</td><td>支持记忆关联和图谱能力，中文优化，适合阿里云用户。</td></tr>
<tr><td><strong>开发测试/成本敏感</strong></td><td>Mem0 (本地)</td><td>开源免费，数据自主，高度可定制，需自行维护。</td></tr>
</table>

<p><strong>简要结论</strong>：</p>
<ul>
<li>选 <strong>AWS Bedrock Memory</strong>：AWS 生态、需要托管服务、自动记忆管理。</li>
<li>选 <strong>火山引擎 AgentKit</strong>：国内业务、中文场景、性能要求高。</li>
<li>选 <strong>阿里云百炼</strong>：阿里云生态、需要记忆关联能力。</li>
<li>选 <strong>Mem0 本地</strong>：开发测试、数据自主、成本敏感。</li>
</ul>"""

    def _sync_to_web_reports(self, generated_files: Dict[str, str]) -> None:
        """同步报告到 web/reports 目录（用于 Railway 部署）

        Args:
            generated_files: 生成的文件路径字典
        """
        try:
            import shutil

            # 获取项目根目录的 web/reports 路径
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            web_reports_dir = project_root / "web" / "reports"

            # 如果 web/reports 目录不存在，创建它
            if not web_reports_dir.exists():
                web_reports_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"创建 web/reports 目录: {web_reports_dir}")

            # 复制每个生成的文件到 web/reports
            synced_count = 0
            for file_type, file_path in generated_files.items():
                source_file = Path(file_path)
                if source_file.exists():
                    dest_file = web_reports_dir / source_file.name
                    shutil.copy2(source_file, dest_file)
                    logger.debug(f"同步报告到 web: {source_file.name}")
                    synced_count += 1

            if synced_count > 0:
                logger.info(f"✓ 已同步 {synced_count} 个报告文件到 web/reports 目录")
                logger.info(f"  提示: 提交代码后 Railway 将显示最新报告")

        except Exception as e:
            logger.warning(f"同步报告到 web/reports 失败 (不影响报告生成): {e}")

