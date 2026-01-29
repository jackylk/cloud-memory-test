"""ChromaDB 本地适配器 - 用于本地调试"""

import time
from typing import List, Optional, Dict, Any
from loguru import logger

from ..base import (
    KnowledgeBaseAdapter,
    Document,
    QueryResult,
    UploadResult,
    IndexResult,
)


class ChromaDBAdapter(KnowledgeBaseAdapter):
    """ChromaDB 本地向量数据库适配器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.persist_directory = config.get("persist_directory")
        self.embedding_model = config.get("embedding_model", "all-MiniLM-L6-v2")
        self.collection_name = config.get("collection_name", "test_collection")

        self._client = None
        self._collection = None
        self._embedding_function = None

    async def initialize(self) -> None:
        """初始化 ChromaDB 连接"""
        logger.debug(f"初始化 ChromaDB 适配器")
        logger.debug(f"  → 持久化目录: {self.persist_directory or '内存模式'}")
        logger.debug(f"  → Embedding 模型: {self.embedding_model}")
        logger.debug(f"  → Collection: {self.collection_name}")

        try:
            import chromadb
            from chromadb.utils import embedding_functions

            # 创建 embedding function
            self._embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            )

            # 创建客户端
            if self.persist_directory:
                self._client = chromadb.PersistentClient(path=self.persist_directory)
                logger.debug(f"  → 使用持久化存储: {self.persist_directory}")
            else:
                self._client = chromadb.Client()
                logger.debug("  → 使用内存存储")

            # 获取或创建 collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self._embedding_function,
                metadata={"hnsw:space": "cosine"}
            )

            self._initialized = True
            logger.debug("  → ChromaDB 初始化完成")

        except ImportError as e:
            raise ImportError(
                "请安装 chromadb 和 sentence-transformers: "
                "pip install chromadb sentence-transformers"
            ) from e
        except Exception as e:
            logger.error(f"ChromaDB 初始化失败: {e}")
            raise

    async def upload_documents(self, documents: List[Document]) -> UploadResult:
        """上传文档到 ChromaDB"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化，请先调用 initialize()")

        start_time = time.time()
        success_count = 0
        failed_count = 0
        failed_ids = []

        logger.debug(f"开始上传 {len(documents)} 个文档")

        for i, doc in enumerate(documents):
            try:
                # 准备数据
                metadata = {
                    "title": doc.title or doc.id,
                    "format": doc.format.value,
                    **doc.metadata
                }

                # 添加到 collection
                self._collection.add(
                    ids=[doc.id],
                    documents=[doc.content],
                    metadatas=[metadata]
                )

                success_count += 1
                logger.debug(f"  → 文档 {i + 1}/{len(documents)}: {doc.id} (成功)")

            except Exception as e:
                failed_count += 1
                failed_ids.append(doc.id)
                logger.warning(f"  → 文档 {i + 1}/{len(documents)}: {doc.id} (失败: {e})")

        elapsed_ms = (time.time() - start_time) * 1000

        result = UploadResult(
            success_count=success_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            total_time_ms=elapsed_ms,
            details={
                "avg_time_per_doc_ms": elapsed_ms / len(documents) if documents else 0
            }
        )

        logger.debug(f"上传完成: 成功 {success_count}, 失败 {failed_count}, 耗时 {elapsed_ms:.2f}ms")
        return result

    async def build_index(self) -> IndexResult:
        """构建索引 - ChromaDB 自动构建，此处仅返回状态"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        # ChromaDB 在添加文档时自动构建索引
        # 这里我们只获取当前状态
        count = self._collection.count()
        elapsed_ms = (time.time() - start_time) * 1000

        logger.debug(f"索引状态: {count} 个文档已索引")

        return IndexResult(
            success=True,
            index_time_ms=elapsed_ms,
            doc_count=count,
            details={"auto_indexed": True}
        )

    async def query(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> QueryResult:
        """执行检索查询"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        logger.debug(f"执行查询: '{query[:50]}...' (top_k={top_k})")

        try:
            # 构建查询参数
            query_params = {
                "query_texts": [query],
                "n_results": top_k,
            }

            if filters:
                query_params["where"] = filters

            # 执行查询
            results = self._collection.query(**query_params)

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果
            documents = []
            scores = []

            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    doc_data = {
                        "id": doc_id,
                        "content": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    }
                    documents.append(doc_data)

                    # ChromaDB 返回的是距离，转换为相似度分数
                    if results["distances"] and results["distances"][0]:
                        distance = results["distances"][0][i]
                        # cosine distance to similarity
                        score = 1 - distance
                        scores.append(score)
                    else:
                        scores.append(0.0)

            logger.debug(f"查询完成: 返回 {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

            return QueryResult(
                documents=documents,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(documents),
                query=query
            )

        except Exception as e:
            logger.error(f"查询失败: {e}")
            raise

    async def delete_documents(self, doc_ids: List[str]) -> Dict[str, Any]:
        """删除文档"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        logger.debug(f"删除 {len(doc_ids)} 个文档")

        try:
            self._collection.delete(ids=doc_ids)
            return {
                "success": True,
                "deleted_count": len(doc_ids),
                "deleted_ids": doc_ids
            }
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            return {"initialized": False}

        count = self._collection.count()

        return {
            "initialized": True,
            "collection_name": self.collection_name,
            "document_count": count,
            "embedding_model": self.embedding_model,
            "storage_mode": "persistent" if self.persist_directory else "in-memory"
        }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._collection:
            # 删除 collection
            try:
                self._client.delete_collection(self.collection_name)
                logger.debug(f"已删除 collection: {self.collection_name}")
            except Exception as e:
                logger.warning(f"删除 collection 失败: {e}")

        self._collection = None
        self._client = None
        self._initialized = False
        logger.debug("ChromaDB 适配器已清理")
