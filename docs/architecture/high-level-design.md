# 高层架构设计

## 1. 系统架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Performance Test Framework                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   CLI/UI    │  │  Benchmark  │  │   Report    │  │   Config    │     │
│  │  Interface  │  │   Runner    │  │  Generator  │  │   Manager   │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │                │             │
│         └────────────────┼────────────────┼────────────────┘             │
│                          │                │                               │
│                          ▼                ▼                               │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                         Core Engine                                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │   Test      │  │   Metrics   │  │   Data      │               │  │
│  │  │ Orchestrator│  │  Collector  │  │   Manager   │               │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
│                                    ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      Adapter Layer (统一接口)                       │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │                                                                     │  │
│  │  Knowledge Base Adapters          Memory System Adapters           │  │
│  │  ┌─────────┐ ┌─────────┐         ┌─────────┐ ┌─────────┐         │  │
│  │  │ AWS     │ │ Google  │         │ AWS     │ │ Google  │         │  │
│  │  │ Bedrock │ │Dialogflow│        │ Bedrock │ │ Vertex  │         │  │
│  │  │   KB    │ │   KB    │         │ Memory  │ │ Memory  │         │  │
│  │  └─────────┘ └─────────┘         └─────────┘ └─────────┘         │  │
│  │  ┌─────────┐ ┌─────────┐         ┌─────────┐ ┌─────────┐         │  │
│  │  │ Volcano │ │ Aliyun  │         │ Volcano │ │ Aliyun  │         │  │
│  │  │ Viking  │ │ Bailian │         │AgentKit │ │ Bailian │         │  │
│  │  └─────────┘ └─────────┘         └─────────┘ └─────────┘         │  │
│  │  ┌─────────┐                     ┌─────────┐                      │  │
│  │  │ Huawei  │                     │  mem0   │                      │  │
│  │  │  CSS    │                     │ (local) │                      │  │
│  │  └─────────┘                     └─────────┘                      │  │
│  │                                                                     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                      │
└────────────────────────────────────┼──────────────────────────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │        Cloud Services          │
                    │   (各云服务商的实际API)          │
                    └────────────────────────────────┘
```

## 2. 核心模块设计

### 2.1 模块职责

| 模块 | 职责 | 关键类/函数 |
|------|------|-------------|
| CLI Interface | 命令行交互，参数解析 | `main.py`, `cli.py` |
| Benchmark Runner | 执行测试套件，控制测试流程 | `BenchmarkRunner` |
| Report Generator | 生成测试报告 | `ReportGenerator` |
| Config Manager | 配置文件加载和管理 | `ConfigManager` |
| Test Orchestrator | 编排测试执行，管理并发 | `TestOrchestrator` |
| Metrics Collector | 收集和聚合性能指标 | `MetricsCollector` |
| Data Manager | 测试数据加载和管理 | `DataManager` |
| Adapters | 各云服务的适配器实现 | `BaseAdapter`, `*Adapter` |

### 2.2 核心流程

```
1. 加载配置 → 2. 初始化适配器 → 3. 准备测试数据 → 4. 执行测试
                                                           │
    ┌──────────────────────────────────────────────────────┘
    │
    ▼
5. 收集指标 → 6. 聚合数据 → 7. 生成报告 → 8. 输出结果
```

## 3. 适配器设计

### 3.1 统一接口定义

```python
# 知识库适配器接口
class KnowledgeBaseAdapter(ABC):
    @abstractmethod
    async def upload_documents(self, documents: List[Document]) -> UploadResult

    @abstractmethod
    async def build_index(self) -> IndexResult

    @abstractmethod
    async def query(self, query: str, top_k: int = 5) -> QueryResult

    @abstractmethod
    async def delete_documents(self, doc_ids: List[str]) -> DeleteResult

