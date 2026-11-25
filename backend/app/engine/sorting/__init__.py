"""排序算法执行器子包。

统一定义排序执行结果结构，并导出四种手动实现的确定性排序算法。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SortRunResult:
    """单个排序执行器的统一底层返回结果。"""

    output: list[int]
    comparisons: int
    swaps: int
    writes: int
    max_recursion_depth: int
    elapsed_ms: float
    trace: list[dict[str, Any]]
    trace_truncated: bool


from app.engine.sorting.bubble import bubble_sort, run_bubble_sort
from app.engine.sorting.insertion_sort import insertion_sort, run_insertion_sort
from app.engine.sorting.merge_sort import merge_sort, run_merge_sort
from app.engine.sorting.quick_sort import quick_sort, run_quick_sort

__all__ = [
    "SortRunResult",
    "bubble_sort",
    "insertion_sort",
    "merge_sort",
    "quick_sort",
    "run_bubble_sort",
    "run_insertion_sort",
    "run_merge_sort",
    "run_quick_sort",
]
