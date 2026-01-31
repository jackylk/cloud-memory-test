# AWS Bedrock Knowledge Base - Aurora PostgreSQL 存储后端需求文档

## 1. 需求概述

### 1.1 背景
AWS Bedrock Knowledge Base 支持多种向量存储后端。当前测试框架已实现基于 OpenSearch Serverless 的知识库，本需求旨在扩展支持基于 Aurora PostgreSQL 的知识库测试。

### 1.2 目标
- 对比 OpenSearch Serverless 和 Aurora PostgreSQL 两种存储后端的性能差异
- 评估 Aurora PostgreSQL + pgvector 在知识库场景的适用性
- 为技术选型提供数据支持

## 2. 技术方案

### 2.1 Aurora PostgreSQL Serverless 架构

```
┌─────────────────────────────────────────────┐
│     AWS Bedrock Knowledge Base (Aurora)     │
├─────────────────────────────────────────────┤
│                                              │
│  ┌─────────────┐     ┌──────────────────┐  │
│  │   S3 Data   │────▶│  Titan Embed v2  │  │
│  │   Source    │     │  (1024 dims)     │  │
│  └─────────────┘     └─────────┬──────────┘  │
│                               │             │
│                               ▼             │
│  ┌──────────────────────────────────────┐  │
│  │  Aurora PostgreSQL Serverless v2    │  │
│  │  + pgvector Extension               │  │
│  │                                      │  │
│  │  - 向量索引: HNSW/IVFFlat           │  │
│  │  - 存储: RDS Storage                │  │
│  │  - 扩缩容: 0.5-128 ACU              │  │
│  └──────────────────────────────────────┘  │
│                                              │
└─────────────────────────────────────────────┘
```

### 2.2 与 OpenSearch Serverless 对比

| 对比项 | OpenSearch Serverless | Aurora PostgreSQL + pgvector |
|--------|----------------------|----------------------------|
| **向量索引** | k-NN plugin | pgvector (HNSW/IVFFlat) |
| **扩展性** | 自动扩展 | Serverless v2: 0.5-128 ACU |
| **定价模式** | 按 OCU (搜索+索引) | 按 ACU (计算) + Storage |
| **查询性能** | 优化搜索场景 | 通用数据库 + 向量扩展 |
| **管理复杂度** | 低（全托管） | 中（需配置 VPC/安全组） |
| **SQL 支持** | 有限 | 完整 PostgreSQL SQL |
| **事务支持** | 否 | ACID 事务 |
| **数据一致性** | 最终一致 | 强一致性 |

### 2.3 技术栈

**必需组件**：
1. **Aurora PostgreSQL Serverless v2**
   - 版本：15.x （支持 pgvector 0.5.0+）
   - 扩展：pgvector
   - 配置：Multi-AZ for HA

2. **网络配置**
   - VPC with 2+ subnets
   - DB Subnet Group
   - Security Group (PostgreSQL 5432)
   - Internet Gateway (for public access)

3. **IAM 权限**
   - Bedrock 访问 RDS 的角色
   - RDS Data API 启用（可选）
   - Secret Manager 存储凭证

4. **Bedrock Configuration**
   - Embedding Model: amazon.titan-embed-text-v2:0 (1024维)
   - Vector Field: bedrock-knowledge-base-vector
   - Metadata Field: AMAZON_BEDROCK_METADATA

## 3. 功能需求

### 3.1 基础功能

**FR-1: Aurora 集群创建**
- 支持通过 API 自动创建 Aurora PostgreSQL Serverless v2 集群
- 配置 pgvector 扩展
- 创建向量表和索引

**FR-2: Knowledge Base 创建**
- 使用 Aurora 作为存储后端
- 配置 S3 数据源
- 支持文档摄取和向量化

**FR-3: 检索测试**
- 支持相同的查询接口
- 测量查询延迟、吞吐量
- 评估检索质量

### 3.2 性能测试

**FR-4: 对比测试**
- 使用相同的测试数据集
- 相同的查询集合
- 对比两种后端的性能指标

