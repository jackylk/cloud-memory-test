"""Milvus 本地适配器 - 使用 Milvus Lite 进行本地测试"""

import time
import hashlib
from typing import List, Optional, Dict, Any
from loguru import logger

from ..base import (
    KnowledgeBaseAdapter,
    Document,
    QueryResult,
    UploadResult,
    IndexResult,
)


class MilvusAdapter(KnowledgeBaseAdapter):
    """Milvus 向量数据库适配器

    使用 Milvus Lite 进行本地测试，无需启动服务器。
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "MilvusAdapter"

        # 配置
        self.collection_name = config.get("collection_name", "benchmark_kb")
        self.dimension = config.get("dimension", 384)  # 向量维度
        self.db_path = config.get("db_path", "./milvus_data.db")  # Milvus Lite 数据文件

        self._client = None
        self._use_lite = config.get("use_lite", True)

    async def initialize(self) -> None:
        """初始化 Milvus 连接"""
        logger.debug("初始化 Milvus 适配器")
        logger.debug(f"  → Collection: {self.collection_name}")
        logger.debug(f"  → 向量维度: {self.dimension}")
        logger.debug(f"  → Lite 模式: {self._use_lite}")

        try:
            from pymilvus import MilvusClient

            if self._use_lite:
                # Milvus Lite - 本地文件模式
                self._client = MilvusClient(self.db_path)
                logger.debug(f"  → 使用 Milvus Lite: {self.db_path}")
            else:
                # 连接远程 Milvus 服务
                uri = self.config.get("uri", "http://localhost:19530")
                self._client = MilvusClient(uri=uri)
                logger.debug(f"  → 连接 Milvus: {uri}")

            # 检查并创建 collection
            if self._client.has_collection(self.collection_name):
                self._client.drop_collection(self.collection_name)
                logger.debug(f"  → 删除旧 collection: {self.collection_name}")

            self._initialized = True
            logger.debug("  → Milvus 初始化完成")

        except ImportError as e:
            raise ImportError("请安装 pymilvus: pip install pymilvus") from e
        except Exception as e:
            logger.error(f"Milvus 初始化失败: {e}")
            raise

    def _text_to_vector(self, text: str) -> List[float]:
        """简单的文本转向量（用于测试）

        实际使用时应该用真正的 embedding 模型
        """
        # 使用哈希生成伪向量
        hash_bytes = hashlib.sha384(text.encode()).digest()
        # 转换为浮点数向量
        vector = []
        for i in range(0, len(hash_bytes), 2):
            val = int.from_bytes(hash_bytes[i:i+2], 'big')
            # 归一化到 [-1, 1]
            vector.append((val / 32768.0) - 1.0)

        # 确保维度正确
        while len(vector) < self.dimension:
            vector.extend(vector[:self.dimension - len(vector)])
        return vector[:self.dimension]

    async def upload_documents(self, documents: List[Document]) -> UploadResult:
        """上传文档到 Milvus"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        success_count = 0
        failed_count = 0
        failed_ids = []

        logger.debug(f"开始上传 {len(documents)} 个文档")

        try:
            # 准备数据
            data = []
            for doc in documents:
                vector = self._text_to_vector(doc.content)
                data.append({
                    "id": hash(doc.id) % (2**63),  # Milvus 需要整数 ID
                    "doc_id": doc.id,
                    "content": doc.content,
                    "title": doc.title or doc.id,
                    "vector": vector
                })
                success_count += 1
                logger.debug(f"  → 准备文档: {doc.id}")

            # 创建 collection 并插入数据
            self._client.create_collection(
                collection_name=self.collection_name,
                dimension=self.dimension,
                auto_id=False
            )

            self._client.insert(
                collection_name=self.collection_name,
                data=data
            )

            logger.debug(f"  → 插入 {len(data)} 条数据")

        except Exception as e:
            logger.error(f"上传失败: {e}")
            failed_count = len(documents)
            failed_ids = [doc.id for doc in documents]
            success_count = 0

        elapsed_ms = (time.time() - start_time) * 1000

        return UploadResult(
            success_count=success_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            total_time_ms=elapsed_ms
        )

    async def build_index(self) -> IndexResult:
        """构建索引 - Milvus 自动管理索引"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        # Milvus Lite 自动创建索引
        # 对于完整 Milvus，可以在这里创建自定义索引
        elapsed_ms = (time.time() - start_time) * 1000

        # 获取文档数量
        stats = self._client.get_collection_stats(self.collection_name)
        doc_count = stats.get("row_count", 0)

        logger.debug(f"索引状态: {doc_count} 个文档")

        return IndexResult(
            success=True,
            index_time_ms=elapsed_ms,
            doc_count=doc_count
        )

    async def query(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> QueryResult:
        """执行向量检索"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        logger.debug(f"执行查询: '{query[:50]}...'")

        try:
            # 转换查询为向量
            query_vector = self._text_to_vector(query)

            # 执行搜索
            results = self._client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                limit=top_k,
                output_fields=["doc_id", "content", "title"]
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果
            documents = []
            scores = []

            if results and len(results) > 0:
                for hit in results[0]:
                    doc_data = {
                        "id": hit.get("entity", {}).get("doc_id", ""),
                        "content": hit.get("entity", {}).get("content", ""),
                        "title": hit.get("entity", {}).get("title", ""),
                    }
                    documents.append(doc_data)
                    # Milvus 返回距离，转换为相似度
                    distance = hit.get("distance", 0)
                    score = 1 / (1 + distance)  # 转换为相似度分数
                    scores.append(score)

            logger.debug(f"查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

            return QueryResult(
                documents=documents,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(documents),
                query=query
            )

        except Exception as e:
            logger.error(f"查询失败: {e}")
            elapsed_ms = (time.time() - start_time) * 1000
            return QueryResult(
                documents=[],
                scores=[],
                latency_ms=elapsed_ms,
                total_results=0,
                query=query
            )

    async def delete_documents(self, doc_ids: List[str]) -> Dict[str, Any]:
        """删除文档"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        try:
            # 转换 doc_id 为整数 ID
            int_ids = [hash(doc_id) % (2**63) for doc_id in doc_ids]
            self._client.delete(
                collection_name=self.collection_name,
                ids=int_ids
            )
            return {"success": True, "deleted_count": len(doc_ids)}
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            return {"initialized": False}

        try:
            stats = self._client.get_collection_stats(self.collection_name)
            return {
                "initialized": True,
                "collection_name": self.collection_name,
                "document_count": stats.get("row_count", 0),
                "dimension": self.dimension,
                "mode": "lite" if self._use_lite else "server"
            }
        except Exception:
            return {
                "initialized": True,
                "collection_name": self.collection_name,
                "document_count": 0,
                "dimension": self.dimension
            }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._client:
            try:
                if self._client.has_collection(self.collection_name):
                    self._client.drop_collection(self.collection_name)
                self._client.close()
            except Exception as e:
                logger.warning(f"清理时发生错误: {e}")

        self._client = None
        self._initialized = False
        logger.debug("Milvus 适配器已清理")
