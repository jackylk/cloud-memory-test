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
from .adapters.knowledge_base import SimpleVectorStore, MilvusAdapter, PineconeAdapter, AWSBedrockKBAdapter, OpenSearchServerlessAdapter
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
        if adapter_type == "knowledge_base":
            all_adapters = {}

            # AWS Bedrock KB 适配器
            aws_config = {
                "region": config.aws.region,
                "knowledge_base_id": config.aws.knowledge_base_id,
            }
            if config.aws.access_key_id:
                aws_config["access_key_id"] = config.aws.access_key_id.get_secret_value()
            if config.aws.secret_access_key:
                aws_config["secret_access_key"] = config.aws.secret_access_key.get_secret_value()

            # OpenSearch Serverless 适配器（本地 embedding + 云存储）
            if config.opensearch.host:
                os_config = {
                    "host": config.opensearch.host,
                    "region": config.opensearch.region,
                    "index_name": config.opensearch.index_name,
                    "embedding_model": config.opensearch.embedding_model,
                    "dimension": config.opensearch.dimension,
                }
                if config.aws.access_key_id:
                    os_config["access_key_id"] = config.aws.access_key_id.get_secret_value()
                if config.aws.secret_access_key:
                    os_config["secret_access_key"] = config.aws.secret_access_key.get_secret_value()

                all_adapters["OpenSearchServerless"] = OpenSearchServerlessAdapter(os_config)

            # 只有配置了 knowledge_base_id 才添加 Bedrock 适配器
            if config.aws.knowledge_base_id:
                opensearch_config = aws_config.copy()
                opensearch_config["adapter_name"] = "AWSBedrockKB-OpenSearch"
                all_adapters["AWSBedrockKB-OpenSearch"] = AWSBedrockKBAdapter(opensearch_config)

            # Aurora PostgreSQL 后端的 Bedrock KB
            if config.aws.knowledge_base_id_aurora:
                aws_aurora_config = aws_config.copy()
                aws_aurora_config["knowledge_base_id"] = config.aws.knowledge_base_id_aurora
                aws_aurora_config["adapter_name"] = "AWSBedrockKB-Aurora"
                all_adapters["AWSBedrockKB-Aurora"] = AWSBedrockKBAdapter(aws_aurora_config)

            # 火山引擎 VikingDB 适配器
            from .adapters.knowledge_base.volcengine_vikingdb import VolcengineVikingDBAdapter

            volcengine_config = {
                "region": config.volcengine.region,
                "collection_name": getattr(config.volcengine, 'collection_name', None),
                "host": getattr(config.volcengine, 'host', 'api-knowledgebase.mlp.cn-beijing.volces.com'),
            }
            if config.volcengine.access_key:
                volcengine_config["access_key"] = config.volcengine.access_key.get_secret_value()
            if config.volcengine.secret_key:
                volcengine_config["secret_key"] = config.volcengine.secret_key.get_secret_value()

            all_adapters["VolcengineVikingDB"] = VolcengineVikingDBAdapter(volcengine_config)

            # 阿里百炼适配器
            from .adapters.knowledge_base.alibaba_bailian import AlibabaBailianAdapter

            aliyun_config = {
                "region": config.aliyun.region,
                "workspace_id": getattr(config.aliyun, 'workspace_id', None),
                "index_id": getattr(config.aliyun, 'index_id', None),
                "endpoint": getattr(config.aliyun, 'endpoint', 'bailian.cn-beijing.aliyuncs.com'),
            }
            if config.aliyun.access_key_id:
                aliyun_config["access_key_id"] = config.aliyun.access_key_id.get_secret_value()
            if config.aliyun.access_key_secret:
                aliyun_config["access_key_secret"] = config.aliyun.access_key_secret.get_secret_value()

            all_adapters["AlibabaBailian"] = AlibabaBailianAdapter(aliyun_config)

            # Google Dialogflow CX 适配器 - 已禁用
            # from .adapters.knowledge_base.google_dialogflow_cx import GoogleDialogflowCXAdapter
            #
            # gcp_config = {
            #     "project_id": getattr(config.gcp, 'project_id', None),
            #     "location": config.gcp.location,
            #     "agent_id": getattr(config.gcp, 'agent_id', None),
            #     "data_store_id": getattr(config.gcp, 'data_store_id', None),
            #     "credentials_path": getattr(config.gcp, 'service_account_json', None),
            # }
            # all_adapters["GoogleDialogflowCX"] = GoogleDialogflowCXAdapter(gcp_config)

            # 华为云 CSS 适配器 - 已暂时禁用
            # from .adapters.knowledge_base.huawei_css import HuaweiCSSAdapter
            #
            # huawei_config = {
            #     "region": config.huawei.region,
            #     "cluster_id": getattr(config.huawei, 'cluster_id', None),
            #     "endpoint": getattr(config.huawei, 'endpoint', None),
            #     "index_name": getattr(config.huawei, 'index_name', 'benchmark-test-index'),
            #     "es_username": getattr(config.huawei, 'es_username', 'admin'),
            #     "es_password": getattr(config.huawei, 'es_password', None),
            # }
            # if config.huawei.ak:
            #     huawei_config["ak"] = config.huawei.ak.get_secret_value()
            # if config.huawei.sk:
            #     huawei_config["sk"] = config.huawei.sk.get_secret_value()
            #
            # all_adapters["HuaweiCSS"] = HuaweiCSSAdapter(huawei_config)

        elif adapter_type == "memory":
            # 云模式记忆适配器
            from .adapters.memory.aws_bedrock_memory import AWSBedrockMemoryAdapter
            from .adapters.memory.google_vertex_memory import GoogleVertexMemoryAdapter
            from .adapters.memory.volcengine_agentkit_memory import VolcengineAgentKitMemoryAdapter
            from .adapters.memory.alibaba_bailian_memory import AlibabaBailianMemoryAdapter

            all_adapters = {}

            # 添加本地Mem0作为对比基准
            all_adapters["Mem0LocalAdapter"] = Mem0LocalAdapter({
                "vector_store": config.local.mem0.vector_store,
                "embedding_model": config.local.mem0.embedding_model,
                "use_simple_store": True,
            })

            # AWS Bedrock Memory
            aws_mem_config = {
                "region": config.aws.region,
                "memory_id": getattr(config.aws, 'memory_id', None),
            }
            if config.aws.access_key_id:
                aws_mem_config["access_key_id"] = config.aws.access_key_id.get_secret_value()
            if config.aws.secret_access_key:
                aws_mem_config["secret_access_key"] = config.aws.secret_access_key.get_secret_value()

            all_adapters["AWSBedrockMemory"] = AWSBedrockMemoryAdapter(aws_mem_config)

            # Google Vertex AI Memory - 已禁用
            # gcp_mem_config = {
            #     "project_id": getattr(config.gcp, 'project_id', None),
            #     "location": config.gcp.location,
            #     "memory_bank_id": getattr(config.gcp, 'memory_bank_id', None),
            #     "credentials_path": getattr(config.gcp, 'service_account_json', None),
            # }
            # all_adapters["GoogleVertexMemory"] = GoogleVertexMemoryAdapter(gcp_mem_config)

            # Volcengine AgentKit Memory (使用 VeADK + VikingDB)
            volcengine_mem_config = {
                "region": config.volcengine.region,
                "collection_name": getattr(config.volcengine, 'memory_collection_name', 'cloud_memory_test_ltm'),
            }
            if config.volcengine.access_key:
                volcengine_mem_config["access_key"] = config.volcengine.access_key.get_secret_value()
            if config.volcengine.secret_key:
                volcengine_mem_config["secret_key"] = config.volcengine.secret_key.get_secret_value()

            all_adapters["VolcengineAgentKitMemory"] = VolcengineAgentKitMemoryAdapter(volcengine_mem_config)

            # Alibaba Bailian Memory
            aliyun_mem_config = {
                "workspace_id": getattr(config.aliyun, 'workspace_id', None),
                "memory_id": getattr(config.aliyun, 'memory_id_for_longterm', None),
                "endpoint": getattr(config.aliyun, 'endpoint', 'bailian.cn-beijing.aliyuncs.com'),
            }
            if config.aliyun.access_key_id:
                aliyun_mem_config["access_key_id"] = config.aliyun.access_key_id.get_secret_value()
            if config.aliyun.access_key_secret:
                aliyun_mem_config["access_key_secret"] = config.aliyun.access_key_secret.get_secret_value()

            all_adapters["AlibabaBailianMemory"] = AlibabaBailianMemoryAdapter(aliyun_mem_config)
        else:
            all_adapters = {}

        # 筛选指定的适配器
        if adapter_names:
            for name in adapter_names:
                if name in all_adapters:
                    adapters[name] = all_adapters[name]
        else:
            adapters = all_adapters

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
    """云端知识库和记忆系统性能测试工具

    支持的云服务:
      - AWS Bedrock KB/Memory
      - Google Vertex AI/Dialogflow CX
      - 火山引擎 VikingDB/AgentKit
      - 阿里云百炼
      - 华为云 CSS
      - OpenSearch Serverless

    主要命令:
      benchmark      运行基准测试（推荐）
      list-adapters  列出所有可用的适配器
      compare        对比所有适配器性能
      report         从结果文件生成测试报告
      info           显示当前配置

    快速开始:
      python -m src benchmark -s tiny -t all        # 运行tiny规模全部测试
      python -m src benchmark -s tiny -r            # 运行测试并生成报告
      python -m src list-adapters                   # 查看可用适配器
      python -m src --help                          # 查看完整帮助

    更多信息请查看: docs/README.md
    """
    ctx.ensure_object(dict)

    # 加载配置
    cfg = load_config(config)

    # 设置日志
    log_level = "DEBUG" if verbose else cfg.debug.log_level
    setup_logger(level=log_level, verbose=verbose or cfg.debug.verbose)

    ctx.obj["config"] = cfg
    ctx.obj["verbose"] = verbose


