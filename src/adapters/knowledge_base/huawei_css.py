"""华为云 CSS (Cloud Search Service) 适配器

支持两种模式:
1. Mock 模式: 使用本地 TF-IDF 向量存储模拟行为（无需凭证）
2. 真实模式: 连接华为云 CSS 进行检索（基于 Elasticsearch）

使用方式:
- 如果配置中没有 cluster_id，自动启用 mock 模式
- 配置完整参数后切换到真实服务

SDK: pip install huaweicloudsdkcss elasticsearch
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


class HuaweiCSSAdapter(KnowledgeBaseAdapter):
    """华为云 CSS 适配器

    特点:
    - 支持 mock 模式用于无凭证测试
    - 真实模式使用 Elasticsearch 客户端查询 CSS 集群
    - 支持全文检索和语义搜索
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "HuaweiCSS"

        # 华为云配置
        self._ak = config.get("ak")
        self._sk = config.get("sk")
        self._region = config.get("region", "cn-north-4")
        self._cluster_id = config.get("cluster_id")
        self._endpoint = config.get("endpoint")  # CSS 集群访问地址
        self._index_name = config.get("index_name", "benchmark-test-index")

        # Elasticsearch 认证
        self._es_username = config.get("es_username", "admin")
        self._es_password = config.get("es_password")

        # 如果没有必要配置，启用 mock 模式
        self._mock_mode = not (
            self._cluster_id and
            self._endpoint
        )

        # Elasticsearch 客户端（真实模式）
        self._es_client = None

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
            logger.info("HuaweiCSS: 初始化 Mock 模式")
            logger.debug("  → 使用本地 TF-IDF 向量存储模拟")
            if not self._cluster_id:
                logger.debug("  → 未配置 cluster_id")
            if not self._endpoint:
                logger.debug("  → 未配置 endpoint")
        else:
            logger.info(f"HuaweiCSS: 初始化真实模式")
            logger.debug(f"  → Region: {self._region}")
            logger.debug(f"  → Cluster ID: {self._cluster_id}")
            logger.debug(f"  → Endpoint: {self._endpoint}")
            logger.debug(f"  → Index: {self._index_name}")

            try:
                from elasticsearch import Elasticsearch

                # 创建 Elasticsearch 客户端连接到 CSS
                es_config = {
                    "hosts": [self._endpoint],
                    "verify_certs": True,
                    "ssl_show_warn": False,
                }

                # 如果提供了用户名密码
                if self._es_username and self._es_password:
                    es_config["http_auth"] = (self._es_username, self._es_password)

                self._es_client = Elasticsearch(**es_config)

                # 检查连接
                info = self._es_client.info()
                logger.debug(f"  → 连接到 Elasticsearch: {info.get('version', {}).get('number', 'unknown')}")

                # 确保索引存在
                await self._ensure_index()

            except ImportError:
                logger.error(
                    "Elasticsearch SDK 未安装，请运行: "
                    "pip install elasticsearch"
                )
                raise RuntimeError("elasticsearch is required for Huawei CSS adapter")
            except Exception as e:
                logger.error(f"初始化 CSS 客户端失败: {e}")
                raise

        self._initialized = True
        logger.debug("  → 初始化完成")

    async def _ensure_index(self) -> None:
        """确保索引存在"""
        try:
            if not self._es_client.indices.exists(index=self._index_name):
                logger.info(f"创建索引: {self._index_name}")

                # 创建索引映射
                index_body = {
                    "mappings": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "content": {"type": "text", "analyzer": "standard"},
                            "title": {"type": "text"},
                            "metadata": {"type": "object", "enabled": False},
                        }
                    }
                }

                self._es_client.indices.create(index=self._index_name, body=index_body)
                logger.debug(f"  → 索引创建成功")
            else:
                logger.debug(f"  → 索引已存在: {self._index_name}")
        except Exception as e:
            logger.warning(f"索引操作失败: {e}")

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
            # 真实模式：批量索引到 Elasticsearch
            success_count = 0
            failed_count = 0
            failed_ids = []

            logger.debug(f"上传 {len(documents)} 个文档到 CSS")

            # 批量索引
            from elasticsearch.helpers import bulk

            actions = []
            for doc in documents:
                action = {
                    "_index": self._index_name,
                    "_id": doc.id,
                    "_source": {
                        "id": doc.id,
                        "content": doc.content,
                        "title": doc.title or "",
                        "metadata": doc.metadata,
                    }
                }
                actions.append(action)

            try:
                success, failed = bulk(self._es_client, actions, raise_on_error=False)
                success_count = success
                failed_count = len(failed)
                failed_ids = [item['index']['_id'] for item in failed] if failed else []

                # 刷新索引确保可搜索
                self._es_client.indices.refresh(index=self._index_name)

            except Exception as e:
                logger.error(f"批量索引失败: {e}")
                failed_count = len(documents)
                success_count = 0
                failed_ids = [doc.id for doc in documents]

            elapsed_ms = (time.time() - start_time) * 1000

            logger.debug(f"上传完成: 成功 {success_count}, 失败 {failed_count}, 耗时 {elapsed_ms:.2f}ms")

            return UploadResult(
                success_count=success_count,
                failed_count=failed_count,
                failed_ids=failed_ids,
                total_time_ms=elapsed_ms,
                details={"mode": "real", "index": self._index_name}
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
            # 真实模式：刷新索引
            try:
                self._es_client.indices.refresh(index=self._index_name)
                count = self._es_client.count(index=self._index_name)
                doc_count = count.get('count', 0)
            except Exception as e:
                logger.warning(f"索引刷新失败: {e}")
                doc_count = 0

            elapsed_ms = (time.time() - start_time) * 1000
            return IndexResult(
                success=True,
                index_time_ms=elapsed_ms,
                doc_count=doc_count,
                details={"mode": "real", "index": self._index_name}
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
        """真实模式查询 - 调用 Elasticsearch search API"""
        logger.debug(f"执行 CSS 查询: '{query[:50]}...'")

        try:
            # 构建 Elasticsearch 查询
            search_body = {
                "size": top_k,
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["content^2", "title"],  # content 权重更高
                        "type": "best_fields"
                    }
                }
            }

            # 添加过滤器
            if filters:
                search_body["query"] = {
                    "bool": {
                        "must": search_body["query"],
                        "filter": filters
                    }
                }

            # 执行搜索
            response = self._es_client.search(
                index=self._index_name,
                body=search_body
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果
            documents = []
            scores = []

            for hit in response['hits']['hits']:
                source = hit['_source']
                documents.append({
                    "id": source.get('id', hit['_id']),
                    "content": source.get('content', ''),
                    "metadata": source.get('metadata', {}),
                    "title": source.get('title')
                })
                scores.append(hit['_score'])

            logger.debug(f"CSS 查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

            return QueryResult(
                documents=documents,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=response['hits']['total']['value'],
                query=query
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"CSS 查询失败: {e}")

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
            try:
                deleted = 0
                for doc_id in doc_ids:
                    self._es_client.delete(index=self._index_name, id=doc_id)
                    deleted += 1

                self._es_client.indices.refresh(index=self._index_name)

                return {
                    "success": True,
                    "deleted_count": deleted,
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
                "algorithm": "TF-IDF + Cosine Similarity"
            }
        else:
            stats = {
                "initialized": self._initialized,
                "mode": "real",
                "region": self._region,
                "cluster_id": self._cluster_id,
                "endpoint": self._endpoint,
                "index": self._index_name,
                "client_ready": self._es_client is not None
            }

            if self._es_client:
                try:
                    count = self._es_client.count(index=self._index_name)
                    stats["document_count"] = count.get('count', 0)
                except:
                    pass

            return stats

    async def cleanup(self) -> None:
        """清理资源"""
        if self._mock_mode:
            self._documents.clear()
            self._doc_vectors.clear()
            self._idf.clear()

        if self._es_client:
            self._es_client.close()
        self._es_client = None
        self._initialized = False
        logger.debug("HuaweiCSS 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized:
            return False

        if self._mock_mode:
            return True
        else:
            try:
                self._es_client.cluster.health()
                return True
            except Exception as e:
                logger.warning(f"健康检查失败: {e}")
                return False

    async def measure_network_latency(self, num_samples: int = 10) -> Dict[str, float]:
        """测量网络基线延迟（重写基类方法）

        使用 TCP 连接测试到华为云 CSS endpoint 的网络往返时间（RTT），
        避免使用完整的 API 调用（包含服务端处理时间）。

        Args:
            num_samples: 采样次数，默认10次

        Returns:
            包含 min/max/avg/p50/p95 的延迟字典（单位：毫秒）
        """
        import socket
        import statistics
        from urllib.parse import urlparse

        if self._mock_mode:
            # Mock 模式返回近似零的本地延迟
            return {
                "min": 0.1,
                "max": 0.5,
                "avg": 0.2,
                "p50": 0.2,
                "p95": 0.4,
                "samples": num_samples,
                "method": "mock"
            }

        # 解析华为云 CSS endpoint
        parsed = urlparse(self._endpoint if self._endpoint.startswith("http") else f"https://{self._endpoint}")
        host = parsed.hostname or self._endpoint
        port = parsed.port or 443  # 默认 HTTPS 端口

        latencies = []

        for _ in range(num_samples):
            try:
                start = time.time()
                # 创建 TCP 连接测试（仅测量网络延迟，不发送 HTTP 请求）
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)  # 5秒超时
                sock.connect((host, port))
                sock.close()
                elapsed_ms = (time.time() - start) * 1000
                latencies.append(elapsed_ms)
            except socket.timeout:
                logger.warning(f"TCP 连接超时: {host}:{port}")
            except socket.error as e:
                logger.warning(f"TCP 连接失败: {host}:{port} - {e}")
            except Exception as e:
                logger.warning(f"网络延迟测量失败: {e}")

        if not latencies:
            logger.warning("所有网络延迟采样均失败，返回零值")
            return {
                "min": 0.0,
                "max": 0.0,
                "avg": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "samples": 0,
                "method": "tcp_connect_failed"
            }

        sorted_latencies = sorted(latencies)
        p50_idx = int(len(sorted_latencies) * 0.5)
        p95_idx = min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)

        result = {
            "min": min(latencies),
            "max": max(latencies),
            "avg": statistics.mean(latencies),
            "p50": sorted_latencies[p50_idx],
            "p95": sorted_latencies[p95_idx],
            "samples": len(latencies),
            "method": "tcp_connect",
            "endpoint": f"{host}:{port}"
        }

        logger.debug(f"华为云 CSS 网络延迟测量完成: {result}")
        return result
