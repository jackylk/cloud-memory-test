"""基于 Milvus 的记忆系统适配器"""

import time
import hashlib
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from loguru import logger

from ..base import (
    MemoryAdapter,
    Memory,
    MemorySearchResult,
    MemoryAddResult,
)


class MilvusMemoryAdapter(MemoryAdapter):
    """基于 Milvus 的记忆系统适配器

    使用 Milvus Lite 进行本地测试。
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "MilvusMemoryAdapter"

        self.collection_name = config.get("collection_name", "benchmark_memory")
        self.dimension = config.get("dimension", 384)
        self.db_path = config.get("db_path", "./milvus_memory.db")
        self._use_lite = config.get("use_lite", True)

        self._client = None

    async def initialize(self) -> None:
        """初始化 Milvus 连接"""
        logger.debug("初始化 MilvusMemoryAdapter")
        logger.debug(f"  → Collection: {self.collection_name}")
        logger.debug(f"  → 向量维度: {self.dimension}")

        try:
            from pymilvus import MilvusClient

            if self._use_lite:
                self._client = MilvusClient(self.db_path)
                logger.debug(f"  → 使用 Milvus Lite: {self.db_path}")
            else:
                uri = self.config.get("uri", "http://localhost:19530")
                self._client = MilvusClient(uri=uri)

            # 删除旧 collection（如果存在）
            if self._client.has_collection(self.collection_name):
                self._client.drop_collection(self.collection_name)

            self._initialized = True
            logger.debug("  → 初始化完成")

        except ImportError as e:
            raise ImportError("请安装 pymilvus: pip install pymilvus") from e
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise

    def _text_to_vector(self, text: str) -> List[float]:
        """简单的文本转向量"""
        hash_bytes = hashlib.sha384(text.encode()).digest()
        vector = []
        for i in range(0, len(hash_bytes), 2):
            val = int.from_bytes(hash_bytes[i:i+2], 'big')
            vector.append((val / 32768.0) - 1.0)
        while len(vector) < self.dimension:
            vector.extend(vector[:self.dimension - len(vector)])
        return vector[:self.dimension]

    async def add_memory(self, memory: Memory) -> MemoryAddResult:
        """添加单条记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        try:
            memory_id = memory.id or str(uuid.uuid4())
            vector = self._text_to_vector(memory.content)

            data = [{
                "id": hash(memory_id) % (2**63),
                "memory_id": memory_id,
                "user_id": memory.user_id,
                "content": memory.content,
                "session_id": memory.session_id or "",
                "memory_type": memory.memory_type,
                "timestamp": memory.timestamp.isoformat(),
                "vector": vector
            }]

            # 确保 collection 存在
            if not self._client.has_collection(self.collection_name):
                self._client.create_collection(
                    collection_name=self.collection_name,
                    dimension=self.dimension,
                    auto_id=False
                )

            self._client.insert(
                collection_name=self.collection_name,
                data=data
            )

            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"  → 添加记忆: {memory_id}")

            return MemoryAddResult(
                memory_id=memory_id,
                success=True,
                latency_ms=elapsed_ms
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"添加记忆失败: {e}")
            return MemoryAddResult(
                memory_id="",
                success=False,
                latency_ms=elapsed_ms,
                details={"error": str(e)}
            )

    async def add_memories_batch(self, memories: List[Memory]) -> List[MemoryAddResult]:
        """批量添加记忆"""
        results = []
        for memory in memories:
            result = await self.add_memory(memory)
            results.append(result)
        return results

    async def search_memory(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> MemorySearchResult:
        """搜索相关记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        logger.debug(f"搜索记忆: '{query[:50]}...' (user={user_id})")

        try:
            if not self._client.has_collection(self.collection_name):
                return MemorySearchResult(
                    memories=[],
                    scores=[],
                    latency_ms=(time.time() - start_time) * 1000,
                    total_results=0
                )

            query_vector = self._text_to_vector(query)

            # 搜索
            results = self._client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=top_k * 2,  # 多搜一些再过滤
                output_fields=["memory_id", "user_id", "content", "session_id", "memory_type", "timestamp"],
                filter=f'user_id == "{user_id}"' if user_id else None
            )

            elapsed_ms = (time.time() - start_time) * 1000

            memories = []
            scores = []

            if results and len(results) > 0:
                for hit in results[0][:top_k]:
                    entity = hit.get("entity", {})
                    # 只返回匹配用户的记忆
                    if entity.get("user_id") == user_id:
                        mem = Memory(
                            id=entity.get("memory_id"),
                            user_id=entity.get("user_id", ""),
                            content=entity.get("content", ""),
                            session_id=entity.get("session_id"),
                            memory_type=entity.get("memory_type", "general"),
                            timestamp=datetime.fromisoformat(entity.get("timestamp", datetime.now().isoformat()))
                        )
                        memories.append(mem)
                        distance = hit.get("distance", 0)
                        scores.append(1 / (1 + distance))

            logger.debug(f"搜索完成: {len(memories)} 条记忆, 耗时 {elapsed_ms:.2f}ms")

            return MemorySearchResult(
                memories=memories,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(memories)
            )

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return MemorySearchResult(
                memories=[],
                scores=[],
                latency_ms=(time.time() - start_time) * 1000,
                total_results=0
            )

    async def update_memory(self, memory_id: str, content: str) -> bool:
        """更新记忆 - Milvus 不直接支持更新，需要删除再插入"""
        logger.warning("Milvus 不支持直接更新，跳过")
        return False

    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        try:
            int_id = hash(memory_id) % (2**63)
            self._client.delete(
                collection_name=self.collection_name,
                ids=[int_id]
            )
            return True
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False

    async def get_user_memories(self, user_id: str, limit: int = 100) -> List[Memory]:
        """获取用户所有记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        try:
            if not self._client.has_collection(self.collection_name):
                return []

            # 使用空向量搜索并过滤
            dummy_vector = [0.0] * self.dimension
            results = self._client.search(
                collection_name=self.collection_name,
                data=[dummy_vector],
                limit=limit,
                output_fields=["memory_id", "user_id", "content", "session_id", "memory_type", "timestamp"],
                filter=f'user_id == "{user_id}"'
            )

            memories = []
            if results and len(results) > 0:
                for hit in results[0]:
                    entity = hit.get("entity", {})
                    if entity.get("user_id") == user_id:
                        mem = Memory(
                            id=entity.get("memory_id"),
                            user_id=entity.get("user_id", ""),
                            content=entity.get("content", ""),
                            session_id=entity.get("session_id"),
                            memory_type=entity.get("memory_type", "general"),
                            timestamp=datetime.fromisoformat(entity.get("timestamp", datetime.now().isoformat()))
                        )
                        memories.append(mem)

            return memories

        except Exception as e:
            logger.error(f"获取用户记忆失败: {e}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            return {"initialized": False}

        try:
            if self._client.has_collection(self.collection_name):
                stats = self._client.get_collection_stats(self.collection_name)
                return {
                    "initialized": True,
                    "collection_name": self.collection_name,
                    "total_memories": stats.get("row_count", 0),
                    "dimension": self.dimension
                }
        except Exception:
            pass

        return {
            "initialized": True,
            "collection_name": self.collection_name,
            "total_memories": 0
        }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._client:
            try:
                if self._client.has_collection(self.collection_name):
                    self._client.drop_collection(self.collection_name)
                self._client.close()
            except Exception as e:
                logger.warning(f"清理时发生错误: {e}")

        self._client = None
        self._initialized = False
        logger.debug("MilvusMemoryAdapter 已清理")
