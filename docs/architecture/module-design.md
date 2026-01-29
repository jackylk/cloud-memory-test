# 模块详细设计

## 1. 适配器基类设计

### 1.1 知识库适配器基类

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

class DocumentFormat(Enum):
    PDF = "pdf"
    TXT = "txt"
    DOCX = "docx"
    HTML = "html"
    MARKDOWN = "md"

@dataclass
class Document:
    id: str
    content: str
    metadata: Dict[str, Any]
    format: DocumentFormat

@dataclass
class QueryResult:
    documents: List[Dict[str, Any]]
    latency_ms: float
    total_tokens: Optional[int] = None

@dataclass
class UploadResult:
    success_count: int
    failed_count: int
    failed_ids: List[str]
    total_time_ms: float

class KnowledgeBaseAdapter(ABC):
    """知识库适配器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """初始化连接和认证"""
        pass

    @abstractmethod
    async def upload_documents(self, documents: List[Document]) -> UploadResult:
        """上传文档"""
        pass

    @abstractmethod
    async def build_index(self) -> Dict[str, Any]:
        """构建/更新索引"""
        pass

    @abstractmethod
    async def query(self, query: str, top_k: int = 5, filters: Optional[Dict] = None) -> QueryResult:
        """执行检索查询"""
        pass

    @abstractmethod
    async def delete_documents(self, doc_ids: List[str]) -> Dict[str, Any]:
        """删除文档"""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        pass

    async def cleanup(self) -> None:
        """清理资源"""
        pass
```

### 1.2 记忆系统适配器基类

```python
@dataclass
class Memory:
    id: Optional[str]
    user_id: str
    session_id: Optional[str]
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
    memory_type: str  # "fact", "preference", "episode"

@dataclass
class MemorySearchResult:
    memories: List[Memory]
    scores: List[float]
    latency_ms: float

class MemoryAdapter(ABC):
    """记忆系统适配器基类"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def initialize(self) -> None:
        """初始化连接"""
        pass

    @abstractmethod
    async def add_memory(self, memory: Memory) -> str:
        """添加记忆，返回记忆ID"""
        pass

    @abstractmethod
    async def add_memories_batch(self, memories: List[Memory]) -> List[str]:
        """批量添加记忆"""
        pass

    @abstractmethod
    async def search_memory(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> MemorySearchResult:
        """搜索相关记忆"""
        pass

    @abstractmethod
    async def update_memory(self, memory_id: str, content: str) -> bool:
        """更新记忆内容"""
        pass

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        pass

    @abstractmethod
    async def get_user_memories(self, user_id: str, limit: int = 100) -> List[Memory]:
        """获取用户所有记忆"""
        pass
```

## 2. 核心引擎模块

### 2.1 测试编排器

```python
class TestOrchestrator:
    """测试执行编排器"""

    def __init__(self, config: Config):
        self.config = config
        self.adapters: Dict[str, BaseAdapter] = {}
        self.metrics_collector = MetricsCollector()

    async def run_benchmark_suite(
        self,
        suite_name: str,
        adapter_names: List[str],
        concurrency_levels: List[int]
    ) -> BenchmarkResults:
        """运行完整的基准测试套件"""
        pass

    async def run_single_test(
        self,
        test_case: TestCase,
        adapter: BaseAdapter
    ) -> TestResult:
        """执行单个测试用例"""
        pass

    async def run_concurrent_test(
        self,
        test_case: TestCase,
        adapter: BaseAdapter,
        concurrency: int,
        duration_seconds: int
    ) -> ConcurrencyTestResult:
        """执行并发测试"""
        pass
```

### 2.2 指标收集器

```python
class MetricsCollector:
    """性能指标收集和计算"""

    def __init__(self):
        self.raw_data: List[MetricPoint] = []

    def record(self, metric_type: str, value: float, labels: Dict[str, str]):
        """记录单个指标点"""
        pass

    def calculate_percentiles(self, metric_type: str) -> Dict[str, float]:
        """计算P50, P95, P99等百分位数"""
        pass

    def calculate_throughput(self, metric_type: str, window_seconds: float) -> float:
        """计算吞吐量"""
        pass

    def calculate_quality_metrics(
        self,
        predictions: List[List[str]],
        ground_truth: List[List[str]]
    ) -> QualityMetrics:
        """计算Precision, Recall, MRR, NDCG等"""
        pass

    def export(self) -> Dict[str, Any]:
        """导出所有指标数据"""
        pass
```

### 2.3 数据管理器

```python
class DataManager:
    """测试数据加载和管理"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    async def load_beir_dataset(self, dataset_name: str, split: str = "test") -> BEIRDataset:
        """加载BEIR基准数据集"""
        pass

    async def generate_synthetic_memories(
        self,
        num_users: int,
        memories_per_user: int,
        time_span_days: int
    ) -> List[Memory]:
        """生成合成记忆数据"""
        pass

    def prepare_documents(
        self,
        raw_data: List[Dict],
        target_format: DocumentFormat
    ) -> List[Document]:
        """准备文档数据"""
        pass
```

## 3. 工具模块

### 3.1 认证管理器

```python
class AuthManager:
    """统一认证管理"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._credentials: Dict[str, Any] = {}

    def get_aws_credentials(self) -> Dict[str, str]:
        """获取AWS凭证"""
        return {
            "aws_access_key_id": self.config.get("aws_access_key_id"),
            "aws_secret_access_key": self.config.get("aws_secret_access_key"),
            "region_name": self.config.get("aws_region", "us-east-1")
        }

    def get_gcp_credentials(self) -> str:
        """获取GCP服务账号JSON路径"""
        return self.config.get("gcp_service_account_json")

    def get_volcengine_credentials(self) -> Dict[str, str]:
        """获取火山引擎凭证"""
        return {
            "access_key": self.config.get("volcengine_access_key"),
            "secret_key": self.config.get("volcengine_secret_key")
        }

    def get_aliyun_credentials(self) -> Dict[str, str]:
        """获取阿里云凭证"""
        return {
            "access_key_id": self.config.get("aliyun_access_key_id"),
            "access_key_secret": self.config.get("aliyun_access_key_secret")
        }

    def get_huawei_credentials(self) -> Dict[str, str]:
        """获取华为云凭证"""
        return {
            "ak": self.config.get("huawei_ak"),
            "sk": self.config.get("huawei_sk")
        }
```

### 3.2 重试机制

```python
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
    )

