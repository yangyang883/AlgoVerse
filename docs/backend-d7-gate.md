# 组员 3 D7 联调闸门记录（2026-11-23）

## 仓库与依赖

分支 `组员3`，本次检查起点 `a1b654c`。其他成员已有未提交文档和 ZIP 均保留。仓库 `backend/app` 没有 Qwen Provider 或 RAG 模块；`engine/sorting` 只有 `bubble.py`。`GET /api/v1/algorithms` 实测仅 `bubble_sort` 可执行，其余三种排序为 `executable=false`。前端 `App.vue` 只调用 health 与手工冒泡 run；聊天、来源引用、会话修订和 SVG 播放尚无页面流程。

## 闸门逐项结果

| 项目 | 状态 | 实际证据或缺口 |
|---|---|---|
| `/chat` 真实问答 | BLOCKED | localhost 请求返回 501；组员 1 Provider/RAG 未交付。 |
| `/parse` 真实 Qwen | BLOCKED | localhost 请求返回 501；无 Provider。Mock 回归测试通过不计入真实联调。 |
| `/run` 冒泡排序 | PASS | localhost 200；固定 seed 42，规模 30，真实执行。 |
| SQLite 保存与 run_id 读取 | PASS | localhost run/get 均 200，响应数据相同，隔离临时数据库文件存在。 |
| 多轮局部修订 | PASS（手工 API） | 创建会话 200，修订 size 20→30 后 seed 仍为 42；带 `X-Session-ID` 运行后 `last_run_id` 与结果一致。自然语言多轮仍 BLOCKED。 |
| RAG 来源 | BLOCKED | 无检索模块和真实来源 ID；未生成虚构引用。 |
| 四排序 | BLOCKED | 仅冒泡可执行，其他三种能力标记为不可执行。 |
| 前端展示 | NOT TESTED | `npm run typecheck`、`npm run build` 通过；代码只有手工冒泡结果及 JSON 轨迹，未进行浏览器人工验收，聊天/RAG/SVG 不存在。 |
| 错误响应 | PASS（已有范围） | localhost 缺失 run_id 返回 404；pytest 覆盖 409、422、500、504 和 request_id。 |
| CI 全组闸门 | BLOCKED | 未运行 GitHub CI；全后端 Ruff 仍有组员 2 文件中的 8 项。 |

## 调用契约与交接

组员 1：提供接受 `ParseRequest{text,session_id?,confirmed_changes?}`、返回合法 `ParseResult{config,source,requires_confirmation}` 的真实 Qwen Provider，以及 `/chat` 所需 RAG 结果和来源 ID。已有会话的追问必须取得用户明确确认的字段级变更，例如 `confirmed_changes:{"input.size":30}`；完整配置差异不能当作授权。模型返回的 session_id 不作为后端状态。超时和不可用需区分。

组员 2：提交通过正确性、指标和轨迹测试的插入、快速、归并排序执行器，再更新可执行注册信息、Pydantic 白名单与生成契约。当前 Ruff 剩余：`engine/registry.py` I001 ×1；`engine/sorting/bubble.py` UP035 ×2、UP006 ×5。未修改这些文件。

组员 4：现可调用 `POST /api/v1/conversations` 创建会话；`POST /api/v1/conversations/{session_id}/revise` 提交 `{"changes":{"input.size":30}}`；`GET /api/v1/conversations/{session_id}` 读状态。解析入口在 Provider 交付后使用 `POST /api/v1/experiments/parse`，已有会话须传 `session_id` 和已确认的 `confirmed_changes`；使用响应的确认后 `config` 调用 `POST /api/v1/experiments/run`，请求头 `X-Session-ID` 取后端返回的 ID；以返回的 run_id 调用 `GET /api/v1/experiments/{run_id}`。缺上下文和配置冲突为 409，读取 `error.code` 与 `request_id`。当前页面未实现此流程。

组员 5：可用 run_id 查询真实 input/output、comparisons、swaps、validation、trace 和 seed；真实模型版本、RAG 来源及四排序评测样本尚不可用。

## 实际执行命令与结果

- `python -m pytest -q`（backend，正常 Windows 执行环境，pytest cache 指向临时目录）：**25 passed，0 skipped**。测试数据库由 fixture 放在临时目录；受限执行环境的 asyncio 曾卡住，本次未将其结果计为通过。
- `python scripts/export_contracts.py --check`：通过。
- `python -m ruff check backend/app backend/tests --output-format concise`：失败，组员 2 文件 8 项；CI 阻断。
- `npm run typecheck`：通过。
- `npm run build`：通过，有大包体积提示。
- 临时 Uvicorn localhost 请求：health 200；algorithms 返回 1 可执行、3 不可执行；create 200；revise 200（size 30、seed 42）；run/get 200 且数据相同、SQLite 文件存在；会话 last_run_id 一致；无 Provider 的 parse/chat 各 501；缺失 run_id 为 404。服务器与数据库在测试后清理。

**D7 闸门未通过。**真实 Qwen、RAG、四排序、前端完整交互与 CI 尚缺实际通过证据；不进入 D8。
