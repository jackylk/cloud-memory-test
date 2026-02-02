"""AWS资源管理器"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .base import BaseResourceManager
from ..resources import CloudResource, ResourceType, ResourceStatus


class AWSResourceManager(BaseResourceManager):
    """AWS资源管理器

    支持管理：
    - Bedrock Knowledge Base (OpenSearch Serverless / Aurora PG)
    - Bedrock Memory
    """

    def __init__(self, config: Any):
        super().__init__(config)
        self.access_key_id = None
        self.secret_access_key = None
        self.region = config.region

        # 安全地获取凭证
        if hasattr(config, 'access_key_id') and config.access_key_id:
            self.access_key_id = (
                config.access_key_id.get_secret_value()
                if hasattr(config.access_key_id, 'get_secret_value')
                else config.access_key_id
            )
        if hasattr(config, 'secret_access_key') and config.secret_access_key:
            self.secret_access_key = (
                config.secret_access_key.get_secret_value()
                if hasattr(config.secret_access_key, 'get_secret_value')
                else config.secret_access_key
            )

    def _get_boto3_session(self):
        """获取boto3 session"""
        try:
            import boto3

            session_kwargs = {"region_name": self.region}
            if self.access_key_id and self.secret_access_key:
                session_kwargs["aws_access_key_id"] = self.access_key_id
                session_kwargs["aws_secret_access_key"] = self.secret_access_key

            return boto3.Session(**session_kwargs)
        except ImportError:
            raise RuntimeError("请安装boto3: pip install boto3")

    async def list_resources(self) -> List[CloudResource]:
        """列出所有AWS资源"""
        resources = []

        try:
            session = self._get_boto3_session()

            # 列出Bedrock Knowledge Bases
            try:
                bedrock_agent = session.client('bedrock-agent')
                response = bedrock_agent.list_knowledge_bases()

                for kb in response.get('knowledgeBaseSummaries', []):
                    resource = CloudResource(
                        provider="aws",
                        resource_type=ResourceType.KNOWLEDGE_BASE,
                        resource_id=kb['knowledgeBaseId'],
                        name=kb.get('name', kb['knowledgeBaseId']),
                        status=self._map_kb_status(kb.get('status', 'ACTIVE')),
                        region=self.region,
                        created_at=kb.get('createdAt'),
                        config={
                            "description": kb.get('description', ''),
                        }
                    )
                    resources.append(resource)
            except Exception as e:
                logger.debug(f"列出Bedrock Knowledge Bases失败: {e}")

            # 列出Bedrock Memories
            try:
                # 注意：Bedrock Memory可能没有直接的list API
                # 如果有memory_id配置，则查询状态
                if hasattr(self.config, 'memory_id') and self.config.memory_id:
                    memory_status = await self._get_memory_status(self.config.memory_id)
                    if memory_status:
                        resources.append(memory_status)
            except Exception as e:
                logger.debug(f"列出Bedrock Memories失败: {e}")

        except Exception as e:
            logger.error(f"查询AWS资源失败: {e}")

        return resources

    async def create_knowledge_base(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建Bedrock Knowledge Base

        注意：创建Knowledge Base需要：
        1. OpenSearch Serverless集合或Aurora PG数据库
        2. S3存储桶
        3. IAM角色和权限

        这是一个复杂的操作，建议在AWS控制台手动创建
        """
        raise NotImplementedError(
            "创建Bedrock Knowledge Base需要多个前置资源（OpenSearch/Aurora、S3、IAM角色），"
            "建议在AWS控制台手动创建。创建后将knowledge_base_id添加到配置文件中。"
        )

    async def create_memory(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建Bedrock Memory

        注意：需要先在AWS控制台创建Memory实例
        """
        try:
            from bedrock_agentcore_starter_toolkit.memory import Memory as BedrockMemory

            session = self._get_boto3_session()

            # Bedrock Memory需要memory_id，通常在控制台创建
            # 这里实现的是验证Memory是否可用
            memory_id = config.get("memory_id")
            if not memory_id:
                raise ValueError(
                    "创建Bedrock Memory需要在AWS控制台预先创建并提供memory_id。"
                    "请访问 AWS Console -> Bedrock -> Agents -> Memory 创建。"
                )

            # 创建Memory客户端验证连接
            memory_client = BedrockMemory(
                memory_id=memory_id,
                session=session
            )

            # 测试连接
            memory_client.list_events(max_results=1)

            logger.info(f"Bedrock Memory验证成功: {memory_id}")

            return CloudResource(
                provider="aws",
                resource_type=ResourceType.MEMORY,
                resource_id=memory_id,
                name=name,
                status=ResourceStatus.ACTIVE,
                region=self.region,
                created_at=datetime.now(),
                config={
                    "memory_id": memory_id,
                }
            )

        except ImportError:
            raise RuntimeError(
                "请安装AWS Bedrock AgentCore SDK: "
                "pip install bedrock-agentcore bedrock-agentcore-starter-toolkit"
            )
        except Exception as e:
            logger.error(f"验证Bedrock Memory失败: {e}")
            raise

    async def delete_resource(self, resource_id: str) -> bool:
        """删除AWS资源

        注意：删除Knowledge Base和Memory可能需要手动操作
        """
        try:
            session = self._get_boto3_session()

            # 尝试删除Knowledge Base
            try:
                bedrock_agent = session.client('bedrock-agent')
                bedrock_agent.delete_knowledge_base(knowledgeBaseId=resource_id)
                logger.info(f"Bedrock Knowledge Base删除成功: {resource_id}")
                return True
            except Exception as e:
                logger.debug(f"作为Knowledge Base删除失败: {e}")

            # Memory通常不支持程序化删除，需要在控制台操作
            logger.warning(
                f"无法删除资源 {resource_id}。"
                "Bedrock Memory需要在AWS控制台手动删除。"
            )
            return False

        except Exception as e:
            logger.error(f"删除AWS资源失败: {e}")
            return False

    async def get_resource_status(self, resource_id: str) -> Optional[CloudResource]:
        """获取资源状态"""
        try:
            session = self._get_boto3_session()

            # 尝试获取Knowledge Base状态
            try:
                bedrock_agent = session.client('bedrock-agent')
                response = bedrock_agent.get_knowledge_base(knowledgeBaseId=resource_id)
                kb = response['knowledgeBase']

                return CloudResource(
                    provider="aws",
                    resource_type=ResourceType.KNOWLEDGE_BASE,
                    resource_id=resource_id,
                    name=kb.get('name', resource_id),
                    status=self._map_kb_status(kb.get('status', 'ACTIVE')),
                    region=self.region,
                    config={
                        "description": kb.get('description', ''),
                        "storage_config": kb.get('storageConfiguration', {}),
                    }
                )
            except Exception as e:
                logger.debug(f"作为Knowledge Base查询失败: {e}")

            # 尝试获取Memory状态
            memory_status = await self._get_memory_status(resource_id)
            if memory_status:
                return memory_status

        except Exception as e:
            logger.debug(f"获取AWS资源状态失败: {e}")

        return None

    async def _get_memory_status(self, memory_id: str) -> Optional[CloudResource]:
        """获取Memory状态"""
        try:
            from bedrock_agentcore_starter_toolkit.memory import Memory as BedrockMemory

            session = self._get_boto3_session()
            memory_client = BedrockMemory(
                memory_id=memory_id,
                session=session
            )

            # 测试连接
            memory_client.list_events(max_results=1)

            return CloudResource(
                provider="aws",
                resource_type=ResourceType.MEMORY,
                resource_id=memory_id,
                name=f"bedrock-memory-{memory_id}",
                status=ResourceStatus.ACTIVE,
                region=self.region,
                config={
                    "memory_id": memory_id,
                }
            )
        except Exception as e:
            logger.debug(f"获取Memory状态失败: {e}")
            return None

    def _map_kb_status(self, status: str) -> ResourceStatus:
        """映射Knowledge Base状态"""
        status_map = {
            "CREATING": ResourceStatus.CREATING,
            "ACTIVE": ResourceStatus.ACTIVE,
            "DELETING": ResourceStatus.DELETING,
            "UPDATING": ResourceStatus.ACTIVE,
            "FAILED": ResourceStatus.ERROR,
        }
        return status_map.get(status, ResourceStatus.UNKNOWN)
