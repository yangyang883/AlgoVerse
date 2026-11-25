"""AlgoVerse 确定性算法执行引擎包。

对外提供统一的算法能力查询、单次实验执行与多策略/多算法对比接口，
供后端服务层直接调用，不依赖前端或外部大模型运行。
"""

from __future__ import annotations

from app.engine.comparison import (
    compare_algorithms_on_same_input,
    compare_experiments,
    compare_quick_sort_pivots,
)
from app.engine.config import ConfigValidationError, parse_experiment_config
from app.engine.counterexamples import run_counterexamples
from app.engine.registry import (
    CAPABILITIES,
    get_algorithm_capability,
    get_algorithm_parameters,
    is_algorithm_executable,
    is_registered_algorithm,
    list_algorithms,
)
from app.engine.runner import run_experiment, run_repeated_experiments

__all__ = [
    "CAPABILITIES",
    "ConfigValidationError",
    "compare_algorithms_on_same_input",
    "compare_experiments",
    "compare_quick_sort_pivots",
    "get_algorithm_capability",
    "get_algorithm_parameters",
    "is_algorithm_executable",
    "is_registered_algorithm",
    "list_algorithms",
    "parse_experiment_config",
    "run_counterexamples",
    "run_experiment",
    "run_repeated_experiments",
]
