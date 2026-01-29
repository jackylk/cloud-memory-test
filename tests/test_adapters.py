"""适配器单元测试"""

import pytest
import asyncio
from datetime import datetime

from src.adapters.base import Document, DocumentFormat, Memory
from src.adapters.knowledge_base import SimpleVectorStore, MilvusAdapter, PineconeAdapter
from src.adapters.memory import Mem0LocalAdapter, MilvusMemoryAdapter


class TestSimpleVectorStore:
    """SimpleVectorStore 适配器测试"""

    @pytest.fixture
    def adapter(self):
        """创建测试适配器"""
        return SimpleVectorStore({
            "similarity_threshold": 0.1
        })

    @pytest.fixture
    def sample_documents(self):
        """创建测试文档"""
        return [
            Document(
                id="doc_001",
                content="机器学习是人工智能的一个分支，它使计算机能够从数据中学习。",
                format=DocumentFormat.TXT,
                title="机器学习基础"
            ),
            Document(
                id="doc_002",
                content="深度学习是机器学习的子集，使用多层神经网络。",
                format=DocumentFormat.TXT,
                title="深度学习入门"
            ),
            Document(
                id="doc_003",
                content="自然语言处理让计算机理解人类语言。",
                format=DocumentFormat.TXT,
                title="NLP简介"
            ),
        ]

    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        """测试初始化"""
        await adapter.initialize()
        assert adapter.is_initialized
        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_upload_and_query(self, adapter, sample_documents):
        """测试文档上传和查询"""
        await adapter.initialize()

        # 上传文档
        result = await adapter.upload_documents(sample_documents)
        assert result.success_count == 3
        assert result.failed_count == 0

        # 构建索引
        index_result = await adapter.build_index()
        assert index_result.success
        assert index_result.doc_count == 3

        # 查询
        query_result = await adapter.query("机器学习", top_k=3)
        assert query_result.total_results > 0
        assert query_result.latency_ms > 0

        await adapter.cleanup()


class TestMilvusAdapter:
    """Milvus 适配器测试"""

    @pytest.fixture
    def adapter(self):
        """创建测试适配器"""
        return MilvusAdapter({
            "collection_name": f"test_kb_{datetime.now().strftime('%H%M%S%f')}",
            "dimension": 384,
            "db_path": "./test_milvus_kb.db",
            "use_lite": True
        })

    @pytest.fixture
    def sample_documents(self):
        """创建测试文档"""
        return [
            Document(
                id="doc_001",
                content="机器学习是人工智能的一个分支，它使计算机能够从数据中学习。",
                format=DocumentFormat.TXT,
                title="机器学习基础"
            ),
            Document(
                id="doc_002",
                content="深度学习是机器学习的子集，使用多层神经网络。",
                format=DocumentFormat.TXT,
                title="深度学习入门"
            ),
            Document(
                id="doc_003",
                content="自然语言处理让计算机理解人类语言。",
                format=DocumentFormat.TXT,
                title="NLP简介"
            ),
        ]

    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        """测试初始化"""
        await adapter.initialize()
        assert adapter.is_initialized
        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_upload_documents(self, adapter, sample_documents):
        """测试文档上传"""
        await adapter.initialize()

        result = await adapter.upload_documents(sample_documents)

        assert result.success_count == 3
        assert result.failed_count == 0
        assert result.total_time_ms > 0

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_query(self, adapter, sample_documents):
        """测试查询"""
        await adapter.initialize()
        await adapter.upload_documents(sample_documents)

        result = await adapter.query("什么是机器学习？", top_k=3)

        assert result.total_results > 0
        assert result.latency_ms > 0
        assert len(result.documents) <= 3
        assert len(result.scores) == len(result.documents)

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_build_index(self, adapter, sample_documents):
        """测试构建索引"""
        await adapter.initialize()
        await adapter.upload_documents(sample_documents)

        result = await adapter.build_index()

        assert result.success
        assert result.doc_count == 3
        assert result.index_time_ms >= 0

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_delete_documents(self, adapter, sample_documents):
        """测试删除文档"""
        await adapter.initialize()
        await adapter.upload_documents(sample_documents)

        result = await adapter.delete_documents(["doc_001"])

        assert result["success"]
        assert result["deleted_count"] == 1

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_get_stats(self, adapter, sample_documents):
        """测试获取统计信息"""
        await adapter.initialize()
        await adapter.upload_documents(sample_documents)

        stats = await adapter.get_stats()

        assert stats["initialized"]
        assert stats["document_count"] == 3

        await adapter.cleanup()


