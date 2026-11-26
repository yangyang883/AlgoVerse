"""统一轨迹记录协议单元测试。"""

from __future__ import annotations

import pytest

from app.engine.runner import run_experiment
from app.engine.tracing import validate_trace_events


@pytest.mark.parametrize("algorithm", ["bubble_sort", "insertion_sort", "quick_sort", "merge_sort"])
def test_trace_protocol_format_and_endpoints(algorithm: str) -> None:
    """四种排序在小规模样本下均应生成合法、连续且首尾完整的轨迹。"""
    res = run_experiment(
        {
            "algorithm": algorithm,
            "input": {"array": [5, 1, 4, 2, 3]},
            "parameters": {"pivot_strategy": "first"} if algorithm == "quick_sort" else {},
            "visualization": {"enabled": True},
        }
    )
    trace = res["trace"]
    assert len(trace) >= 2
    assert validate_trace_events(trace) == []
    assert trace[0]["type"] == "initial"
    assert trace[0]["array"] == [5, 1, 4, 2, 3]
    assert trace[-1]["type"] == "complete"
    assert trace[-1]["array"] == [1, 2, 3, 4, 5]
    assert res["trace_truncated"] is False


def test_quick_sort_records_pivot_events() -> None:
    """快速排序必须记录枢轴事件。"""
    res = run_experiment(
        {
            "algorithm": "quick_sort",
            "input": {"array": [6, 2, 8, 1, 5]},
            "parameters": {"pivot_strategy": "random", "seed": 42},
            "visualization": {"enabled": True},
        }
    )
    pivot_events = [e for e in res["trace"] if e["type"] == "pivot"]
    assert len(pivot_events) >= 1
    assert all("pivot_value" in e["metadata"] for e in pivot_events)


def test_swap_and_write_not_mixed_in_trace() -> None:
    """交换型排序与写入型排序在轨迹事件上应严格区分 swap 与 write。"""
    bubble = run_experiment({"algorithm": "bubble_sort", "input": {"array": [3, 2, 1]}})
    assert any(e["type"] == "swap" for e in bubble["trace"])
    assert not any(e["type"] == "write" for e in bubble["trace"])

    insertion = run_experiment({"algorithm": "insertion_sort", "input": {"array": [3, 2, 1]}})
    assert any(e["type"] == "write" for e in insertion["trace"])
    assert not any(e["type"] == "swap" for e in insertion["trace"])

    merge = run_experiment({"algorithm": "merge_sort", "input": {"array": [3, 2, 1]}})
    assert any(e["type"] == "write" for e in merge["trace"])
    assert not any(e["type"] == "swap" for e in merge["trace"])


def test_large_input_omits_full_array_and_marks_truncation() -> None:
    """大规模样本开启轨迹时仅记录索引与元数据，超过硬限额必须标记 trace_truncated=True。"""
    res = run_experiment(
        {
            "algorithm": "bubble_sort",
            "input": {"size": 60, "distribution": "reverse", "seed": 42},
            "visualization": {"enabled": True, "trace_limit": 50},
        }
    )
    assert res["trace_truncated"] is True
    assert len(res["trace"]) == 50
    assert validate_trace_events(res["trace"]) == []
    assert all(event["array"] is None for event in res["trace"])


def test_disabled_visualization_produces_empty_trace() -> None:
    """关闭可视化时不应生成轨迹且不标记截断。"""
    res = run_experiment(
        {
            "algorithm": "merge_sort",
            "input": {"size": 100, "distribution": "random", "seed": 42},
            "visualization": {"enabled": False},
        }
    )
    assert res["trace"] == []
    assert res["trace_truncated"] is False
    assert res["metrics"]["trace_steps"] == 0
