# 组员 3 D6 验收记录

## 范围与接口

当前只有 `bubble_sort` 执行器及其测试；注册表里 `insertion_sort`、`quick_sort`、`merge_sort` 为不可执行占位，D6 未虚假启用。仓库仍无组员 1 Qwen Provider；D6 的解析联调使用明确标记的 Mock，未声称真实模型成功。

新增后端会话入口：

- `POST /api/v1/conversations`：提交合法 `ExperimentConfig`，由后端生成 `session_id` 并返回 `ConversationState`。
- `GET /api/v1/conversations/{session_id}`：读取后端状态；未知会话返回 409 `CONTEXT_CONFLICT`。
- `POST /api/v1/conversations/{session_id}/revise`：传 `{"changes":{"input.size":12}}`；只更新明示字段，其他配置保持不变。字段白名单为 `algorithm`、`input.size`、`input.distribution`、`input.seed`、`input.values`、`visualization.enabled`、`metrics`。未知字段或非法结果为 422；缺上下文为 409。
- `POST /api/v1/experiments/parse`：组员 1 Provider 或 Mock 返回 `ParseResult`；后端验证配置、创建或更新会话，并以**后端生成的** `session_id` 覆盖模型建议的 ID。无 Provider 时仍返回 501。
- `POST /api/v1/experiments/run`：可选请求头 `X-Session-ID`；成功保存后更新相应会话的最近 `run_id`。未知会话先返回 409，不执行实验。

`ConversationState.modified_fields` 与 `ParseResult.session_id` 是可选新增字段，原有请求仍有效。新增请求模型和 OpenAPI、JSON Schema、TypeScript 类型均由 Pydantic 生成。会话保存在单进程内存中，服务重启或多进程部署时不共享；此限制需要后续改为共享存储。

组员 4 可以直接调用上述真实会话 API 做手工配置及局部修订。自然语言解析入口在组员 1 Provider 交付前仅可通过测试替身联调。组员 1 需提供接受 `ParseRequest`、返回 `ParseResult` 的 Provider 和超时/不可用错误类型；组员 2 需提供已测试的其他执行器并同步算法白名单、参数校验及契约。

## Ruff 问题归属

全后端 `python -m ruff check backend/app backend/tests --output-format json` 当前共 40 项：

| 文件 | 负责人 | 数量 | 规则 |
|---|---|---:|---|
| `backend/app/engine/registry.py` | 组员 2（算法注册） | 1 | I001 ×1 |
| `backend/app/engine/sorting/bubble.py` | 组员 2 | 7 | UP035 ×2、UP006 ×5 |
| `backend/app/schemas/models.py` | 组员 3（公共契约） | 32 | UP035 ×2、FA100 ×13、UP006 ×17 |

Schema 的 32 项是已有类型注解风格问题；批量改写可能影响生成契约，因此本次 D6 只新增字段并验证生成结果，不做无关格式重构。组员 2 的文件未修改。D6 新增服务、API、测试及契约脚本单独 Ruff 检查通过；全后端检查仍未通过，需在后续协调清理。

## 实际测试

在可运行 Windows asyncio 的正常执行环境中执行 `python -m pytest -q`：**18 passed，0 failed，0 skipped**。`python scripts/export_contracts.py --check` 与 `python -m ruff check backend/app/main.py backend/app/services/conversation.py backend/tests/conftest.py backend/tests/test_conversation.py scripts/export_contracts.py`：均通过。`npm run build`：通过，仅有包体积提示。测试覆盖会话创建、字段保留、最近 run_id、缺上下文 409、非法算法 422、Mock 不能指定历史会话、显式数组与规模冲突。真实 Qwen 测试仍未执行。

## 独立审查修复（本节覆盖以上阶段性数字与行为）

已有会话的 `/parse` 不再使用 Provider 的完整配置覆盖历史状态。调用者须在 `ParseRequest.confirmed_changes` 提交用户明确确认的字段；后端检查 Provider 的候选字段值后，只对原有配置应用这些字段。没有可靠字段级信息返回 409，未知字段返回 422。组员 1 应提供字段级修订建议及用户确认流程；不能把完整配置差异自动视为用户意图。Provider 仍只需返回兼容的 `ParseResult`，`session_id` 由后端管理。

关联会话的 `/run` 先比较提交配置与已确认配置，不同则返回 409 `CONFIG_CONFLICT`，不执行、不保存、不更新状态；成功保存后仅更新 `last_run_id`。无会话 run 保持可用。会话默认 TTL 1800 秒、容量 100，分别由 `ALGOVERSE_SESSION_TTL_SECONDS`、`ALGOVERSE_MAX_SESSIONS` 配置；容量满返回 503，过期返回 409 `SESSION_EXPIRED`。这满足课程单 Worker 演示，重启后会话消失，多 Worker 不共享，长期部署需持久化。

SQLite Engine 按数据库路径复用，建表仅在首次创建 Engine 时执行；每次操作单独创建并关闭 Session，测试结束和应用关闭时可 dispose。测试数据库路径独立。公共 Schema 只调整类型注解与导入，不改变原字段语义；为兼容 Python 3.9 的 Pydantic，`Optional` 使用有说明的 Ruff `UP045` 例外。剩余 Ruff 8 项均在组员 2：`engine/registry.py` I001 ×1；`engine/sorting/bubble.py` UP035 ×2、UP006 ×5。建议组员 2 整理导入并将 `List`/`Tuple` 注解换为内建泛型，先确认 Python 3.9 兼容性。本次未改写其业务文件。

全后端 Ruff 仍有 8 项，**未通过**。契约生成和前端类型/构建须以本次最终执行记录为准。真实 Qwen、四排序和 RAG 仍缺组员 1、2 的交付；Mock 测试不是模型联调通过。

最终本地验证：`python -m pytest -q` 为 **24 passed、0 skipped**，包括有限并发的多会话隔离测试；`python scripts/export_contracts.py --check` 通过；`npm run typecheck`、`npm run build` 通过。全后端 Ruff 仍为上述 8 项组员 2 文件问题，未计为通过。受限执行窗口的最小 `asyncio.run(asyncio.sleep(0))` 会卡住；正常 Windows 执行环境中完整 pytest 通过。CI 未实际运行，不能声称 CI 通过。

### `/parse` 响应与同会话并发修复

`/parse` 对已有会话应用确认字段后，响应 `config` 现在取后端 `state.last_config`，避免响应中仍带 Provider 未确认的字段。回归用例中原 seed 42、Provider 给 seed 999、只确认 size 30：响应和会话均为 size 30/seed 42；直接把响应配置传给带 `X-Session-ID` 的 `/run` 成功并更新 `last_run_id`。

关联会话的配置检查、执行、SQLite 保存、最近 run_id 记录现在与 `revise` 共用会话服务锁；同会话修订会等待运行完成。正常 Windows 环境依次执行：`python -m pytest -q` **25 passed**；`python scripts/export_contracts.py --check` 通过；全后端 Ruff 仍为组员 2 的 **8 项**，未通过。真实 Qwen 与其他三种排序未交付，D6 全部要求及 D7 闸门均未宣称通过。
