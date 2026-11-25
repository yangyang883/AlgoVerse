"""可复现整数测试数据集生成模块。

使用独立的 random.Random(seed) 实例生成测试数组，不污染全局随机状态，
支持 random、sorted、reverse/reversed、duplicates、nearly_sorted 分布。
"""

from __future__ import annotations

import random

# 支持的数据分布（兼容仓库原有的 reversed 与新契约的 reverse）
SUPPORTED_DISTRIBUTIONS: tuple[str, ...] = (
    "random",
    "sorted",
    "reverse",
    "reversed",
    "duplicates",
    "nearly_sorted",
)

MAX_INPUT_SIZE = 2000


def normalize_distribution(distribution: str) -> str:
    """将分布别名规范化，统一保留 reverse/reversed 兼容能力。"""
    if distribution == "reversed":
        return "reverse"
    return distribution


def generate_dataset(
    size: int,
    distribution: str = "random",
    seed: int = 42,
) -> list[int]:
    """根据规模、分布类型与固定随机种子生成可复现整数数组。"""
    if isinstance(size, bool) or not isinstance(size, int) or size < 0 or size > MAX_INPUT_SIZE:
        raise ValueError(f"输入规模 size 必须为 0 到 {MAX_INPUT_SIZE} 之间的整数，当前为: {size}")
    if distribution not in SUPPORTED_DISTRIBUTIONS:
        raise ValueError(
            f"不支持的输入分布: {distribution}，支持列表: {', '.join(SUPPORTED_DISTRIBUTIONS)}"
        )
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError(f"随机种子 seed 必须为整数，当前为: {seed}")

    if size == 0:
        return []

    normalized = normalize_distribution(distribution)
    rng = random.Random(seed)

    if normalized == "sorted":
        return list(range(size))

    if normalized == "reverse":
        return list(range(size, 0, -1))

    if normalized == "duplicates":
        # 使用较小的候选值域，保证 size >= 2 时高概率且稳定地包含重复整数
        if size == 1:
            return [rng.randint(1, 5)]
        pool_size = max(2, min(5, max(2, size // 3)))
        pool = list(range(1, pool_size + 1))
        values = [rng.choice(pool) for _ in range(size)]
        # 确保至少存在一对重复元素，避免极小规模下意外全不重复
        if len(set(values)) == len(values):
            values[-1] = values[0]
        return values

    if normalized == "nearly_sorted":
        # 从有序数组出发，按固定种子执行少量局部交换，模拟接近有序场景
        values = list(range(size))
        if size >= 2:
            swap_count = max(1, size // 10)
            for _ in range(swap_count):
                idx = rng.randint(0, size - 2)
                values[idx], values[idx + 1] = values[idx + 1], values[idx]
        return values

    # 默认 random 分布：与仓库现有范围 [-1000, 1000] 保持一致
    return [rng.randint(-1000, 1000) for _ in range(size)]