@cli.command()
@click.option("--scale", "-s", default=None, type=click.Choice(["existing", "tiny", "small", "medium", "large"]),
              help="数据规模: existing(已有文档仅查询), tiny/small/medium/large(需生成上传)")
@click.option("--type", "-t", "test_type", default="all", type=click.Choice(["all", "kb", "memory"]),
              help="测试类型: all(全部), kb(知识库), memory(记忆系统)")
@click.option("--output", "-o", default=None, help="保存结果到JSON文件（可选）")
@click.option("--report", "-r", is_flag=True, help="运行后自动生成测试报告")
@click.option("--report-dir", default="docs/test-reports", help="报告输出目录")
@click.option("--skip-upload", is_flag=True, help="跳过文档上传（文档已预先入库）")
@click.pass_context
def benchmark(ctx, scale, test_type, output, report, report_dir, skip_upload):
    """运行基准测试

    知识库已预先入库时（不需 tiny/small 等规模）:
      python -m src benchmark -t kb -r          # 仅查询，不生成/上传，自动生成报告

    数据规模说明（需生成上传时再指定 -s）:
      existing - 已有文档，仅执行查询与质量评估（100 文档规模，5 查询）
      tiny     - 10个文档, 5个查询
      small    - 100个文档, 50个查询
      medium   - 1000个文档, 200个查询
      large    - 10000个文档, 500个查询

    生成测试报告:
      python -m src benchmark -t kb -r          # 知识库测试并生成报告
      python -m src benchmark -s tiny -o results.json && python -m src report results.json
    """
    config: Config = ctx.obj["config"]

    # 未指定规模时：仅知识库则用 existing（已有文档仅查询），否则用 tiny
    if scale is None:
        scale = "existing" if test_type == "kb" else "tiny"
    # existing 规模下知识库测试强制跳过上传，不生成上传数据
    if scale == "existing" and test_type in ["all", "kb"]:
        skip_upload = True

    logger.info("=" * 60)
    logger.info("云端知识库和记忆系统性能测试")
    logger.info("=" * 60)
    logger.info(f"运行模式: {config.mode}")
    logger.info(f"数据规模: {scale}")
    logger.info(f"测试类型: {test_type}")
    if skip_upload and test_type in ["all", "kb"]:
        logger.info("(跳过入库，仅对已有知识库执行查询与质量评估)")
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
                        run_quality_test=True,
                        skip_upload=skip_upload
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
    """显示当前配置信息

    显示运行模式、数据规模配置、适配器配置等信息。
    用于确认配置文件是否正确加载。

    示例:
      python -m src info
    """
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
@click.option("--output", "-o", default="docs/test-reports", help="报告输出目录")
@click.option("--format", "-f", "formats", multiple=True, default=["markdown", "html"],
              type=click.Choice(["markdown", "html"]), help="输出格式（可多选）")
