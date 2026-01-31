"""所有适配器的完整测试套件

测试覆盖:
- 6 个知识库适配器（云服务）
- 4 个记忆系统适配器（云服务）
- 所有适配器的 Mock 模式
"""

import pytest
import asyncio
from datetime import datetime
from typing import List

from src.adapters.base import Document, Memory

# ==================== 知识库适配器测试 ====================


class TestKnowledgeBaseAdapters:
    """知识库适配器测试基类"""

    @pytest.fixture
    def sample_documents(self) -> List[Document]:
        """生成测试文档"""
        return [
            Document(
                id="doc1",
                content="Python 是一种高级编程语言，广泛用于数据科学和机器学习。",
                title="Python 简介",
                metadata={"category": "programming", "language": "zh"}
            ),
            Document(
                id="doc2",
                content="机器学习是人工智能的一个分支，通过数据训练模型进行预测。",
                title="机器学习基础",
                metadata={"category": "AI", "language": "zh"}
            ),
            Document(
                id="doc3",
                content="深度学习使用神经网络处理复杂的数据模式和特征提取。",
                title="深度学习",
                metadata={"category": "AI", "language": "zh"}
            ),
        ]

    async def _test_adapter_lifecycle(self, adapter, sample_documents):
        """通用适配器生命周期测试"""
        # 1. 初始化
        await adapter.initialize()
        assert adapter.is_initialized

        # 2. 上传文档
        upload_result = await adapter.upload_documents(sample_documents)
        if not adapter.mock_mode:
            # 真实模式可能不支持上传
            pass
        else:
            assert upload_result.success_count >= 0

        # 3. 构建索引
        index_result = await adapter.build_index()
        assert index_result.success

        # 4. 查询
        query_result = await adapter.query("机器学习", top_k=2)
        assert query_result is not None
        assert query_result.latency_ms >= 0

        # 5. 统计信息
        stats = await adapter.get_stats()
        assert stats["initialized"] is True

        # 6. 健康检查
        health = await adapter.health_check()
        assert isinstance(health, bool)

        # 7. 清理
        await adapter.cleanup()
        assert not adapter.is_initialized


class TestAWSBedrockKB(TestKnowledgeBaseAdapters):
    """AWS Bedrock KB 适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_documents):
        """测试 Mock 模式"""
        from src.adapters.knowledge_base.aws_bedrock_kb import AWSBedrockKBAdapter

        adapter = AWSBedrockKBAdapter({})
        assert adapter.mock_mode is True
        await self._test_adapter_lifecycle(adapter, sample_documents)

    @pytest.mark.asyncio
    async def test_query_quality_mock(self):
        """测试查询质量"""
        from src.adapters.knowledge_base.aws_bedrock_kb import AWSBedrockKBAdapter

        adapter = AWSBedrockKBAdapter({})
        await adapter.initialize()

        docs = [
            Document(id="1", content="机器学习是AI的重要分支", title="ML"),
            Document(id="2", content="深度学习使用神经网络", title="DL"),
        ]
        await adapter.upload_documents(docs)
        await adapter.build_index()

        result = await adapter.query("机器学习")
        assert len(result.documents) > 0

        await adapter.cleanup()


class TestVolcengineVikingDB(TestKnowledgeBaseAdapters):
    """火山引擎 VikingDB 适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_documents):
        """测试 Mock 模式"""
        from src.adapters.knowledge_base.volcengine_vikingdb import VolcengineVikingDBAdapter

        adapter = VolcengineVikingDBAdapter({})
        assert adapter.mock_mode is True
        await self._test_adapter_lifecycle(adapter, sample_documents)


