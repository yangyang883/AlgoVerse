"""算法能力注册表单元测试。"""

from __future__ import annotations

from app.engine.registry import (
    CAPABILITIES,
    get_algorithm_capability,
    get_algorithm_parameters,
    is_algorithm_executable,
    is_registered_algorithm,
    list_algorithms,
)


def test_list_and_query_registered_algorithms() -> None:
    """应列出全部四种已注册排序算法并包含必要字段。"""
    algorithms = list_algorithms()
    ids = {item["algorithm_id"] for item in algorithms}
    assert ids == {"bubble_sort", "insertion_sort", "quick_sort", "merge_sort"}

    required_fields = {
        "algorithm_id",
        "display_name",
        "family",
        "supported_level",
        "executable",
        "supports_trace",
        "supports_comparison",
        "parameters",
        "description",
    }
    for item in algorithms:
        assert required_fields.issubset(item.keys())
        assert item["family"] == "sorting"
        assert item["supported_level"] == "L3_EXECUTABLE"
        assert item["executable"] is True
        assert item["supports_trace"] is True
        assert item["supports_comparison"] is True

    # 兼容仓库现有 CAPABILITIES
    assert len(CAPABILITIES) == 4
    assert all(cap.executable is True for cap in CAPABILITIES)


def test_quick_sort_parameter_constraints() -> None:
    """快速排序必须声明 first 与 random 枢轴策略及可复现 seed 参数。"""
    cap = get_algorithm_capability("quick_sort")
    assert cap is not None
    params = get_algorithm_parameters("quick_sort")
    assert params["pivot_strategy"]["enum"] == ["first", "random"]
    assert "seed" in params


def test_unknown_algorithm_not_registered_or_executable() -> None:
    """未注册算法绝不能被标记为可执行。"""
    for unknown in ("heap_sort", "binary_search", "linear_search", "magic_sort", ""):
        assert is_registered_algorithm(unknown) is False
        assert is_algorithm_executable(unknown) is False
        assert get_algorithm_capability(unknown) is None
        assert get_algorithm_parameters(unknown) == {}
