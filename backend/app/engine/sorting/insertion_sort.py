"""插入排序（Insertion Sort）手动实现。

采用经典移位写入方式实现：比较与写入严格分开计数，不将写入混记为交换。
"""

from __future__ import annotations

import time

from app.engine.sorting import SortRunResult
from app.engine.tracing import (
    ANIMATION_SNAPSHOT_MAX_SIZE,
    DEFAULT_TRACE_LIMIT,
    TraceRecorder,
)


def run_insertion_sort(
    values: list[int],
    *,
    trace_enabled: bool = True,
    trace_limit: int = DEFAULT_TRACE_LIMIT,
    include_array: bool | None = None,
) -> SortRunResult:
    """执行插入排序，精确记录比较次数、写入次数与轨迹事件。"""
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

    recorder.record("initial", [], result)
    start = time.perf_counter()

    for i in range(1, len(result)):
        key = result[i]
        j = i - 1
        # 向左扫描已排序区间，寻找 key 的插入位置
        while j >= 0:
            comparisons += 1
            recorder.record("compare", [j, j + 1], result, {"key": key})
            if result[j] > key:
                result[j + 1] = result[j]
                writes += 1
                recorder.record("write", [j + 1], result, {"value": result[j], "from": j})
                j -= 1
            else:
                break

        # 仅当目标位置发生变化时写入 key，避免有序输入下产生冗余写入
        target = j + 1
        if target != i:
            result[target] = key
            writes += 1
            recorder.record("write", [target], result, {"value": key, "inserted_from": i})

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    recorder.record("complete", [], result)

    return SortRunResult(
        output=result,
        comparisons=comparisons,
        swaps=0,
        writes=writes,
        max_recursion_depth=0,
        elapsed_ms=elapsed_ms,
        trace=recorder.events,
        trace_truncated=recorder.truncated,
    )


def insertion_sort(values: list[int], trace_limit: int = DEFAULT_TRACE_LIMIT) -> SortRunResult:
    """便捷调用入口。"""
    return run_insertion_sort(
        values,
        trace_enabled=trace_limit > 0,
        trace_limit=trace_limit,
    )
