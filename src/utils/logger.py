"""日志工具 - 支持详细的步骤输出"""

import sys
import time
from typing import Optional, Any
from contextlib import contextmanager
from loguru import logger


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    verbose: bool = False
) -> None:
    """配置日志系统"""
    # 移除默认处理器
    logger.remove()

    # 控制台格式
    if verbose:
        console_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <7}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
    else:
        console_format = (
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <7}</level> | "
            "<level>{message}</level>"
        )

    # 添加控制台处理器
    logger.add(
        sys.stderr,
        format=console_format,
        level=level,
        colorize=True,
    )

    # 添加文件处理器
    if log_file:
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {name}:{function}:{line} | {message}",
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
        )


def get_logger(name: str = "benchmark"):
    """获取命名的日志器"""
    return logger.bind(name=name)


class StepLogger:
    """步骤日志器 - 用于清晰地输出测试步骤

    支持两种使用方式:
    1. 上下文管理器模式: with step_logger.step("描述") as ctx: ...
    2. 简单模式: step_logger.start("名称"), step_logger.step("名称", "详情"), step_logger.complete("总结")
    """

    def __init__(self, task_name: str = "测试", total_steps: int = 0):
        """初始化步骤日志器

        Args:
            task_name: 任务名称
            total_steps: 总步骤数（可选，用于显示进度）
        """
        # 支持旧版 (total_steps, task_name) 参数顺序
        if isinstance(task_name, int):
            total_steps, task_name = task_name, total_steps if isinstance(total_steps, str) else "测试"

        self.task_name = task_name
        self.total_steps = total_steps
        self.current_step = 0
        self.step_times: list[float] = []
        self._start_time: Optional[float] = None

    def start(self, name: Optional[str] = None):
        """开始任务"""
        self._start_time = time.time()
        display_name = name or self.task_name
        logger.info("")
        logger.info("=" * 50)
        logger.info(f">>> {display_name} <<<")
        logger.info("=" * 50)

    def end(self, summary: Optional[dict] = None):
        """结束任务（兼容旧接口）"""
        logger.info("=" * 50)
        logger.info(f"========== {self.task_name} 完成 ==========")
        if summary:
            for key, value in summary.items():
                logger.info(f"  {key}: {value}")
        logger.info("=" * 50)

    def complete(self, summary: str = ""):
        """完成任务"""
        elapsed = time.time() - self._start_time if self._start_time else 0
        logger.info("-" * 50)
        if summary:
            logger.info(f"✓ 完成: {summary} (耗时 {elapsed:.2f}s)")
        else:
            logger.info(f"✓ {self.task_name} 完成 (耗时 {elapsed:.2f}s)")
        logger.info("")

    @contextmanager
    def step_context(self, description: str):
        """执行一个步骤（上下文管理器模式）"""
        self.current_step += 1
        if self.total_steps > 0:
            step_label = f"[步骤 {self.current_step}/{self.total_steps}]"
        else:
            step_label = f"[{self.current_step}]"

        logger.info(f"{step_label} {description}")
        start_time = time.time()

        try:
            yield StepContext(step_label)
            elapsed = time.time() - start_time
            self.step_times.append(elapsed)
            logger.info(f"  ✓ 完成 ({elapsed:.2f}s)")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"  ✗ 失败 ({elapsed:.2f}s): {e}")
            raise

    def step(self, step_name: str, detail: str = ""):
        """输出一个步骤

        支持两种使用方式:
        1. 上下文管理器: with step_logger.step("描述") as ctx: ...
        2. 简单模式: step_logger.step("名称", "详情")

        Args:
            step_name: 步骤名称
            detail: 步骤详情（可选）

        Returns:
            如果没有 detail，返回上下文管理器（用于 with 语句）
            如果有 detail，返回 None（简单模式）
        """
        if detail:
            # 简单模式：直接输出
            self.current_step += 1
            step_time = time.time()
            self.step_times.append(step_time)

            if self.total_steps > 0:
                progress = f"[{self.current_step}/{self.total_steps}]"
            else:
                progress = f"[{self.current_step}]"

            logger.info(f"{progress} {step_name}: {detail}")
            return None
        else:
            # 上下文管理器模式
            return self.step_context(step_name)

    def detail(self, message: str):
        """输出步骤详情"""
        logger.debug(f"  → {message}")

    def result(self, message: str):
        """输出步骤结果"""
        logger.info(f"  → {message}")


class StepContext:
    """步骤上下文 - 用于在步骤内输出详情"""

    def __init__(self, step_label: str):
        self.step_label = step_label

    def detail(self, message: str):
        """输出详情（DEBUG级别）"""
        logger.debug(f"  → {message}")

    def info(self, message: str):
        """输出信息（INFO级别）"""
        logger.info(f"  → {message}")

    def result(self, key: str, value: Any):
        """输出结果"""
        logger.info(f"  → {key}: {value}")

    def progress(self, current: int, total: int, item: str = ""):
        """输出进度"""
        percent = (current / total) * 100 if total > 0 else 0
        msg = f"  → 进度: {current}/{total} ({percent:.1f}%)"
        if item:
            msg += f" - {item}"
        logger.debug(msg)
