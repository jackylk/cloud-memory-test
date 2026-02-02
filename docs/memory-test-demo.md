# 记忆系统测试快速演示

## 演示步骤

### 1. 查看可用的记忆系统适配器

```bash
python -m src list-adapters
```

输出示例：
```
可用的记忆系统适配器:
  - AWSBedrockMemory
  - VolcengineAgentKitMemory
  - AlibabaBailianMemory
```

### 2. 运行记忆系统测试（本地Mock模式）

```bash
# 使用CLI命令
python -m src benchmark -t memory -r
```

或者

```bash
# 使用专用脚本
python test_memory_systems.py
```

### 3. 查看测试结果

测试完成后，在 `docs/test-reports/` 目录下会生成：

```
docs/test-reports/
├── memory_report_20260201_150000.md   # Markdown格式
└── memory_report_20260201_150000.html # HTML格式（含图表）
```

### 4. 报告内容预览

#### Markdown报告示例

```markdown
# 云端记忆系统性能测试报告

**生成时间**: 2026-02-01 15:00:00

## 一、参与对比的记忆系统

- **AWS Bedrock Memory** 是 Amazon Bedrock AgentCore 提供的托管记忆服务
- **火山引擎 AgentKit Memory** 是字节跳动火山引擎提供的 Agent 记忆管理服务
- **阿里云百炼长期记忆** 是阿里云百炼平台提供的记忆节点服务
- **Mem0 (本地)** 是开源的记忆管理框架

### 🏗️ 架构特点对比

| 记忆系统 | 存储方式 | 记忆类型 | 索引方式 | 特点 |
|----------|----------|----------|----------|------|
| AWSBedrockMemory | 托管向量存储 | Events + Insights | 向量索引 | 自动提取长期记忆 |
| VolcengineAgentKitMemory | 火山引擎存储 | 对话记忆 + 长期记忆 | 向量检索 | Agent 工作流集成 |
| AlibabaBailianMemory | 百炼平台存储 | 记忆节点 | 图谱 + 向量 | 支持记忆关联 |
| Mem0LocalAdapter | 本地向量库 | 统一记忆 | Embedding检索 | 开源可定制 |

## 二、测试方法

### 测试数据
- **记忆条目数**: 100 条
- **模拟用户数**: 10 个
- **记忆类型**: 用户偏好、对话记录、学习进度等

### 测试流程
1. **记忆添加**: 批量添加测试记忆数据
2. **记忆搜索**: 执行查询测试，评估检索性能
3. **性能指标**: 记录延迟、吞吐量、成功率

## 三、对比结果

### 时延对比

| 记忆系统 | P50 (ms) | P95 (ms) | P99 (ms) | 平均 (ms) |
|----------|----------|----------|----------|-----------|
| AWSBedrockMemory | 45.23 | 89.45 | 125.67 | 52.34 |
| VolcengineAgentKitMemory | 38.12 | 76.89 | 98.45 | 43.21 |
| AlibabaBailianMemory | 52.34 | 102.45 | 145.67 | 61.23 |
| Mem0LocalAdapter | 12.45 | 25.67 | 34.89 | 15.23 |

### 吞吐对比

| 记忆系统 | QPS | 总请求数 | 成功率 |
|----------|-----|----------|--------|
| AWSBedrockMemory | 18.5 | 1000 | 99.8% |
| VolcengineAgentKitMemory | 22.3 | 1000 | 99.5% |
| AlibabaBailianMemory | 16.2 | 1000 | 98.9% |
| Mem0LocalAdapter | 65.7 | 1000 | 100.0% |

### 成本对比（估算）

| 记忆系统 | 月度成本估算 | 计费方式 | 备注 |
|----------|--------------|----------|------|
| AWSBedrockMemory | $50-100/月 | 按记忆存储和查询计费 | 支持长期记忆自动提取 |
| VolcengineAgentKitMemory | ¥200-400/月 | 按Agent调用次数 | 包含在Agent费用中 |
| AlibabaBailianMemory | ¥150-300/月 | 按记忆节点数 | 支持记忆关联查询 |
| Mem0LocalAdapter | 自托管成本 | 服务器 + 存储 | 开源免费，需自行维护 |

### 🏆 综合评分对比

| 记忆系统 | 性能得分 | 成本得分 | 易用性 | 综合评分 | 推荐场景 |
|----------|----------|----------|--------|----------|----------|
| AWSBedrockMemory | 4/5 | 3/5 | 5/5 | 4/5 | AWS 生态 |
| VolcengineAgentKitMemory | 5/5 | 4/5 | 4/5 | 4/5 | 国内中文场景 |
| AlibabaBailianMemory | 3/5 | 4/5 | 4/5 | 4/5 | 阿里云生态 |
| Mem0LocalAdapter | 5/5 | 5/5 | 3/5 | 4/5 | 自托管/开源 |

## 四、选型建议

### 🎯 AWS Bedrock Memory

**适合场景**:
- 使用 AWS 云服务的企业
- 需要自动提取长期记忆 (Insights)
- 对托管服务有强需求

**优势**: 托管服务、与 Bedrock Agent 集成、自动记忆管理

**劣势**: 成本相对较高、需要 AWS 账号

### 🎯 火山引擎 AgentKit Memory

**适合场景**:
- 国内企业，中文应用场景
- 需要与火山引擎 Agent 工作流集成
- 对中文记忆检索有较高要求

**优势**: 国内服务、中文优化、Agent 工作流集成

**劣势**: 需要火山引擎账号、文档相对较少

### 🎯 阿里云百炼长期记忆

**适合场景**:
- 使用阿里云生态的企业
- 需要记忆关联和图谱能力
- 国内中文场景

**优势**: 阿里云生态、支持记忆关联、中文优化

**劣势**: 需要阿里云账号、API 限流较严格

### 🎯 Mem0 (本地开源)

**适合场景**:
- 需要完全控制数据的企业
- 开发测试环境
- 对成本敏感的项目

**优势**: 开源免费、数据自主、高度可定制

**劣势**: 需要自行维护、缺少托管服务的便利性

---

*本报告由云端记忆系统性能测试框架自动生成*
```

## 常用命令参考

```bash
# 1. 查看配置
python -m src info

# 2. 列出所有适配器
python -m src list-adapters

# 3. 快速测试记忆系统
python -m src test-adapter memory

# 4. 运行完整测试并生成报告
python -m src benchmark -t memory -r

# 5. 指定不同数据规模
python -m src benchmark -t memory -s tiny -r    # 100条记忆
python -m src benchmark -t memory -s small -r   # 1000条记忆
python -m src benchmark -t memory -s medium -r  # 10000条记忆

# 6. 只生成报告（从已有结果）
python -m src report memory_results.json -o docs/test-reports/

# 7. 对比所有记忆系统
python -m src compare -t memory -s tiny -q 20

# 8. 使用专用测试脚本
python test_memory_systems.py
```

## 配置提示

如果你只是想测试功能而不连接真实云服务，可以使用Mock模式：

1. 不配置云服务凭证
2. 系统会自动启用Mock模式
3. Mock模式会模拟API响应，用于功能验证

要测试真实云服务，需要在 `config/config.yaml` 中配置对应的云服务凭证。

## 下一步

1. 查看生成的HTML报告（在浏览器中打开）
2. 根据测试结果进行技术选型
3. 调整数据规模进行更大规模的测试
4. 使用压力测试评估系统极限
