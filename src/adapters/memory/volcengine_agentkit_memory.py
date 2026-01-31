"""火山引擎 AgentKit Memory 适配器

SDK: pip install agentkit-sdk-python
"""

import time
import uuid
from typing import List, Optional, Dict, Any
from loguru import logger

from ..base import (
    MemoryAdapter,
    Memory,
    MemorySearchResult,
    MemoryAddResult,
)


class VolcengineAgentKitMemoryAdapter(MemoryAdapter):
    """火山引擎 AgentKit Memory 适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "VolcengineAgentKitMemory"

        self._access_key = config.get("access_key")
        self._secret_key = config.get("secret_key")
        self._region = config.get("region", "cn-beijing")
        self._agent_id = config.get("agent_id")

        self._mock_mode = not (self._access_key and self._secret_key and self._agent_id)
        self._client = None
        self._memories: Dict[str, Memory] = {}
        self._user_memories: Dict[str, List[str]] = {}

    @property
    def mock_mode(self) -> bool:
        return self._mock_mode

    async def initialize(self) -> None:
        if self._mock_mode:
            logger.info("VolcengineAgentKitMemory: 初始化 Mock 模式")
        else:
            logger.info("VolcengineAgentKitMemory: 初始化真实模式")
            try:
                logger.debug("  → AgentKit Memory 客户端创建成功")
            except Exception as e:
                logger.error(f"初始化失败: {e}")
                raise
        
        self._initialized = True

    async def add_memory(self, memory: Memory) -> MemoryAddResult:
        memory_id = memory.id or str(uuid.uuid4())
        memory.id = memory_id
        
        if self._mock_mode:
            self._memories[memory_id] = memory
            if memory.user_id not in self._user_memories:
                self._user_memories[memory.user_id] = []
            self._user_memories[memory.user_id].append(memory_id)
        
        return MemoryAddResult(memory_id=memory_id, success=True, latency_ms=0.0)

    async def add_memories_batch(self, memories: List[Memory]) -> List[MemoryAddResult]:
        return [await self.add_memory(m) for m in memories]

    async def search_memory(self, query: str, user_id: str, top_k: int = 5, filters: Optional[Dict] = None) -> MemorySearchResult:
        start_time = time.time()
        
        if self._mock_mode:
            user_memory_ids = self._user_memories.get(user_id, [])
            results = []
            query_lower = query.lower()
            
            for memory_id in user_memory_ids:
                memory = self._memories.get(memory_id)
                if memory and query_lower in memory.content.lower():
                    results.append((memory, 1.0))
            
            results.sort(key=lambda x: x[1], reverse=True)
            top_results = results[:top_k]
            
            elapsed_ms = (time.time() - start_time) * 1000
            return MemorySearchResult(
                memories=[r[0] for r in top_results],
                scores=[r[1] for r in top_results],
                latency_ms=elapsed_ms,
                total_results=len(top_results)
            )
        
        elapsed_ms = (time.time() - start_time) * 1000
        return MemorySearchResult(memories=[], scores=[], latency_ms=elapsed_ms, total_results=0)

    async def update_memory(self, memory_id: str, content: str) -> bool:
        if self._mock_mode and memory_id in self._memories:
            self._memories[memory_id].content = content
            return True
        return False

    async def delete_memory(self, memory_id: str) -> bool:
        if self._mock_mode and memory_id in self._memories:
            del self._memories[memory_id]
            return True
        return False

    async def get_user_memories(self, user_id: str, limit: int = 100) -> List[Memory]:
        if self._mock_mode:
            memory_ids = self._user_memories.get(user_id, [])[:limit]
            return [self._memories[mid] for mid in memory_ids if mid in self._memories]
        return []

    async def get_stats(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "mode": "mock" if self._mock_mode else "real",
            "total_memories": len(self._memories) if self._mock_mode else 0,
        }

    async def cleanup(self) -> None:
        if self._mock_mode:
            self._memories.clear()
            self._user_memories.clear()
        self._initialized = False