def with_retry(config: RetryConfig = RetryConfig()):
    """重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        delay = min(
                            config.base_delay * (config.exponential_base ** attempt),
                            config.max_delay
                        )
                        await asyncio.sleep(delay)
            raise last_exception
        return wrapper
    return decorator
```

### 3.3 限流器

```python
class RateLimiter:
    """令牌桶限流器"""

    def __init__(self, rate: float, capacity: float):
        self.rate = rate  # 每秒添加的令牌数
        self.capacity = capacity  # 桶容量
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """获取令牌，返回等待时间"""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0

            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)
            self.tokens = 0
            self.last_update = time.monotonic()
            return wait_time
```

## 4. 报告生成模块

### 4.1 报告生成器

```python
class ReportGenerator:
    """测试报告生成器"""

    def __init__(self, template_dir: str):
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def generate_markdown(self, results: BenchmarkResults, output_path: str):
        """生成Markdown报告"""
        template = self.env.get_template("report.md.j2")
        content = template.render(results=results)
        Path(output_path).write_text(content)

    def generate_html(self, results: BenchmarkResults, output_path: str):
        """生成HTML报告（含图表）"""
        template = self.env.get_template("report.html.j2")
        charts = self._generate_charts(results)
        content = template.render(results=results, charts=charts)
        Path(output_path).write_text(content)

    def _generate_charts(self, results: BenchmarkResults) -> Dict[str, str]:
        """生成图表的HTML/JS代码"""
        charts = {}
        charts["latency_comparison"] = self._latency_chart(results)
        charts["throughput_comparison"] = self._throughput_chart(results)
        charts["quality_comparison"] = self._quality_chart(results)
        charts["cost_comparison"] = self._cost_chart(results)
        return charts
```

## 5. 配置模块

### 5.1 配置结构

```python
from pydantic import BaseModel, SecretStr
from typing import Optional

class AWSConfig(BaseModel):
    access_key_id: SecretStr
    secret_access_key: SecretStr
    region: str = "us-east-1"
    knowledge_base_id: Optional[str] = None

class GCPConfig(BaseModel):
    project_id: str
    service_account_json: str
    location: str = "us-central1"

class VolcanoConfig(BaseModel):
    access_key: SecretStr
    secret_key: SecretStr
    region: str = "cn-beijing"

class AliyunConfig(BaseModel):
    access_key_id: SecretStr
    access_key_secret: SecretStr
    region: str = "cn-hangzhou"

class HuaweiConfig(BaseModel):
    ak: SecretStr
    sk: SecretStr
    region: str = "cn-north-4"

class BenchmarkConfig(BaseModel):
    concurrency_levels: List[int] = [1, 10, 50, 100, 500]
    duration_seconds: int = 60
    warmup_seconds: int = 10
    data_scales: List[str] = ["small", "medium", "large"]

class Config(BaseModel):
    aws: Optional[AWSConfig] = None
    gcp: Optional[GCPConfig] = None
    volcano: Optional[VolcanoConfig] = None
    aliyun: Optional[AliyunConfig] = None
    huawei: Optional[HuaweiConfig] = None
    benchmark: BenchmarkConfig = BenchmarkConfig()
```

## 6. 数据模型

### 6.1 测试结果模型

```python
@dataclass
class LatencyMetrics:
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    mean: float
    min: float
    max: float

@dataclass
class ThroughputMetrics:
    qps: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float

@dataclass
class QualityMetrics:
    precision_at_1: float
    precision_at_5: float
    precision_at_10: float
    recall_at_10: float
    mrr: float
    ndcg_at_10: float

@dataclass
class CostMetrics:
    cost_per_query: float
    storage_cost_per_gb: float
    index_cost: float
    estimated_monthly_cost: float

@dataclass
class TestResult:
    adapter_name: str
    test_case_id: str
    data_scale: str
    concurrency: int
    latency: LatencyMetrics
    throughput: ThroughputMetrics
    quality: Optional[QualityMetrics] = None
    cost: Optional[CostMetrics] = None
    raw_data: List[Dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
```
