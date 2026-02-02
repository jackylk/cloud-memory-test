"""AWS Bedrock Knowledge Base 适配器

支持两种模式:
1. Mock 模式: 使用本地 TF-IDF 向量存储模拟 AWS Bedrock 行为（无需 AWS 凭证）
2. 真实模式: 连接 AWS Bedrock Knowledge Base 进行检索

使用方式:
- 如果配置中没有 knowledge_base_id，自动启用 mock 模式
- 配置 knowledge_base_id 后切换到真实 AWS 服务

注意: AWS Bedrock KB 不支持直接上传文档，需要在 AWS Console 预先配置 S3 数据源。
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


class AWSBedrockKBAdapter(KnowledgeBaseAdapter):
    """AWS Bedrock Knowledge Base 适配器

    特点:
    - 支持 mock 模式用于无凭证测试
    - 真实模式使用 boto3 调用 Bedrock retrieve API
    - upload_documents 在真实模式下返回不支持提示
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        # 允许自定义适配器名称（用于区分不同存储后端）
        self.name = config.get("adapter_name", "AWSBedrockKB")

        # AWS 配置
        self._region = config.get("region", "us-east-1")
        self._knowledge_base_id = config.get("knowledge_base_id")
        self._access_key_id = config.get("access_key_id")
        self._secret_access_key = config.get("secret_access_key")

        # 如果没有 knowledge_base_id，启用 mock 模式
        self._mock_mode = not self._knowledge_base_id

        # boto3 客户端（真实模式）
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
            logger.info("AWSBedrockKB: 初始化 Mock 模式")
            logger.debug("  → 使用本地 TF-IDF 向量存储模拟")
            logger.debug("  → 未配置 knowledge_base_id")
        else:
            logger.info(f"AWSBedrockKB: 初始化真实模式")
            logger.debug(f"  → Region: {self._region}")
            logger.debug(f"  → KB ID: {self._knowledge_base_id}")

            try:
                import boto3
                from botocore.config import Config as BotoConfig

                # 构建客户端配置
                boto_config = BotoConfig(
                    region_name=self._region,
                    retries={"max_attempts": 3, "mode": "adaptive"}
                )

                # 创建客户端
                session_kwargs = {}
                if self._access_key_id and self._secret_access_key:
                    session_kwargs["aws_access_key_id"] = self._access_key_id
                    session_kwargs["aws_secret_access_key"] = self._secret_access_key

                session = boto3.Session(**session_kwargs)
                self._client = session.client(
                    "bedrock-agent-runtime",
                    config=boto_config
                )

                logger.debug("  → boto3 客户端创建成功")

            except ImportError:
                logger.error("boto3 未安装，请运行: pip install boto3")
                raise RuntimeError("boto3 is required for AWS Bedrock KB adapter")
            except Exception as e:
                logger.error(f"初始化 AWS 客户端失败: {e}")
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
        真实模式: AWS Bedrock 不支持直接上传，返回提示信息
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
            # 真实模式：AWS Bedrock 不支持直接上传
            elapsed_ms = (time.time() - start_time) * 1000

            logger.warning(
                "AWS Bedrock KB 不支持直接上传文档。"
                "请在 AWS Console 配置 S3 数据源并同步。"
            )

            return UploadResult(
                success_count=0,
                failed_count=len(documents),
                failed_ids=[doc.id for doc in documents],
                total_time_ms=elapsed_ms,
                details={
                    "mode": "real",
                    "error": "AWS Bedrock KB does not support direct upload. "
                             "Use S3 data source in AWS Console.",
                    "knowledge_base_id": self._knowledge_base_id
                }
            )

    async def build_index(self) -> IndexResult:
        """构建/更新索引

        Mock 模式: 计算本地 TF-IDF 索引
        真实模式: AWS Bedrock 自动管理索引，返回成功
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
            # 真实模式：AWS 自动管理索引
            elapsed_ms = (time.time() - start_time) * 1000

            return IndexResult(
                success=True,
                index_time_ms=elapsed_ms,
                doc_count=0,  # 无法获取实际文档数
                details={
                    "mode": "real",
                    "note": "AWS Bedrock manages indexing automatically",
                    "knowledge_base_id": self._knowledge_base_id
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
        真实模式: 调用 bedrock-agent-runtime.retrieve()
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
        """真实模式查询 - 调用 AWS Bedrock API"""
        logger.debug(f"执行 Bedrock 查询: '{query[:50]}...'")

        try:
            # 构建请求参数
            request_params = {
                "knowledgeBaseId": self._knowledge_base_id,
                "retrievalQuery": {"text": query},
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {
                        "numberOfResults": top_k
                    }
                }
            }

            # 添加过滤器（如果有）
            if filters:
                request_params["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"] = filters

            # 调用 API
            response = self._client.retrieve(**request_params)

            elapsed_ms = (time.time() - start_time) * 1000

            # 解析结果
            documents = []
            scores = []

            for result in response.get("retrievalResults", []):
                content = result.get("content", {})
                doc_text = content.get("text", "")

                # 获取元数据
                location = result.get("location", {})
                metadata = {
                    "type": location.get("type", ""),
                    "uri": location.get("s3Location", {}).get("uri", "")
                        if location.get("type") == "S3" else "",
                }

                documents.append({
                    "id": metadata.get("uri", f"doc_{len(documents)}"),
                    "content": doc_text,
                    "metadata": metadata,
                    "title": None
                })

                # Bedrock 返回的分数
                scores.append(result.get("score", 0.0))

            logger.debug(f"Bedrock 查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

            return QueryResult(
                documents=documents,
                scores=scores,
                latency_ms=elapsed_ms,
                total_results=len(documents),
                query=query
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Bedrock 查询失败: {e}")

            # 返回空结果而不是抛出异常
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
        真实模式: AWS Bedrock 不支持直接删除
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
            logger.warning(
                "AWS Bedrock KB 不支持直接删除文档。"
                "请在 S3 数据源中删除文件并重新同步。"
            )
            return {
                "success": False,
                "deleted_count": 0,
                "error": "AWS Bedrock KB does not support direct deletion",
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
                "region": self._region,
                "knowledge_base_id": self._knowledge_base_id,
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
        logger.debug("AWSBedrockKB 已清理")

    async def health_check(self) -> bool:
        """健康检查"""
        if not self._initialized:
            return False

        if self._mock_mode:
            return True
        else:
            # 尝试一个简单的查询来验证连接
            try:
                self._client.retrieve(
                    knowledgeBaseId=self._knowledge_base_id,
                    retrievalQuery={"text": "health check"},
                    retrievalConfiguration={
                        "vectorSearchConfiguration": {
                            "numberOfResults": 1
                        }
                    }
                )
                return True
            except Exception as e:
                logger.warning(f"健康检查失败: {e}")
                return False

    async def measure_network_latency(self, num_samples: int = 10) -> Dict[str, float]:
        """测量网络基线延迟（重写基类方法）

        使用 TCP 连接测试到 AWS Bedrock endpoint 的网络往返时间（RTT），
        避免使用完整的 retrieve API（包含服务端处理时间）。

        Args:
            num_samples: 采样次数，默认10次

        Returns:
            包含 min/max/avg/p50/p95 的延迟字典（单位：毫秒）
        """
        import socket
        import statistics

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

        # AWS Bedrock Agent Runtime endpoint
        host = f"bedrock-agent-runtime.{self._region}.amazonaws.com"
        port = 443  # HTTPS 默认端口

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

        logger.debug(f"AWS Bedrock 网络延迟测量完成: {result}")
        return result
