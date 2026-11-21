# [AV-006 AV-008 AV-013] API 契约、编排、存储与部署

- 负责人角色：组员 3（后端与集成）
- 模块：`backend/app/api/`、`schemas/`、`services/`、`db/`、`contracts/`
- 前置依赖：组员 1 的解析接口、组员 2 的执行器
- 实现要求：D1–D3 固定 Schema/OpenAPI/TS、错误码和健康检查；D4–D7 SQLite 与编排；D8–D12 compare/report 查询；D17–D20 部署。
- 验收标准：契约生成检查通过；七个约定端点从 501 转为功能响应；run_id 持久查询；异常统一封套；目标机器启动。
- 预计开发阶段：D1–D20；P0