@click.pass_context
def report(ctx, input_file, output, formats):
    """从测试结果JSON文件生成测试报告

    支持的格式:
      - markdown: 适合版本控制和查看
      - html:     适合浏览器查看，包含图表

    使用场景:
      当使用 benchmark -o 保存了结果文件后，可以用此命令生成报告

    示例:
      python -m src report results.json                    # 生成markdown和html报告
      python -m src report results.json -f markdown        # 只生成markdown
      python -m src report results.json -o custom-dir/     # 指定输出目录
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
@click.option("--type", "-t", "test_type", default="kb", type=click.Choice(["kb", "memory"]),
              help="测试类型: kb(知识库) 或 memory(记忆系统)")
@click.option("--scale", "-s", default="tiny", type=click.Choice(["tiny", "small", "medium"]),
              help="数据规模")
@click.option("--queries", "-q", default=10, type=int, help="每个适配器的查询次数")
@click.pass_context
def compare(ctx, test_type, scale, queries):
    """对比所有可用适配器的性能

    快速对比测试，用于评估不同适配器的相对性能。
    会测试所有可用的适配器，并生成性能对比报告。

    示例:
      python -m src compare -t kb -s tiny -q 20      # 对比知识库适配器
      python -m src compare -t memory -q 10          # 对比记忆系统适配器
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
    """列出所有可用的适配器

    显示当前配置下可用的知识库和记忆系统适配器。
    如果某个云服务未配置凭证，该适配器将自动运行在mock模式。

    示例:
      python -m src list-adapters
    """
    config: Config = ctx.obj["config"]

    click.echo("\n可用的知识库适配器:")
    kb_adapters = get_adapters(config, "knowledge_base")
    for name in kb_adapters.keys():
        click.echo(f"  - {name}")

    click.echo("\n可用的记忆系统适配器:")
    memory_adapters = get_adapters(config, "memory")
    for name in memory_adapters.keys():
        click.echo(f"  - {name}")


