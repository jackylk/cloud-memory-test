"""阿里百炼知识库适配器

支持两种模式:
1. Mock 模式: 使用本地 TF-IDF 向量存储模拟百炼行为（无需凭证）
2. 真实模式: 连接阿里百炼知识库进行检索

使用方式:
- 如果配置中没有 index_id，自动启用 mock 模式
- 配置 access_key_id/access_key_secret/workspace_id/index_id 后切换到真实服务

SDK: pip install alibabacloud-bailian20231229
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


class AlibabaBailianAdapter(KnowledgeBaseAdapter):
    """阿里百炼知识库适配器

    特点:
    - 支持 mock 模式用于无凭证测试
    - 真实模式使用阿里云 SDK 调用百炼 API
    - 支持混合搜索和重排序
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "AlibabaBailian"

        # 阿里云配置
        self._access_key_id = config.get("access_key_id")
        self._access_key_secret = config.get("access_key_secret")
        self._workspace_id = config.get("workspace_id")
        self._index_id = config.get("index_id")
        self._endpoint = config.get("endpoint", "bailian.cn-beijing.aliyuncs.com")
        self._region = config.get("region", "cn-beijing")

        # 检索配置
        self._dense_similarity_top_k = config.get("dense_similarity_top_k", 100)
        self._sparse_similarity_top_k = config.get("sparse_similarity_top_k", 100)
        self._enable_reranking = config.get("enable_reranking", True)
        self._rerank_top_n = config.get("rerank_top_n", 5)
        self._rerank_min_score = config.get("rerank_min_score", 0.01)

        # 如果没有必要配置，启用 mock 模式
        self._mock_mode = not (
            self._access_key_id and
            self._access_key_secret and
            self._workspace_id and
            self._index_id
        )

        # SDK 客户端（真实模式）
        self._client = None

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
            logger.info("AlibabaBailian: 初始化 Mock 模式")
            logger.debug("  → 使用本地 TF-IDF 向量存储模拟")
            if not self._workspace_id:
                logger.debug("  → 未配置 workspace_id")
            if not self._index_id:
                logger.debug("  → 未配置 index_id")
            if not self._access_key_id or not self._access_key_secret:
                logger.debug("  → 未配置 access_key_id/access_key_secret")
        else:
            logger.info(f"AlibabaBailian: 初始化真实模式")
            logger.debug(f"  → Endpoint: {self._endpoint}")
            logger.debug(f"  → Workspace ID: {self._workspace_id}")
            logger.debug(f"  → Index ID: {self._index_id}")

            try:
                from alibabacloud_bailian20231229.client import Client as BailianClient
                from alibabacloud_tea_openapi import models as open_api_models

                config = open_api_models.Config(
                    access_key_id=self._access_key_id,
                    access_key_secret=self._access_key_secret,
                    endpoint=self._endpoint
                )
                self._client = BailianClient(config)

                logger.debug("  → 百炼客户端创建成功")

            except ImportError:
                logger.error(
                    "阿里云 SDK 未安装，请运行: "
                    "pip install alibabacloud-bailian20231229"
                )
                raise RuntimeError(
                    "alibabacloud-bailian20231229 is required for Bailian adapter"
                )
            except Exception as e:
                logger.error(f"初始化百炼客户端失败: {e}")
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
        真实模式: 百炼需要通过多步骤上传流程
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
            # 真实模式：百炼需要多步骤上传
            elapsed_ms = (time.time() - start_time) * 1000

            logger.warning(
                "阿里百炼需要通过多步骤流程上传文档："
                "1. ApplyFileUploadLease 2. 上传到临时存储 3. AddFile。"
                "请参考 API 文档配置数据源。"
            )

            return UploadResult(
                success_count=0,
                failed_count=len(documents),
                failed_ids=[doc.id for doc in documents],
                total_time_ms=elapsed_ms,
                details={
                    "mode": "real",
                    "error": "Bailian requires multi-step upload process. "
                             "See API documentation.",
                    "workspace_id": self._workspace_id,
                    "index_id": self._index_id
                }
            )

    async def build_index(self) -> IndexResult:
        """构建/更新索引

        Mock 模式: 计算本地 TF-IDF 索引
        真实模式: 百炼自动管理索引
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
            # 真实模式：百炼自动管理索引
            elapsed_ms = (time.time() - start_time) * 1000

            return IndexResult(
                success=True,
                index_time_ms=elapsed_ms,
                doc_count=0,
                details={
                    "mode": "real",
                    "note": "Bailian manages indexing automatically after SubmitIndexJob",
                    "workspace_id": self._workspace_id,
                    "index_id": self._index_id
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
        真实模式: 调用百炼 Retrieve API
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
        """真实模式查询 - 调用百炼 Retrieve API"""
        logger.debug(f"执行百炼查询: '{query[:50]}...'")

        try:
            from alibabacloud_bailian20231229 import models as bailian_20231229_models

            # 构建检索请求
            # 使用 rerank_top_n 作为最终返回数量，如果 top_k 更小则使用 top_k
            final_top_n = min(top_k, self._rerank_top_n)

            retrieve_request = bailian_20231229_models.RetrieveRequest(
                query=query,
                index_id=self._index_id,
                dense_similarity_top_k=self._dense_similarity_top_k,
                sparse_similarity_top_k=self._sparse_similarity_top_k,
                enable_reranking=self._enable_reranking,
                rerank_top_n=max(final_top_n, 1),  # 至少返回 1 个结果
                rerank_min_score=self._rerank_min_score,
                enable_rewrite=False  # 单轮查询不需要重写
            )

            # 调用 Retrieve API
            from alibabacloud_tea_util import models as util_models
            runtime = util_models.RuntimeOptions()

            response = self._client.retrieve_with_options(
                self._workspace_id,
                retrieve_request,
                {},
                runtime
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果
            documents = []
            scores = []

            # 百炼API返回结构: response.body.data.nodes (对象属性访问)
            data = getattr(response.body, 'data', None)
            nodes = getattr(data, 'nodes', []) if data else []

            if nodes:
                for node in nodes[:top_k]:
                    # 提取metadata - node是对象，有metadata/score/text属性
                    node_metadata = getattr(node, 'metadata', None)
                    text = getattr(node, 'text', '')
                    score = getattr(node, 'score', 0.0)

                    # 从metadata提取文档信息
                    doc_name = None
                    doc_id = None
                    metadata_raw = {}

                    if node_metadata:
                        # metadata是字典，使用字典访问方式
                        doc_name = node_metadata.get('doc_name')
                        title = node_metadata.get('title')
                        doc_id = node_metadata.get('doc_id')
                        file_path = node_metadata.get('file_path')

                        metadata_raw = {
                            "title": title,
                            "doc_id": doc_id,
                            "file_path": file_path,
                            "doc_name": doc_name,
                        }

                        # 优先使用doc_name，其次title
                        if not doc_name:
                            doc_name = title

                        # 如果还是None，尝试从file_path提取
                        if not doc_name and file_path:
                            # 从URL中提取文件名
                            if "/" in file_path:
                                fname = file_path.split("/")[-1].split("?")[0]
                                # 去除.json后缀
                                if fname.endswith('.json'):
                                    fname = fname[:-5]
                                doc_name = fname

                    # 构建文档对象
                    documents.append({
                        "id": doc_name or doc_id or f"doc_{len(documents)}",
                        "content": text,
                        "metadata": metadata_raw,
                        "title": doc_name
                    })

                    scores.append(score)

            logger.debug(f"百炼查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

            return QueryResult(
                documents=documents,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(documents),
                query=query
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"百炼查询失败: {e}")

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
        真实模式: 调用百炼删除 API
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
                from alibabacloud_bailian20231229 import models as bailian_20231229_models

                # 百炼使用 DeleteFile API 删除文档
                deleted = 0
                for doc_id in doc_ids:
                    try:
                        delete_request = bailian_20231229_models.DeleteFileRequest(
                            file_id=doc_id
                        )
                        self._client.delete_file(self._workspace_id, delete_request)
                        deleted += 1
                    except Exception as e:
                        logger.warning(f"删除文档 {doc_id} 失败: {e}")

                return {
                    "success": True,
                    "deleted_count": deleted,
                    "deleted_ids": doc_ids[:deleted],
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
                "endpoint": self._endpoint,
                "workspace_id": self._workspace_id,
                "index_id": self._index_id,
                "enable_reranking": self._enable_reranking,
                "rerank_top_n": self._rerank_top_n,
                "client_ready": self._client is not None
            }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mock_mode:
            self._documents.clear()
            self._doc_vectors.clear()
            self._idf.clear()

        self._client = None
        self._initialized = False
        logger.debug("AlibabaBailian 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized:
            return False

        if self._mock_mode:
            return True
        else:
            try:
                # 尝试一个简单的查询来验证连接
                from alibabacloud_bailian20231229 import models as bailian_20231229_models

                retrieve_request = bailian_20231229_models.RetrieveRequest(
                    query="health check",
                    index_id=self._index_id,
                    rerank_top_n=1
                )
                self._client.retrieve(
                    self._workspace_id,
                    self._index_id,
                    retrieve_request
                )
                return True
            except Exception as e:
                logger.warning(f"健康检查失败: {e}")
                return False
