# 云资源管理指南

## 概述

本框架提供了 `cloud-resources` 命令来管理云端知识库和记忆库资源，帮助您：
- 查看所有创建的云资源
- 创建测试用的知识库/记忆库
- 删除不再使用的资源，避免产生费用

## 快速开始

### 1. 查看所有云资源

```bash
python -m src cloud-resources
```

### 2. 创建知识库资源

```bash
# 火山引擎 VikingDB
python -m src cloud-resources -a create -p volcengine -t kb -n test-kb

# 阿里云百炼
python -m src cloud-resources -a create -p aliyun -t kb -n test-kb

# Google Dialogflow CX
python -m src cloud-resources -a create -p gcp -t kb -n test-agent
```

### 3. 删除资源

```bash
python -m src cloud-resources -a delete -p volcengine -r collection-name --confirm
```

### 4. 清理所有资源

```bash
python -m src cloud-resources -a cleanup --confirm
```

## 手动创建资源指南

如果自动创建遇到问题，您可以在各云服务控制台手动创建资源，然后在配置文件中填入资源ID。

### 火山引擎 VikingDB

1. **创建知识库**:
   - 登录火山引擎控制台
   - 进入 VikingDB 服务
   - 创建集合(Collection)
   - 记录集合名称

2. **配置**:
   ```yaml
   volcengine:
     collection_name: "your-collection-name"
     access_key: "YOUR_AK"
     secret_key: "YOUR_SK"
   ```

3. **测试**:
   ```bash
   python -m src benchmark -s tiny -t kb
   ```

### 阿里云百炼

1. **创建工作空间和知识库**:
   - 登录阿里云控制台
   - 进入百炼服务
   - 创建工作空间(Workspace)
   - 在工作空间中创建索引(Index)
   - 记录 workspace_id 和 index_id

2. **配置**:
   ```yaml
   aliyun:
     workspace_id: "YOUR_WORKSPACE_ID"
     index_id: "YOUR_INDEX_ID"
     access_key_id: "YOUR_AK"
     access_key_secret: "YOUR_SK"
   ```

3. **创建长期记忆**（可选）:
   - 在百炼控制台创建长期记忆
   - 记录 memory_id
   ```yaml
   aliyun:
     memory_id_for_longterm: "YOUR_MEMORY_ID"
   ```

### Google Cloud Platform

1. **创建 Dialogflow CX Agent**:
   - 登录 GCP Console
   - 进入 Dialogflow CX
   - 创建新 Agent
   - 创建 Data Store（用于知识库）
   - 记录 Agent ID 和 Data Store ID

2. **配置**:
   ```yaml
   gcp:
     project_id: "your-project-id"
     agent_id: "YOUR_AGENT_ID"
     data_store_id: "YOUR_DATA_STORE_ID"
     service_account_json: "/path/to/service-account.json"
   ```

3. **本地认证**（如已使用 gcloud init）:
   ```bash
   gcloud auth application-default login
   ```

## 资源费用说明

### 火山引擎 VikingDB
- **存储费用**: 按数据量计费
- **查询费用**: 按查询次数计费
- **建议**: tiny规模测试费用 < ¥1/天

### 阿里云百炼
- **工作空间**: 免费
- **知识库**: 按存储和调用量计费
- **建议**: tiny规模测试费用 < ¥1/天

### Google Cloud
- **Dialogflow CX**: 按会话计费
- **免费额度**: 每月前100个会话免费
- **建议**: tiny规模测试通常在免费额度内

## 成本优化建议

1. **及时清理**: 测试完成后立即删除资源
   ```bash
   python -m src cloud-resources -a cleanup --confirm
   ```

2. **使用 Mock 模式**: 开发时使用 Mock 模式，无需真实云服务
   ```bash
   # 在 config.yaml 中注释掉资源ID即可自动切换到 Mock 模式
   # knowledge_base_id: "xxx"  # 注释掉
   ```

3. **选择性测试**: 只测试需要对比的云服务
   ```bash
   # 只测试火山引擎
   python -m src benchmark -s tiny -t kb
   ```

4. **定期检查**: 使用 cloud-resources 命令定期检查资源
   ```bash
   python -m src cloud-resources
   ```

## 常见问题

### Q: 为什么看不到某个云服务的资源？

A: 可能原因：
1. 该云服务的SDK未安装
2. 凭证配置不正确
3. API权限不足

解决方法：
```bash
# 检查SDK
pip list | grep -E "volcengine|alibabacloud|google-cloud"

# 安装缺失的SDK
pip install volcengine-python-sdk  # 火山引擎（如需要）
pip install alibabacloud-bailian20231229  # 阿里云
pip install google-cloud-dialogflow-cx  # Google Cloud
```

### Q: 自动创建资源失败怎么办？

A: 建议手动在控制台创建资源，然后在配置文件中填入资源ID。这样更稳定可靠。

### Q: 如何确保不会产生意外费用？

A:
1. 每次测试后运行 `python -m src cloud-resources` 检查资源
2. 及时删除不需要的资源
3. 设置云服务的费用预警
4. 优先使用各云服务的免费额度

## 命令参考

### 列出资源
```bash
python -m src cloud-resources
python -m src cloud-resources -a list
```

### 创建资源
```bash
python -m src cloud-resources -a create \
  -p <provider> \
  -t <kb|memory> \
  -n <resource-name>
```

### 删除资源
```bash
python -m src cloud-resources -a delete \
  -p <provider> \
  -r <resource-id> \
  --confirm
```

### 清理所有资源
```bash
python -m src cloud-resources -a cleanup --confirm
```

## 下一步

1. 在各云服务控制台创建必要的资源
2. 在 `config/config.yaml` 中填入资源ID
3. 运行测试验证配置
   ```bash
   python -m src list-adapters
   python -m src benchmark -s tiny -t all
   ```
4. 查看生成的测试报告
   ```bash
   ls docs/test-reports/
   ```
