from app.schemas.models import TraceEvent


def bubble_sort(values: list[int], trace_limit: int = 5000) -> tuple[list[int], int, int, list[TraceEvent], bool]:
    result = values.copy()
    trace = [TraceEvent(step=0, type="initial", array=result.copy())] if trace_limit else []
    comparisons = swaps = 0
    truncated = False

    def record(kind: str, indices: list[int]) -> None:
        nonlocal truncated
        if not trace_limit:
            return
        if len(trace) < trace_limit:
            trace.append(TraceEvent(step=len(trace), type=kind, indices=indices, array=result.copy()))
        else:
            truncated = True

    for end in range(len(result) - 1, 0, -1):
        changed = False
        for index in range(end):
            comparisons += 1
            record("compare", [index, index + 1])
            if result[index] > result[index + 1]:
                result[index], result[index + 1] = result[index + 1], result[index]
                swaps += 1
                changed = True
                record("swap", [index, index + 1])
        if not changed:
            break
    if trace_limit:
        record("complete", [])
    return result, comparisons, swaps, trace, truncated
