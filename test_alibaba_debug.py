# -*- coding: utf-8 -*-
"""调试阿里云API响应结构"""
import asyncio
from src.utils.config import load_config

async def test():
    config = load_config()

    try:
        from alibabacloud_bailian20231229.client import Client as BailianClient
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_bailian20231229 import models as bailian_20231229_models

        bailian_config = open_api_models.Config(
            access_key_id=config.aliyun.access_key_id.get_secret_value(),
            access_key_secret=config.aliyun.access_key_secret.get_secret_value(),
            endpoint=config.aliyun.endpoint
        )
        client = BailianClient(bailian_config)

        # 构建检索请求
        retrieve_request = bailian_20231229_models.RetrieveRequest(
            query="行程题",
            index_id=config.aliyun.index_id,
            dense_similarity_top_k=100,
            sparse_similarity_top_k=100,
            enable_reranking=True,
            rerank_top_n=5,
            rerank_min_score=0.01,
            enable_rewrite=False
        )

        # 调用 Retrieve API
        from alibabacloud_tea_util import models as util_models
        runtime = util_models.RuntimeOptions()

        response = client.retrieve_with_options(
            config.aliyun.workspace_id,
            retrieve_request,
            {},
            runtime
        )

        print("响应类型:", type(response))
        print("response.body类型:", type(response.body))
        print("response.body属性:", dir(response.body))
        print()

        data = getattr(response.body, 'data', None)
        print("data类型:", type(data))
        print("data值:", data)
        print()

        if hasattr(data, '__dict__'):
            print("data.__dict__:", data.__dict__)
        elif isinstance(data, dict):
            print("data是字典，keys:", data.keys())
            print("data内容:", data)

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