class TestAlibabaBailian(TestKnowledgeBaseAdapters):
    """阿里百炼适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_documents):
        """测试 Mock 模式"""
        from src.adapters.knowledge_base.alibaba_bailian import AlibabaBailianAdapter

        adapter = AlibabaBailianAdapter({})
        assert adapter.mock_mode is True
        await self._test_adapter_lifecycle(adapter, sample_documents)


class TestGoogleDialogflowCX(TestKnowledgeBaseAdapters):
    """Google Dialogflow CX 适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_documents):
        """测试 Mock 模式"""
        from src.adapters.knowledge_base.google_dialogflow_cx import GoogleDialogflowCXAdapter

        adapter = GoogleDialogflowCXAdapter({})
        assert adapter.mock_mode is True
        await self._test_adapter_lifecycle(adapter, sample_documents)


class TestHuaweiCSS(TestKnowledgeBaseAdapters):
    """华为云 CSS 适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_documents):
        """测试 Mock 模式"""
        from src.adapters.knowledge_base.huawei_css import HuaweiCSSAdapter

        adapter = HuaweiCSSAdapter({})
        assert adapter.mock_mode is True
        await self._test_adapter_lifecycle(adapter, sample_documents)


class TestOpenSearchServerless(TestKnowledgeBaseAdapters):
    """OpenSearch Serverless 适配器测试"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """测试初始化"""
        from src.adapters.knowledge_base.opensearch_serverless import OpenSearchServerlessAdapter

        # Mock 模式（无配置）
        adapter = OpenSearchServerlessAdapter({})
        # OpenSearch 适配器没有 mock_mode，总是尝试连接
        # 这里只测试创建不会抛出异常
        assert adapter is not None


# ==================== 记忆系统适配器测试 ====================


class TestMemoryAdapters:
    """记忆系统适配器测试基类"""

    @pytest.fixture
    def sample_memories(self) -> List[Memory]:
        """生成测试记忆"""
        return [
            Memory(
                id="mem1",
                user_id="user_001",
                content="用户喜欢 Python 编程",
                metadata={"type": "preference"},
                memory_type="preference"
            ),
            Memory(
                id="mem2",
                user_id="user_001",
                content="用户在学习机器学习",
                metadata={"type": "fact"},
                memory_type="fact"
            ),
            Memory(
                id="mem3",
                user_id="user_002",
                content="用户对深度学习感兴趣",
                metadata={"type": "preference"},
                memory_type="preference"
            ),
        ]

    async def _test_memory_adapter_lifecycle(self, adapter, sample_memories):
        """通用记忆适配器生命周期测试"""
        # 1. 初始化
        await adapter.initialize()
        assert adapter.is_initialized

        # 2. 添加单个记忆
        result = await adapter.add_memory(sample_memories[0])
        assert result.memory_id is not None

        # 3. 批量添加记忆
        results = await adapter.add_memories_batch(sample_memories[1:])
        assert len(results) == 2

        # 4. 搜索记忆
        search_result = await adapter.search_memory(
            query="Python",
            user_id="user_001",
            top_k=5
        )
        assert search_result is not None
        assert search_result.latency_ms >= 0

        # 5. 获取用户记忆
        user_memories = await adapter.get_user_memories("user_001", limit=10)
        assert isinstance(user_memories, list)

        # 6. 统计信息
        stats = await adapter.get_stats()
        assert stats["initialized"] is True

        # 7. 更新记忆
        if sample_memories[0].id:
            update_success = await adapter.update_memory(
                sample_memories[0].id,
                "更新后的内容"
            )
            assert isinstance(update_success, bool)

        # 8. 删除记忆
        if sample_memories[0].id:
            delete_success = await adapter.delete_memory(sample_memories[0].id)
            assert isinstance(delete_success, bool)

        # 9. 健康检查
        health = await adapter.health_check()
        assert isinstance(health, bool)

        # 10. 清理
        await adapter.cleanup()


class TestAWSBedrockMemory(TestMemoryAdapters):
    """AWS Bedrock Memory 适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_memories):
        """测试 Mock 模式"""
        from src.adapters.memory.aws_bedrock_memory import AWSBedrockMemoryAdapter

        adapter = AWSBedrockMemoryAdapter({})
        assert adapter.mock_mode is True
        await self._test_memory_adapter_lifecycle(adapter, sample_memories)

    @pytest.mark.asyncio
    async def test_search_quality(self):
        """测试搜索质量"""
        from src.adapters.memory.aws_bedrock_memory import AWSBedrockMemoryAdapter

        adapter = AWSBedrockMemoryAdapter({})
        await adapter.initialize()

        # 添加测试记忆
        memories = [
            Memory(id=None, user_id="user1", content="喜欢Python编程"),
            Memory(id=None, user_id="user1", content="在学习机器学习"),
            Memory(id=None, user_id="user2", content="对深度学习感兴趣"),
        ]

        for mem in memories:
            await adapter.add_memory(mem)

        # 搜索 user1 的记忆
        result = await adapter.search_memory("Python", "user1", top_k=5)
        assert len(result.memories) > 0

        await adapter.cleanup()