class TestPineconeAdapter:
    """Pinecone 适配器测试（模拟模式）"""

    @pytest.fixture
    def adapter(self):
        """创建测试适配器（模拟模式）"""
        return PineconeAdapter({
            "index_name": f"test_kb_{datetime.now().strftime('%H%M%S%f')}",
            "dimension": 384,
            "mock_mode": True  # 使用模拟模式，不需要 API Key
        })

    @pytest.fixture
    def sample_documents(self):
        """创建测试文档"""
        return [
            Document(
                id="doc_001",
                content="机器学习是人工智能的一个分支，它使计算机能够从数据中学习。",
                format=DocumentFormat.TXT,
                title="机器学习基础"
            ),
            Document(
                id="doc_002",
                content="深度学习是机器学习的子集，使用多层神经网络。",
                format=DocumentFormat.TXT,
                title="深度学习入门"
            ),
            Document(
                id="doc_003",
                content="自然语言处理让计算机理解人类语言。",
                format=DocumentFormat.TXT,
                title="NLP简介"
            ),
        ]

    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        """测试初始化"""
        await adapter.initialize()
        assert adapter.is_initialized
        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_upload_documents(self, adapter, sample_documents):
        """测试文档上传"""
        await adapter.initialize()

        result = await adapter.upload_documents(sample_documents)

        assert result.success_count == 3
        assert result.failed_count == 0
        assert result.total_time_ms > 0

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_query(self, adapter, sample_documents):
        """测试查询"""
        await adapter.initialize()
        await adapter.upload_documents(sample_documents)

        result = await adapter.query("什么是机器学习？", top_k=3)

        assert result.total_results > 0
        assert result.latency_ms > 0
        assert len(result.documents) <= 3
        assert len(result.scores) == len(result.documents)

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_build_index(self, adapter, sample_documents):
        """测试构建索引"""
        await adapter.initialize()
        await adapter.upload_documents(sample_documents)

        result = await adapter.build_index()

        assert result.success
        assert result.doc_count == 3
        assert result.index_time_ms >= 0

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_delete_documents(self, adapter, sample_documents):
        """测试删除文档"""
        await adapter.initialize()
        await adapter.upload_documents(sample_documents)

        result = await adapter.delete_documents(["doc_001"])

        assert result["success"]
        assert result["deleted_count"] == 1

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_get_stats(self, adapter, sample_documents):
        """测试获取统计信息"""
        await adapter.initialize()
        await adapter.upload_documents(sample_documents)

        stats = await adapter.get_stats()

        assert stats["initialized"]
        assert stats["mode"] == "mock"
        assert stats["document_count"] == 3

        await adapter.cleanup()


