"""火山引擎 VikingDB 知识库适配器

支持两种模式:
1. Mock 模式: 使用本地 TF-IDF 向量存储模拟 VikingDB 行为（无需凭证）
2. 真实模式: 连接火山引擎 VikingDB 进行检索

使用方式:
- 如果配置中没有 collection_name，自动启用 mock 模式
- 配置 access_key/secret_key/collection_name 后切换到真实服务

SDK: pip install volcengine
"""

import time
import re
import math
from typing import List, Optional, Dict, Any
from collections import Counter
from loguru import logger

from ..base import (
    KnowledgeBaseAdapter,
    Document,
    QueryResult,
    UploadResult,
    IndexResult,
)


class VolcengineVikingDBAdapter(KnowledgeBaseAdapter):
    """火山引擎 VikingDB 知识库适配器

    特点:
    - 支持 mock 模式用于无凭证测试
    - 真实模式使用 volcengine SDK 调用 VikingDB API
    - 支持混合搜索和重排序
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "VolcengineVikingDB"

        # 火山引擎配置
        self._access_key = config.get("access_key")
        self._secret_key = config.get("secret_key")
        self._collection_name = config.get("collection_name")
        self._host = config.get("host", "api-knowledgebase.mlp.cn-beijing.volces.com")
        self._region = config.get("region", "cn-beijing")

        # 搜索配置
        self._dense_weight = config.get("dense_weight", 0.5)
        self._rerank_switch = config.get("rerank_switch", True)
        self._rerank_model = config.get("rerank_model", "m3-v2-rerank")

        # 如果没有 collection_name 或凭证，启用 mock 模式
        self._mock_mode = not (self._collection_name and self._access_key and self._secret_key)

        # SDK 客户端（真实模式）
        self._service = None

        # Mock 模式存储
        self._documents: Dict[str, Document] = {}
        self._idf: Dict[str, float] = {}
        self._doc_vectors: Dict[str, Dict[str, float]] = {}

    @property
    def mock_mode(self) -> bool:
        """是否处于 mock 模式"""
        return self._mock_mode

    async def initialize(self) -> None:
        """初始化连接和认证"""
        if self._mock_mode:
            logger.info("VolcengineVikingDB: 初始化 Mock 模式")
            logger.debug("  → 使用本地 TF-IDF 向量存储模拟")
            if not self._collection_name:
                logger.debug("  → 未配置 collection_name")
            if not self._access_key or not self._secret_key:
                logger.debug("  → 未配置 access_key/secret_key")
        else:
            logger.info(f"VolcengineVikingDB: 初始化真实模式")
            logger.debug(f"  → Host: {self._host}")
            logger.debug(f"  → Collection: {self._collection_name}")

            try:
                from volcengine.viking_knowledgebase import VikingKnowledgeBaseService

                self._service = VikingKnowledgeBaseService(
                    host=self._host,
                    scheme="https",
                    connection_timeout=30,
                    socket_timeout=30
                )
                self._service.set_ak(self._access_key)
                self._service.set_sk(self._secret_key)

                logger.debug("  → VikingDB 客户端创建成功")

            except ImportError:
                logger.error("volcengine SDK 未安装，请运行: pip install volcengine")
                raise RuntimeError("volcengine is required for VikingDB adapter")
            except Exception as e:
                logger.error(f"初始化 VikingDB 客户端失败: {e}")
                raise

        self._initialized = True
        logger.debug("  → 初始化完成")

    # ========== Mock 模式辅助方法 ==========

    def _tokenize(self, text: str) -> List[str]:
        """简单分词 - 支持中英文"""
        text = text.lower()
        tokens = []

        # 英文单词
        english_words = re.findall(r'[a-zA-Z]+', text)
        tokens.extend(english_words)

        # 中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)

        # 中文词组
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i + 1])

        return tokens

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """计算词频"""
        counter = Counter(tokens)
        total = len(tokens)
        if total == 0:
            return {}
        return {word: count / total for word, count in counter.items()}

    def _compute_idf(self) -> None:
        """计算逆文档频率"""
        n_docs = len(self._documents)
        if n_docs == 0:
            return

        doc_freq = Counter()
        for doc in self._documents.values():
            tokens = set(self._tokenize(doc.content))
            for token in tokens:
                doc_freq[token] += 1

        self._idf = {}
        for word, freq in doc_freq.items():
            self._idf[word] = math.log(n_docs / (1 + freq))

    def _compute_tfidf(self, tokens: List[str]) -> Dict[str, float]:
        """计算 TF-IDF 向量"""
        tf = self._compute_tf(tokens)
        tfidf = {}
        for word, tf_val in tf.items():
            idf_val = self._idf.get(word, 0)
            tfidf[word] = tf_val * idf_val
        return tfidf

    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """计算余弦相似度"""
        all_words = set(vec1.keys()) | set(vec2.keys())

        dot_product = 0
        norm1 = 0
        norm2 = 0

        for word in all_words:
            v1 = vec1.get(word, 0)
            v2 = vec2.get(word, 0)
            dot_product += v1 * v2
            norm1 += v1 * v1
            norm2 += v2 * v2

        if norm1 == 0 or norm2 == 0:
            return 0

        return dot_product / (math.sqrt(norm1) * math.sqrt(norm2))

    # ========== 适配器接口实现 ==========

    async def upload_documents(self, documents: List[Document]) -> UploadResult:
        """上传文档

        Mock 模式: 存储到本地字典
        真实模式: VikingDB 支持从 URL 或 TOS 上传
        """
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        if self._mock_mode:
            # Mock 模式：存储到本地
            success_count = 0
            failed_count = 0
            failed_ids = []

            logger.debug(f"[Mock] 上传 {len(documents)} 个文档")

            for doc in documents:
                try:
                    self._documents[doc.id] = doc
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    failed_ids.append(doc.id)
                    logger.warning(f"文档 {doc.id} 上传失败: {e}")

            elapsed_ms = (time.time() - start_time) * 1000

            return UploadResult(
                success_count=success_count,
                failed_count=failed_count,
                failed_ids=failed_ids,
                total_time_ms=elapsed_ms,
                details={"mode": "mock"}
            )
        else:
            # 真实模式：Viking知识库需要通过控制台或API上传文档
            elapsed_ms = (time.time() - start_time) * 1000

            logger.warning(
                "Viking知识库需要通过控制台、URL或TOS上传文档。\n"
                "  建议:\n"
                "  1. 在火山引擎控制台手动上传测试文档\n"
                "  2. 或使用 collection.add_doc(add_type='url', url='...') 方法\n"
                "  3. 或切换到Mock模式进行功能测试"
            )

            return UploadResult(
                success_count=0,
                failed_count=len(documents),
                failed_ids=[doc.id for doc in documents],
                total_time_ms=elapsed_ms,
                details={
                    "mode": "real",
                    "note": "Viking Knowledge Base requires console/URL/TOS upload",
                    "collection_name": self._collection_name,
                    "suggestion": "Upload documents via console for testing"
                }
            )

    async def build_index(self) -> IndexResult:
        """构建/更新索引

        Mock 模式: 计算本地 TF-IDF 索引
        真实模式: VikingDB 自动管理索引
        """
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        if self._mock_mode:
            logger.debug(f"[Mock] 构建索引，文档数: {len(self._documents)}")

            # 计算 IDF
            self._compute_idf()

            # 计算每个文档的 TF-IDF 向量
            self._doc_vectors = {}
            for doc_id, doc in self._documents.items():
                tokens = self._tokenize(doc.content)
                self._doc_vectors[doc_id] = self._compute_tfidf(tokens)

            elapsed_ms = (time.time() - start_time) * 1000

            return IndexResult(
                success=True,
                index_time_ms=elapsed_ms,
                doc_count=len(self._documents),
                details={
                    "mode": "mock",
                    "vocabulary_size": len(self._idf)
                }
            )
        else:
            # 真实模式：VikingDB 自动管理索引
            elapsed_ms = (time.time() - start_time) * 1000

            return IndexResult(
                success=True,
                index_time_ms=elapsed_ms,
                doc_count=0,
                details={
                    "mode": "real",
                    "note": "VikingDB manages indexing automatically",
                    "collection_name": self._collection_name
                }
            )

    async def query(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> QueryResult:
        """执行检索查询

        Mock 模式: 使用本地 TF-IDF 相似度搜索
        真实模式: 调用 VikingDB search_collection()
        """
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        if self._mock_mode:
            return await self._query_mock(query, top_k, start_time)
        else:
            return await self._query_real(query, top_k, filters, start_time)

    async def _query_mock(
        self,
        query: str,
        top_k: int,
        start_time: float
    ) -> QueryResult:
        """Mock 模式查询"""
        logger.debug(f"[Mock] 执行查询: '{query[:50]}...'")

        # 计算查询的 TF-IDF 向量
        query_tokens = self._tokenize(query)
        query_vector = self._compute_tfidf(query_tokens)

        # 计算与所有文档的相似度
        similarities = []
        for doc_id, doc_vector in self._doc_vectors.items():
            sim = self._cosine_similarity(query_vector, doc_vector)
            similarities.append((doc_id, sim))

        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        # 取 top_k
        top_results = similarities[:top_k]

        elapsed_ms = (time.time() - start_time) * 1000

        # 构建结果
        documents = []
        scores = []
        for doc_id, score in top_results:
            doc = self._documents[doc_id]
            documents.append({
                "id": doc_id,
                "content": doc.content,
                "metadata": doc.metadata,
                "title": doc.title
            })
            scores.append(score)

        logger.debug(f"[Mock] 查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

        return QueryResult(
            documents=documents,
            scores=scores,
            latency_ms=elapsed_ms,
            total_results=len(documents),
            query=query
        )

    async def _query_real(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict],
        start_time: float
    ) -> QueryResult:
        """真实模式查询 - 调用 VikingDB API"""
        logger.debug(f"执行 VikingDB 查询: '{query[:50]}...'")

        try:
            # 直接调用 search_knowledge API (知识库标准版)
            search_params = {
                "collection_name": self._collection_name,
                "query": query,
                "limit": top_k,
                "dense_weight": self._dense_weight
            }

            # 添加过滤器
            if filters:
                search_params["doc_filter"] = filters

            search_result = self._service.search_knowledge(**search_params)

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果
            documents = []
            scores = []

            # search_knowledge 返回格式: {'result_list': [], 'rewrite_query': str}
            result_list = search_result.get('result_list', []) if isinstance(search_result, dict) else []

            if result_list:
                for item in result_list:
                    # 每个结果包含 content, score, doc_name, chunk_id 等字段
                    documents.append({
                        "id": item.get("chunk_id", item.get("id", f"doc_{len(documents)}")),
                        "content": item.get("content", ""),
                        "metadata": {
                            "doc_name": item.get("doc_name", ""),
                            "chunk_id": item.get("chunk_id"),
                        },
                        "title": item.get("doc_name", item.get("title"))
                    })
                    scores.append(item.get("score", 0.0))

            logger.debug(f"VikingDB 查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

            return QueryResult(
                documents=documents,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(documents),
                query=query
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"VikingDB 查询失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")

            return QueryResult(
                documents=[],
                scores=[],
                latency_ms=elapsed_ms,
                total_results=0,
                query=query
            )

    async def delete_documents(self, doc_ids: List[str]) -> Dict[str, Any]:
        """删除文档

        Mock 模式: 从本地存储删除
        真实模式: 调用 VikingDB 删除 API
        """
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        if self._mock_mode:
            deleted = 0
            for doc_id in doc_ids:
                if doc_id in self._documents:
                    del self._documents[doc_id]
                    if doc_id in self._doc_vectors:
                        del self._doc_vectors[doc_id]
                    deleted += 1

            return {
                "success": True,
                "deleted_count": deleted,
                "deleted_ids": doc_ids,
                "mode": "mock"
            }
        else:
            try:
                collection = self._service.get_collection(
                    collection_name=self._collection_name
                )
                for doc_id in doc_ids:
                    collection.delete_doc(doc_id=doc_id)

                return {
                    "success": True,
                    "deleted_count": len(doc_ids),
                    "deleted_ids": doc_ids,
                    "mode": "real"
                }
            except Exception as e:
                logger.error(f"删除文档失败: {e}")
                return {
                    "success": False,
                    "deleted_count": 0,
                    "error": str(e),
                    "mode": "real"
                }

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._mock_mode:
            return {
                "initialized": self._initialized,
                "mode": "mock",
                "document_count": len(self._documents),
                "vocabulary_size": len(self._idf),
                "storage_mode": "in-memory",
                "algorithm": "TF-IDF + Cosine Similarity"
            }
        else:
            return {
                "initialized": self._initialized,
                "mode": "real",
                "host": self._host,
                "collection_name": self._collection_name,
                "dense_weight": self._dense_weight,
                "rerank_switch": self._rerank_switch,
                "service_ready": self._service is not None
            }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mock_mode:
            self._documents.clear()
            self._doc_vectors.clear()
            self._idf.clear()

        self._service = None
        self._initialized = False
        logger.debug("VolcengineVikingDB 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized:
            return False

        if self._mock_mode:
            return True
        else:
            try:
                # 尝试获取 collection 信息来验证连接
                self._service.get_collection(collection_name=self._collection_name)
                return True
            except Exception as e:
                logger.warning(f"健康检查失败: {e}")
                return False