class TestGoogleVertexMemory(TestMemoryAdapters):
    """Google Vertex AI Memory 适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_memories):
        """测试 Mock 模式"""
        from src.adapters.memory.google_vertex_memory import GoogleVertexMemoryAdapter

        adapter = GoogleVertexMemoryAdapter({})
        assert adapter.mock_mode is True
        await self._test_memory_adapter_lifecycle(adapter, sample_memories)


class TestVolcengineAgentKitMemory(TestMemoryAdapters):
    """火山引擎 AgentKit Memory 适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_memories):
        """测试 Mock 模式"""
        from src.adapters.memory.volcengine_agentkit_memory import VolcengineAgentKitMemoryAdapter

        adapter = VolcengineAgentKitMemoryAdapter({})
        assert adapter.mock_mode is True
        await self._test_memory_adapter_lifecycle(adapter, sample_memories)


class TestAlibabaBailianMemory(TestMemoryAdapters):
    """阿里百炼 Memory 适配器测试"""

    @pytest.mark.asyncio
    async def test_mock_mode(self, sample_memories):
        """测试 Mock 模式"""
        from src.adapters.memory.alibaba_bailian_memory import AlibabaBailianMemoryAdapter

        adapter = AlibabaBailianMemoryAdapter({})
        assert adapter.mock_mode is True
        await self._test_memory_adapter_lifecycle(adapter, sample_memories)


