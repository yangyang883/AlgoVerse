"""统一实验配置解析与参数校验模块。

未知字段处理策略说明：
为与仓库现有 backend/app/schemas/models.py 中 StrictModel(extra="forbid") 保持一致，
本模块对顶层配置、input、visualization 以及 parameters 中的未知字段采取“显式拒绝”策略，
并抛出带可读错误列表的 ConfigValidationError，避免字段拼写错误被静默忽略。
"""

from __future__ import annotations

from typing import Any

from app.engine.dataset import MAX_INPUT_SIZE, SUPPORTED_DISTRIBUTIONS, normalize_distribution
from app.engine.metrics import ALL_METRICS
from app.engine.registry import (
    get_algorithm_parameters,
    is_algorithm_executable,
    is_registered_algorithm,
)
from app.engine.tracing import DEFAULT_TRACE_LIMIT

ALLOWED_TOP_KEYS = {
    "schema_version",
    "algorithm",
    "mode",
    "input",
    "parameters",
    "visualization",
    "metrics",
}
ALLOWED_INPUT_KEYS = {"size", "distribution", "seed", "array", "values"}
ALLOWED_VISUALIZATION_KEYS = {"enabled", "trace_limit", "include_array"}
MAX_TRACE_LIMIT = 20000


class ConfigValidationError(ValueError):
    """实验配置校验失败异常，包含可供后端直接展示的可读错误列表。"""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _is_strict_int(value: Any) -> bool:
    """判断值是否为严格整数（排除 Python 中 bool 是 int 子类的情况）。"""
    return isinstance(value, int) and not isinstance(value, bool)


