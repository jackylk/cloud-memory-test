"""华为云 CSS 文档入库和查询测试脚本"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.adapters.base import Document
from src.adapters.knowledge_base.huawei_css import HuaweiCSSAdapter
from src.utils.config import load_config


async def extract_text_from_files(test_data_dir: Path, max_files: int = 10) -> List[Document]:
    """从 test-data 目录提取文本内容

    注意：简化版本，直接将文件名作为标题，内容使用占位符
    实际生产环境需要使用 python-docx, PyPDF2 等库提取真实内容
    """
    documents = []
    files = list(test_data_dir.glob("*.doc")) + list(test_data_dir.glob("*.docx")) + list(test_data_dir.glob("*.pdf"))
    files = files[:max_files]

    logger.info(f"找到 {len(files)} 个文档文件")

    for idx, file_path in enumerate(files):
        # 简化处理：使用文件名作为内容
        # 实际应该用 python-docx 或 PyPDF2 提取真实内容
        title = file_path.stem
        content = f"这是来自文件 {file_path.name} 的内容。"
        content += f"文件主题：{title}。"
        content += "这是一份小学数学试题和学习资料。" if "数学" in title or "试题" in title or "试卷" in title else "这是一份教育学习资料。"

        doc = Document(
            id=f"doc_{idx:03d}",
            content=content,
            title=title,
            metadata={
                "source": "test-data",
                "filename": file_path.name,
                "file_type": file_path.suffix
            }
        )
        documents.append(doc)
        logger.debug(f"  [{idx+1}/{len(files)}] {file_path.name} -> {len(content)} chars")

    return documents


async def main():
    """主测试流程"""
    logger.info("=" * 60)
    logger.info("华为云 CSS 文档入库和查询测试")
    logger.info("=" * 60)

    # 1. 加载配置
    config = load_config()
    huawei_config = {
        "ak": config.huawei.ak,
        "sk": config.huawei.sk,
        "region": config.huawei.region,
        "cluster_id": config.huawei.cluster_id,
        "endpoint": config.huawei.endpoint,
        "index_name": config.huawei.index_name,
        "es_username": config.huawei.es_username,
        "es_password": config.huawei.es_password,
    }

    logger.info(f"华为云 CSS 配置:")
    logger.info(f"  Region: {huawei_config['region']}")
    logger.info(f"  Cluster ID: {huawei_config['cluster_id']}")
    logger.info(f"  Endpoint: {huawei_config['endpoint']}")
    logger.info(f"  Index: {huawei_config['index_name']}")
    logger.info("")

    # 2. 初始化适配器
    adapter = HuaweiCSSAdapter(huawei_config)
    await adapter.initialize()

    logger.info(f"适配器模式: {'Mock' if adapter.mock_mode else 'Real (真实连接)'}")
    logger.info("")

    # 3. 提取文档
    test_data_dir = project_root / "test-data"
    if not test_data_dir.exists():
        logger.error(f"测试数据目录不存在: {test_data_dir}")
        return

    logger.info(f"从 {test_data_dir} 提取文档...")
    documents = await extract_text_from_files(test_data_dir, max_files=10)
    logger.info(f"成功提取 {len(documents)} 个文档")
    logger.info("")

    # 4. 上传文档
    logger.info("开始上传文档到华为云 CSS...")
    upload_result = await adapter.upload_documents(documents)
    logger.info(f"上传结果:")
    logger.info(f"  成功: {upload_result.success_count}")
    logger.info(f"  失败: {upload_result.failed_count}")
    logger.info(f"  耗时: {upload_result.total_time_ms:.2f}ms")
    logger.info("")

    # 5. 构建索引
    logger.info("构建索引...")
    index_result = await adapter.build_index()
    logger.info(f"索引结果:")
    logger.info(f"  成功: {index_result.success}")
    logger.info(f"  文档数: {index_result.doc_count}")
    logger.info(f"  耗时: {index_result.index_time_ms:.2f}ms")
    logger.info("")

    # 6. 执行查询测试
    test_queries = [
        "小升初数学试题",
        "2011年数学试卷",
        "迎春杯竞赛",
        "数学解题",
        "整除问题"
    ]

    logger.info("开始查询测试...")
    logger.info("=" * 60)

    for idx, query in enumerate(test_queries, 1):
        logger.info(f"查询 {idx}/{len(test_queries)}: {query}")
        result = await adapter.query(query, top_k=3)

        logger.info(f"  结果数: {result.total_results}")
        logger.info(f"  延迟: {result.latency_ms:.2f}ms")

        if result.documents:
            logger.info(f"  Top 3 结果:")
            for i, (doc, score) in enumerate(zip(result.documents, result.scores), 1):
                logger.info(f"    {i}. [{score:.4f}] {doc.get('title', 'N/A')}")
                logger.info(f"       内容: {doc.get('content', '')[:60]}...")
        else:
            logger.warning(f"  没有找到结果")

        logger.info("")

    # 7. 获取统计信息
    stats = await adapter.get_stats()
    logger.info("=" * 60)
    logger.info("CSS 统计信息:")
    for key, value in stats.items():
        logger.info(f"  {key}: {value}")

    # 8. 清理
    await adapter.cleanup()
    logger.info("")
    logger.info("测试完成！")


if __name__ == "__main__":
    asyncio.run(main())
