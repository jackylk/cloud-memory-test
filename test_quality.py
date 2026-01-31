# -*- coding: utf-8 -*-
"""测试质量评估的文档ID匹配"""
import asyncio
from src.core.data_generator import TestDataGenerator
from src.adapters.knowledge_base.alibaba_bailian import AlibabaBailianAdapter
from src.utils.config import load_config

async def test():
    config = load_config()

    # 生成查询和ground truth
    gen = TestDataGenerator()
    queries_with_truth = gen.generate_queries_from_test_data(num_queries=5)

    print("=" * 60)
    print("查询和Ground Truth:")
    print("=" * 60)
    for i, (query, truth) in enumerate(queries_with_truth, 1):
        print(f"\n{i}. 查询: '{query}'")
        print(f"   Ground truth ({len(truth)} 个文档):")
        for doc in truth[:3]:
            print(f"     - {doc}")

    # 测试阿里云百炼
    print("\n" + "=" * 60)
    print("测试阿里云百炼返回的文档ID格式:")
    print("=" * 60)

    alibaba_config = {
        "access_key_id": config.aliyun.access_key_id.get_secret_value(),
        "access_key_secret": config.aliyun.access_key_secret.get_secret_value(),
        "workspace_id": config.aliyun.workspace_id,
        "index_id": config.aliyun.index_id,
        "endpoint": config.aliyun.endpoint,
        "enable_reranking": config.aliyun.enable_reranking,
        "rerank_top_n": config.aliyun.rerank_top_n,
    }

    adapter = AlibabaBailianAdapter(alibaba_config)
    await adapter.initialize()

    # 查询第一个
    query, truth = queries_with_truth[0]
    print(f"\n执行查询: '{query}'")
    result = await adapter.query(query, top_k=5)

    print(f"返回 {result.total_results} 个文档:\n")
    for i, doc in enumerate(result.documents, 1):
        print(f"{i}. ID: {doc.get('id')}")
        print(f"   Title: {doc.get('title')}")
        print(f"   Metadata: {doc.get('metadata', {})}")
        print(f"   Content preview: {doc.get('content', '')[:100]}...")
        print()

    await adapter.cleanup()

asyncio.run(test())
