# 参与开发

五人按 `docs/team-responsibilities.md` 认领角色任务。分支用 `feature/<issue-id>-<short-name>`；向 `main` 提交 PR，说明需求编号、实现、测试命令和结果。不得直接提交密钥、`.env`、数据库或模型缓存。`main` 应保持健康检查可用。

接口先改 `backend/app/schemas/models.py`，再运行 `python scripts/export_contracts.py`；前端不得手改生成类型。算法不得执行模型生成的代码，指标和轨迹只能来自实际执行。新增功能要补一个能验证行为的测试。发现异常要保留输入、seed 和可复现步骤。

本地检查：`cd backend; python -m pytest -q; python -m ruff check .`，根目录运行 `python scripts/export_contracts.py --check`，`cd frontend; npm ci; npm run build`。代码评审至少检查契约兼容、资源边界、错误提示和 README 是否更新。
