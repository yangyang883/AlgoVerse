"""性能指标统计模块。

负责统一组织单次实验指标与多次重复实验的分轮次统计，
确保耗时仅计算核心算法执行本身，不包含前端动画和响应序列化开销。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# 引擎支持的全部标准指标名称
ALL_METRICS: tuple[str, ...] = (
    "comparisons",
    "swaps",
    "writes",
    "max_recursion_depth",
    "elapsed_ms",
    "input_size",
    "trace_steps",
)


@dataclass
class MetricCounters:
    """算法执行过程的基础计数器。"""

    comparisons: int = 0
    swaps: int = 0
    writes: int = 0
    max_recursion_depth: int = 0
    elapsed_ms: float = 0.0
    input_size: int = 0
    trace_steps: int = 0

    def to_dict(self, requested_metrics: list[str] | None = None) -> dict[str, int | float]:
        """转换为字典；默认输出全部标准指标，便于后端和前端统一读取。"""
        full: dict[str, int | float] = {
            "comparisons": self.comparisons,
            "swaps": self.swaps,
            "writes": self.writes,
            "max_recursion_depth": self.max_recursion_depth,
            "elapsed_ms": round(self.elapsed_ms, 6),
            "input_size": self.input_size,
            "trace_steps": self.trace_steps,
        }
        if not requested_metrics:
            return full
        # 保留所有核心必需指标，同时确保用户请求的指标均在返回结果中
        selected = set(requested_metrics) | set(ALL_METRICS)
        return {key: full[key] for key in ALL_METRICS if key in selected}


def aggregate_repeated_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """按轮次汇总多次重复实验的指标，返回每轮明细分表及均值/极值统计。"""
    per_round: list[dict[str, Any]] = []
    for idx, run in enumerate(runs, start=1):
        metrics = run.get("metrics", {})
        per_round.append({"round": idx, **metrics})

    summary: dict[str, dict[str, float]] = {}
    if per_round:
        for key in ALL_METRICS:
            values = [float(item[key]) for item in per_round if key in item]
            if values:
                summary[key] = {
                    "min": round(min(values), 6),
                    "max": round(max(values), 6),
                    "avg": round(sum(values) / len(values), 6),
                }

    return {
        "rounds": len(per_round),
        "per_round": per_round,
        "summary": summary,
    }
