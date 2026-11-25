"""排序结果正确性校验器模块。

对输入数组和输出数组执行非递减顺序、长度一致性和多重集合一致性检查，
明确指出元素丢失或新增情况，并保证空数组和单元素数组合法通过。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any


def validate_sort_result(
    input_array: Sequence[int],
    output_array: Sequence[int],
) -> dict[str, Any]:
    """校验排序结果正确性，返回符合引擎契约的校验结果字典。"""
    errors: list[str] = []

    # 1. 检查输出数组是否非递减（空数组与单元素数组天然满足）
    is_sorted = all(
        output_array[i] <= output_array[i + 1] for i in range(len(output_array) - 1)
    )
    if not is_sorted:
        errors.append("输出数组未按非递减顺序排列")

    # 2. 检查输出长度是否与输入长度一致
    same_length = len(output_array) == len(input_array)
    if not same_length:
        errors.append(
            f"输出长度与输入长度不一致: 输入 {len(input_array)}，输出 {len(output_array)}"
        )

    # 3. 检查多重集合一致性，明确区分元素丢失与新增元素
    input_counter = Counter(input_array)
    output_counter = Counter(output_array)
    same_multiset = input_counter == output_counter

    missing = input_counter - output_counter
    if missing:
        missing_detail = ", ".join(f"{val}x{cnt}" for val, cnt in sorted(missing.items()))
        errors.append(f"存在元素丢失: {missing_detail}")

    extra = output_counter - input_counter
    if extra:
        extra_detail = ", ".join(f"{val}x{cnt}" for val, cnt in sorted(extra.items()))
        errors.append(f"存在新增元素: {extra_detail}")

    return {
        "valid": is_sorted and same_length and same_multiset,
        "checks": {
            "sorted": is_sorted,
            "same_length": same_length,
            "same_multiset": same_multiset,
        },
        "errors": errors,
    }
