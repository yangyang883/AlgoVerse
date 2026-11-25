# 组员1 AI/NLP D01–D05 交付说明

生成时间：2026-11-25。范围：仅 D01–D05，未做 D06–D20。
更新：2026-11-25 13:40 后补入真实 Qwen 调用验证结果（`.env` 到位后）。

## 一、完成情况对照

| 日 | 计划要求 | 实现状态 |
|---|---|---|
| D01 | 10 条配置样例 + 工具请求样例 + 契约确认草案 | 完成。样例在 `backend/tests/fixtures/config_samples.json`（10 条）与 `tool_request_samples.json`（4 条）；契约草案 `docs/ai-integration-draft.md`（含 7 个待组员3确认问题） |
| D02 | `ai/provider.py` HTTP/超时/非2xx/无效JSON + 脱敏记录 + 失败样例 | 完成。`backend/app/ai/provider.py`；13 项测试通过（含 `.env` 自动加载）；脱敏样例 `backend/tests/fixtures/provider_mock_transcript.jsonl`；真实调用已通过：`backend/scripts/provider_smoke.py`（qwen-flash，约 300ms），脱敏记录 `backend/artifacts/provider_smoke.jsonl` |
| D03 | 提示词 + `ai/planner.py` + Pydantic 校验 + 一次修复 + parse→run 闭环 | 完成。`prompts.py`（parse-v1.1.0）、`planner.py`；10 条样例离线 Mock 10/10、真实 Qwen 10/10。逐条记录 `backend/artifacts/d03-sample-results.json`（离线）与 `d03-sample-results-live.json`（真实） |
| D04 | 25–40 条人工复核知识条目，含元数据 | 完成。40 条，分 `knowledge/documents/sorting-knowledge.json`（20）与 `general-algorithms.json`（20）；均含 source_id/title/topic/version/source_url；待组员5复核来源 |
| D05 | BGE + FAISS 离线索引 + Top-k 验证 | 完成（真实 BGE 已验证，离线对照保留）。`backend/app/ai/rag.py`、`knowledge/scripts/build_index.py`；真实模型 `BAAI/bge-small-zh-v1.5`（512 维）索引 40 条 → `knowledge/index/faiss_index_bge.bin`；4 查询 Top-4 全部命中且 Top-1 精准；9 项检索测试通过；真实样例 `backend/artifacts/d05-retrieval-samples-bge.json` |

## 二、验证结果

- 后端全量 `pytest -q`：**37 passed**（含仓库原有 11 项，无回归）。
- D03 离线：10/10 通过（配置校验与真实算法执行为仓库代码，模型响应用规则型 Mock）。
- D03 真实 Qwen：10/10 通过，`source=qwen`、模型 `qwen-flash`；每条都有 request_id、prompt_version 与真实算法执行结果。首轮 9/10，CFG-10 因提示词未定义错误码规则被误标为 `E-UNKNOWN-ALGORITHM`；提示词升版 parse-v1.1.0 补上「字段/参数错误 → E-SCHEMA-*」与动画边界规则后重跑通过。
- D05 真实 BGE：模型从国内镜像下载（官方域名被代理 502），索引 40 条/512 维；4 个查询 Top-4 全部返回可核查来源，Top-1 分别为「快速排序最坏情形」(0.7883)、「冒泡排序时间复杂度前提」(0.8293)、「Dijkstra 算法前提与复杂度」(0.5655)、「同输入公平对照的前提」(0.7126)。
- D05 离线对照：原 `faiss_index.bin` 未覆盖，仍返回可核查来源；无结果/空查询返回空 sources 与明确提示。
- ruff：无致命错误（F/E 类为 0）；剩余风格提示与仓库原有代码同类，未改动他人代码。

## 三、关键边界与已知限制

1. **真实 Qwen 已验证，但额度有限**：`.env` 在工作区根目录，Provider 会自动加载（系统环境变量优先，不覆盖）。`provider_smoke.py` 与 D03 十条样例均已真实调用成功；脱敏记录不含 Key。后续如需大批量评测请先确认额度。
2. **两套索引并存，勿混用**：真实 BGE 索引 `faiss_index_bge.bin`（`embedding=bge-real`）与离线哈希索引 `faiss_index.bin`（`embedding=offline-hash`）各自独立；`load_index(path, use_real_bge=True/False)` 必须与索引类型匹配，否则维度校验或检索语义不一致。真实模型已缓存本机（约 92MB），换机器需重新下载；官方 HuggingFace 域名在本机被代理拦截，请用 `HF_ENDPOINT=https://hf-mirror.com`。
3. **契约窄**：仓库当前 `ExperimentConfig.algorithm` 只接受 `bubble_sort`，分布只 `random/sorted/reversed`，`ParseResult` 无错误态字段。CFG-09（快速排序）等样例按当前契约期望报错，待组员2/3扩展后需更新期望。
4. **未接入路由**：`main.py` 的 `/chat` 与 `/experiments/parse` 仍返回 501（属组员3所有权）。本组模块已就绪，待组员3在路由中调用 `app.ai.planner.parse()` 与 `app.ai.rag.load_index()`。
5. **知识来源待复核**：40 条来源 URL 为人工整理初稿，需组员5核对；部分概念条目来源指向 Wikipedia 通用页，可替换为更精确链接。

## 四、需要你（或团队）提供的内容

### 真实模型闭环（已由用户提供 `.env`，已验证）
1. `QWEN_BASE_URL`：已配置（`https://dashscope.aliyuncs.com/compatible-mode/v1`）。
2. `QWEN_MODEL`：已配置（`qwen-flash`）。
3. `QWEN_API_KEY`：已配置（仅存本地 `.env`，未提交、未写入任何产物）。
4. **仍待确认：额度与超时预算**——`QWEN_TIMEOUT` 当前默认 30s；真实验证共发起约 12 次请求，后续批量评测请确认上限。

### 建议提供（提升质量）
5. ~~真实 BGE 环境~~：已由用户授权并安装 `sentence-transformers`，已下载 `BAAI/bge-small-zh-v1.5`，真实索引与检索样例均已产出（见上）。
6. **组员3确认**：`docs/ai-integration-draft.md` 中 7 个契约问题（错误码映射、source 取值、错误态承载、工具建议端点、request_id、会话切片、路由接入时机）。
7. **组员5复核**：40 条知识条目的来源 URL 与内容准确性。
8. **样例扩展决策**：快速排序等三种算法何时在注册表中启用；启用后更新 `config_samples.json` 中 CFG-09 的期望。

## 五、关键文件路径

```
backend/app/ai/{__init__,errors,provider,prompts,planner,rag}.py
backend/app/ai/__init__.py
backend/tests/{test_provider,test_planner,test_rag}.py
backend/tests/fixtures/{config_samples,tool_request_samples}.json, provider_mock_transcript.jsonl
backend/scripts/{provider_smoke,verify_d03,verify_d03_live,verify_d05}.py
backend/artifacts/{d03-sample-results,d03-sample-results-live,d05-retrieval-samples,d05-retrieval-samples-bge}.json
backend/artifacts/{provider_smoke.jsonl,d03-live-transcript.jsonl}
knowledge/documents/{sorting-knowledge,general-algorithms}.json
knowledge/index/{faiss_index.bin,faiss_index.meta.json}                # 离线对照
knowledge/index/{faiss_index_bge.bin,faiss_index_bge.meta.json}       # 真实 BGE
knowledge/scripts/build_index.py
docs/ai-integration-draft.md
docs/member1-d01-d05-delivery.md
```
