"""排序结果正确性校验器单元测试。"""

from __future__ import annotations

from app.engine.validation import validate_sort_result


def test_valid_normal_and_edge_cases() -> None:
    """正常数组、空数组、单元素与重复元素数组均应校验通过。"""
    for inp, out in (
        ([], []),
        ([1], [1]),
        ([3, 1, 2], [1, 2, 3]),
        ([2, -1, 2, 0, -1], [-1, -1, 0, 2, 2]),
    ):
        res = validate_sort_result(inp, out)
        assert res["valid"] is True
        assert res["checks"] == {"sorted": True, "same_length": True, "same_multiset": True}
        assert res["errors"] == []


def test_detect_unsorted_output() -> None:
    """能识别乱序结果。"""
    res = validate_sort_result([3, 1, 2], [1, 3, 2])
    assert res["valid"] is False
    assert res["checks"]["sorted"] is False
    assert res["checks"]["same_length"] is True
    assert res["checks"]["same_multiset"] is True
    assert any("非递减" in err for err in res["errors"])


def test_detect_length_mismatch_and_missing_elements() -> None:
    """能识别长度不一致和元素丢失。"""
    res = validate_sort_result([3, 1, 2], [1, 2])
    assert res["valid"] is False
    assert res["checks"]["same_length"] is False
    assert res["checks"]["same_multiset"] is False
    assert any("长度" in err for err in res["errors"])
    assert any("丢失" in err for err in res["errors"])


def test_detect_extra_elements_and_multiset_mismatch() -> None:
    """能识别新增元素以及长度相同但多重集合不一致的情况。"""
    res_extra = validate_sort_result([1, 2], [1, 2, 3])
    assert res_extra["valid"] is False
    assert any("新增" in err for err in res_extra["errors"])

    res_replaced = validate_sort_result([1, 2, 2], [1, 2, 3])
    assert res_replaced["valid"] is False
    assert res_replaced["checks"]["sorted"] is True
    assert res_replaced["checks"]["same_length"] is True
    assert res_replaced["checks"]["same_multiset"] is False
    assert any("丢失" in err for err in res_replaced["errors"])
    assert any("新增" in err for err in res_replaced["errors"])
