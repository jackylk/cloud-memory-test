"""AWS Bedrock Memory 适配器

支持两种模式:
1. Mock 模式: 使用本地字典存储模拟行为（无需凭证）
2. 真实模式: 使用 AWS Bedrock AgentCore Memory API

SDK: pip install bedrock-agentcore bedrock-agentcore-starter-toolkit boto3
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


class AWSBedrockMemoryAdapter(MemoryAdapter):
    """AWS Bedrock Memory 适配器

    特点:
    - 支持 mock 模式用于无凭证测试
    - 真实模式使用 AWS Bedrock AgentCore Memory
    - 支持短期记忆(events)和长期记忆(extracted insights)
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "AWSBedrockMemory"

        # AWS 配置
        self._region = config.get("region", "us-east-1")
        self._memory_id = config.get("memory_id")
        self._access_key_id = config.get("access_key_id")
        self._secret_access_key = config.get("secret_access_key")

        # 如果没有 memory_id，启用 mock 模式
        self._mock_mode = not self._memory_id

        # SDK 客户端（真实模式）
        self._memory_client = None

        # Mock 模式存储
        self._memories: Dict[str, Memory] = {}  # memory_id -> Memory
        self._user_memories: Dict[str, List[str]] = {}  # user_id -> [memory_ids]

    @property
    def mock_mode(self) -> bool:
        """是否处于 mock 模式"""
        return self._mock_mode

    async def initialize(self) -> None:
        """初始化连接和认证"""
        if self._mock_mode:
            logger.info("AWSBedrockMemory: 初始化 Mock 模式")
            logger.debug("  → 使用本地字典存储模拟")
            if not self._memory_id:
                logger.debug("  → 未配置 memory_id")
        else:
            logger.info(f"AWSBedrockMemory: 初始化真实模式")
            logger.debug(f"  → Region: {self._region}")
            logger.debug(f"  → Memory ID: {self._memory_id}")

            try:
                # 导入 AWS Bedrock AgentCore SDK
                try:
                    from bedrock_agentcore_starter_toolkit.memory import Memory as BedrockMemory
                    import boto3

                    # 创建 boto3 session
                    session_kwargs = {}
                    if self._access_key_id and self._secret_access_key:
                        session_kwargs["aws_access_key_id"] = self._access_key_id
                        session_kwargs["aws_secret_access_key"] = self._secret_access_key
                    session_kwargs["region_name"] = self._region

                    session = boto3.Session(**session_kwargs)

                    # 创建 Memory 客户端
                    self._memory_client = BedrockMemory(
                        memory_id=self._memory_id,
                        session=session
                    )

                    logger.debug("  → Bedrock Memory 客户端创建成功")

                except ImportError:
                    logger.error(
                        "AWS Bedrock AgentCore SDK 未安装，请运行: "
                        "pip install bedrock-agentcore bedrock-agentcore-starter-toolkit"
                    )
                    raise RuntimeError(
                        "bedrock-agentcore is required for AWS Bedrock Memory adapter"
                    )

            except Exception as e:
                logger.error(f"初始化 Bedrock Memory 客户端失败: {e}")
                raise

        self._initialized = True
        logger.debug("  → 初始化完成")

    async def add_memory(self, memory: Memory) -> MemoryAddResult:
        """添加记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        if self._mock_mode:
            # Mock 模式：存储到本地
            memory_id = memory.id or str(uuid.uuid4())
            memory.id = memory_id
            self._memories[memory_id] = memory

            # 更新用户记忆列表
            if memory.user_id not in self._user_memories:
                self._user_memories[memory.user_id] = []
            self._user_memories[memory.user_id].append(memory_id)

            logger.debug(f"[Mock] 添加记忆: {memory_id} for user {memory.user_id}")

            return MemoryAddResult(memory_id=memory_id, success=True, latency_ms=0.0)
        else:
            # 真实模式：调用 Bedrock Memory API
            try:
                # 创建 event（短期记忆）
                event_data = {
                    "user_id": memory.user_id,
                    "content": memory.content,
                    "metadata": memory.metadata,
                    "session_id": memory.session_id or str(uuid.uuid4()),
                }

                response = self._memory_client.create_event(**event_data)
                memory_id = response.get("event_id", str(uuid.uuid4()))

                logger.debug(f"添加记忆: {memory_id} for user {memory.user_id}")

                return MemoryAddResult(memory_id=memory_id, success=True, latency_ms=0.0)

            except Exception as e:
                logger.error(f"添加记忆失败: {e}")
                # 返回 fallback ID
                return MemoryAddResult(memory_id=str(uuid.uuid4()))

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

        if self._mock_mode:
            # Mock 模式：简单的关键词匹配
            user_memory_ids = self._user_memories.get(user_id, [])
            results = []

            query_lower = query.lower()
            for memory_id in user_memory_ids:
                memory = self._memories.get(memory_id)
                if memory and query_lower in memory.content.lower():
                    score = 1.0  # 简单评分
                    results.append((memory, score))

            # 按分数排序并取 top_k
            results.sort(key=lambda x: x[1], reverse=True)
            top_results = results[:top_k]

            elapsed_ms = (time.time() - start_time) * 1000

            memories = [r[0] for r in top_results]
            scores = [r[1] for r in top_results]

            logger.debug(f"[Mock] 搜索记忆: 找到 {len(memories)} 个结果")

            return MemorySearchResult(
                memories=memories,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(memories)
            )
        else:
            # 真实模式：调用 search_long_term_memories
            try:
                response = self._memory_client.search_long_term_memories(
                    query=query,
                    user_id=user_id,
                    max_results=top_k
                )

                elapsed_ms = (time.time() - start_time) * 1000

                # 解析结果
                memories = []
                scores = []

                for item in response.get("memories", []):
                    memory = Memory(
                        id=item.get("memory_id"),
                        user_id=user_id,
                        content=item.get("content", ""),
                        metadata=item.get("metadata", {}),
                        memory_type="long_term"
                    )
                    memories.append(memory)
                    scores.append(item.get("score", 0.0))

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

        if self._mock_mode:
            if memory_id in self._memories:
                self._memories[memory_id].content = content
                logger.debug(f"[Mock] 更新记忆: {memory_id}")
                return True
            return False
        else:
            try:
                # Bedrock Memory 不直接支持更新，需要删除后重新添加
                logger.warning("Bedrock Memory 不支持直接更新，建议删除后重新添加")
                return False
            except Exception as e:
                logger.error(f"更新记忆失败: {e}")
                return False

    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        if self._mock_mode:
            if memory_id in self._memories:
                memory = self._memories[memory_id]
                del self._memories[memory_id]

                # 从用户记忆列表中移除
                if memory.user_id in self._user_memories:
                    self._user_memories[memory.user_id].remove(memory_id)

                logger.debug(f"[Mock] 删除记忆: {memory_id}")
                return True
            return False
        else:
            try:
                # 调用删除 event API
                self._memory_client.delete_event(event_id=memory_id)
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

        if self._mock_mode:
            memory_ids = self._user_memories.get(user_id, [])[:limit]
            memories = [self._memories[mid] for mid in memory_ids if mid in self._memories]
            logger.debug(f"[Mock] 获取用户记忆: {len(memories)} 个")
            return memories
        else:
            try:
                # 调用 list_events API
                response = self._memory_client.list_events(
                    user_id=user_id,
                    max_results=limit
                )

                memories = []
                for event in response.get("events", []):
                    memory = Memory(
                        id=event.get("event_id"),
                        user_id=user_id,
                        content=event.get("content", ""),
                        metadata=event.get("metadata", {}),
                        session_id=event.get("session_id"),
                        memory_type="event"
                    )
                    memories.append(memory)

                logger.debug(f"获取用户记忆: {len(memories)} 个")
                return memories

            except Exception as e:
                logger.error(f"获取用户记忆失败: {e}")
                return []

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._mock_mode:
            return {
                "initialized": self._initialized,
                "mode": "mock",
                "total_memories": len(self._memories),
                "total_users": len(self._user_memories),
            }
        else:
            return {
                "initialized": self._initialized,
                "mode": "real",
                "region": self._region,
                "memory_id": self._memory_id,
                "client_ready": self._memory_client is not None
            }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mock_mode:
            self._memories.clear()
            self._user_memories.clear()

        self._memory_client = None
        self._initialized = False
        logger.debug("AWSBedrockMemory 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized:
            return False

        if self._mock_mode:
            return True
        else:
            try:
                # 尝试列出 events 来验证连接
                self._memory_client.list_events(max_results=1)
                return True
            except Exception as e:
                logger.warning(f"健康检查失败: {e}")
                return False
