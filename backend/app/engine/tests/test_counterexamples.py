"""反例与边界测试场景单元测试。"""

from __future__ import annotations

from app.engine.counterexamples import run_counterexamples


def test_counterexamples_cover_all_required_scenarios() -> None:
    """应覆盖全部 10 类标准边界与退化场景，并真实暴露快排首枢轴退化现象。"""
    reports = run_counterexamples(degradation_size=30, seed=42)
    assert len(reports) == 10

    case_map = {item["case_id"]: item for item in reports}
    expected_ids = {
        "empty_array",
        "single_element",
        "already_sorted",
        "reverse_sorted",
        "all_equal",
        "with_duplicates",
        "small_random",
        "nearly_sorted",
        "quick_sort_first_sorted_degradation",
        "quick_sort_first_reverse_degradation",
    }
    assert set(case_map.keys()) == expected_ids

    for item in reports:
        assert item["validation_passed"] is True
        assert "算法理论上一定最坏" not in item["observation"]

    # 两个快速排序首枢轴退化案例应真实触发退化标记并输出客观描述
    for deg_id in (
        "quick_sort_first_sorted_degradation",
        "quick_sort_first_reverse_degradation",
    ):
        deg = case_map[deg_id]
        assert deg["pivot_strategy"] == "first"
        assert deg["degradation_triggered"] is True
        assert deg["max_recursion_depth"] == 29
        assert deg["comparisons"] == 435
        assert "当前实现在该输入下出现了比较次数或递归深度退化" in deg["observation"]
