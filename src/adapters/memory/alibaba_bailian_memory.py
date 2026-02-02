"""阿里百炼长期记忆适配器

SDK: pip install alibabacloud-bailian20231229
"""

import time
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from loguru import logger

from ..base import (
    MemoryAdapter,
    Memory,
    MemorySearchResult,
    MemoryAddResult,
)


class AlibabaBailianMemoryAdapter(MemoryAdapter):
    """阿里百炼长期记忆适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "AlibabaBailianMemory"

        self._access_key_id = config.get("access_key_id")
        self._access_key_secret = config.get("access_key_secret")
        self._workspace_id = config.get("workspace_id")
        self._memory_id = config.get("memory_id")
        self._endpoint = config.get("endpoint", "bailian.cn-beijing.aliyuncs.com")

        # 如果缺少必要的配置，启用Mock模式
        self._mock_mode = not (
            self._access_key_id and 
            self._access_key_secret and 
            self._workspace_id and
            self._memory_id  # memory_id也是必需的
        )
        
        self._client = None
        self._memories: Dict[str, Memory] = {}
        self._user_memories: Dict[str, List[str]] = {}

    @property
    def mock_mode(self) -> bool:
        return self._mock_mode

    async def initialize(self) -> None:
        if self._mock_mode:
            logger.info("AlibabaBailianMemory: 初始化 Mock 模式")
            if not self._memory_id:
                logger.debug("  → 未配置 memory_id，使用Mock模式")
        else:
            logger.info("AlibabaBailianMemory: 初始化真实模式")
            try:
                from alibabacloud_bailian20231229.client import Client as BailianClient
                from alibabacloud_tea_openapi import models as open_api_models

                config = open_api_models.Config(
                    access_key_id=self._access_key_id,
                    access_key_secret=self._access_key_secret,
                    endpoint=self._endpoint
                )
                self._client = BailianClient(config)
                logger.debug("  → 百炼客户端创建成功")
                logger.debug(f"  → Memory ID: {self._memory_id}")
            except ImportError:
                logger.error("请安装: pip install alibabacloud-bailian20231229")
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
        
        # 真实模式
        try:
            from alibabacloud_bailian20231229 import models
            
            # 创建记忆节点请求
            request = models.CreateMemoryNodeRequest(
                content=memory.content
            )
            
            # 调用API，memory_id作为路径参数
            response = self._client.create_memory_node(
                self._workspace_id,
                self._memory_id,
                request
            )
            
            # 获取返回的节点ID（响应格式：response.body.memoryNodeId）
            if hasattr(response, 'body'):
                # 尝试多种可能的字段名
                memory_node_id = (
                    getattr(response.body, 'memoryNodeId', None) or
                    getattr(response.body, 'memory_node_id', None)
                )
                if memory_node_id:
                    memory_id = memory_node_id
                    logger.debug(f"  → 创建记忆节点成功: {memory_id}")
                else:
                    logger.warning(f"  → API返回无memory_node_id，使用fallback ID")
            else:
                logger.warning(f"  → API返回格式异常")
            
            # 限速：避免触发限流
            await asyncio.sleep(1)
            return MemoryAddResult(memory_id=memory_id, success=True, latency_ms=0.0)
            
        except Exception as e:
            logger.error(f"添加记忆失败: {e}")
            import traceback
            logger.debug(f"  → 错误详情: {traceback.format_exc()}")
            return MemoryAddResult(memory_id=memory_id, success=False, latency_ms=0.0)

    async def add_memories_batch(self, memories: List[Memory]) -> List[MemoryAddResult]:
        return [await self.add_memory(m) for m in memories]

    async def search_memory(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> MemorySearchResult:
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
            logger.debug(f"[Mock] 搜索记忆: 找到 {len(top_results)} 个结果")
            return MemorySearchResult(
                memories=[r[0] for r in top_results],
                scores=[r[1] for r in top_results],
                latency_ms=elapsed_ms,
                total_results=len(top_results)
            )

        # 真实模式：调用百炼长期记忆搜索API
        try:
            from alibabacloud_bailian20231229 import models

            # 列出记忆节点（百炼使用ListMemoryNodes接口）
            request = models.ListMemoryNodesRequest(
                max_results=top_k
            )

            # 调用API
            response = self._client.list_memory_nodes(
                self._workspace_id,
                self._memory_id,
                request
            )

            elapsed_ms = (time.time() - start_time) * 1000

            memories = []
            scores = []

            # 响应格式：response.body.memoryNodes (列表)
            if hasattr(response, 'body'):
                nodes = getattr(response.body, 'memoryNodes', None) or getattr(response.body, 'memory_nodes', [])

                if nodes:
                    for node in nodes:
                        content = getattr(node, 'content', '')
                        if content:
                            # 简单的关键词匹配评分
                            score = 1.0 if query.lower() in content.lower() else 0.5

                            memory_node_id = (
                                getattr(node, 'memoryNodeId', None) or
                                getattr(node, 'memory_node_id', str(uuid.uuid4()))
                            )

                            memory = Memory(
                                id=memory_node_id,
                                user_id=user_id,
                                content=content,
                                metadata={},
                                memory_type="long_term"
                            )
                            memories.append(memory)
                            scores.append(score)

            # 按分数排序并取top_k
            if memories:
                sorted_pairs = sorted(
                    zip(memories, scores),
                    key=lambda x: x[1],
                    reverse=True
                )[:top_k]
                memories = [m for m, _ in sorted_pairs]
                scores = [s for _, s in sorted_pairs]

            logger.debug(f"搜索记忆: 找到 {len(memories)} 个结果")

            return MemorySearchResult(
                memories=memories,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(memories)
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"搜索记忆失败: {e}")
            import traceback
            logger.debug(f"  → 错误详情: {traceback.format_exc()}")

            return MemorySearchResult(
                memories=[],
                scores=[],
                latency_ms=elapsed_ms,
                total_results=0
            )

    async def update_memory(self, memory_id: str, content: str) -> bool:
        if self._mock_mode:
            if memory_id in self._memories:
                self._memories[memory_id].content = content
                logger.debug(f"[Mock] 更新记忆: {memory_id}")
                return True
            return False

        # 真实模式：调用UpdateMemoryNode API
        try:
            from alibabacloud_bailian20231229 import models

            request = models.UpdateMemoryNodeRequest(
                content=content
            )

            self._client.update_memory_node(
                self._workspace_id,
                self._memory_id,
                memory_id,
                request
            )

            logger.debug(f"更新记忆成功: {memory_id}")
            await asyncio.sleep(0.5)  # 限速
            return True

        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False

    async def delete_memory(self, memory_id: str) -> bool:
        if self._mock_mode:
            if memory_id in self._memories:
                del self._memories[memory_id]
                logger.debug(f"[Mock] 删除记忆: {memory_id}")
                return True
            return False

        # 真实模式：调用DeleteMemoryNode API
        try:
            self._client.delete_memory_node(
                self._workspace_id,
                self._memory_id,
                memory_id
            )

            logger.debug(f"删除记忆成功: {memory_id}")
            await asyncio.sleep(0.5)  # 限速
            return True

        except Exception as e:
            logger.error(f"删除记忆失败: {e}")
            return False

    async def get_user_memories(self, user_id: str, limit: int = 100) -> List[Memory]:
        if self._mock_mode:
            memory_ids = self._user_memories.get(user_id, [])[:limit]
            memories = [self._memories[mid] for mid in memory_ids if mid in self._memories]
            logger.debug(f"[Mock] 获取用户记忆: {len(memories)} 个")
            return memories

        # 真实模式：列出所有记忆节点
        try:
            from alibabacloud_bailian20231229 import models

            request = models.ListMemoryNodesRequest(
                max_results=limit
            )

            response = self._client.list_memory_nodes(
                self._workspace_id,
                self._memory_id,
                request
            )

            memories = []
            # 响应格式：response.body.memoryNodes
            if hasattr(response, 'body'):
                nodes = getattr(response.body, 'memoryNodes', None) or getattr(response.body, 'memory_nodes', [])

                if nodes:
                    for node in nodes:
                        content = getattr(node, 'content', '')
                        if content:
                            memory_node_id = (
                                getattr(node, 'memoryNodeId', None) or
                                getattr(node, 'memory_node_id', str(uuid.uuid4()))
                            )

                            memory = Memory(
                                id=memory_node_id,
                                user_id=user_id,
                                content=content,
                                metadata={},
                                memory_type="long_term"
                            )
                            memories.append(memory)

            logger.debug(f"获取用户记忆: {len(memories)} 个")
            return memories

        except Exception as e:
            logger.error(f"获取用户记忆失败: {e}")
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
