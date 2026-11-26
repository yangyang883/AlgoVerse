# 组员1 ↔ 组员3 联调交付（2026-11-26）

针对你提的 5 项联调要求，逐条交付。**我没改你的 `main.py` / `schemas/models.py` / SQLite / services**；`/parse` 路由注入和 HTTP 抓包仍归你。

---

## 1. 调用入口 + 最简单示例

三个文件的实际入口：

| 文件 | 入口 | 作用 |
|---|---|---|
| `app/ai/provider.py` | `QwenProvider.chat_json(messages, source, request_id)` | HTTP 调用、超时/非2xx/无效JSON、脱敏 |
| `app/ai/prompts.py` | `build_parse_messages(text, session)` / `PROMPT_VERSION` | 严格 JSON 提示词，当前 `parse-v1.1.0` |
| `app/ai/planner.py` | `parse(text, source, provider, tool_fn, request_id)` | 校验 + 最多一次修复，返回 `ParseOutcome` |

**给你注入的封装**（新增 `app/ai/integration.py`）：

```python
# 你在 main.py 启动时注入（这行你写，我不动你的文件）
from app.ai.integration import make_parse_provider
app.state.parse_provider = make_parse_provider()   # 默认 source='qwen'，读仓库根 .env
```

你现有 `/parse` 路由不用改：`provider(body)` 接收 `ParseRequest`，返回可被 `ParseResult.model_validate()` 接受的 dict。

**最简单调用示例**（不经过 HTTP，验证模型链路）：

```python
from app.ai.planner import parse
out = parse("请用冒泡排序把3、1、2从小到大排序", source="qwen")
print(out.status, out.config.model_dump(), out.error_code)
```

---

## 2. Planner 返回数据结构

`parse()` 返回 `ParseOutcome` dataclass，字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | str | `ok` / `needs_clarification` / `error` |
| `config` | `ExperimentConfig \| None` | 成功时的配置（已是你的 Pydantic 模型，不是 dict） |
| `source` | str | `qwen`（真实）/ `mock`（离线，显式标注） |
| `requires_confirmation` | 通过 `to_contract_result()` 置 `True` | 配置需用户确认才执行 |
| `error_code` | `str \| None` | 见下表 |
| `error_message` / `clarification` | `str \| None` | 可展示文本 |
| `repair` | `RepairInfo` | `attempted/failed/attempts/reason`，最多 1 次 |
| `request_id` / `prompt_version` / `raw_model_output` | str | 脱敏记录与对账 |

**成功转契约**：`out.to_contract_result()` → `ParseResult(config, source, requires_confirmation=True, session_id=None)`，字段与你远程 main 的四字段契约一致（`session_id` 由你的路由用 `conversations` 回填）。

**错误码 → HTTP 映射**（我适配层已实现，对齐你路由的 catch）：
- `E-QWEN-TIMEOUT` → `TimeoutError` → **504 MODEL_TIMEOUT**
- `E-QWEN-HTTP` / `E-QWEN-NO-CREDENTIAL` → `ConnectionError` → **503 MODEL_UNAVAILABLE**
- `E-SCHEMA-*` / `E-UNKNOWN-ALGORITHM` / `E-PARSE-FAILED` / `E-AMBIGUOUS-INPUT` / 无效JSON → `ValidationError` → **422 VALIDATION_ERROR**，具体 code 在 `error.details.errors[].ctx.code`
- 错误态一律 `data=null`，不塞进 `config`（契合你 `ParseResult.config` 必填）

---

## 3. 7 个待决问题核对结果

详见 `docs/ai-integration-draft.md` 第 5 节。**4 项你已实现解决，剩 3 项需你拍板**：

1. **工具建议出口**（原 Q4）：`ParseResult` 无 `intent/tool_suggestions` 字段。建议本期先不暴露，评测不覆盖。
2. **`/chat` 是否本期接入 RAG**（原 Q7）：`rag.py` + 真实 BGE 索引已就绪；不接就保持 501。
3. **错误码命名对齐**：我的 `E-QWEN-*` / `E-SCHEMA-*` 是否并入你的统一码表；若希望 code 直接进 `error.code`，需你的路由 catch 改一处（你所有）。

---

## 4. 真实 Qwen 环境确认 + 脱敏记录

**能跑**。用你指定的句子实测：

> 请用冒泡排序把3、1、2从小到大排序

- 模型 `qwen-flash`，真实 HTTP 调用 1 次，成功
- 解析出的 config：`algorithm=bubble_sort, input.values=[3,1,2], size=3, visualization.enabled=true`
- `run_experiment(config)` 执行：`output=[1,2,3]`，`comparisons=3, swaps=2`
- `run_id=77a99b80-cf14-45d9-afb1-d6ded3d6aa0a`

产物（均已脱敏，grep 无明文 Key）：
- `backend/artifacts/integration-smoke.json` — 结构化结果
- `backend/artifacts/integration-transcript.jsonl` — 模型请求/响应脱敏记录

**前提**：集成工作区仓库根放 `.env`（`QWEN_BASE_URL` / `QWEN_MODEL` / `QWEN_API_KEY`），已被 `.gitignore` 忽略。我在本地 clone 验证时临时放了 `.env`，跑完已删除，不会误提交。

---

## 5. 共同交付 `/parse → /run → run_id` HTTP 记录

我已证明 parse 出的 config 能被真实执行器跑出 `[1,2,3]`；**HTTP 层抓包请你在集成工作区完成**：

1. 你启动服务并注入：`app.state.parse_provider = make_parse_provider()`
2. `POST /api/v1/experiments/parse` `{"text":"请用冒泡排序把3、1、2从小到大排序"}` → 记录 `ParseResult`（含 `session_id`）
3. `POST /api/v1/experiments/run` 用返回的 config（带 `X-Session-ID` 如有会话）→ 记录 `run_id`
4. `GET /api/v1/experiments/{run_id}` → 记录查询结果
5. 三段请求/响应 + `request_id` 存成 JSON，交组员5归档

如注入时遇到异常映射或字段对不齐，把 `error.code` 和 `request_id` 发我，我按日志定位。

---

## 附：本次新增文件

```
backend/app/ai/integration.py
backend/scripts/integration_smoke.py
backend/tests/test_integration.py          (4 passed)
backend/artifacts/integration-smoke.json
backend/artifacts/integration-transcript.jsonl
docs/ai-integration-draft.md               (新增第5节核对结果)
docs/member1-member3-integration.md        (本文件)
```

全量测试：在 team clone 上 `pytest -q` 需基于远程 main 的新契约；我本地 clone 是旧版（parse 501），故仅对我新增模块跑测试（4 passed）。合并到你集成工作区后请再跑一次全量。
