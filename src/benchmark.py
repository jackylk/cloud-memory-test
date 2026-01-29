"""基准测试 CLI - 云端知识库和记忆系统性能测试工具

使用方式:
    python -m src benchmark --help
    python -m src compare -t kb -s tiny
    python -m src run-suite --suite quick
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime
import click
from loguru import logger

from .utils.config import load_config, Config
from .utils.logger import setup_logger
from .adapters.knowledge_base import SimpleVectorStore, MilvusAdapter, PineconeAdapter
from .adapters.memory import Mem0LocalAdapter, MilvusMemoryAdapter
from .core.benchmark_runner import BenchmarkRunner
from .core.orchestrator import TestOrchestrator, TestType, ConcurrencyConfig


def get_adapters(config: Config, adapter_type: str, adapter_names: list = None):
    """根据配置获取适配器列表

    Args:
        config: 配置对象
        adapter_type: "knowledge_base" 或 "memory"
        adapter_names: 指定要使用的适配器名称列表

    Returns:
        适配器字典 {名称: 适配器}
    """
    adapters = {}

    if config.mode == "local":
        # 本地模式：使用本地适配器
        if adapter_type == "knowledge_base":
            all_adapters = {
                "SimpleVectorStore": SimpleVectorStore({}),
                "MilvusAdapter": MilvusAdapter({
                    "collection_name": "benchmark_kb",
                    "dimension": 384,
                    "db_path": "./milvus_benchmark.db",
                    "use_lite": True,
                }),
                "PineconeAdapter": PineconeAdapter({
                    "index_name": "benchmark_kb",
                    "dimension": 384,
                    "mock_mode": True,  # 无 API Key 时使用模拟模式
                }),
            }
        elif adapter_type == "memory":
            all_adapters = {
                "Mem0LocalAdapter": Mem0LocalAdapter({
                    "vector_store": config.local.mem0.vector_store,
                    "embedding_model": config.local.mem0.embedding_model,
                    "use_simple_store": True,
                }),
                "MilvusMemoryAdapter": MilvusMemoryAdapter({
                    "collection_name": "benchmark_memory",
                    "dimension": 384,
                    "db_path": "./milvus_memory_benchmark.db",
                    "use_lite": True,
                }),
            }
        else:
            all_adapters = {}

        # 筛选指定的适配器
        if adapter_names:
            for name in adapter_names:
                if name in all_adapters:
                    adapters[name] = all_adapters[name]
        else:
            adapters = all_adapters

    elif config.mode == "cloud":
        # 云模式：使用云服务适配器
        # TODO: 添加云服务适配器
        logger.warning("云模式尚未实现，回退到本地模式")
        return get_adapters(Config(mode="local"), adapter_type, adapter_names)

    return adapters


def get_adapter_list(config: Config, adapter_type: str) -> list:
    """获取适配器列表（兼容旧接口）"""
    adapters_dict = get_adapters(config, adapter_type)
    return list(adapters_dict.values())


@click.group()
@click.option("--config", "-c", default=None, help="配置文件路径")
@click.option("--verbose", "-v", is_flag=True, help="详细输出")
@click.pass_context
def cli(ctx, config, verbose):
    """云端知识库和记忆系统性能测试工具"""
    ctx.ensure_object(dict)

    # 加载配置
    cfg = load_config(config)

    # 设置日志
    log_level = "DEBUG" if verbose else cfg.debug.log_level
    setup_logger(level=log_level, verbose=verbose or cfg.debug.verbose)

    ctx.obj["config"] = cfg
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--scale", "-s", default="tiny", type=click.Choice(["tiny", "small", "medium", "large"]))
@click.option("--type", "-t", "test_type", default="all", type=click.Choice(["all", "kb", "memory"]))
@click.option("--output", "-o", default=None, help="结果输出文件")
@click.option("--report", "-r", is_flag=True, help="自动生成测试报告")
@click.option("--report-dir", default="docs/test-reports", help="报告输出目录")
@click.pass_context
def benchmark(ctx, scale, test_type, output, report, report_dir):
    """运行基准测试

    示例:
        python -m src.main benchmark --scale tiny --type all
        python -m src.main benchmark -s small -t kb -o results.json
        python -m src.main benchmark -s tiny -r  # 自动生成报告
    """
    config: Config = ctx.obj["config"]

    logger.info("=" * 60)
    logger.info("云端知识库和记忆系统性能测试")
    logger.info("=" * 60)
    logger.info(f"运行模式: {config.mode}")
    logger.info(f"数据规模: {scale}")
    logger.info(f"测试类型: {test_type}")
    logger.info("=" * 60)

    # 转换配置为字典
    config_dict = config.model_dump()
    config_dict["debug"] = {
        "verbose": ctx.obj["verbose"],
        "print_results": config.debug.print_results,
        "save_raw_data": config.debug.save_raw_data,
    }

    runner = BenchmarkRunner(config_dict)

    async def run_tests():
        results = []

        # 知识库测试
        if test_type in ["all", "kb"]:
            logger.info("")
            logger.info(">>> 开始知识库测试 <<<")
            kb_adapters = get_adapter_list(config, "knowledge_base")

            for adapter in kb_adapters:
                try:
                    result = await runner.run_knowledge_base_benchmark(
                        adapter,
                        data_scale=scale,
                        run_quality_test=True
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"知识库测试失败 [{adapter.name}]: {e}")

        # 记忆系统测试
        if test_type in ["all", "memory"]:
            logger.info("")
            logger.info(">>> 开始记忆系统测试 <<<")
            memory_adapters = get_adapter_list(config, "memory")

            for adapter in memory_adapters:
                try:
                    result = await runner.run_memory_benchmark(
                        adapter,
                        data_scale=scale
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"记忆系统测试失败 [{adapter.name}]: {e}")

        return results

    # 运行测试
    results = asyncio.run(run_tests())

    # 输出结果摘要
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果摘要")
    logger.info("=" * 60)

    for result in results:
        logger.info(f"\n[{result.adapter_name}] ({result.adapter_type})")
        logger.info(f"  数据规模: {result.data_scale}")
        if result.latency:
            logger.info(f"  延迟: P50={result.latency.p50:.2f}ms, P95={result.latency.p95:.2f}ms, P99={result.latency.p99:.2f}ms")
        if result.throughput:
            logger.info(f"  吞吐: {result.throughput.qps:.2f} QPS, 成功率={100-result.throughput.error_rate*100:.1f}%")
        if result.quality:
            logger.info(f"  质量: P@1={result.quality.precision_at_1:.3f}, MRR={result.quality.mrr:.3f}")

    # 保存结果
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "config": {
                        "mode": config.mode,
                        "scale": scale,
                        "test_type": test_type,
                    },
                    "results": [r.to_dict() for r in results]
                },
                f,
                ensure_ascii=False,
                indent=2
            )

        logger.info(f"\n结果已保存到: {output_path}")

    # 生成报告
    if report:
        from .report import ReportGenerator

        logger.info("")
        logger.info("生成测试报告...")

        test_config = {
            "mode": config.mode,
            "scale": scale,
            "test_type": test_type,
        }

        generator = ReportGenerator()
        generated_files = generator.generate_report(
            results=[r.to_dict() for r in results],
            config=test_config,
            output_dir=report_dir,
            formats=["markdown", "html"]
        )

        logger.info("报告生成完成:")
        for fmt, path in generated_files.items():
            logger.info(f"  {fmt}: {path}")


@cli.command()
@click.pass_context
def info(ctx):
    """显示当前配置信息"""
    config: Config = ctx.obj["config"]

    click.echo("\n当前配置:")
    click.echo(f"  运行模式: {config.mode}")
    click.echo(f"  数据规模: {config.data.scale}")
    click.echo(f"  日志级别: {config.debug.log_level}")
    click.echo(f"  详细输出: {config.debug.verbose}")

    click.echo("\n数据规模配置:")
    for scale in ["tiny", "small", "medium", "large"]:
        scale_config = getattr(config.data, scale)
        click.echo(f"  {scale}: {scale_config.doc_count} docs, {scale_config.queries_count} queries")

    click.echo("\n本地适配器配置:")
    click.echo(f"  ChromaDB:")
    click.echo(f"    Embedding: {config.local.chromadb.embedding_model}")
    click.echo(f"    Collection: {config.local.chromadb.collection_name}")
    click.echo(f"  mem0:")
    click.echo(f"    Vector Store: {config.local.mem0.vector_store}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="docs/test-reports", help="输出目录")
@click.option("--format", "-f", "formats", multiple=True, default=["markdown", "html"],
              type=click.Choice(["markdown", "html"]), help="输出格式")
@click.pass_context
def report(ctx, input_file, output, formats):
    """从测试结果生成报告

    示例:
        python -m src.main report results.json
        python -m src.main report results.json -o reports/ -f html
    """
    from .report import ReportGenerator

    config: Config = ctx.obj["config"]

    logger.info("生成测试报告...")
    logger.info(f"输入文件: {input_file}")
    logger.info(f"输出目录: {output}")
    logger.info(f"输出格式: {', '.join(formats)}")

    # 加载测试结果
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    test_config = data.get("config", {})

    if not results:
        logger.error("未找到测试结果数据")
        return

    # 生成报告
    generator = ReportGenerator()
    generated_files = generator.generate_report(
        results=results,
        config=test_config,
        output_dir=output,
        formats=list(formats)
    )

    logger.info("")
    logger.info("报告生成完成:")
    for fmt, path in generated_files.items():
        logger.info(f"  {fmt}: {path}")


@cli.command()
@click.argument("adapter_type", type=click.Choice(["kb", "memory"]))
@click.pass_context
def test_adapter(ctx, adapter_type):
    """快速测试单个适配器

    示例:
        python -m src.main test-adapter kb
        python -m src.main test-adapter memory
    """
    config: Config = ctx.obj["config"]

    logger.info(f"测试适配器: {adapter_type}")

    async def run_test():
        if adapter_type == "kb":
            adapter = SimpleVectorStore({})

            logger.info("初始化 SimpleVectorStore 适配器...")
            await adapter.initialize()

            logger.info("上传测试文档...")
            from .adapters.base import Document, DocumentFormat
            docs = [
                Document(id="test_1", content="这是第一个测试文档，关于机器学习。", format=DocumentFormat.TXT),
                Document(id="test_2", content="这是第二个测试文档，关于深度学习。", format=DocumentFormat.TXT),
                Document(id="test_3", content="这是第三个测试文档，关于自然语言处理。", format=DocumentFormat.TXT),
            ]
            result = await adapter.upload_documents(docs)
            logger.info(f"上传结果: 成功 {result.success_count}, 失败 {result.failed_count}")

            logger.info("构建索引...")
            index_result = await adapter.build_index()
            logger.info(f"索引完成: {index_result.doc_count} 个文档")

            logger.info("执行查询...")
            query_result = await adapter.query("什么是机器学习？", top_k=3)
            logger.info(f"查询延迟: {query_result.latency_ms:.2f}ms")
            logger.info(f"返回结果: {query_result.total_results} 个")
            for i, (doc, score) in enumerate(zip(query_result.documents, query_result.scores)):
                logger.info(f"  {i+1}. [{doc['id']}] score={score:.3f}: {doc['content'][:50]}...")

            await adapter.cleanup()
            logger.info("测试完成")

        elif adapter_type == "memory":
            adapter = Mem0LocalAdapter({
                "use_simple_store": True,
            })

            logger.info("初始化 mem0 适配器...")
            await adapter.initialize()

            logger.info("添加测试记忆...")
            from .adapters.base import Memory
            memories = [
                Memory(id=None, user_id="user_001", content="用户喜欢机器学习相关的内容"),
                Memory(id=None, user_id="user_001", content="用户正在学习深度学习"),
                Memory(id=None, user_id="user_002", content="用户对自然语言处理感兴趣"),
            ]
            for mem in memories:
                result = await adapter.add_memory(mem)
                logger.info(f"添加记忆: {result.memory_id}, 耗时 {result.latency_ms:.2f}ms")

            logger.info("搜索记忆...")
            search_result = await adapter.search_memory("机器学习", "user_001", top_k=3)
            logger.info(f"搜索延迟: {search_result.latency_ms:.2f}ms")
            logger.info(f"返回结果: {search_result.total_results} 个")
            for i, (mem, score) in enumerate(zip(search_result.memories, search_result.scores)):
                logger.info(f"  {i+1}. score={score:.3f}: {mem.content[:50]}...")

            await adapter.cleanup()
            logger.info("测试完成")

    asyncio.run(run_test())


@cli.command()
@click.option("--suite", "-s", default="quick", type=click.Choice(["quick", "full", "stress"]),
              help="测试套件类型")
@click.option("--type", "-t", "test_type", default="all", type=click.Choice(["all", "kb", "memory"]))
@click.option("--adapters", "-a", default=None, help="指定适配器（逗号分隔）")
@click.option("--output", "-o", default=None, help="结果输出目录")
@click.pass_context
def run_suite(ctx, suite, test_type, adapters, output):
    """运行预定义的基准测试套件

    示例:
        python -m src.main run-suite --suite quick
        python -m src.main run-suite -s full -t kb
        python -m src.main run-suite -s quick -a SimpleVectorStore,MilvusAdapter
    """
    from .benchmarks import get_quick_suite, get_full_suite, get_stress_suite

    config: Config = ctx.obj["config"]

    logger.info("=" * 60)
    logger.info(f"运行基准测试套件: {suite}")
    logger.info("=" * 60)

    # 获取套件
    if suite == "quick":
        benchmark_suite = get_quick_suite()
    elif suite == "full":
        benchmark_suite = get_full_suite()
    else:
        benchmark_suite = get_stress_suite()

    # 解析适配器列表
    adapter_names = None
    if adapters:
        adapter_names = [a.strip() for a in adapters.split(",")]

    async def run_tests():
        kb_adapters = None
        memory_adapters = None

        if test_type in ["all", "kb"]:
            kb_adapters = get_adapters(config, "knowledge_base", adapter_names)
            logger.info(f"知识库适配器: {list(kb_adapters.keys())}")

        if test_type in ["all", "memory"]:
            memory_adapters = get_adapters(config, "memory", adapter_names)
            logger.info(f"记忆系统适配器: {list(memory_adapters.keys())}")

        result = await benchmark_suite.run(
            kb_adapters=kb_adapters,
            memory_adapters=memory_adapters,
        )
        return result

    result = asyncio.run(run_tests())

    # 输出结果摘要
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果摘要")
    logger.info("=" * 60)
    logger.info(f"总测试数: {len(result.results)}")
    logger.info(f"总耗时: {result.total_duration_seconds:.2f}s")

    for test_result in result.results:
        logger.info(f"\n[{test_result.adapter_name}] {test_result.test_case_id}")
        logger.info(f"  延迟: P50={test_result.latency.p50:.2f}ms, P95={test_result.latency.p95:.2f}ms")
        logger.info(f"  吞吐: {test_result.throughput.qps:.2f} QPS")
        if test_result.quality:
            logger.info(f"  质量: P@1={test_result.quality.precision_at_1:.3f}, MRR={test_result.quality.mrr:.3f}")

    # 保存结果
    if output:
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"suite_{suite}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "suite_name": result.suite_name,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "total_duration_seconds": result.total_duration_seconds,
                "results": [
                    {
                        "test_case_id": r.test_case_id,
                        "adapter_name": r.adapter_name,
                        "data_scale": r.data_scale,
                        "concurrency": r.concurrency,
                        "latency": r.latency.to_dict(),
                        "throughput": r.throughput.to_dict(),
                        "quality": r.quality.to_dict() if r.quality else None,
                        "details": r.details,
                    }
                    for r in result.results
                ]
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"\n结果已保存到: {output_file}")


@cli.command()
@click.option("--type", "-t", "test_type", default="kb", type=click.Choice(["kb", "memory"]))
@click.option("--adapter", "-a", default=None, help="适配器名称")
@click.option("--concurrency", "-c", default="1,10,50", help="并发级别（逗号分隔）")
@click.option("--duration", "-d", default=30, type=int, help="每个级别的测试时长（秒）")
@click.pass_context
def stress_test(ctx, test_type, adapter, concurrency, duration):
    """运行阶梯式并发压力测试

    示例:
        python -m src.main stress-test -t kb -a MilvusAdapter -c 1,10,50 -d 30
        python -m src.main stress-test -t memory -c 1,5,10
    """
    config: Config = ctx.obj["config"]

    logger.info("=" * 60)
    logger.info("阶梯式并发压力测试")
    logger.info("=" * 60)

    # 解析并发级别
    concurrency_levels = [int(c.strip()) for c in concurrency.split(",")]
    logger.info(f"并发级别: {concurrency_levels}")
    logger.info(f"每级时长: {duration}s")

    async def run_stress():
        orchestrator = TestOrchestrator()

        # 获取适配器
        adapter_names = [adapter] if adapter else None

        if test_type == "kb":
            adapters = get_adapters(config, "knowledge_base", adapter_names)
            test_type_enum = TestType.KNOWLEDGE_BASE
        else:
            adapters = get_adapters(config, "memory", adapter_names)
            test_type_enum = TestType.MEMORY

        if not adapters:
            logger.error("没有可用的适配器")
            return []

        all_results = []

        for name, adapter_instance in adapters.items():
            logger.info(f"\n测试适配器: {name}")

            results = await orchestrator.run_stepped_concurrency_test(
                adapter=adapter_instance,
                adapter_name=name,
                test_type=test_type_enum,
                concurrency_levels=concurrency_levels,
                duration_per_level=duration,
            )
            all_results.extend(results)

        return all_results

    results = asyncio.run(run_stress())

    # 输出结果
    logger.info("")
    logger.info("=" * 60)
    logger.info("压力测试结果")
    logger.info("=" * 60)

    for result in results:
        logger.info(f"\n[{result.adapter_name}] 并发={result.concurrency}")
        logger.info(f"  P50: {result.latency.p50:.2f}ms")
        logger.info(f"  P95: {result.latency.p95:.2f}ms")
        logger.info(f"  P99: {result.latency.p99:.2f}ms")
        logger.info(f"  QPS: {result.throughput.qps:.2f}")
        logger.info(f"  错误率: {result.throughput.error_rate * 100:.2f}%")


@cli.command()
@click.option("--type", "-t", "test_type", default="kb", type=click.Choice(["kb", "memory"]))
@click.option("--scale", "-s", default="tiny", type=click.Choice(["tiny", "small", "medium"]))
@click.option("--queries", "-q", default=10, type=int, help="查询次数")
@click.pass_context
def compare(ctx, test_type, scale, queries):
    """对比所有可用适配器的性能

    示例:
        python -m src.main compare -t kb -s tiny -q 20
        python -m src.main compare -t memory
    """
    config: Config = ctx.obj["config"]

    logger.info("=" * 60)
    logger.info("适配器性能对比")
    logger.info("=" * 60)
    logger.info(f"测试类型: {test_type}")
    logger.info(f"数据规模: {scale}")
    logger.info(f"查询次数: {queries}")

    async def run_comparison():
        from .benchmarks.knowledge_base import KnowledgeBaseBenchmark, KBTestConfig
        from .benchmarks.memory import MemoryBenchmark, MemoryTestConfig

        if test_type == "kb":
            adapters = get_adapters(config, "knowledge_base")
            test_config = KBTestConfig(
                name="对比测试",
                description="适配器对比",
                data_scales=[scale],
                num_queries=queries,
                concurrency_levels=[1],
            )
            benchmark = KnowledgeBaseBenchmark(config=test_config)
        else:
            adapters = get_adapters(config, "memory")
            test_config = MemoryTestConfig(
                name="对比测试",
                description="适配器对比",
                data_scales=[scale],
                num_queries=queries,
                concurrency_levels=[1],
            )
            benchmark = MemoryBenchmark(config=test_config)

        all_results = {}
        for name, adapter in adapters.items():
            logger.info(f"\n测试: {name}")
            try:
                results = await benchmark.run(adapter, name)
                all_results[name] = results
            except Exception as e:
                logger.error(f"测试失败: {e}")
                all_results[name] = None

        return all_results

    results = asyncio.run(run_comparison())

    # 输出对比表格
    logger.info("")
    logger.info("=" * 60)
    logger.info("性能对比结果")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"{'适配器':<25} {'P50(ms)':<10} {'P95(ms)':<10} {'QPS':<10}")
    logger.info("-" * 55)

    for name, result_list in results.items():
        if result_list and len(result_list) > 0:
            result = result_list[0]
            logger.info(
                f"{name:<25} "
                f"{result.latency.p50:<10.2f} "
                f"{result.latency.p95:<10.2f} "
                f"{result.throughput.qps:<10.2f}"
            )
        else:
            logger.info(f"{name:<25} {'失败':<10} {'-':<10} {'-':<10}")


@cli.command()
@click.pass_context
def list_adapters(ctx):
    """列出所有可用的适配器"""
    config: Config = ctx.obj["config"]

    click.echo("\n可用的知识库适配器:")
    kb_adapters = get_adapters(config, "knowledge_base")
    for name in kb_adapters.keys():
        click.echo(f"  - {name}")

    click.echo("\n可用的记忆系统适配器:")
    memory_adapters = get_adapters(config, "memory")
    for name in memory_adapters.keys():
        click.echo(f"  - {name}")


def main():
    """主入口"""
    cli(obj={})


if __name__ == "__main__":
    main()
