# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

云端Agent知识库和记忆系统性能测试框架，用于对比评估多个云服务商的知识库和记忆系统性能。

## 测试目标系统

**知识库**: AWS Bedrock KB, Google Dialogflow KB, 火山引擎Viking, 阿里云百炼, 华为云CSS

**记忆系统**: AWS Bedrock Memory, Google Vertex AI Memory, 火山引擎AgentKit, 阿里云百炼长期记忆, mem0(本地)

## 项目结构

```
docs/requirements/     # 需求分析文档
docs/architecture/     # 架构设计文档
docs/test-reports/     # 测试报告输出
src/
  core/                # 核心引擎
    benchmark_runner.py  # 基准测试运行器
    data_generator.py    # 测试数据生成
    metrics.py           # 指标收集计算
    orchestrator.py      # 测试编排器
  adapters/            # 云服务适配器层
    base.py              # 适配器基类
    knowledge_base/      # 知识库适配器
      simple_vector_store.py  # TF-IDF向量存储
      milvus_local.py    # Milvus向量数据库
      pinecone_adapter.py # Pinecone适配器
    memory/              # 记忆系统适配器
      mem0_local.py      # 本地mem0
      milvus_memory.py   # Milvus记忆存储
  benchmarks/          # 基准测试套件
    knowledge_base.py    # 知识库测试套件
    memory.py            # 记忆系统测试套件
    suites.py            # 组合测试套件
  utils/               # 工具模块
    config.py            # 配置管理
    logger.py            # 日志(含StepLogger)
    retry.py             # 重试机制
    rate_limiter.py      # 限流器
    auth.py              # 认证管理
  benchmark.py         # CLI入口
config/                # 配置文件(敏感信息不提交)
tests/                 # 单元测试
```

## 开发命令

```bash
# 安装依赖
pip install -r requirements.txt
pip install "pymilvus[milvus_lite]"  # Milvus 本地支持

# 列出可用适配器
python -m src list-adapters

# 快速测试适配器
python -m src test-adapter kb      # 测试知识库适配器
python -m src test-adapter memory  # 测试记忆适配器

# 运行基准测试
python -m src benchmark -s tiny -t all     # tiny规模,全部测试
python -m src benchmark -s small -t kb     # small规模,仅知识库
python -m src benchmark -s tiny -t memory  # tiny规模,仅记忆

# 运行预定义测试套件
python -m src run-suite --suite quick   # 快速测试
python -m src run-suite --suite full    # 完整测试
python -m src run-suite --suite stress  # 压力测试

# 对比所有适配器性能
python -m src compare -t kb -s tiny -q 10    # 知识库对比
python -m src compare -t memory -s tiny      # 记忆系统对比

# 运行压力测试
python -m src stress-test -t kb -c 1,10,50 -d 30

# 运行基准测试并自动生成报告
python -m src benchmark -s tiny -r

# 使用详细输出
python -m src -v benchmark -s tiny

# 输出结果到文件
python -m src benchmark -s tiny -o results.json

# 从已有结果生成报告
python -m src report results.json -o docs/test-reports/

# 查看配置
python -m src info

# 运行单元测试
pytest tests/ -v
pytest tests/test_adapters.py -v
```

## 运行模式

- **local**: 使用本地ChromaDB和mem0进行调试（当前默认）
- **cloud**: 使用云服务（待实现）
- **hybrid**: 混合模式

## 架构要点

1. **适配器模式**: 所有服务通过 `KnowledgeBaseAdapter` 和 `MemoryAdapter` 接口访问
2. **异步设计**: 使用 asyncio 支持高并发测试
3. **步骤日志**: `StepLogger` 提供清晰的测试步骤输出，便于调试
4. **指标收集**: `MetricsCollector` 统一收集延迟、吞吐、质量指标

## 配置文件

- `config/config.local.yaml` - 本地开发配置
- `config/config.example.yaml` - 配置模板（含云服务配置项）

## 添加新适配器

1. 在 `src/adapters/knowledge_base/` 或 `src/adapters/memory/` 创建新文件
2. 继承 `KnowledgeBaseAdapter` 或 `MemoryAdapter` 基类
3. 实现所有抽象方法
4. 在 `src/benchmark.py` 的 `get_adapters()` 函数中注册
5. 在对应的 `__init__.py` 中导出
