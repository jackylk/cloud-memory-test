"""测试编排器模块 - 管理测试执行、并发和结果聚合"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Union
from enum import Enum
from loguru import logger

from ..adapters.base import (
    KnowledgeBaseAdapter,
    MemoryAdapter,
    Document,
    Memory,
)
from .metrics import MetricsCollector, LatencyMetrics, ThroughputMetrics, QualityMetrics
from .data_generator import TestDataGenerator
from ..utils.rate_limiter import RateLimiter, get_service_rate_limiter
from ..utils.logger import StepLogger


class TestType(Enum):
    """测试类型"""
    KNOWLEDGE_BASE = "knowledge_base"
    MEMORY = "memory"


class TestPhase(Enum):
    """测试阶段"""
    UPLOAD = "upload"
    INDEX = "index"
    QUERY = "query"
    SEARCH = "search"
    ADD = "add"


@dataclass
class TestCase:
    """测试用例"""
    id: str
    name: str
    test_type: TestType
    description: str = ""
    data_scale: str = "tiny"
    num_queries: int = 10
    top_k: int = 5
    filters: Optional[Dict] = None


@dataclass
class ConcurrencyConfig:
    """并发配置"""
    concurrency: int = 1
    duration_seconds: int = 60
    warmup_seconds: int = 5
    ramp_up_seconds: int = 5


@dataclass
class TestResult:
    """单次测试结果"""
    test_case_id: str
    adapter_name: str
    data_scale: str
    concurrency: int
    latency: LatencyMetrics
    throughput: ThroughputMetrics
    quality: Optional[QualityMetrics] = None
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkSuiteResult:
    """基准测试套件结果"""
    suite_name: str
    results: List[TestResult] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class TestOrchestrator:
    """测试编排器

    负责：
    - 协调多个适配器的测试执行
    - 管理并发测试
    - 收集和聚合测试结果
    - 支持阶梯式并发测试
    """

    def __init__(
        self,
        data_generator: Optional[TestDataGenerator] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """初始化测试编排器

        Args:
            data_generator: 测试数据生成器
            rate_limiter: 限流器
        """
        self.data_generator = data_generator or TestDataGenerator()
        self.rate_limiter = rate_limiter
        self.metrics_collector = MetricsCollector()
        self.step_logger = StepLogger("TestOrchestrator")

        self._adapters: Dict[str, Union[KnowledgeBaseAdapter, MemoryAdapter]] = {}
        self._results: List[TestResult] = []

    def register_adapter(
        self,
        name: str,
        adapter: Union[KnowledgeBaseAdapter, MemoryAdapter]
    ):
        """注册适配器

        Args:
            name: 适配器名称
            adapter: 适配器实例
        """
        self._adapters[name] = adapter
        logger.debug(f"注册适配器: {name}")

    async def run_benchmark_suite(
        self,
        suite_name: str,
        adapter_names: List[str],
        test_cases: List[TestCase],
        concurrency_levels: List[int] = [1],
    ) -> BenchmarkSuiteResult:
        """运行完整的基准测试套件

        Args:
            suite_name: 套件名称
            adapter_names: 要测试的适配器名称列表
            test_cases: 测试用例列表
            concurrency_levels: 并发级别列表

        Returns:
            测试套件结果
        """
        suite_result = BenchmarkSuiteResult(
            suite_name=suite_name,
            start_time=datetime.now(),
        )

        self.step_logger.start(f"运行基准测试套件: {suite_name}")

        total_tests = len(adapter_names) * len(test_cases) * len(concurrency_levels)
        current_test = 0

        for adapter_name in adapter_names:
            if adapter_name not in self._adapters:
                logger.warning(f"适配器 {adapter_name} 未注册，跳过")
                continue

            adapter = self._adapters[adapter_name]

            for test_case in test_cases:
                for concurrency in concurrency_levels:
                    current_test += 1
                    self.step_logger.step(
                        f"测试 {current_test}/{total_tests}",
                        f"{adapter_name} - {test_case.name} - 并发:{concurrency}"
                    )

                    try:
                        result = await self.run_single_test(
                            test_case=test_case,
                            adapter=adapter,
                            adapter_name=adapter_name,
                            concurrency=concurrency,
                        )
                        suite_result.results.append(result)

                    except Exception as e:
                        logger.error(f"测试失败: {e}")
                        # 记录失败结果
                        suite_result.results.append(TestResult(
                            test_case_id=test_case.id,
                            adapter_name=adapter_name,
                            data_scale=test_case.data_scale,
                            concurrency=concurrency,
                            latency=LatencyMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                            throughput=ThroughputMetrics(0, 0, 0, 0, 1.0, 0),
                            details={"error": str(e)},
                        ))

        suite_result.end_time = datetime.now()
        suite_result.total_duration_seconds = (
            suite_result.end_time - suite_result.start_time
        ).total_seconds()

        self.step_logger.complete(
            f"完成 {len(suite_result.results)} 个测试"
        )

        return suite_result

    async def run_single_test(
        self,
        test_case: TestCase,
        adapter: Union[KnowledgeBaseAdapter, MemoryAdapter],
        adapter_name: str,
        concurrency: int = 1,
    ) -> TestResult:
        """执行单个测试用例

        Args:
            test_case: 测试用例
            adapter: 适配器实例
            adapter_name: 适配器名称
            concurrency: 并发数

        Returns:
            测试结果
        """
        self.metrics_collector.clear()
        self.metrics_collector.start()

        if test_case.test_type == TestType.KNOWLEDGE_BASE:
            result = await self._run_kb_test(
                test_case, adapter, adapter_name, concurrency
            )
        else:
            result = await self._run_memory_test(
                test_case, adapter, adapter_name, concurrency
            )

        self.metrics_collector.stop()
        return result

    async def _run_kb_test(
        self,
        test_case: TestCase,
        adapter: KnowledgeBaseAdapter,
        adapter_name: str,
        concurrency: int,
    ) -> TestResult:
        """运行知识库测试"""
        # 生成测试数据
        documents = self.data_generator.generate_documents(
            count=self._get_doc_count(test_case.data_scale)
        )
        queries_with_truth = self.data_generator.generate_queries_with_ground_truth(
            documents, queries_per_topic=2
        )

        # 初始化适配器
        await adapter.initialize()

        # 上传文档
        upload_start = time.time()
        upload_result = await adapter.upload_documents(documents)
        upload_time = (time.time() - upload_start) * 1000

        # 构建索引
        index_start = time.time()
        await adapter.build_index()
        index_time = (time.time() - index_start) * 1000

        # 执行查询测试
        predictions = []
        ground_truth = []

        if concurrency == 1:
            # 单线程查询
            for query, relevant_ids in queries_with_truth[:test_case.num_queries]:
                start = time.time()
                result = await adapter.query(query, top_k=test_case.top_k)
                latency = (time.time() - start) * 1000

                self.metrics_collector.record_latency("query", latency)
                predictions.append([d.get("id", "") for d in result.documents])
                ground_truth.append(relevant_ids)
        else:
            # 并发查询
            async def query_task(query: str, relevant_ids: List[str]):
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                start = time.time()
                result = await adapter.query(query, top_k=test_case.top_k)
                latency = (time.time() - start) * 1000
                self.metrics_collector.record_latency("query", latency)
                return [d.get("id", "") for d in result.documents], relevant_ids

            tasks = [
                query_task(q, ids)
                for q, ids in queries_with_truth[:test_case.num_queries]
            ]

            # 分批执行以控制并发
            for i in range(0, len(tasks), concurrency):
                batch = tasks[i:i + concurrency]
                results = await asyncio.gather(*batch, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        predictions.append([])
                        ground_truth.append([])
                    else:
                        predictions.append(r[0])
                        ground_truth.append(r[1])

        # 清理
        await adapter.cleanup()

        # 计算指标
        latency_metrics = self.metrics_collector.calculate_latency_metrics("latency_query")
        throughput_metrics = self.metrics_collector.calculate_throughput_metrics("latency_query")
        quality_metrics = self.metrics_collector.calculate_quality_metrics(predictions, ground_truth)

        return TestResult(
            test_case_id=test_case.id,
            adapter_name=adapter_name,
            data_scale=test_case.data_scale,
            concurrency=concurrency,
            latency=latency_metrics,
            throughput=throughput_metrics,
            quality=quality_metrics,
            details={
                "upload_time_ms": upload_time,
                "index_time_ms": index_time,
                "upload_success": upload_result.success_count,
                "upload_failed": upload_result.failed_count,
            }
        )

    async def _run_memory_test(
        self,
        test_case: TestCase,
        adapter: MemoryAdapter,
        adapter_name: str,
        concurrency: int,
    ) -> TestResult:
        """运行记忆系统测试"""
        # 生成测试数据
        memories = self.data_generator.generate_memories(
            count=self._get_memory_count(test_case.data_scale),
            num_users=10,
        )
        queries = self.data_generator.generate_queries(test_case.num_queries)

        # 初始化适配器
        await adapter.initialize()

        # 添加记忆
        add_start = time.time()
        add_results = await adapter.add_memories_batch(memories)
        add_time = (time.time() - add_start) * 1000
        success_count = sum(1 for r in add_results if r.success)

        # 执行搜索测试
        user_ids = list(set(m.user_id for m in memories))

        if concurrency == 1:
            for query in queries:
                user_id = user_ids[hash(query) % len(user_ids)]
                start = time.time()
                await adapter.search_memory(query, user_id, top_k=test_case.top_k)
                latency = (time.time() - start) * 1000
                self.metrics_collector.record_latency("search", latency)
        else:
            async def search_task(query: str):
                if self.rate_limiter:
                    await self.rate_limiter.acquire()
                user_id = user_ids[hash(query) % len(user_ids)]
                start = time.time()
                await adapter.search_memory(query, user_id, top_k=test_case.top_k)
                latency = (time.time() - start) * 1000
                self.metrics_collector.record_latency("search", latency)

            tasks = [search_task(q) for q in queries]
            for i in range(0, len(tasks), concurrency):
                batch = tasks[i:i + concurrency]
                await asyncio.gather(*batch, return_exceptions=True)

        # 清理
        await adapter.cleanup()

        # 计算指标
        latency_metrics = self.metrics_collector.calculate_latency_metrics("latency_search")
        throughput_metrics = self.metrics_collector.calculate_throughput_metrics("latency_search")

        return TestResult(
            test_case_id=test_case.id,
            adapter_name=adapter_name,
            data_scale=test_case.data_scale,
            concurrency=concurrency,
            latency=latency_metrics,
            throughput=throughput_metrics,
            details={
                "add_time_ms": add_time,
                "add_success": success_count,
                "add_failed": len(add_results) - success_count,
            }
        )

    async def run_concurrent_stress_test(
        self,
        adapter: Union[KnowledgeBaseAdapter, MemoryAdapter],
        adapter_name: str,
        test_type: TestType,
        config: ConcurrencyConfig,
    ) -> TestResult:
        """运行并发压力测试

        持续一段时间的高并发测试，用于评估系统在压力下的表现。

        Args:
            adapter: 适配器实例
            adapter_name: 适配器名称
            test_type: 测试类型
            config: 并发配置

        Returns:
            测试结果
        """
        self.metrics_collector.clear()
        self.step_logger.step("压力测试", f"并发={config.concurrency}, 持续={config.duration_seconds}s")

        # 初始化
        await adapter.initialize()

        # 准备测试数据
        if test_type == TestType.KNOWLEDGE_BASE:
            documents = self.data_generator.generate_documents(count=50)
            await adapter.upload_documents(documents)
            await adapter.build_index()
            queries = self.data_generator.generate_queries(100)
        else:
            memories = self.data_generator.generate_memories(count=100, num_users=10)
            await adapter.add_memories_batch(memories)
            queries = self.data_generator.generate_queries(100)
            user_ids = list(set(m.user_id for m in memories))

        # 预热
        if config.warmup_seconds > 0:
            self.step_logger.step("预热", f"{config.warmup_seconds}s")
            warmup_end = time.time() + config.warmup_seconds
            while time.time() < warmup_end:
                query = queries[int(time.time()) % len(queries)]
                if test_type == TestType.KNOWLEDGE_BASE:
                    await adapter.query(query, top_k=5)
                else:
                    user_id = user_ids[int(time.time()) % len(user_ids)]
                    await adapter.search_memory(query, user_id, top_k=5)
                await asyncio.sleep(0.1)

        # 正式测试
        self.metrics_collector.start()
        self.step_logger.step("压力测试中", f"持续 {config.duration_seconds}s")

        test_end = time.time() + config.duration_seconds
        active_tasks = set()

        async def worker():
            while time.time() < test_end:
                query = queries[int(time.time() * 1000) % len(queries)]
                start = time.time()

                try:
                    if test_type == TestType.KNOWLEDGE_BASE:
                        await adapter.query(query, top_k=5)
                    else:
                        user_id = user_ids[int(time.time() * 1000) % len(user_ids)]
                        await adapter.search_memory(query, user_id, top_k=5)

                    latency = (time.time() - start) * 1000
                    self.metrics_collector.record_latency("stress", latency, success=True)
                except Exception:
                    latency = (time.time() - start) * 1000
                    self.metrics_collector.record_latency("stress", latency, success=False)

                # 小延迟避免过度消耗
                await asyncio.sleep(0.01)

        # 启动并发 workers
        workers = [asyncio.create_task(worker()) for _ in range(config.concurrency)]
        await asyncio.gather(*workers)

        self.metrics_collector.stop()

        # 清理
        await adapter.cleanup()

        # 计算指标
        latency_metrics = self.metrics_collector.calculate_latency_metrics("latency_stress")
        throughput_metrics = self.metrics_collector.calculate_throughput_metrics("latency_stress")

        self.step_logger.complete(f"QPS: {throughput_metrics.qps:.2f}")

        return TestResult(
            test_case_id="stress_test",
            adapter_name=adapter_name,
            data_scale="stress",
            concurrency=config.concurrency,
            latency=latency_metrics,
            throughput=throughput_metrics,
            details={
                "duration_seconds": config.duration_seconds,
                "warmup_seconds": config.warmup_seconds,
            }
        )

    async def run_stepped_concurrency_test(
        self,
        adapter: Union[KnowledgeBaseAdapter, MemoryAdapter],
        adapter_name: str,
        test_type: TestType,
        concurrency_levels: List[int] = [1, 10, 50, 100],
        duration_per_level: int = 30,
    ) -> List[TestResult]:
        """运行阶梯式并发测试

        逐步增加并发级别，评估系统在不同负载下的表现。

        Args:
            adapter: 适配器实例
            adapter_name: 适配器名称
            test_type: 测试类型
            concurrency_levels: 并发级别列表
            duration_per_level: 每个级别的测试时长（秒）

        Returns:
            各级别的测试结果列表
        """
        results = []

        self.step_logger.start(f"阶梯式并发测试: {adapter_name}")

        for i, concurrency in enumerate(concurrency_levels):
            self.step_logger.step(
                f"级别 {i + 1}/{len(concurrency_levels)}",
                f"并发 = {concurrency}"
            )

            config = ConcurrencyConfig(
                concurrency=concurrency,
                duration_seconds=duration_per_level,
                warmup_seconds=5 if i == 0 else 0,  # 只在第一级预热
            )

            result = await self.run_concurrent_stress_test(
                adapter=adapter,
                adapter_name=adapter_name,
                test_type=test_type,
                config=config,
            )
            results.append(result)

            # 级别之间短暂休息
            if i < len(concurrency_levels) - 1:
                await asyncio.sleep(2)

        self.step_logger.complete(f"完成 {len(results)} 个并发级别测试")
        return results

    def _get_doc_count(self, scale: str) -> int:
        """获取文档数量"""
        scales = {
            "tiny": 10,
            "small": 100,
            "medium": 1000,
            "large": 10000,
        }
        return scales.get(scale, 10)

    def _get_memory_count(self, scale: str) -> int:
        """获取记忆数量"""
        scales = {
            "tiny": 20,
            "small": 200,
            "medium": 2000,
            "large": 20000,
        }
        return scales.get(scale, 20)
