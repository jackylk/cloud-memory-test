"""性能测试框架集成测试"""

import pytest
import asyncio
import os
from datetime import datetime

from src.adapters.base import Document, DocumentFormat, Memory
from src.adapters.knowledge_base import SimpleVectorStore, MilvusAdapter, PineconeAdapter
from src.adapters.memory import Mem0LocalAdapter, MilvusMemoryAdapter
from src.core.benchmark_runner import BenchmarkRunner
from src.core.data_generator import TestDataGenerator as DataGen
from src.core.metrics import MetricsCollector


class TestDataGeneratorClass:
    """测试数据生成器测试"""

    def test_generate_documents(self):
        """测试文档数据生成"""
        generator = DataGen()
        documents = generator.generate_documents(count=5)

        assert len(documents) == 5
        assert all(doc.id for doc in documents)
        assert all(doc.content for doc in documents)

    def test_generate_queries(self):
        """测试查询生成"""
        generator = DataGen()
        queries = generator.generate_queries(count=5)

        assert len(queries) == 5
        assert all(isinstance(q, str) for q in queries)

    def test_generate_memories(self):
        """测试记忆数据生成"""
        generator = DataGen()
        memories = generator.generate_memories(count=10, num_users=3)

        assert len(memories) == 10
        assert all(mem.user_id for mem in memories)
        assert all(mem.content for mem in memories)


class TestMetricsCollector:
    """指标收集器测试"""

    def test_calculate_latency_metrics(self):
        """测试延迟指标计算"""
        collector = MetricsCollector()
        collector.start()

        # 记录一些延迟数据
        for latency in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            collector.record_latency("query", latency)

        collector.stop()
        metrics = collector.calculate_latency_metrics("latency_query")

        assert metrics.p50 > 0
        assert metrics.p95 > 0
        assert metrics.count == 10

    def test_calculate_quality_metrics(self):
        """测试质量指标计算"""
        collector = MetricsCollector()

        # 模拟完美召回情况
        predictions = [["doc1", "doc2", "doc3"]]
        ground_truth = [["doc1"]]

        metrics = collector.calculate_quality_metrics(predictions, ground_truth)

        assert metrics.precision_at_1 == 1.0  # doc1 在第一位
        assert metrics.mrr == 1.0


