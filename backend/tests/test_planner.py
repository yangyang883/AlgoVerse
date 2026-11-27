"""AV-M1-D03 解析器测试：离线 Mock 模型 → 真实 ExperimentConfig → 真实 run_experiment。

Mock 只替代「模型返回」，不替代配置校验与算法执行；所有样例逐条记录于
backend/artifacts/d03-sample-results.json（由 scripts/verify_d03.py 生成）。
"""

import json
from pathlib import Path

from app.ai import errors
from app.ai.planner import parse
from app.main import run
from app.schemas.models import ExperimentConfig

FIXTURES = Path(__file__).parent / "fixtures"


def request_stub(path):
    from starlette.requests import Request
    return Request({"type": "http", "method": "POST", "path": path, "headers": []})


def make_mock_fn(_config_valid=True, invalid_field=False, always_fail=False, repair_fixes=True):
    """返回一个模型函数：第 1 次可故意返回非法 JSON，第 2 次修复。"""
    calls = {"n": 0}

    def fn(messages, _source, _rid):
        calls["n"] += 1
        is_repair = any(m.get("role") == "assistant" for m in messages)
        if always_fail:
            return json.dumps({"status": "ok", "config": {"algorithm": "bubble_sort", "foo": 1}})
        if invalid_field and calls["n"] == 1 and not is_repair:
            return json.dumps({"status": "ok", "config": {
                "schema_version": "1.0", "algorithm": "bubble_sort", "mode": "experiment",
                "input": {"size": 3, "distribution": "random", "seed": 42},
                "parameters": {}, "visualization": {"enabled": True},
                "metrics": ["comparisons", "swaps", "elapsed_ms"], "foo": 1,
            }})
        if invalid_field and is_repair and not repair_fixes:
            return json.dumps({"status": "ok", "config": {
                "schema_version": "1.0", "algorithm": "bubble_sort", "mode": "experiment",
                "input": {"size": 3}, "parameters": {}, "visualization": {"enabled": True},
                "metrics": ["comparisons"], "foo": 1,
            }})
        config = {
            "schema_version": "1.0", "algorithm": "bubble_sort", "mode": "experiment",
            "input": {"size": 3, "distribution": "random", "seed": 42, "values": [3, 1, 2]},
            "parameters": {}, "visualization": {"enabled": True},
            "metrics": ["comparisons", "swaps", "elapsed_ms"],
        }
        return json.dumps({"status": "ok", "config": config, "tool_suggestions": []})

    return fn


def test_unknown_field_rejected_and_repaired():
    out = parse("用冒泡排序排 3,1,2", source="mock",
                tool_fn=make_mock_fn(invalid_field=True))
    assert out.status == "ok"
    assert out.repair.attempted is True
    assert out.repair.failed is False
    assert isinstance(out.config, ExperimentConfig)


def test_one_repair_then_still_fails():
    out = parse("用冒泡排序排 3,1,2", source="mock",
                tool_fn=make_mock_fn(invalid_field=True, repair_fixes=False, always_fail=True))
    assert out.status == "error"
    assert out.repair.failed is True
    assert out.error_code in (errors.SCHEMA_INVALID, errors.UNKNOWN_FIELD)


def test_unknown_algorithm_rejected():
    def fn(_messages, _source, _rid):
        return json.dumps({"status": "error", "error_code": "E-UNKNOWN-ALGORITHM",
                           "config": None, "tool_suggestions": []})
    out = parse("用快速排序排 3,1,2", source="mock", tool_fn=fn)
    assert out.status == "error"
    assert out.error_code == "E-UNKNOWN-ALGORITHM"
    assert out.config is None


def test_needs_clarification():
    def fn(_messages, _source, _rid):
        return json.dumps({"status": "needs_clarification", "clarification": "请指定算法",
                           "config": None, "tool_suggestions": []})
    out = parse("把它改成逆序分布", source="mock", tool_fn=fn)
    assert out.status == "needs_clarification"
    assert "算法" in out.clarification


def test_outcome_to_contract_result():
    out = parse("用冒泡排序排 3,1,2", source="mock", tool_fn=make_mock_fn())
    result = out.to_contract_result()
    assert result.source == "mock"
    assert result.requires_confirmation is True
    assert result.config.input.values == [3, 1, 2]


def test_parse_to_run_round_trip():
    """从一句话到冒泡实测结果的 HTTP 往返。"""
    out = parse("用冒泡排序排 3,1,2", source="mock", tool_fn=make_mock_fn())
    contract_result = out.to_contract_result()
    # 真实执行（不经过模型）
    exec_result = run(request_stub("/api/v1/experiments/run"), contract_result.config).data
    assert exec_result.output == [1, 2, 3]
    assert exec_result.validation.valid is True
    assert exec_result.metrics["comparisons"] == 3


def test_request_id_and_prompt_version_present():
    out = parse("用冒泡排序排 3,1,2", source="mock", tool_fn=make_mock_fn(), request_id="rid-001")
    assert out.request_id == "rid-001"
    assert out.prompt_version.startswith("parse-v")
    assert out.source == "mock"


def test_all_ten_samples_have_expectations():
    data = json.loads((FIXTURES / "config_samples.json").read_text(encoding="utf-8"))
    samples = data["samples"]
    assert len(samples) == 10
    for s in samples:
        assert s["id"] and s["text"] and s["expected"]["status"]
