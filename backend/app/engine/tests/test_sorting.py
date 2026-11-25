"""四种排序算法、统一配置校验、执行入口与策略对比的单元测试。"""

from __future__ import annotations

import pytest

from app.engine.comparison import (
    compare_algorithms_on_same_input,
    compare_experiments,
    compare_quick_sort_pivots,
)
from app.engine.config import ConfigValidationError, parse_experiment_config
from app.engine.dataset import generate_dataset
from app.engine.runner import run_experiment, run_repeated_experiments

ALL_ALGORITHMS = ["bubble_sort", "insertion_sort", "quick_sort", "merge_sort"]


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
@pytest.mark.parametrize("distribution", ["random", "sorted", "reverse", "duplicates", "nearly_sorted"])
def test_four_sorts_on_all_distributions(algorithm: str, distribution: str) -> None:
    """四种排序在五种标准分布下均应输出正确结果并通过校验。"""
    result = run_experiment(
        {
            "schema_version": "1.0",
            "algorithm": algorithm,
            "mode": "experiment",
            "input": {"size": 25, "distribution": distribution, "seed": 123, "array": None},
            "parameters": {"pivot_strategy": "first"} if algorithm == "quick_sort" else {},
            "visualization": {"enabled": True},
        }
    )
    assert result["status"] == "success"
    assert result["validation"]["valid"] is True
    assert result["output"] == sorted(result["input"])
    assert result["metrics"]["input_size"] == 25
    assert result["metrics"]["elapsed_ms"] >= 0.0


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
@pytest.mark.parametrize("array", [[], [1], [-5, 0, -5, 3, -1, 3], [9, 9, 9, 9]])
def test_four_sorts_edge_arrays(algorithm: str, array: list[int]) -> None:
    """空数组、单元素数组、负数与全重复数组均不报错且排序正确。"""
    result = run_experiment(
        {
            "algorithm": algorithm,
            "input": {"array": array},
            "visualization": {"enabled": True},
        }
    )
    assert result["status"] == "success"
    assert result["validation"]["valid"] is True
    assert result["output"] == sorted(array)


def test_bubble_sort_early_exit_on_sorted() -> None:
    """冒泡排序在已有序数组上应在首轮无交换后提前退出。"""
    result = run_experiment(
        {
            "algorithm": "bubble_sort",
            "input": {"array": [1, 2, 3, 4, 5, 6]},
        }
    )
    assert result["metrics"]["comparisons"] == 5
    assert result["metrics"]["swaps"] == 0
    assert result["metrics"]["writes"] == 0


def test_insertion_sort_separates_writes_from_swaps() -> None:
    """插入排序只记录写入次数，不与交换次数混计。"""
    result = run_experiment(
        {
            "algorithm": "insertion_sort",
            "input": {"array": [5, 4, 3, 2, 1]},
        }
    )
    assert result["output"] == [1, 2, 3, 4, 5]
    assert result["metrics"]["swaps"] == 0
    assert result["metrics"]["writes"] > 0
    assert result["metrics"]["comparisons"] == 10


def test_quick_sort_first_and_random_reproducible() -> None:
    """快速排序首枢轴和随机枢轴在相同种子下结果、指标与轨迹完全可复现。"""
    for strategy in ("first", "random"):
        cfg = {
            "algorithm": "quick_sort",
            "input": {"size": 30, "distribution": "random", "seed": 77},
            "parameters": {"pivot_strategy": strategy, "seed": 77} if strategy == "random" else {"pivot_strategy": strategy},
            "visualization": {"enabled": True},
        }
        r1 = run_experiment(cfg)
        r2 = run_experiment(cfg)
        assert r1["input"] == r2["input"]
        assert r1["output"] == r2["output"] == sorted(r1["input"])
        assert r1["metrics"]["comparisons"] == r2["metrics"]["comparisons"]
        assert r1["metrics"]["swaps"] == r2["metrics"]["swaps"]
        assert r1["metrics"]["max_recursion_depth"] == r2["metrics"]["max_recursion_depth"]
        assert r1["trace"] == r2["trace"]


