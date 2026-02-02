#!/usr/bin/env python3
"""记忆系统测试脚本

测试所有记忆系统适配器并生成独立测试报告

使用方式:
    python test_memory_systems.py              # 运行所有测试
    python test_memory_systems.py --scale tiny # 指定数据规模
    python test_memory_systems.py --skip-local # 跳过本地适配器

支持的数据规模:
    tiny   - 10用户, 20条记忆（默认，快速测试）
    small  - 50用户, 100条记忆
    medium - 100用户, 500条记忆
"""

import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.utils.config import load_config
from src.adapters.memory import (
    Mem0LocalAdapter,
    AWSBedrockMemoryAdapter,
    VolcengineAgentKitMemoryAdapter,
    AlibabaBailianMemoryAdapter,
)
from src.core.benchmark_runner import BenchmarkRunner
from src.report.generator import ReportGenerator


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="记忆系统性能测试工具")
    parser.add_argument(
        "--scale",
        "-s",
        default="tiny",
        choices=["tiny", "small", "medium"],
        help="数据规模（默认：tiny）"
    )
    parser.add_argument(
        "--skip-local",
        action="store_true",
        help="跳过本地适配器测试"
    )
    parser.add_argument(
        "--adapters",
        "-a",
        nargs="+",
        help="指定要测试的适配器（如：mem0 aws volcengine aliyun）"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="docs/test-reports",
        help="报告输出目录（默认：docs/test-reports）"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出"
    )
    return parser.parse_args()


