#!/usr/bin/env python3
"""AlgoVerse 批量评测最小入口（D5）。

只做三件事：读题 -> 发请求 -> 存原始结果。
本脚本不评分、不做主观判断；字段比对与人工评分在后续统计脚本/人工复核中完成。

用法:
    python evaluation/scripts/run_eval.py --mode dry-run
    python evaluation/scripts/run_eval.py --mode mock
    python evaluation/scripts/run_eval.py --mode real --base-url http://127.0.0.1:8000
"""

import argparse
import hashlib
import json
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

EVAL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = EVAL_DIR / "datasets" / "v0.1" / "cases.seed.jsonl"
OUT_ROOT = EVAL_DIR / "results" / "raw"

ENVELOPE_KEYS = ("data", "error", "request_id")
INJECTED_FAILURES = {
    # 演示用确定性失败：一个 HTTP 级、一个信封级，确保失败路径可复现
    "EXE-0001": "HTTP_502",
    "CFG-0003": "ENVELOPE_INVALID",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(EVAL_DIR), capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def load_cases(path: Path) -> list:
    cases = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"dataset line {lineno} is not valid JSON: {exc}")
    return cases


def validate_cases(cases: list) -> None:
    schema_path = EVAL_DIR / "datasets" / "schema" / "case.schema.json"
    if not schema_path.exists():
        print("[warn] schema not found, skip structural check")
        return
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("[warn] jsonschema not installed, skip structural check")
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    bad = 0
    for case in cases:
        for err in validator.iter_errors(case):
            bad += 1
            loc = "/".join(str(p) for p in err.absolute_path)
            print(f"[schema] {case.get('case_id')} {loc}: {err.message}")
    if bad:
        raise SystemExit(f"dataset has {bad} schema errors; fix before running")
    print(f"[ok] schema check passed: {len(cases)} cases")


def build_request(case: dict, step_index: int, run_id: str) -> dict:
    step = case["input"]["steps"][step_index]
    body = json.loads(json.dumps(step["request"]))  # deep copy
    endpoint = step["endpoint"]
    if endpoint != "/api/v1/algorithms" and "session_id" not in body:
        body["session_id"] = f"eval-{run_id}-{case['case_id']}"
    return body


def post_json(url: str, body: dict, timeout: float):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urlrequest.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    start = time.perf_counter()
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, raw, (time.perf_counter() - start) * 1000, None
    except urlerror.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, raw, (time.perf_counter() - start) * 1000, None
    except urlerror.URLError as exc:
        reason = str(exc.reason)
        if "timed out" in reason.lower():
            return None, "", (time.perf_counter() - start) * 1000, "TIMEOUT"
        return None, "", (time.perf_counter() - start) * 1000, "CONNECTION_ERROR"
    except Exception as exc:  # 网络层兜底，保留原始信息
        return None, f"{type(exc).__name__}: {exc}", (time.perf_counter() - start) * 1000, "CONNECTION_ERROR"


def mock_response(case: dict, step_index: int, run_id: str):
    """可复现的假响应。合法但明确不保证正确，仅用于验证采集链路。"""
    case_id = case["case_id"]
    if case_id in INJECTED_FAILURES and INJECTED_FAILURES[case_id] == "HTTP_502" and step_index == 0:
        return 502, json.dumps({"detail": "mock upstream error"}, ensure_ascii=False), 12.0, "HTTP_502"

    category = case["category"]
    if category == "knowledge":
        payload = {
            "answer": "[MOCK] 这是占位回答，不构成任何评测结论。",
            "citations": [{"source_id": "MOCK-SRC", "title": "mock"}],
            "capability_level": "L1",
        }
    elif category in ("config_followup", "invalid_input"):
        payload = {
            "config": {
                "schema_version": "1.0",
                "algorithm": "bubble_sort",
                "mode": "experiment",
                "input": {"size": 20, "distribution": "sorted"},
                "parameters": {},
                "visualization": {"enabled": False},
                "metrics": ["comparisons"],
            },
            "requires_user_input": category == "invalid_input",
            "message": "[MOCK] 占位响应",
        }
    elif category == "execution_explain":
        payload = {
            "run_id": f"mock-run-{case_id}-{step_index}",
            "status": "ok",
            "metrics": {"comparisons": 15, "swaps": 9},
            "validation": {"passed": True},
            "trace_truncated": False,
            "output": [1, 2, 3, 5, 8, 9],
        }
    else:  # counterexample
        payload = {"answer": "[MOCK] 占位反例说明", "verified": False}

    envelope = {"data": payload, "error": None, "request_id": f"mock-{run_id}-{case_id}-{step_index}"}
    if case_id in INJECTED_FAILURES and INJECTED_FAILURES[case_id] == "ENVELOPE_INVALID" and step_index == 0:
        envelope.pop("request_id")
    return 200, json.dumps(envelope, ensure_ascii=False), 8.0, None


def classify(status, raw, transport_error):
    if transport_error:
        return transport_error, None, False
    if status is None:
        return "CONNECTION_ERROR", None, False
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return f"HTTP_{status}" if status >= 400 else "INVALID_JSON", None, False
    if status >= 400:
        return f"HTTP_{status}", parsed, False
    if not isinstance(parsed, dict) or not all(k in parsed for k in ENVELOPE_KEYS):
        return "ENVELOPE_INVALID", parsed, False
    if parsed.get("error"):
        return "API_ERROR", parsed, False
    return None, parsed, True


