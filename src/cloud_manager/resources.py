"""云资源定义"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


class ResourceType(Enum):
    """资源类型"""
    KNOWLEDGE_BASE = "knowledge_base"
    MEMORY = "memory"
    VECTOR_STORE = "vector_store"


class ResourceStatus(Enum):
    """资源状态"""
    CREATING = "creating"
    ACTIVE = "active"
    DELETING = "deleting"
    DELETED = "deleted"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class CloudResource:
    """云资源"""
    # 基本信息
    provider: str  # aws, gcp, volcengine, aliyun, huawei
    resource_type: ResourceType
    resource_id: str
    name: str

    # 状态信息
    status: ResourceStatus
    region: str
    created_at: Optional[datetime] = None

    # 配置信息
    config: Dict[str, Any] = None

    # 费用信息（可选）
    estimated_cost_per_hour: Optional[float] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "provider": self.provider,
            "resource_type": self.resource_type.value,
            "resource_id": self.resource_id,
            "name": self.name,
            "status": self.status.value,
            "region": self.region,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "config": self.config,
            "estimated_cost_per_hour": self.estimated_cost_per_hour,
        }
