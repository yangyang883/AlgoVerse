# 首批知识条目来源复核（D4）

- 范围：`KNW-0001` ~ `KNW-0005`　｜　复核人：组员 5　｜　更新：2026-11-26
- 复核三项：**来源是否存在**、**章/节与稳定 URL 是否可定位**、**复杂度/前提条件表述是否正确**。

## 1. 复核状态说明

| 状态 | 含义 |
|---|---|
| `fact_ok` | 结论与来源表述一致，且已定位到章/节；在线来源保留稳定 URL |
| `locator_pending` | 结论可信，但章/节或稳定 URL 仍需补齐 |
| `rejected` | 来源或结论有问题，退回修订 |

按组员 1 在 2026-11-26 确认的口径，现阶段采用 `fact_ok + 节号`，纸质页码在冻结前统一补，**不作为 `reviewed` 硬门槛**。KNW-0005 因快排实现口径待组员 2 确认，只进入 `pending`；其余题在联合会审前保持 `draft`。

## 2. 逐条复核

| case_id | source_id | 版本 | locator | 结论要点 | 状态 | 待办 |
|---|---|---|---|---|---|---|
| KNW-0001 | CLRS-3E-7.2 | CLRS 3rd ed. | 第 7 章 7.2 节 | 快排最坏 O(n²)，发生在划分 0/n-1 时，典型为有序+首枢轴 | `fact_ok` / `draft` | 页码冻结前统一补；核对"最坏"定义表述 |
| KNW-0002 | CLRS-3E-2.3 | CLRS 3rd ed. | 第 2 章 2.3 节 | 归并 O(n log n) 最坏=平均，额外空间 O(n)，与分布无关 | `fact_ok` / `draft` | 页码冻结前统一补；确认"与分布无关"限定在比较次数 |
| KNW-0003 | CLRS-3E-24.3 | CLRS 3rd ed. | 第 24 章 24.3 节 | Dijkstra 要求边权非负，负权用 Bellman-Ford | `fact_ok` / `draft` | 页码冻结前统一补；补充"负权环"边界说明 |
| KNW-0004 | CLRS-3E-32.4 | CLRS 3rd ed. | 第 32 章 32.4 节 | 前缀函数表征相同前后缀，主串指针不回退，O(n+m) | `fact_ok` / `draft` | 页码冻结前统一补；统一用"前缀函数"还是"next 数组"称呼 |
| KNW-0005 | SORT-004（主）；SORT-008/015/009/011 | 知识库 v1.0，PR #6 | 在线来源，URL 见第 3 节 | 冒泡/插入/归并稳定，快排通常不稳定 | `fact_ok` / `pending` | 组员 2 确认快排是否做稳定化前不得标 `reviewed` |

## 3. KNW-0005 在线来源（已核对 PR #6）

| source_id | 用途 | 稳定 URL | 版本 |
|---|---|---|---|
| SORT-004 | 冒泡排序稳定性 | https://en.wikipedia.org/wiki/Sorting_algorithm#Stability | 1.0 |
| SORT-008 | 插入排序稳定性 | https://en.wikipedia.org/wiki/Insertion_sort | 1.0 |
| SORT-015 | 归并排序复杂度与稳定性 | https://en.wikipedia.org/wiki/Merge_sort | 1.0 |
| SORT-009 | 快排基本定义与分治结构 | https://en.wikipedia.org/wiki/Quicksort | 1.0 |
| SORT-011 | 快排首枢轴与有序输入的最坏情形 | https://en.wikipedia.org/wiki/Quicksort#Worst-case_analysis | 1.0 |

`SORT-009/011` 提供快排实现与最坏情形背景；快排在本项目中的最终稳定性判定仍以组员 2 的实际实现口径为准，不能只凭通用定义把本题标为 `reviewed`。

## 4. 已知风险

1. **稳定性条目依赖具体实现**：若引擎的快排用了稳定分区，标准答案就要改。此条在组员 2 答复前保持 `pending`。
2. **自动检查不验证引用内容**：`citation_present` 只表示有引用，来源是否支持每个 `answer_point` 仍需人工逐条核对。
3. **复杂度条件容易被模型答成"平均"**："最坏"必须与"平均"区分，评分时按 `answer_points` 逐条核对，不做整体印象分。

## 5. 复核流程（后续 20 条知识题沿用）

1. 出题人填 `source` 字段，状态 `draft`。
2. 复核人核对结论、章/节和版本；在线来源同时核对稳定 URL。纸质页码可在冻结前统一补，不阻塞进入 `pending` 或 `reviewed`。
3. 两条以上知识题共用同一 `source_id` 时，只核一次，其余引用该核验记录；一道题有多个来源时，主来源写入 `source`，辅助来源在本表留痕。
4. 标注完成后状态改 `pending`，经复核及实现口径确认后才改 `reviewed`（双人规则见标注规则第 7 节）。

## 6. 组员 1 已回复与后续待办

- 引用粒度已定为"章/节 + 稳定 URL"，采用两阶段复核，页码不再作为 `reviewed` 硬门槛。
- KNW-0005 不再等待教材指定，改用上述在线来源；题目状态为 `pending`，等待组员 2 确认快排实现。
- 联合会审定为 2026-11-26 10:00–10:30，会后由组员 1 按会审结论更新相关题的 `review.status`。
- `ParseResult` 对澄清/错误的表达方式仍需会审：组员 1 建议 HTTP 422 + `E-SCHEMA-* / E-AMBIGUOUS-INPUT`，`details` 带字段路径，待组员 3 确认。
