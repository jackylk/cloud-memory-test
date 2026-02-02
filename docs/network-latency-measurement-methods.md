# 云服务网络延迟测量方案

## 🎯 目标

准确测量从本地到不同云服务的网络往返时间（RTT），以便从端到端延迟中分离出服务端处理时间。

## 📊 测量策略

### 通用原则

网络延迟 = TCP连接时间 + DNS解析时间 + 数据传输时间

我们通过轻量级请求测量完整的网络RTT：
```
网络RTT = 请求发送 → 网络传输 → 服务器接收 → 最小处理 → 响应返回 → 网络传输 → 客户端接收
```

## 🔧 针对不同云服务的实现

### 1. AWS Bedrock (us-east-1)

**测量方法：** 使用最小查询（1个结果）

```python
async def measure_network_latency(self, num_samples: int = 10):
    """AWS: 使用返回1个结果的最小查询"""
    latencies = []
    for _ in range(num_samples):
        start = time.time()
        try:
            # 最小化查询：只返回1个结果
            self._client.retrieve(
                knowledgeBaseId=self._knowledge_base_id,
                retrievalQuery={"text": "test"},  # 最短查询
                retrievalConfiguration={
                    "vectorSearchConfiguration": {
                        "numberOfResults": 1  # 最少结果
                    }
                }
            )
        except:
            pass
        elapsed_ms = (time.time() - start) * 1000
        latencies.append(elapsed_ms)
```

**网络组成：**
- DNS解析（首次）：~20ms
- TCP+SSL握手：~40-60ms（美国东部→中国）
- 数据传输：~10-20ms
- 服务端处理：~10-30ms（最小查询）
- **总计：~80-130ms**

### 2. 阿里云百炼 (cn-beijing)

**测量方法：** 使用最小参数的检索

```python
async def measure_network_latency(self, num_samples: int = 10):
    """阿里云: 使用最小参数检索"""
    latencies = []
    for _ in range(num_samples):
        start = time.time()
        try:
            retrieve_request = RetrieveRequest(
                query="test",  # 最短查询
                index_id=self._index_id,
                dense_similarity_top_k=1,  # 最少召回
                sparse_similarity_top_k=1,
                enable_reranking=False,  # 关闭重排序
                rerank_top_n=1
            )
            self._client.retrieve_with_options(
                self._workspace_id,
                retrieve_request,
                {},
                runtime
            )
        except:
            pass
        elapsed_ms = (time.time() - start) * 1000
        latencies.append(elapsed_ms)
```

**网络组成：**
- TCP+SSL握手：~15-30ms（北京）
- 数据传输：~5-10ms
- 服务端处理：~30-50ms（最小检索）
- **总计：~50-90ms**

### 3. 火山引擎 VikingDB (cn-beijing)

**测量方法：** 使用单向量搜索

```python
async def measure_network_latency(self, num_samples: int = 10):
    """火山引擎: 使用最小搜索"""
    latencies = []
    for _ in range(num_samples):
        start = time.time()
        try:
            # 最简单的搜索
            search_params = {
                "limit": 1,  # 只返回1个结果
                "dense_weight": 1.0
            }
            self._collection.search_by_text(
                text="test",
                **search_params
            )
        except:
            pass
        elapsed_ms = (time.time() - start) * 1000
        latencies.append(elapsed_ms)
```

**网络组成：**
- TCP+SSL握手：~15-30ms
- 数据传输：~5-10ms
- 服务端处理：~20-40ms
- **总计：~40-80ms**

### 4. 本地 Milvus/Mem0

**测量方法：** 本地连接测试

```python
async def measure_network_latency(self, num_samples: int = 10):
    """本地服务: 进程通信时间"""
    latencies = []
    for _ in range(num_samples):
        start = time.time()
        try:
            # 本地健康检查或最小查询
            self.health_check()
        except:
            pass
        elapsed_ms = (time.time() - start) * 1000
        latencies.append(elapsed_ms)
```

**网络组成：**
- 本地回环：~0.1-1ms
- 进程通信：~0.5-2ms
- **总计：~0.5-3ms**（几乎可以忽略）

## 📈 实际测量结果示例

### 测试输出格式

```
>>> 步骤1: 初始化适配器 <<<
适配器: AlibabaBailian
测量网络基线延迟...
  采样 10 次...
网络基线: P50=75.23ms, P95=92.45ms, Mean=78.12ms

>>> 步骤4: 执行查询测试 <<<
查询 1: '什么是机器学习...' → 3 结果, 485.67ms

>>> 步骤5: 收集指标 <<<
端到端延迟: P50=485.67ms, P95=723.45ms, Mean=512.34ms
网络基线: P50=75.23ms
估算服务端时延: P50=410.44ms, P95=648.22ms, Mean=437.11ms
```

