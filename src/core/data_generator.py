"""测试数据生成器"""

import random
import uuid
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
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

# 小学教育相关查询（针对小学考试题文档）
# 使用具体题目关键词以提高检索准确度
ELEMENTARY_QUERIES = [
    # 数学应用题类型
    "行程题怎么做",
    "相向而行的问题",
    "鸡兔同笼问题解法",
    "求面积的方法",
    "水流速度问题",
    "追及问题怎么解",
    "相遇问题的公式",
    "平均速度计算",
    "长方形面积",
    "三角形面积公式",

    # 英语语法相关
    "英语语法规则",
    "动词过去式",
    "一般过去式用法",
    "完形填空技巧",
    "英语阅读理解",
    "英语时态变化",

    # 语文相关
    "古诗文阅读",
    "李白的诗",
    "唐诗鉴赏",
    "文言文翻译",
    "诗歌赏析方法",

    # 其他学科
    "社会主义核心价值观",
    "思想品德题目",
    "科学实验题",
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

    def generate_queries(self, count: int, query_type: str = "default") -> List[str]:
        """生成测试查询

        Args:
            count: 查询数量
            query_type: 查询类型 ("default" 或 "elementary")

        Returns:
            查询列表
        """
        logger.debug(f"生成 {count} 个测试查询 (类型: {query_type})")

        # 选择查询池
        if query_type == "elementary":
            query_pool = ELEMENTARY_QUERIES
        else:
            query_pool = SAMPLE_QUERIES

        queries = []
        for i in range(count):
            # 从预定义查询中选择，或生成变体
            base_query = random.choice(query_pool)

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
        queries_per_topic: int = 2,
        query_type: str = "default"
    ) -> List[Tuple[str, List[str]]]:
        """生成带有ground truth的查询

        Args:
            documents: 文档列表
            queries_per_topic: 每个主题的查询数
            query_type: 查询类型 ("default" 或 "elementary")

        Returns:
            [(查询, [相关文档ID列表]), ...]
        """
        logger.debug(f"生成带 ground truth 的查询 (类型: {query_type})")

        # 按主题分组文档
        topic_docs = {}
        for doc in documents:
            topic = doc.metadata.get("topic", "unknown")
            if topic not in topic_docs:
                topic_docs[topic] = []
            topic_docs[topic].append(doc.id)

        queries_with_truth = []

        if query_type == "elementary":
            # 对于小学教育文档，使用通用查询，不依赖具体主题
            all_doc_ids = [doc.id for doc in documents]
            query_pool = ELEMENTARY_QUERIES

            # 生成多个查询，每个查询都可能匹配所有文档
            num_queries = len(topic_docs) * queries_per_topic
            for i in range(min(num_queries, len(query_pool))):
                query = query_pool[i % len(query_pool)]
                # 所有文档都作为候选
                queries_with_truth.append((query, all_doc_ids))
        else:
            # 默认模式：基于主题生成查询
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

    def load_test_data_documents(self, test_data_dir: str = "test-data") -> Dict[str, str]:
        """从test-data目录加载文档文件名列表

        Args:
            test_data_dir: 测试数据目录路径

        Returns:
            {文档ID: 文件名} 的字典
        """
        doc_map = {}

        # 获取项目根目录
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        test_data_path = project_root / test_data_dir

        if not test_data_path.exists():
            logger.warning(f"测试数据目录不存在: {test_data_path}")
            return doc_map

        # 读取所有文档文件
        for file_path in test_data_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.doc', '.docx', '.pdf', '.txt']:
                # 使用文件名（不含扩展名）作为文档ID的一部分
                file_name = file_path.stem
                # 文档ID需要匹配知识库中的ID格式
                # 不同知识库的ID格式不同，这里先存储文件名
                doc_map[file_name] = file_path.name

        logger.info(f"从 {test_data_path} 加载了 {len(doc_map)} 个文档")
        return doc_map

    def generate_queries_from_test_data(
        self,
        test_data_dir: str = "test-data",
        num_queries: int = 20
    ) -> List[Tuple[str, List[str]]]:
        """从test-data文档生成查询和ground truth

        基于文档文件名中的关键词生成相关查询，并创建查询到文档的映射。

        Args:
            test_data_dir: 测试数据目录
            num_queries: 生成查询数量

        Returns:
            [(查询, [相关文档文件名列表]), ...]
        """
        doc_map = self.load_test_data_documents(test_data_dir)

        if not doc_map:
            logger.warning("未找到测试数据文档，返回空查询列表")
            return []

        # 定义关键词到文档的映射规则
        keyword_patterns = {
            # 数学行程问题
            "行程": ["行程", "速度", "距离", "时间"],
            "相向而行": ["行程", "相遇", "相向"],
            "追及问题": ["行程", "追及"],

            # 数学其他类型
            "鸡兔同笼": ["鸡兔"],
            "面积": ["面积", "几何"],
            "整除": ["整除", "因数", "倍数"],
            "分数": ["分数"],
            "应用题": ["应用"],

            # 年份和考试
            "2009年": ["2009"],
            "2010年": ["2010"],
            "2011年": ["2011"],
            "2012年": ["2012"],
            "小升初": ["小升初"],
            "迎春杯": ["迎春杯"],
            "学而思": ["学而思"],
            "海淀区": ["海淀"],
            "分班考试": ["分班"],

            # 试卷类型
            "试题": ["试题", "试卷"],
            "答案": ["答案"],
            "讲义": ["讲义"],
            "模拟": ["模拟"],
        }

        # 为每个查询关键词找到相关文档
        queries_with_truth = []

        for query_keyword, match_patterns in keyword_patterns.items():
            # 找到文件名中包含任一匹配模式的文档
            relevant_docs = []
            for doc_id, file_name in doc_map.items():
                for pattern in match_patterns:
                    if pattern in file_name:
                        relevant_docs.append(file_name)
                        break

            if relevant_docs:
                # 生成查询
                query = f"{query_keyword}"
                queries_with_truth.append((query, relevant_docs))

        # 打乱顺序并限制数量
        random.shuffle(queries_with_truth)
        queries_with_truth = queries_with_truth[:num_queries]

        logger.info(f"生成 {len(queries_with_truth)} 个基于测试数据的查询")
        for query, docs in queries_with_truth[:3]:
            logger.debug(f"  查询: '{query}' -> {len(docs)} 个相关文档")

        return queries_with_truth
