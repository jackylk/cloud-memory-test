"""测试数据生成器"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple
from loguru import logger

from ..adapters.base import Document, DocumentFormat, Memory


# 示例文档主题和内容模板
DOCUMENT_TOPICS = [
    ("机器学习基础", "机器学习是人工智能的一个分支，它使计算机能够从数据中学习。"),
    ("深度学习入门", "深度学习是机器学习的子集，使用多层神经网络来学习数据表示。"),
    ("自然语言处理", "自然语言处理(NLP)是让计算机理解、解释和生成人类语言的技术。"),
    ("计算机视觉", "计算机视觉使机器能够从图像或视频中获取有意义的信息。"),
    ("推荐系统", "推荐系统通过分析用户行为和偏好来预测用户可能感兴趣的内容。"),
    ("知识图谱", "知识图谱是一种结构化的语义知识库，用于描述物理世界中的概念及其相互关系。"),
    ("强化学习", "强化学习是机器学习的一种方法，智能体通过与环境交互来学习最优策略。"),
    ("迁移学习", "迁移学习是将一个领域学到的知识应用到另一个相关领域的技术。"),
    ("联邦学习", "联邦学习是一种分布式机器学习方法，可以在不共享原始数据的情况下训练模型。"),
    ("模型压缩", "模型压缩技术可以减少深度学习模型的大小和计算需求，便于部署。"),
]

SAMPLE_QUERIES = [
    "什么是机器学习？",
    "深度学习和机器学习有什么区别？",
    "如何入门自然语言处理？",
    "推荐系统的工作原理是什么？",
    "知识图谱有哪些应用场景？",
    "强化学习的基本概念是什么？",
    "什么是迁移学习？",
    "联邦学习如何保护隐私？",
    "如何进行模型压缩？",
    "计算机视觉的主要任务有哪些？",
]

MEMORY_TEMPLATES = [
    ("用户偏好: 喜欢{topic}相关的内容", "preference"),
    ("用户提到: 正在学习{topic}", "fact"),
    ("对话记录: 用户询问了关于{topic}的问题", "episode"),
    ("用户反馈: 觉得{topic}的解释很清楚", "feedback"),
    ("学习进度: 用户已完成{topic}的基础学习", "progress"),
]


class TestDataGenerator:
    """测试数据生成器"""

    def __init__(self, seed: int = 42):
        """初始化，设置随机种子以保证可重复性"""
        random.seed(seed)
        self.seed = seed
        logger.debug(f"数据生成器初始化，随机种子: {seed}")

    def generate_documents(
        self,
        count: int,
        content_length: int = 500
    ) -> List[Document]:
        """生成测试文档

        Args:
            count: 文档数量
            content_length: 每个文档的大致字符数

        Returns:
            文档列表
        """
        logger.debug(f"生成 {count} 个测试文档，每个约 {content_length} 字符")

        documents = []
        for i in range(count):
            # 随机选择主题
            topic, base_content = random.choice(DOCUMENT_TOPICS)

            # 扩展内容到指定长度
            content = self._expand_content(base_content, content_length, topic)

            doc = Document(
                id=f"doc_{i:04d}",
                title=f"{topic} - 文档 {i + 1}",
                content=content,
                format=DocumentFormat.TXT,
                metadata={
                    "topic": topic,
                    "generated": True,
                    "index": i
                }
            )
            documents.append(doc)

        logger.debug(f"生成完成: {len(documents)} 个文档")
        return documents

    def generate_queries(self, count: int) -> List[str]:
        """生成测试查询

        Args:
            count: 查询数量

        Returns:
            查询列表
        """
        logger.debug(f"生成 {count} 个测试查询")

        queries = []
        for i in range(count):
            # 从预定义查询中选择，或生成变体
            base_query = random.choice(SAMPLE_QUERIES)

            if random.random() > 0.5:
                # 使用原始查询
                queries.append(base_query)
            else:
                # 生成变体
                queries.append(self._generate_query_variant(base_query))

        return queries

    def generate_queries_with_ground_truth(
        self,
        documents: List[Document],
        queries_per_topic: int = 2
    ) -> List[Tuple[str, List[str]]]:
        """生成带有ground truth的查询

        Args:
            documents: 文档列表
            queries_per_topic: 每个主题的查询数

        Returns:
            [(查询, [相关文档ID列表]), ...]
        """
        logger.debug("生成带 ground truth 的查询")

        # 按主题分组文档
        topic_docs = {}
        for doc in documents:
            topic = doc.metadata.get("topic", "unknown")
            if topic not in topic_docs:
                topic_docs[topic] = []
            topic_docs[topic].append(doc.id)

        queries_with_truth = []
        for topic, doc_ids in topic_docs.items():
            # 为每个主题生成查询
            for _ in range(queries_per_topic):
                query = f"关于{topic}的详细介绍"
                # 该主题的文档都是相关的
                queries_with_truth.append((query, doc_ids))

        logger.debug(f"生成 {len(queries_with_truth)} 个带 ground truth 的查询")
        return queries_with_truth

    def generate_memories(
        self,
        count: int,
        num_users: int = 10,
        time_span_days: int = 30
    ) -> List[Memory]:
        """生成测试记忆数据

        Args:
            count: 记忆总数
            num_users: 用户数量
            time_span_days: 时间跨度（天）

        Returns:
            记忆列表
        """
        logger.debug(f"生成 {count} 条记忆，{num_users} 个用户，跨度 {time_span_days} 天")

        memories = []
        user_ids = [f"user_{i:03d}" for i in range(num_users)]
        base_time = datetime.now() - timedelta(days=time_span_days)

        for i in range(count):
            # 随机选择用户
            user_id = random.choice(user_ids)

            # 随机选择主题和模板
            topic, _ = random.choice(DOCUMENT_TOPICS)
            template, memory_type = random.choice(MEMORY_TEMPLATES)

            # 生成内容
            content = template.format(topic=topic)

            # 随机时间戳
            random_days = random.uniform(0, time_span_days)
            timestamp = base_time + timedelta(days=random_days)

            # 随机会话ID
            session_id = f"session_{random.randint(1, 100):03d}"

            memory = Memory(
                id=f"mem_{i:04d}",
                user_id=user_id,
                content=content,
                session_id=session_id,
                timestamp=timestamp,
                memory_type=memory_type,
                metadata={
                    "topic": topic,
                    "generated": True,
                    "index": i
                }
            )
            memories.append(memory)

        logger.debug(f"生成完成: {len(memories)} 条记忆")
        return memories

    def generate_memory_queries(
        self,
        memories: List[Memory],
        count: int
    ) -> List[Tuple[str, str]]:
        """生成记忆搜索查询

        Args:
            memories: 记忆列表
            count: 查询数量

        Returns:
            [(查询, 用户ID), ...]
        """
        # 获取所有用户
        user_ids = list(set(m.user_id for m in memories))

        queries = []
        for _ in range(count):
            user_id = random.choice(user_ids)
            topic, _ = random.choice(DOCUMENT_TOPICS)
            query = f"关于{topic}的记忆"
            queries.append((query, user_id))

        return queries

    def _expand_content(self, base_content: str, target_length: int, topic: str) -> str:
        """扩展内容到目标长度"""
        content = base_content

        # 添加更多相关内容
        expansions = [
            f"\n\n{topic}是当前人工智能领域的重要研究方向之一。",
            f"在实际应用中，{topic}已经被广泛应用于各个行业。",
            f"学习{topic}需要掌握一定的数学基础和编程能力。",
            f"随着技术的发展，{topic}的应用场景还在不断扩展。",
            f"许多科技公司都在{topic}领域投入了大量研究资源。",
        ]

        while len(content) < target_length:
            expansion = random.choice(expansions)
            content += expansion

        return content[:target_length]

    def _generate_query_variant(self, base_query: str) -> str:
        """生成查询变体"""
        prefixes = ["请问", "我想知道", "能否解释一下", "帮我理解"]
        suffixes = ["", "谢谢", "？", "呢"]

        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)

        # 简化基础查询
        simplified = base_query.rstrip("？?")

        return f"{prefix}{simplified}{suffix}"
