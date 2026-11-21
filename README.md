# AlgoVerse

基于大语言模型的智能算法问答、实验规划与交互验证平台。此仓库当前为 D1 工程骨架：可运行冒泡排序手动实验、真实指标/轨迹与验证，提供 Vue 页面和健康检查。Qwen、RAG、另外三种排序、存储、对比、报告与科研评测属于后续 P0，尚未实现。P1/P2 边界见 `docs/requirements.md`。

## 技术栈与架构

Vue 3 + TypeScript + Vite + Element Plus；FastAPI + Pydantic；计划引入 SQLite/SQLAlchemy、Qwen 兼容 API、BGE/FAISS、SVG/ECharts。模块化单体结构及数据流见 `docs/architecture.md`。算法由确定性白名单执行，模型只负责解析、规划和解释。

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

`.env.example` 列出后续 Qwen 和 SQLite 配置；D1 不读取 Qwen Key。不要提交 `.env`。`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL` 待 D2 Provider 接入后才生效。

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

五人职责和第一周任务见 `docs/team-responsibilities.md`；20 天路线和硬验收见 `docs/development-roadmap.md`；PR 规范见 `CONTRIBUTING.md`。当前只完成 D1 手动配置闭环。D2 优先 SQLite 追溯和 Qwen Provider，D3 联通自然语言解析并实测模型可达性。D7 未通过 P0 则不开始 P1，D12 冻结 P0 新功能。暂不提供开源许可证，待项目所有者确定。
