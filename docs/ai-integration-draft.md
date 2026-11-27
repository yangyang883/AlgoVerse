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

---

## 5. 与远程 main 核对结果（2026-11-26，组员3联调）

远程 `main` 已合并 D1–D6，契约与路由状态变了。以下逐条更新上面 7 问：**4 项已由组员3实现解决，3 项仍需他拍板**。

| # | 原问题 | 当前状态 | 结论 |
|---|---|---|---|
| 1 | 解析失败返回什么 HTTP 码/错误体 | **已解决**：`/parse` 路由 catch `TimeoutError→504`、`ConnectionError→503`、`ValidationError→422`，统一 `APIError{code,message,details}` + `request_id` | 无需再定。我的错误码放 `error.details.errors[].ctx.code`（422 路径）；超时/不可达走标准异常映射 |
| 2 | `source` 是否沿用 qwen/manual/mock | **已解决**：`ParseResult.source: Literal["qwen","manual","mock"]` | 沿用；真实调用只输出 `qwen` |
| 3 | 错误态能否 `data=null` + APIError | **已解决**：路由用统一信封，失败 `data=null`，错误码在 `error.code`；AI 适配层把失败态映射到 422/503/504 | 无需扩展 `ParseResult`，错误不塞 config |
| 4 | 工具建议走哪个端点/信封字段 | **仍待决**：`ParseResult` 无 `intent/tool_suggestions` 字段，`ChatResult` 也无 | **请组员3决定**：①加字段 ②独立端点 ③暂不暴露（评测不覆盖） |
| 5 | `request_id` 是否由统一信封生成、AI 只透传 | **基本解决**：信封与 `X-Request-ID` 由路由生成；AI 内部 `ParseOutcome.request_id` 仅用于脱敏 transcript 对账 | 确认：AI 不自行生成第二套对外 ID |
| 6 | parse 是否需带会话切片支持局部修订 | **已解决**：`ParseRequest` 有 `session_id/confirmed_changes`，路由用 `conversations.accept_parse`；`ChatResult` 含 `ConversationState` | 无需改；AI 不自行改写会话状态，只出候选 |
| 7 | AI 何时接入 `/parse` 与 `/chat` | **部分解决**：`/parse` 已留 `app.state.parse_provider` 注入点（未注入→501）；`/chat` 仍 501 | **请组员3决定**：`/chat` 是否本期接入 RAG（`rag.py` 已就绪，真实 BGE 索引可用） |

### 仍需组员3拍板的 3 件事（按优先级）

1. **Q4 工具建议出口**：影响评测是否覆盖工具调用类题目（CEX/INV 若干道）。建议本期先走③暂不暴露，避免改公共 Schema。
2. **Q7 `/chat` 接入范围**：`rag.py + BGE` 已就绪；若本期接入，我提供 provider 注入示例；若不接，保持 501 并由评测如实记录。
3. **错误码命名对齐**：我的 `E-QWEN-*` / `E-SCHEMA-*` / `E-UNKNOWN-ALGORITHM` 需并入你的统一码表；当前 422 路径下我的具体 code 在 `error.details.errors[].ctx.code`，若你希望直接放 `error.code`，需在路由 catch 里改一处（你所有）。

### 已交付的联调件（本仓库）

- `backend/app/ai/integration.py` — `make_parse_provider()` 生成可注入 `app.state.parse_provider` 的 callable；成功返回契约 dict，失败映射标准异常。
- `backend/scripts/integration_smoke.py` — 真实 Qwen 跑「请用冒泡排序把3、1、2从小到大排序」，已验证 parse→run 输出 `[1,2,3]`。
- `backend/artifacts/integration-smoke.json`、`integration-transcript.jsonl` — 脱敏记录，无 Key 泄漏。
- `backend/tests/test_integration.py` — 4 项离线测试通过。

**边界声明**：我未修改 `main.py` / `schemas/models.py` / SQLite / services；`/parse` 与 `/run` 的 HTTP 抓包由组员3在集成工作区完成。
