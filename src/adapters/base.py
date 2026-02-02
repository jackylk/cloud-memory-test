"""适配器基类定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class DocumentFormat(Enum):
    """文档格式"""
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "md"
    JSON = "json"


@dataclass
class Document:
    """文档数据结构"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    format: DocumentFormat = DocumentFormat.TXT
    title: Optional[str] = None


@dataclass
class QueryResult:
    """查询结果"""
    documents: List[Dict[str, Any]]
    scores: List[float]
    latency_ms: float
    total_results: int = 0
    query: str = ""


@dataclass
class UploadResult:
    """上传结果"""
    success_count: int
    failed_count: int
    failed_ids: List[str] = field(default_factory=list)
    total_time_ms: float = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexResult:
    """索引结果"""
    success: bool
    index_time_ms: float
    doc_count: int
    index_size_bytes: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Memory:
    """记忆数据结构"""
    id: Optional[str]
    user_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    memory_type: str = "general"  # general, fact, preference, episode


@dataclass
class MemorySearchResult:
    """记忆搜索结果"""
    memories: List[Memory]
    scores: List[float]
    latency_ms: float
    total_results: int = 0


@dataclass
class MemoryAddResult:
    """记忆添加结果"""
    memory_id: str
    success: bool
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


class KnowledgeBaseAdapter(ABC):
    """知识库适配器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._initialized = False
        self.name = self.__class__.__name__

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @abstractmethod
    async def initialize(self) -> None:
        """初始化连接和认证"""
        pass

    @abstractmethod
    async def upload_documents(self, documents: List[Document]) -> UploadResult:
        """上传文档"""
        pass

    @abstractmethod
    async def build_index(self) -> IndexResult:
        """构建/更新索引"""
        pass

    @abstractmethod
    async def query(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> QueryResult:
        """执行检索查询"""
        pass

    @abstractmethod
    async def delete_documents(self, doc_ids: List[str]) -> Dict[str, Any]:
        """删除文档"""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        pass

    async def cleanup(self) -> None:
        """清理资源"""
        self._initialized = False

    async def health_check(self) -> bool:
        """健康检查"""
        return self._initialized

    async def measure_network_latency(self, num_samples: int = 10) -> Dict[str, float]:
        """测量网络基线延迟

        通过多次轻量级请求测量网络往返时间（RTT）

        Args:
            num_samples: 采样次数，默认10次

        Returns:
            包含 min/max/avg/p50/p95 的延迟字典（单位：毫秒）
        """
        import time
        import statistics

        latencies = []

        for _ in range(num_samples):
            start = time.time()
            try:
                # 尝试调用健康检查或最轻量级的API
                await self.health_check()
            except:
                # 如果健康检查失败，使用简单的连接测试
                pass
            elapsed_ms = (time.time() - start) * 1000
            latencies.append(elapsed_ms)

        if not latencies:
            return {
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "samples": 0
            }

        sorted_latencies = sorted(latencies)
        p50_idx = int(len(sorted_latencies) * 0.5)
        p95_idx = int(len(sorted_latencies) * 0.95)

        return {
            "min": min(latencies),
            "max": max(latencies),
            "avg": statistics.mean(latencies),
            "p50": sorted_latencies[p50_idx],
            "p95": sorted_latencies[p95_idx],
            "samples": num_samples
        }


class MemoryAdapter(ABC):
    """记忆系统适配器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._initialized = False
        self.name = self.__class__.__name__

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @abstractmethod
    async def initialize(self) -> None:
        """初始化连接"""
        pass

    @abstractmethod
    async def add_memory(self, memory: Memory) -> MemoryAddResult:
        """添加记忆"""
        pass

    @abstractmethod
    async def add_memories_batch(self, memories: List[Memory]) -> List[MemoryAddResult]:
        """批量添加记忆"""
        pass

    @abstractmethod
    async def search_memory(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> MemorySearchResult:
        """搜索相关记忆"""
        pass

    @abstractmethod
    async def update_memory(self, memory_id: str, content: str) -> bool:
        """更新记忆内容"""
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        pass

    @abstractmethod
    async def get_user_memories(
        self,
        user_id: str,
        limit: int = 100
    ) -> List[Memory]:
        """获取用户所有记忆"""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pass

    async def cleanup(self) -> None:
        """清理资源"""
        self._initialized = False

    async def health_check(self) -> bool:
        """健康检查"""
        return self._initialized

    async def measure_network_latency(self, num_samples: int = 10) -> Dict[str, float]:
        """测量网络基线延迟

        通过多次轻量级请求测量网络往返时间（RTT）

        Args:
            num_samples: 采样次数，默认10次

        Returns:
            包含 min/max/avg/p50/p95 的延迟字典（单位：毫秒）
        """
        import time
        import statistics

        latencies = []

        for _ in range(num_samples):
            start = time.time()
            try:
                # 尝试调用健康检查或最轻量级的API
                await self.health_check()
            except:
                # 如果健康检查失败，使用简单的连接测试
                pass
            elapsed_ms = (time.time() - start) * 1000
            latencies.append(elapsed_ms)

        if not latencies:
            return {
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "samples": 0
            }

        sorted_latencies = sorted(latencies)
        p50_idx = int(len(sorted_latencies) * 0.5)
        p95_idx = int(len(sorted_latencies) * 0.95)

        return {
            "min": min(latencies),
            "max": max(latencies),
            "avg": statistics.mean(latencies),
            "p50": sorted_latencies[p50_idx],
            "p95": sorted_latencies[p95_idx],
            "samples": num_samples
        }
