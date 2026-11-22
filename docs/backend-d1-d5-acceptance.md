# 组员 3 D1–D5 验收记录

## D1 契约与依赖

Pydantic 是公共契约源；`scripts/export_contracts.py` 生成 JSON Schema、OpenAPI 和 TypeScript。`ExperimentConfig` 当前只允许 `bubble_sort`，注册表中只有它标记为可执行。`ParseRequest/ParseResult` 已定义，但仓库没有 Qwen Provider 或 RAG 实现。`ConversationState` 只有基础会话字段，尚无持久化状态或结构化差异。`ExperimentResult` 公共响应保持不变，复现元数据保存在数据库记录中。现有文档把 GET 实验标为 501；本阶段已实现为 200/404。

模块边界：组员 1 提供返回 `ParseResult` 的解析函数；组员 2 提供排序执行器；组员 3 在 API 校验配置、检查可执行白名单、执行并保存结果。解析函数通过 `app.state.parse_provider` 接入，输入为 `ParseRequest`，输出必须通过 `ParseResult.model_validate`。

工具请求示例：`{"text":"使用冒泡排序对 20 个随机整数进行排序。"}`。Mock 解析响应示例：`{"config":{"algorithm":"bubble_sort","input":{"size":20,"seed":42}},"source":"mock","requires_confirmation":true}`。客户端确认后将 `config` 传给 `POST /api/v1/experiments/run`，再以返回的 `run_id` 请求 `GET /api/v1/experiments/{run_id}`。

## D2–D4 实现与验证

SQLite 路径由 `ALGOVERSE_DB_PATH` 配置，默认 `algoverse.db`；`.gitignore` 排除 `*.db`。记录保存配置、输入、输出、指标、验证、受限轨迹、seed、算法版本、执行环境、状态和时间；模型相关版本留空。事务由 SQLAlchemy `Session.begin()` 管理。GET 不存在的记录返回 404 `NOT_FOUND`。

成功和错误响应均使用 `data/error/request_id` 封套；响应头 `X-Request-ID` 与封套一致。422 `VALIDATION_ERROR`、404 `NOT_FOUND`、409 `CONTEXT_CONFLICT`、503 `MODEL_UNAVAILABLE`、504 `MODEL_TIMEOUT`、500 `INTERNAL_ERROR` 已建立全局映射。解析服务尚不存在时返回 501 `NOT_IMPLEMENTED`。错误日志只记录请求 ID 和异常类型，不写异常正文或环境变量。

Mock 测试覆盖自然语言请求 → `ParseResult` 校验 → 真实冒泡排序 → SQLite → run_id 查询；真实 Qwen 调用**未验证**，因为仓库没有 Provider。HTTP 测试在本地事件循环环境中卡住，未计为通过；现有项目开关 `ALGOVERSE_SKIP_HTTP_TEST=1` 可跳过。直接服务与数据库测试已运行。尚无会话状态管理，409 映射仅为接口约定，未声称冲突流程已实现。

## D5 交接

组员 1：提供符合 `ParseRequest → ParseResult` 的 Qwen Provider，并明确超时、不可用及版本元数据。组员 2：当前只有冒泡排序可执行；新增排序算法须先完成测试并更新注册表、Pydantic 白名单和生成契约。组员 4：使用生成的 `frontend/src/types/contracts.ts` 与 `data/error/request_id` 封套；解析后由用户确认配置再调用 run。组员 5：可通过 run_id 查询真实输出、指标和验证结果；模型版本字段当前为空。

运行命令：在 `backend` 下运行 `python -m pytest -q`；在仓库根目录运行 `python scripts/export_contracts.py --check`。当前环境需设置 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，HTTP 事件循环不可用时再设置 `ALGOVERSE_SKIP_HTTP_TEST=1`。前端检查命令为 `npm run build`。

D6–D10 优先对接 Qwen Provider、会话状态和组员 2 测试通过的新执行器，再做真实 HTTP 端到端验收。未提前实施这些业务功能。