class TestBenchmarkIntegration:
    """性能测试集成测试"""

    @pytest.fixture
    def simple_kb_adapter(self):
        """创建 SimpleVectorStore 适配器"""
        return SimpleVectorStore({"similarity_threshold": 0.1})

    @pytest.fixture
    def milvus_kb_adapter(self):
        """创建 Milvus 知识库适配器"""
        return MilvusAdapter({
            "collection_name": f"int_test_kb_{datetime.now().strftime('%H%M%S%f')}",
            "dimension": 384,
            "db_path": f"./int_test_milvus_kb_{datetime.now().strftime('%H%M%S%f')}.db",
            "use_lite": True
        })

    @pytest.fixture
    def pinecone_kb_adapter(self):
        """创建 Pinecone 知识库适配器（模拟模式）"""
        return PineconeAdapter({
            "index_name": f"int_test_kb_{datetime.now().strftime('%H%M%S%f')}",
            "dimension": 384,
            "mock_mode": True
        })

    @pytest.fixture
    def mem0_adapter(self):
        """创建 Mem0 记忆适配器"""
        return Mem0LocalAdapter({"use_simple_store": True})

    @pytest.fixture
    def milvus_mem_adapter(self):
        """创建 Milvus 记忆适配器"""
        return MilvusMemoryAdapter({
            "collection_name": f"int_test_mem_{datetime.now().strftime('%H%M%S%f')}",
            "dimension": 384,
            "db_path": f"./int_test_milvus_mem_{datetime.now().strftime('%H%M%S%f')}.db",
            "use_lite": True
        })

    @pytest.mark.asyncio
    async def test_simple_kb_full_flow(self, simple_kb_adapter):
        """测试 SimpleVectorStore 完整流程"""
        await simple_kb_adapter.initialize()

        # 上传文档
        documents = [
            Document(
                id="doc1",
                content="机器学习是人工智能的核心技术",
                format=DocumentFormat.TXT,
                title="机器学习"
            ),
            Document(
                id="doc2",
                content="深度学习使用神经网络进行学习",
                format=DocumentFormat.TXT,
                title="深度学习"
            ),
        ]

        upload_result = await simple_kb_adapter.upload_documents(documents)
        assert upload_result.success_count == 2

        # 构建索引
        index_result = await simple_kb_adapter.build_index()
        assert index_result.success

        # 查询
        query_result = await simple_kb_adapter.query("机器学习技术", top_k=2)
        assert query_result.total_results > 0

        await simple_kb_adapter.cleanup()

    @pytest.mark.asyncio
    async def test_milvus_kb_full_flow(self, milvus_kb_adapter):
        """测试 Milvus 知识库完整流程"""
        await milvus_kb_adapter.initialize()

        # 上传文档
        documents = [
            Document(
                id="doc1",
                content="机器学习是人工智能的核心技术",
                format=DocumentFormat.TXT,
                title="机器学习"
            ),
            Document(
                id="doc2",
                content="深度学习使用神经网络进行学习",
                format=DocumentFormat.TXT,
                title="深度学习"
            ),
        ]

        upload_result = await milvus_kb_adapter.upload_documents(documents)
        assert upload_result.success_count == 2

        # 构建索引
        index_result = await milvus_kb_adapter.build_index()
        assert index_result.success
        assert index_result.doc_count == 2

        # 查询
        query_result = await milvus_kb_adapter.query("机器学习技术", top_k=2)
        assert query_result.total_results > 0
        assert query_result.latency_ms > 0

        # 统计
        stats = await milvus_kb_adapter.get_stats()
        assert stats["initialized"]

        await milvus_kb_adapter.cleanup()

    @pytest.mark.asyncio
    async def test_pinecone_kb_full_flow(self, pinecone_kb_adapter):
        """测试 Pinecone 知识库完整流程（模拟模式）"""
        await pinecone_kb_adapter.initialize()

        # 上传文档
        documents = [
            Document(
                id="doc1",
                content="机器学习是人工智能的核心技术",
                format=DocumentFormat.TXT,
                title="机器学习"
            ),
            Document(
                id="doc2",
                content="深度学习使用神经网络进行学习",
                format=DocumentFormat.TXT,
                title="深度学习"
            ),
        ]

        upload_result = await pinecone_kb_adapter.upload_documents(documents)
        assert upload_result.success_count == 2

        # 构建索引
        index_result = await pinecone_kb_adapter.build_index()
        assert index_result.success
        assert index_result.doc_count == 2

        # 查询
        query_result = await pinecone_kb_adapter.query("机器学习技术", top_k=2)
        assert query_result.total_results > 0

        # 统计
        stats = await pinecone_kb_adapter.get_stats()
        assert stats["mode"] == "mock"

        await pinecone_kb_adapter.cleanup()

    @pytest.mark.asyncio
    async def test_mem0_full_flow(self, mem0_adapter):
        """测试 Mem0 记忆系统完整流程"""
        await mem0_adapter.initialize()

        # 添加记忆
        memories = [
            Memory(
                id=None,
                user_id="user1",
                content="用户喜欢机器学习",
                memory_type="preference"
            ),
            Memory(
                id=None,
                user_id="user1",
                content="用户正在学习深度学习",
                memory_type="fact"
            ),
        ]

        results = await mem0_adapter.add_memories_batch(memories)
        assert all(r.success for r in results)

        # 搜索记忆
        search_result = await mem0_adapter.search_memory("机器学习", "user1", top_k=5)
        assert search_result.latency_ms >= 0

        # 获取用户记忆
        user_memories = await mem0_adapter.get_user_memories("user1")
        assert len(user_memories) == 2

        await mem0_adapter.cleanup()

    @pytest.mark.asyncio
    async def test_milvus_memory_full_flow(self, milvus_mem_adapter):
        """测试 Milvus 记忆系统完整流程"""
        await milvus_mem_adapter.initialize()

        # 添加记忆
        memories = [
            Memory(
                id=None,
                user_id="user1",
                content="用户喜欢机器学习",
                memory_type="preference"
            ),
            Memory(
                id=None,
                user_id="user1",
                content="用户正在学习深度学习",
                memory_type="fact"
            ),
        ]

        results = await milvus_mem_adapter.add_memories_batch(memories)
        assert all(r.success for r in results)

        # 搜索记忆
        search_result = await milvus_mem_adapter.search_memory("机器学习", "user1", top_k=5)
        assert search_result.latency_ms >= 0

        # 获取用户记忆
        user_memories = await milvus_mem_adapter.get_user_memories("user1")
        assert len(user_memories) == 2

        # 统计
        stats = await milvus_mem_adapter.get_stats()
        assert stats["initialized"]
        assert stats["total_memories"] == 2

        await milvus_mem_adapter.cleanup()


