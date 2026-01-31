"""阿里云资源管理器"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .base import BaseResourceManager
from ..resources import CloudResource, ResourceType, ResourceStatus


class AliyunResourceManager(BaseResourceManager):
    """阿里云百炼资源管理器"""

    def __init__(self, config: Any):
        super().__init__(config)
        self.access_key_id = config.access_key_id.get_secret_value() if hasattr(config.access_key_id, 'get_secret_value') else config.access_key_id
        self.access_key_secret = config.access_key_secret.get_secret_value() if hasattr(config.access_key_secret, 'get_secret_value') else config.access_key_secret
        self.region = config.region
        self.endpoint = getattr(config, 'endpoint', 'bailian.cn-beijing.aliyuncs.com')

    async def list_resources(self) -> List[CloudResource]:
        """列出所有资源"""
        resources = []

        try:
            # 导入阿里云SDK
            from alibabacloud_bailian20231229.client import Client as BailianClient
            from alibabacloud_tea_openapi import models as open_api_models

            config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                endpoint=self.endpoint
            )
            client = BailianClient(config)

            # 列出所有工作空间
            # 注意：百炼API可能需要workspace_id来查询具体资源
            # 这里暂时返回空列表，需要根据实际API调整
            logger.debug("阿里云百炼资源列表查询需要workspace_id")

        except ImportError:
            logger.warning("阿里云百炼SDK未安装，跳过资源查询")
        except Exception as e:
            logger.error(f"查询阿里云资源失败: {e}")

        return resources

    async def create_knowledge_base(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建百炼知识库"""
        try:
            from alibabacloud_bailian20231229.client import Client as BailianClient
            from alibabacloud_bailian20231229 import models
            from alibabacloud_tea_openapi import models as open_api_models

            api_config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                endpoint=self.endpoint
            )
            client = BailianClient(api_config)

            workspace_id = config.get("workspace_id")
            if not workspace_id:
                raise ValueError("创建百炼知识库需要workspace_id")

            # 创建索引（知识库）
            request = models.CreateIndexRequest(
                name=name,
                description=config.get("description", f"Benchmark test index - {name}"),
                # 其他配置参数
            )

            response = client.create_index(workspace_id, request)
            index_id = response.body.data.index_id

            logger.info(f"百炼知识库创建成功: {index_id}")

            return CloudResource(
                provider="aliyun",
                resource_type=ResourceType.KNOWLEDGE_BASE,
                resource_id=index_id,
                name=name,
                status=ResourceStatus.ACTIVE,
                region=self.region,
                created_at=datetime.now(),
                config={
                    "workspace_id": workspace_id,
                }
            )

        except ImportError:
            raise RuntimeError("请安装阿里云百炼SDK: pip install alibabacloud-bailian20231229")
        except Exception as e:
            logger.error(f"创建百炼知识库失败: {e}")
            raise

    async def create_memory(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建百炼长期记忆"""
        try:
            from alibabacloud_bailian20231229.client import Client as BailianClient
            from alibabacloud_bailian20231229 import models
            from alibabacloud_tea_openapi import models as open_api_models

            api_config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                endpoint=self.endpoint
            )
            client = BailianClient(api_config)

            workspace_id = config.get("workspace_id")
            if not workspace_id:
                raise ValueError("创建百炼记忆需要workspace_id")

            # 创建长期记忆
            request = models.CreateMemoryRequest(
                name=name,
                description=config.get("description", f"Benchmark test memory - {name}"),
            )

            response = client.create_memory(workspace_id, request)
            memory_id = response.body.data.memory_id

            logger.info(f"百炼长期记忆创建成功: {memory_id}")

            return CloudResource(
                provider="aliyun",
                resource_type=ResourceType.MEMORY,
                resource_id=memory_id,
                name=name,
                status=ResourceStatus.ACTIVE,
                region=self.region,
                created_at=datetime.now(),
                config={
                    "workspace_id": workspace_id,
                }
            )

        except ImportError:
            raise RuntimeError("请安装阿里云百炼SDK: pip install alibabacloud-bailian20231229")
        except Exception as e:
            logger.error(f"创建百炼长期记忆失败: {e}")
            raise

    async def delete_resource(self, resource_id: str) -> bool:
        """删除资源"""
        try:
            from alibabacloud_bailian20231229.client import Client as BailianClient
            from alibabacloud_tea_openapi import models as open_api_models

            api_config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                endpoint=self.endpoint
            )
            client = BailianClient(api_config)

            # 需要workspace_id来删除资源
            # 这里暂时返回False，需要根据实际情况调整
            logger.warning("删除百炼资源需要workspace_id和资源类型")
            return False

        except Exception as e:
            logger.error(f"删除百炼资源失败: {e}")
            return False

    async def get_resource_status(self, resource_id: str) -> Optional[CloudResource]:
        """获取资源状态"""
        # 百炼API需要workspace_id和具体的资源类型来查询
        logger.debug("百炼资源状态查询需要workspace_id和资源类型")
        return None
