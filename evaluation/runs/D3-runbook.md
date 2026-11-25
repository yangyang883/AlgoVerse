# D3 真实执行留证规范

- 对应任务：AV-M5-D03　｜　版本：v0.1　｜　维护：组员 5
- 闸门要求：**Qwen → 配置 → 真实执行** 的请求/响应可复演；失败同样留证；Mock 与真实结果物理分离。

## 1. 当前状态（诚实记录）

| 项 | 状态 | 说明 |
|---|---|---|
| 留证规范与记录结构 | 已完成 | 本文件 + `scripts/run_eval.py` 自动生成 manifest |
| 采集脚本 | 已完成（mock 验证通过） | 见 D5 |
| 真实 Qwen 推理服务 | **未就绪** | 等待组员 1 提供可达地址与额度；当前无 `QWEN_BASE_URL` |
| 本地 API（`/api/v1/*`） | **未就绪** | 等待组员 3 的 Mock/OpenAPI 与可启动服务 |
| D3 闸门 | **未通过** | 原因是依赖未就绪，不是脚本缺失 |

在真实接口可达前，**不得**把任何 mock 结果写成"真实成功率"。

## 2. 一次 D3 留证必须包含

| 类别 | 字段 | 来源 |
|---|---|---|
| 环境 | `run_id`、开始/结束时间、主机名、OS、Python 版本、git commit | 脚本自动写 `manifest.json` |
| 模型 | `model_id`、`temperature`、`top_p`、`max_tokens` | 环境变量 / 组员1 提供 |
| RAG | `embedding_model`、`kb_version`、`top_k` | 环境变量 |
| 提示词 | `prompt_version` | 环境变量 |
| 数据 | `dataset_path`、`dataset_sha256`、`dataset_version` | 脚本自动计算 |
| 请求 | 完整请求体（含 `session_id`） | 脚本原样存 `responses.jsonl` |
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
$env:QWEN_MODEL="qwen-plus"
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

六项全过才算 D3 通过；当前第 1 项起的真实分支全部阻塞在服务可达性上。
