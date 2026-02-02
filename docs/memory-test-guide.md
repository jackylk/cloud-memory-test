# 记忆系统性能测试指南

本文档说明如何运行云端记忆系统的性能测试并生成独立的测试报告。

## 测试目标

对比以下4个记忆系统的性能：

1. **AWS Bedrock Memory** - AWS托管记忆服务
2. **火山引擎 AgentKit Memory** - 字节跳动的Agent记忆服务
3. **阿里云百炼长期记忆** - 阿里云的记忆节点服务
4. **Mem0 (本地)** - 开源记忆框架作为对比基准

## 快速开始

### 方式一：使用CLI命令（推荐）

```bash
# 测试记忆系统并生成独立报告
python -m src benchmark -t memory -r

# 指定数据规模
python -m src benchmark -t memory -s tiny -r    # 100条记忆，10个用户
python -m src benchmark -t memory -s small -r   # 1000条记忆，50个用户
```

### 方式二：使用专用测试脚本

```bash
# 运行所有记忆系统测试
python test_memory_systems.py
```

## 配置要求

### 本地测试（Mem0）

无需特殊配置，直接运行即可。

### 云服务测试

需要在 `config/config.yaml` 中配置对应的云服务凭证：

#### AWS Bedrock Memory

```yaml
aws:
  region: us-east-1
  access_key_id: YOUR_ACCESS_KEY
  secret_access_key: YOUR_SECRET_KEY
  memory_id: YOUR_MEMORY_ID  # 可选，不配置则使用Mock模式
```

#### 火山引擎 AgentKit Memory

```yaml
volcengine:
  region: cn-beijing
  access_key: YOUR_ACCESS_KEY
  secret_key: YOUR_SECRET_KEY
  agent_id: YOUR_AGENT_ID  # 可选，不配置则使用Mock模式
```

#### 阿里云百炼长期记忆

```yaml
aliyun:
  workspace_id: YOUR_WORKSPACE_ID
  memory_id_for_longterm: YOUR_MEMORY_ID
  access_key_id: YOUR_ACCESS_KEY
  access_key_secret: YOUR_ACCESS_KEY_SECRET
  endpoint: bailian.cn-beijing.aliyuncs.com
```

## 测试内容

### 测试数据

- **记忆条目**：100-1000条（根据规模）
- **模拟用户**：10-50个（根据规模）
- **记忆类型**：用户偏好、对话记录、学习进度等

### 测试流程

1. **记忆添加**：批量添加测试记忆数据
2. **记忆搜索**：执行多轮查询测试
3. **性能指标**：记录延迟、吞吐量、成功率

### 评估维度

- **延迟指标**：P50/P95/P99 响应时间
- **吞吐指标**：QPS (每秒查询数)
- **可靠性**：请求成功率
- **成本估算**：月度使用成本对比

## 测试报告

测试完成后会在 `docs/test-reports/` 目录生成：

- `memory_report_YYYYMMDD_HHMMSS.md` - Markdown格式报告
- `memory_report_YYYYMMDD_HHMMSS.html` - HTML格式报告（含图表）

### 报告内容

1. **参与对比的记忆系统**
   - 各系统介绍
   - 架构特点对比

2. **测试方法说明**
   - 测试数据规模
   - 测试流程
   - 评估维度

3. **对比结果**
   - 延迟对比表格
   - 吞吐对比表格
   - 成本对比表格
   - 综合评分对比

4. **选型建议**
   - 各系统适合的场景
   - 优势与劣势分析

## 数据规模说明

| 规模 | 记忆条目数 | 用户数 | 查询数 | 适用场景 |
|------|-----------|--------|--------|----------|
| tiny | 100 | 10 | 50 | 快速测试 |
| small | 1000 | 50 | 200 | 中等规模 |
| medium | 10000 | 100 | 500 | 大规模 |

## 常见问题

### 1. 某个云服务测试失败怎么办？

如果未配置某个云服务的凭证，系统会自动启用Mock模式进行模拟测试。Mock模式只用于验证功能，不代表真实性能。

### 2. 测试耗时多久？

- tiny规模：约5-10分钟
- small规模：约15-30分钟
- medium规模：约30-60分钟

### 3. 可以只测试部分系统吗？

可以，在 `test_memory_systems.py` 中注释掉不需要测试的适配器即可。

### 4. 如何对比知识库和记忆系统？

知识库和记忆系统会生成独立的测试报告：
- 知识库报告：`kb_report_*.md/html`
- 记忆系统报告：`memory_report_*.md/html`

## 示例命令

```bash
# 1. 快速测试所有记忆系统（本地 + 云服务）
python -m src benchmark -t memory -r

# 2. 只测试本地Mem0（用于开发调试）
# 修改 benchmark.py 的 get_adapters() 方法，只返回 Mem0LocalAdapter

# 3. 对比测试（生成性能对比表）
python -m src compare -t memory -s tiny -q 20

# 4. 压力测试
python -m src stress-test -t memory -c 1,5,10,20 -d 30

# 5. 查看已配置的适配器
python -m src list-adapters
```

## 相关文档

- [架构设计](docs/architecture/high-level-design.md)
- [知识库测试指南](docs/requirements/test-scenarios.md)
- [云服务配置](config/README.md)
