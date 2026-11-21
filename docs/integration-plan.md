# 集成计划

1. D1 由组员 3 管理 Pydantic 源模型，运行 `python scripts/export_contracts.py` 更新 OpenAPI、JSON Schema 和 TS 类型。PR 中必须包含导出文件；CI 用 `--check` 检查漂移。
2. 组员 1 先用 `ParseResult` 固定响应，组员 2 按 `TraceEvent` 记录数组快照；组员 4 只消费导出类型。Mock 样例位于 `api-contracts.md`，必须标明 `source: mock`。
3. 每天合并前运行 backend pytest、契约校验、前端构建和 ruff。主线保持可启动。功能分支只改所属模块；跨模块改动先由 3 更新契约。
4. D3 将 Qwen 实际返回的配置流接入 `run`；D4 起加入 SQLite 追溯。运行指标由执行器产生，AI 解释必须引用运行记录。
5. 集成验收记录 API 请求、响应、模型标识、seed、知识版本和失败原因。D7、D12、D16 用同一批固定样例复演；对外展示只引用实际结果。
