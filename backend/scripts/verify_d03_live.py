"""AV-M1-D03 十条样例「真实 Qwen 调用」验证脚本。

用法（backend/ 下）：python scripts/verify_d03_live.py
前提：仓库根目录 .env 已配置 QWEN_BASE_URL / QWEN_MODEL / QWEN_API_KEY。
产物：
  artifacts/d03-sample-results-live.json   每条样例的真实结果与逐条判定
  artifacts/d03-live-transcript.jsonl       每次模型调用的脱敏记录

说明：模型输出来自真实 Qwen；配置校验、注册表检查、算法执行是仓库真实代码。
期望值直接取自 D01 样例，不做任何迁就修改；失败项如实记录。
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verify_d03 import req_stub

from app.ai.planner import parse
from app.ai.provider import (
    ProviderConfig,
    QwenProvider,
    new_request_id,
    write_transcript,
)
from app.main import run

FIXTURE = ROOT / "tests" / "fixtures" / "config_samples.json"
OUT = ROOT / "artifacts" / "d03-sample-results-live.json"
TRANSCRIPT = ROOT / "artifacts" / "d03-live-transcript.jsonl"


def make_live_tool_fn(provider):
    """真实 HTTP 调用；每次请求/响应写脱敏 transcript。"""

    def fn(messages, source, rid):
        resp = provider.chat_json(
            messages,
            source=source,
            request_id=rid,
            response_format={"type": "json_object"},
        )
        write_transcript(TRANSCRIPT, request={"messages": messages, "request_id": rid}, response=resp)
        return resp.content

    return fn


def expected_value(config, key):
    if key == "algorithm":
        return str(config.algorithm)
    if key == "values":
        return config.input.values
    if key == "visualization.enabled":
        return config.visualization.enabled
    return getattr(config.input, key, None)


def main():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cfg = ProviderConfig.from_env()
    cfg.check_real_call()
    results = []

    with QwenProvider(cfg) as provider:
        tool_fn = make_live_tool_fn(provider)
        for s in data["samples"]:
            rid = new_request_id()
            out = parse(s["text"], source="qwen", provider=provider, tool_fn=tool_fn, request_id=rid)
            record = {
                "id": s["id"],
                "text": s["text"],
                "expected": s["expected"],
                "actual_status": out.status,
                "actual_error_code": out.error_code,
                "config": out.config.model_dump(mode="json") if out.config else None,
                "repair": {
                    "attempted": out.repair.attempted,
                    "failed": out.repair.failed,
                    "reason": out.repair.reason[:300],
                },
                "source": out.source,
                "request_id": out.request_id,
                "prompt_version": out.prompt_version,
                "raw_model_output": out.raw_model_output[:800],
            }
            record["passed"] = out.status == s["expected"]["status"]
            if out.status == "ok" and out.config is not None:
                result = run(req_stub(), out.config).data
                record["execution"] = {
                    "run_id": result.run_id,
                    "valid": result.validation.valid,
                    "output": result.output,
                    "metrics": result.metrics,
                }
                for key in ("algorithm", "size", "distribution", "seed", "values", "visualization.enabled"):
                    if key in s["expected"]:
                        record["passed"] = record["passed"] and expected_value(out.config, key) == s["expected"][key]
            if "error_code" in s["expected"]:
                record["passed"] = record["passed"] and out.error_code == s["expected"]["error_code"]
            elif "error_code_candidates" in s["expected"]:
                record["passed"] = record["passed"] and out.error_code in s["expected"]["error_code_candidates"]
            results.append(record)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "REAL QWEN CALL — 模型输出来自真实 API",
        "model": cfg.model,
        "base_url": cfg.base_url,
        "note": "期望值取自 D01 样例，未做任何修改；失败项如实保留",
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["passed"]),
            "failed": sum(1 for r in results if not r["passed"]),
        },
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    for r in results:
        print("{} {} status={} error={}".format(
            "PASS" if r["passed"] else "FAIL", r["id"], r["actual_status"], r["actual_error_code"]
        ))


if __name__ == "__main__":
    main()