async def main():
    """主测试流程"""
    # 解析命令行参数
    args = parse_args()

    # 设置日志级别
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    logger.info("=" * 80)
    logger.info("云端记忆系统性能测试")
    logger.info("=" * 80)
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"数据规模: {args.scale}")

    # 加载配置
    config = load_config()
    logger.info(f"运行模式: {config.mode}")

    # 准备测试适配器
    adapters = []
    adapter_map = {
        "mem0": ("Mem0LocalAdapter", lambda: Mem0LocalAdapter({
            "vector_store": config.local.mem0.vector_store,
            "embedding_model": config.local.mem0.embedding_model,
            "use_simple_store": True,
        })),
        "aws": ("AWSBedrockMemory", lambda: AWSBedrockMemoryAdapter({
            "region": config.aws.region,
            "memory_id": getattr(config.aws, 'memory_id', None),
            "access_key_id": config.aws.access_key_id.get_secret_value() if config.aws.access_key_id else None,
            "secret_access_key": config.aws.secret_access_key.get_secret_value() if config.aws.secret_access_key else None,
        })),
        "volcengine": ("VolcengineAgentKitMemory", lambda: VolcengineAgentKitMemoryAdapter({
            "region": config.volcengine.region,
            "collection_name": getattr(config.volcengine, 'memory_collection_name', 'cloud_memory_test_ltm'),
            "access_key": config.volcengine.access_key.get_secret_value() if config.volcengine.access_key else None,
            "secret_key": config.volcengine.secret_key.get_secret_value() if config.volcengine.secret_key else None,
        })),
        "aliyun": ("AlibabaBailianMemory", lambda: AlibabaBailianMemoryAdapter({
            "workspace_id": getattr(config.aliyun, 'workspace_id', None),
            "memory_id": getattr(config.aliyun, 'memory_id_for_longterm', None),
            "endpoint": getattr(config.aliyun, 'endpoint', 'bailian.cn-beijing.aliyuncs.com'),
            "access_key_id": config.aliyun.access_key_id.get_secret_value() if config.aliyun.access_key_id else None,
            "access_key_secret": config.aliyun.access_key_secret.get_secret_value() if config.aliyun.access_key_secret else None,
        })),
    }

    # 根据参数选择适配器
    if args.adapters:
        # 用户指定的适配器
        for adapter_key in args.adapters:
            if adapter_key in adapter_map:
                name, factory = adapter_map[adapter_key]
                adapters.append((name, factory()))
                logger.info(f"✓ 添加 {name}")
            else:
                logger.warning(f"⚠ 未知的适配器: {adapter_key}")
    else:
        # 默认：根据模式和参数选择
        if not args.skip_local:
            name, factory = adapter_map["mem0"]
            adapters.append((name, factory()))
            logger.info(f"✓ 添加 {name} (基准)")

        if config.mode == "cloud":
            for key in ["aws", "volcengine", "aliyun"]:
                name, factory = adapter_map[key]
                adapters.append((name, factory()))
                logger.info(f"✓ 添加 {name}")

    if not adapters:
        logger.error("没有可测试的适配器")
        return

    logger.info(f"\n共 {len(adapters)} 个记忆系统待测试\n")

    # 初始化测试运行器
    config_dict = config.model_dump()
    runner = BenchmarkRunner(config_dict)

    # 运行测试
    results = []
    failed_tests = []

    for i, (name, adapter) in enumerate(adapters, 1):
        logger.info("=" * 80)
        logger.info(f"[{i}/{len(adapters)}] 测试 {name}")
        logger.info("=" * 80)

        try:
            # 检查适配器状态
            await adapter.initialize()
            is_mock = getattr(adapter, 'mock_mode', False)
            if is_mock:
                logger.warning(f"  ⚠ {name} 运行在 Mock 模式（未配置凭证或资源ID）")

            result = await runner.run_memory_benchmark(
                adapter,
                data_scale=args.scale
            )
            results.append(result)
            logger.info(f"  ✓ {name} 测试完成")

            # 显示简要结果
            if result.latency:
                logger.info(f"    延迟: P50={result.latency.p50:.2f}ms, P95={result.latency.p95:.2f}ms")
            if result.throughput:
                logger.info(f"    吞吐: {result.throughput.qps:.2f} QPS, 成功率={100-result.throughput.error_rate*100:.1f}%")

        except Exception as e:
            logger.error(f"  ✗ {name} 测试失败: {e}")
            failed_tests.append((name, str(e)))
            if args.verbose:
                import traceback
                logger.error(traceback.format_exc())

        logger.info("")
    
    # 输出结果摘要
    logger.info("")
    logger.info("=" * 80)
    logger.info("测试结果摘要")
    logger.info("=" * 80)

    if results:
        # 性能对比表格
        logger.info("\n性能对比:")
        logger.info(f"{'适配器':<30} {'P50延迟':<12} {'P95延迟':<12} {'QPS':<10} {'成功率':<10}")
        logger.info("-" * 80)

        for result in results:
            p50 = f"{result.latency.p50:.2f}ms" if result.latency else "N/A"
            p95 = f"{result.latency.p95:.2f}ms" if result.latency else "N/A"
            qps = f"{result.throughput.qps:.2f}" if result.throughput else "N/A"
            success_rate = (
                f"{100 - result.throughput.error_rate * 100:.1f}%"
                if result.throughput
                else "N/A"
            )

            logger.info(
                f"{result.adapter_name:<30} "
                f"{p50:<12} "
                f"{p95:<12} "
                f"{qps:<10} "
                f"{success_rate:<10}"
            )

        # 找出最佳性能
        if len(results) > 1:
            best_latency = min(results, key=lambda r: r.latency.p50 if r.latency else float('inf'))
            best_throughput = max(results, key=lambda r: r.throughput.qps if r.throughput else 0)

            logger.info("\n最佳性能:")
            logger.info(f"  最低延迟: {best_latency.adapter_name} (P50={best_latency.latency.p50:.2f}ms)")
            logger.info(f"  最高吞吐: {best_throughput.adapter_name} ({best_throughput.throughput.qps:.2f} QPS)")

    # 显示失败的测试
    if failed_tests:
        logger.info("\n失败的测试:")
        for name, error in failed_tests:
            logger.info(f"  ✗ {name}: {error}")

    # 生成测试报告
    if results:
        logger.info("")
        logger.info("=" * 80)
        logger.info("生成测试报告...")
        logger.info("=" * 80)

        test_config = {
            "mode": config.mode,
            "scale": args.scale,
            "test_type": "memory",
            "start_time": datetime.now().isoformat(),
            "adapters_tested": len(results),
            "adapters_failed": len(failed_tests),
        }

        generator = ReportGenerator()
        generated_files = generator.generate_report(
            results=[r.to_dict() for r in results],
            config=test_config,
            output_dir=args.output_dir,
            formats=["markdown", "html"]
        )

        logger.info("✓ 报告生成完成:")
        for fmt, path in generated_files.items():
            logger.info(f"  {fmt}: {path}")

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"测试完成！总耗时: {datetime.now()}")
    logger.info("=" * 80)

    # 返回状态码
    return 0 if not failed_tests else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