def parse_experiment_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    """校验并规范化统一实验配置字典，非法时抛出 ConfigValidationError。"""
    if not isinstance(raw_config, dict):
        raise ConfigValidationError(["实验配置必须为字典对象"])

    errors: list[str] = []

    unknown_top = sorted(set(raw_config.keys()) - ALLOWED_TOP_KEYS)
    if unknown_top:
        errors.append(f"配置包含未知字段: {', '.join(unknown_top)}")

    # 1. schema_version 校验
    schema_version = raw_config.get("schema_version", "1.0")
    if schema_version != "1.0":
        errors.append(f"不支持的 schema_version: {schema_version}，当前仅支持 '1.0'")

    # 2. mode 校验
    mode = raw_config.get("mode", "experiment")
    if mode != "experiment":
        errors.append(f"不支持的 mode: {mode}，当前仅支持 'experiment'")

    # 3. algorithm 校验（必须已注册且可执行）
    algorithm = raw_config.get("algorithm")
    if not isinstance(algorithm, str) or not algorithm.strip():
        errors.append("缺少有效的 algorithm 字段")
    elif not is_registered_algorithm(algorithm):
        errors.append(f"未注册的算法: {algorithm}")
    elif not is_algorithm_executable(algorithm):
        errors.append(f"算法暂不可执行: {algorithm}")

    # 4. input 校验（同时兼容 array 与仓库原有的 values 字段）
    raw_input = raw_config.get("input", {})
    if not isinstance(raw_input, dict):
        errors.append("input 字段必须为字典对象")
        raw_input = {}
    else:
        unknown_input = sorted(set(raw_input.keys()) - ALLOWED_INPUT_KEYS)
        if unknown_input:
            errors.append(f"input 包含未知字段: {', '.join(unknown_input)}")

    has_array = "array" in raw_input and raw_input["array"] is not None
    has_values = "values" in raw_input and raw_input["values"] is not None
    explicit_array: list[int] | None = None

    if has_array and has_values and raw_input["array"] != raw_input["values"]:
        errors.append("input.array 与 input.values 不能同时传入且内容不一致")
    elif has_array:
        explicit_array = raw_input["array"]
    elif has_values:
        explicit_array = raw_input["values"]

    if explicit_array is not None:
        if not isinstance(explicit_array, list):
            errors.append("input.array 必须为整数列表")
            explicit_array = None
        elif len(explicit_array) > MAX_INPUT_SIZE:
            errors.append(f"input.array 长度不能超过 {MAX_INPUT_SIZE}")
        elif any(not _is_strict_int(item) for item in explicit_array):
            errors.append("input.array 中的所有元素必须为整数")

    size = raw_input.get("size", 20 if explicit_array is None else len(explicit_array))
    if explicit_array is not None:
        # 契约要求：若提供了具体数组，优先使用用户给定数组并以数组长度为准
        size = len(explicit_array)
    elif not _is_strict_int(size) or size < 0 or size > MAX_INPUT_SIZE:
        errors.append(f"input.size 必须为 0 到 {MAX_INPUT_SIZE} 之间的整数")

    distribution = raw_input.get("distribution", "random")
    if distribution not in SUPPORTED_DISTRIBUTIONS:
        errors.append(
            f"不支持的 input.distribution: {distribution}，"
            f"可选值: {', '.join(SUPPORTED_DISTRIBUTIONS)}"
        )

    seed = raw_input.get("seed", 42)
    if not _is_strict_int(seed):
        errors.append("input.seed 必须为整数")

    # 5. parameters 校验（依据算法注册表约束逐项校验）
    raw_params = raw_config.get("parameters", {})
    normalized_params: dict[str, Any] = {}
    if raw_params is None:
        raw_params = {}
    if not isinstance(raw_params, dict):
        errors.append("parameters 字段必须为字典对象")
    elif isinstance(algorithm, str) and is_registered_algorithm(algorithm):
        param_schema = get_algorithm_parameters(algorithm)
        unknown_params = sorted(set(raw_params.keys()) - set(param_schema.keys()))
        if unknown_params:
            errors.append(
                f"算法 {algorithm} 不支持参数: {', '.join(unknown_params)}"
            )
        for param_name, spec in param_schema.items():
            if param_name in raw_params and raw_params[param_name] is not None:
                val = raw_params[param_name]
                expected_type = spec.get("type")
                if expected_type == "string" and not isinstance(val, str):
                    errors.append(f"参数 {param_name} 必须为字符串")
                    continue
                if expected_type == "integer" and not _is_strict_int(val):
                    errors.append(f"参数 {param_name} 必须为整数")
                    continue
                if "enum" in spec and val not in spec["enum"]:
                    errors.append(
                        f"参数 {param_name} 非法: {val}，可选值: {', '.join(spec['enum'])}"
                    )
                    continue
                normalized_params[param_name] = val
            elif spec.get("default") is not None:
                normalized_params[param_name] = spec["default"]

        # 快速排序随机枢轴必须具备确定 seed，保证实验可复现
        if (
            algorithm == "quick_sort"
            and normalized_params.get("pivot_strategy") == "random"
            and "seed" not in normalized_params
        ):
            normalized_params["seed"] = seed if _is_strict_int(seed) else 42

    # 6. visualization 校验
    raw_vis = raw_config.get("visualization", {})
    if not isinstance(raw_vis, dict):
        errors.append("visualization 字段必须为字典对象")
        raw_vis = {}
    else:
        unknown_vis = sorted(set(raw_vis.keys()) - ALLOWED_VISUALIZATION_KEYS)
        if unknown_vis:
            errors.append(f"visualization 包含未知字段: {', '.join(unknown_vis)}")

    vis_enabled = raw_vis.get("enabled", True)
    if not isinstance(vis_enabled, bool):
        errors.append("visualization.enabled 必须为布尔值")

    trace_limit = raw_vis.get("trace_limit", DEFAULT_TRACE_LIMIT)
    if not _is_strict_int(trace_limit) or trace_limit < 1 or trace_limit > MAX_TRACE_LIMIT:
        errors.append(f"visualization.trace_limit 必须为 1 到 {MAX_TRACE_LIMIT} 之间的整数")

    include_array = raw_vis.get("include_array")
    if include_array is not None and not isinstance(include_array, bool):
        errors.append("visualization.include_array 必须为布尔值或 null")

    # 7. metrics 校验
    raw_metrics = raw_config.get("metrics", list(ALL_METRICS))
    if not isinstance(raw_metrics, list) or any(not isinstance(m, str) for m in raw_metrics):
        errors.append("metrics 必须为字符串列表")
        normalized_metrics = list(ALL_METRICS)
    else:
        invalid_metrics = [m for m in raw_metrics if m not in ALL_METRICS]
        if invalid_metrics:
            errors.append(
                f"metrics 包含不支持的指标: {', '.join(invalid_metrics)}，"
                f"可选值: {', '.join(ALL_METRICS)}"
            )
        normalized_metrics = list(dict.fromkeys(raw_metrics))

    if errors:
        raise ConfigValidationError(errors)

    vis_config: dict[str, Any] = {
        "enabled": vis_enabled,
        "trace_limit": trace_limit,
    }
    if include_array is not None:
        vis_config["include_array"] = include_array

    return {
        "schema_version": schema_version,
        "algorithm": algorithm,
        "mode": mode,
        "input": {
            "size": size,
            "distribution": normalize_distribution(distribution),
            "seed": seed,
            "array": list(explicit_array) if explicit_array is not None else None,
        },
        "parameters": normalized_params,
        "visualization": vis_config,
        "metrics": normalized_metrics,
    }
