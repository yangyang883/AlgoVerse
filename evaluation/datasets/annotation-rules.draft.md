# AlgoVerse 评测标注规则（草稿 v0.3）

- 状态：**组员 1 已确认引用粒度，待联合会审**｜维护：组员 5｜更新：2026-11-26
- 依据：项目书 9.1 四组对照、9.2 测试集建议、9.3 报告要求
- 配套：`datasets/schema/case.schema.json`、`datasets/v0.1/cases.seed.jsonl`、`datasets/error-taxonomy.md`

## 1. 目的与边界

只解决一件事：**每道题的标准答案与判定方式由人确定，并留下可追溯记录。**

不覆盖：模型自动打分、LLM-as-judge、自评。脚本只采集原始响应，判分权在人。

## 2. 角色分工

| 角色 | 人 | 职责 |
|---|---|---|
| 出题 | 组员 5 | 题面、`source`、初版 `expected`，状态 `draft` |
| 标注 | 组员 1 + 1 名领域同学 | 核定标准答案，补全 `expected`，状态改 `pending` |
| 复核 | 非标注人的第三人 | 二审，通过改 `reviewed`，不通过改 `rejected` 并写理由 |
| 仲裁 | 组内 2 人以上共识 | 分歧定案，写入 `review.note` |

硬约束：**出题人不能把自己出的题单独标成 `reviewed`。**

## 3. 五条通用原则

1. **可追溯**：标准答案能指向原文（`source_id`+`locator`）或用验证器复现。
2. **不抄模型**：模型输出不进入 `expected`。
3. **拿不准就退回**：`pending`/`rejected` 是正常状态。
4. **不预写数字**：准确率、完成率只能由实际结果统计。
5. **冻结后不改题**：结果难看也不删题、不降标准；负结果照实保留。

## 4. 字段填写规则

响应路径统一以组员 3 在 D2 发布的 OpenAPI 为准，`data` 段为业务体。

| 字段 | 填什么 | 常见错误 |
|---|---|---|
| `case_id` | `KNW/CFG/EXE/CEX/INV-四位序号` | 复用题号、跳号 |
| `dataset_version` / `split` | 当前 `v0.1` / `dev`；冻结集 `v1.0-frozen` / `frozen` | 把 dev 题混入冻结集统计 |
| `input.mode` | `chat`/`parse`/`run`/`compare`/`multi_turn` | 多轮题漏填 `multi_turn` |
| `input.steps[].endpoint` | `/api/v1/chat`、`/api/v1/experiments/parse`、`/api/v1/experiments/run`、`/api/v1/experiments/compare` | 用简称 `/chat` 或漏掉 `/api/v1` 前缀，与契约和 schema enum 不符 |
| `expected.required_fields` | 点号路径，如 `data.config.input.distribution` | 写中文描述而非路径 |
| `expected.field_values` | 路径 → 期望值，用于客观比对 | 值写成"约等于" |
| `expected.forbidden_fields` | 不得出现的路径，如 `data.config.color` | 遗漏，导致未知字段混过 |
| `expected.reference_value` | 真实执行输出（数组/数值） | 手算未验证器复核 |
| `expected.reference_metrics` | 只填实现确定的值，如 `comparisons=28` | 把深度等口径未定的值写死 |
| `expected.should_reject` | 非法输入/缺上下文/超界为 `true` | 与题目合法性矛盾 |
| `source.source_id` | 稳定编号，如 `CLRS-3E-7.2`、`SORT-004` | 写"课本"或"网上" |
| `source.locator` | 在线来源写"章/节 + 稳定 URL"；教材写"版本 + 章/节"，页码冻结前统一补 | 只写网页标题，或把纸质页码作为 `reviewed` 硬门槛 |
| `review.status` | `draft → pending → reviewed/rejected` | 跳过 `pending` |

### 4.1 引用定位两阶段规则（组员 1 已确认）

- 现阶段知识条目标记 `fact_ok`，并定位到章/节，例如 `CLRS-3E-7.2 / 第 7 章 7.2 节`；在线来源同时保留稳定 URL。
- 纸质页码在题集冻结前统一补齐，**不作为 `reviewed` 的硬门槛**。
- `auto_checks=citation_present` 只检查引用是否存在；引用是否真正支持结论仍由人工复核，不能用自动检查替代事实核对。

## 5. 统一评分档位

先算 rubric 加权分（0~1），再折算二值 `passed`（≥0.8）。对外报二值通过率，细粒度分数留在原始结果。含错误事实一律 0。

四类评分方式的 `passed` 折算：

| method | passed 条件 |
|---|---|
| `human_rubric` | rubric 加权分 ≥ 0.8 |
| `field_match` | `required_fields` 全部存在、`field_values` 全部相等、`forbidden_fields` 均未出现 |
| `executor_check` | `reference_value` / `reference_metrics` 全部命中，且证据取自本次真实 `run_id` |
| `refusal_check` | 明确拒绝并说明原因；`should_reject=true` 时不得出现执行结果 |

说明：三点式 rubric 若权重为 0.4/0.3/0.3，≥0.8 等价于三点全中，这是知识题“要点齐全”的有意设计，不视为权重失效；出题时须保证权重设置与期望的 `passed` 行为一致。

