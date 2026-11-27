# D3 真实执行留证规范

- 对应任务：AV-M5-D03　｜　版本：v0.3　｜　维护：组员 5　｜　更新：2026-11-27
- 闸门要求：**Qwen → 配置 → 真实执行** 的请求/响应可复演；失败同样留证；Mock 与真实结果物理分离。

## 1. 当前状态（诚实记录）

| 项 | 状态 | 说明 |
|---|---|---|
| 留证规范与记录结构 | 已完成 | 本文件 + `scripts/run_eval.py` 自动生成 manifest |
| 采集脚本 | 已完成（mock 验证通过） | 见 D5 |
| 真实 Qwen 模型调用 | **模型侧已就绪** | 组员 1 在 PR #6 留存 `qwen-flash` 真实调用 10/10 证据；这不等于本评测 D3 链路已通过 |
| Provider / `/parse` 接线 | **待接入** | 组员 3 负责 `/parse` 接线；组员 1 不改 `main.py`、不加启动钩子，只维护 Provider / Planner / RAG；未注入时返回 501 |
| 澄清/错误响应映射 | **已定案** | 409 `CONTEXT_CONFLICT`；504 `MODEL_TIMEOUT`；503 `MODEL_UNAVAILABLE`；非法 JSON / Schema / 不支持算法为 422 `VALIDATION_ERROR`。业务错误走 `error` 信封，`E-*` 仅内部日志，`details` 只写真实字段路径 |
| 五题路径与字段 | **已按契约改题** | KNW-0001 / CEX-0001 的 `/chat` 暂为 `BLOCKED`（501 不通过）；CFG-0001 / INV-0001 用 `/parse` + `text`；EXE-0001 用 `/run` + 裸 `ExperimentConfig` + `input.values` |
| 四排序 HTTP 接入与验收 | **组员 3 推进中，逐算法验收** | 先检查注册、Schema、参数、TraceEvent 和指标兼容性，再做真实 `/run` 验收；仅通过的算法标为可执行。CEX-0001 单测只作阶段性证据，接入后保存 `run_id`、轨迹和验证结果；`/chat` 仍单独记 `BLOCKED` |
| 本地 API（`/api/v1/*`） | **代码已交付，待启动联调** | 组员 3 的 D1–D6 已合入最新 `main`；服务未启动时脚本记录 `CONNECTION_ERROR` |
| D3 闸门 | **未通过：待 Provider 接入** | 模型本身不再记为“未就绪”；必须补齐 Qwen → 配置 → 真实执行的完整留证 |

真实模式的两类阻断必须分开记录：① 服务未启动 → `CONNECTION_ERROR`；② 服务已启动但 Provider 未注入 → HTTP 501 `NOT_IMPLEMENTED`。不得把后者写成模型不存在，也不得把 PR #6 的独立模型调用证据当成本评测的端到端证据。

在真实接口可达前，**不得**把任何 mock 结果写成"真实成功率"。

## 2. 一次 D3 留证必须包含

| 类别 | 字段 | 来源 |
|---|---|---|
| 环境 | `run_id`、开始/结束时间、主机名、OS、Python 版本、git commit | 脚本自动写 `manifest.json` |
| 模型 | `model_id`、`temperature`、`top_p`、`max_tokens` | 环境变量 / 组员1 提供 |
| RAG | `embedding_model`、`kb_version`、`top_k` | 环境变量 |
| 提示词 | `prompt_version` | 环境变量 |
| 数据 | `dataset_path`、`dataset_sha256`、`dataset_version` | 脚本自动计算 |
| 请求 | 完整请求体与必要请求头；`/run` 的会话 ID 只放在 `X-Session-ID` | 脚本原样存 `responses.jsonl` |
| 响应 | HTTP 状态、原始响应体、耗时 ms、`request_id` | 脚本原样存 |
| 执行 | `run_id`（服务端返回）、`config`、`metrics`、`validation`、`trace_truncated` | 响应体 `data` 段 |
| 失败 | 错误类、错误码、原始报文 | `failures.jsonl` |

## 3. 运行命令

```powershell
# 0) 先确认服务可达（不产生留证）
curl.exe -s http://127.0.0.1:8000/api/v1/algorithms

# 1) 试跑一题，确认真实链路
python evaluation/scripts/run_eval.py --mode real --limit 1 --run-id d3-probe-01

# 2) 五类各一题
python evaluation/scripts/run_eval.py --mode real --limit 5 --run-id d3-seed-01

# 3) 全量种子题
python evaluation/scripts/run_eval.py --mode real --run-id d3-seed-full-01
```

环境变量（PowerShell）：

```powershell
$env:ALGOVERSE_BASE_URL="http://127.0.0.1:8000"
$env:QWEN_MODEL="qwen-flash"
$env:QWEN_TEMPERATURE="0.2"
$env:EMBEDDING_MODEL="bge-small-zh-v1.5"
$env:KB_VERSION="kb-0.1"
$env:PROMPT_VERSION="prompt-0.1"
```

## 4. 产物位置

```
evaluation/results/raw/<run_id>/
├── manifest.json     # 环境 + 模型 + 数据指纹
├── responses.jsonl   # 逐题、逐步原始响应（含失败）
├── failures.jsonl    # 仅失败项，便于错误分析
└── summary.json      # 成功/失败计数，按类别与错误类聚合
```

`manifest.json` 中 `mode` 字段区分 `real` / `mock` / `dry-run`，mock 目录名强制带 `mock-` 前缀，禁止改名为 real。

## 5. 失败也必须记录

- 连接拒绝、超时、5xx、信封缺字段、返回非 JSON、执行异常，全部写进 `responses.jsonl` 与 `failures.jsonl`。
- 失败项 `error_class` 取值：`CONNECTION_ERROR` / `TIMEOUT` / `HTTP_<code>` / `INVALID_JSON` / `ENVELOPE_INVALID`。
- 不得重跑后只保留成功记录；重跑新建 `run_id`，旧记录保留。

## 6. D3 闸门自检表

| 检查项 | 判定 |
|---|---|
| 自然语言 → `config` 结构完整且合法 | 人工看 `data.config` |
| `config` → 真实执行并返回 `run_id` | `data.run_id` 非空 |
| 指标来自执行器而非模型 | `metrics` 与 `trace` 可对上 |
| 至少一条失败记录在案 | `failures.jsonl` 非空 |
| 同一命令可复演出相同 `case_id` 集合 | 两次 `run_id` 的 case 列表一致 |
| 模型/温度/seed/版本齐全 | `manifest.json` 字段无空值 |

六项全过才算 D3 通过；当前真实分支待本地服务启动及 Provider 接入。服务未启动与 Provider 未注入分别按 `CONNECTION_ERROR` 和 HTTP 501 留证，不能合并为同一种“模型未就绪”。