class TestMultiAdapterComparison:
    """多适配器对比测试"""

    @pytest.mark.asyncio
    async def test_kb_adapters_comparison(self):
        """对比不同知识库适配器"""
        adapters = [
            ("SimpleVectorStore", SimpleVectorStore({"similarity_threshold": 0.1})),
            ("MilvusAdapter", MilvusAdapter({
                "collection_name": f"cmp_kb_{datetime.now().strftime('%H%M%S%f')}",
                "dimension": 384,
                "db_path": f"./cmp_milvus_kb_{datetime.now().strftime('%H%M%S%f')}.db",
                "use_lite": True
            })),
            ("PineconeAdapter", PineconeAdapter({
                "index_name": f"cmp_kb_{datetime.now().strftime('%H%M%S%f')}",
                "dimension": 384,
                "mock_mode": True
            })),
        ]

        documents = [
            Document(
                id=f"doc_{i}",
                content=f"这是测试文档 {i}，内容关于机器学习和人工智能",
                format=DocumentFormat.TXT,
                title=f"文档{i}"
            )
            for i in range(5)
        ]

        results = {}

        for name, adapter in adapters:
            await adapter.initialize()

            # 上传
            upload_result = await adapter.upload_documents(documents)

            # 对于 SimpleVectorStore，需要构建索引
            if name == "SimpleVectorStore":
                await adapter.build_index()

            # 查询
            query_result = await adapter.query("机器学习", top_k=3)

            results[name] = {
                "upload_time_ms": upload_result.total_time_ms,
                "query_latency_ms": query_result.latency_ms,
                "result_count": query_result.total_results
            }

            await adapter.cleanup()

        # 验证所有适配器都返回了结果
        for name, metrics in results.items():
            assert metrics["result_count"] > 0, f"{name} 没有返回结果"
            print(f"\n{name}:")
            print(f"  上传耗时: {metrics['upload_time_ms']:.2f}ms")
            print(f"  查询延迟: {metrics['query_latency_ms']:.2f}ms")
            print(f"  结果数量: {metrics['result_count']}")

    @pytest.mark.asyncio
    async def test_memory_adapters_comparison(self):
        """对比不同记忆系统适配器"""
        adapters = [
            ("Mem0LocalAdapter", Mem0LocalAdapter({"use_simple_store": True})),
            ("MilvusMemoryAdapter", MilvusMemoryAdapter({
                "collection_name": f"cmp_mem_{datetime.now().strftime('%H%M%S%f')}",
                "dimension": 384,
                "db_path": f"./cmp_milvus_mem_{datetime.now().strftime('%H%M%S%f')}.db",
                "use_lite": True
            })),
        ]

        memories = [
            Memory(
                id=None,
                user_id="user1",
                content=f"用户记忆 {i}：关于机器学习和数据科学的内容",
                memory_type="fact"
            )
            for i in range(5)
        ]

        results = {}

        for name, adapter in adapters:
            await adapter.initialize()

            # 添加记忆
            import time
            start = time.time()
            add_results = await adapter.add_memories_batch(memories)
            add_time = (time.time() - start) * 1000

            # 搜索
            search_result = await adapter.search_memory("机器学习", "user1", top_k=3)

            results[name] = {
                "add_time_ms": add_time,
                "search_latency_ms": search_result.latency_ms,
                "success_rate": sum(1 for r in add_results if r.success) / len(add_results) * 100
            }

            await adapter.cleanup()

        # 输出对比结果
        for name, metrics in results.items():
            print(f"\n{name}:")
            print(f"  添加耗时: {metrics['add_time_ms']:.2f}ms")
            print(f"  搜索延迟: {metrics['search_latency_ms']:.2f}ms")
            print(f"  成功率: {metrics['success_rate']:.1f}%")


# 清理测试生成的文件
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_files():
    """测试完成后清理生成的文件"""
    yield

    import glob
    # 清理 Milvus Lite 数据库文件
    for f in glob.glob("./*_test_*.db"):
        try:
            os.remove(f)
        except:
            pass
    for f in glob.glob("./int_test_*.db"):
        try:
            os.remove(f)
        except:
            pass
    for f in glob.glob("./cmp_*.db"):
        try:
            os.remove(f)
        except:
            pass


# 运行测试的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto", "-s"])