| 档 | 含义 |
|---|---|
| 1.0 | 完全正确、要点齐全、无错误事实 |
| 0.5 | 部分正确，关键点缺失但无错误事实 |
| 0 | 错误、编造、该拒未拒、假称执行 |

## 6. 五类任务判定细则

### 6.1 知识（KNW，目标 25）

指标：**事实正确率 + 引用命中率**（项目书 9.1 A/B 组）。

| 档 | 条件 |
|---|---|
| 1.0 | 事实正确、要点齐全、引用可定位到原文 |
| 0.5 | 事实正确但漏机制/漏前置条件 |
| 0 | 事实错误、概念错配、引用编造 |

退回：存在两种都成立的标准表述；`source` 疑似错误。

### 6.2 配置与追问（CFG，目标 30）

指标：**字段级准确率 + Schema 合法率 + 上下文引用正确率**（9.1 C 组）。

| 档 | 条件 |
|---|---|
| 1.0 | 必需字段齐全且值正确；多轮该继承的继承、该替换的替换；未知字段被拒 |
| 0.5 | 字段齐全但个别值偏差（如速度档近似） |
| 0 | 缺关键字段 / 多轮丢失上文 / 新数组被追加而非替换 / 接受未知字段 |

退回：`required_fields` 与 OpenAPI 不一致。

### 6.3 执行与性能解释（EXE，目标 20）

指标：**执行成功率 + 验证通过率 + 解释一致性**（9.1 D 组）。

| 档 | 条件 |
|---|---|
| 1.0 | 有真实 `run_id`，解释与 `metrics`/`trace` 完全一致 |
| 0.5 | 结论正确但未给可核验依据，或部分步骤对 |
| 0 | 未执行却声称执行、数字与 `metrics` 不符、假数据糊过 |

退回：`reference_value`/`reference_metrics` 未经执行器复核。

### 6.4 反例与边界（CEX，目标 15）

看：反例是否**真的**触发所声称的坏情况（有执行器则实测，否则人工复算并留算式）。

| 档 | 条件 |
|---|---|
| 1.0 | 反例经实测/复算有效 + 机制解释正确 |
| 0.5 | 反例有效但解释不完整 |
| 0 | 反例无效 / 用错误结论当反例 |

退回：当前无法验证该反例。

### 6.5 异常与非法输入（INV，目标 10）

指标：**拒绝率 + 提示可理解率**。

| 档 | 条件 |
|---|---|
| 1.0 | 明确拒绝 + 说明原因 + 给出可操作修正建议 |
| 0.5 | 拒绝但提示含糊（只有错误码） |
| 0 | 照常执行、静默返回错值、编造数据补齐 |

退回：题目其实是合法输入。

## 7. 一致性与抽检

- 双人盲标 **10%**（每类至少 2 题），独立填写后比对。
- 分歧率 **> 20%**：暂停，重读第 6 节后重新对齐。
- 每周抽 5 题由非标注人复算，重点查 `reference_value` / `reference_metrics`。
- 分歧与结论写 `review.note`，不删历史。

## 8. 数据划分

- 开发集 70 / 冻结集 30（项目书 9.2）。当前 23 题全部 `dev`。
- 冻结集在 D13 建立，之后**不用于调 Prompt**，只用于最终报告。

## 9. 已确认事项与待会审项

联合会审：2026-11-26 10:00–10:30，组员 1 拉组员 3，与组员 5 共同检查 `KNW-0001 / CFG-0001 / EXE-0001 / CEX-0001 / INV-0001` 的路径、字段和评分方式。

1. **已定：引用粒度。** 采用"章/节 + 稳定 URL"，不强制纸质页码；现阶段标 `fact_ok + 节号`，页码在冻结前统一补，不作为 `reviewed` 硬门槛。
2. 待确认：对外只报二值通过率（≥0.8），还是同时报加权均分？
3. 待确认：双人盲标 10%（23 题即 2~3 题）是否够？
4. **已定：KNW-0005 来源。** 使用现有在线来源，不指定教材：冒泡 `SORT-004`、插入 `SORT-008`、归并 `SORT-015`、快排相关 `SORT-009/011`。快排是否做稳定化仍待组员 2 确认，此题先保持 `pending`，不由组员 1 单方面标 `reviewed`。
5. **已确认：执行记录位置。** `run_id` 保存在 SQLite `experiments` 表；统一响应含 `request_id`；`compare` 请求体为 `{"run_ids":["id-1","id-2"]}`。
6. 待确认：反例有效性统一用"执行器实测比较次数 ÷ 理论值"判定，可以吗？
7. **待会审：澄清与错误响应映射。** 当前 `ParseResult` 只有 `config/source/requires_confirmation/session_id`，无法直接表达 `needs_clarification/error`。组员 1 建议映射为 HTTP 422，`error.code=E-SCHEMA-* / E-AMBIGUOUS-INPUT`，`details` 带字段路径，需组员 3 确认后冻结契约。
   - 补充风险：FastAPI 的 422 已被请求校验占用（`HTTPValidationError.detail[]`），业务澄清复用 422 会出现同一状态码两种响应结构；建议统一走 `error` 信封并停用默认 `detail` 格式，或改用 400/409。
   - 采纳后同步成本：`case.schema.json` 的 `expected` 为 `additionalProperties: false`，需先新增 `expected.error_code`、`expected.error_details_paths`，再改 INV-0001/0002/0003/0004、CFG-0005。
