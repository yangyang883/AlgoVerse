# API 契约与 D1 实现状态

统一成功体为 `{ "data": ..., "error": null, "request_id": "uuid" }`；错误体的 `data` 为 null、`error` 含 code/message/details。所有端点使用 `/api/v1`。未实现的五个端点目前固定返回 501 `NOT_IMPLEMENTED`；表中的成功码是后续目标。以下 Mock 仅是联调样例，不表示已实现。

| 端点 | 请求 | 成功 data / 状态 | 异常 | D1 |
|---|---|---|---|---|
| GET `/algorithms` | 无 | `AlgorithmCapability[]` / 200 | 服务故障 500 | 已实现 |
| POST `/chat` | `ChatRequest{message,session_id?}` | `ChatResult` / 200 | 模型超时 504，检索无结果 200 且 sources=[]，非法请求 422 | 待实现 |
| POST `/experiments/parse` | `ParseRequest{text,session_id?}` | `ParseResult{config,source,requires_confirmation}` / 200 | 上下文缺失 409，配置非法 422，模型超时 504 | 待实现 |
| POST `/experiments/run` | `ExperimentConfig` | `ExperimentResult` / 200 | 不支持算法/资源上限 422，执行失败 500 | 已实现，尚未持久化 |
| POST `/experiments/compare` | `CompareRequest{run_ids}` | `CompareResult` / 200 | 不同输入 409，记录缺失 404 | 待实现 |
| GET `/experiments/{id}` | UUID 路径 | `ExperimentResult` / 200 | 未找到 404 | 待实现 |
| GET `/experiments/{id}/report` | UUID 路径 | `ReportResult` / 200 | 未找到 404 | 待实现 |

联调 Mock 示例：`{"data":{"config":{"schema_version":"1.0","algorithm":"bubble_sort","mode":"experiment","input":{"size":3,"distribution":"random","seed":42,"values":[3,1,2]},"parameters":{},"visualization":{"enabled":true},"metrics":["comparisons","swaps","elapsed_ms"]},"source":"mock","requires_confirmation":true},"error":null,"request_id":"mock-request"}`。运行接口使用真实数据，不使用 Mock。D2 如要让快速排序配置通过，应先扩展能力注册表、Pydantic 枚举和前端生成类型，并增加对应测试。
