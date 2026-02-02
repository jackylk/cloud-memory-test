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
            from alibabacloud_bailian20231229 import models
            from alibabacloud_tea_openapi import models as open_api_models

            config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                endpoint=self.endpoint
            )
            client = BailianClient(config)

            # 如果配置了workspace_id，则查询该工作空间下的资源
            workspace_id = getattr(self.config, 'workspace_id', None)
            if not workspace_id:
                logger.debug("未配置workspace_id，无法列出阿里云百炼资源")
                return resources

            # 列出知识库（索引）
            try:
                request = models.ListIndicesRequest()
                response = client.list_indices(workspace_id, request)

                logger.debug(f"阿里云: ListIndices响应: {response}")

                if hasattr(response, 'body') and hasattr(response.body, 'data'):
                    data = response.body.data
                    # 可能是 indices 或 index_list
                    indexes = getattr(data, 'indices', None) or getattr(data, 'index_list', [])

                    logger.debug(f"阿里云: 找到 {len(indexes) if indexes else 0} 个知识库")

                    if indexes:
                        for index in indexes:
                            index_id = getattr(index, 'id', None) or getattr(index, 'index_id', 'unknown')
                            index_name = getattr(index, 'name', f"index-{index_id}")
                            logger.debug(f"阿里云: 知识库 {index_name} ({index_id})")

                            resource = CloudResource(
                                provider="aliyun",
                                resource_type=ResourceType.KNOWLEDGE_BASE,
                                resource_id=str(index_id),
                                name=index_name,
                                status=ResourceStatus.ACTIVE,
                                region=self.region,
                                config={
                                    "workspace_id": workspace_id,
                                    "description": getattr(index, 'description', ''),
                                }
                            )
                            resources.append(resource)
                    else:
                        logger.info("阿里云: 当前工作空间下没有知识库")
            except Exception as e:
                logger.warning(f"列出知识库失败: {e}")
                import traceback
                logger.debug(traceback.format_exc())

            # 列出长期记忆
            try:
                request = models.ListMemoriesRequest()
                response = client.list_memories(workspace_id, request)

                logger.debug(f"阿里云: ListMemories响应: {response}")

                if hasattr(response, 'body') and hasattr(response.body, 'data'):
                    data = response.body.data
                    memories = getattr(data, 'memories', [])

                    logger.debug(f"阿里云: 找到 {len(memories) if memories else 0} 个长期记忆")

                    if memories:
                        for memory in memories:
                            memory_id = getattr(memory, 'memory_id', None) or getattr(memory, 'id', 'unknown')
                            memory_name = getattr(memory, 'name', f"memory-{memory_id}")
                            logger.debug(f"阿里云: 长期记忆 {memory_name} ({memory_id})")

                            resource = CloudResource(
                                provider="aliyun",
                                resource_type=ResourceType.MEMORY,
                                resource_id=str(memory_id),
                                name=memory_name,
                                status=ResourceStatus.ACTIVE,
                                region=self.region,
                                config={
                                    "workspace_id": workspace_id,
                                    "description": getattr(memory, 'description', ''),
                                }
                            )
                            resources.append(resource)
                    else:
                        logger.info("阿里云: 当前工作空间下没有长期记忆")
            except Exception as e:
                logger.warning(f"列出长期记忆失败: {e}")
                import traceback
                logger.debug(traceback.format_exc())

        except ImportError:
            logger.warning("阿里云百炼SDK未安装，跳过资源查询")
        except Exception as e:
            logger.error(f"查询阿里云资源失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())

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

            # 创建长期记忆（API只接受description参数）
            description = config.get("description", f"Benchmark test memory - {name}")
            request = models.CreateMemoryRequest(
                description=description
            )

            response = client.create_memory(workspace_id, request)
            memory_id = response.body.memory_id

            logger.info(f"百炼长期记忆创建成功: {memory_id}")

            return CloudResource(
                provider="aliyun",
                resource_type=ResourceType.MEMORY,
                resource_id=memory_id,
                name=name,  # 使用传入的name作为显示名称
                status=ResourceStatus.ACTIVE,
                region=self.region,
                created_at=datetime.now(),
                config={
                    "workspace_id": workspace_id,
                    "description": description,
                }
            )

        except ImportError:
            raise RuntimeError("请安装阿里云百炼SDK: pip install alibabacloud-bailian20231229")
        except Exception as e:
            logger.error(f"创建百炼长期记忆失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
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
