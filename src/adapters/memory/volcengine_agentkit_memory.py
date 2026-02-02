"""火山引擎 AgentKit Memory 适配器

使用 VeADK SDK (veadk-python) 进行长期记忆管理
SDK: pip install veadk-python
文档: https://volcengine.github.io/veadk-python/
"""

import time
import uuid
import os
from typing import List, Optional, Dict, Any
from loguru import logger

from ..base import (
    MemoryAdapter,
    Memory,
    MemorySearchResult,
    MemoryAddResult,
)


class VolcengineAgentKitMemoryAdapter(MemoryAdapter):
    """火山引擎 AgentKit Memory 适配器

    特点:
    - 支持 mock 模式用于无凭证测试
    - 真实模式使用 VeADK LongTermMemory (VikingDB backend)
    - 支持长期记忆存储和检索
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "VolcengineAgentKitMemory"

        self._access_key = config.get("access_key")
        self._secret_key = config.get("secret_key")
        self._region = config.get("region", "cn-beijing")

        # VikingDB collection name (不是 memory_id!)
        # Collection 名称必须: 1-64字符，字母开头，只含字母数字下划线
        self._collection_name = config.get("collection_name", "cloud_memory_test_ltm")

        # 如果缺少凭证，启用 mock 模式
        self._mock_mode = not (self._access_key and self._secret_key)

        # VeADK LongTermMemory 实例
        self._ltm = None

        # Mock 模式存储
        self._memories: Dict[str, Memory] = {}
        self._user_memories: Dict[str, List[str]] = {}

    @property
    def mock_mode(self) -> bool:
        return self._mock_mode

    async def initialize(self) -> None:
        """初始化连接和认证"""
        if self._mock_mode:
            logger.info("VolcengineAgentKitMemory: 初始化 Mock 模式")
            logger.debug("  → 使用本地字典存储模拟")
            if not self._access_key or not self._secret_key:
                logger.debug("  → 未配置 access_key/secret_key")
        else:
            logger.info("VolcengineAgentKitMemory: 初始化真实模式 (VeADK)")
            logger.debug(f"  → Region: {self._region}")
            logger.debug(f"  → Collection: {self._collection_name}")

            try:
                from veadk.memory.long_term_memory import LongTermMemory

                # 设置环境变量供 VeADK 使用
                os.environ["VOLCENGINE_ACCESS_KEY"] = self._access_key
                os.environ["VOLCENGINE_SECRET_KEY"] = self._secret_key
                os.environ["DATABASE_VIKINGMEM_REGION"] = self._region

                # 创建 LongTermMemory 实例
                # backend="viking" 使用 VikingDB 作为存储后端
                self._ltm = LongTermMemory(
                    backend="viking",
                    index=self._collection_name
                )

                logger.debug("  → VeADK LongTermMemory 创建成功")

            except ImportError:
                logger.error("请安装 veadk-python: pip install veadk-python")
                raise RuntimeError("veadk-python is required for Volcengine Memory adapter")
            except Exception as e:
                logger.error(f"初始化 VeADK LongTermMemory 失败: {e}")
                raise

        self._initialized = True
        logger.debug("  → 初始化完成")

    async def add_memory(self, memory: Memory) -> MemoryAddResult:
        """添加记忆

        VeADK 通过 Session 添加记忆，我们将单个记忆转换为 Session 格式
        """
        start_time = time.time()
        memory_id = memory.id or str(uuid.uuid4())
        memory.id = memory_id

        if self._mock_mode:
            # Mock 模式：存储到本地
            self._memories[memory_id] = memory
            if memory.user_id not in self._user_memories:
                self._user_memories[memory.user_id] = []
            self._user_memories[memory.user_id].append(memory_id)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"[Mock] 添加记忆: {memory_id} for user {memory.user_id}")
            return MemoryAddResult(memory_id=memory_id, success=True, latency_ms=elapsed_ms)

        # 真实模式：通过 Session 添加记忆到 VeADK
        try:
            from google.adk.sessions import Session
            from google.adk.events import Event
            from google.genai.types import Content, Part

            # 创建 Event（将记忆内容作为用户消息）
            event = Event(
                author="user",
                content=Content(
                    role="user",
                    parts=[Part(text=memory.content)]
                )
            )

            # 创建 Session
            session_id = f"memory_{memory_id}"
            session = Session(
                id=session_id,
                app_name="benchmark_test",
                user_id=memory.user_id,
                events=[event]
            )

            # 添加到 VeADK
            await self._ltm.add_session_to_memory(session)

            # 同时存储到本地索引
            self._memories[memory_id] = memory
            if memory.user_id not in self._user_memories:
                self._user_memories[memory.user_id] = []
            self._user_memories[memory.user_id].append(memory_id)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"添加记忆到VeADK: {memory_id} for user {memory.user_id}")
            return MemoryAddResult(memory_id=memory_id, success=True, latency_ms=elapsed_ms)

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

        # 真实模式：使用 VeADK LongTermMemory.search_memory
        try:
            # VeADK 的 search_memory 需要 app_name, user_id, query
            # 使用 "benchmark_test" 作为 app_name
            response = await self._ltm.search_memory(
                app_name="benchmark_test",
                user_id=user_id,
                query=query
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析响应
            memories = []
            scores = []

            if hasattr(response, 'memories'):
                for mem_item in response.memories[:top_k]:
                    # mem_item 是 SearchMemoryItem，包含 memory_info, score 等字段
                    # memory_info 包含 summary 和 original_messages
                    memory_info = getattr(mem_item, 'memory_info', {})

                    # 优先使用 summary，如果没有则使用 original_messages
                    if isinstance(memory_info, dict):
                        content = memory_info.get('summary', '') or memory_info.get('original_messages', '')
                    else:
                        # 如果是对象，尝试访问属性
                        content = getattr(memory_info, 'summary', '') or getattr(memory_info, 'original_messages', '')

                    score = getattr(mem_item, 'score', 0.0)

                    memory = Memory(
                        id=str(uuid.uuid4()),
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
        if self._mock_mode or memory_id in self._memories:
            if memory_id in self._memories:
                self._memories[memory_id].content = content
                logger.debug(f"[Mock] 更新记忆: {memory_id}")
                return True
            return False

        # VeADK 不直接支持更新单个记忆
        logger.warning("VeADK LongTermMemory 不支持直接更新单个记忆")
        return False

    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if self._mock_mode or memory_id in self._memories:
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

        # VeADK 不直接支持删除单个记忆
        logger.warning("VeADK LongTermMemory 不支持直接删除单个记忆")
        return False

    async def get_user_memories(self, user_id: str, limit: int = 100) -> List[Memory]:
        """获取用户所有记忆"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        if self._mock_mode:
            memory_ids = self._user_memories.get(user_id, [])[:limit]
            memories = [self._memories[mid] for mid in memory_ids if mid in self._memories]
            logger.debug(f"[Mock] 获取用户记忆: {len(memories)} 个")
            return memories

        # 真实模式：使用搜索来获取用户记忆
        # VeADK 不提供 list_all 接口，我们用空查询搜索
        try:
            result = await self.search_memory(
                query="",  # 空查询
                user_id=user_id,
                top_k=limit
            )
            logger.debug(f"获取用户记忆: {len(result.memories)} 个")
            return result.memories
        except Exception as e:
            logger.error(f"获取用户记忆失败: {e}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "initialized": self._initialized,
            "mode": "mock" if self._mock_mode else "real",
            "backend": "veadk" if not self._mock_mode else "dict",
            "collection_name": self._collection_name,
            "total_memories": len(self._memories) if self._mock_mode else 0,
        }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mock_mode:
            self._memories.clear()
            self._user_memories.clear()
        else:
            # VeADK LongTermMemory 会自动管理连接
            self._ltm = None

        self._initialized = False
        logger.debug("VolcengineAgentKitMemory 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized:
            return False

        if self._mock_mode:
            return True

        try:
            # 尝试搜索来验证连接
            result = await self.search_memory(
                query="health_check",
                user_id="system",
                top_k=1
            )
            return True
        except Exception as e:
            logger.warning(f"健康检查失败: {e}")
            return False