@cli.command()
@click.option("--action", "-a", type=click.Choice(["list", "info", "create", "delete", "cleanup"]),
              default="list", help="操作类型")
@click.option("--provider", "-p", help="云服务提供商 (aws, volcengine, aliyun, gcp)")
@click.option("--resource-type", "-t", type=click.Choice(["kb", "memory"]),
              help="资源类型 (kb=知识库, memory=记忆库)")
@click.option("--name", "-n", help="资源名称")
@click.option("--resource-id", "-r", help="资源ID（用于查询详情或删除）")
@click.option("--confirm", is_flag=True, help="确认删除操作")
@click.option("--verbose", "-v", is_flag=True, help="显示详细信息")
@click.pass_context
def cloud_resources(ctx, action, provider, resource_type, name, resource_id, confirm, verbose):
    """管理云端知识库和记忆库资源

    用于创建、查询、删除云服务资源，避免闲置资源产生费用。

    操作类型:
      list    - 列出所有云资源（默认）
      info    - 查询资源详细信息
      create  - 创建新资源
      delete  - 删除指定资源
      cleanup - 删除所有资源（危险操作）

    示例:
      # 列出所有资源
      python -m src cloud-resources

      # 查看资源详情
      python -m src cloud-resources -a info -p volcengine -r collection-name

      # 在火山引擎创建知识库
      python -m src cloud-resources -a create -p volcengine -t kb -n test-kb

      # 在阿里云创建记忆库
      python -m src cloud-resources -a create -p aliyun -t memory -n test-memory

      # 删除指定资源
      python -m src cloud-resources -a delete -p volcengine -r collection-name --confirm

      # 清理所有资源（需要确认）
      python -m src cloud-resources -a cleanup --confirm
    """
    from .cloud_manager import CloudResourceManager

    config: Config = ctx.obj["config"]

    async def run_action():
        manager = CloudResourceManager(config)

        if action == "list":
            logger.info("查询云资源...")
            resources = await manager.list_all_resources()

            if not resources:
                click.echo("\n未找到云资源")
                click.echo("提示: 您可以使用 -a create 创建测试资源")
                click.echo(f"\n已配置的云服务: {', '.join(manager.get_configured_providers())}")
                return

            click.echo(f"\n找到 {len(resources)} 个云资源:\n")

            if verbose:
                # 详细模式：显示所有字段
                for i, res in enumerate(resources, 1):
                    click.echo(f"{i}. {res.name}")
                    click.echo(f"   云服务: {res.provider}")
                    click.echo(f"   类型: {res.resource_type.value}")
                    click.echo(f"   资源ID: {res.resource_id}")
                    click.echo(f"   状态: {res.status.value}")
                    click.echo(f"   区域: {res.region}")
                    if res.created_at:
                        click.echo(f"   创建时间: {res.created_at}")
                    if res.config:
                        click.echo(f"   配置: {res.config}")
                    click.echo()
            else:
                # 简洁模式：表格输出
                click.echo(f"{'云服务':<12} {'类型':<15} {'名称':<25} {'资源ID':<30} {'状态':<10}")
                click.echo("-" * 95)

                for res in resources:
                    name_display = res.name[:24] if len(res.name) > 24 else res.name
                    id_display = res.resource_id[:29] if len(res.resource_id) > 29 else res.resource_id
                    click.echo(
                        f"{res.provider:<12} "
                        f"{res.resource_type.value:<15} "
                        f"{name_display:<25} "
                        f"{id_display:<30} "
                        f"{res.status.value:<10}"
                    )

            click.echo(f"\n已配置的云服务: {', '.join(manager.get_configured_providers())}")
            click.echo(f"使用 -v 选项查看详细信息")

        elif action == "info":
            if not provider or not resource_id:
                click.echo("错误: 查询详情需要 --provider 和 --resource-id")
                return

            logger.info(f"查询资源详情: {provider}/{resource_id}")
            resource = await manager.get_resource_status(provider, resource_id)

            if resource:
                click.echo(f"\n资源详情:\n")
                click.echo(f"  云服务: {resource.provider}")
                click.echo(f"  类型: {resource.resource_type.value}")
                click.echo(f"  名称: {resource.name}")
                click.echo(f"  资源ID: {resource.resource_id}")
                click.echo(f"  状态: {resource.status.value}")
                click.echo(f"  区域: {resource.region}")
                if resource.created_at:
                    click.echo(f"  创建时间: {resource.created_at}")
                if resource.config:
                    click.echo(f"\n  配置信息:")
                    for key, value in resource.config.items():
                        click.echo(f"    {key}: {value}")
                if resource.estimated_cost_per_hour:
                    click.echo(f"\n  预估费用: ${resource.estimated_cost_per_hour:.4f}/小时")
            else:
                click.echo(f"\n✗ 未找到资源: {resource_id}")

        elif action == "create":
            if not provider or not resource_type or not name:
                click.echo("错误: 创建资源需要 --provider, --resource-type 和 --name")
                return

            logger.info(f"创建资源: {provider}/{resource_type}/{name}")

            try:
                create_config = {"description": f"Benchmark test - {name}"}

                if resource_type == "kb":
                    create_config["dimension"] = 384
                    resource = await manager.create_knowledge_base(
                        provider,
                        name,
                        create_config
                    )
                else:
                    # 记忆库需要workspace_id
                    if provider == "aliyun":
                        if not hasattr(config.aliyun, 'workspace_id') or not config.aliyun.workspace_id:
                            click.echo("\n✗ 创建阿里云记忆库需要配置 workspace_id")
                            return
                        create_config["workspace_id"] = config.aliyun.workspace_id

                    resource = await manager.create_memory(
                        provider,
                        name,
                        create_config
                    )

                click.echo(f"\n✓ 资源创建成功!")
                click.echo(f"  云服务: {resource.provider}")
                click.echo(f"  类型: {resource.resource_type.value}")
                click.echo(f"  资源ID: {resource.resource_id}")
                click.echo(f"  名称: {resource.name}")
                click.echo(f"  区域: {resource.region}")

                # 更新配置文件提示
                click.echo(f"\n✓ 请将资源ID添加到 config/config.yaml 中:")
                if provider == "volcengine" and resource_type == "kb":
                    click.echo(f"  volcengine:")
                    click.echo(f"    collection_name: \"{resource.resource_id}\"")
                elif provider == "volcengine" and resource_type == "memory":
                    click.echo(f"  volcengine:")
                    click.echo(f"    agent_id: \"{resource.resource_id}\"")
                elif provider == "aliyun" and resource_type == "kb":
                    click.echo(f"  aliyun:")
                    click.echo(f"    index_id: \"{resource.resource_id}\"")
                elif provider == "aliyun" and resource_type == "memory":
                    click.echo(f"  aliyun:")
                    click.echo(f"    memory_id_for_longterm: \"{resource.resource_id}\"")
                elif provider == "aws" and resource_type == "kb":
                    click.echo(f"  aws:")
                    click.echo(f"    knowledge_base_id: \"{resource.resource_id}\"")
                elif provider == "aws" and resource_type == "memory":
                    click.echo(f"  aws:")
                    click.echo(f"    memory_id: \"{resource.resource_id}\"")

            except NotImplementedError as e:
                click.echo(f"\n⚠ {e}")
            except Exception as e:
                click.echo(f"\n✗ 创建失败: {e}")
                import traceback
                if verbose:
                    click.echo(traceback.format_exc())

        elif action == "delete":
            if not provider or not resource_id:
                click.echo("错误: 删除资源需要 --provider 和 --resource-id")
                return

            if not confirm:
                click.echo("警告: 删除操作不可恢复，请使用 --confirm 确认")
                return

            logger.info(f"删除资源: {provider}/{resource_id}")
            success = await manager.delete_resource(provider, resource_id)

            if success:
                click.echo(f"\n✓ 资源删除成功: {resource_id}")
            else:
                click.echo(f"\n✗ 资源删除失败")

        elif action == "cleanup":
            if not confirm:
                click.echo("警告: 此操作将删除所有云资源，不可恢复！")
                click.echo("请使用 --confirm 确认")
                return

            click.echo("开始清理所有云资源...")
            deleted_count = await manager.cleanup_all(confirm=True)
            click.echo(f"\n✓ 已删除 {deleted_count} 个资源")

    asyncio.run(run_action())


