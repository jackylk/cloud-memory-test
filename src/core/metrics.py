"""性能指标收集和计算"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import defaultdict
import numpy as np
from loguru import logger


@dataclass
class LatencyMetrics:
    """延迟指标"""
    p50: float  # 中位数
    p75: float
    p90: float
    p95: float
    p99: float
    mean: float
    min: float
    max: float
    std: float
    count: int

    def to_dict(self) -> Dict[str, float]:
        return {
            "p50_ms": round(self.p50, 2),
            "p75_ms": round(self.p75, 2),
            "p90_ms": round(self.p90, 2),
            "p95_ms": round(self.p95, 2),
            "p99_ms": round(self.p99, 2),
            "mean_ms": round(self.mean, 2),
            "min_ms": round(self.min, 2),
            "max_ms": round(self.max, 2),
            "std_ms": round(self.std, 2),
            "count": self.count,
        }

    def __str__(self) -> str:
        return (
            f"P50={self.p50:.2f}ms | P95={self.p95:.2f}ms | "
            f"P99={self.p99:.2f}ms | Mean={self.mean:.2f}ms"
        )


@dataclass
class ThroughputMetrics:
    """吞吐量指标"""
    qps: float  # 每秒查询数
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    duration_seconds: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "qps": round(self.qps, 2),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate": round(self.error_rate * 100, 2),
            "duration_seconds": round(self.duration_seconds, 2),
        }

    def __str__(self) -> str:
        return (
            f"QPS={self.qps:.2f} | Total={self.total_requests} | "
            f"Success={self.successful_requests} | ErrorRate={self.error_rate*100:.2f}%"
        )


@dataclass
class QualityMetrics:
    """检索质量指标"""
    precision_at_1: float
    precision_at_5: float
    precision_at_10: float
    recall_at_10: float
    mrr: float  # Mean Reciprocal Rank
    ndcg_at_10: float  # Normalized Discounted Cumulative Gain

    def to_dict(self) -> Dict[str, float]:
        return {
            "precision@1": round(self.precision_at_1, 4),
            "precision@5": round(self.precision_at_5, 4),
            "precision@10": round(self.precision_at_10, 4),
            "recall@10": round(self.recall_at_10, 4),
            "mrr": round(self.mrr, 4),
            "ndcg@10": round(self.ndcg_at_10, 4),
        }

    def __str__(self) -> str:
        return (
            f"P@1={self.precision_at_1:.4f} | P@5={self.precision_at_5:.4f} | "
            f"MRR={self.mrr:.4f} | NDCG@10={self.ndcg_at_10:.4f}"
        )


@dataclass
class CostMetrics:
    """成本指标"""
    cost_per_query: float  # 每次查询成本（美元）
    storage_cost_per_gb: float  # 每GB存储成本（美元/月）
    index_cost: float  # 索引构建成本（美元）
    estimated_monthly_cost: float  # 预估月度成本（美元）
    currency: str = "USD"

    # 额外的成本细节
    api_calls: int = 0
    data_transfer_gb: float = 0.0
    compute_hours: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost_per_query": round(self.cost_per_query, 6),
            "storage_cost_per_gb": round(self.storage_cost_per_gb, 4),
            "index_cost": round(self.index_cost, 4),
            "estimated_monthly_cost": round(self.estimated_monthly_cost, 2),
            "currency": self.currency,
            "api_calls": self.api_calls,
            "data_transfer_gb": round(self.data_transfer_gb, 4),
            "compute_hours": round(self.compute_hours, 4),
        }

    def __str__(self) -> str:
        return (
            f"PerQuery=${self.cost_per_query:.6f} | "
            f"Storage=${self.storage_cost_per_gb:.4f}/GB | "
            f"Monthly=${self.estimated_monthly_cost:.2f}"
        )

    @classmethod
    def estimate_from_usage(
        cls,
        num_queries: int,
        storage_gb: float,
        pricing: Dict[str, float],
    ) -> "CostMetrics":
        """从使用量估算成本

        Args:
            num_queries: 查询次数
            storage_gb: 存储量（GB）
            pricing: 定价信息 {
                "per_query": 每次查询价格,
                "storage_per_gb": 每GB存储价格,
                "index_per_gb": 每GB索引价格,
            }

        Returns:
            成本指标
        """
        per_query = pricing.get("per_query", 0.0)
        storage_per_gb = pricing.get("storage_per_gb", 0.0)
        index_per_gb = pricing.get("index_per_gb", 0.0)

        query_cost = num_queries * per_query
        storage_cost = storage_gb * storage_per_gb
        index_cost = storage_gb * index_per_gb

        # 估算月度成本（假设每天查询量相同）
        daily_queries = num_queries
        monthly_query_cost = daily_queries * 30 * per_query
        monthly_total = monthly_query_cost + storage_cost

        return cls(
            cost_per_query=per_query,
            storage_cost_per_gb=storage_per_gb,
            index_cost=index_cost,
            estimated_monthly_cost=monthly_total,
            api_calls=num_queries,
        )


# 各云服务的定价信息（示例，需要根据实际更新）
CLOUD_PRICING = {
    "aws_bedrock_kb": {
        "per_query": 0.001,  # 每次检索
        "storage_per_gb": 0.023,  # S3 存储
        "index_per_gb": 0.05,  # 向量索引
    },
    "gcp_vertex": {
        "per_query": 0.0015,
        "storage_per_gb": 0.02,
        "index_per_gb": 0.04,
    },
    "aliyun_bailian": {
        "per_query": 0.006,  # 约0.04元人民币
        "storage_per_gb": 0.015,
        "index_per_gb": 0.03,
    },
    "volcengine_viking": {
        "per_query": 0.005,
        "storage_per_gb": 0.012,
        "index_per_gb": 0.025,
    },
    "local_milvus": {
        "per_query": 0.0,  # 本地免费
        "storage_per_gb": 0.0,
        "index_per_gb": 0.0,
    },
    "local_pinecone_mock": {
        "per_query": 0.0,
        "storage_per_gb": 0.0,
        "index_per_gb": 0.0,
    },
}


def estimate_cost(
    service_name: str,
    num_queries: int,
    storage_gb: float,
) -> CostMetrics:
    """估算服务成本

    Args:
        service_name: 服务名称
        num_queries: 查询次数
        storage_gb: 存储量（GB）

    Returns:
        成本指标
    """
    pricing = CLOUD_PRICING.get(service_name, {
        "per_query": 0.001,
        "storage_per_gb": 0.02,
        "index_per_gb": 0.04,
    })
    return CostMetrics.estimate_from_usage(num_queries, storage_gb, pricing)


@dataclass
class MetricPoint:
    """单个指标点"""
    metric_type: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    success: bool = True


class MetricsCollector:
    """性能指标收集器"""

    def __init__(self):
        self._data: Dict[str, List[MetricPoint]] = defaultdict(list)
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None

    def start(self):
        """开始收集"""
        self._start_time = time.time()
        logger.debug("指标收集开始")

    def stop(self):
        """停止收集"""
        self._end_time = time.time()
        logger.debug("指标收集结束")

    def record(
        self,
        metric_type: str,
        value: float,
        labels: Dict[str, str] = None,
        success: bool = True
    ):
        """记录单个指标点"""
        point = MetricPoint(
            metric_type=metric_type,
            value=value,
            timestamp=time.time(),
            labels=labels or {},
            success=success
        )
        self._data[metric_type].append(point)

    def record_latency(self, operation: str, latency_ms: float, success: bool = True):
        """记录延迟"""
        self.record(
            metric_type=f"latency_{operation}",
            value=latency_ms,
            labels={"operation": operation},
            success=success
        )

    def calculate_latency_metrics(self, metric_type: str = None) -> LatencyMetrics:
        """计算延迟指标"""
        if metric_type:
            points = self._data.get(metric_type, [])
        else:
            # 合并所有延迟指标
            points = []
            for key, values in self._data.items():
                if key.startswith("latency_"):
                    points.extend(values)

        if not points:
            return LatencyMetrics(
                p50=0, p75=0, p90=0, p95=0, p99=0,
                mean=0, min=0, max=0, std=0, count=0
            )

        # 只计算成功的请求
        latencies = [p.value for p in points if p.success]

        if not latencies:
            return LatencyMetrics(
                p50=0, p75=0, p90=0, p95=0, p99=0,
                mean=0, min=0, max=0, std=0, count=0
            )

        arr = np.array(latencies)

        return LatencyMetrics(
            p50=float(np.percentile(arr, 50)),
            p75=float(np.percentile(arr, 75)),
            p90=float(np.percentile(arr, 90)),
            p95=float(np.percentile(arr, 95)),
            p99=float(np.percentile(arr, 99)),
            mean=float(np.mean(arr)),
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            std=float(np.std(arr)),
            count=len(latencies)
        )

    def calculate_throughput_metrics(self, metric_type: str = None) -> ThroughputMetrics:
        """计算吞吐量指标"""
        if metric_type:
            points = self._data.get(metric_type, [])
        else:
            # 合并所有延迟指标
            points = []
            for key, values in self._data.items():
                if key.startswith("latency_"):
                    points.extend(values)

        if not points:
            return ThroughputMetrics(
                qps=0, total_requests=0, successful_requests=0,
                failed_requests=0, error_rate=0, duration_seconds=0
            )

        total = len(points)
        successful = sum(1 for p in points if p.success)
        failed = total - successful

        # 计算时间跨度
        if self._start_time and self._end_time:
            duration = self._end_time - self._start_time
        elif points:
            timestamps = [p.timestamp for p in points]
            duration = max(timestamps) - min(timestamps)
            if duration == 0:
                duration = 1  # 避免除零
        else:
            duration = 1

        qps = total / duration if duration > 0 else 0
        error_rate = failed / total if total > 0 else 0

        return ThroughputMetrics(
            qps=qps,
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            error_rate=error_rate,
            duration_seconds=duration
        )

    def calculate_quality_metrics(
        self,
        predictions: List[List[str]],
        ground_truth: List[List[str]],
        k_values: List[int] = [1, 5, 10]
    ) -> QualityMetrics:
        """计算检索质量指标

        Args:
            predictions: 每个查询返回的文档ID列表
            ground_truth: 每个查询的相关文档ID列表
            k_values: 计算 Precision@K 的K值

        Returns:
            质量指标
        """
        if not predictions or not ground_truth:
            return QualityMetrics(
                precision_at_1=0, precision_at_5=0, precision_at_10=0,
                recall_at_10=0, mrr=0, ndcg_at_10=0
            )

        n_queries = len(predictions)

        # Precision@K
        def precision_at_k(preds: List[str], truth: List[str], k: int) -> float:
            if not preds or not truth:
                return 0.0
            preds_k = preds[:k]
            relevant = sum(1 for p in preds_k if p in truth)
            return relevant / k

        # Recall@K
        def recall_at_k(preds: List[str], truth: List[str], k: int) -> float:
            if not truth:
                return 0.0
            preds_k = preds[:k]
            relevant = sum(1 for p in preds_k if p in truth)
            return relevant / len(truth)

        # MRR (Mean Reciprocal Rank)
        def reciprocal_rank(preds: List[str], truth: List[str]) -> float:
            for i, p in enumerate(preds):
                if p in truth:
                    return 1.0 / (i + 1)
            return 0.0

        # NDCG@K
        def ndcg_at_k(preds: List[str], truth: List[str], k: int) -> float:
            def dcg(relevances: List[int], k: int) -> float:
                return sum(
                    rel / np.log2(i + 2)
                    for i, rel in enumerate(relevances[:k])
                )

            # 实际DCG
            relevances = [1 if p in truth else 0 for p in preds[:k]]
            actual_dcg = dcg(relevances, k)

            # 理想DCG
            ideal_relevances = [1] * min(len(truth), k) + [0] * max(0, k - len(truth))
            ideal_dcg = dcg(ideal_relevances, k)

            return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0

        # 计算各指标的平均值
        p_at_1 = np.mean([precision_at_k(p, t, 1) for p, t in zip(predictions, ground_truth)])
        p_at_5 = np.mean([precision_at_k(p, t, 5) for p, t in zip(predictions, ground_truth)])
        p_at_10 = np.mean([precision_at_k(p, t, 10) for p, t in zip(predictions, ground_truth)])
        r_at_10 = np.mean([recall_at_k(p, t, 10) for p, t in zip(predictions, ground_truth)])
        mrr = np.mean([reciprocal_rank(p, t) for p, t in zip(predictions, ground_truth)])
        ndcg = np.mean([ndcg_at_k(p, t, 10) for p, t in zip(predictions, ground_truth)])

        return QualityMetrics(
            precision_at_1=float(p_at_1),
            precision_at_5=float(p_at_5),
            precision_at_10=float(p_at_10),
            recall_at_10=float(r_at_10),
            mrr=float(mrr),
            ndcg_at_10=float(ndcg)
        )

    def get_raw_data(self) -> Dict[str, List[Dict]]:
        """获取原始数据"""
        result = {}
        for metric_type, points in self._data.items():
            result[metric_type] = [
                {
                    "value": p.value,
                    "timestamp": p.timestamp,
                    "labels": p.labels,
                    "success": p.success
                }
                for p in points
            ]
        return result

    def clear(self):
        """清空数据"""
        self._data.clear()
        self._start_time = None
        self._end_time = None

    def summary(self) -> Dict[str, Any]:
        """生成摘要"""
        latency = self.calculate_latency_metrics()
        throughput = self.calculate_throughput_metrics()

        return {
            "latency": latency.to_dict(),
            "throughput": throughput.to_dict(),
        }
