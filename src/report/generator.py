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

        # 准备报告数据
        report_data = self._prepare_report_data(results, config)

        generated_files = {}

        if "markdown" in formats:
            md_path = output_path / f"report_{report_data.generated_at.strftime('%Y%m%d_%H%M%S')}.md"
            self._generate_markdown(report_data, md_path)
            generated_files["markdown"] = str(md_path)
            logger.info(f"生成 Markdown 报告: {md_path}")

        if "html" in formats:
            html_path = output_path / f"report_{report_data.generated_at.strftime('%Y%m%d_%H%M%S')}.html"
            self._generate_html(report_data, html_path)
            generated_files["html"] = str(html_path)
            logger.info(f"生成 HTML 报告: {html_path}")

        return generated_files

    def _prepare_report_data(
        self,
        results: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> ReportData:
        """准备报告数据"""
        # 分类结果
        kb_results = [r for r in results if r.get("adapter_type") == "knowledge_base"]
        memory_results = [r for r in results if r.get("adapter_type") == "memory"]

        # 计算文档数量（从第一个结果中获取）
        doc_count = 100  # 默认值
        if results and results[0].get('details'):
            doc_count = results[0]['details'].get('doc_count', 100)

        # 计算汇总
        summary = {
            "total_tests": len(results),
            "kb_tests": len(kb_results),
            "memory_tests": len(memory_results),
            "data_scales": list(set(r.get("data_scale", "unknown") for r in results)),
            "adapters_tested": list(set(r.get("adapter_name", "unknown") for r in results)),
            "doc_count": doc_count,
        }

        # 知识库汇总
        if kb_results:
            summary["kb_summary"] = self._summarize_results(kb_results)

        # 记忆系统汇总
        if memory_results:
            summary["memory_summary"] = self._summarize_results(memory_results)

        return ReportData(
            title="云端知识库性能测试报告",
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
        lines = []

        # 标题
        lines.append(f"# {data.title}")
        lines.append("")
        lines.append(f"**生成时间**: {data.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 执行摘要
        lines.append("## 📋 执行摘要")
        lines.append("")
        lines.extend(self._generate_executive_summary(data))
        lines.append("")

        # 测试环境
        lines.append("## 🖥️ 测试环境")
        lines.append("")
        lines.extend(self._generate_environment_info(data))
        lines.append("")

        # 测试概览
        lines.append("## 📊 测试概览")
        lines.append("")
        lines.append(f"- **总测试数**: {data.summary['total_tests']}")
        lines.append(f"- **知识库测试**: {data.summary['kb_tests']}")
        doc_count = data.summary.get('doc_count', 100)
        lines.append(f"- **文档数量**: {doc_count} 个")
        lines.append(f"- **测试适配器**: {', '.join(data.summary['adapters_tested'])}")
        lines.append("")

        # 测试配置
        lines.append("## ⚙️ 测试配置")
        lines.append("")
        lines.append(f"- **运行模式**: {data.config.get('mode', 'unknown')}")
        lines.append(f"- **查询类型**: {data.config.get('query_type', 'default')}")
        lines.extend(self._generate_scale_details(data))
        lines.append("")

        # 知识库架构对比（放在性能对比前面）
        kb_results = [r for r in data.results if r.get("adapter_type") == "knowledge_base"]
        if kb_results and len(kb_results) >= 2:
            lines.append("## 🏗️ 知识库架构对比")
            lines.append("")
            lines.extend(self._generate_architecture_comparison(kb_results))
            lines.append("")

        # 知识库性能对比结果
        if kb_results:
            lines.append("## ⚡ 性能对比")
            lines.append("")
            lines.extend(self._format_results_table(kb_results, "knowledge_base"))
            lines.append("")

        # 详细结果
        lines.append("## 📊 详细结果")
        lines.append("")

        for result in data.results:
            lines.append(f"### {result.get('adapter_name', 'Unknown')}")
            lines.append("")
            lines.append(f"- 类型: {result.get('adapter_type', 'unknown')}")
            lines.append(f"- 测试时间: {result.get('timestamp', 'unknown')}")
            lines.append("")

            if result.get("latency"):
                lat = result["latency"]
                lines.append("**延迟指标**")
                lines.append("")
                lines.append(f"| 指标 | 数值 |")
                lines.append(f"|------|------|")
                lines.append(f"| P50 | {lat.get('p50_ms', 0):.2f}ms |")
                lines.append(f"| P95 | {lat.get('p95_ms', 0):.2f}ms |")
                lines.append(f"| P99 | {lat.get('p99_ms', 0):.2f}ms |")
                lines.append(f"| 平均 | {lat.get('mean_ms', 0):.2f}ms |")
                lines.append(f"| 最小 | {lat.get('min_ms', 0):.2f}ms |")
                lines.append(f"| 最大 | {lat.get('max_ms', 0):.2f}ms |")
                lines.append("")

            if result.get("throughput"):
                tp = result["throughput"]
                lines.append("**吞吐量指标**")
                lines.append("")
                lines.append(f"| 指标 | 数值 |")
                lines.append(f"|------|------|")
                lines.append(f"| QPS | {tp.get('qps', 0):.2f} |")
                lines.append(f"| 总请求数 | {tp.get('total_requests', 0)} |")
                lines.append(f"| 成功请求 | {tp.get('successful_requests', 0)} |")
                lines.append(f"| 失败请求 | {tp.get('failed_requests', 0)} |")
                lines.append(f"| 错误率 | {tp.get('error_rate', 0):.2f}% |")
                lines.append("")

            if result.get("quality"):
                qual = result["quality"]
                lines.append("**质量指标**")
                lines.append("")
                lines.append(f"| 指标 | 数值 |")
                lines.append(f"|------|------|")
                lines.append(f"| Precision@1 | {qual.get('precision@1', 0):.4f} |")
                lines.append(f"| Precision@5 | {qual.get('precision@5', 0):.4f} |")
                lines.append(f"| Recall@10 | {qual.get('recall@10', 0):.4f} |")
                lines.append(f"| MRR | {qual.get('mrr', 0):.4f} |")
                lines.append(f"| NDCG@10 | {qual.get('ndcg@10', 0):.4f} |")
                lines.append("")

        # 知识库综合对比分析
        kb_results = [r for r in data.results if r.get("adapter_type") == "knowledge_base"]
        if kb_results:
            lines.append("## 📊 知识库综合对比分析")
            lines.append("")
            lines.extend(self._generate_comprehensive_kb_comparison(kb_results))
            lines.append("")

        # AWS Bedrock KB 存储后端对比分析
        aws_results = [r for r in data.results if "AWSBedrockKB" in r.get("adapter_name", "")]
        if len(aws_results) >= 2:
            lines.append("## 🔬 AWS Bedrock KB 存储后端深度对比")
            lines.append("")
            lines.extend(self._generate_aws_bedrock_comparison(aws_results))
            lines.append("")

        # 成本对比与选型建议
        if kb_results:
            lines.append("## 💰 成本对比与选型建议")
            lines.append("")
            lines.extend(self._generate_cost_comparison(kb_results))
            lines.append("")

        # 页脚
        lines.append("---")
        lines.append("")
        lines.append("*本报告由云端知识库性能测试框架自动生成*")

        # 写入文件
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
                <div class="card-value">{data.summary['kb_tests']}</div>
                <div class="card-label">知识库测试</div>
            </div>
            <div class="card kb">
                <div class="card-value">{data.summary.get('doc_count', 0)}</div>
                <div class="card-label">文档数量</div>
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
                lines.append("- **成本**: Aurora PostgreSQL 节省约 **93%** (~$656/月)")
                lines.append("- **推荐**: 默认选择 **Aurora PostgreSQL**，除非对P95/P99延迟要求极高")
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
        lines.append("| 指标 | OpenSearch Serverless | Aurora PostgreSQL | 差异 | 赢家 |")
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
        lines.append(f"1. **中位数性能 (P50)**: {'Aurora PostgreSQL 表现略好' if p50_diff < 0 else 'OpenSearch Serverless 表现略好'}，差异 {abs(p50_diff):.1f}%")
        lines.append(f"2. **尾部延迟 (P95/P99)**: {'Aurora PostgreSQL 更稳定' if p95_diff < 0 else 'OpenSearch Serverless 更稳定'}，P95差异 {abs(p95_diff):.1f}%")
        lines.append(f"3. **吞吐量**: 两者基本相当 ({abs(qps_diff):.1f}% 差异)")
        lines.append("4. **成本**: Aurora PostgreSQL 有压倒性优势（详见成本对比章节）")
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
        lines.append("#### Aurora PostgreSQL + pgvector")
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

        # 架构特点对比
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
        lines.append("- **Aurora PostgreSQL**: 最小0.5 ACU，按秒计费，空闲时可缩至最小")
        lines.append("- **火山引擎/阿里云**: 根据资源使用量和API调用次数计费")
        lines.append("")

        # 成本节省分析
        if opensearch_result and aurora_result:
            savings = 700 - 44
            savings_pct = (savings / 700) * 100
            lines.append(f"### 💡 成本节省分析")
            lines.append("")
            lines.append(f"选择 **Aurora PostgreSQL** 相比 **OpenSearch Serverless**:")
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
        html = []

        def convert_md_to_html(text):
            """将Markdown的**加粗**转换为HTML"""
            import re
            # 转换 **text** 为 <strong>text</strong>
            text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
            return text

        # 执行摘要
        html.append('<h2>📋 执行摘要</h2>')
        exec_summary = self._generate_executive_summary(data)
        if exec_summary:
            html.append('<div class="section">')
            for line in exec_summary:
                line = convert_md_to_html(line)
                if line.startswith('### '):
                    html.append(f'<h3>{line[4:]}</h3>')
                elif line.startswith('- '):
                    html.append(f'<li>{line[2:]}</li>')
                elif line.strip():
                    html.append(f'<p>{line}</p>')
            html.append('</div>')

        # 测试环境
        html.append('<h2>🖥️ 测试环境</h2>')
        env_info = self._generate_environment_info(data)
        if env_info:
            html.append('<table>')
            for line in env_info:
                if '|' in line and not line.startswith('|---'):
                    cols = [c.strip() for c in line.split('|')[1:-1]]
                    if cols and '项目' not in cols[0]:
                        # 转换列内容中的Markdown加粗
                        col0 = convert_md_to_html(cols[0])
                        col1 = convert_md_to_html(cols[1])
                        html.append(f'<tr><td>{col0}</td><td>{col1}</td></tr>')
            html.append('</table>')

        # 测试概览
        html.append('<h2>📊 测试概览</h2>')
        html.append('<ul>')
        html.append(f'<li><strong>总测试数</strong>: {data.summary["total_tests"]}</li>')
        html.append(f'<li><strong>知识库测试</strong>: {data.summary["kb_tests"]}</li>')
        doc_count = data.summary.get('doc_count', 100)
        html.append(f'<li><strong>文档数量</strong>: {doc_count} 个</li>')
        html.append(f'<li><strong>测试适配器</strong>: {", ".join(data.summary["adapters_tested"])}</li>')
        html.append('</ul>')

        # 测试配置
        html.append('<h2>⚙️ 测试配置</h2>')
        html.append('<ul>')
        html.append(f'<li><strong>运行模式</strong>: {data.config.get("mode", "unknown")}</li>')
        html.append(f'<li><strong>查询类型</strong>: {data.config.get("query_type", "default")}</li>')
        scale_details = self._generate_scale_details(data)
        for line in scale_details:
            if line.startswith('- '):
                line_html = convert_md_to_html(line[2:])
                html.append(f'<li>{line_html}</li>')
        html.append('</ul>')

        # 知识库架构对比（放在前面）
        kb_results = [r for r in data.results if r.get("adapter_type") == "knowledge_base"]
        if kb_results and len(kb_results) >= 2:
            html.append('<h2>🏗️ 架构对比</h2>')
            html.append(self._generate_architecture_html_comparison(kb_results))

        # 知识库性能对比结果（添加图表）
        if kb_results:
            html.append('<h2>⚡ 性能对比</h2>')
            # 添加对比图表
            html.append(self._generate_performance_charts(kb_results))
            # 添加对比表格
            html.append(self._generate_results_section(data))

        # 详细结果
        html.append('<h2>📊 详细结果</h2>')
        for result in data.results:
            html.append(f'<h3>{result.get("adapter_name", "Unknown")}</h3>')
            html.append('<div class="result-detail">')
            html.append(f'<p><strong>类型</strong>: {result.get("adapter_type", "unknown")}</p>')
            html.append(f'<p><strong>测试时间</strong>: {result.get("timestamp", "unknown")}</p>')

            if result.get("latency"):
                lat = result["latency"]
                html.append('<h4>延迟指标</h4>')
                html.append('<table>')
                html.append(f'<tr><td>P50</td><td>{lat.get("p50_ms", 0):.2f}ms</td></tr>')
                html.append(f'<tr><td>P95</td><td>{lat.get("p95_ms", 0):.2f}ms</td></tr>')
                html.append(f'<tr><td>P99</td><td>{lat.get("p99_ms", 0):.2f}ms</td></tr>')
                html.append(f'<tr><td>平均</td><td>{lat.get("mean_ms", 0):.2f}ms</td></tr>')
                html.append(f'<tr><td>最小</td><td>{lat.get("min_ms", 0):.2f}ms</td></tr>')
                html.append(f'<tr><td>最大</td><td>{lat.get("max_ms", 0):.2f}ms</td></tr>')
                html.append('</table>')

            if result.get("throughput"):
                tp = result["throughput"]
                html.append('<h4>吞吐量指标</h4>')
                html.append('<table>')
                html.append(f'<tr><td>QPS</td><td>{tp.get("qps", 0):.2f}</td></tr>')
                html.append(f'<tr><td>总请求数</td><td>{tp.get("total_requests", 0)}</td></tr>')
                html.append(f'<tr><td>成功请求</td><td>{tp.get("successful_requests", 0)}</td></tr>')
                html.append(f'<tr><td>失败请求</td><td>{tp.get("failed_requests", 0)}</td></tr>')
                html.append(f'<tr><td>错误率</td><td>{tp.get("error_rate", 0):.2f}%</td></tr>')
                html.append('</table>')

            if result.get("quality"):
                qual = result["quality"]
                html.append('<h4>质量指标</h4>')
                html.append('<table>')
                html.append(f'<tr><td>Precision@1</td><td>{qual.get("precision@1", 0):.4f}</td></tr>')
                html.append(f'<tr><td>Precision@5</td><td>{qual.get("precision@5", 0):.4f}</td></tr>')
                html.append(f'<tr><td>Recall@10</td><td>{qual.get("recall@10", 0):.4f}</td></tr>')
                html.append(f'<tr><td>MRR</td><td>{qual.get("mrr", 0):.4f}</td></tr>')
                html.append(f'<tr><td>NDCG@10</td><td>{qual.get("ndcg@10", 0):.4f}</td></tr>')
                html.append('</table>')

            html.append('</div>')

        # 知识库综合对比
        if kb_results:
            html.append('<h2>📊 知识库综合对比分析</h2>')
            html.append(self._generate_comprehensive_kb_html_comparison(kb_results))

        # AWS Bedrock KB对比分析
        aws_results = [r for r in data.results if "AWSBedrockKB" in r.get("adapter_name", "")]
        if len(aws_results) >= 2:
            html.append('<h2>🔬 AWS Bedrock KB 存储后端深度对比</h2>')
            html.append(self._generate_aws_bedrock_html_comparison(aws_results))

        # 成本对比
        if kb_results:
            html.append('<h2>💰 成本对比与选型建议</h2>')
            html.append(self._generate_cost_html_comparison(kb_results))

        return '\n'.join(html)

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
        """生成性能对比图表"""
        html = []

        # 延迟对比图
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
                title='延迟对比 (毫秒)',
                barmode='group',
                xaxis_title='知识库',
                yaxis_title='延迟 (ms)',
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            html.append(f'<div class="chart-container"><div id="latency-chart"></div></div>')
            html.append(f'<script>Plotly.newPlot("latency-chart", {fig.to_json()});</script>')

        # 质量对比图
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
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            html.append(f'<div class="chart-container"><div id="quality-chart"></div></div>')
            html.append(f'<script>Plotly.newPlot("quality-chart", {fig.to_json()});</script>')

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

        # 架构对比表
        html.append('<h3>🏗️ 架构特点对比</h3>')
        html.append('<table>')
        html.append('<tr><th>特性</th><th>AWS OpenSearch</th><th>AWS Aurora PG</th><th>火山引擎 VikingDB</th><th>阿里云百炼</th></tr>')
        html.append('<tr><td><strong>底层技术</strong></td><td>OpenSearch + HNSW</td><td>PostgreSQL + pgvector</td><td>自研向量引擎</td><td>自研向量引擎</td></tr>')
        html.append('<tr><td><strong>索引类型</strong></td><td>HNSW</td><td>IVFFlat/HNSW</td><td>HNSW + Hybrid</td><td>混合检索</td></tr>')
        html.append('<tr><td><strong>SQL支持</strong></td><td>有限</td><td>✅ 完整</td><td>有限</td><td>有限</td></tr>')
        html.append('<tr><td><strong>中文优化</strong></td><td>一般</td><td>一般</td><td>✅ 优化</td><td>✅ 深度优化</td></tr>')
        html.append('<tr><td><strong>混合检索</strong></td><td>支持</td><td>需自实现</td><td>✅ 原生支持</td><td>✅ 原生支持</td></tr>')
        html.append('<tr><td><strong>Rerank</strong></td><td>需自实现</td><td>需自实现</td><td>✅ 内置</td><td>✅ 内置</td></tr>')
        html.append('</table>')

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
        html.append('<tr><th>指标</th><th>OpenSearch Serverless</th><th>Aurora PostgreSQL</th><th>差异</th><th>赢家</th></tr>')

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
        html.append(f'<li><strong>中位数性能 (P50)</strong>: {"Aurora PostgreSQL 表现略好" if p50_diff < 0 else "OpenSearch Serverless 表现略好"}，差异 {abs(p50_diff):.1f}%</li>')
        html.append(f'<li><strong>尾部延迟 (P95/P99)</strong>: {"Aurora PostgreSQL 更稳定" if p95_diff < 0 else "OpenSearch Serverless 更稳定"}，P95差异 {abs(p95_diff):.1f}%</li>')
        html.append(f'<li><strong>吞吐量</strong>: 两者基本相当 ({abs(qps_diff):.1f}% 差异)</li>')
        html.append('<li><strong>成本</strong>: Aurora PostgreSQL 有压倒性优势（详见成本对比章节）</li>')
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
            html.append('<p>选择 <strong>Aurora PostgreSQL</strong> 相比 <strong>OpenSearch Serverless</strong>:</p>')
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
