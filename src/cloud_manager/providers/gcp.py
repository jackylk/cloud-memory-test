"""Google Cloud资源管理器"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from .base import BaseResourceManager
from ..resources import CloudResource, ResourceType, ResourceStatus


class GCPResourceManager(BaseResourceManager):
    """Google Cloud资源管理器"""

    def __init__(self, config: Any):
        super().__init__(config)
        self.project_id = getattr(config, 'project_id', None)
        self.location = getattr(config, 'location', 'us-central1')
        self.service_account_json = getattr(config, 'service_account_json', None)

    async def list_resources(self) -> List[CloudResource]:
        """列出所有资源"""
        resources = []

        try:
            # 设置认证
            if self.service_account_json:
                import os
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.service_account_json

            # 列出Dialogflow CX agents
            try:
                from google.cloud.dialogflowcx_v3 import AgentsClient

                client = AgentsClient()
                parent = f"projects/{self.project_id}/locations/{self.location}"

                agents = client.list_agents(parent=parent)
                for agent in agents:
                    resource = CloudResource(
                        provider="gcp",
                        resource_type=ResourceType.KNOWLEDGE_BASE,
                        resource_id=agent.name.split('/')[-1],
                        name=agent.display_name,
                        status=ResourceStatus.ACTIVE,
                        region=self.location,
                        config={
                            "full_name": agent.name,
                        }
                    )
                    resources.append(resource)
            except Exception as e:
                logger.debug(f"列出Dialogflow CX agents失败: {e}")

        except ImportError:
            logger.warning("Google Cloud SDK未安装，跳过资源查询")
        except Exception as e:
            logger.error(f"查询GCP资源失败: {e}")

        return resources

    async def create_knowledge_base(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建Dialogflow CX Agent"""
        try:
            if self.service_account_json:
                import os
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.service_account_json

            from google.cloud.dialogflowcx_v3 import AgentsClient, Agent

            client = AgentsClient()
            parent = f"projects/{self.project_id}/locations/{self.location}"

            # 创建Agent
            agent = Agent(
                display_name=name,
                default_language_code=config.get("language", "zh-CN"),
                time_zone=config.get("timezone", "Asia/Shanghai"),
            )

            response = client.create_agent(parent=parent, agent=agent)
            agent_id = response.name.split('/')[-1]

            logger.info(f"Dialogflow CX Agent创建成功: {agent_id}")

            return CloudResource(
                provider="gcp",
                resource_type=ResourceType.KNOWLEDGE_BASE,
                resource_id=agent_id,
                name=name,
                status=ResourceStatus.ACTIVE,
                region=self.location,
                created_at=datetime.now(),
                config={
                    "full_name": response.name,
                }
            )

        except ImportError:
            raise RuntimeError("请安装Google Cloud SDK: pip install google-cloud-dialogflow-cx")
        except Exception as e:
            logger.error(f"创建Dialogflow CX Agent失败: {e}")
            raise

    async def create_memory(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> CloudResource:
        """创建Vertex AI Memory Bank（暂不支持）"""
        raise NotImplementedError("Vertex AI Memory Bank暂不支持自动创建，请在控制台创建")

    async def delete_resource(self, resource_id: str) -> bool:
        """删除资源"""
        try:
            if self.service_account_json:
                import os
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.service_account_json

            from google.cloud.dialogflowcx_v3 import AgentsClient

            client = AgentsClient()
            name = f"projects/{self.project_id}/locations/{self.location}/agents/{resource_id}"

            client.delete_agent(name=name)
            logger.info(f"Dialogflow CX Agent删除成功: {resource_id}")
            return True

        except Exception as e:
            logger.error(f"删除GCP资源失败: {e}")
            return False

    async def get_resource_status(self, resource_id: str) -> Optional[CloudResource]:
        """获取资源状态"""
        try:
            if self.service_account_json:
                import os
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.service_account_json

            from google.cloud.dialogflowcx_v3 import AgentsClient

            client = AgentsClient()
            name = f"projects/{self.project_id}/locations/{self.location}/agents/{resource_id}"

            agent = client.get_agent(name=name)
            if agent:
                return CloudResource(
                    provider="gcp",
                    resource_type=ResourceType.KNOWLEDGE_BASE,
                    resource_id=resource_id,
                    name=agent.display_name,
                    status=ResourceStatus.ACTIVE,
                    region=self.location,
                    config={
                        "full_name": agent.name,
                    }
                )

        except Exception as e:
            logger.debug(f"获取GCP资源状态失败: {e}")

        return None
