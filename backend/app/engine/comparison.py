"""同输入策略与多算法对比模块。

支持：
1. 接收多份实验配置列表，按统一口径执行并输出对比指标与同输入校验标记。
2. 同一数组运行多个排序算法。
3. 同一快速排序算法对比不同枢轴策略（first 与 random），保留随机种子与输入配置确保可复现。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.engine.config import ConfigValidationError, parse_experiment_config
from app.engine.dataset import generate_dataset


def _build_comparison_row(run: dict[str, Any]) -> dict[str, Any]:
    """提取单次实验用于横向对比的核心指标行。"""
    cfg = run["config"]
    metrics = run["metrics"]
    return {
        "run_id": run["run_id"],
        "algorithm": cfg["algorithm"],
        "parameters": deepcopy(cfg["parameters"]),
        "status": run["status"],
        "valid": run["validation"]["valid"],
        "comparisons": metrics.get("comparisons", 0),
        "swaps": metrics.get("swaps", 0),
        "writes": metrics.get("writes", 0),
        "max_recursion_depth": metrics.get("max_recursion_depth", 0),
        "elapsed_ms": metrics.get("elapsed_ms", 0.0),
        "input_size": metrics.get("input_size", len(run["input"])),
        "trace_steps": metrics.get("trace_steps", len(run["trace"])),
        "trace_truncated": run["trace_truncated"],
    }


def compare_experiments(configs: list[dict[str, Any]]) -> dict[str, Any]:
    """执行多份配置对比实验，返回各次完整结果及横向指标对比表。"""
    if not isinstance(configs, list) or len(configs) < 2:
        raise ConfigValidationError(["对比实验至少需要提供 2 份配置"])

    # 延迟导入避免与 runner.py 产生循环导入
    from app.engine.runner import run_experiment

    runs = [run_experiment(cfg) for cfg in configs]
    first_input = runs[0]["input"]
    same_input = all(run["input"] == first_input for run in runs[1:])

    return {
        "same_input": same_input,
        "input_size": len(first_input),
        "input_config": deepcopy(runs[0]["config"]["input"]),
        "seed": runs[0]["config"]["input"]["seed"],
        "runs": runs,
        "comparison_table": [_build_comparison_row(run) for run in runs],
        "notes": (
            "所有对比轮次均在完全相同的输入数组上执行。"
            if same_input
            else "警告：对比配置生成的输入数组不一致，请谨慎解读横向指标差异。"
        ),
    }


def compare_algorithms_on_same_input(
    algorithms: list[str],
    *,
    input_config: dict[str, Any],
    parameters_map: dict[str, dict[str, Any]] | None = None,
    visualization_enabled: bool = False,
) -> dict[str, Any]:
    """在完全相同的输入数组上运行多个排序算法并对比核心指标。"""
    if len(algorithms) < 2:
        raise ConfigValidationError(["多算法对比至少需要指定 2 个算法"])

    # 先基于第一份配置解析输入并固化数组，确保后续所有算法使用绝对一致的输入副本
    probe_cfg = parse_experiment_config(
        {
            "algorithm": algorithms[0],
            "input": deepcopy(input_config),
            "parameters": deepcopy((parameters_map or {}).get(algorithms[0], {})),
            "visualization": {"enabled": visualization_enabled},
        }
    )
    resolved_input = probe_cfg["input"]
    if resolved_input["array"] is not None:
        shared_array = list(resolved_input["array"])
    else:
        shared_array = generate_dataset(
            size=resolved_input["size"],
            distribution=resolved_input["distribution"],
            seed=resolved_input["seed"],
        )

    configs: list[dict[str, Any]] = []
    for algo in algorithms:
        algo_input = {
            "size": len(shared_array),
            "distribution": resolved_input["distribution"],
            "seed": resolved_input["seed"],
            "array": list(shared_array),
        }
        configs.append(
            {
                "schema_version": "1.0",
                "algorithm": algo,
                "mode": "experiment",
                "input": algo_input,
                "parameters": deepcopy((parameters_map or {}).get(algo, {})),
                "visualization": {"enabled": visualization_enabled},
            }
        )

    result = compare_experiments(configs)
    result["shared_input"] = shared_array
    return result


def compare_quick_sort_pivots(
    *,
    input_config: dict[str, Any],
    strategies: list[str] | None = None,
    pivot_seed: int | None = None,
    visualization_enabled: bool = False,
) -> dict[str, Any]:
    """在相同输入与固定种子下对比快速排序的不同枢轴策略（默认 first 与 random）。"""
    chosen_strategies = strategies or ["first", "random"]
    if len(chosen_strategies) < 2:
        raise ConfigValidationError(["枢轴策略对比至少需要 2 种策略"])

    base_input = deepcopy(input_config)
    effective_seed = pivot_seed if pivot_seed is not None else base_input.get("seed", 42)

    configs: list[dict[str, Any]] = []
    for strategy in chosen_strategies:
        params: dict[str, Any] = {"pivot_strategy": strategy}
        if strategy == "random":
            params["seed"] = effective_seed
        configs.append(
            {
                "schema_version": "1.0",
                "algorithm": "quick_sort",
                "mode": "experiment",
                "input": deepcopy(base_input),
                "parameters": params,
                "visualization": {"enabled": visualization_enabled},
            }
        )

    result = compare_experiments(configs)
    result["pivot_seed"] = effective_seed
    return result
