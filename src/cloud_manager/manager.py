"""云资源管理器"""

import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from .resources import CloudResource, ResourceType, ResourceStatus
from .providers.volcengine import VolcengineResourceManager
from .providers.aliyun import AliyunResourceManager
from .providers.gcp import GCPResourceManager
from ..utils.config import Config


class CloudResourceManager:
    """云资源管理器

    功能：
    - 列出所有云资源
    - 创建知识库/记忆库实例
    - 删除资源
    - 查询资源状态和费用
    """

    def __init__(self, config: Config):
        self.config = config
        self.providers = {}

        # 初始化各云服务的资源管理器
        if hasattr(config, 'volcengine') and config.volcengine.access_key:
            self.providers['volcengine'] = VolcengineResourceManager(config.volcengine)

        if hasattr(config, 'aliyun') and config.aliyun.access_key_id:
            self.providers['aliyun'] = AliyunResourceManager(config.aliyun)

        if hasattr(config, 'gcp') and getattr(config.gcp, 'project_id', None):
            self.providers['gcp'] = GCPResourceManager(config.gcp)

    async def list_all_resources(self) -> List[CloudResource]:
        """列出所有云资源"""
        all_resources = []

        for provider_name, provider in self.providers.items():
            try:
                logger.info(f"查询 {provider_name} 资源...")
                resources = await provider.list_resources()
                all_resources.extend(resources)
                logger.info(f"  → 找到 {len(resources)} 个资源")
            except Exception as e:
                logger.error(f"查询 {provider_name} 资源失败: {e}")

        return all_resources

    async def create_knowledge_base(
        self,
        provider: str,
        name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> CloudResource:
        """创建知识库"""
        if provider not in self.providers:
            raise ValueError(f"未配置云服务: {provider}")

        logger.info(f"在 {provider} 创建知识库: {name}")
        resource = await self.providers[provider].create_knowledge_base(name, config or {})
        logger.info(f"  → 创建成功: {resource.resource_id}")
        return resource

    async def create_memory(
        self,
        provider: str,
        name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> CloudResource:
        """创建记忆库"""
        if provider not in self.providers:
            raise ValueError(f"未配置云服务: {provider}")

        logger.info(f"在 {provider} 创建记忆库: {name}")
        resource = await self.providers[provider].create_memory(name, config or {})
        logger.info(f"  → 创建成功: {resource.resource_id}")
        return resource

    async def delete_resource(self, provider: str, resource_id: str) -> bool:
        """删除资源"""
        if provider not in self.providers:
            raise ValueError(f"未配置云服务: {provider}")

        logger.info(f"删除 {provider} 资源: {resource_id}")
        success = await self.providers[provider].delete_resource(resource_id)
        if success:
            logger.info(f"  → 删除成功")
        else:
            logger.error(f"  → 删除失败")
        return success

    async def get_resource_status(
        self,
        provider: str,
        resource_id: str
    ) -> Optional[CloudResource]:
        """获取资源状态"""
        if provider not in self.providers:
            raise ValueError(f"未配置云服务: {provider}")

        return await self.providers[provider].get_resource_status(resource_id)

    async def cleanup_all(self, confirm: bool = False) -> int:
        """清理所有资源（危险操作）"""
        if not confirm:
            logger.warning("请使用 confirm=True 确认删除所有资源")
            return 0

        all_resources = await self.list_all_resources()
        deleted_count = 0

        for resource in all_resources:
            try:
                success = await self.delete_resource(
                    resource.provider,
                    resource.resource_id
                )
                if success:
                    deleted_count += 1
            except Exception as e:
                logger.error(f"删除资源失败 {resource.resource_id}: {e}")

        logger.info(f"共删除 {deleted_count}/{len(all_resources)} 个资源")
        return deleted_count

    def get_configured_providers(self) -> List[str]:
        """获取已配置的云服务列表"""
        return list(self.providers.keys())
