# 组员 3 D1–D5 验收记录

## D1 契约与依赖

Pydantic 是公共契约源；`scripts/export_contracts.py` 生成 JSON Schema、OpenAPI 和 TypeScript。`ExperimentConfig` 当前只允许 `bubble_sort`，注册表中只有它标记为可执行。`ParseRequest/ParseResult` 已定义，但仓库没有 Qwen Provider 或 RAG 实现。`ConversationState` 只有基础会话字段，尚无持久化状态或结构化差异。`ExperimentResult` 公共响应保持不变，复现元数据保存在数据库记录中。现有文档把 GET 实验标为 501；本阶段已实现为 200/404。

模块边界：组员 1 提供返回 `ParseResult` 的解析函数；组员 2 提供排序执行器；组员 3 在 API 校验配置、检查可执行白名单、执行并保存结果。解析函数通过 `app.state.parse_provider` 接入，输入为 `ParseRequest`，输出必须通过 `ParseResult.model_validate`。

工具请求示例：`{"text":"使用冒泡排序对 20 个随机整数进行排序。"}`。Mock 解析响应示例：`{"config":{"algorithm":"bubble_sort","input":{"size":20,"seed":42}},"source":"mock","requires_confirmation":true}`。客户端确认后将 `config` 传给 `POST /api/v1/experiments/run`，再以返回的 `run_id` 请求 `GET /api/v1/experiments/{run_id}`。

## D2–D4 实现与验证

SQLite 路径由 `ALGOVERSE_DB_PATH` 配置，默认 `algoverse.db`；`.gitignore` 排除 `*.db`。记录保存配置、输入、输出、指标、验证、受限轨迹、seed、算法版本、执行环境、状态和时间；模型相关版本留空。事务由 SQLAlchemy `Session.begin()` 管理。GET 不存在的记录返回 404 `NOT_FOUND`。

成功和错误响应均使用 `data/error/request_id` 封套；响应头 `X-Request-ID` 与封套一致。422 `VALIDATION_ERROR`、404 `NOT_FOUND`、409 `CONTEXT_CONFLICT`、503 `MODEL_UNAVAILABLE`、504 `MODEL_TIMEOUT`、500 `INTERNAL_ERROR` 已建立全局映射。解析服务尚不存在时返回 501 `NOT_IMPLEMENTED`。错误日志只记录请求 ID 和异常类型，不写异常正文或环境变量。

Mock HTTP 测试覆盖自然语言请求 → `ParseResult` 校验 → 真实冒泡排序 → SQLite → run_id 查询，已通过；真实 Qwen 调用**未验证**，因为仓库没有 Provider。尚无会话状态管理，409 映射仅为接口约定，未声称冲突流程已实现。

## D5 交接

组员 1：提供符合 `ParseRequest → ParseResult` 的 Qwen Provider，并明确超时、不可用及版本元数据。组员 2：当前只有冒泡排序可执行；新增排序算法须先完成测试并更新注册表、Pydantic 白名单和生成契约。组员 4：使用生成的 `frontend/src/types/contracts.ts` 与 `data/error/request_id` 封套；解析后由用户确认配置再调用 run。组员 5：可通过 run_id 查询真实输出、指标和验证结果；模型版本字段当前为空。

运行命令：在 `backend` 下运行 `python -m pytest -q`；在仓库根目录运行 `python scripts/export_contracts.py --check`。前端检查命令为 `npm run build` 和 `npm run typecheck`。

## D1–D5 工程验收补齐（2026-11-22）

环境：Windows、Python 3.9.13、pytest 7.1.2、httpx 0.28.1、FastAPI 0.120.1、SQLAlchemy 2.0.58、Ruff 0.17.6、Node 24.22.0、npm 11.19.1。后端依赖由 `backend/pyproject.toml` 声明；前端按 `frontend/package.json` 执行 `npm install`，新增 `package-lock.json`。测试数据库由 autouse fixture 按测试隔离到临时目录。

先前卡顿的最小复现为 `asyncio.run(asyncio.sleep(0))`，在受限执行环境内卡住，在正常执行环境中立即完成；与 FastAPI、httpx、SQLite 代码无关。移除 6 个 HTTP 测试的环境跳过标记，在可运行 asyncio 的环境下运行 `python -m pytest -vv`：**14 passed，0 failed，0 skipped**。原先跳过的 `test_http_round_trip`、`test_persist_and_reload`、`test_missing_and_invalid`、`test_transaction_failure_has_no_record`、`test_mock_parse_to_real_execution`、`test_model_timeout` 均通过。未安装 `pytest-asyncio`，现有同步 TestClient 测试不需要它。

另外实际启动 Uvicorn 并向 localhost 发请求：health 200、algorithms 200、run 200（输入 `[3,1,2]`，输出 `[1,2,3]`，run_id `50bb18e7-6f70-4704-a9a7-ff7128af78de`）、GET 相同 run_id 200，响应数据一致，临时 SQLite 文件存在。该 run_id 是一次性测试记录，服务器退出后测试数据库已清理。API 自动化测试同时覆盖 404、422、500、504 和 request_id。

`python -m ruff check backend/app/main.py backend/app/services/experiment.py backend/app/db backend/tests`：通过。全仓 `python -m ruff check backend/app backend/tests` 最初报告 43 项，其中多数在此前已有的 Schema 和组员 2 排序模块；本次只修复组员 3 文件，不改写其他成员实现。`npm run build` 与 `npm run typecheck`：通过；构建仅有大包体积提示。`python scripts/export_contracts.py --check`：通过，公共契约无变化。

当前阻断：真实 Qwen Provider、模型错误类型与模型/提示词版本元数据尚未交付；组员 2 的其他算法未注册为可执行。组员 1 应提供接受 `ParseRequest`、返回符合 `ParseResult` 的调用入口，区分超时和不可用并提供版本信息。组员 2 应提供测试通过的执行器及能力注册信息，遵循现有 `ExperimentConfig`、`ExperimentResult`、`TraceEvent` 和指标/验证口径。新增算法仍需同步 Pydantic 白名单及生成契约；当前 API 层不需大规模改写。

D6–D10 优先对接 Qwen Provider、会话状态和组员 2 测试通过的新执行器，再做真实 HTTP 端到端验收。未提前实施这些业务功能。