# 记忆系统适配器接口
class MemoryAdapter(ABC):
    @abstractmethod
    async def add_memory(self, memory: Memory) -> AddResult

    @abstractmethod
    async def search_memory(self, query: str, user_id: str) -> SearchResult

    @abstractmethod
    async def update_memory(self, memory_id: str, content: str) -> UpdateResult

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> DeleteResult
```

### 3.2 适配器实现清单

| 类型 | 服务 | 适配器类 | SDK/API |
|------|------|----------|---------|
| KB | AWS Bedrock | `AWSBedrockKBAdapter` | boto3 |
| KB | Google Dialogflow | `GoogleDialogflowKBAdapter` | google-cloud-dialogflow |
| KB | 火山引擎Viking | `VolcanoVikingKBAdapter` | volcengine-sdk |
| KB | 阿里云百炼 | `AliyunBailianKBAdapter` | alibabacloud-sdk |
| KB | 华为云CSS | `HuaweiCSSAdapter` | huaweicloud-sdk |
| Memory | AWS Bedrock | `AWSBedrockMemoryAdapter` | boto3 |
| Memory | Google Vertex AI | `GoogleVertexMemoryAdapter` | google-cloud-aiplatform |
| Memory | 火山引擎AgentKit | `VolcanoAgentKitMemoryAdapter` | volcengine-sdk |
| Memory | 阿里云百炼 | `AliyunBailianMemoryAdapter` | alibabacloud-sdk |
| Memory | mem0 | `Mem0Adapter` | mem0 |

## 4. 公共模块复用

### 4.1 认证模块

```python
class AuthManager:
    """统一的认证管理，支持多种认证方式"""
    - API Key 认证
    - OAuth2 认证
    - IAM Role 认证
    - AK/SK 认证
```

### 4.2 错误处理模块

```python
class ErrorHandler:
    """统一的错误处理和重试机制"""
    - 自动重试（指数退避）
    - 错误分类和记录
    - 熔断机制
```

### 4.3 限流模块

```python
class RateLimiter:
    """请求限流，避免触发云服务限制"""
    - 令牌桶算法
    - 支持不同服务的限流配置
```

## 5. 数据流设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        Test Data Flow                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ BEIR     │    │ 数据     │    │ 测试     │    │ 原始     │  │
│  │ Dataset  │───▶│ 预处理   │───▶│ 执行     │───▶│ 结果     │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                        │         │
│                                                        ▼         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ HTML     │◀───│ 报告     │◀───│ 指标     │◀───│ 数据     │  │
│  │ Report   │    │ 生成     │    │ 计算     │    │ 聚合     │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 6. 目录结构

```
cloud-memory-test/
├── docs/
│   ├── requirements/          # 需求文档
│   ├── architecture/          # 架构设计文档
│   └── test-reports/          # 测试报告
├── src/
│   ├── core/                  # 核心引擎
│   │   ├── __init__.py
│   │   ├── orchestrator.py    # 测试编排
│   │   ├── metrics.py         # 指标收集
│   │   └── data_manager.py    # 数据管理
│   ├── adapters/              # 适配器层
│   │   ├── __init__.py
│   │   ├── base.py            # 基类定义
│   │   ├── knowledge_base/    # 知识库适配器
│   │   │   ├── __init__.py
│   │   │   ├── aws_bedrock.py
│   │   │   ├── google_dialogflow.py
│   │   │   ├── volcano_viking.py
│   │   │   ├── aliyun_bailian.py
│   │   │   └── huawei_css.py
│   │   └── memory/            # 记忆系统适配器
│   │       ├── __init__.py
│   │       ├── aws_bedrock.py
│   │       ├── google_vertex.py
│   │       ├── volcano_agentkit.py
│   │       ├── aliyun_bailian.py
│   │       └── mem0_local.py
│   ├── benchmarks/            # 测试套件
│   │   ├── __init__.py
│   │   ├── knowledge_base.py
│   │   └── memory.py
│   ├── utils/                 # 工具模块
│   │   ├── __init__.py
│   │   ├── auth.py            # 认证
│   │   ├── retry.py           # 重试
│   │   ├── rate_limiter.py    # 限流
│   │   └── logger.py          # 日志
│   ├── report/                # 报告生成
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   └── templates/
│   └── main.py                # 入口
├── tests/                     # 单元测试
├── config/
│   ├── config.yaml            # 主配置文件
│   ├── config.example.yaml    # 配置模板
│   └── .gitignore             # 忽略敏感配置
├── scripts/                   # 辅助脚本
├── data/                      # 测试数据
│   ├── beir/
│   └── synthetic/
├── requirements.txt
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

## 7. 技术选型

| 组件 | 技术选择 | 理由 |
|------|----------|------|
| 异步框架 | asyncio + aiohttp | 高并发性能测试必需 |
| 配置管理 | pydantic + yaml | 类型安全，易于验证 |
| CLI框架 | click/typer | 优雅的命令行接口 |
| 图表生成 | plotly/echarts | 交互式可视化 |
| 报告模板 | jinja2 | 灵活的模板引擎 |
| 日志 | loguru | 简洁强大的日志库 |
| 测试 | pytest + pytest-asyncio | 异步测试支持 |

## 8. 扩展性考虑

1. **新增云服务**: 只需实现相应的 Adapter 类
2. **新增测试场景**: 在 benchmarks 模块添加新的测试套件
3. **新增指标**: 扩展 MetricsCollector
4. **新增报告格式**: 扩展 ReportGenerator
