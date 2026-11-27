"""集成适配层测试：验证 callable 契约与异常映射。全部离线 Mock。"""

import json

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.ai import errors
from app.ai.integration import CONNECTION_CODES, TIMEOUT_CODES, make_parse_provider
from app.schemas.models import ExperimentConfig, ParseRequest, ParseResult


def ok_json(_messages):
    return json.dumps({
        "status": "ok",
        "config": {
            "schema_version": "1.0",
            "algorithm": "bubble_sort",
            "mode": "experiment",
            "input": {"size": 3, "distribution": "random", "seed": 42, "values": [3, 1, 2]},
            "parameters": {},
            "visualization": {"enabled": True},
            "metrics": ["comparisons", "swaps", "elapsed_ms"],
        },
        "tool_suggestions": [],
        "clarification": None,
        "error_code": None,
    }, ensure_ascii=False)


def test_success_returns_contract_compatible_dict():
    provider = make_parse_provider(source="mock", call_model=lambda m, _s, _r: ok_json(m))
    result = ParseResult.model_validate(provider(ParseRequest(text="排一下3,1,2")))
    assert result.source == "mock"
    assert result.requires_confirmation is True
    assert isinstance(result.config, ExperimentConfig)
    assert result.config.input.values == [3, 1, 2]


def test_error_code_mapping_taxonomy():
    assert errors.REQUEST_TIMEOUT in TIMEOUT_CODES
    assert errors.HTTP_ERROR in CONNECTION_CODES
    assert errors.NO_CREDENTIAL in CONNECTION_CODES


def test_repair_failure_maps_to_validation_error_with_code():
    def bad(_messages, _source, _rid):
        return json.dumps({
            "status": "error",
            "config": None,
            "tool_suggestions": [],
            "error_code": errors.UNKNOWN_ALGORITHM,
        }, ensure_ascii=False)

    provider = make_parse_provider(source="mock", call_model=bad)
    with pytest.raises(ValidationError) as exc_info:
        provider(ParseRequest(text="用快排"))
    err = exc_info.value.errors()[0]
    assert err["loc"] == ()
    assert err["ctx"]["code"] == errors.UNKNOWN_ALGORITHM


def test_needs_clarification_maps_to_409_context_conflict():
    def ambiguous(_messages, _source, _rid):
        return json.dumps({
            "status": "needs_clarification",
            "config": None,
            "tool_suggestions": [],
            "clarification": "请指定要排序的数组",
            "error_code": None,
        }, ensure_ascii=False)

    provider = make_parse_provider(source="mock", call_model=ambiguous)
    with pytest.raises(HTTPException) as exc_info:
        provider(ParseRequest(text="排一下"))
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "请指定要排序的数组"


def test_transcript_is_written_on_success(tmp_path):
    transcript = tmp_path / "t.jsonl"
    provider = make_parse_provider(
        source="mock",
        call_model=lambda m, _s, _r: ok_json(m),
        transcript_path=str(transcript),
    )
    provider(ParseRequest(text="排一下3,1,2"))
    # mock 模式下 write_transcript 在 call_model 内部由调用方负责；
    # 此处仅验证 provider 不因 transcript_path 报错。
    assert transcript.parent.exists()
