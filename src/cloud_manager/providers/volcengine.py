"""火山引擎资源管理器"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .base import BaseResourceManager
from ..resources import CloudResource, ResourceType, ResourceStatus


class VolcengineResourceManager(BaseResourceManager):
    """火山引擎资源管理器"""

    def __init__(self, config: Any):
        super().__init__(config)
        self.access_key = config.access_key.get_secret_value() if hasattr(config.access_key, 'get_secret_value') else config.access_key
        self.secret_key = config.secret_key.get_secret_value() if hasattr(config.secret_key, 'get_secret_value') else config.secret_key
        self.region = config.region

    async def list_resources(self) -> List[CloudResource]:
        """列出所有资源"""
        resources = []

        try:
            # 导入火山引擎SDK
            from volcenginesdkvikingdb import VIKINGDBApi
            from volcenginesdkcore.rest import ApiException

            # 创建API客户端
            api = VIKINGDBApi()
            api.api_client.configuration.ak = self.access_key
            api.api_client.configuration.sk = self.secret_key
            api.api_client.configuration.region = self.region

            # 列出所有集合（知识库）
            try:
                from volcenginesdkvikingdb import ListVikingdbCollectionRequest
                request = ListVikingdbCollectionRequest()
                response = api.list_vikingdb_collection(request)
                if response and hasattr(response, 'result') and response.result.collection_list:
                    for coll in response.result.collection_list:
                        resource = CloudResource(
                            provider="volcengine",
                            resource_type=ResourceType.KNOWLEDGE_BASE,
                            resource_id=coll.collection_name,
                            name=coll.collection_name,
                            status=ResourceStatus.ACTIVE,
                            region=self.region,
                            config={
                                "description": getattr(coll, 'description', ''),
                                "collection_type": getattr(coll, 'collection_type', ''),
                            }
                        )
                        resources.append(resource)
            except ApiException as e:
                logger.debug(f"列出VikingDB集合失败: {e}")

        except ImportError:
            logger.warning("火山引擎SDK未安装，跳过资源查询")
        except Exception as e:
            logger.error(f"查询火山引擎资源失败: {e}")

        return resources

    async def create_knowledge_base(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建VikingDB知识库"""
        try:
            from volcenginesdkvikingdb import VIKINGDBApi, CreateVikingdbCollectionRequest
            from volcenginesdkvikingdb.models import FieldForCreateVikingdbCollectionInput, DenseForCreateVikingdbCollectionInput
            from volcenginesdkcore.rest import ApiException

            # 创建API客户端
            api = VIKINGDBApi()
            api.api_client.configuration.ak = self.access_key
            api.api_client.configuration.sk = self.secret_key
            api.api_client.configuration.region = self.region

            # 创建集合
            dimension = config.get("dimension", 384)
            description = config.get("description", f"Benchmark test collection - {name}")

            # 构建请求
            request = CreateVikingdbCollectionRequest(
                collection_name=name,
                description=description,
                fields=[
                    FieldForCreateVikingdbCollectionInput(
                        field_name="id",
                        field_type="string",
                        default_val=""
                    ),
                    FieldForCreateVikingdbCollectionInput(
                        field_name="content",
                        field_type="string",
                        default_val=""
                    ),
                    FieldForCreateVikingdbCollectionInput(
                        field_name="vector",
                        field_type="dense_vector",
                        default_val="",
                        dense=DenseForCreateVikingdbCollectionInput(
                            dimension=dimension,
                            distance_type="cosine"
                        )
                    )
                ]
            )

            response = api.create_vikingdb_collection(request)

            logger.info(f"VikingDB集合创建成功: {name}")

            return CloudResource(
                provider="volcengine",
                resource_type=ResourceType.KNOWLEDGE_BASE,
                resource_id=name,
                name=name,
                status=ResourceStatus.ACTIVE,
                region=self.region,
                created_at=datetime.now(),
                config={
                    "dimension": dimension,
                    "description": description,
                }
            )

        except ImportError:
            raise RuntimeError("请安装火山引擎SDK: pip install volcengine-python-sdk")
        except ApiException as e:
            logger.error(f"创建VikingDB集合失败: {e}")
            raise
        except Exception as e:
            logger.error(f"创建VikingDB集合失败: {e}")
            raise

    async def create_memory(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建AgentKit记忆库（暂不支持）"""
        raise NotImplementedError("火山引擎AgentKit记忆库暂不支持自动创建，请在控制台创建")

    async def delete_resource(self, resource_id: str) -> bool:
        """删除资源"""
        try:
            from volcenginesdkvikingdb import VIKINGDBApi, DeleteVikingdbCollectionRequest
            from volcenginesdkcore.rest import ApiException

            # 创建API客户端
            api = VIKINGDBApi()
            api.api_client.configuration.ak = self.access_key
            api.api_client.configuration.sk = self.secret_key
            api.api_client.configuration.region = self.region

            # 删除集合
            request = DeleteVikingdbCollectionRequest(collection_name=resource_id)
            api.delete_vikingdb_collection(request)
            logger.info(f"VikingDB集合删除成功: {resource_id}")
            return True

        except ApiException as e:
            logger.error(f"删除VikingDB集合失败: {e}")
            return False
        except Exception as e:
            logger.error(f"删除VikingDB集合失败: {e}")
            return False

    async def get_resource_status(self, resource_id: str) -> Optional[CloudResource]:
        """获取资源状态"""
        try:
            from volcenginesdkvikingdb import VIKINGDBApi, GetVikingdbCollectionRequest
            from volcenginesdkcore.rest import ApiException

            # 创建API客户端
            api = VIKINGDBApi()
            api.api_client.configuration.ak = self.access_key
            api.api_client.configuration.sk = self.secret_key
            api.api_client.configuration.region = self.region

            # 获取集合信息
            request = GetVikingdbCollectionRequest(collection_name=resource_id)
            response = api.get_vikingdb_collection(request)

            if response and response.result:
                coll = response.result
                return CloudResource(
                    provider="volcengine",
                    resource_type=ResourceType.KNOWLEDGE_BASE,
                    resource_id=resource_id,
                    name=resource_id,
                    status=ResourceStatus.ACTIVE,
                    region=self.region,
                    config={
                        "description": getattr(coll, 'description', ''),
                        "collection_type": getattr(coll, 'collection_type', ''),
                    }
                )

        except ApiException as e:
            logger.debug(f"获取VikingDB集合状态失败: {e}")
        except Exception as e:
            logger.debug(f"获取VikingDB集合状态失败: {e}")

        return None
