# AlgoVerse

基于大语言模型的智能算法问答、实验规划与交互验证平台。当前后端可执行冒泡排序、保存 SQLite 实验结果，并提供 D6 单进程会话服务。真实 Qwen Provider、RAG、另外三种排序、对比、报告与科研评测尚未实现。P1/P2 边界见 `docs/requirements.md`。

## 技术栈与架构

Vue 3 + TypeScript + Vite + Element Plus；FastAPI + Pydantic + SQLite/SQLAlchemy；计划接入 Qwen 兼容 API、BGE/FAISS、SVG/ECharts。模块化单体结构及数据流见 `docs/architecture.md`。算法由确定性白名单执行，模型只负责解析、规划和解释。

## Windows 安装与启动

需要 Python 3.9+、Node.js 22+、npm 10+。在仓库根目录运行：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
cd frontend
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`。API 文档：`http://127.0.0.1:8000/docs`；健康检查：`http://127.0.0.1:8000/api/v1/health`。D1 可在页面输入 `3,1,2` 并运行冒泡排序。前端 Vite 将 `/api` 代理到本地后端。

## 环境变量与测试

`ALGOVERSE_DB_PATH` 指定 SQLite 文件；`ALGOVERSE_SESSION_TTL_SECONDS` 和 `ALGOVERSE_MAX_SESSIONS` 配置单进程内存会话。不要提交 `.env`。`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL` 待组员 1 Provider 接入后才生效。

```powershell
cd backend
python -m pytest -q
python -m ruff check .
cd ..
python scripts/export_contracts.py --check
cd frontend
npm run build
```

契约源是 `backend/app/schemas/models.py`，生成文件位于 `contracts/` 和 `frontend/src/types/contracts.ts`。接口状态与异常见 `docs/api-contracts.md`。

## 协作与进度

五人职责和第一周任务见 `docs/team-responsibilities.md`；每人四份、按五天周期执行的详细指导见 `docs/guides/README.md`；20 天路线和硬验收见 `docs/development-roadmap.md`；PR 规范见 `CONTRIBUTING.md`。当前完成 D6 后端会话与 SQLite 链路，真实 Qwen Provider 和其他排序算法待组员交付。D7 未通过 P0 则不开始 P1，D12 冻结 P0 新功能。暂不提供开源许可证，待项目所有者确定。

## 当前 API

`POST /api/v1/conversations` 创建会话；`GET /api/v1/conversations/{session_id}` 查询；`POST /api/v1/conversations/{session_id}/revise` 修订明示字段。`POST /api/v1/experiments/run` 运行并保存；`GET /api/v1/experiments/{run_id}` 查询结果。`POST /api/v1/experiments/parse` 等待组员 1 Provider，现仅 Mock 测试通过。已有会话解析须传 `confirmed_changes`；关联会话的运行配置须与已确认配置一致。会话默认 30 分钟过期、最多 100 个；演示使用单 Worker。错误统一返回 `data/error/request_id`。详见 `docs/api-contracts.md`。
