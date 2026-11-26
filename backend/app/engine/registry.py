"""统一算法能力注册表模块。

同时维护：
1. 兼容仓库现有 HTTP API 层（app/main.py、services/experiment.py、services/evidence_lab.py）的
   CAPABILITIES 列表；在组员 3 扩展 schemas/models.py 与 services/experiment.py 接入四排序前，
   HTTP 层仅暴露当前服务层实际可调度的 bubble_sort，避免与服务端校验和测试冲突。
2. 面向算法引擎层的完整能力注册表及查询接口，四个已实现的确定性排序执行器均为可执行状态。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.schemas.models import AlgorithmCapability

# 兼容仓库既有 HTTP 服务层的能力清单（与当前 services/experiment.py 实际可调度能力保持一致）
CAPABILITIES: list[AlgorithmCapability] = [
    AlgorithmCapability(
        name="bubble_sort",
        level="L4",
        executable=True,
        visualizable=True,
        max_input_size=2000,
    ),
    AlgorithmCapability(
        name="insertion_sort",
        level="L2",
        executable=False,
        visualizable=False,
        max_input_size=0,
    ),
    AlgorithmCapability(
        name="quick_sort",
        level="L2",
        executable=False,
        visualizable=False,
        max_input_size=0,
    ),
    AlgorithmCapability(
        name="merge_sort",
        level="L2",
        executable=False,
        visualizable=False,
        max_input_size=0,
    ),
]

# 引擎层统一算法能力注册表（未注册算法一律视为不可执行）
_ALGORITHM_REGISTRY: dict[str, dict[str, Any]] = {
    "bubble_sort": {
        "algorithm_id": "bubble_sort",
        "display_name": "冒泡排序",
        "family": "sorting",
        "supported_level": "L3_EXECUTABLE",
        "executable": True,
        "supports_trace": True,
        "supports_comparison": True,
        "max_input_size": 2000,
        "animation_max_size": 40,
        "parameters": {},
        "description": "手动实现的相邻元素比较交换排序，支持无交换提前退出优化。",
    },
    "insertion_sort": {
        "algorithm_id": "insertion_sort",
        "display_name": "插入排序",
        "family": "sorting",
        "supported_level": "L3_EXECUTABLE",
        "executable": True,
        "supports_trace": True,
        "supports_comparison": True,
        "max_input_size": 2000,
        "animation_max_size": 40,
        "parameters": {},
        "description": "手动实现的移位写入插入排序，严格区分比较次数与写入次数。",
    },
    "quick_sort": {
        "algorithm_id": "quick_sort",
        "display_name": "快速排序",
        "family": "sorting",
        "supported_level": "L3_EXECUTABLE",
        "executable": True,
        "supports_trace": True,
        "supports_comparison": True,
        "max_input_size": 2000,
        "animation_max_size": 40,
        "parameters": {
            "pivot_strategy": {
                "type": "string",
                "enum": ["first", "random"],
                "default": "first",
                "required": False,
                "description": "枢轴选择策略：first（首元素枢轴）或 random（随机枢轴）。",
            },
            "seed": {
                "type": "integer",
                "default": None,
                "required": False,
                "description": "随机枢轴策略使用的随机种子；未显式传入时继承 input.seed 以保证可复现。",
            },
        },
        "description": "手动实现的分治快速排序，支持首元素与随机枢轴策略并记录枢轴与递归深度。",
    },
    "merge_sort": {
        "algorithm_id": "merge_sort",
        "display_name": "归并排序",
        "family": "sorting",
        "supported_level": "L3_EXECUTABLE",
        "executable": True,
        "supports_trace": True,
        "supports_comparison": True,
        "max_input_size": 2000,
        "animation_max_size": 40,
        "parameters": {},
        "description": "手动实现的自顶向下稳定归并排序，记录比较、写入与最大递归深度。",
    },
}


def list_algorithms() -> list[dict[str, Any]]:
    """查询全部已注册算法能力记录（返回深拷贝防止外部意外修改）。"""
    return [deepcopy(item) for item in _ALGORITHM_REGISTRY.values()]


def get_algorithm_capability(algorithm_id: str) -> dict[str, Any] | None:
    """按 algorithm_id 查询算法能力；未注册算法返回 None。"""
    record = _ALGORITHM_REGISTRY.get(algorithm_id)
    return deepcopy(record) if record is not None else None


def is_registered_algorithm(algorithm_id: str) -> bool:
    """判断算法 ID 是否属于已注册能力。"""
    return algorithm_id in _ALGORITHM_REGISTRY


def is_algorithm_executable(algorithm_id: str) -> bool:
    """判断算法是否可真实执行；未注册算法始终返回 False。"""
    record = _ALGORITHM_REGISTRY.get(algorithm_id)
    return bool(record and record.get("executable", False))


def get_algorithm_parameters(algorithm_id: str) -> dict[str, Any]:
    """返回指定算法支持的参数定义与约束；未注册算法返回空字典。"""
    record = _ALGORITHM_REGISTRY.get(algorithm_id)
    if record is None:
        return {}
    return deepcopy(record.get("parameters", {}))
