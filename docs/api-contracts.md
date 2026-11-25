# API 契约与当前实现状态

统一成功体为 `{ "data": ..., "error": null, "request_id": "uuid" }`；错误体的 `data` 为 null、`error` 含 code/message/details。所有端点使用 `/api/v1`。未实现的端点目前固定返回 501 `NOT_IMPLEMENTED`；表中的成功码对应已实现或规划目标，以当前状态列为准。以下 Mock 仅是联调样例，不表示已实现。

| 端点 | 请求 | 成功 data / 状态 | 异常 | 当前 |
|---|---|---|---|---|
| GET `/algorithms` | 无 | `AlgorithmCapability[]` / 200 | 服务故障 500 | 已实现 |
| POST `/chat` | `ChatRequest{message,session_id?}` | `ChatResult` / 200 | 模型超时 504，检索无结果 200 且 sources=[]，非法请求 422 | 待实现 |
| POST `/experiments/parse` | `ParseRequest{text,session_id?,confirmed_changes?}` | `ParseResult{config,source,requires_confirmation,session_id?}` / 200 | 上下文缺失 409，配置非法 422，模型超时 504 | Provider 接口已实现；真实模型待交付，无 Provider 时 501 |
| POST `/experiments/run` | `ExperimentConfig` | `ExperimentResult` / 200 | 不支持算法/资源上限 422，执行失败 500 | 已实现并保存至 SQLite |
| POST `/experiments/compare` | `CompareRequest{run_ids}` | `CompareResult` / 200 | 不同实际输入 409，记录缺失 404 | 已实现（同输入对照） |
| GET `/experiments/{id}` | run_id 路径 | `ExperimentResult` / 200 | 未找到 404 | 已实现 |
| GET `/experiments/{id}/report` | UUID 路径 | `ReportResult` / 200 | 未找到 404 | 待实现 |

联调 Mock 示例：`{"data":{"config":{"schema_version":"1.0","algorithm":"bubble_sort","mode":"experiment","input":{"size":3,"distribution":"random","seed":42,"values":[3,1,2]},"parameters":{},"visualization":{"enabled":true},"metrics":["comparisons","swaps","elapsed_ms"]},"source":"mock","requires_confirmation":true},"error":null,"request_id":"mock-request"}`。运行接口使用真实数据，不使用 Mock。D2 如要让快速排序配置通过，应先扩展能力注册表、Pydantic 枚举和前端生成类型，并增加对应测试。

## 会话与解析说明

已实现：`GET /health`、`GET /algorithms`、`POST /experiments/run`、`GET /experiments/{run_id}`，以及同输入对照 `POST /experiments/compare`、会话创建 `POST /conversations`、查询 `GET /conversations/{session_id}`、修订 `POST /conversations/{session_id}/revise`；路径均加 `/api/v1` 前缀。`POST /experiments/parse` 仅有 Provider 接口，未接真实 Qwen；无 Provider 返回 501。`/chat`、`/report` 仍为 501。

已有会话解析请求须携带 `session_id` 和用户确认的 `confirmed_changes` 字段映射，例如 `{"text":"把规模改成 30","session_id":"...","confirmed_changes":{"input.size":30}}`。Provider 完整配置只用于校验候选字段；后端从最后合法配置应用明示变更，其他字段不继承 Provider 的改动。缺字段级确认返回 409。关联会话运行使用 `X-Session-ID`，配置与已确认版本不同返回 409 `CONFIG_CONFLICT`。错误封套及 request_id 在 OpenAPI 响应中声明。
