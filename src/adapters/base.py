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
