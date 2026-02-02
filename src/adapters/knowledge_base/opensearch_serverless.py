"""OpenSearch Serverless 适配器

支持本地 embedding 后直接写入 AWS OpenSearch Serverless 集合。
可以与 Bedrock Knowledge Base 共用同一个 OpenSearch 集合，或独立使用。

特点:
- 本地生成嵌入向量（支持 sentence-transformers 或 TF-IDF 备选）
- 直接写入 OpenSearch Serverless（无需 AWS 嵌入模型）
- 支持向量相似度搜索
"""

import time
import json
import hashlib
import math
import re
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


class TFIDFEmbedder:
    """TF-IDF 嵌入器 - 无需深度学习框架"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._vocabulary: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._fitted = False

    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        text = text.lower()
        tokens = []
        tokens.extend(re.findall(r'[a-zA-Z]+', text))
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i + 1])
        return tokens

    def fit(self, texts: List[str]) -> None:
        """训练词汇表和 IDF"""
        n_docs = len(texts)
        doc_freq = Counter()

        for text in texts:
            tokens = set(self._tokenize(text))
            for token in tokens:
                doc_freq[token] += 1

        # 构建词汇表（按频率排序，取 top dimension 个）
        sorted_words = sorted(doc_freq.items(), key=lambda x: x[1], reverse=True)
        self._vocabulary = {word: idx for idx, (word, _) in enumerate(sorted_words[:self.dimension])}

        # 计算 IDF
        for word, freq in doc_freq.items():
            if word in self._vocabulary:
                self._idf[word] = math.log(n_docs / (1 + freq))

        self._fitted = True

    def encode(self, texts: List[str], convert_to_numpy: bool = True) -> List[List[float]]:
        """编码文本为向量"""
        if not self._fitted:
            self.fit(texts)

        embeddings = []
        for text in texts:
            tokens = self._tokenize(text)
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1

            # 生成固定维度向量
            vector = [0.0] * self.dimension
            for word, count in tf.items():
                if word in self._vocabulary:
                    idx = self._vocabulary[word]
                    tf_val = count / total
                    idf_val = self._idf.get(word, 0)
                    vector[idx] = tf_val * idf_val

            # 归一化
            norm = math.sqrt(sum(v * v for v in vector))
            if norm > 0:
                vector = [v / norm for v in vector]

            embeddings.append(vector)

        return embeddings


class OpenSearchServerlessAdapter(KnowledgeBaseAdapter):
    """OpenSearch Serverless 适配器

    使用本地嵌入模型 + AWS OpenSearch Serverless 进行向量存储和检索。
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "OpenSearchServerless"

        # OpenSearch 配置
        self._host = config.get("host")  # e.g., "xxx.ap-southeast-1.aoss.amazonaws.com"
        self._region = config.get("region", "ap-southeast-1")
        self._index_name = config.get("index_name", "benchmark-test-index")

        # AWS 凭证
        self._access_key = config.get("access_key_id")
        self._secret_key = config.get("secret_access_key")

        # 嵌入模型配置
        self._embedding_model = config.get("embedding_model", "all-MiniLM-L6-v2")
        self._dimension = config.get("dimension", 384)

        # 客户端
        self._client = None
        self._embedder = None

        # 文档缓存（用于返回原始内容）
        self._doc_cache: Dict[str, Document] = {}

    async def initialize(self) -> None:
        """初始化连接"""
        logger.info(f"OpenSearchServerless: 初始化")
        logger.debug(f"  → Host: {self._host}")
        logger.debug(f"  → Region: {self._region}")
        logger.debug(f"  → Index: {self._index_name}")
        logger.debug(f"  → Embedding model: {self._embedding_model}")

        try:
            # 尝试使用 sentence-transformers
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(self._embedding_model)
                self._use_tfidf = False
                logger.debug(f"  → 使用 sentence-transformers，维度: {self._dimension}")
            except ImportError:
                # 回退到 TF-IDF
                self._embedder = TFIDFEmbedder(dimension=self._dimension)
                self._use_tfidf = True
                logger.info(f"  → sentence-transformers 不可用，使用 TF-IDF 备选方案")

            # 初始化 OpenSearch 客户端
            from opensearchpy import OpenSearch, RequestsHttpConnection
            from requests_aws4auth import AWS4Auth
            import boto3

            # 获取 AWS 凭证
            if self._access_key and self._secret_key:
                credentials = boto3.Session(
                    aws_access_key_id=self._access_key,
                    aws_secret_access_key=self._secret_key
                ).get_credentials()
            else:
                credentials = boto3.Session().get_credentials()

            auth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                self._region,
                'aoss',  # OpenSearch Serverless 服务名
                session_token=credentials.token
            )

            self._client = OpenSearch(
                hosts=[{'host': self._host, 'port': 443}],
                http_auth=auth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                pool_maxsize=20,
            )

            # 检查/创建索引
            await self._ensure_index()

            logger.debug("  → OpenSearch 客户端创建成功")

        except ImportError as e:
            logger.error(f"缺少依赖: {e}")
            logger.error("请运行: pip install opensearch-py requests-aws4auth sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise

        self._initialized = True
        logger.debug("  → 初始化完成")

    async def _ensure_index(self) -> None:
        """确保索引存在"""
        try:
            if not self._client.indices.exists(index=self._index_name):
                logger.info(f"创建索引: {self._index_name}")

                # 创建索引映射
                index_body = {
                    "settings": {
                        "index": {
                            "knn": True,
                            "knn.algo_param.ef_search": 100
                        }
                    },
                    "mappings": {
                        "properties": {
                            "id": {"type": "keyword"},
                            "content": {"type": "text"},
                            "title": {"type": "text"},
                            "metadata": {"type": "object", "enabled": False},
                            "embedding": {
                                "type": "knn_vector",
                                "dimension": self._dimension,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimil",
                                    "engine": "nmslib",
                                    "parameters": {
                                        "ef_construction": 128,
                                        "m": 24
                                    }
                                }
                            }
                        }
                    }
                }

                self._client.indices.create(index=self._index_name, body=index_body)
                logger.debug(f"  → 索引创建成功")
            else:
                logger.debug(f"  → 索引已存在: {self._index_name}")
        except Exception as e:
            logger.warning(f"索引操作失败: {e}")

    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        if self._use_tfidf:
            embeddings = self._embedder.encode([text])
            return embeddings[0]
        else:
            embedding = self._embedder.encode(text, convert_to_numpy=True)
            return embedding.tolist()

    def _generate_doc_id(self, doc_id: str) -> str:
        """生成 OpenSearch 文档 ID"""
        return hashlib.md5(doc_id.encode()).hexdigest()

    async def upload_documents(self, documents: List[Document]) -> UploadResult:
        """上传文档"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        success_count = 0
        failed_count = 0
        failed_ids = []

        logger.debug(f"上传 {len(documents)} 个文档到 OpenSearch")

        # 批量生成嵌入
        texts = [doc.content for doc in documents]
        if self._use_tfidf:
            # TF-IDF 需要先 fit
            self._embedder.fit(texts)
            embeddings = self._embedder.encode(texts)
        else:
            embeddings = self._embedder.encode(texts, convert_to_numpy=True)

        # 批量索引
        bulk_body = []
        for doc, embedding in zip(documents, embeddings):
            try:
                # OpenSearch Serverless 不支持指定文档 ID
                # 添加到批量操作（不指定 _id）
                bulk_body.append({"index": {"_index": self._index_name}})
                # embedding 可能是 numpy array 或 list
                emb_list = embedding if isinstance(embedding, list) else embedding.tolist()
                bulk_body.append({
                    "id": doc.id,
                    "content": doc.content,
                    "title": doc.title or "",
                    "metadata": doc.metadata,
                    "embedding": emb_list
                })

                # 缓存文档
                self._doc_cache[doc.id] = doc
                success_count += 1

            except Exception as e:
                failed_count += 1
                failed_ids.append(doc.id)
                logger.warning(f"文档 {doc.id} 处理失败: {e}")

        # 执行批量索引
        if bulk_body:
            try:
                # OpenSearch Serverless 不支持 refresh=True
                response = self._client.bulk(body=bulk_body)
                if response.get("errors"):
                    for item in response.get("items", []):
                        if "error" in item.get("index", {}):
                            error = item["index"]["error"]
                            logger.warning(f"索引错误: {error}")
            except Exception as e:
                logger.error(f"批量索引失败: {e}")
                failed_count = len(documents)
                success_count = 0

        elapsed_ms = (time.time() - start_time) * 1000

        logger.debug(f"上传完成: 成功 {success_count}, 失败 {failed_count}, 耗时 {elapsed_ms:.2f}ms")

        return UploadResult(
            success_count=success_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            total_time_ms=elapsed_ms,
            details={"index": self._index_name}
        )

    async def build_index(self) -> IndexResult:
        """构建索引 - OpenSearch Serverless 使用近实时索引，等待文档可搜索"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        doc_count = 0

        # OpenSearch Serverless 不支持 indices.refresh()
        # 需要等待近实时索引完成
        import asyncio

        # 等待文档被索引（最多 10 秒，每秒检查一次）
        expected_count = len(self._doc_cache)
        for attempt in range(10):
            try:
                count_response = self._client.count(index=self._index_name)
                doc_count = count_response.get("count", 0)
                logger.debug(f"  → 索引检查 {attempt+1}/10: {doc_count}/{expected_count} 文档")

                if doc_count >= expected_count:
                    break
            except Exception as e:
                logger.warning(f"获取文档数量失败: {e}")

            await asyncio.sleep(1)

        elapsed_ms = (time.time() - start_time) * 1000

        if doc_count < expected_count:
            logger.warning(f"索引可能未完成: 预期 {expected_count}, 实际 {doc_count}")

        return IndexResult(
            success=True,
            index_time_ms=elapsed_ms,
            doc_count=doc_count,
            details={"index": self._index_name}
        )

    async def query(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> QueryResult:
        """执行向量搜索"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        logger.debug(f"执行 OpenSearch 查询: '{query[:50]}...'")

        try:
            # 生成查询向量
            query_embedding = self._generate_embedding(query)

            # 构建 KNN 查询
            search_body = {
                "size": top_k,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": top_k
                        }
                    }
                },
                "_source": ["id", "content", "title", "metadata"]
            }

            # 执行搜索
            response = self._client.search(
                index=self._index_name,
                body=search_body
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果
            documents = []
            scores = []

            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                documents.append({
                    "id": source.get("id", hit.get("_id")),
                    "content": source.get("content", ""),
                    "metadata": source.get("metadata", {}),
                    "title": source.get("title")
                })
                scores.append(hit.get("_score", 0.0))

            logger.debug(f"查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

            return QueryResult(
                documents=documents,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(documents),
                query=query
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"OpenSearch 查询失败: {e}")

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

        deleted = 0

        for doc_id in doc_ids:
            try:
                os_doc_id = self._generate_doc_id(doc_id)
                # OpenSearch Serverless 不支持 refresh=True
                self._client.delete(index=self._index_name, id=os_doc_id)

                if doc_id in self._doc_cache:
                    del self._doc_cache[doc_id]

                deleted += 1
            except Exception as e:
                logger.warning(f"删除文档 {doc_id} 失败: {e}")

        return {
            "success": True,
            "deleted_count": deleted,
            "deleted_ids": doc_ids[:deleted]
        }

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "initialized": self._initialized,
            "host": self._host,
            "region": self._region,
            "index": self._index_name,
            "embedding_model": self._embedding_model,
            "dimension": self._dimension,
        }

        if self._initialized and self._client:
            try:
                count_response = self._client.count(index=self._index_name)
                stats["document_count"] = count_response.get("count", 0)
            except:
                stats["document_count"] = len(self._doc_cache)

        return stats

    async def cleanup(self) -> None:
        """清理资源"""
        self._doc_cache.clear()
        self._client = None
        self._embedder = None
        self._initialized = False
        logger.debug("OpenSearchServerless 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized or not self._client:
            return False

        try:
            self._client.cluster.health()
            return True
        except:
            return False

    async def measure_network_latency(self, num_samples: int = 10) -> Dict[str, float]:
        """测量网络基线延迟（重写基类方法）

        使用 TCP 连接测试到 OpenSearch Serverless endpoint 的网络往返时间（RTT），
        避免使用完整的 API 调用（包含服务端处理时间）。

        Args:
            num_samples: 采样次数，默认10次

        Returns:
            包含 min/max/avg/p50/p95 的延迟字典（单位：毫秒）
        """
        import socket
        import statistics
        from urllib.parse import urlparse

        # 解析 OpenSearch endpoint
        parsed = urlparse(self._host if self._host.startswith("http") else f"https://{self._host}")
        host = parsed.hostname or self._host
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

        logger.debug(f"OpenSearch Serverless 网络延迟测量完成: {result}")
        return result
