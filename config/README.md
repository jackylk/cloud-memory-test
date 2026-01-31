# 配置文件说明

## 配置文件位置

`config/config.yaml` - 主配置文件，填入您的云服务凭证

> **安全提示**: `config.yaml` 已在 `.gitignore` 中，不会被提交到 Git。请妥善保管您的凭证。

## 快速开始

编辑 `config/config.yaml`，取消注释并填入您要测试的云服务凭证：

```yaml
# 示例：配置 AWS
aws:
  region: "ap-southeast-1"
  access_key_id: "YOUR_ACCESS_KEY"          # 取消注释并填入
  secret_access_key: "YOUR_SECRET_KEY"      # 取消注释并填入
```

## 各云服务配置说明

### AWS Bedrock

```yaml
aws:
  region: "ap-southeast-1"
  # Bedrock Knowledge Base ID（可选）
  knowledge_base_id: "YOUR_KB_ID"
  # Bedrock Memory ID（可选）
  memory_id: "YOUR_MEMORY_ID"
  # 凭证（可选，优先使用 ~/.aws/credentials）
  access_key_id: "YOUR_ACCESS_KEY"
  secret_access_key: "YOUR_SECRET_KEY"
```

**说明**:
- 凭证可通过 AWS CLI 配置: `aws configure`
- 也可直接在配置文件中填写
- 不填写 KB/Memory ID 将使用 Mock 模式

### OpenSearch Serverless

```yaml
opensearch:
  region: "ap-southeast-1"
  host: "xxxxx.ap-southeast-1.aoss.amazonaws.com"  # OpenSearch 端点
  index_name: "benchmark-test-index"
  # 使用 AWS 凭证（同上）
```

**说明**:
- 需要先在 AWS Console 创建 OpenSearch Serverless 集合
- 配置数据访问策略允许读写权限

### Google Cloud

```yaml
gcp:
  project_id: "your-project-id"
  location: "us-central1"
  # Dialogflow CX
  agent_id: "YOUR_AGENT_ID"
  data_store_id: "YOUR_DATA_STORE_ID"
  # Vertex AI Memory Bank
  memory_bank_id: "YOUR_MEMORY_BANK_ID"
  # 服务账号密钥
  service_account_json: "/path/to/service-account.json"
```

**说明**:
- 下载服务账号密钥 JSON 文件
- 确保服务账号有相应的 IAM 权限

### 火山引擎

```yaml
volcengine:
  region: "cn-beijing"
  # VikingDB 知识库
  collection_name: "your-collection"
  host: "api-knowledgebase.mlp.cn-beijing.volces.com"
  # AgentKit Memory
  agent_id: "YOUR_AGENT_ID"
  # 凭证
  access_key: "YOUR_ACCESS_KEY"
  secret_key: "YOUR_SECRET_KEY"
```

### 阿里云百炼

```yaml
aliyun:
  region: "cn-beijing"
  workspace_id: "YOUR_WORKSPACE_ID"
  index_id: "YOUR_INDEX_ID"
  memory_id_for_longterm: "YOUR_MEMORY_ID"
  access_key_id: "YOUR_ACCESS_KEY_ID"
  access_key_secret: "YOUR_ACCESS_KEY_SECRET"
```

### 华为云 CSS

```yaml
huawei:
  region: "cn-north-4"
  cluster_id: "YOUR_CLUSTER_ID"
  endpoint: "https://your-css-endpoint.com"
  index_name: "benchmark-index"
  es_username: "YOUR_USERNAME"
  es_password: "YOUR_PASSWORD"
  ak: "YOUR_AK"
  sk: "YOUR_SK"
```

## Mock 模式

**未填写凭证的云服务会自动运行在 Mock 模式**，使用本地 TF-IDF 模拟行为，无需真实云服务即可测试框架功能。

### 如何判断是否在 Mock 模式？

运行测试时查看日志：
```
INFO | AWSBedrockKB: 初始化 Mock 模式
```

或运行：
```bash
python -m src list-adapters
```

## 验证配置

检查配置是否正确加载：

```bash
python -m src info
```

查看可用的适配器：

```bash
python -m src list-adapters
```

## 安全最佳实践

1. **不要在配置文件中硬编码凭证**（推荐使用各云服务的 CLI 工具配置）
2. **使用环境变量**: 支持从环境变量读取凭证
3. **权限最小化**: 只给测试账号必需的权限
4. **定期轮换**: 定期更换访问密钥

## 常见问题

### Q: 我可以只测试部分云服务吗？

A: 可以，只填写您要测试的云服务凭证，其他服务会自动运行在 Mock 模式。

### Q: 如何使用环境变量？

A: 设置环境变量后，配置文件中可不填写凭证：

```bash
# AWS
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# GCP
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

### Q: 测试会产生费用吗？

A:
- **Mock 模式**: 完全免费，无云服务调用
- **真实模式**: 会调用云服务 API，产生少量费用
- **建议**: 先用 tiny 规模测试，费用通常在几分钱以内

## 更多帮助

查看完整文档: `docs/README.md`
