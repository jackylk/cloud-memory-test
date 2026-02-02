"""配置管理"""

from pathlib import Path
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, SecretStr, Field
import yaml


class DebugConfig(BaseModel):
    """调试配置"""
    verbose: bool = False
    log_level: str = "INFO"
    print_results: bool = True
    save_raw_data: bool = False


class TinyDataConfig(BaseModel):
    """微型数据集配置（调试用）"""
    doc_count: int = 10
    queries_count: int = 5
    memories_count: int = 20


class SmallDataConfig(BaseModel):
    """小规模数据集配置"""
    doc_count: int = 100
    queries_count: int = 50
    memories_count: int = 100


class MediumDataConfig(BaseModel):
    """中规模数据集配置"""
    doc_count: int = 1000
    queries_count: int = 200
    memories_count: int = 1000


class LargeDataConfig(BaseModel):
    """大规模数据集配置"""
    doc_count: int = 10000
    queries_count: int = 500
    memories_count: int = 10000


class DataConfig(BaseModel):
    """数据配置"""
    scale: Literal["tiny", "small", "medium", "large"] = "tiny"
    query_type: Literal["default", "elementary"] = "default"  # 查询类型
    tiny: TinyDataConfig = Field(default_factory=TinyDataConfig)
    small: SmallDataConfig = Field(default_factory=SmallDataConfig)
    medium: MediumDataConfig = Field(default_factory=MediumDataConfig)
    large: LargeDataConfig = Field(default_factory=LargeDataConfig)

    def get_current_scale(self) -> TinyDataConfig | SmallDataConfig | MediumDataConfig | LargeDataConfig:
        """获取当前规模配置"""
        return getattr(self, self.scale)


class ChromaDBConfig(BaseModel):
    """ChromaDB 本地配置"""
    persist_directory: Optional[str] = None  # None = in-memory
    embedding_model: str = "all-MiniLM-L6-v2"
    collection_name: str = "test_collection"


class Mem0LocalConfig(BaseModel):
    """mem0 本地配置"""
    vector_store: str = "chroma"
    embedding_model: str = "all-MiniLM-L6-v2"


class LocalConfig(BaseModel):
    """本地模式配置"""
    chromadb: ChromaDBConfig = Field(default_factory=ChromaDBConfig)
    mem0: Mem0LocalConfig = Field(default_factory=Mem0LocalConfig)


class AWSConfig(BaseModel):
    """AWS 配置"""
    access_key_id: Optional[SecretStr] = None
    secret_access_key: Optional[SecretStr] = None
    region: str = "us-east-1"
    knowledge_base_id: Optional[str] = None
    knowledge_base_id_aurora: Optional[str] = None
    memory_id: Optional[str] = None


class GCPConfig(BaseModel):
    """GCP 配置"""
    project_id: Optional[str] = None
    service_account_json: Optional[str] = None
    location: str = "us-central1"


class VolcengineConfig(BaseModel):
    """火山引擎配置"""
    access_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None
    region: str = "cn-beijing"
    collection_name: Optional[str] = None
    host: str = "api-knowledgebase.mlp.cn-beijing.volces.com"
    dense_weight: float = 0.5
    rerank_switch: bool = True
    rerank_model: str = "m3-v2-rerank"


class AliyunConfig(BaseModel):
    """阿里云配置"""
    access_key_id: Optional[SecretStr] = None
    access_key_secret: Optional[SecretStr] = None
    region: str = "cn-hangzhou"
    workspace_id: Optional[str] = None
    index_id: Optional[str] = None
    endpoint: str = "bailian.cn-beijing.aliyuncs.com"
    dense_similarity_top_k: int = 100
    sparse_similarity_top_k: int = 100
    enable_reranking: bool = True
    rerank_top_n: int = 5
    rerank_min_score: float = 0.01
    # 记忆系统配置
    memory_id_for_longterm: Optional[str] = None
    agent_id: Optional[str] = None


class HuaweiConfig(BaseModel):
    """华为云配置"""
    ak: Optional[SecretStr] = None
    sk: Optional[SecretStr] = None
    region: str = "cn-north-4"


class OpenSearchConfig(BaseModel):
    """OpenSearch Serverless 配置"""
    host: Optional[str] = None
    region: str = "ap-southeast-1"
    index_name: str = "benchmark-test-index"
    embedding_model: str = "all-MiniLM-L6-v2"
    dimension: int = 384


class BenchmarkConfig(BaseModel):
    """基准测试配置"""
    concurrency_levels: list[int] = [1, 10, 50, 100]
    duration_seconds: int = 60
    warmup_seconds: int = 10


class ReportConfig(BaseModel):
    """报告配置"""
    output_dir: str = "docs/test-reports"
    formats: list[str] = ["markdown", "html"]
    include_raw_data: bool = False


class Config(BaseModel):
    """主配置"""
    mode: Literal["local", "cloud", "hybrid"] = "local"
    debug: DebugConfig = Field(default_factory=DebugConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    local: LocalConfig = Field(default_factory=LocalConfig)
    aws: AWSConfig = Field(default_factory=AWSConfig)
    gcp: GCPConfig = Field(default_factory=GCPConfig)
    volcengine: VolcengineConfig = Field(default_factory=VolcengineConfig)
    aliyun: AliyunConfig = Field(default_factory=AliyunConfig)
    huawei: HuaweiConfig = Field(default_factory=HuaweiConfig)
    opensearch: OpenSearchConfig = Field(default_factory=OpenSearchConfig)
    benchmark: BenchmarkConfig = Field(default_factory=BenchmarkConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)


def load_config(config_path: Optional[str] = None) -> Config:
    """加载配置文件"""
    if config_path is None:
        # 默认配置路径
        default_paths = [
            Path("config/config.yaml"),
            Path("config/config.local.yaml"),
        ]
        for path in default_paths:
            if path.exists():
                config_path = str(path)
                break

    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return Config(**data)

    # 返回默认配置
    return Config()


def save_config_template(output_path: str = "config/config.example.yaml"):
    """保存配置模板"""
    config = Config()
    # 转换为字典并移除敏感信息的实际值
    data = config.model_dump()

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
