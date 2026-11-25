# AI/NLP ↔ 后端 交接草案（AV-M1-D01 / D02）

状态：**待组员3确认**。本文件不是已冻结契约。契约源为 `backend/app/schemas/models.py`（组员3所有），
本组不得单方修改公共 Schema。

## 1. 当前约束（已核实）

- `ExperimentConfig.algorithm` 目前只接受 `bubble_sort`；`insertion_sort/quick_sort/merge_sort` 在注册表中为 L2、`executable=False`。
- `ExperimentInput.distribution` 仅 `random / sorted / reversed`；`metrics` 仅 `comparisons / swaps / elapsed_ms`。
- `ParseResult` 只有 `config / source / requires_confirmation` 三个字段，**没有**错误态字段。
- `ParseRequest` 只有 `text / session_id`，没有 `source` 字段。
- 工具白名单见项目书 4.2，共 7 项；`source='qwen'` 只用于真实调用，`mock` 仅离线预案。

## 2. 需要组员3确认的 7 个问题

1. 模型解析失败（超时 / Schema 非法 / 一次修复仍失败）时，`/experiments/parse` 应返回什么 HTTP 码与错误体？建议 504 / 422 / 409 + `APIError{code,message,details}`，其中 code 用 `backend/app/ai/errors.py` 的错误码。
2. `source` 字段是否沿用 `qwen | manual | mock` 三值？AI 模块只在真实调用时输出 `qwen`。
3. 错误态无法塞进当前 `ParseResult`（config 必填）。是否允许 AI 模块在失败时返回 `data=null` + `APIError`，由组员3转换？
4. 工具建议（intent + tool_suggestions + arguments）走哪个端点或信封字段？AI 只输出建议，白名单校验与执行由 `services/tools.py` 独占。
5. `request_id` 由统一信封生成；AI 内部只记录 `request_id` 透传，不自行生成第二套。是否确认？
6. `ConversationState` 目前在 `ChatResult` 中；parse 端点是否需要在请求里带会话切片以支持局部修订（D06）？
7. AI 模块何时接入 `main.py` 的 `/chat` 与 `/experiments/parse`？建议由组员3在路由中调用 `app.ai.*`，保持 schema 所有权不变。

## 3. 关键边界

- 模型**不得**执行任意 Python 代码；只输出配置 JSON 或工具建议。
- 未知字段一律拒绝（`StrictModel.extra='forbid'`）；最多一次自动修复。
- 所有 Key 从环境变量读取（`QWEN_API_KEY` / `QWEN_BASE_URL` / `QWEN_MODEL`），禁止提交。
- 无凭据时只能标注「离线预案」，不得把 Mock 结果写成真实模型结果。

## 4. 样例索引

- `backend/tests/fixtures/config_samples.json` — 10 条自然语言配置样例及期望。
- `backend/tests/fixtures/tool_request_samples.json` — 4 条工具建议样例。
