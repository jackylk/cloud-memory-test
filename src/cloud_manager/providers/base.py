"""云资源管理器基类"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from ..resources import CloudResource


class BaseResourceManager(ABC):
    """资源管理器基类"""

    def __init__(self, config: Any):
        self.config = config

    @abstractmethod
    async def list_resources(self) -> List[CloudResource]:
        """列出所有资源"""
        pass

    @abstractmethod
    async def create_knowledge_base(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建知识库"""
        pass

    @abstractmethod
    async def create_memory(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建记忆库"""
        pass

    @abstractmethod
    async def delete_resource(self, resource_id: str) -> bool:
        """删除资源"""
        pass

    @abstractmethod
    async def get_resource_status(self, resource_id: str) -> Optional[CloudResource]:
        """获取资源状态"""
        pass
