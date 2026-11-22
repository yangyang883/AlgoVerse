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
