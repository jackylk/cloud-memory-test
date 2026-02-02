"""AWS Bedrock Memory 适配器

使用 bedrock-agentcore MemorySessionManager
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
    - 真实模式使用 bedrock-agentcore MemorySessionManager
    - 支持对话记忆存储和检索
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

        # MemorySessionManager 实例
        self._session_manager = None

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
                from bedrock_agentcore.memory import MemorySessionManager
                import boto3

                # 创建 boto3 session
                session_kwargs = {}
                if self._access_key_id and self._secret_access_key:
                    session_kwargs["aws_access_key_id"] = self._access_key_id
                    session_kwargs["aws_secret_access_key"] = self._secret_access_key
                session_kwargs["region_name"] = self._region

                boto3_session = boto3.Session(**session_kwargs)

                # 创建 MemorySessionManager
                self._session_manager = MemorySessionManager(
                    memory_id=self._memory_id,
                    boto3_session=boto3_session
                )

                logger.debug("  → MemorySessionManager 创建成功")

            except ImportError:
                logger.error("请安装: pip install bedrock-agentcore boto3")
                raise RuntimeError("bedrock-agentcore is required for AWS Bedrock Memory adapter")
            except Exception as e:
                logger.error(f"初始化 MemorySessionManager 失败: {e}")
                raise

        self._initialized = True
        logger.debug("  → 初始化完成")

    async def add_memory(self, memory: Memory) -> MemoryAddResult:
        """添加记忆（对话消息）"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        memory_id = memory.id or str(uuid.uuid4())
        memory.id = memory_id

        if self._mock_mode:
            # Mock 模式：存储到本地
            self._memories[memory_id] = memory

            # 更新用户记忆列表
            if memory.user_id not in self._user_memories:
                self._user_memories[memory.user_id] = []
            self._user_memories[memory.user_id].append(memory_id)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"[Mock] 添加记忆: {memory_id} for user {memory.user_id}")

            return MemoryAddResult(memory_id=memory_id, success=True, latency_ms=elapsed_ms)

        # 真实模式：使用 MemorySessionManager
        try:
            from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

            # 创建或获取 session
            session_id = memory.session_id or f"session_{memory.user_id}"
            session = self._session_manager.create_memory_session(
                actor_id=memory.user_id,
                session_id=session_id
            )

            # 添加对话消息
            # 根据 memory_type 决定角色
            role = MessageRole.USER if memory.memory_type != "assistant" else MessageRole.ASSISTANT

            session.add_turns(
                messages=[ConversationalMessage(memory.content, role)]
            )

            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"添加记忆: session={session_id}, user={memory.user_id}")

            return MemoryAddResult(
                memory_id=f"{session_id}_{memory_id}",
                success=True,
                latency_ms=elapsed_ms
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"添加记忆失败: {e}")
            return MemoryAddResult(
                memory_id=memory_id,
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

        # 真实模式：使用 search_long_term_memories
        try:
            # 使用 MemorySessionManager 搜索
            # namespace_prefix 用于过滤特定用户的记忆
            response = self._session_manager.search_long_term_memories(
                query=query,
                namespace_prefix=user_id,  # 使用 namespace_prefix 过滤用户记忆
                top_k=top_k,
                max_results=top_k
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果 - response 是 List[MemoryRecord]
            memories = []
            scores = []

            if isinstance(response, list):
                for item in response:
                    # MemoryRecord 包含 text, memory_id, score 等
                    content = getattr(item, 'text', '') or getattr(item, 'content', '')
                    memory_id = getattr(item, 'memory_id', str(uuid.uuid4()))
                    score = getattr(item, 'score', 0.0)

                    memory = Memory(
                        id=memory_id,
                        user_id=user_id,
                        content=content,
                        metadata={},
                        memory_type="long_term"
                    )
                    memories.append(memory)
                    scores.append(score)

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

        # 真实模式：Bedrock Memory 不直接支持更新
        logger.warning("AWS Bedrock Memory 不支持直接更新单个记忆")
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
                    if memory_id in self._user_memories[memory.user_id]:
                        self._user_memories[memory.user_id].remove(memory_id)

                logger.debug(f"[Mock] 删除记忆: {memory_id}")
                return True
            return False

        # 真实模式：调用 delete_event
        try:
            self._session_manager.delete_event(event_id=memory_id)
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

        # 真实模式：列出用户的 sessions 和 events
        try:
            # 列出用户的所有 sessions
            sessions = self._session_manager.list_actor_sessions(actor_id=user_id)

            memories = []
            for session_info in sessions[:limit]:
                session_id = session_info.get('session_id')
                if session_id:
                    # 获取该 session 的最近对话
                    session = self._session_manager.create_memory_session(
                        actor_id=user_id,
                        session_id=session_id
                    )

                    # 获取最近的对话记录
                    turns = session.get_last_k_turns(k=10)
                    for turn in turns:
                        if hasattr(turn, 'text'):
                            memory = Memory(
                                id=str(uuid.uuid4()),
                                user_id=user_id,
                                content=turn.text,
                                session_id=session_id,
                                metadata={},
                                memory_type="event"
                            )
                            memories.append(memory)

            logger.debug(f"获取用户记忆: {len(memories)} 个")
            return memories[:limit]

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
                "session_manager_ready": self._session_manager is not None
            }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mock_mode:
            self._memories.clear()
            self._user_memories.clear()

        self._session_manager = None
        self._initialized = False
        logger.debug("AWSBedrockMemory 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized:
            return False

        if self._mock_mode:
            return True

        try:
            # 尝试列出 actors 来验证连接
            actors = self._session_manager.list_actors()
            return True
        except Exception as e:
            logger.warning(f"健康检查失败: {e}")
            return False
