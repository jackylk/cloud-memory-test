"""基准测试套件集合"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import asyncio

from ..adapters.base import KnowledgeBaseAdapter, MemoryAdapter
from ..core.orchestrator import TestResult, BenchmarkSuiteResult
from ..utils.logger import StepLogger
from .knowledge_base import (
    KnowledgeBaseBenchmark,
    KBTestConfig,
    KB_QUICK_TEST,
    KB_FULL_TEST,
    KB_STRESS_TEST,
)
from .memory import (
    MemoryBenchmark,
    MemoryTestConfig,
    MEMORY_QUICK_TEST,
    MEMORY_FULL_TEST,
    MEMORY_STRESS_TEST,
)


@dataclass
class BenchmarkSuiteConfig:
    """基准测试套件配置"""
    name: str
    description: str
    kb_config: Optional[KBTestConfig] = None
    memory_config: Optional[MemoryTestConfig] = None
    run_kb: bool = True
    run_memory: bool = True


class BenchmarkSuite:
    """基准测试套件

    组合知识库和记忆系统的测试。
    """

    def __init__(
        self,
        config: BenchmarkSuiteConfig,
    ):
        """初始化基准测试套件

        Args:
            config: 套件配置
        """
        self.config = config
        self.step_logger = StepLogger(f"Suite: {config.name}")

        # 创建子测试
        self.kb_benchmark = None
        self.memory_benchmark = None

        if config.run_kb and config.kb_config:
            self.kb_benchmark = KnowledgeBaseBenchmark(config=config.kb_config)

        if config.run_memory and config.memory_config:
            self.memory_benchmark = MemoryBenchmark(config=config.memory_config)

    async def run(
        self,
        kb_adapters: Optional[Dict[str, KnowledgeBaseAdapter]] = None,
        memory_adapters: Optional[Dict[str, MemoryAdapter]] = None,
    ) -> BenchmarkSuiteResult:
        """运行基准测试套件

        Args:
            kb_adapters: 知识库适配器字典 {名称: 适配器}
            memory_adapters: 记忆系统适配器字典 {名称: 适配器}

        Returns:
            测试套件结果
        """
        result = BenchmarkSuiteResult(
            suite_name=self.config.name,
            start_time=datetime.now(),
        )

        self.step_logger.start(self.config.name)

        # 运行知识库测试
        if self.kb_benchmark and kb_adapters:
            self.step_logger.step("知识库测试", f"{len(kb_adapters)} 个适配器")

            for name, adapter in kb_adapters.items():
                try:
                    kb_results = await self.kb_benchmark.run(adapter, name)
                    result.results.extend(kb_results)
                except Exception as e:
                    self.step_logger.step(f"错误: {name}", str(e))

        # 运行记忆系统测试
        if self.memory_benchmark and memory_adapters:
            self.step_logger.step("记忆系统测试", f"{len(memory_adapters)} 个适配器")

            for name, adapter in memory_adapters.items():
                try:
                    memory_results = await self.memory_benchmark.run(adapter, name)
                    result.results.extend(memory_results)
                except Exception as e:
                    self.step_logger.step(f"错误: {name}", str(e))

        result.end_time = datetime.now()
        result.total_duration_seconds = (
            result.end_time - result.start_time
        ).total_seconds()

        self.step_logger.complete(
            f"完成 {len(result.results)} 个测试，"
            f"耗时 {result.total_duration_seconds:.2f}s"
        )

        return result

    def get_summary(self) -> Dict[str, Any]:
        """获取测试摘要"""
        summary = {
            "suite_name": self.config.name,
            "description": self.config.description,
        }

        if self.kb_benchmark:
            summary["knowledge_base"] = self.kb_benchmark.get_summary()

        if self.memory_benchmark:
            summary["memory"] = self.memory_benchmark.get_summary()

        return summary


# 预定义的测试套件


def get_quick_suite() -> BenchmarkSuite:
    """获取快速测试套件

    用于快速验证适配器功能。
    """
    config = BenchmarkSuiteConfig(
        name="快速测试套件",
        description="快速验证知识库和记忆系统功能",
        kb_config=KB_QUICK_TEST,
        memory_config=MEMORY_QUICK_TEST,
    )
    return BenchmarkSuite(config)


def get_full_suite() -> BenchmarkSuite:
    """获取完整测试套件

    完整的性能测试，包含多个数据规模和并发级别。
    """
    config = BenchmarkSuiteConfig(
        name="完整测试套件",
        description="完整的知识库和记忆系统性能测试",
        kb_config=KB_FULL_TEST,
        memory_config=MEMORY_FULL_TEST,
    )
    return BenchmarkSuite(config)


def get_stress_suite() -> BenchmarkSuite:
    """获取压力测试套件

    高并发压力测试。
    """
    config = BenchmarkSuiteConfig(
        name="压力测试套件",
        description="知识库和记忆系统高并发压力测试",
        kb_config=KB_STRESS_TEST,
        memory_config=MEMORY_STRESS_TEST,
    )
    return BenchmarkSuite(config)


def get_kb_only_suite(config: KBTestConfig = KB_FULL_TEST) -> BenchmarkSuite:
    """获取仅知识库测试套件"""
    suite_config = BenchmarkSuiteConfig(
        name=f"知识库测试: {config.name}",
        description=config.description,
        kb_config=config,
        memory_config=None,
        run_kb=True,
        run_memory=False,
    )
    return BenchmarkSuite(suite_config)


def get_memory_only_suite(config: MemoryTestConfig = MEMORY_FULL_TEST) -> BenchmarkSuite:
    """获取仅记忆系统测试套件"""
    suite_config = BenchmarkSuiteConfig(
        name=f"记忆系统测试: {config.name}",
        description=config.description,
        kb_config=None,
        memory_config=config,
        run_kb=False,
        run_memory=True,
    )
    return BenchmarkSuite(suite_config)
