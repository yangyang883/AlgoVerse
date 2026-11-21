# [AV-001 AV-002 AV-003 AV-004] Qwen 与基础 NLP 链路

- 负责人角色：组员 1（AI/NLP）
- 模块：`backend/app/ai/`、`knowledge/`
- 前置依赖：AV-006 契约；Qwen API 凭据和模型可达性
- 实现要求：D1–D3 Provider、超时/错误、10 个配置样例；D4–D7 BGE/FAISS、来源 ID、意图路由、会话局部修订。
- 验收标准：真实模型可达证据；10 样例合法配置；无结果和超时可识别；追问只修改指定字段。
- 预计开发阶段：D1–D7；P0
