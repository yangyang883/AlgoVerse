# 组员 3 → 组员 1、4、5：评测接口交接

本文件描述当前后端实际行为。所有响应使用 `{ "data": ..., "error": null, "request_id": "..." }`；失败时 `data` 为 `null`，错误码位于 `error.code`，同一 ID 也在 `X-Request-ID` 响应头。

## 已可调用

- `GET /api/v1/algorithms` 返回能力列表；目前只有 `bubble_sort` 的 `executable=true`。
- `POST /api/v1/experiments/run` 接受完整 `ExperimentConfig`，返回 `ExperimentResult`，其中有 `run_id`、实际 `input`、`output`、`metrics`、`validation`、`trace`、`trace_truncated`。已有会话运行需将确认后的配置作为请求体，并在 `X-Session-ID` 传会话 ID；配置冲突返回 409 `CONFIG_CONFLICT`。
- `GET /api/v1/experiments/{run_id}` 从 SQLite 的 `experiments` 表读取已保存结果。相同 `run_id` 的输入、输出、配置和 trace 可读取；目前没有重新执行接口，耗时不保证可重复。
- `POST /api/v1/experiments/compare` 请求体为 `{"run_ids":["id-1","id-2"]}`，至少两个 ID。仅当所有已保存运行的**实际输入数组完全相同**时返回 `{"runs":[...],"same_input":true}`；不存在的 ID 返回 404，不同输入返回 409。该接口只建立同输入对照，不做统计显著性或不同条件比较。
- `POST /api/v1/conversations`、`GET /api/v1/conversations/{session_id}` 和 `POST /api/v1/conversations/{session_id}/revise` 支持会话创建、查询、局部修订。修订请求示例：`{"changes":{"input.size":30}}`。

运行及比较的最小请求示例：

```json
{"algorithm":"bubble_sort","input":{"values":[3,1,2]}}
```

当前配置字段为 `schema_version`、`algorithm`、`mode`、`input`、`parameters`、`visualization`、`metrics`。`input` 有 `size`、`distribution`、`seed`、可选 `values`；分布值仅为 `random`、`sorted`、`reversed`。实际数组在运行结果的 `input`。当前没有 `pivot`、`playback` 配置字段，也不接受 `reverse` 或 `nearly_sorted`。生成的正式契约位于 `contracts/` 与 `frontend/src/types/contracts.ts`。

## 解析及错误归因

`POST /api/v1/experiments/parse` 使用 `ParseRequest{text,session_id?,confirmed_changes?}`。尚无真实 Qwen Provider；未注入 Provider 时返回 501 `NOT_IMPLEMENTED`。后端测试中注入的 `source="mock"` 仅供测试，不代表 HTTP 服务提供真实模型模式。已有会话的请求必须带真实的后端 `session_id`，并用 `confirmed_changes` 明确字段，例如 `{"text":"把规模改成 30","session_id":"...","confirmed_changes":{"input.size":30}}`。返回配置是后端确认后的配置。组员 1 的 Provider 只提供候选解析，不能自行改写会话状态。

请求 Schema 错误和 Provider 返回结构不合法时，422 响应的字段路径位于 `error.details.errors[].loc`；没有独立的 `schema_error` 字段。统一错误码位于 `error.code`。评测脚本应读取 HTTP 状态、错误码及 `request_id`，并自行记录 `latency_ms`。

数据库 `experiments` 表保留 `algorithm_version` 和执行环境；`model_version`、`prompt_version`、`knowledge_version` 目前为 `null`。当前没有 `intent`、`tools_called`、`temperature` 或服务端 `latency_ms` 字段。`trace_truncated` 为结果中的布尔值；可视化开启时最多采集 5000 个事件，关闭时不采集。模型及知识版本应由组员 1 在真实 Provider 交付时提供，不能由后端猜测填充。

## 各组对接动作

- **组员 1**：交付真实 Provider 的调用入口、模型/提示词/知识快照版本、超时及错误类型；明确字段级候选修订信息。真实 Provider 接入前，`/parse` 和 `/chat` 不能作为真实 AI 评测通过。
- **组员 2**：交付并测试其余排序执行器及注册表能力，再扩展 `ExperimentConfig` 的合法算法、参数和对应版本；当前仅冒泡排序可执行。
- **组员 4**：使用生成的 TypeScript 契约；用 `X-Session-ID` 提交已确认配置；区分 409 配置冲突与 501 未实现。
- **组员 5**：`--mode mock` 是评测脚本自身的模拟，不是后端模型结果。真实请求不可为每个步骤伪造 `session_id`：会话 ID 应先由 `/conversations` 或 `/parse` 获得；`/run` 的请求体是 `ExperimentConfig`，会话 ID 放在 `X-Session-ID`，不能塞进配置 JSON。当前脚本如直接向 `/run` 配置体添加 `session_id`，会收到 422。使用相同显式 `input.values` 运行两次后，可调用 `/compare` 验证同输入对照。`/chat`、未接 Provider 的 `/parse` 仍会返回 501，应如实记录为阻断。
