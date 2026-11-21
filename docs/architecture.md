# 系统架构与契约

```mermaid
flowchart LR
  U[用户] --> V[Vue 3 工作台]
  V --> A[FastAPI REST / Pydantic]
  A --> C[会话与实验编排]
  C --> Q[Qwen Provider]
  C --> R[BGE + FAISS 检索]
  C --> E[白名单排序执行器]
  E --> X[校验与轨迹]
  C --> DB[(SQLite)]
  X --> DB
  DB --> F[评测脚本]
```

```mermaid
flowchart TD
  S[schemas/ 契约] --> AI[ai/ NLP]
  S --> EN[engine/ 排序与校验]
  AI --> SV[services/ 编排]
  EN --> SV
  SV --> API[api/ REST]
  API --> FE[frontend/ 展示]
  API --> EV[evaluation/ 评测]
```

```mermaid
sequenceDiagram
  participant U as 用户
  participant F as Vue
  participant A as FastAPI
  participant Q as Qwen
  participant E as 执行器
  participant D as SQLite
  U->>F: 自然语言请求
  F->>A: parse
  A->>Q: 约束解析
  Q-->>A: 配置 JSON
  A-->>F: 校验后的配置供确认
  F->>A: run(配置)
  A->>E: 白名单执行与验证
  E-->>A: 真实指标与轨迹
  A->>D: 保存配置、结果
  A-->>F: 统一响应
```

```mermaid
stateDiagram-v2
  [*] --> INPUT
  INPUT --> INTENT_CLASSIFY
  INTENT_CLASSIFY --> KNOWLEDGE_QA
  INTENT_CLASSIFY --> EXPERIMENT_PARSE
  EXPERIMENT_PARSE --> SCHEMA_VALIDATE
  SCHEMA_VALIDATE --> TOOL_ROUTE: 合法
  SCHEMA_VALIDATE --> ONE_REPAIR_ATTEMPT: 非法
  ONE_REPAIR_ATTEMPT --> SCHEMA_VALIDATE: 一次重试
  ONE_REPAIR_ATTEMPT --> USER_ERROR: 仍非法
  TOOL_ROUTE --> EXECUTE
  EXECUTE --> RESULT_VALIDATE
  RESULT_VALIDATE --> EXPLAIN
  EXPLAIN --> SAVE
  SAVE --> PRESENT
```

```mermaid
flowchart LR
  C[ExperimentConfig] --> G[固定 seed/显式数组生成]
  G --> E[注册表执行器]
  E --> M[比较/交换/耗时]
  E --> T[TraceEvent 限额]
  E --> V[输出正确性校验]
  M --> R[ExperimentResult]
  T --> R
  V --> R
  R --> P[前端播放/报告/评测]
```

前端只调用 `/api/v1`；`contracts/openapi.json` 是接口快照，`frontend/src/types/contracts.ts` 从 Pydantic 导出。D1 实际功能为 health、algorithms、run；其余五个约定端点固定返回 501，状态码见 `docs/api-contracts.md`。模型仅生成配置与解释，不执行生成代码，也不产生实测指标。