**FR-5: 成本分析**
- 记录资源使用情况
- 估算两种方案的成本差异

## 4. 非功能需求

### 4.1 性能要求
- P95 延迟 < 500ms （相同数据规模）
- 支持并发查询
- 索引构建时间可接受

### 4.2 可靠性要求
- 集群可用性 > 99.9%
- 支持自动故障转移
- 数据持久性保证

### 4.3 安全要求
- VPC 隔离
- 加密传输 (SSL/TLS)
- 加密存储（可选）
- IAM 认证

## 5. 测试场景

### 5.1 基准测试场景

**场景 1：小规模测试 (Tiny)**
- 文档数：10
- 查询数：5
- 目标：验证功能正确性

**场景 2：中等规模测试 (Small)**
- 文档数：100
- 查询数：20
- 目标：性能对比

**场景 3：大规模测试 (Medium)**
- 文档数：1000
- 查询数：50
- 目标：扩展性评估

### 5.2 对比测试指标

| 指标类别 | 具体指标 | OpenSearch | Aurora PG |
|---------|----------|------------|-----------|
| **延迟** | P50 | ? | ? |
| | P95 | ? | ? |
| | P99 | ? | ? |
| **吞吐** | QPS | ? | ? |
| **质量** | Precision@1 | ? | ? |
| | MRR | ? | ? |
| | NDCG@10 | ? | ? |
| **成本** | 每月估算 | ? | ? |

## 6. 实施计划

### 6.1 第一阶段：基础设施准备
- [x] 创建 VPC 和子网（需要权限）
- [ ] 创建 Aurora PostgreSQL Serverless 集群
- [ ] 配置 pgvector 扩展
- [ ] 配置安全组和网络访问

### 6.2 第二阶段：Knowledge Base 配置
- [ ] 创建 IAM 角色
- [ ] 创建 Bedrock KB (Aurora 后端)
- [ ] 配置 S3 数据源
- [ ] 触发文档摄取

### 6.3 第三阶段：测试执行
- [ ] 运行基准测试
- [ ] 收集性能数据
- [ ] 生成对比报告

### 6.4 第四阶段：分析和优化
- [ ] 分析性能差异
- [ ] 成本对比分析
- [ ] 提出优化建议

## 7. 风险和限制

### 7.1 技术风险
- **VPC 配置复杂度**：需要正确配置网络
- **权限限制**：需要足够的 IAM 权限
- **pgvector 版本兼容性**：确保 Aurora 版本支持

### 7.2 成本风险
- **Aurora Serverless 成本**：可能高于 OpenSearch
- **存储成本**：RDS 存储单独计费
- **数据传输成本**：跨 AZ 传输费用

### 7.3 当前限制
- 用户 IAM 缺少 EC2/VPC 创建权限
- 需要手动在控制台创建 Aurora 集群
- 测试需要额外的权限配置

## 8. 替代方案

### 8.1 手动创建 Aurora 集群
如果 API 创建受限，可以：
1. 在 AWS Console 手动创建集群
2. 提供集群信息给测试框架
3. 框架仅负责测试执行

### 8.2 使用 RDS Proxy
通过 RDS Proxy 简化连接管理：
- 连接池管理
- 自动故障转移
- IAM 认证集成

### 8.3 仅文档化对比
如果无法创建实际资源：
- 基于 AWS 文档进行理论对比
- 引用已有的性能基准测试
- 提供决策建议

## 9. 成功标准

- ✅ 成功创建 Aurora PostgreSQL 知识库
- ✅ 完成端到端的文档摄取和查询测试
- ✅ 生成详细的性能对比报告
- ✅ 提供清晰的技术选型建议

## 10. 参考资料

- [AWS Bedrock Knowledge Base Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [Aurora PostgreSQL pgvector](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraPostgreSQL.VectorDB.html)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [OpenSearch Serverless](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless.html)

---

**文档版本**: 1.0
**创建日期**: 2026-01-31
**最后更新**: 2026-01-31
**状态**: 待实施（受权限限制）
