"""认证管理器模块 - 统一管理各云服务的认证凭证"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger


@dataclass
class AWSCredentials:
    """AWS 凭证"""
    access_key_id: str
    secret_access_key: str
    region: str = "us-east-1"
    session_token: Optional[str] = None

    def to_boto3_config(self) -> Dict[str, str]:
        """转换为 boto3 配置"""
        config = {
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
            "region_name": self.region,
        }
        if self.session_token:
            config["aws_session_token"] = self.session_token
        return config


@dataclass
class GCPCredentials:
    """Google Cloud 凭证"""
    project_id: str
    service_account_json: str  # JSON 文件路径
    location: str = "us-central1"

    def validate(self) -> bool:
        """验证凭证文件是否存在"""
        return Path(self.service_account_json).exists()


@dataclass
class VolcengineCredentials:
    """火山引擎凭证"""
    access_key: str
    secret_key: str
    region: str = "cn-beijing"
    endpoint: Optional[str] = None


@dataclass
class AliyunCredentials:
    """阿里云凭证"""
    access_key_id: str
    access_key_secret: str
    region: str = "cn-hangzhou"
    endpoint: Optional[str] = None


@dataclass
class HuaweiCredentials:
    """华为云凭证"""
    ak: str  # Access Key
    sk: str  # Secret Key
    region: str = "cn-north-4"
    project_id: Optional[str] = None


class AuthManager:
    """统一认证管理器

    支持从配置文件、环境变量或直接传入的方式获取各云服务的凭证。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化认证管理器

        Args:
            config: 配置字典，包含各服务的凭证信息
        """
        self.config = config or {}
        self._credentials_cache: Dict[str, Any] = {}

        logger.debug("认证管理器初始化")

    def get_aws_credentials(self, profile: str = "default") -> Optional[AWSCredentials]:
        """获取 AWS 凭证

        优先级：config > 环境变量 > AWS 配置文件

        Args:
            profile: AWS 配置文件中的 profile 名称

        Returns:
            AWS 凭证对象，如果无法获取则返回 None
        """
        cache_key = f"aws_{profile}"
        if cache_key in self._credentials_cache:
            return self._credentials_cache[cache_key]

        # 1. 从 config 获取
        aws_config = self.config.get("aws", {})
        if aws_config.get("access_key_id") and aws_config.get("secret_access_key"):
            creds = AWSCredentials(
                access_key_id=aws_config["access_key_id"],
                secret_access_key=aws_config["secret_access_key"],
                region=aws_config.get("region", "us-east-1"),
                session_token=aws_config.get("session_token"),
            )
            self._credentials_cache[cache_key] = creds
            logger.debug("从配置获取 AWS 凭证")
            return creds

        # 2. 从环境变量获取
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if access_key and secret_key:
            creds = AWSCredentials(
                access_key_id=access_key,
                secret_access_key=secret_key,
                region=os.environ.get("AWS_REGION", "us-east-1"),
                session_token=os.environ.get("AWS_SESSION_TOKEN"),
            )
            self._credentials_cache[cache_key] = creds
            logger.debug("从环境变量获取 AWS 凭证")
            return creds

        logger.warning("无法获取 AWS 凭证")
        return None

    def get_gcp_credentials(self) -> Optional[GCPCredentials]:
        """获取 Google Cloud 凭证

        优先级：config > 环境变量

        Returns:
            GCP 凭证对象
        """
        if "gcp" in self._credentials_cache:
            return self._credentials_cache["gcp"]

        # 1. 从 config 获取
        gcp_config = self.config.get("gcp", {})
        if gcp_config.get("project_id") and gcp_config.get("service_account_json"):
            creds = GCPCredentials(
                project_id=gcp_config["project_id"],
                service_account_json=gcp_config["service_account_json"],
                location=gcp_config.get("location", "us-central1"),
            )
            self._credentials_cache["gcp"] = creds
            logger.debug("从配置获取 GCP 凭证")
            return creds

        # 2. 从环境变量获取
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        service_account = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if project_id and service_account:
            creds = GCPCredentials(
                project_id=project_id,
                service_account_json=service_account,
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )
            self._credentials_cache["gcp"] = creds
            logger.debug("从环境变量获取 GCP 凭证")
            return creds

        logger.warning("无法获取 GCP 凭证")
        return None

    def get_volcengine_credentials(self) -> Optional[VolcengineCredentials]:
        """获取火山引擎凭证

        Returns:
            火山引擎凭证对象
        """
        if "volcengine" in self._credentials_cache:
            return self._credentials_cache["volcengine"]

        # 1. 从 config 获取
        volc_config = self.config.get("volcengine", {})
        if volc_config.get("access_key") and volc_config.get("secret_key"):
            creds = VolcengineCredentials(
                access_key=volc_config["access_key"],
                secret_key=volc_config["secret_key"],
                region=volc_config.get("region", "cn-beijing"),
                endpoint=volc_config.get("endpoint"),
            )
            self._credentials_cache["volcengine"] = creds
            logger.debug("从配置获取火山引擎凭证")
            return creds

        # 2. 从环境变量获取
        access_key = os.environ.get("VOLCENGINE_ACCESS_KEY")
        secret_key = os.environ.get("VOLCENGINE_SECRET_KEY")
        if access_key and secret_key:
            creds = VolcengineCredentials(
                access_key=access_key,
                secret_key=secret_key,
                region=os.environ.get("VOLCENGINE_REGION", "cn-beijing"),
            )
            self._credentials_cache["volcengine"] = creds
            logger.debug("从环境变量获取火山引擎凭证")
            return creds

        logger.warning("无法获取火山引擎凭证")
        return None

    def get_aliyun_credentials(self) -> Optional[AliyunCredentials]:
        """获取阿里云凭证

        Returns:
            阿里云凭证对象
        """
        if "aliyun" in self._credentials_cache:
            return self._credentials_cache["aliyun"]

        # 1. 从 config 获取
        ali_config = self.config.get("aliyun", {})
        if ali_config.get("access_key_id") and ali_config.get("access_key_secret"):
            creds = AliyunCredentials(
                access_key_id=ali_config["access_key_id"],
                access_key_secret=ali_config["access_key_secret"],
                region=ali_config.get("region", "cn-hangzhou"),
                endpoint=ali_config.get("endpoint"),
            )
            self._credentials_cache["aliyun"] = creds
            logger.debug("从配置获取阿里云凭证")
            return creds

        # 2. 从环境变量获取
        access_key_id = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")
        access_key_secret = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        if access_key_id and access_key_secret:
            creds = AliyunCredentials(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
                region=os.environ.get("ALIBABA_CLOUD_REGION", "cn-hangzhou"),
            )
            self._credentials_cache["aliyun"] = creds
            logger.debug("从环境变量获取阿里云凭证")
            return creds

        logger.warning("无法获取阿里云凭证")
        return None

    def get_huawei_credentials(self) -> Optional[HuaweiCredentials]:
        """获取华为云凭证

        Returns:
            华为云凭证对象
        """
        if "huawei" in self._credentials_cache:
            return self._credentials_cache["huawei"]

        # 1. 从 config 获取
        hw_config = self.config.get("huawei", {})
        if hw_config.get("ak") and hw_config.get("sk"):
            creds = HuaweiCredentials(
                ak=hw_config["ak"],
                sk=hw_config["sk"],
                region=hw_config.get("region", "cn-north-4"),
                project_id=hw_config.get("project_id"),
            )
            self._credentials_cache["huawei"] = creds
            logger.debug("从配置获取华为云凭证")
            return creds

        # 2. 从环境变量获取
        ak = os.environ.get("HUAWEI_CLOUD_AK")
        sk = os.environ.get("HUAWEI_CLOUD_SK")
        if ak and sk:
            creds = HuaweiCredentials(
                ak=ak,
                sk=sk,
                region=os.environ.get("HUAWEI_CLOUD_REGION", "cn-north-4"),
                project_id=os.environ.get("HUAWEI_CLOUD_PROJECT_ID"),
            )
            self._credentials_cache["huawei"] = creds
            logger.debug("从环境变量获取华为云凭证")
            return creds

        logger.warning("无法获取华为云凭证")
        return None

    def get_credentials_status(self) -> Dict[str, bool]:
        """获取各云服务凭证配置状态

        Returns:
            各服务的凭证是否已配置
        """
        return {
            "aws": self.get_aws_credentials() is not None,
            "gcp": self.get_gcp_credentials() is not None,
            "volcengine": self.get_volcengine_credentials() is not None,
            "aliyun": self.get_aliyun_credentials() is not None,
            "huawei": self.get_huawei_credentials() is not None,
        }

    def clear_cache(self):
        """清除凭证缓存"""
        self._credentials_cache.clear()
        logger.debug("凭证缓存已清除")


# 全局认证管理器实例
_auth_manager: Optional[AuthManager] = None


def get_auth_manager(config: Optional[Dict[str, Any]] = None) -> AuthManager:
    """获取认证管理器实例

    Args:
        config: 配置字典

    Returns:
        认证管理器实例
    """
    global _auth_manager
    if _auth_manager is None or config is not None:
        _auth_manager = AuthManager(config)
    return _auth_manager


def init_auth_manager(config: Dict[str, Any]) -> AuthManager:
    """初始化认证管理器

    Args:
        config: 配置字典

    Returns:
        认证管理器实例
    """
    global _auth_manager
    _auth_manager = AuthManager(config)
    return _auth_manager
