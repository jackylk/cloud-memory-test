"""重试机制"""

import asyncio
import functools
from dataclasses import dataclass, field
from typing import Tuple, Type, Callable, Any
from loguru import logger


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (ConnectionError, TimeoutError, OSError)
    )


def with_retry(config: RetryConfig = None):
    """重试装饰器，支持同步和异步函数"""
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                last_exception = None
                for attempt in range(config.max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except config.retryable_exceptions as e:
                        last_exception = e
                        if attempt < config.max_retries:
                            delay = min(
                                config.base_delay * (config.exponential_base ** attempt),
                                config.max_delay
                            )
                            logger.warning(
                                f"重试 {attempt + 1}/{config.max_retries}: {func.__name__} "
                                f"失败 ({type(e).__name__}), {delay:.1f}s 后重试"
                            )
                            await asyncio.sleep(delay)
                        else:
                            logger.error(f"重试耗尽: {func.__name__} 最终失败")
                raise last_exception
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                import time
                last_exception = None
                for attempt in range(config.max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except config.retryable_exceptions as e:
                        last_exception = e
                        if attempt < config.max_retries:
                            delay = min(
                                config.base_delay * (config.exponential_base ** attempt),
                                config.max_delay
                            )
                            logger.warning(
                                f"重试 {attempt + 1}/{config.max_retries}: {func.__name__} "
                                f"失败 ({type(e).__name__}), {delay:.1f}s 后重试"
                            )
                            time.sleep(delay)
                        else:
                            logger.error(f"重试耗尽: {func.__name__} 最终失败")
                raise last_exception
            return sync_wrapper

    return decorator