def test_quick_sort_large_degraded_input_no_recursion_error() -> None:
    """n=1500 有序退化输入下，首枢轴快排应真实统计深度且不发生栈溢出。"""
    result = run_experiment(
        {
            "algorithm": "quick_sort",
            "input": {"size": 1500, "distribution": "sorted", "seed": 42},
            "parameters": {"pivot_strategy": "first"},
            "visualization": {"enabled": False},
        }
    )
    assert result["status"] == "success"
    assert result["validation"]["valid"] is True
    assert result["metrics"]["max_recursion_depth"] == 1499


def test_config_priority_and_invalid_rejection() -> None:
    """提供 input.array 时应优先使用给定数组；非法参数与未知字段应被拒绝。"""
    parsed = parse_experiment_config(
        {
            "algorithm": "merge_sort",
            "input": {"size": 99, "distribution": "random", "array": [4, 2, 7]},
        }
    )
    assert parsed["input"]["array"] == [4, 2, 7]
    assert parsed["input"]["size"] == 3

    # 非法算法、非法枢轴、未知字段、超限规模、布尔伪装整数均应抛出异常
    invalid_configs = [
        {"algorithm": "unknown_sort"},
        {"algorithm": "quick_sort", "parameters": {"pivot_strategy": "median_of_three"}},
        {"algorithm": "bubble_sort", "parameters": {"pivot_strategy": "first"}},
        {"algorithm": "merge_sort", "unknown_field": 123},
        {"algorithm": "bubble_sort", "input": {"size": 2001}},
        {"algorithm": "bubble_sort", "input": {"array": [1, True, 3]}},
        {"algorithm": "bubble_sort", "input": {"distribution": "gaussian"}},
    ]
    for bad in invalid_configs:
        with pytest.raises(ConfigValidationError):
            run_experiment(bad)

    # 关闭抛异常模式时应返回 invalid_config 状态
    res = run_experiment({"algorithm": "unknown_sort"}, raise_on_invalid=False)
    assert res["status"] == "invalid_config"
    assert res["validation"]["valid"] is False
    assert res["validation"]["errors"]


def test_dataset_reproducibility() -> None:
    """相同种子生成的各类分布数组应完全一致。"""
    for dist in ("random", "sorted", "reverse", "reversed", "duplicates", "nearly_sorted"):
        a = generate_dataset(20, dist, seed=99)
        b = generate_dataset(20, dist, seed=99)
        assert a == b
        assert len(a) == 20


def test_comparison_and_repeated_runs() -> None:
    """验证多算法同输入对比、快排策略对比与多轮重复实验统计。"""
    cmp_all = compare_algorithms_on_same_input(
        ALL_ALGORITHMS,
        input_config={"size": 30, "distribution": "random", "seed": 42},
    )
    assert cmp_all["same_input"] is True
    assert len(cmp_all["comparison_table"]) == 4
    assert all(row["valid"] for row in cmp_all["comparison_table"])

    pivot_cmp = compare_quick_sort_pivots(
        input_config={"size": 40, "distribution": "sorted", "seed": 42},
        pivot_seed=42,
    )
    assert pivot_cmp["same_input"] is True
    first_row, random_row = pivot_cmp["comparison_table"]
    assert first_row["max_recursion_depth"] > random_row["max_recursion_depth"]
    assert first_row["comparisons"] > random_row["comparisons"]

    direct_cmp = compare_experiments(
        [
            {"algorithm": "bubble_sort", "input": {"array": [3, 1, 2]}},
            {"algorithm": "merge_sort", "input": {"array": [3, 1, 2]}},
        ]
    )
    assert direct_cmp["same_input"] is True

    repeated = run_repeated_experiments(
        {"algorithm": "merge_sort", "input": {"size": 20, "distribution": "random", "seed": 7}},
        rounds=3,
    )
    assert repeated["rounds"] == 3
    assert len(repeated["metrics_report"]["per_round"]) == 3
    assert repeated["metrics_report"]["summary"]["comparisons"]["min"] == (
        repeated["metrics_report"]["summary"]["comparisons"]["max"]
    )