### 延迟分解表

| 云服务 | 端到端P50 | 网络基线 | 服务端时延 | 计算方式 |
|--------|-----------|----------|-----------|---------|
| AWS Bedrock | 180ms | 95ms | 85ms | 180-95 |
| 阿里云百炼 | 500ms | 75ms | 425ms | 500-75 |
| 火山引擎 | 350ms | 60ms | 290ms | 350-60 |
| 本地Milvus | 8ms | 1ms | 7ms | 8-1 |

## 🎯 提高测量准确性的方法

### 1. 增加采样次数

```python
# 从默认10次增加到50次
network_latency = await adapter.measure_network_latency(num_samples=50)
```

### 2. 预热连接

```python
# 在测量前先预热连接，避免首次连接的开销
await adapter.health_check()  # 预热
await adapter.measure_network_latency()  # 真实测量
```

### 3. 使用专用的延迟测量API

某些云服务提供延迟测量API：

**AWS CloudWatch**
```python
# 查询CloudWatch指标获取区域延迟
cloudwatch.get_metric_statistics(
    Namespace='AWS/Bedrock',
    MetricName='Latency',
    ...
)
```

**阿里云云监控**
```python
# 查询云监控API
cms.describe_metric_list(
    Namespace='acs_bailian',
    MetricName='RequestLatency',
    ...
)
```

### 4. 使用PING测试（如果支持）

```python
import subprocess

def ping_host(host: str, count: int = 10) -> float:
    """Ping测试（仅限支持ICMP的服务）"""
    result = subprocess.run(
        ['ping', '-c', str(count), host],
        capture_output=True,
        text=True
    )
    # 解析平均延迟
    # 注意：很多云服务不响应PING
```

## ⚠️ 注意事项

### 1. 网络波动

网络延迟会随时间波动，建议：
- 增加采样次数（50-100次）
- 在不同时段多次测试
- 使用P50而不是平均值（更稳定）

### 2. 服务端最小处理时间

即使是"轻量级"请求，服务端也需要：
- 解析请求：1-5ms
- 认证：5-10ms
- 最小查询：10-50ms
- 构建响应：1-5ms

因此网络基线测量会包含10-70ms的服务端开销。

### 3. 冷启动效应

第一次请求可能包含：
- DNS解析：10-50ms
- TCP连接建立：1-2个RTT
- SSL握手：2-4个RTT
- 认证token获取：50-200ms

建议在测量前进行预热。

### 4. CDN和边缘节点

某些云服务使用CDN或边缘节点：
- 可能导致网络延迟非常低
- 但实际查询可能需要回源
- 网络基线可能低估实际网络开销

## 📊 改进建议

### 1. 分离不同类型的延迟

```python
latency_breakdown = {
    "dns_resolution": 5ms,      # DNS解析
    "tcp_handshake": 30ms,      # TCP握手
    "ssl_handshake": 40ms,      # SSL握手
    "request_transfer": 10ms,   # 请求传输
    "server_processing": 200ms, # 服务端处理
    "response_transfer": 15ms,  # 响应传输
}
```

### 2. 使用traceroute分析网络路径

```python
import subprocess

def trace_route(host: str):
    """分析网络路径和每跳延迟"""
    result = subprocess.run(
        ['traceroute', host],
        capture_output=True,
        text=True
    )
    # 分析每一跳的延迟
```

### 3. 使用专门的网络测量工具

```bash
# MTR (My Traceroute) - 持续测量
mtr --report --report-cycles 100 api.bedrock.us-east-1.amazonaws.com

# 输出每跳的延迟和丢包率
```

## 🎓 最佳实践

1. **测试前预热连接**
   ```python
   await adapter.initialize()
   await adapter.health_check()  # 预热
   await adapter.measure_network_latency()
   ```

2. **在稳定网络环境中测试**
   - 避免WiFi、移动网络
   - 使用有线网络
   - 避免网络高峰期

3. **多次测试取中位数**
   ```python
   results = []
   for _ in range(5):
       latency = await adapter.measure_network_latency(num_samples=20)
       results.append(latency['p50'])

   median_baseline = sorted(results)[len(results)//2]
   ```

4. **记录测试环境**
   - 本地网络：带宽、ISP、位置
   - 云服务区域：us-east-1、cn-beijing等
   - 测试时间：避免峰值时段

5. **使用地理位置接近的区域**
   - 中国用户：优先选择cn-beijing、cn-shanghai
   - 海外用户：选择就近的AWS区域
