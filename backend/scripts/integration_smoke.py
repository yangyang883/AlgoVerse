"""组员1 ↔ 组员3 联调：一句话 → /parse 契约 → /run 结果。

用法（backend/ 下）：
    python scripts/integration_smoke.py

前提：仓库根 .env 已配置 QWEN_BASE_URL / QWEN_MODEL / QWEN_API_KEY。
产物：
    artifacts/integration-smoke.json          结构化结果（脱敏）
    artifacts/integration-transcript.jsonl     每次模型调用的脱敏记录

说明：
- 本脚本只调用组员的 run_experiment 函数（不修改任何后端文件），
  用于证明 parse 出的 config 可被真实执行器接受。
- 真正的 /parse → /run → run_id HTTP 链路由组员3在集成工作区完成并抓包。
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai.integration import (
    make_parse_provider,
)
from app.ai.provider import ProviderConfig, QwenProvider, write_transcript
from app.schemas.models import ParseRequest
from app.services.experiment import run_experiment

TEXT = "请用冒泡排序把3、1、2从小到大排序"
TRANSCRIPT = ROOT / "artifacts" / "integration-transcript.jsonl"
OUT = ROOT / "artifacts" / "integration-smoke.json"


def main() -> int:
    cfg = ProviderConfig.from_env()
    cfg.check_real_call()

    transcript_calls = []

    def call_model(messages, source, rid):
        with QwenProvider(cfg) as p:
            resp = p.chat_json(
                messages,
                source=source,
                request_id=rid,
                response_format={"type": "json_object"},
            )
        write_transcript(
            TRANSCRIPT,
            request={"messages": messages, "request_id": rid},
            response=resp,
        )
        transcript_calls.append({
            "request_id": resp.request_id,
            "model": resp.model,
            "source": resp.source,
            "latency_ms": resp.latency_ms,
            "usage": resp.usage,
        })
        return resp.content

    provider = make_parse_provider(
        source="qwen",
        call_model=call_model,
        transcript_path=str(TRANSCRIPT),
    )
    body = ParseRequest(text=TEXT)

    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "REAL QWEN CALL",
        "text": TEXT,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "transcript_calls": transcript_calls,
    }

    try:
        parsed = provider(body)
        record["parse"] = {
            "status": "ok",
            "contract": parsed,
            "note": "source=requires_confirmation 已就位；session_id 由组员3路由回填",
        }
        # 用真实执行器验证 config 可执行（不修改后端文件）
        from app.schemas.models import ExperimentConfig
        config = ExperimentConfig.model_validate(parsed["config"])
        result = run_experiment(config)
        record["run"] = {
            "status": "ok",
            "run_id": result.run_id,
            "input": result.input,
            "output": result.output,
            "metrics": result.metrics,
            "validation": result.validation.model_dump(mode="json"),
        }
    except TimeoutError as exc:
        record["parse"] = {
            "status": "mapped_error",
            "route_status": 504,
            "code": "MODEL_TIMEOUT",
            "detail": str(exc),
        }
    except ConnectionError as exc:
        record["parse"] = {
            "status": "mapped_error",
            "route_status": 503,
            "code": "MODEL_UNAVAILABLE",
            "detail": str(exc),
        }
    except Exception as exc:  # noqa: BLE001 - 汇总所有校验类异常为 422
        errs = getattr(exc, "errors", list)()
        record["parse"] = {
            "status": "mapped_error",
            "route_status": 422,
            "code": "VALIDATION_ERROR",
            "errors": errs,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "parse_status": record["parse"]["status"],
        "run_id": record.get("run", {}).get("run_id"),
        "output": record.get("run", {}).get("output"),
        "model": record["model"],
        "calls": len(transcript_calls),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
