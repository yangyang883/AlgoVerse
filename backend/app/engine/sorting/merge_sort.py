"""归并排序（Merge Sort）手动实现。

采用自顶向下分治合并，使用 <= 比较条件保证重复元素排序稳定性，
精确统计比较次数、写入次数与最大递归深度。
"""

from __future__ import annotations

import time

from app.engine.sorting import SortRunResult
from app.engine.tracing import (
    ANIMATION_SNAPSHOT_MAX_SIZE,
    DEFAULT_TRACE_LIMIT,
    TraceRecorder,
)


def run_merge_sort(
    values: list[int],
    *,
    trace_enabled: bool = True,
    trace_limit: int = DEFAULT_TRACE_LIMIT,
    include_array: bool | None = None,
) -> SortRunResult:
    """执行归并排序，记录比较、写入、递归深度与轨迹事件。"""
    result = list(values)
    should_include_array = (
        len(result) <= ANIMATION_SNAPSHOT_MAX_SIZE if include_array is None else include_array
    )
    recorder = TraceRecorder(
        enabled=trace_enabled,
        trace_limit=trace_limit,
        include_array=should_include_array,
    )
    comparisons = 0
    writes = 0
    max_recursion_depth = 0

    def merge(left: int, mid: int, right: int) -> None:
        nonlocal comparisons, writes
        left_part = result[left : mid + 1]
        right_part = result[mid + 1 : right + 1]
        i = 0
        j = 0
        k = left

        while i < len(left_part) and j < len(right_part):
            comparisons += 1
            recorder.record(
                "compare",
                [left + i, mid + 1 + j],
                result,
                {"left": left, "mid": mid, "right": right},
            )
            # 使用 <= 保证当左右两段元素相等时优先取左侧元素，从而维持排序稳定性
            if left_part[i] <= right_part[j]:
                result[k] = left_part[i]
                i += 1
            else:
                result[k] = right_part[j]
                j += 1
            writes += 1
            recorder.record("write", [k], result, {"value": result[k]})
            k += 1

        while i < len(left_part):
            result[k] = left_part[i]
            writes += 1
            recorder.record("write", [k], result, {"value": result[k]})
            i += 1
            k += 1

        while j < len(right_part):
            result[k] = right_part[j]
            writes += 1
            recorder.record("write", [k], result, {"value": result[k]})
            j += 1
            k += 1

    def sort_range(left: int, right: int, depth: int) -> None:
        nonlocal max_recursion_depth
        if left >= right:
            return
        max_recursion_depth = max(max_recursion_depth, depth)
        mid = (left + right) // 2
        sort_range(left, mid, depth + 1)
        sort_range(mid + 1, right, depth + 1)
        merge(left, mid, right)

    recorder.record("initial", [], result)
    start = time.perf_counter()

    if len(result) > 1:
        sort_range(0, len(result) - 1, 1)

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    recorder.record("complete", [], result)

    return SortRunResult(
        output=result,
        comparisons=comparisons,
        swaps=0,
        writes=writes,
        max_recursion_depth=max_recursion_depth,
        elapsed_ms=elapsed_ms,
        trace=recorder.events,
        trace_truncated=recorder.truncated,
    )


def merge_sort(values: list[int], trace_limit: int = DEFAULT_TRACE_LIMIT) -> SortRunResult:
    """便捷调用入口。"""
    return run_merge_sort(
        values,
        trace_enabled=trace_limit > 0,
        trace_limit=trace_limit,
    )
