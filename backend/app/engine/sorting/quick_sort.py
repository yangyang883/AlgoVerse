"""快速排序（Quick Sort）手动实现。

支持首元素枢轴（first）与随机枢轴（random）两种策略：
- 两种策略共享完全相同的分区逻辑与比较条件（result[j] <= pivot_value）。
- 随机枢轴使用独立的 random.Random(seed) 保证实验可复现。
- 使用显式调用栈模拟递归并精确统计逻辑最大递归深度，避免 n=2000 退化输入触发 Python 栈溢出。
"""

from __future__ import annotations

import random
import time

from app.engine.sorting import SortRunResult
from app.engine.tracing import (
    ANIMATION_SNAPSHOT_MAX_SIZE,
    DEFAULT_TRACE_LIMIT,
    TraceRecorder,
)

SUPPORTED_PIVOT_STRATEGIES: tuple[str, ...] = ("first", "random")


def run_quick_sort(
    values: list[int],
    *,
    pivot_strategy: str = "first",
    seed: int = 42,
    trace_enabled: bool = True,
    trace_limit: int = DEFAULT_TRACE_LIMIT,
    include_array: bool | None = None,
) -> SortRunResult:
    """执行快速排序，真实暴露不同枢轴策略在比较次数与递归深度上的差异。"""
    if pivot_strategy not in SUPPORTED_PIVOT_STRATEGIES:
        raise ValueError(
            f"不支持的枢轴策略: {pivot_strategy}，可选值: {', '.join(SUPPORTED_PIVOT_STRATEGIES)}"
        )

    result = list(values)
    should_include_array = (
        len(result) <= ANIMATION_SNAPSHOT_MAX_SIZE if include_array is None else include_array
    )
    recorder = TraceRecorder(
        enabled=trace_enabled,
        trace_limit=trace_limit,
        include_array=should_include_array,
    )
    rng = random.Random(seed)
    comparisons = 0
    swaps = 0
    max_recursion_depth = 0

    def partition(low: int, high: int) -> int:
        """统一分区函数：首元素与随机枢轴策略共用同一套分区与比较逻辑。"""
        nonlocal comparisons, swaps

        # 根据枢轴策略选择枢轴下标；若为随机枢轴则先交换至区间首部 low
        if pivot_strategy == "random":
            chosen = rng.randint(low, high)
            recorder.record(
                "pivot",
                [chosen],
                result,
                {"strategy": pivot_strategy, "pivot_value": result[chosen], "low": low, "high": high},
            )
            if chosen != low:
                result[low], result[chosen] = result[chosen], result[low]
                swaps += 1
                recorder.record("swap", [low, chosen], result, {"reason": "move_random_pivot"})
        else:
            recorder.record(
                "pivot",
                [low],
                result,
                {"strategy": pivot_strategy, "pivot_value": result[low], "low": low, "high": high},
            )

        pivot_value = result[low]
        boundary = low
        for j in range(low + 1, high + 1):
            comparisons += 1
            recorder.record("compare", [j, low], result, {"pivot_value": pivot_value})
            if result[j] <= pivot_value:
                boundary += 1
                if boundary != j:
                    result[boundary], result[j] = result[j], result[boundary]
                    swaps += 1
                    recorder.record("swap", [boundary, j], result)

        # 将枢轴交换到最终分区位置 boundary
        if boundary != low:
            result[low], result[boundary] = result[boundary], result[low]
            swaps += 1
            recorder.record("swap", [low, boundary], result, {"reason": "place_pivot"})
        return boundary

    recorder.record("initial", [], result)
    start = time.perf_counter()

    if len(result) > 1:
        # 显式栈保存 (low, high, depth)，与标准递归先左后右调用完全等价且无栈溢出风险
        stack: list[tuple[int, int, int]] = [(0, len(result) - 1, 1)]
        while stack:
            low, high, depth = stack.pop()
            if low >= high:
                continue
            max_recursion_depth = max(max_recursion_depth, depth)
            pivot_pos = partition(low, high)
            # 先压入右半区间，再压入左半区间，保证出栈顺序与递归先左后右一致
            if pivot_pos + 1 < high:
                stack.append((pivot_pos + 1, high, depth + 1))
            if low < pivot_pos - 1:
                stack.append((low, pivot_pos - 1, depth + 1))

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    recorder.record("complete", [], result)

    return SortRunResult(
        output=result,
        comparisons=comparisons,
        swaps=swaps,
        writes=0,
        max_recursion_depth=max_recursion_depth,
        elapsed_ms=elapsed_ms,
        trace=recorder.events,
        trace_truncated=recorder.truncated,
    )


def quick_sort(
    values: list[int],
    *,
    pivot_strategy: str = "first",
    seed: int = 42,
    trace_limit: int = DEFAULT_TRACE_LIMIT,
) -> SortRunResult:
    """便捷调用入口。"""
    return run_quick_sort(
        values,
        pivot_strategy=pivot_strategy,
        seed=seed,
        trace_enabled=trace_limit > 0,
        trace_limit=trace_limit,
    )
