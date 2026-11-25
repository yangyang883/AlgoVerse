"""冒泡排序（Bubble Sort）手动实现。

保留原有 bubble_sort(...) 返回签名以兼容后端现有 services/experiment.py，
同时提供统一的 run_bubble_sort(...) 接口供引擎调度层调用。
"""

from __future__ import annotations

import time

from app.engine.sorting import SortRunResult
from app.engine.tracing import (
    ANIMATION_SNAPSHOT_MAX_SIZE,
    DEFAULT_TRACE_LIMIT,
    TraceRecorder,
)
from app.schemas.models import TraceEvent


def run_bubble_sort(
    values: list[int],
    *,
    trace_enabled: bool = True,
    trace_limit: int = DEFAULT_TRACE_LIMIT,
    include_array: bool | None = None,
) -> SortRunResult:
    """执行冒泡排序，支持提前退出优化并记录比较、交换与轨迹。"""
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
    swaps = 0

    recorder.record("initial", [], result)
    start = time.perf_counter()

    n = len(result)
    for end in range(n - 1, 0, -1):
        changed = False
        for index in range(end):
            comparisons += 1
            recorder.record("compare", [index, index + 1], result)
            if result[index] > result[index + 1]:
                result[index], result[index + 1] = result[index + 1], result[index]
                swaps += 1
                changed = True
                recorder.record("swap", [index, index + 1], result)
        # 某一轮未发生任何交换，说明数组已完全有序，提前结束
        if not changed:
            break

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    recorder.record("complete", [], result)

    return SortRunResult(
        output=result,
        comparisons=comparisons,
        swaps=swaps,
        writes=0,
        max_recursion_depth=0,
        elapsed_ms=elapsed_ms,
        trace=recorder.events,
        trace_truncated=recorder.truncated,
    )


def bubble_sort(
    values: list[int],
    trace_limit: int = DEFAULT_TRACE_LIMIT,
) -> tuple[list[int], int, int, list[TraceEvent], bool]:
    """兼容仓库 D1 服务层的旧签名接口。"""
    run = run_bubble_sort(
        values,
        trace_enabled=trace_limit > 0,
        trace_limit=trace_limit,
        include_array=True,
    )
    trace_models = [TraceEvent.model_validate(item) for item in run.trace]
    return run.output, run.comparisons, run.swaps, trace_models, run.trace_truncated
