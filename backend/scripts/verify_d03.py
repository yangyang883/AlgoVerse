"""AV-M1-D03 十条样例验证脚本（离线 Mock，明确标注）。

用法（backend/ 下）：python scripts/verify_d03.py
产物：backend/artifacts/d03-sample-results.json

说明：当前无真实 Qwen 凭据。脚本用「规则型 Mock 模型」逐条模拟模型输出，
但配置校验、注册表检查、算法执行全部是仓库真实代码。
Mock 结果不得冒充真实模型结果；真实凭据到位后用 provider_smoke.py 补测。
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from starlette.requests import Request

from app.ai.planner import parse
from app.main import run

FIXTURE = ROOT / "tests" / "fixtures" / "config_samples.json"
OUT = ROOT / "artifacts" / "d03-sample-results.json"


def req_stub():
    return Request({"type": "http", "method": "POST", "path": "/api/v1/experiments/run", "headers": []})


def rule_based_model(text):
    """规则型 Mock：按关键词生成模型 JSON（纯离线，不代表真实模型）。"""
    import re

    low = text.lower()
    if "dijkstra" in low or "快速排序" in low:
        return {"status": "error", "error_code": "E-UNKNOWN-ALGORITHM", "config": None,
                "tool_suggestions": []}
    if "改成" in low and "冒泡" not in low:
        return {"status": "needs_clarification", "clarification": "请指定算法",
                "config": None, "tool_suggestions": []}
    if "foo" in low or "-5" in low:
        return {"status": "ok", "config": {
            "schema_version": "1.0", "algorithm": "bubble_sort", "mode": "experiment",
            "input": {"size": 10, "distribution": "random", "seed": -5, "values": None},
            "parameters": {"foo": 1}, "visualization": {"enabled": True},
            "metrics": ["comparisons", "swaps", "elapsed_ms"]}, "tool_suggestions": []}

    size = 20
    m = re.search(r"(\d+)\s*个", text)
    if m:
        size = int(m.group(1))
    distribution = "random"
    if "有序" in text:
        distribution = "sorted"
    elif "逆序" in text:
        distribution = "reversed"
    seed = 42
    m = re.search(r"(?:seed|种子)\s*(?:设成|设为|=|:)?\s*(\d+)", text)
    if m:
        seed = int(m.group(1))
    values = None
    m = re.search(r"\[([0-9,\s]+)\]", text)
    if m:
        values = [int(x.strip()) for x in m.group(1).split(",") if x.strip()]
        size = len(values)
    animation = size <= 40 and "不需要动画" not in text and "性能实验" not in text

    config = {
        "schema_version": "1.0", "algorithm": "bubble_sort", "mode": "experiment",
        "input": {"size": size, "distribution": distribution, "seed": seed, "values": values},
        "parameters": {}, "visualization": {"enabled": animation},
        "metrics": ["comparisons", "swaps", "elapsed_ms"],
    }
    return {"status": "ok", "config": config, "tool_suggestions": []}


def expected_value(config, key):
    if key == "algorithm":
        return str(config.algorithm)
    if key == "values":
        return config.input.values
    if key == "visualization.enabled":
        return config.visualization.enabled
    return getattr(config.input, key, None)


def make_tool_fn(model_first):
    """模型函数：第一次给原始输出；修复时给修正后的合法输出（非法样例则保持失败）。"""
    calls = {"n": 0}

    def fn(messages, source, rid):
        calls["n"] += 1
        is_repair = any(m.get("role") == "assistant" for m in messages)
        user_text = ""
        for m in messages:
            if m.get("role") == "user" and "user_request" in m.get("content", ""):
                try:
                    user_text = json.loads(m["content"]).get("user_request", "")
                except (ValueError, TypeError):
                    pass
        payload = model_first(user_text)
        if is_repair:
            # 非法输入样例（CFG-10）：模拟模型一次修复后仍失败，验证 E-REPAIR-FAILED 路径
            if "foo" in user_text or "-5" in user_text:
                # 一次修复仍含未知字段 foo → StrictModel 拒绝 → E-REPAIR-FAILED 路径
                payload = {"status": "ok", "config": {
                    "schema_version": "1.0", "algorithm": "bubble_sort", "mode": "experiment",
                    "input": {"size": 10, "distribution": "random", "seed": 42, "values": None},
                    "parameters": {}, "visualization": {"enabled": True},
                    "metrics": ["comparisons", "swaps", "elapsed_ms"]},
                    "tool_suggestions": [], "foo": 1}
            else:
                payload = {"status": "ok", "config": None, "tool_suggestions": []}
        return json.dumps(payload, ensure_ascii=False)

    return fn


def main():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    results = []
    for s in data["samples"]:
        out = parse(s["text"], source="mock", tool_fn=make_tool_fn(rule_based_model))
        record = {
            "id": s["id"],
            "text": s["text"],
            "expected": s["expected"],
            "actual_status": out.status,
            "actual_error_code": out.error_code,
            "config": out.config.model_dump(mode="json") if out.config else None,
            "repair": {"attempted": out.repair.attempted, "failed": out.repair.failed},
            "source": out.source,
            "request_id": out.request_id,
        }
        expected_status = s["expected"]["status"]
        record["passed"] = out.status == expected_status
        if out.status == "ok" and out.config is not None:
            # 真实执行（非 Mock）
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
        "mode": "OFFLINE MOCK MODEL — 不代表真实 Qwen 结果",
        "note": "模型响应用规则型 Mock，配置校验/注册表检查/算法执行为真实代码",
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
        print("{} {} {}".format("PASS" if r["passed"] else "FAIL", r["id"], r["actual_status"]))


if __name__ == "__main__":
    main()
