"""简单向量存储 - 使用纯 numpy 实现，无外部依赖

这是一个用于本地调试的简单实现，使用 TF-IDF 和余弦相似度进行检索。
不需要安装 chromadb 或 sentence-transformers。
"""

import time
import re
from typing import List, Optional, Dict, Any
from collections import Counter
import math
from loguru import logger

from ..base import (
    KnowledgeBaseAdapter,
    Document,
    QueryResult,
    UploadResult,
    IndexResult,
)


class SimpleVectorStore(KnowledgeBaseAdapter):
    """简单向量存储 - 基于 TF-IDF 的本地实现

    特点:
    - 无外部依赖，只需要 numpy
    - 使用 TF-IDF 进行文本向量化
    - 使用余弦相似度进行检索
    - 适合本地调试和小规模测试
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "SimpleVectorStore"

        # 文档存储
        self._documents: Dict[str, Document] = {}

        # TF-IDF 相关
        self._vocabulary: Dict[str, int] = {}  # 词 -> 索引
        self._idf: Dict[str, float] = {}  # 词 -> IDF值
        self._doc_vectors: Dict[str, Dict[str, float]] = {}  # doc_id -> {word: tf-idf}

    async def initialize(self) -> None:
        """初始化"""
        logger.debug("初始化 SimpleVectorStore")
        logger.debug("  → 使用 TF-IDF 向量化")
        logger.debug("  → 使用余弦相似度检索")
        self._initialized = True
        logger.debug("  → 初始化完成")

    def _tokenize(self, text: str) -> List[str]:
        """简单分词 - 支持中英文"""
        # 英文：按空格和标点分割
        # 中文：按字符分割
        text = text.lower()

        # 分离中英文
        tokens = []

        # 使用正则分离
        # 英文单词
        english_words = re.findall(r'[a-zA-Z]+', text)
        tokens.extend(english_words)

        # 中文字符（每个字作为一个token）
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)

        # 也支持中文词组（2-3个字的组合）
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i + 1])

        return tokens

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """计算词频 (Term Frequency)"""
        counter = Counter(tokens)
        total = len(tokens)
        if total == 0:
            return {}
        return {word: count / total for word, count in counter.items()}

    def _compute_idf(self) -> None:
        """计算逆文档频率 (Inverse Document Frequency)"""
        n_docs = len(self._documents)
        if n_docs == 0:
            return

        # 统计每个词出现在多少文档中
        doc_freq = Counter()
        for doc in self._documents.values():
            tokens = set(self._tokenize(doc.content))
            for token in tokens:
                doc_freq[token] += 1

        # 计算 IDF
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
        # 获取所有词
        all_words = set(vec1.keys()) | set(vec2.keys())

        # 计算点积和模长
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

    async def upload_documents(self, documents: List[Document]) -> UploadResult:
        """上传文档"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        success_count = 0
        failed_count = 0
        failed_ids = []

        logger.debug(f"开始上传 {len(documents)} 个文档")

        for i, doc in enumerate(documents):
            try:
                self._documents[doc.id] = doc
                success_count += 1
                logger.debug(f"  → 文档 {i + 1}/{len(documents)}: {doc.id}")
            except Exception as e:
                failed_count += 1
                failed_ids.append(doc.id)
                logger.warning(f"  → 文档 {doc.id} 上传失败: {e}")

        elapsed_ms = (time.time() - start_time) * 1000

        logger.debug(f"上传完成: 成功 {success_count}, 失败 {failed_count}")
        return UploadResult(
            success_count=success_count,
            failed_count=failed_count,
            failed_ids=failed_ids,
            total_time_ms=elapsed_ms
        )

    async def build_index(self) -> IndexResult:
        """构建索引 - 计算 TF-IDF"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

        start_time = time.time()
        logger.debug(f"开始构建索引，文档数: {len(self._documents)}")

        # 计算 IDF
        self._compute_idf()

        # 计算每个文档的 TF-IDF 向量
        self._doc_vectors = {}
        for doc_id, doc in self._documents.items():
            tokens = self._tokenize(doc.content)
            self._doc_vectors[doc_id] = self._compute_tfidf(tokens)

        elapsed_ms = (time.time() - start_time) * 1000

        logger.debug(f"索引构建完成: {len(self._doc_vectors)} 个文档, 词汇量 {len(self._idf)}")

        return IndexResult(
            success=True,
            index_time_ms=elapsed_ms,
            doc_count=len(self._documents),
            details={
                "vocabulary_size": len(self._idf)
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
        logger.debug(f"执行查询: '{query[:50]}...'")

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

        logger.debug(f"查询完成: {len(documents)} 个结果, 耗时 {elapsed_ms:.2f}ms")

        return QueryResult(
            documents=documents,
            scores=scores,
            latency_ms=elapsed_ms,
            total_results=len(documents),
            query=query
        )

    async def delete_documents(self, doc_ids: List[str]) -> Dict[str, Any]:
        """删除文档"""
        if not self._initialized:
            raise RuntimeError("适配器未初始化")

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
            "deleted_ids": doc_ids
        }

    async def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "initialized": self._initialized,
            "document_count": len(self._documents),
            "vocabulary_size": len(self._idf),
            "storage_mode": "in-memory",
            "algorithm": "TF-IDF + Cosine Similarity"
        }

    async def cleanup(self) -> None:
        """清理资源"""
        self._documents.clear()
        self._doc_vectors.clear()
        self._idf.clear()
        self._initialized = False
        logger.debug("SimpleVectorStore 已清理")
