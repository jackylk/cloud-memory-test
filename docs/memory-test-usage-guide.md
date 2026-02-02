# 记忆系统测试使用指南

本指南介绍如何使用云端记忆系统性能测试工具，包括资源管理、测试执行和报告生成。

## 目录

- [快速开始](#快速开始)
- [云资源管理](#云资源管理)
- [运行测试](#运行测试)
- [配置说明](#配置说明)
- [测试报告](#测试报告)
- [常见问题](#常见问题)

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置云服务凭证

编辑 `config/config.yaml`，添加您的云服务凭证：

```yaml
# AWS Bedrock Memory
aws:
  region: "us-east-1"
  # access_key_id: "YOUR_AWS_ACCESS_KEY"
  # secret_access_key: "YOUR_AWS_SECRET_KEY"
  # memory_id: "YOUR_MEMORY_ID"  # 需要先创建

# 火山引擎 AgentKit Memory
volcengine:
  region: "cn-beijing"
  access_key: "YOUR_ACCESS_KEY"
  secret_key: "YOUR_SECRET_KEY"
  # agent_id: "YOUR_AGENT_ID"  # 需要先创建

# 阿里云百炼长期记忆
aliyun:
  workspace_id: "YOUR_WORKSPACE_ID"
  access_key_id: "YOUR_ACCESS_KEY_ID"
  access_key_secret: "YOUR_ACCESS_KEY_SECRET"
  # memory_id_for_longterm: "YOUR_MEMORY_ID"  # 需要先创建
```

### 3. 查看可用资源

```bash
# 列出所有云资源
python -m src cloud-resources

# 查看详细信息
python -m src cloud-resources -v
```

### 4. 运行测试

```bash
# 快速测试（tiny规模）
python test_memory_systems.py

# 指定数据规模
python test_memory_systems.py --scale small

# 仅测试特定适配器
python test_memory_systems.py --adapters aws aliyun
```

## 云资源管理

### 列出所有资源

```bash
# 简洁模式
python -m src cloud-resources

# 详细模式（显示配置、创建时间等）
python -m src cloud-resources -v
```

### 查看资源详情

```bash
python -m src cloud-resources -a info -p volcengine -r collection-name
```

输出示例：
```
资源详情:
  云服务: volcengine
  类型: knowledge_base
  名称: test-kb
  资源ID: test-kb-collection
  状态: active
  区域: cn-beijing
  创建时间: 2026-01-15 10:30:00
```

### 创建资源

#### 创建火山引擎VikingDB知识库

```bash
python -m src cloud-resources \
  -a create \
  -p volcengine \
  -t kb \
  -n test-kb-benchmark
```

#### 创建阿里云百炼记忆库

```bash
python -m src cloud-resources \
  -a create \
  -p aliyun \
  -t memory \
  -n test-memory-benchmark
```

创建成功后，工具会提示您将资源ID添加到配置文件：

```
✓ 请将资源ID添加到 config/config.yaml 中:
  aliyun:
    memory_id_for_longterm: "memory-xxx"
```

#### AWS Bedrock Memory

AWS Bedrock Memory需要在AWS控制台手动创建：

1. 访问 AWS Console → Bedrock → Agents → Memory
2. 创建新的Memory实例
3. 将 Memory ID 添加到配置文件：

```yaml
aws:
  memory_id: "YOUR_MEMORY_ID"
```

#### 火山引擎 AgentKit Memory

火山引擎 AgentKit Memory需要在控制台手动创建：

1. 访问火山引擎控制台 → AgentKit
2. 创建Agent实例
3. 将 Agent ID 添加到配置文件：

```yaml
volcengine:
  agent_id: "YOUR_AGENT_ID"
```

### 删除资源

```bash
# 删除指定资源（需要确认）
python -m src cloud-resources \
  -a delete \
  -p volcengine \
  -r collection-name \
  --confirm

# 清理所有资源（危险操作！）
python -m src cloud-resources \
  -a cleanup \
  --confirm
```

## 运行测试

### 基本用法

```bash
# 使用默认设置（tiny规模，所有适配器）
python test_memory_systems.py

# 指定数据规模
python test_memory_systems.py --scale small

# 跳过本地适配器
python test_memory_systems.py --skip-local

# 仅测试特定适配器
python test_memory_systems.py --adapters aws volcengine

# 详细输出
python test_memory_systems.py -v
```

### 数据规模说明

| 规模 | 用户数 | 记忆数 | 查询数 | 适用场景 |
|------|--------|--------|--------|----------|
| tiny | 10 | 20 | 5 | 快速测试、开发调试 |
| small | 50 | 100 | 20 | 功能验证 |
| medium | 100 | 500 | 50 | 性能对比 |

### 使用CLI命令

也可以通过主CLI运行测试：

```bash
# 仅测试记忆系统
python -m src benchmark -t memory -s tiny -r

# 知识库和记忆系统都测试
python -m src benchmark -t all -s small -r
```

## 配置说明

### 完整配置示例

```yaml
mode: "cloud"  # 运行模式: local / cloud

# AWS配置
aws:
  region: "us-east-1"
  memory_id: "abcd1234"  # Bedrock Memory ID
  access_key_id: "YOUR_KEY"  # 可选，优先使用环境变量
  secret_access_key: "YOUR_SECRET"

# 火山引擎配置
volcengine:
  region: "cn-beijing"
  access_key: "YOUR_KEY"
  secret_key: "YOUR_SECRET"
  agent_id: "agent-xxx"  # AgentKit Agent ID

# 阿里云配置
aliyun:
  region: "cn-beijing"
  workspace_id: "llm-xxx"
  memory_id_for_longterm: "memory-xxx"
  access_key_id: "YOUR_KEY"
  access_key_secret: "YOUR_SECRET"

# 本地适配器配置
local:
  mem0:
    vector_store: "chromadb"
    use_simple_store: true  # 简化模式，无需复杂配置
```

### 环境变量

支持通过环境变量配置凭证：

```bash
# AWS
export AWS_ACCESS_KEY_ID="YOUR_KEY"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET"
export AWS_DEFAULT_REGION="us-east-1"

# 火山引擎
export VOLCENGINE_ACCESS_KEY="YOUR_KEY"
export VOLCENGINE_SECRET_KEY="YOUR_SECRET"

# 阿里云
export ALIBABA_CLOUD_ACCESS_KEY_ID="YOUR_KEY"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="YOUR_SECRET"
```

## 测试报告

### 报告格式

测试完成后会自动生成两种格式的报告：

1. **Markdown报告** (`.md`)：适合版本控制和快速查看
2. **HTML报告** (`.html`)：包含图表，适合浏览器查看

报告默认保存在 `docs/test-reports/` 目录。

### 报告内容

- **测试配置**：数据规模、测试时间、参与系统
- **性能指标**：
  - 延迟分布（P50, P90, P95, P99）
  - 吞吐量（QPS）
  - 成功率
- **性能对比图表**：
  - 延迟对比柱状图
  - 吞吐量对比
- **详细数据**：每个系统的具体测试结果

### 查看报告

```bash
# Markdown报告
cat docs/test-reports/memory_report_*.md

# HTML报告（在浏览器中打开）
open docs/test-reports/memory_report_*.html
```

## 常见问题

### 1. Mock模式是什么？

当某个云服务未配置凭证或资源ID时，适配器会自动进入Mock模式，使用本地存储模拟API行为。这适用于：

- 开发和调试
- 在没有云服务凭证时测试代码逻辑
- 对比本地和云端性能

测试输出中会显示：`⚠ XXX 运行在 Mock 模式`

### 2. 如何切换到真实模式？

确保配置文件中包含：

1. **云服务凭证**（access_key等）
2. **资源ID**（memory_id、agent_id等）

如果资源不存在，使用 `cloud-resources` 命令创建。

### 3. 测试失败怎么办？

常见原因：

- **凭证错误**：检查配置文件中的凭证是否正确
- **资源不存在**：使用 `cloud-resources` 查看资源状态
- **网络问题**：检查网络连接，尝试使用代理
- **限流**：云服务API有速率限制，可以降低并发或增加延迟

使用 `-v` 参数查看详细错误信息：

```bash
python test_memory_systems.py -v
```

### 4. 如何只测试某一个系统？

```bash
# 仅测试AWS
python test_memory_systems.py --adapters aws

# 测试AWS和阿里云
python test_memory_systems.py --adapters aws aliyun
```

### 5. 如何解读测试结果？

关键指标：

- **P50延迟**：50%的请求完成时间，代表典型性能
- **P95延迟**：95%的请求完成时间，代表大部分用户体验
- **QPS**：每秒查询数，越高越好
- **成功率**：应该接近100%

性能对比：

- 延迟越低越好（<100ms为优秀，<500ms为良好）
- QPS越高越好
- 注意Mock模式的结果仅供参考，真实性能需要看真实模式

### 6. 测试会产生费用吗？

会产生少量费用：

- **存储费用**：记忆数据存储（通常很低）
- **API调用费用**：测试期间的API调用
- **数据传输费用**：上传/下载数据

建议：

- 使用 `tiny` 规模进行初步测试
- 测试完成后及时删除不需要的资源
- 定期检查云服务账单

### 7. 如何自定义测试数据？

修改 `config/config.yaml` 中的数据规模配置：

```yaml
data:
  tiny:
    memories_count: 20  # 记忆数量
  small:
    memories_count: 100
  medium:
    memories_count: 500
```

## 进阶使用

### 批量测试多个规模

```bash
for scale in tiny small medium; do
  echo "Testing scale: $scale"
  python test_memory_systems.py --scale $scale
done
```

### 定时测试

```bash
# 添加到crontab，每天凌晨2点运行
0 2 * * * cd /path/to/project && python test_memory_systems.py --scale small
```

### 性能基准追踪

```bash
# 保存结果到带日期的文件
python test_memory_systems.py \
  --scale small \
  --output-dir docs/test-reports/$(date +%Y%m%d)
```

## 支持与反馈

如有问题或建议，请：

1. 查看 `docs/` 目录下的其他文档
2. 查看项目 Issues
3. 联系开发团队

## 相关文档

- [项目README](../README.md)
- [架构设计](architecture/)
- [知识库测试指南](knowledge-base-test-guide.md)
- [API文档](api-documentation.md)
