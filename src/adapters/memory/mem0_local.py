"""mem0 本地适配器 - 用于本地调试和作为对比基准"""

import time
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


class Mem0LocalAdapter(MemoryAdapter):
    """mem0 本地记忆系统适配器

    使用 mem0 开源库在本地运行，可以作为：
    1. 本地调试环境
    2. 与云服务对比的基准
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.vector_store = config.get("vector_store", "chroma")
        self.embedding_model = config.get("embedding_model", "all-MiniLM-L6-v2")

        self._memory = None
        self._use_simple_store = config.get("use_simple_store", True)
        self._simple_memories: Dict[str, Memory] = {}  # 简单内存存储用于调试

    async def initialize(self) -> None:
        """初始化 mem0"""
        logger.debug("初始化 mem0 适配器")
        logger.debug(f"  → 向量存储: {self.vector_store}")
        logger.debug(f"  → Embedding 模型: {self.embedding_model}")
        logger.debug(f"  → 简单存储模式: {self._use_simple_store}")

        if self._use_simple_store:
            # 使用简单的内存存储，避免依赖复杂配置
            logger.debug("  → 使用简单内存存储模式（调试用）")
            self._simple_memories = {}
            self._initialized = True
            return

        try:
            from mem0 import Memory as Mem0Memory

            # 配置 mem0
            config = {
                "vector_store": {
                    "provider": self.vector_store,
                    "config": {
                        "collection_name": "benchmark_memories",
                    }
                },
                "embedder": {
                    "provider": "huggingface",
                    "config": {
                        "model": self.embedding_model
                    }
                }
            }

            self._memory = Mem0Memory.from_config(config)
            self._initialized = True
            logger.debug("  → mem0 初始化完成")

        except ImportError as e:
            logger.warning(f"mem0 导入失败，使用简单存储模式: {e}")
            self._use_simple_store = True
            self._simple_memories = {}
            self._initialized = True
        except Exception as e:
            logger.warning(f"mem0 初始化失败，使用简单存储模式: {e}")
            self._use_simple_store = True
            self._simple_memories = {}
            self._initialized = True

    async def add_memory(self, memory: Memory) -> MemoryAddResult:
        """添加单条记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        try:
            if self._use_simple_store:
                # 简单存储模式
                memory_id = memory.id or str(uuid.uuid4())
                memory.id = memory_id
                self._simple_memories[memory_id] = memory

                elapsed_ms = (time.time() - start_time) * 1000
                logger.debug(f"  → 添加记忆: {memory_id} (简单模式)")

                return MemoryAddResult(
                    memory_id=memory_id,
                    success=True,
                    latency_ms=elapsed_ms
                )

            # mem0 模式
            result = self._memory.add(
                memory.content,
                user_id=memory.user_id,
                metadata={
                    "session_id": memory.session_id,
                    "memory_type": memory.memory_type,
                    "timestamp": memory.timestamp.isoformat(),
                    **memory.metadata
                }
            )

            elapsed_ms = (time.time() - start_time) * 1000
            memory_id = result.get("id", str(uuid.uuid4()))

            logger.debug(f"  → 添加记忆: {memory_id}")

            return MemoryAddResult(
                memory_id=memory_id,
                success=True,
                latency_ms=elapsed_ms,
                details=result
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
        for i, memory in enumerate(memories):
            result = await self.add_memory(memory)
            results.append(result)
            if (i + 1) % 10 == 0:
                logger.debug(f"  → 批量添加进度: {i + 1}/{len(memories)}")
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
        logger.debug(f"搜索记忆: '{query[:50]}...' (user={user_id}, top_k={top_k})")

        try:
            if self._use_simple_store:
                # 简单存储模式 - 基于关键词/子串匹配
                user_memories = [
                    m for m in self._simple_memories.values()
                    if m.user_id == user_id
                ]

                # 简单的匹配评分 - 支持中英文
                scored_memories = []
                query_lower = query.lower()

                for mem in user_memories:
                    content_lower = mem.content.lower()
                    # 方法1: 直接子串匹配
                    if query_lower in content_lower:
                        score = len(query_lower) / len(content_lower)
                        scored_memories.append((mem, score))
                    else:
                        # 方法2: 英文单词匹配
                        query_words = set(query_lower.split())
                        content_words = set(content_lower.split())
                        overlap = len(query_words & content_words)
                        if overlap > 0:
                            score = overlap / max(len(query_words), 1)
                            scored_memories.append((mem, score * 0.5))  # 降权

                # 排序并取 top_k
                scored_memories.sort(key=lambda x: x[1], reverse=True)
                top_memories = scored_memories[:top_k]

                elapsed_ms = (time.time() - start_time) * 1000

                return MemorySearchResult(
                    memories=[m for m, _ in top_memories],
                    scores=[s for _, s in top_memories],
                    latency_ms=elapsed_ms,
                    total_results=len(top_memories)
                )

            # mem0 模式
            results = self._memory.search(
                query,
                user_id=user_id,
                limit=top_k
            )

            elapsed_ms = (time.time() - start_time) * 1000

            memories = []
            scores = []

            for item in results:
                mem = Memory(
                    id=item.get("id"),
                    user_id=user_id,
                    content=item.get("memory", ""),
                    metadata=item.get("metadata", {}),
                    timestamp=datetime.fromisoformat(
                        item.get("metadata", {}).get("timestamp", datetime.now().isoformat())
                    )
                )
                memories.append(mem)
                scores.append(item.get("score", 0.0))

            logger.debug(f"搜索完成: 返回 {len(memories)} 条记忆, 耗时 {elapsed_ms:.2f}ms")

            return MemorySearchResult(
                memories=memories,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(memories)
            )

        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            elapsed_ms = (time.time() - start_time) * 1000
            return MemorySearchResult(
                memories=[],
                scores=[],
                latency_ms=elapsed_ms,
                total_results=0
            )

    async def update_memory(self, memory_id: str, content: str) -> bool:
        """更新记忆内容"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        try:
            if self._use_simple_store:
                if memory_id in self._simple_memories:
                    self._simple_memories[memory_id].content = content
                    logger.debug(f"更新记忆: {memory_id}")
                    return True
                return False

            self._memory.update(memory_id, content)
            logger.debug(f"更新记忆: {memory_id}")
            return True

        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False

    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        try:
            if self._use_simple_store:
                if memory_id in self._simple_memories:
                    del self._simple_memories[memory_id]
                    logger.debug(f"删除记忆: {memory_id}")
                    return True
                return False

            self._memory.delete(memory_id)
            logger.debug(f"删除记忆: {memory_id}")
            return True

        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            return False

    async def get_user_memories(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[Memory]:
        """获取用户所有记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        try:
            if self._use_simple_store:
                user_memories = [
                    m for m in self._simple_memories.values()
                    if m.user_id == user_id
                ]
                return user_memories[:limit]

            results = self._memory.get_all(user_id=user_id, limit=limit)

            memories = []
            for item in results:
                mem = Memory(
                    id=item.get("id"),
                    user_id=user_id,
                    content=item.get("memory", ""),
                    metadata=item.get("metadata", {}),
                    timestamp=datetime.fromisoformat(
                        item.get("metadata", {}).get("timestamp", datetime.now().isoformat())
                    )
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

        if self._use_simple_store:
            return {
                "initialized": True,
                "mode": "simple_store",
                "total_memories": len(self._simple_memories),
                "unique_users": len(set(m.user_id for m in self._simple_memories.values()))
            }

        # mem0 模式暂时返回基本信息
        return {
            "initialized": True,
            "mode": "mem0",
            "vector_store": self.vector_store,
            "embedding_model": self.embedding_model
        }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._use_simple_store:
            self._simple_memories.clear()
        self._memory = None
        self._initialized = False
        logger.debug("mem0 适配器已清理")
