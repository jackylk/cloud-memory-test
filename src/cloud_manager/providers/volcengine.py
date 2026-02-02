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

            logger.debug(f"火山引擎: 初始化API客户端 (region={self.region})")

            # 创建API客户端
            api = VIKINGDBApi()
            api.api_client.configuration.ak = self.access_key
            api.api_client.configuration.sk = self.secret_key
            api.api_client.configuration.region = self.region

            # 列出所有集合（知识库）
            try:
                from volcenginesdkvikingdb import ListVikingdbCollectionRequest
                request = ListVikingdbCollectionRequest()
                logger.debug("火山引擎: 调用 list_vikingdb_collection API")
                response = api.list_vikingdb_collection(request)

                logger.debug(f"火山引擎: API响应类型: {type(response)}")
                logger.debug(f"火山引擎: 响应对象: {response}")

                if response:
                    # 响应格式：{'collections': [...], 'total_count': N}
                    collections = None
                    if hasattr(response, 'collections'):
                        collections = response.collections
                    elif isinstance(response, dict) and 'collections' in response:
                        collections = response['collections']
                    elif hasattr(response, 'result') and hasattr(response.result, 'collection_list'):
                        # 旧格式兼容
                        collections = response.result.collection_list

                    if collections is not None:
                        logger.debug(f"火山引擎: 找到 {len(collections)} 个集合")
                        for coll in collections:
                            coll_name = coll.collection_name if hasattr(coll, 'collection_name') else coll.get('collection_name', 'unknown')
                            logger.debug(f"火山引擎: 集合名称: {coll_name}")
                            resource = CloudResource(
                                provider="volcengine",
                                resource_type=ResourceType.KNOWLEDGE_BASE,
                                resource_id=coll_name,
                                name=coll_name,
                                status=ResourceStatus.ACTIVE,
                                region=self.region,
                                config={
                                    "description": getattr(coll, 'description', '') if hasattr(coll, 'description') else coll.get('description', ''),
                                    "collection_type": getattr(coll, 'collection_type', '') if hasattr(coll, 'collection_type') else coll.get('collection_type', ''),
                                }
                            )
                            resources.append(resource)

                        if len(collections) == 0:
                            logger.info("火山引擎: 当前账户下没有VikingDB集合")
                            logger.info("  提示: 请在火山引擎控制台创建集合，或使用命令:")
                            logger.info("  python -m src cloud-resources -a create -p volcengine -t kb -n your-collection-name")
                    else:
                        logger.debug("火山引擎: 无法解析响应格式")
                else:
                    logger.debug("火山引擎: response 为 None")

            except ApiException as e:
                logger.warning(f"列出VikingDB集合失败: {e}")
                logger.debug(f"API异常详情: status={getattr(e, 'status', 'N/A')}, reason={getattr(e, 'reason', 'N/A')}")

        except ImportError as e:
            logger.warning(f"火山引擎SDK未安装: {e}")
        except Exception as e:
            logger.error(f"查询火山引擎资源失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())

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
