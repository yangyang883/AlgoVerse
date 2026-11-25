"""反例与边界测试场景模块。

覆盖 10 类标准边界与退化场景，真实运行排序算法并输出指标、校验结果和退化观察。
注意：仅基于当前实现在该输入下的真实运行数据给出客观描述，不作泛化理论断言。
"""

from __future__ import annotations

import json
import math
from typing import Any

from app.engine.dataset import generate_dataset
from app.engine.runner import run_experiment


def build_counterexample_scenarios(
    *,
    degradation_size: int = 30,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """构造 10 个固定可复现的边界与反例测试场景定义。"""
    return [
        {
            "case_id": "empty_array",
            "case_name": "空数组",
            "algorithm": "bubble_sort",
            "parameters": {},
            "array": [],
            "seed": seed,
        },
        {
            "case_id": "single_element",
            "case_name": "单元素数组",
            "algorithm": "insertion_sort",
            "parameters": {},
            "array": [1],
            "seed": seed,
        },
        {
            "case_id": "already_sorted",
            "case_name": "已有序数组",
            "algorithm": "bubble_sort",
            "parameters": {},
            "array": list(range(1, 11)),
            "seed": seed,
        },
        {
            "case_id": "reverse_sorted",
            "case_name": "逆序数组",
            "algorithm": "insertion_sort",
            "parameters": {},
            "array": list(range(10, 0, -1)),
            "seed": seed,
        },
        {
            "case_id": "all_equal",
            "case_name": "全部相同元素",
            "algorithm": "merge_sort",
            "parameters": {},
            "array": [7] * 10,
            "seed": seed,
        },
        {
            "case_id": "with_duplicates",
            "case_name": "含重复元素数组",
            "algorithm": "quick_sort",
            "parameters": {"pivot_strategy": "random", "seed": seed},
            "array": [5, 2, 5, 1, 2, 9, 1, 5, 3, 2],
            "seed": seed,
        },
        {
            "case_id": "small_random",
            "case_name": "小规模随机数组",
            "algorithm": "merge_sort",
            "parameters": {},
            "array": generate_dataset(size=12, distribution="random", seed=seed),
            "seed": seed,
        },
        {
            "case_id": "nearly_sorted",
            "case_name": "接近有序数组",
            "algorithm": "insertion_sort",
            "parameters": {},
            "array": generate_dataset(size=12, distribution="nearly_sorted", seed=seed),
            "seed": seed,
        },
        {
            "case_id": "quick_sort_first_sorted_degradation",
            "case_name": "快速排序首枢轴有序退化案例",
            "algorithm": "quick_sort",
            "parameters": {"pivot_strategy": "first"},
            "array": list(range(1, degradation_size + 1)),
            "seed": seed,
        },
        {
            "case_id": "quick_sort_first_reverse_degradation",
            "case_name": "快速排序首枢轴逆序退化案例",
            "algorithm": "quick_sort",
            "parameters": {"pivot_strategy": "first"},
            "array": list(range(degradation_size, 0, -1)),
            "seed": seed,
        },
    ]


def _detect_degradation(algorithm: str, n: int, comparisons: int, max_depth: int) -> bool:
    """判断当前实现在该输入下是否触发了比较次数或递归深度退化现象。"""
    if algorithm != "quick_sort" or n < 8:
        return False
    # 针对快速排序：若递归深度接近线性（>= n * 0.7）或比较次数接近 n*(n-1)/2（>= 0.4 * n^2），
    # 且显著高于 n * log2(n)，则判定为触发退化现象
    n_log_n = n * math.log2(n)
    depth_degraded = max_depth >= int(n * 0.7)
    comparisons_degraded = comparisons >= int(0.4 * n * n) and comparisons > 2 * n_log_n
    return depth_degraded or comparisons_degraded


def run_counterexamples(
    *,
    degradation_size: int = 30,
    seed: int = 42,
    visualization_enabled: bool = False,
) -> list[dict[str, Any]]:
    """运行全部边界与反例场景，返回包含真实指标与退化判断的报告列表。"""
    scenarios = build_counterexample_scenarios(degradation_size=degradation_size, seed=seed)
    reports: list[dict[str, Any]] = []

    for scenario in scenarios:
        result = run_experiment(
            {
                "schema_version": "1.0",
                "algorithm": scenario["algorithm"],
                "mode": "experiment",
                "input": {
                    "size": len(scenario["array"]),
                    "distribution": "random",
                    "seed": scenario["seed"],
                    "array": list(scenario["array"]),
                },
                "parameters": dict(scenario["parameters"]),
                "visualization": {"enabled": visualization_enabled},
            }
        )
        metrics = result["metrics"]
        n = len(scenario["array"])
        degraded = _detect_degradation(
            scenario["algorithm"],
            n,
            int(metrics["comparisons"]),
            int(metrics["max_recursion_depth"]),
        )
        observation = (
            "当前实现在该输入下出现了比较次数或递归深度退化。"
            if degraded
            else "当前实现在该输入下运行正常，未出现显著退化现象。"
        )
        reports.append(
            {
                "case_id": scenario["case_id"],
                "case_name": scenario["case_name"],
                "input": list(scenario["array"]),
                "input_size": n,
                "algorithm": scenario["algorithm"],
                "pivot_strategy": scenario["parameters"].get("pivot_strategy"),
                "comparisons": metrics["comparisons"],
                "swaps": metrics["swaps"],
                "writes": metrics["writes"],
                "max_recursion_depth": metrics["max_recursion_depth"],
                "elapsed_ms": metrics["elapsed_ms"],
                "validation_passed": result["validation"]["valid"],
                "degradation_triggered": degraded,
                "observation": observation,
            }
        )
    return reports


if __name__ == "__main__":
    print(json.dumps(run_counterexamples(), ensure_ascii=False, indent=2))