@cli.command()
@click.option("--type", "-t", "test_type", default="all", type=click.Choice(["all", "kb", "memory"]),
              help="测试类型: all(全部，默认), kb(知识库), memory(记忆系统)")
@click.option("--scale", "-s", default="tiny", type=click.Choice(["tiny", "small", "medium"]),
              help="数据规模（默认：tiny）")
@click.option("--skip-local", is_flag=True, help="跳过本地适配器测试")
@click.option("--report-dir", default="docs/test-reports", help="报告输出目录")
@click.option("--commit", is_flag=True, help="自动提交到Git（默认不提交）")
@click.option("--commit-message", "-m", default=None, help="自定义提交信息（需要配合--commit使用）")
@click.option("--push", is_flag=True, help="提交后推送到远程（需要配合--commit使用）")
@click.pass_context
def full_test(ctx, test_type, scale, skip_local, report_dir, commit, commit_message, push):
    """运行完整测试流程：测试→生成报告→同步web

    这个命令会自动完成以下步骤：
    1. 运行完整的性能测试（默认：知识库+记忆系统）
    2. 生成Markdown和HTML测试报告
    3. 同步报告到web/reports目录
    4. 可选：Git提交和推送（使用--commit和--push选项）

    示例:
      # 运行完整测试（知识库+记忆系统，默认不提交）
      python -m src full-test

      # 仅测试记忆系统
      python -m src full-test -t memory

      # 仅测试知识库
      python -m src full-test -t kb

      # 指定数据规模
      python -m src full-test -s small

      # 跳过本地适配器（只测云服务）
      python -m src full-test --skip-local

      # 测试后自动提交（不推送）
      python -m src full-test --commit

      # 测试后提交并推送到远程
      python -m src full-test --commit --push

      # 自定义提交信息
      python -m src full-test --commit --push -m "新增火山引擎和阿里云测试结果"
    """
    import subprocess
    import shutil

    config: Config = ctx.obj["config"]

    logger.info("=" * 80)
    logger.info("完整测试流程")
    logger.info("=" * 80)
    logger.info(f"步骤1: 运行{test_type}测试（规模：{scale}）")
    logger.info(f"步骤2: 生成测试报告")
    logger.info(f"步骤3: 同步报告到web目录")
    if commit:
        logger.info(f"步骤4: Git提交" + ("和推送" if push else "（不推送）"))
    logger.info("=" * 80)
    logger.info("")

    # ============================================================
    # 步骤1: 运行测试
    # ============================================================
    logger.info(">>> 步骤1: 运行测试 <<<")
    logger.info("")

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
            logger.info("开始知识库测试...")
            kb_adapters = get_adapter_list(config, "knowledge_base")

            for adapter in kb_adapters:
                try:
                    result = await runner.run_knowledge_base_benchmark(
                        adapter,
                        data_scale=scale,
                        run_quality_test=True,
                        skip_upload=True  # 已有文档，仅查询
                    )
                    results.append(result)
                    logger.info(f"  ✓ {adapter.name} 完成")
                except Exception as e:
                    logger.error(f"  ✗ {adapter.name} 失败: {e}")

        # 记忆系统测试
        if test_type in ["all", "memory"]:
            logger.info("开始记忆系统测试...")
            memory_adapters = get_adapter_list(config, "memory")

            # 根据参数过滤适配器
            if skip_local:
                memory_adapters = [a for a in memory_adapters if "Local" not in a.name]

            for adapter in memory_adapters:
                try:
                    result = await runner.run_memory_benchmark(
                        adapter,
                        data_scale=scale
                    )
                    results.append(result)
                    logger.info(f"  ✓ {adapter.name} 完成")
                except Exception as e:
                    logger.error(f"  ✗ {adapter.name} 失败: {e}")

        return results

    results = asyncio.run(run_tests())

    if not results:
        logger.error("测试失败，没有结果数据")
        return

    logger.info(f"✓ 测试完成，共 {len(results)} 个适配器")
    logger.info("")

    # ============================================================
    # 步骤2: 生成测试报告
    # ============================================================
    logger.info(">>> 步骤2: 生成测试报告 <<<")
    logger.info("")

    from .report import ReportGenerator

    test_config = {
        "mode": config.mode,
        "scale": scale,
        "test_type": test_type,
        "start_time": datetime.now().isoformat(),
    }

    generator = ReportGenerator()
    report_path = Path(report_dir)
    report_path.mkdir(parents=True, exist_ok=True)

    generated_files = generator.generate_report(
        results=[r.to_dict() for r in results],
        config=test_config,
        output_dir=report_dir,
        formats=["markdown", "html"]
    )

    logger.info("✓ 报告生成完成:")
    for fmt, path in generated_files.items():
        logger.info(f"  {fmt}: {path}")
    logger.info("")

    # ============================================================
    # 步骤3: 同步报告到web目录
    # ============================================================
    logger.info(">>> 步骤3: 同步报告到web目录 <<<")
    logger.info("")

    web_reports_dir = Path("web/reports")
    web_reports_dir.mkdir(parents=True, exist_ok=True)

    synced_files = []
    for fmt, src_path in generated_files.items():
        src = Path(src_path)
        if src.exists():
            dst = web_reports_dir / src.name
            shutil.copy2(src, dst)
            synced_files.append(dst)
            logger.info(f"  ✓ {src.name} → web/reports/")

    logger.info(f"✓ 同步完成，共 {len(synced_files)} 个文件")
    logger.info("")

    # ============================================================
    # 步骤4: Git提交和推送（可选）
    # ============================================================
    if not commit:
        logger.info("⊘ 跳过Git操作（使用 --commit 选项可自动提交）")
        logger.info("")
        logger.info("=" * 80)
        logger.info("✓ 完整测试流程完成！")
        logger.info("=" * 80)
        logger.info("")
        logger.info("提示: 如需提交更改，请手动执行:")
        logger.info("  git add docs/test-reports web/reports")
        logger.info("  git commit -m '更新测试报告'")
        logger.info("  git push")
        return

    logger.info(">>> 步骤4: Git提交和推送 <<<")
    logger.info("")

    try:
        # 检查git状态
        status_result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            check=True
        )

        if not status_result.stdout.strip():
            logger.info("⊘ 没有需要提交的更改")
        else:
            logger.info("检测到以下更改:")
            for line in status_result.stdout.strip().split('\n')[:10]:
                logger.info(f"  {line}")
            if len(status_result.stdout.strip().split('\n')) > 10:
                logger.info(f"  ... 还有更多文件")
            logger.info("")

            # 添加测试报告文件
            logger.info("添加文件到Git...")
            subprocess.run(["git", "add", report_dir], check=True)
            subprocess.run(["git", "add", "web/reports/"], check=True)
            logger.info("  ✓ 文件已添加")
            logger.info("")

            # 生成提交信息
            if not commit_message:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                test_type_name = {
                    "all": "完整系统",
                    "kb": "知识库",
                    "memory": "记忆系统"
                }.get(test_type, test_type)

                adapter_names = [r.adapter_name for r in results[:3]]
                adapter_summary = "、".join(adapter_names)
                if len(results) > 3:
                    adapter_summary += f"等{len(results)}个适配器"

                commit_message = f"""添加{test_type_name}测试报告 ({timestamp})

测试规模: {scale}
测试适配器: {adapter_summary}
测试结果: {len(results)}个适配器完成测试

- 生成Markdown和HTML报告
- 同步报告到web/reports目录

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"""

            # 提交
            logger.info("创建Git提交...")
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                check=True
            )
            logger.info("  ✓ 提交成功")
            logger.info("")

            # 推送
            if push:
                logger.info("推送到远程仓库...")
                subprocess.run(["git", "push"], check=True)
                logger.info("  ✓ 推送成功")
                logger.info("")
            else:
                logger.info("⊘ 未推送到远程（使用 --push 选项可自动推送）")
                logger.info("  手动推送: git push")
                logger.info("")

    except subprocess.CalledProcessError as e:
        logger.error(f"Git操作失败: {e}")
        logger.error("请手动检查并提交")
        logger.info("")
    except Exception as e:
        logger.error(f"发生错误: {e}")
        logger.info("")

    # ============================================================
    # 完成
    # ============================================================
    logger.info("=" * 80)
    logger.info("✓ 完整测试流程完成！")
    logger.info("=" * 80)
    logger.info("")
    logger.info("生成的报告:")
    for fmt, path in generated_files.items():
        logger.info(f"  - {path}")
    logger.info("")
    logger.info("Web报告目录:")
    logger.info(f"  - web/reports/ (已同步 {len(synced_files)} 个文件)")
    logger.info("")

    if commit and push:
        logger.info("✓ 更改已提交并推送到远程仓库")
        logger.info("  Railway等部署服务会自动检测并部署更新")
    elif commit:
        logger.info("✓ 更改已提交到本地仓库")
        logger.info("  使用 git push 推送到远程")


def main():
    """主入口"""
    cli(obj={})


if __name__ == "__main__":
    main()
