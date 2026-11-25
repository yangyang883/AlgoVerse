"""统一实验执行入口模块。

提供 run_experiment、run_repeated_experiments 与 compare_experiments，
负责串联配置校验、数据集生成、确定性算法调度、指标统计、结果校验与结果组装。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.engine.config import ConfigValidationError, parse_experiment_config
from app.engine.dataset import generate_dataset
from app.engine.metrics import MetricCounters, aggregate_repeated_metrics
from app.engine.sorting import (
    SortRunResult,
    run_bubble_sort,
    run_insertion_sort,
    run_merge_sort,
    run_quick_sort,
)
from app.engine.validation import validate_sort_result


def _dispatch_algorithm(
    algorithm: str,
    values: list[int],
    parameters: dict[str, Any],
    *,
    trace_enabled: bool,
    trace_limit: int,
    include_array: bool | None,
) -> SortRunResult:
    """按白名单调度对应的确定性排序执行器。"""
    if algorithm == "bubble_sort":
        return run_bubble_sort(
            values,
            trace_enabled=trace_enabled,
            trace_limit=trace_limit,
            include_array=include_array,
        )
    if algorithm == "insertion_sort":
        return run_insertion_sort(
            values,
            trace_enabled=trace_enabled,
            trace_limit=trace_limit,
            include_array=include_array,
        )
    if algorithm == "quick_sort":
        return run_quick_sort(
            values,
            pivot_strategy=parameters.get("pivot_strategy", "first"),
            seed=parameters.get("seed", 42),
            trace_enabled=trace_enabled,
            trace_limit=trace_limit,
            include_array=include_array,
        )
    if algorithm == "merge_sort":
        return run_merge_sort(
            values,
            trace_enabled=trace_enabled,
            trace_limit=trace_limit,
            include_array=include_array,
        )
    raise ConfigValidationError([f"未注册或不支持执行的算法: {algorithm}"])


def run_experiment(
    config: dict[str, Any],
    *,
    raise_on_invalid: bool = True,
) -> dict[str, Any]:
    """执行单个排序实验并返回符合统一契约的结果字典。

    参数:
        config: 原始实验配置字典。
        raise_on_invalid: 默认为 True，配置非法时抛出 ConfigValidationError；
            设为 False 时返回 status='invalid_config' 的结构化结果。
    """
    created_at = datetime.now(timezone.utc).isoformat()

    try:
        normalized = parse_experiment_config(config)
    except ConfigValidationError as exc:
        if raise_on_invalid:
            raise
        return {
            "run_id": str(uuid4()),
            "status": "invalid_config",
            "config": config if isinstance(config, dict) else {},
            "input": [],
            "output": [],
            "metrics": {},
            "validation": {
                "valid": False,
                "checks": {
                    "sorted": False,
                    "same_length": False,
                    "same_multiset": False,
                },
                "errors": list(exc.errors),
            },
            "trace": [],
            "trace_truncated": False,
            "created_at": created_at,
        }

    input_cfg = normalized["input"]
    if input_cfg["array"] is not None:
        input_values = list(input_cfg["array"])
    else:
        input_values = generate_dataset(
            size=input_cfg["size"],
            distribution=input_cfg["distribution"],
            seed=input_cfg["seed"],
        )

    vis_cfg = normalized["visualization"]
    sort_result = _dispatch_algorithm(
        normalized["algorithm"],
        input_values,
        normalized["parameters"],
        trace_enabled=vis_cfg["enabled"],
        trace_limit=vis_cfg["trace_limit"],
        include_array=vis_cfg.get("include_array"),
    )

    validation = validate_sort_result(input_values, sort_result.output)
    counters = MetricCounters(
        comparisons=sort_result.comparisons,
        swaps=sort_result.swaps,
        writes=sort_result.writes,
        max_recursion_depth=sort_result.max_recursion_depth,
        elapsed_ms=sort_result.elapsed_ms,
        input_size=len(input_values),
        trace_steps=len(sort_result.trace),
    )

    return {
        "run_id": str(uuid4()),
        "status": "success" if validation["valid"] else "failed",
        "config": normalized,
        "input": list(input_values),
        "output": list(sort_result.output),
        "metrics": counters.to_dict(normalized["metrics"]),
        "validation": validation,
        "trace": sort_result.trace,
        "trace_truncated": sort_result.trace_truncated,
        "created_at": created_at,
    }


def run_repeated_experiments(
    config: dict[str, Any],
    rounds: int = 3,
) -> dict[str, Any]:
    """按相同配置执行多轮重复实验，输出每轮指标及汇总统计。"""
    if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1:
        raise ValueError("重复实验轮次 rounds 必须为大于等于 1 的整数")

    runs = [run_experiment(config) for _ in range(rounds)]
    return {
        "config": runs[0]["config"],
        "input": runs[0]["input"],
        "rounds": rounds,
        "runs": runs,
        "metrics_report": aggregate_repeated_metrics(runs),
    }


from app.engine.comparison import compare_experiments

__all__ = [
    "compare_experiments",
    "run_experiment",
    "run_repeated_experiments",
]
