"""记忆系统基准测试套件"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from ..core.orchestrator import TestCase, TestType, TestResult, ConcurrencyConfig
from ..core.data_generator import TestDataGenerator
from ..core.metrics import MetricsCollector
from ..adapters.base import MemoryAdapter


@dataclass
class MemoryTestConfig:
    """记忆系统测试配置"""
    name: str
    description: str
    data_scales: List[str] = field(default_factory=lambda: ["tiny"])
    num_users: int = 10
    num_queries: int = 10
    top_k: int = 5
    concurrency_levels: List[int] = field(default_factory=lambda: [1])
    test_update: bool = False
    test_delete: bool = False


# 预定义测试配置
MEMORY_QUICK_TEST = MemoryTestConfig(
    name="Memory快速测试",
    description="快速验证记忆系统适配器功能",
    data_scales=["tiny"],
    num_users=5,
    num_queries=5,
    top_k=5,
    concurrency_levels=[1],
)

MEMORY_FULL_TEST = MemoryTestConfig(
    name="Memory完整测试",
    description="完整的记忆系统性能测试",
    data_scales=["tiny", "small", "medium"],
    num_users=10,
    num_queries=20,
    top_k=5,
    concurrency_levels=[1, 5, 10],
    test_update=True,
    test_delete=True,
)

MEMORY_STRESS_TEST = MemoryTestConfig(
    name="Memory压力测试",
    description="记忆系统高并发压力测试",
    data_scales=["small"],
    num_users=50,
    num_queries=100,
    top_k=5,
    concurrency_levels=[1, 10, 50, 100],
)


class MemoryBenchmark:
    """记忆系统基准测试"""

    def __init__(
        self,
        config: MemoryTestConfig = MEMORY_QUICK_TEST,
        data_generator: Optional[TestDataGenerator] = None,
    ):
        """初始化记忆系统基准测试

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
                id=f"memory_{scale}",
                name=f"记忆系统测试 ({scale})",
                test_type=TestType.MEMORY,
                description=f"数据规模: {scale}",
                data_scale=scale,
                num_queries=self.config.num_queries,
                top_k=self.config.top_k,
            ))

        return test_cases

    async def run(
        self,
        adapter: MemoryAdapter,
        adapter_name: str,
    ) -> List[TestResult]:
        """运行基准测试

        Args:
            adapter: 记忆系统适配器
            adapter_name: 适配器名称

        Returns:
            测试结果列表
        """
        from ..utils.logger import StepLogger

        step_logger = StepLogger(f"Memory Benchmark: {adapter_name}")
        step_logger.start(f"运行 {self.config.name}")

        results = []

        for scale in self.config.data_scales:
            step_logger.step(f"数据规模: {scale}", "准备数据")

            # 生成测试数据
            memory_count = self._get_memory_count(scale)
            memories = self.data_generator.generate_memories(
                count=memory_count,
                num_users=self.config.num_users,
            )
            queries = self.data_generator.generate_queries(self.config.num_queries)

            # 初始化适配器
            await adapter.initialize()

            # 添加记忆
            step_logger.step("添加记忆", f"{len(memories)} 条")
            add_start = time.time()
            add_results = await adapter.add_memories_batch(memories)
            add_time = (time.time() - add_start) * 1000
            add_success = sum(1 for r in add_results if r.success)

            # 获取用户ID列表
            user_ids = list(set(m.user_id for m in memories))

            for concurrency in self.config.concurrency_levels:
                step_logger.step(f"搜索测试", f"并发={concurrency}")

                self.metrics_collector.clear()
                self.metrics_collector.start()

                # 执行搜索
                for i, query in enumerate(queries):
                    user_id = user_ids[i % len(user_ids)]
                    start = time.time()
                    await adapter.search_memory(query, user_id, top_k=self.config.top_k)
                    latency = (time.time() - start) * 1000
                    self.metrics_collector.record_latency("search", latency)

                self.metrics_collector.stop()

                # 计算指标
                latency_metrics = self.metrics_collector.calculate_latency_metrics("latency_search")
                throughput_metrics = self.metrics_collector.calculate_throughput_metrics("latency_search")

                test_result = TestResult(
                    test_case_id=f"memory_{scale}_c{concurrency}",
                    adapter_name=adapter_name,
                    data_scale=scale,
                    concurrency=concurrency,
                    latency=latency_metrics,
                    throughput=throughput_metrics,
                    details={
                        "memory_count": memory_count,
                        "user_count": self.config.num_users,
                        "query_count": self.config.num_queries,
                        "add_success": add_success,
                        "add_time_ms": add_time,
                    }
                )
                results.append(test_result)

            # 测试更新操作
            if self.config.test_update and add_results:
                step_logger.step("更新测试", "")
                self.metrics_collector.clear()
                self.metrics_collector.start()

                for i, add_result in enumerate(add_results[:10]):
                    if add_result.success and add_result.memory_id:
                        start = time.time()
                        await adapter.update_memory(
                            add_result.memory_id,
                            f"更新的记忆内容 {i}"
                        )
                        latency = (time.time() - start) * 1000
                        self.metrics_collector.record_latency("update", latency)

                self.metrics_collector.stop()

            # 测试删除操作
            if self.config.test_delete and add_results:
                step_logger.step("删除测试", "")
                self.metrics_collector.clear()
                self.metrics_collector.start()

                for add_result in add_results[:5]:
                    if add_result.success and add_result.memory_id:
                        start = time.time()
                        await adapter.delete_memory(add_result.memory_id)
                        latency = (time.time() - start) * 1000
                        self.metrics_collector.record_latency("delete", latency)

                self.metrics_collector.stop()

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
                "success_rate": (
                    result.throughput.successful_requests /
                    result.throughput.total_requests * 100
                    if result.throughput.total_requests > 0 else 0
                ),
            })

        return summary

    def _get_memory_count(self, scale: str) -> int:
        """获取记忆数量"""
        scales = {
            "tiny": 20,
            "small": 200,
            "medium": 2000,
            "large": 20000,
        }
        return scales.get(scale, 20)