# ==================== 集成测试 ====================


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_all_kb_adapters_load(self):
        """测试所有知识库适配器能正确加载"""
        from src.adapters.knowledge_base import (
            AWSBedrockKBAdapter,
            VolcengineVikingDBAdapter,
            AlibabaBailianAdapter,
            GoogleDialogflowCXAdapter,
            HuaweiCSSAdapter,
        )

        adapters = [
            AWSBedrockKBAdapter({}),
            VolcengineVikingDBAdapter({}),
            AlibabaBailianAdapter({}),
            GoogleDialogflowCXAdapter({}),
            HuaweiCSSAdapter({}),
        ]

        for adapter in adapters:
            assert adapter is not None
            assert hasattr(adapter, 'initialize')
            assert hasattr(adapter, 'query')

    @pytest.mark.asyncio
    async def test_all_memory_adapters_load(self):
        """测试所有记忆适配器能正确加载"""
        from src.adapters.memory import (
            AWSBedrockMemoryAdapter,
            GoogleVertexMemoryAdapter,
            VolcengineAgentKitMemoryAdapter,
            AlibabaBailianMemoryAdapter,
        )

        adapters = [
            AWSBedrockMemoryAdapter({}),
            GoogleVertexMemoryAdapter({}),
            VolcengineAgentKitMemoryAdapter({}),
            AlibabaBailianMemoryAdapter({}),
        ]

        for adapter in adapters:
            assert adapter is not None
            assert hasattr(adapter, 'initialize')
            assert hasattr(adapter, 'add_memory')
            assert hasattr(adapter, 'search_memory')

    @pytest.mark.asyncio
    async def test_concurrent_queries(self):
        """测试并发查询"""
        from src.adapters.knowledge_base.aws_bedrock_kb import AWSBedrockKBAdapter

        adapter = AWSBedrockKBAdapter({})
        await adapter.initialize()

        # 添加测试文档
        docs = [
            Document(id=f"doc{i}", content=f"测试文档 {i}", title=f"Doc {i}")
            for i in range(10)
        ]
        await adapter.upload_documents(docs)
        await adapter.build_index()

        # 并发查询
        tasks = [
            adapter.query(f"测试 {i}", top_k=3)
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result in results:
            assert result is not None

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """测试错误处理"""
        from src.adapters.knowledge_base.aws_bedrock_kb import AWSBedrockKBAdapter

        adapter = AWSBedrockKBAdapter({})

        # 未初始化时查询应该抛出异常
        with pytest.raises(RuntimeError):
            await adapter.query("test")

    @pytest.mark.asyncio
    async def test_edge_cases(self):
        """测试边界情况"""
        from src.adapters.knowledge_base.aws_bedrock_kb import AWSBedrockKBAdapter

        adapter = AWSBedrockKBAdapter({})
        await adapter.initialize()

        # 空文档列表
        result = await adapter.upload_documents([])
        assert result.success_count == 0

        # 空查询
        query_result = await adapter.query("", top_k=5)
        assert query_result is not None

        # top_k = 0
        query_result = await adapter.query("test", top_k=0)
        assert len(query_result.documents) == 0

        await adapter.cleanup()


# ==================== 性能测试 ====================


class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_large_batch_upload(self):
        """测试大批量上传"""
        from src.adapters.knowledge_base.volcengine_vikingdb import VolcengineVikingDBAdapter

        adapter = VolcengineVikingDBAdapter({})
        await adapter.initialize()

        # 创建 100 个文档
        docs = [
            Document(
                id=f"doc{i}",
                content=f"这是测试文档 {i}，包含一些随机内容用于测试",
                title=f"Document {i}"
            )
            for i in range(100)
        ]

        result = await adapter.upload_documents(docs)
        assert result.success_count == 100

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_query_latency(self):
        """测试查询延迟"""
        from src.adapters.knowledge_base.alibaba_bailian import AlibabaBailianAdapter
        import time

        adapter = AlibabaBailianAdapter({})
        await adapter.initialize()

        # 添加文档
        docs = [Document(id=f"doc{i}", content=f"测试 {i}") for i in range(10)]
        await adapter.upload_documents(docs)
        await adapter.build_index()

        # 测试查询延迟
        start = time.time()
        result = await adapter.query("测试", top_k=5)
        elapsed = (time.time() - start) * 1000

        assert result.latency_ms > 0
        # Mock 模式应该很快
        assert elapsed < 100  # 应该在 100ms 内完成

        await adapter.cleanup()


# ==================== 配置测试 ====================


class TestConfiguration:
    """配置测试"""

    @pytest.mark.asyncio
    async def test_config_validation(self):
        """测试配置验证"""
        from src.adapters.knowledge_base.aws_bedrock_kb import AWSBedrockKBAdapter

        # 空配置应该启用 Mock 模式
        adapter = AWSBedrockKBAdapter({})
        assert adapter.mock_mode is True

        # 有 KB ID 应该启用真实模式
        adapter2 = AWSBedrockKBAdapter({"knowledge_base_id": "test-kb-id"})
        assert adapter2.mock_mode is False

    @pytest.mark.asyncio
    async def test_multiple_adapters_isolation(self):
        """测试多个适配器之间的隔离"""
        from src.adapters.knowledge_base.aws_bedrock_kb import AWSBedrockKBAdapter

        adapter1 = AWSBedrockKBAdapter({})
        adapter2 = AWSBedrockKBAdapter({})

        await adapter1.initialize()
        await adapter2.initialize()

        # 在 adapter1 中添加文档
        docs = [Document(id="doc1", content="测试文档")]
        await adapter1.upload_documents(docs)
        await adapter1.build_index()

        # adapter2 不应该看到 adapter1 的文档
        result = await adapter2.query("测试", top_k=5)
        assert len(result.documents) == 0

        await adapter1.cleanup()
        await adapter2.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
