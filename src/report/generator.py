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

        # 保存原始数据
        json_path = output_path / f"report_{report_data.generated_at.strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": report_data.generated_at.isoformat(),
                "config": config,
                "results": results,
                "summary": report_data.summary
            }, f, ensure_ascii=False, indent=2)
        generated_files["json"] = str(json_path)

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

        # 计算汇总
        summary = {
            "total_tests": len(results),
            "kb_tests": len(kb_results),
            "memory_tests": len(memory_results),
            "data_scales": list(set(r.get("data_scale", "unknown") for r in results)),
            "adapters_tested": list(set(r.get("adapter_name", "unknown") for r in results)),
        }

        # 知识库汇总
        if kb_results:
            summary["kb_summary"] = self._summarize_results(kb_results)

        # 记忆系统汇总
        if memory_results:
            summary["memory_summary"] = self._summarize_results(memory_results)

        return ReportData(
            title="云端知识库和记忆系统性能测试报告",
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

        # 测试概览
        lines.append("## 测试概览")
        lines.append("")
        lines.append(f"- 总测试数: {data.summary['total_tests']}")
        lines.append(f"- 知识库测试: {data.summary['kb_tests']}")
        lines.append(f"- 记忆系统测试: {data.summary['memory_tests']}")
        lines.append(f"- 数据规模: {', '.join(data.summary['data_scales'])}")
        lines.append(f"- 测试适配器: {', '.join(data.summary['adapters_tested'])}")
        lines.append("")

        # 配置信息
        lines.append("## 测试配置")
        lines.append("")
        lines.append(f"- 运行模式: {data.config.get('mode', 'unknown')}")
        lines.append(f"- 数据规模: {data.config.get('scale', 'unknown')}")
        lines.append("")

        # 知识库测试结果
        kb_results = [r for r in data.results if r.get("adapter_type") == "knowledge_base"]
        if kb_results:
            lines.append("## 知识库测试结果")
            lines.append("")
            lines.extend(self._format_results_table(kb_results, "knowledge_base"))
            lines.append("")

        # 记忆系统测试结果
        memory_results = [r for r in data.results if r.get("adapter_type") == "memory"]
        if memory_results:
            lines.append("## 记忆系统测试结果")
            lines.append("")
            lines.extend(self._format_results_table(memory_results, "memory"))
            lines.append("")

        # 详细结果
        lines.append("## 详细结果")
        lines.append("")

        for result in data.results:
            lines.append(f"### {result.get('adapter_name', 'Unknown')}")
            lines.append("")
            lines.append(f"- 类型: {result.get('adapter_type', 'unknown')}")
            lines.append(f"- 数据规模: {result.get('data_scale', 'unknown')}")
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

        # 页脚
        lines.append("---")
        lines.append("")
        lines.append("*本报告由云端知识库和记忆系统性能测试框架自动生成*")

        # 写入文件
        output_path.write_text("\n".join(lines), encoding="utf-8")

    def _format_results_table(self, results: List[Dict], result_type: str) -> List[str]:
        """格式化结果表格"""
        lines = []

        if result_type == "knowledge_base":
            lines.append("| 适配器 | 数据规模 | P50延迟 | P95延迟 | QPS | P@1 | MRR |")
            lines.append("|--------|----------|---------|---------|-----|-----|-----|")

            for r in results:
                adapter = r.get("adapter_name", "-")
                scale = r.get("data_scale", "-")
                lat = r.get("latency", {})
                tp = r.get("throughput", {})
                qual = r.get("quality", {})

                p50 = f"{lat.get('p50_ms', 0):.2f}ms" if lat else "-"
                p95 = f"{lat.get('p95_ms', 0):.2f}ms" if lat else "-"
                qps = f"{tp.get('qps', 0):.1f}" if tp else "-"
                p1 = f"{qual.get('precision@1', 0):.3f}" if qual else "-"
                mrr = f"{qual.get('mrr', 0):.3f}" if qual else "-"

                lines.append(f"| {adapter} | {scale} | {p50} | {p95} | {qps} | {p1} | {mrr} |")

        elif result_type == "memory":
            lines.append("| 适配器 | 数据规模 | P50延迟 | P95延迟 | QPS | 成功率 |")
            lines.append("|--------|----------|---------|---------|-----|--------|")

            for r in results:
                adapter = r.get("adapter_name", "-")
                scale = r.get("data_scale", "-")
                lat = r.get("latency", {})
                tp = r.get("throughput", {})

                p50 = f"{lat.get('p50_ms', 0):.2f}ms" if lat else "-"
                p95 = f"{lat.get('p95_ms', 0):.2f}ms" if lat else "-"
                qps = f"{tp.get('qps', 0):.1f}" if tp else "-"
                success = f"{100 - tp.get('error_rate', 0):.1f}%" if tp else "-"

                lines.append(f"| {adapter} | {scale} | {p50} | {p95} | {qps} | {success} |")

        return lines

    def _generate_html(self, data: ReportData, output_path: Path):
        """生成 HTML 报告（含图表）"""
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
            <div class="card memory">
                <div class="card-value">{data.summary['memory_tests']}</div>
                <div class="card-label">记忆系统测试</div>
            </div>
        </div>

        {self._generate_results_section(data)}

        <h2>性能对比图表</h2>
        {charts}

        <div class="footer">
            本报告由云端知识库和记忆系统性能测试框架自动生成
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
            html += "<tr><th>适配器</th><th>数据规模</th><th>P50延迟</th><th>P95延迟</th><th>QPS</th><th>P@1</th><th>MRR</th></tr>"
            for r in kb_results:
                lat = r.get("latency", {})
                tp = r.get("throughput", {})
                qual = r.get("quality", {})
                p1_val = f"{qual.get('precision@1', 0):.3f}" if qual else "-"
                mrr_val = f"{qual.get('mrr', 0):.3f}" if qual else "-"
                html += f"""<tr>
                    <td>{r.get('adapter_name', '-')}</td>
                    <td>{r.get('data_scale', '-')}</td>
                    <td>{lat.get('p50_ms', 0):.2f}ms</td>
                    <td>{lat.get('p95_ms', 0):.2f}ms</td>
                    <td>{tp.get('qps', 0):.1f}</td>
                    <td>{p1_val}</td>
                    <td>{mrr_val}</td>
                </tr>"""
            html += "</table>"

        memory_results = [r for r in data.results if r.get("adapter_type") == "memory"]
        if memory_results:
            html += "<h2>记忆系统测试结果</h2>"
            html += "<table>"
            html += "<tr><th>适配器</th><th>数据规模</th><th>P50延迟</th><th>P95延迟</th><th>QPS</th><th>成功率</th></tr>"
            for r in memory_results:
                lat = r.get("latency", {})
                tp = r.get("throughput", {})
                html += f"""<tr>
                    <td>{r.get('adapter_name', '-')}</td>
                    <td>{r.get('data_scale', '-')}</td>
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
