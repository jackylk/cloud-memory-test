"""基准测试运行器"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from ..adapters.base import KnowledgeBaseAdapter, MemoryAdapter, Document, Memory
from ..utils.logger import StepLogger
from .data_generator import TestDataGenerator
from .metrics import MetricsCollector, LatencyMetrics, ThroughputMetrics, QualityMetrics


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    adapter_name: str
    adapter_type: str  # "knowledge_base" or "memory"
    test_name: str
    data_scale: str
    timestamp: datetime = field(default_factory=datetime.now)

    # 性能指标
    latency: Optional[LatencyMetrics] = None
    throughput: Optional[ThroughputMetrics] = None
    quality: Optional[QualityMetrics] = None

    # 详细信息
    details: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "adapter_type": self.adapter_type,
            "test_name": self.test_name,
            "data_scale": self.data_scale,
            "timestamp": self.timestamp.isoformat(),
            "latency": self.latency.to_dict() if self.latency else None,
            "throughput": self.throughput.to_dict() if self.throughput else None,
            "quality": self.quality.to_dict() if self.quality else None,
            "details": self.details,
        }


class BenchmarkRunner:
    """基准测试运行器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.data_generator = TestDataGenerator()
        self.results: List[BenchmarkResult] = []

    async def run_knowledge_base_benchmark(
        self,
        adapter: KnowledgeBaseAdapter,
        data_scale: str = "tiny",
        run_quality_test: bool = True,
        skip_upload: bool = False
    ) -> BenchmarkResult:
        """运行知识库基准测试

        Args:
            adapter: 知识库适配器
            data_scale: 数据规模 (tiny, small, medium, large)
            run_quality_test: 是否运行质量测试
            skip_upload: 是否跳过文档上传（文档已预先入库）

        Returns:
            测试结果
        """
        # 获取数据规模配置
        scale_config = self._get_scale_config(data_scale)
        doc_count = scale_config.get("doc_count", 10)
        query_count = scale_config.get("queries_count", 5)

        step_logger = StepLogger(total_steps=5, task_name=f"知识库测试 [{adapter.name}]")
        step_logger.start()

        metrics = MetricsCollector()
        metrics.start()

        details = {
            "data_scale": data_scale,
            "doc_count": doc_count,
            "query_count": query_count,
        }

        try:
            # 步骤 1: 初始化
            with step_logger.step("初始化适配器") as ctx:
                await adapter.initialize()
                stats = await adapter.get_stats()
                ctx.info(f"适配器: {adapter.name}")
                for key, value in stats.items():
                    ctx.detail(f"{key}: {value}")

                # 测量网络基线延迟（用于分离网络时延和服务端时延）
                ctx.info("测量网络基线延迟...")
                network_latency = await adapter.measure_network_latency(num_samples=10)
                ctx.info(f"网络基线: P50={network_latency['p50']:.2f}ms, P95={network_latency['p95']:.2f}ms, Avg={network_latency['avg']:.2f}ms")
                details["network_latency"] = network_latency

            # 步骤 2: 生成并上传文档（可选）
            # 跳过上传时不再生成文档，仅对已有知识库做查询；质量评估使用 test-data
            documents = []
            if not skip_upload:
                documents = self.data_generator.generate_documents(doc_count)

            if skip_upload:
                with step_logger.step("跳过文档上传") as ctx:
                    ctx.info(f"文档已预先入库（{doc_count}个），仅执行查询与质量评估")
                    details["upload_time_ms"] = 0
                    details["upload_success"] = 0
                    details["upload_failed"] = 0
            else:
                with step_logger.step("生成并上传文档") as ctx:
                    ctx.info(f"生成 {len(documents)} 个文档")

                    upload_result = await adapter.upload_documents(documents)
                    ctx.info(f"上传完成: 成功 {upload_result.success_count}, 失败 {upload_result.failed_count}")
                    ctx.info(f"上传耗时: {upload_result.total_time_ms:.2f}ms")

                    details["upload_time_ms"] = upload_result.total_time_ms
                    details["upload_success"] = upload_result.success_count
                    details["upload_failed"] = upload_result.failed_count

            # 步骤 3: 构建索引（可选）
            if skip_upload:
                with step_logger.step("跳过索引构建") as ctx:
                    ctx.info(f"索引已存在")
                    details["index_time_ms"] = 0
                    details["indexed_docs"] = doc_count
            else:
                with step_logger.step("构建索引") as ctx:
                    index_result = await adapter.build_index()
                    ctx.info(f"索引文档数: {index_result.doc_count}")
                    ctx.info(f"索引耗时: {index_result.index_time_ms:.2f}ms")

                    details["index_time_ms"] = index_result.index_time_ms
                    details["indexed_docs"] = index_result.doc_count

            # 步骤 4: 执行查询测试
            with step_logger.step("执行查询测试") as ctx:
                # 获取查询类型配置
                query_type = self.config.get("data", {}).get("query_type", "default")
                queries = self.data_generator.generate_queries(query_count, query_type=query_type)
                ctx.info(f"执行 {len(queries)} 个查询")

                for i, query in enumerate(queries):
                    result = await adapter.query(query, top_k=5)
                    metrics.record_latency("query", result.latency_ms)

                    ctx.progress(i + 1, len(queries))
                    ctx.detail(f"查询 {i+1}: '{query[:30]}...' → {result.total_results} 结果, {result.latency_ms:.2f}ms")

                    # 打印前几个结果的详情
                    if self.config.get("debug", {}).get("print_results", False):
                        for j, doc in enumerate(result.documents[:3]):
                            ctx.detail(f"  结果 {j+1}: {doc.get('id')} (score: {result.scores[j]:.3f})")

            # 步骤 5: 收集和计算指标
            with step_logger.step("收集指标") as ctx:
                metrics.stop()
                latency_metrics = metrics.calculate_latency_metrics()
                throughput_metrics = metrics.calculate_throughput_metrics()

                ctx.info(f"端到端延迟: {latency_metrics}")
                ctx.info(f"吞吐: {throughput_metrics}")

                # 计算服务端时延（端到端延迟 - 网络基线）
                if "network_latency" in details:
                    network_baseline = details["network_latency"]["p50"]
                    server_p50 = max(0, latency_metrics.p50 - network_baseline)
                    server_p95 = max(0, latency_metrics.p95 - network_baseline)
                    server_avg = max(0, latency_metrics.avg - network_baseline)

                    ctx.info(f"网络基线: P50={network_baseline:.2f}ms")
                    ctx.info(f"估算服务端时延: P50={server_p50:.2f}ms, P95={server_p95:.2f}ms, Avg={server_avg:.2f}ms")

                    details["server_latency_estimate"] = {
                        "p50": server_p50,
                        "p95": server_p95,
                        "avg": server_avg
                    }

                # 质量测试（可选）
                quality_metrics = None
                if run_quality_test:
                    ctx.info("执行质量评估...")

                    if skip_upload:
                        # 使用test-data文档进行质量评估
                        ctx.info("使用test-data文档生成查询和ground truth")
                        queries_with_truth = self.data_generator.generate_queries_from_test_data(
                            test_data_dir="test-data",
                            num_queries=min(20, query_count)
                        )
                    else:
                        # 使用生成的文档进行质量评估
                        query_type = self.config.get("data", {}).get("query_type", "default")
                        queries_with_truth = self.data_generator.generate_queries_with_ground_truth(
                            documents, queries_per_topic=2, query_type=query_type
                        )

                    predictions = []
                    ground_truths = []

                    for query, truth in queries_with_truth:
                        result = await adapter.query(query, top_k=10)

                        # 提取返回文档的ID/文件名（用于与 ground truth 匹配）
                        pred_ids = []
                        for doc in result.documents:
                            doc_id = doc.get("id", "")
                            doc_id = str(doc_id) if doc_id else ""
                            # 优先使用与文件名相关的字段，并统一取 basename 便于匹配
                            raw = ""
                            if "s3://" in doc_id:
                                raw = doc_id.split("/")[-1]
                            elif doc.get("title"):
                                raw = doc.get("title") or ""
                            elif doc.get("metadata", {}).get("doc_name"):
                                raw = doc.get("metadata", {}).get("doc_name") or ""
                            else:
                                raw = doc_id
                            if isinstance(raw, str) and "/" in raw:
                                raw = raw.split("/")[-1]
                            pred_ids.append(raw if raw else doc_id)

                        predictions.append(pred_ids)
                        ground_truths.append(truth)

                    quality_metrics = metrics.calculate_quality_metrics(predictions, ground_truths)
                    ctx.info(f"质量: {quality_metrics}")

                    # 打印一些匹配样例用于调试
                    if self.config.get("debug", {}).get("print_results", False) and queries_with_truth:
                        ctx.info("质量评估样例:")
                        for i, (query, truth) in enumerate(queries_with_truth[:3]):
                            ctx.detail(f"  查询: '{query}'")
                            ctx.detail(f"  Ground truth: {truth[:3]}")
                            ctx.detail(f"  预测结果: {predictions[i][:3]}")

        except Exception as e:
            logger.error(f"测试过程中发生错误: {e}")
            raise

        finally:
            # 清理资源
            try:
                await adapter.cleanup()
            except Exception as e:
                logger.warning(f"清理资源时发生错误: {e}")

        # 构建结果
        result = BenchmarkResult(
            adapter_name=adapter.name,
            adapter_type="knowledge_base",
            test_name="knowledge_base_benchmark",
            data_scale=data_scale,
            latency=latency_metrics,
            throughput=throughput_metrics,
            quality=quality_metrics,
            details=details,
            raw_data=metrics.get_raw_data() if self.config.get("debug", {}).get("save_raw_data") else {}
        )

        # 输出摘要
        step_logger.end({
            "适配器": adapter.name,
            "数据规模": data_scale,
            "文档数": doc_count,
            "查询数": query_count,
            "平均延迟": f"{latency_metrics.mean:.2f}ms",
            "P95延迟": f"{latency_metrics.p95:.2f}ms",
            "QPS": f"{throughput_metrics.qps:.2f}",
        })

        self.results.append(result)
        return result

    async def run_memory_benchmark(
        self,
        adapter: MemoryAdapter,
        data_scale: str = "tiny"
    ) -> BenchmarkResult:
        """运行记忆系统基准测试

        Args:
            adapter: 记忆适配器
            data_scale: 数据规模

        Returns:
            测试结果
        """
        scale_config = self._get_scale_config(data_scale)
        memory_count = scale_config.get("memories_count", 20)
        num_users = min(10, memory_count // 2)
        query_count = scale_config.get("queries_count", 5)

        step_logger = StepLogger(total_steps=5, task_name=f"记忆系统测试 [{adapter.name}]")
        step_logger.start()

        metrics = MetricsCollector()
        metrics.start()

        details = {
            "data_scale": data_scale,
            "memory_count": memory_count,
            "num_users": num_users,
            "query_count": query_count,
        }

        try:
            # 步骤 1: 初始化
            with step_logger.step("初始化适配器") as ctx:
                await adapter.initialize()
                stats = await adapter.get_stats()
                details["run_mode"] = stats.get("mode", "unknown")  # mock | real，供报告标注
                ctx.info(f"适配器: {adapter.name}")
                for key, value in stats.items():
                    ctx.detail(f"{key}: {value}")

                # 测量网络基线延迟
                ctx.info("测量网络基线延迟...")
                network_latency = await adapter.measure_network_latency(num_samples=10)
                ctx.info(f"网络基线: P50={network_latency['p50']:.2f}ms, P95={network_latency['p95']:.2f}ms, Avg={network_latency['avg']:.2f}ms")
                details["network_latency"] = network_latency

            # 步骤 2: 生成并添加记忆
            with step_logger.step("生成并添加记忆") as ctx:
                memories = self.data_generator.generate_memories(
                    memory_count,
                    num_users=num_users,
                    time_span_days=30
                )
                ctx.info(f"生成 {len(memories)} 条记忆")

                success_count = 0
                total_add_time = 0

                for i, memory in enumerate(memories):
                    result = await adapter.add_memory(memory)
                    if result.success:
                        success_count += 1
                    total_add_time += result.latency_ms
                    metrics.record_latency("add_memory", result.latency_ms, result.success)

                    ctx.progress(i + 1, len(memories))

                ctx.info(f"添加完成: 成功 {success_count}/{len(memories)}")
                ctx.info(f"总耗时: {total_add_time:.2f}ms")

                details["add_success"] = success_count
                details["add_total_time_ms"] = total_add_time

            # 步骤 3: 验证存储
            with step_logger.step("验证存储") as ctx:
                stats = await adapter.get_stats()
                ctx.info(f"当前状态: {stats}")

            # 步骤 4: 执行搜索测试
            with step_logger.step("执行搜索测试") as ctx:
                search_queries = self.data_generator.generate_memory_queries(memories, query_count)
                ctx.info(f"执行 {len(search_queries)} 个搜索")

                for i, (query, user_id) in enumerate(search_queries):
                    result = await adapter.search_memory(query, user_id, top_k=5)
                    metrics.record_latency("search_memory", result.latency_ms)

                    ctx.progress(i + 1, len(search_queries))
                    ctx.detail(f"搜索 {i+1}: '{query[:30]}...' (user={user_id}) → {result.total_results} 结果")

                    if self.config.get("debug", {}).get("print_results", False):
                        for j, mem in enumerate(result.memories[:3]):
                            ctx.detail(f"  结果 {j+1}: {mem.content[:50]}... (score: {result.scores[j]:.3f})")

            # 步骤 5: 收集指标
            with step_logger.step("收集指标") as ctx:
                metrics.stop()

                # 写入延迟
                add_latency = metrics.calculate_latency_metrics("latency_add_memory")
                ctx.info(f"写入延迟(端到端): {add_latency}")

                # 搜索延迟
                search_latency = metrics.calculate_latency_metrics("latency_search_memory")
                ctx.info(f"搜索延迟(端到端): {search_latency}")

                # 总体吞吐
                throughput = metrics.calculate_throughput_metrics()
                ctx.info(f"吞吐: {throughput}")

                # 计算服务端时延（搜索延迟 - 网络基线）
                if "network_latency" in details:
                    network_baseline = details["network_latency"]["p50"]
                    server_p50 = max(0, search_latency.p50 - network_baseline)
                    server_p95 = max(0, search_latency.p95 - network_baseline)
                    server_avg = max(0, search_latency.avg - network_baseline)

                    ctx.info(f"网络基线: P50={network_baseline:.2f}ms")
                    ctx.info(f"估算服务端时延: P50={server_p50:.2f}ms, P95={server_p95:.2f}ms, Avg={server_avg:.2f}ms")

                    details["server_latency_estimate"] = {
                        "p50": server_p50,
                        "p95": server_p95,
                        "avg": server_avg
                    }

        except Exception as e:
            logger.error(f"测试过程中发生错误: {e}")
            raise

        finally:
            try:
                await adapter.cleanup()
            except Exception as e:
                logger.warning(f"清理资源时发生错误: {e}")

        # 合并延迟（使用搜索延迟作为主要指标）
        latency_metrics = metrics.calculate_latency_metrics("latency_search_memory")
        throughput_metrics = metrics.calculate_throughput_metrics()

        result = BenchmarkResult(
            adapter_name=adapter.name,
            adapter_type="memory",
            test_name="memory_benchmark",
            data_scale=data_scale,
            latency=latency_metrics,
            throughput=throughput_metrics,
            details=details,
            raw_data=metrics.get_raw_data() if self.config.get("debug", {}).get("save_raw_data") else {}
        )

        step_logger.end({
            "适配器": adapter.name,
            "数据规模": data_scale,
            "记忆数": memory_count,
            "搜索数": query_count,
            "平均延迟": f"{latency_metrics.mean:.2f}ms",
            "P95延迟": f"{latency_metrics.p95:.2f}ms",
        })

        self.results.append(result)
        return result

    def _get_scale_config(self, scale: str) -> Dict[str, Any]:
        """获取数据规模配置"""
        data_config = self.config.get("data", {})

        scale_configs = {
            "existing": {"doc_count": 100, "queries_count": 5, "memories_count": 20},
            "tiny": {"doc_count": 10, "queries_count": 5, "memories_count": 20},
            "small": {"doc_count": 100, "queries_count": 50, "memories_count": 100},
            "medium": {"doc_count": 1000, "queries_count": 200, "memories_count": 1000},
            "large": {"doc_count": 10000, "queries_count": 500, "memories_count": 10000},
        }

        default_config = scale_configs.get(scale, scale_configs["tiny"]).copy()

        # 使用配置文件中的值覆盖默认值
        if scale in data_config:
            default_config.update(data_config[scale])

        return default_config

    def get_all_results(self) -> List[Dict[str, Any]]:
        """获取所有测试结果"""
        return [r.to_dict() for r in self.results]

    def clear_results(self):
        """清空结果"""
        self.results.clear()