class TestMem0LocalAdapter:
    """mem0 本地适配器测试"""

    @pytest.fixture
    def adapter(self):
        """创建测试适配器"""
        return Mem0LocalAdapter({
            "use_simple_store": True,  # 使用简单存储模式
        })

    @pytest.fixture
    def sample_memories(self):
        """创建测试记忆"""
        return [
            Memory(
                id=None,
                user_id="user_001",
                content="用户喜欢机器学习相关的内容",
                memory_type="preference"
            ),
            Memory(
                id=None,
                user_id="user_001",
                content="用户正在学习深度学习课程",
                memory_type="fact"
            ),
            Memory(
                id=None,
                user_id="user_002",
                content="用户对自然语言处理感兴趣",
                memory_type="preference"
            ),
        ]

    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        """测试初始化"""
        await adapter.initialize()
        assert adapter.is_initialized
        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_add_memory(self, adapter, sample_memories):
        """测试添加记忆"""
        await adapter.initialize()

        result = await adapter.add_memory(sample_memories[0])

        assert result.success
        assert result.memory_id
        assert result.latency_ms >= 0

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_add_memories_batch(self, adapter, sample_memories):
        """测试批量添加记忆"""
        await adapter.initialize()

        results = await adapter.add_memories_batch(sample_memories)

        assert len(results) == 3
        assert all(r.success for r in results)

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_search_memory(self, adapter, sample_memories):
        """测试搜索记忆"""
        await adapter.initialize()
        await adapter.add_memories_batch(sample_memories)

        result = await adapter.search_memory("机器学习", "user_001", top_k=5)

        assert result.latency_ms >= 0
        # 简单存储模式下，至少应该找到包含"机器学习"的记忆
        assert result.total_results >= 1

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_get_user_memories(self, adapter, sample_memories):
        """测试获取用户记忆"""
        await adapter.initialize()
        await adapter.add_memories_batch(sample_memories)

        memories = await adapter.get_user_memories("user_001")

        assert len(memories) == 2  # user_001 有2条记忆

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_delete_memory(self, adapter, sample_memories):
        """测试删除记忆"""
        await adapter.initialize()
        results = await adapter.add_memories_batch(sample_memories)
        memory_id = results[0].memory_id

        success = await adapter.delete_memory(memory_id)

        assert success

        # 验证删除后获取不到
        memories = await adapter.get_user_memories("user_001")
        assert len(memories) == 1

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_get_stats(self, adapter, sample_memories):
        """测试获取统计信息"""
        await adapter.initialize()
        await adapter.add_memories_batch(sample_memories)

        stats = await adapter.get_stats()

        assert stats["initialized"]
        assert stats["total_memories"] == 3
        assert stats["unique_users"] == 2

        await adapter.cleanup()


class TestMilvusMemoryAdapter:
    """Milvus 记忆系统适配器测试"""

    @pytest.fixture
    def adapter(self):
        """创建测试适配器"""
        return MilvusMemoryAdapter({
            "collection_name": f"test_mem_{datetime.now().strftime('%H%M%S%f')}",
            "dimension": 384,
            "db_path": "./test_milvus_mem.db",
            "use_lite": True
        })

    @pytest.fixture
    def sample_memories(self):
        """创建测试记忆"""
        return [
            Memory(
                id=None,
                user_id="user_001",
                content="用户喜欢机器学习相关的内容",
                memory_type="preference"
            ),
            Memory(
                id=None,
                user_id="user_001",
                content="用户正在学习深度学习课程",
                memory_type="fact"
            ),
            Memory(
                id=None,
                user_id="user_002",
                content="用户对自然语言处理感兴趣",
                memory_type="preference"
            ),
        ]

    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        """测试初始化"""
        await adapter.initialize()
        assert adapter.is_initialized
        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_add_memory(self, adapter, sample_memories):
        """测试添加记忆"""
        await adapter.initialize()

        result = await adapter.add_memory(sample_memories[0])

        assert result.success
        assert result.memory_id
        assert result.latency_ms >= 0

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_add_memories_batch(self, adapter, sample_memories):
        """测试批量添加记忆"""
        await adapter.initialize()

        results = await adapter.add_memories_batch(sample_memories)

        assert len(results) == 3
        assert all(r.success for r in results)

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_search_memory(self, adapter, sample_memories):
        """测试搜索记忆"""
        await adapter.initialize()
        await adapter.add_memories_batch(sample_memories)

        result = await adapter.search_memory("机器学习", "user_001", top_k=5)

        assert result.latency_ms >= 0
        # Milvus 使用向量搜索，结果可能不同于关键词匹配

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_get_user_memories(self, adapter, sample_memories):
        """测试获取用户记忆"""
        await adapter.initialize()
        await adapter.add_memories_batch(sample_memories)

        memories = await adapter.get_user_memories("user_001")

        assert len(memories) == 2  # user_001 有2条记忆

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_delete_memory(self, adapter, sample_memories):
        """测试删除记忆"""
        await adapter.initialize()
        results = await adapter.add_memories_batch(sample_memories)
        memory_id = results[0].memory_id

        success = await adapter.delete_memory(memory_id)

        assert success

        await adapter.cleanup()

    @pytest.mark.asyncio
    async def test_get_stats(self, adapter, sample_memories):
        """测试获取统计信息"""
        await adapter.initialize()
        await adapter.add_memories_batch(sample_memories)

        stats = await adapter.get_stats()

        assert stats["initialized"]
        assert stats["total_memories"] == 3

        await adapter.cleanup()


# 运行测试的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
