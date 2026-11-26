"""统一轨迹记录协议模块。

负责按 TraceEvent 契约记录排序执行过程中的关键事件，支持小规模动画快照、
大规模仅索引记录以及轨迹硬限额截断标记。
"""

from __future__ import annotations

from typing import Any

from app.schemas.models import TraceEvent

# 协议允许的合法轨迹事件类型集合
VALID_EVENT_TYPES: tuple[str, ...] = (
    "initial",
    "compare",
    "swap",
    "write",
    "pivot",
    "complete",
)

# 轨迹默认硬限额，避免大规模输入导致响应体过大
DEFAULT_TRACE_LIMIT = 5000
# 建议保留完整数组快照的动画样本上限
ANIMATION_SNAPSHOT_MAX_SIZE = 40


class TraceRecorder:
    """统一轨迹记录器。

    - step 从 1 开始连续递增，满足协议示例及 TraceEvent(step>=0) 约束。
    - 当数组规模 <= 40 且未显式关闭快照时，记录操作后的完整数组快照；
      更大规模实验仅记录索引与元数据，避免内存与响应体膨胀。
    - 超过 trace_limit 时不再追加事件，并置 truncated=True。
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        trace_limit: int = DEFAULT_TRACE_LIMIT,
        include_array: bool = True,
        start_step: int = 1,
    ) -> None:
        self.enabled = enabled and trace_limit > 0
        self.trace_limit = max(0, trace_limit)
        self.include_array = include_array
        self._next_step = start_step
        self.events: list[dict[str, Any]] = []
        self.truncated = False

    def record(
        self,
        event_type: str,
        indices: list[int] | None = None,
        array: list[int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """记录单条轨迹事件；超限时仅标记截断而不抛出异常。"""
        if not self.enabled:
            return
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"不支持的轨迹事件类型: {event_type}")
        if len(self.events) >= self.trace_limit:
            self.truncated = True
            return

        event: dict[str, Any] = {
            "step": self._next_step,
            "type": event_type,
            "indices": list(indices) if indices is not None else [],
            "array": list(array) if (self.include_array and array is not None) else None,
            "metadata": dict(metadata) if metadata is not None else {},
        }
        self._next_step += 1
        self.events.append(event)

    def to_trace_models(self) -> list[TraceEvent]:
        """转换为仓库现有 Pydantic TraceEvent 列表，便于服务层兼容对接。"""
        return [TraceEvent.model_validate(item) for item in self.events]


def validate_trace_events(events: list[dict[str, Any]]) -> list[str]:
    """校验轨迹列表是否符合统一协议，返回错误描述列表（为空表示合法）。"""
    errors: list[str] = []
    expected_step: int | None = None
    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"轨迹第 {idx} 项不是字典")
            continue
        for key in ("step", "type", "indices", "array", "metadata"):
            if key not in event:
                errors.append(f"轨迹第 {idx} 项缺少字段: {key}")
        step = event.get("step")
        if not isinstance(step, int) or isinstance(step, bool) or step < 0:
            errors.append(f"轨迹第 {idx} 项 step 非法: {step}")
        else:
            if expected_step is None:
                expected_step = step
            elif step != expected_step:
                errors.append(f"轨迹第 {idx} 项 step 不连续: 期望 {expected_step}，实际 {step}")
            expected_step = step + 1

        event_type = event.get("type")
        if event_type not in VALID_EVENT_TYPES:
            errors.append(f"轨迹第 {idx} 项事件类型非法: {event_type}")

        indices = event.get("indices")
        if not isinstance(indices, list) or any(
            not isinstance(i, int) or isinstance(i, bool) or i < 0 for i in indices
        ):
            errors.append(f"轨迹第 {idx} 项 indices 非法: {indices}")

        array = event.get("array")
        if array is not None and (
            not isinstance(array, list)
            or any(not isinstance(v, int) or isinstance(v, bool) for v in array)
        ):
            errors.append(f"轨迹第 {idx} 项 array 非法")

        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            errors.append(f"轨迹第 {idx} 项 metadata 不是字典")
    return errors
