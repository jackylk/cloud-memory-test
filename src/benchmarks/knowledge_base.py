"""知识库基准测试套件"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..core.orchestrator import TestCase, TestType, TestResult, ConcurrencyConfig
from ..core.data_generator import TestDataGenerator
from ..core.metrics import MetricsCollector
from ..adapters.base import KnowledgeBaseAdapter


@dataclass
class KBTestConfig:
    """知识库测试配置"""
    name: str
    description: str
    data_scales: List[str] = field(default_factory=lambda: ["tiny"])
    num_queries: int = 10
    top_k: int = 5
    concurrency_levels: List[int] = field(default_factory=lambda: [1])
    include_quality_metrics: bool = True
    query_type: str = "default"  # "default" 或 "elementary"


# 预定义测试配置
KB_QUICK_TEST = KBTestConfig(
    name="KB快速测试",
    description="快速验证知识库适配器功能",
    data_scales=["tiny"],
    num_queries=5,
    top_k=5,
    concurrency_levels=[1],
    include_quality_metrics=True,
)

KB_FULL_TEST = KBTestConfig(
    name="KB完整测试",
    description="完整的知识库性能测试，包含多个数据规模",
    data_scales=["tiny", "small", "medium"],
    num_queries=20,
    top_k=5,
    concurrency_levels=[1, 5, 10],
    include_quality_metrics=True,
)

KB_STRESS_TEST = KBTestConfig(
    name="KB压力测试",
    description="知识库高并发压力测试",
    data_scales=["small"],
    num_queries=100,
    top_k=5,
    concurrency_levels=[1, 10, 50, 100],
    include_quality_metrics=False,
)


class KnowledgeBaseBenchmark:
    """知识库基准测试"""

    def __init__(
        self,
        config: KBTestConfig = KB_QUICK_TEST,
        data_generator: Optional[TestDataGenerator] = None,
    ):
        """初始化知识库基准测试

        Args:
            config: 测试配置
            data_generator: 数据生成器
        """
        self.config = config
        self.data_generator = data_generator or TestDataGenerator()
        self.metrics_collector = MetricsCollector()
        self._results: List[TestResult] = []

    def generate_test_cases(self) -> List[TestCase]:
        """生成测试用例列表"""
        test_cases = []

        for scale in self.config.data_scales:
            test_cases.append(TestCase(
                id=f"kb_{scale}",
                name=f"知识库测试 ({scale})",
                test_type=TestType.KNOWLEDGE_BASE,
                description=f"数据规模: {scale}",
                data_scale=scale,
                num_queries=self.config.num_queries,
                top_k=self.config.top_k,
            ))

        return test_cases

    async def run(
        self,
        adapter: KnowledgeBaseAdapter,
        adapter_name: str,
    ) -> List[TestResult]:
        """运行基准测试

        Args:
            adapter: 知识库适配器
            adapter_name: 适配器名称

        Returns:
            测试结果列表
        """
        from ..utils.logger import StepLogger

        step_logger = StepLogger(f"KB Benchmark: {adapter_name}")
        step_logger.start(f"运行 {self.config.name}")

        results = []

        for scale in self.config.data_scales:
            step_logger.step(f"数据规模: {scale}", "准备数据")

            # 生成测试数据
            doc_count = self._get_doc_count(scale)
            documents = self.data_generator.generate_documents(count=doc_count)
            queries_with_truth = self.data_generator.generate_queries_with_ground_truth(
                documents, queries_per_topic=2, query_type=self.config.query_type
            )

            # 初始化适配器
            await adapter.initialize()

            # 上传文档
            step_logger.step(f"上传文档", f"{len(documents)} 个")
            upload_result = await adapter.upload_documents(documents)

            # 构建索引
            step_logger.step("构建索引", "")
            await adapter.build_index()

            for concurrency in self.config.concurrency_levels:
                step_logger.step(f"查询测试", f"并发={concurrency}")

                self.metrics_collector.clear()
                self.metrics_collector.start()

                predictions = []
                ground_truth = []

                # 执行查询
                for query, relevant_ids in queries_with_truth[:self.config.num_queries]:
                    import time
                    start = time.time()
                    result = await adapter.query(query, top_k=self.config.top_k)
                    latency = (time.time() - start) * 1000

                    self.metrics_collector.record_latency("query", latency)
                    predictions.append([d.get("id", "") for d in result.documents])
                    ground_truth.append(relevant_ids)

                self.metrics_collector.stop()

                # 计算指标
                latency_metrics = self.metrics_collector.calculate_latency_metrics("latency_query")
                throughput_metrics = self.metrics_collector.calculate_throughput_metrics("latency_query")

                quality_metrics = None
                if self.config.include_quality_metrics:
                    quality_metrics = self.metrics_collector.calculate_quality_metrics(
                        predictions, ground_truth
                    )

                test_result = TestResult(
                    test_case_id=f"kb_{scale}_c{concurrency}",
                    adapter_name=adapter_name,
                    data_scale=scale,
                    concurrency=concurrency,
                    latency=latency_metrics,
                    throughput=throughput_metrics,
                    quality=quality_metrics,
                    details={
                        "doc_count": doc_count,
                        "query_count": self.config.num_queries,
                        "upload_success": upload_result.success_count,
                    }
                )
                results.append(test_result)

            # 清理
            await adapter.cleanup()

        step_logger.complete(f"完成 {len(results)} 个测试")
        self._results = results
        return results

    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        if not self._results:
            return {"error": "没有测试结果"}

        summary = {
            "benchmark_name": self.config.name,
            "total_tests": len(self._results),
            "results_by_scale": {},
        }

        for result in self._results:
            scale = result.data_scale
            if scale not in summary["results_by_scale"]:
                summary["results_by_scale"][scale] = []

            summary["results_by_scale"][scale].append({
                "concurrency": result.concurrency,
                "p50_ms": result.latency.p50,
                "p95_ms": result.latency.p95,
                "qps": result.throughput.qps,
                "quality": {
                    "precision@1": result.quality.precision_at_1 if result.quality else None,
                    "mrr": result.quality.mrr if result.quality else None,
                }
            })

        return summary

    def _get_doc_count(self, scale: str) -> int:
        """获取文档数量"""
        scales = {
            "tiny": 10,
            "small": 100,
            "medium": 1000,
            "large": 10000,
        }
        return scales.get(scale, 10)
