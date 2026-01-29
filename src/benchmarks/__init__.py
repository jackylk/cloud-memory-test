"""基准测试套件模块"""

from .knowledge_base import (
    KnowledgeBaseBenchmark,
    KB_QUICK_TEST,
    KB_FULL_TEST,
    KB_STRESS_TEST,
)
from .memory import (
    MemoryBenchmark,
    MEMORY_QUICK_TEST,
    MEMORY_FULL_TEST,
    MEMORY_STRESS_TEST,
)
from .suites import (
    BenchmarkSuite,
    get_quick_suite,
    get_full_suite,
    get_stress_suite,
)

__all__ = [
    "KnowledgeBaseBenchmark",
    "KB_QUICK_TEST",
    "KB_FULL_TEST",
    "KB_STRESS_TEST",
    "MemoryBenchmark",
    "MEMORY_QUICK_TEST",
    "MEMORY_FULL_TEST",
    "MEMORY_STRESS_TEST",
    "BenchmarkSuite",
    "get_quick_suite",
    "get_full_suite",
    "get_stress_suite",
]
