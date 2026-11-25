"""冒泡排序模块别名导出，便于按 bubble_sort 名称直接导入。"""

from __future__ import annotations

from app.engine.sorting.bubble import bubble_sort, run_bubble_sort

__all__ = ["bubble_sort", "run_bubble_sort"]
