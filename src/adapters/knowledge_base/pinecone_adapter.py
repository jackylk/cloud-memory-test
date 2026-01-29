"""Pinecone 适配器 - 云端向量数据库"""

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


class PineconeAdapter(KnowledgeBaseAdapter):
    """Pinecone 向量数据库适配器

    Pinecone 是云服务，需要 API Key。
    支持 Serverless 和 Pod-based 部署。
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "PineconeAdapter"

        # 配置
        self.api_key = config.get("api_key")
        self.index_name = config.get("index_name", "benchmark-kb")
        self.namespace = config.get("namespace", "default")
        self.dimension = config.get("dimension", 384)
        self.metric = config.get("metric", "cosine")

        # Serverless 配置
        self.cloud = config.get("cloud", "aws")
        self.region = config.get("region", "us-east-1")

        self._index = None
        self._pc = None

        # 如果没有 API key，使用模拟模式
        self._mock_mode = config.get("mock_mode", not self.api_key)
        self._mock_data: Dict[str, Dict] = {}

    async def initialize(self) -> None:
        """初始化 Pinecone 连接"""
        logger.debug("初始化 Pinecone 适配器")
        logger.debug(f"  → Index: {self.index_name}")
        logger.debug(f"  → Namespace: {self.namespace}")
        logger.debug(f"  → 向量维度: {self.dimension}")

        if self._mock_mode:
            logger.debug("  → 使用模拟模式（无 API Key）")
            self._mock_data = {}
            self._initialized = True
            return

        try:
            from pinecone import Pinecone, ServerlessSpec

            # 初始化客户端
            self._pc = Pinecone(api_key=self.api_key)
            logger.debug("  → Pinecone 客户端已创建")

            # 检查索引是否存在
            existing_indexes = [idx.name for idx in self._pc.list_indexes()]

            if self.index_name in existing_indexes:
                logger.debug(f"  → 使用现有索引: {self.index_name}")
            else:
                # 创建 Serverless 索引
                logger.debug(f"  → 创建新索引: {self.index_name}")
                self._pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                    spec=ServerlessSpec(
                        cloud=self.cloud,
                        region=self.region
                    )
                )
                # 等待索引就绪
                import time as time_module
                while not self._pc.describe_index(self.index_name).status.ready:
                    time_module.sleep(1)

            # 获取索引引用
            self._index = self._pc.Index(self.index_name)
            self._initialized = True
            logger.debug("  → Pinecone 初始化完成")

        except ImportError as e:
            raise ImportError("请安装 pinecone-client: pip install pinecone-client") from e
        except Exception as e:
            logger.error(f"Pinecone 初始化失败: {e}")
            raise

    def _text_to_vector(self, text: str) -> List[float]:
        """简单的文本转向量（用于测试）"""
        hash_bytes = hashlib.sha384(text.encode()).digest()
        vector = []
        for i in range(0, len(hash_bytes), 2):
            val = int.from_bytes(hash_bytes[i:i+2], 'big')
            vector.append((val / 32768.0) - 1.0)
        while len(vector) < self.dimension:
            vector.extend(vector[:self.dimension - len(vector)])
        return vector[:self.dimension]

    async def upload_documents(self, documents: List[Document]) -> UploadResult:
        """上传文档"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        success_count = 0
        failed_count = 0
        failed_ids = []

        logger.debug(f"开始上传 {len(documents)} 个文档")

        try:
            if self._mock_mode:
                # 模拟模式
                for doc in documents:
                    vector = self._text_to_vector(doc.content)
                    self._mock_data[doc.id] = {
                        "id": doc.id,
                        "values": vector,
                        "metadata": {
                            "content": doc.content,
                            "title": doc.title or doc.id
                        }
                    }
                    success_count += 1
                    logger.debug(f"  → 文档 {doc.id} (模拟模式)")
            else:
                # 准备向量数据
                vectors = []
                for doc in documents:
                    vector = self._text_to_vector(doc.content)
                    vectors.append({
                        "id": doc.id,
                        "values": vector,
                        "metadata": {
                            "content": doc.content,
                            "title": doc.title or doc.id
                        }
                    })

                # 批量上传
                batch_size = 100
                for i in range(0, len(vectors), batch_size):
                    batch = vectors[i:i + batch_size]
                    self._index.upsert(
                        vectors=batch,
                        namespace=self.namespace
                    )
                    success_count += len(batch)
                    logger.debug(f"  → 上传批次 {i//batch_size + 1}")

        except Exception as e:
            logger.error(f"上传失败: {e}")
            failed_count = len(documents) - success_count
            failed_ids = [doc.id for doc in documents[success_count:]]

        elapsed_ms = (time.time() - start_time) * 1000

        return UploadResult(
            success_count=success_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            total_time_ms=elapsed_ms
        )

    async def build_index(self) -> IndexResult:
        """Pinecone 自动管理索引"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        if self._mock_mode:
            doc_count = len(self._mock_data)
        else:
            # 获取索引统计
            stats = self._index.describe_index_stats()
            doc_count = stats.total_vector_count

        elapsed_ms = (time.time() - start_time) * 1000

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
            query_vector = self._text_to_vector(query)

            if self._mock_mode:
                # 模拟模式 - 计算余弦相似度
                import math

                def cosine_similarity(v1, v2):
                    dot = sum(a * b for a, b in zip(v1, v2))
                    norm1 = math.sqrt(sum(a * a for a in v1))
                    norm2 = math.sqrt(sum(b * b for b in v2))
                    return dot / (norm1 * norm2) if norm1 * norm2 > 0 else 0

                similarities = []
                for doc_id, doc_data in self._mock_data.items():
                    score = cosine_similarity(query_vector, doc_data["values"])
                    similarities.append((doc_id, doc_data, score))

                # 排序
                similarities.sort(key=lambda x: x[2], reverse=True)
                top_results = similarities[:top_k]

                documents = []
                scores = []
                for doc_id, doc_data, score in top_results:
                    documents.append({
                        "id": doc_id,
                        "content": doc_data["metadata"].get("content", ""),
                        "title": doc_data["metadata"].get("title", "")
                    })
                    scores.append(score)

            else:
                # 真实 Pinecone 查询
                results = self._index.query(
                    vector=query_vector,
                    top_k=top_k,
                    namespace=self.namespace,
                    include_metadata=True
                )

                documents = []
                scores = []
                for match in results.matches:
                    documents.append({
                        "id": match.id,
                        "content": match.metadata.get("content", ""),
                        "title": match.metadata.get("title", "")
                    })
                    scores.append(match.score)

            elapsed_ms = (time.time() - start_time) * 1000
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
            if self._mock_mode:
                for doc_id in doc_ids:
                    self._mock_data.pop(doc_id, None)
            else:
                self._index.delete(ids=doc_ids, namespace=self.namespace)

            return {"success": True, "deleted_count": len(doc_ids)}
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            return {"initialized": False}

        if self._mock_mode:
            return {
                "initialized": True,
                "mode": "mock",
                "index_name": self.index_name,
                "document_count": len(self._mock_data),
                "dimension": self.dimension
            }

        try:
            stats = self._index.describe_index_stats()
            return {
                "initialized": True,
                "mode": "cloud",
                "index_name": self.index_name,
                "namespace": self.namespace,
                "document_count": stats.total_vector_count,
                "dimension": self.dimension
            }
        except Exception:
            return {"initialized": True, "mode": "cloud"}

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mock_mode:
            self._mock_data.clear()
        else:
            if self._index:
                try:
                    # 清空 namespace
                    self._index.delete(delete_all=True, namespace=self.namespace)
                except Exception as e:
                    logger.warning(f"清理时发生错误: {e}")

        self._index = None
        self._pc = None
        self._initialized = False
        logger.debug("Pinecone 适配器已清理")
