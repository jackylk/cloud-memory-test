"""Google Dialogflow CX 数据存储适配器

支持两种模式:
1. Mock 模式: 使用本地 TF-IDF 向量存储模拟行为（无需凭证）
2. 真实模式: 连接 Google Dialogflow CX 数据存储进行检索

使用方式:
- 如果配置中没有 agent_id 或 data_store_id，自动启用 mock 模式
- 配置完整参数后切换到真实服务

SDK: pip install google-cloud-dialogflow-cx
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


class GoogleDialogflowCXAdapter(KnowledgeBaseAdapter):
    """Google Dialogflow CX 数据存储适配器

    特点:
    - 支持 mock 模式用于无凭证测试
    - 真实模式使用 Google Cloud SDK 调用 Dialogflow CX API
    - 通过 detectIntent 查询数据存储
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "GoogleDialogflowCX"

        # Google Cloud 配置
        self._project_id = config.get("project_id")
        self._location = config.get("location", "global")
        self._agent_id = config.get("agent_id")
        self._data_store_id = config.get("data_store_id")
        self._credentials_path = config.get("credentials_path")

        # 如果没有必要配置，启用 mock 模式
        self._mock_mode = not (
            self._project_id and
            self._agent_id and
            self._data_store_id
        )

        # SDK 客户端（真实模式）
        self._session_client = None
        self._session_path = None

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
            logger.info("GoogleDialogflowCX: 初始化 Mock 模式")
            logger.debug("  → 使用本地 TF-IDF 向量存储模拟")
            if not self._project_id:
                logger.debug("  → 未配置 project_id")
            if not self._agent_id:
                logger.debug("  → 未配置 agent_id")
            if not self._data_store_id:
                logger.debug("  → 未配置 data_store_id")
        else:
            logger.info(f"GoogleDialogflowCX: 初始化真实模式")
            logger.debug(f"  → Project ID: {self._project_id}")
            logger.debug(f"  → Location: {self._location}")
            logger.debug(f"  → Agent ID: {self._agent_id}")
            logger.debug(f"  → Data Store ID: {self._data_store_id}")

            try:
                from google.cloud.dialogflowcx_v3 import SessionsClient
                import os

                # 设置凭证路径（如果提供）
                if self._credentials_path:
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self._credentials_path

                self._session_client = SessionsClient()

                # 创建 session path（用于查询）
                self._session_path = self._session_client.session_path(
                    project=self._project_id,
                    location=self._location,
                    agent=self._agent_id,
                    session="benchmark-session"
                )

                logger.debug("  → Dialogflow CX 客户端创建成功")

            except ImportError:
                logger.error(
                    "Google Cloud Dialogflow CX SDK 未安装，请运行: "
                    "pip install google-cloud-dialogflow-cx"
                )
                raise RuntimeError(
                    "google-cloud-dialogflow-cx is required for Dialogflow CX adapter"
                )
            except Exception as e:
                logger.error(f"初始化 Dialogflow CX 客户端失败: {e}")
                raise

        self._initialized = True
        logger.debug("  → 初始化完成")

    # ========== Mock 模式辅助方法 ==========

    def _tokenize(self, text: str) -> List[str]:
        """简单分词 - 支持中英文"""
        text = text.lower()
        tokens = []
        english_words = re.findall(r'[a-zA-Z]+', text)
        tokens.extend(english_words)
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)
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
        """上传文档"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        if self._mock_mode:
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
            elapsed_ms = (time.time() - start_time) * 1000
            logger.warning(
                "Dialogflow CX 需要通过 Console 或 Data Store API 上传文档。"
                "请使用 Google Cloud Console 配置数据源。"
            )
            return UploadResult(
                success_count=0,
                failed_count=len(documents),
                failed_ids=[doc.id for doc in documents],
                total_time_ms=elapsed_ms,
                details={
                    "mode": "real",
                    "error": "Dialogflow CX requires data upload via Console or Data Store API",
                    "data_store_id": self._data_store_id
                }
            )

    async def build_index(self) -> IndexResult:
        """构建/更新索引"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()

        if self._mock_mode:
            logger.debug(f"[Mock] 构建索引，文档数: {len(self._documents)}")
            self._compute_idf()
            self._doc_vectors = {}
            for doc_id, doc in self._documents.items():
                tokens = self._tokenize(doc.content)
                self._doc_vectors[doc_id] = self._compute_tfidf(tokens)

            elapsed_ms = (time.time() - start_time) * 1000
            return IndexResult(
                success=True,
                index_time_ms=elapsed_ms,
                doc_count=len(self._documents),
                details={"mode": "mock", "vocabulary_size": len(self._idf)}
            )
        else:
            elapsed_ms = (time.time() - start_time) * 1000
            return IndexResult(
                success=True,
                index_time_ms=elapsed_ms,
                doc_count=0,
                details={
                    "mode": "real",
                    "note": "Dialogflow CX manages indexing automatically",
                    "data_store_id": self._data_store_id
                }
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

        query_tokens = self._tokenize(query)
        query_vector = self._compute_tfidf(query_tokens)

        similarities = []
        for doc_id, doc_vector in self._doc_vectors.items():
            sim = self._cosine_similarity(query_vector, doc_vector)
            similarities.append((doc_id, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        top_results = similarities[:top_k]
        elapsed_ms = (time.time() - start_time) * 1000

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
        """真实模式查询 - 调用 Dialogflow CX detectIntent API"""
        logger.debug(f"执行 Dialogflow CX 查询: '{query[:50]}...'")

        try:
            from google.cloud.dialogflowcx_v3 import (
                DetectIntentRequest,
                QueryInput,
                TextInput,
                QueryParameters
            )

            # 构建查询请求
            text_input = TextInput(text=query)
            query_input = QueryInput(text=text_input, language_code="zh-CN")

            # 配置查询参数（包含数据存储）
            query_params = QueryParameters()
            if self._data_store_id:
                query_params.search_config = {
                    "data_store_specs": [{
                        "data_store": f"projects/{self._project_id}/locations/{self._location}/dataStores/{self._data_store_id}"
                    }]
                }

            request = DetectIntentRequest(
                session=self._session_path,
                query_input=query_input,
                query_params=query_params
            )

            response = self._session_client.detect_intent(request=request)
            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果
            documents = []
            scores = []

            # 从 knowledge connector 结果中提取
            query_result = response.query_result
            if hasattr(query_result, 'knowledge_connector') and query_result.knowledge_connector:
                for answer in query_result.knowledge_connector.answer_records[:top_k]:
                    documents.append({
                        "id": getattr(answer, 'id', f"doc_{len(documents)}"),
                        "content": getattr(answer, 'answer', ''),
                        "metadata": {
                            "source": getattr(answer, 'source', ''),
                        },
                        "title": None
                    })
                    scores.append(getattr(answer, 'confidence', 0.0))

            logger.debug(f"Dialogflow CX 查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

            return QueryResult(
                documents=documents,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(documents),
                query=query
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Dialogflow CX 查询失败: {e}")

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
            logger.warning("Dialogflow CX 需要通过 Data Store API 删除文档")
            return {
                "success": False,
                "deleted_count": 0,
                "error": "Requires Data Store API for deletion",
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
                "algorithm": "TF-IDF + Cosine Similarity"
            }
        else:
            return {
                "initialized": self._initialized,
                "mode": "real",
                "project_id": self._project_id,
                "location": self._location,
                "agent_id": self._agent_id,
                "data_store_id": self._data_store_id,
                "client_ready": self._session_client is not None
            }

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mock_mode:
            self._documents.clear()
            self._doc_vectors.clear()
            self._idf.clear()

        self._session_client = None
        self._initialized = False
        logger.debug("GoogleDialogflowCX 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized:
            return False

        if self._mock_mode:
            return True
        else:
            try:
                # 简单的健康检查查询
                from google.cloud.dialogflowcx_v3 import DetectIntentRequest, QueryInput, TextInput

                text_input = TextInput(text="health check")
                query_input = QueryInput(text=text_input, language_code="en")
                request = DetectIntentRequest(
                    session=self._session_path,
                    query_input=query_input
                )
                self._session_client.detect_intent(request=request)
                return True
            except Exception as e:
                logger.warning(f"健康检查失败: {e}")
                return False