def main() -> int:
    parser = argparse.ArgumentParser(description="AlgoVerse 批量评测最小入口（不评分）")
    parser.add_argument("--mode", choices=["dry-run", "mock", "real"], default="dry-run")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题")
    parser.add_argument("--only", action="append", default=[], help="只跑指定 case_id，可重复")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--strict", action="store_true", help="有失败项时以非零码退出")
    args = parser.parse_args()

    dataset = Path(args.dataset)
    if not dataset.is_absolute():
        dataset = (EVAL_DIR.parent / dataset).resolve()
    cases = load_cases(dataset)
    if args.only:
        cases = [c for c in cases if c["case_id"] in set(args.only)]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("no cases selected")
    validate_cases(cases)

    run_id = args.run_id or f"{args.mode}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if args.mode == "mock" and not run_id.startswith("mock-"):
        run_id = f"mock-{run_id}"
    out_dir = OUT_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "mode": args.mode,
        "is_mock": args.mode == "mock",
        "scoring": "not_run",
        "started_at": now_iso(),
        "finished_at": None,
        "base_url": args.base_url if args.mode == "real" else None,
        "dataset": {
            "path": str(dataset).replace("\\", "/").split("evaluation/")[-1],
            "sha256": sha256_file(dataset),
            "version": cases[0].get("dataset_version", "unknown"),
            "case_count": len(cases),
        },
        "model": {
            "model_id": __import__("os").environ.get("QWEN_MODEL", "unset"),
            "temperature": __import__("os").environ.get("QWEN_TEMPERATURE", "unset"),
            "for_real_run": args.mode == "real",
        },
        "rag": {
            "embedding_model": __import__("os").environ.get("EMBEDDING_MODEL", "unset"),
            "kb_version": __import__("os").environ.get("KB_VERSION", "unset"),
        },
        "prompt_version": __import__("os").environ.get("PROMPT_VERSION", "unset"),
        "environment": {
            "hostname": socket.gethostname(),
            "os": platform.platform(),
            "python": platform.python_version(),
            "git_commit": git_commit(),
        },
        "command": " ".join(sys.argv),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    resp_path = out_dir / "responses.jsonl"
    fail_path = out_dir / "failures.jsonl"
    summary = {"run_id": run_id, "mode": args.mode, "scoring": "not_run", "total_cases": len(cases)}
    by_category, by_error, failures = {}, {}, []
    ok_cases = 0

    with resp_path.open("w", encoding="utf-8") as rf, fail_path.open("w", encoding="utf-8") as ff:
        for case in cases:
            case_id = case["case_id"]
            category = case["category"]
            steps = case["input"]["steps"]
            case_ok = True
            first_error = None

            if args.mode == "dry-run":
                for idx, step in enumerate(steps):
                    rf.write(json.dumps({
                        "case_id": case_id, "category": category, "step": idx,
                        "endpoint": step["endpoint"],
                        "request": build_request(case, idx, run_id),
                        "mode": "dry-run", "executed": False,
                    }, ensure_ascii=False) + "\n")
                summary.setdefault("not_executed", 0)
                summary["not_executed"] += 1
                continue

            case_runs = []
            for idx, step in enumerate(steps):
                body = build_request(case, idx, run_id)
                if args.mode == "mock":
                    status, raw, latency, transport_error = mock_response(case, idx, run_id)
                else:
                    status, raw, latency, transport_error = post_json(
                        args.base_url.rstrip("/") + step["endpoint"], body, args.timeout
                    )
                err, parsed, envelope_ok = classify(status, raw, transport_error)
                if err:
                    case_ok = False
                    first_error = first_error or err
                    by_error[err] = by_error.get(err, 0) + 1
                record = {
                    "case_id": case_id, "category": category, "step": idx,
                    "endpoint": step["endpoint"], "request": body,
                    "http_status": status, "latency_ms": round(latency, 2),
                    "error_class": err, "envelope_ok": envelope_ok, "mode": args.mode,
                    "response": parsed if parsed is not None else raw,
                    "captured_at": now_iso(),
                }
                rf.write(json.dumps(record, ensure_ascii=False) + "\n")
                case_runs.append(record)

            stat = by_category.setdefault(category, {"total": 0, "ok": 0, "failed": 0})
            stat["total"] += 1
            if case_ok:
                ok_cases += 1
                stat["ok"] += 1
            else:
                stat["failed"] += 1
                item = {
                    "case_id": case_id, "category": category, "run_id": run_id,
                    "primary_code": first_error,
                    "evidence": {"steps": [{"step": r["step"], "error": r["error_class"],
                                            "status": r["http_status"]} for r in case_runs]},
                    "status": "open",
                    "judged_at": None,
                }
                failures.append(item)
                ff.write(json.dumps(item, ensure_ascii=False) + "\n")

    summary.update({
        "ok_cases": ok_cases,
        "failed_cases": len(failures),
        "by_category": by_category,
        "by_error_class": by_error,
        "finished_at": now_iso(),
        "note": "本文件仅统计请求是否成功返回合法信封，不含任何正确性评分。",
    })
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest["finished_at"] = summary["finished_at"]
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"run_id      : {run_id}")
    print(f"mode        : {args.mode}")
    print(f"output      : {out_dir}")
    print(f"cases       : {len(cases)}")
    if args.mode != "dry-run":
        print(f"ok / failed : {ok_cases} / {len(failures)}")
        print(f"error class : {by_error or '{}'}")
    else:
        print("executed    : 0 (dry-run, requests recorded only)")
    return 2 if (args.strict and failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
