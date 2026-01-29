"""限流器模块 - 令牌桶算法实现"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from loguru import logger


@dataclass
class RateLimiterConfig:
    """限流器配置"""
    rate: float = 10.0  # 每秒生成的令牌数
    capacity: float = 100.0  # 桶容量
    name: str = "default"


class RateLimiter:
    """令牌桶限流器

    用于控制请求频率，避免触发云服务限制。
    支持异步操作。
    """

    def __init__(self, rate: float = 10.0, capacity: float = 100.0, name: str = "default"):
        """初始化限流器

        Args:
            rate: 每秒生成的令牌数
            capacity: 桶容量（最大令牌数）
            name: 限流器名称（用于日志）
        """
        self.rate = rate
        self.capacity = capacity
        self.name = name
        self.tokens = capacity  # 初始满桶
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

        logger.debug(f"创建限流器 '{name}': rate={rate}/s, capacity={capacity}")

    async def acquire(self, tokens: int = 1) -> float:
        """获取令牌

        如果令牌不足，会等待直到有足够的令牌。

        Args:
            tokens: 需要获取的令牌数

        Returns:
            实际等待的时间（秒）
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # 补充令牌
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                # 有足够的令牌
                self.tokens -= tokens
                return 0.0

            # 计算需要等待的时间
            wait_time = (tokens - self.tokens) / self.rate
            logger.debug(f"限流器 '{self.name}' 等待 {wait_time:.3f}s")

            await asyncio.sleep(wait_time)

            self.tokens = 0
            self.last_update = time.monotonic()
            return wait_time

    async def try_acquire(self, tokens: int = 1) -> bool:
        """尝试获取令牌（非阻塞）

        Args:
            tokens: 需要获取的令牌数

        Returns:
            是否成功获取
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    @property
    def available_tokens(self) -> float:
        """获取当前可用令牌数"""
        now = time.monotonic()
        elapsed = now - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.rate)

    def reset(self):
        """重置限流器（满桶）"""
        self.tokens = self.capacity
        self.last_update = time.monotonic()


class RateLimiterManager:
    """限流器管理器

    管理多个限流器，为不同的服务/操作提供独立的限流。
    """

    def __init__(self):
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = asyncio.Lock()

    def get_or_create(
        self,
        name: str,
        rate: float = 10.0,
        capacity: float = 100.0
    ) -> RateLimiter:
        """获取或创建限流器

        Args:
            name: 限流器名称
            rate: 每秒生成的令牌数
            capacity: 桶容量

        Returns:
            限流器实例
        """
        if name not in self._limiters:
            self._limiters[name] = RateLimiter(rate, capacity, name)
        return self._limiters[name]

    def get(self, name: str) -> Optional[RateLimiter]:
        """获取限流器"""
        return self._limiters.get(name)

    def remove(self, name: str) -> bool:
        """移除限流器"""
        if name in self._limiters:
            del self._limiters[name]
            return True
        return False

    def reset_all(self):
        """重置所有限流器"""
        for limiter in self._limiters.values():
            limiter.reset()

    @property
    def limiters(self) -> Dict[str, RateLimiter]:
        """获取所有限流器"""
        return self._limiters.copy()


# 默认的全局限流器管理器
_default_manager = RateLimiterManager()


def get_rate_limiter(
    name: str,
    rate: float = 10.0,
    capacity: float = 100.0
) -> RateLimiter:
    """获取限流器的便捷函数

    Args:
        name: 限流器名称
        rate: 每秒生成的令牌数
        capacity: 桶容量

    Returns:
        限流器实例
    """
    return _default_manager.get_or_create(name, rate, capacity)


# 预定义的服务限流配置
SERVICE_RATE_LIMITS = {
    # AWS 服务限流配置
    "aws_bedrock_kb": RateLimiterConfig(rate=5.0, capacity=20.0, name="aws_bedrock_kb"),
    "aws_bedrock_memory": RateLimiterConfig(rate=5.0, capacity=20.0, name="aws_bedrock_memory"),

    # Google Cloud 服务限流配置
    "gcp_dialogflow": RateLimiterConfig(rate=10.0, capacity=50.0, name="gcp_dialogflow"),
    "gcp_vertex": RateLimiterConfig(rate=10.0, capacity=50.0, name="gcp_vertex"),

    # 火山引擎限流配置
    "volcengine_viking": RateLimiterConfig(rate=10.0, capacity=50.0, name="volcengine_viking"),
    "volcengine_agentkit": RateLimiterConfig(rate=10.0, capacity=50.0, name="volcengine_agentkit"),

    # 阿里云限流配置
    "aliyun_bailian": RateLimiterConfig(rate=10.0, capacity=50.0, name="aliyun_bailian"),

    # 华为云限流配置
    "huawei_css": RateLimiterConfig(rate=10.0, capacity=50.0, name="huawei_css"),

    # 本地服务（较高限制）
    "local_milvus": RateLimiterConfig(rate=100.0, capacity=500.0, name="local_milvus"),
    "local_pinecone": RateLimiterConfig(rate=100.0, capacity=500.0, name="local_pinecone"),
    "local_mem0": RateLimiterConfig(rate=100.0, capacity=500.0, name="local_mem0"),
}


def get_service_rate_limiter(service_name: str) -> RateLimiter:
    """获取预定义服务的限流器

    Args:
        service_name: 服务名称

    Returns:
        限流器实例
    """
    config = SERVICE_RATE_LIMITS.get(service_name)
    if config:
        return get_rate_limiter(config.name, config.rate, config.capacity)
    else:
        # 默认配置
        return get_rate_limiter(service_name, rate=10.0, capacity=50.0)
