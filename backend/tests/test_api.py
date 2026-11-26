import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.main import app, health, run
from app.schemas.models import ExperimentConfig


def request(path):
    return Request({"type": "http", "method": "GET", "path": path, "headers": []})


def test_health():
    response = health(request("/api/v1/health"))
    assert response.data == {"status": "ok"}
    assert response.request_id


def test_run_real_sort():
    config = ExperimentConfig.model_validate({"algorithm": "bubble_sort", "input": {"values": [3, 1, 2]}})
    result = run(request("/api/v1/experiments/run"), config).data
    assert result.output == [1, 2, 3]
    assert result.metrics["comparisons"] == 3
    assert result.validation.valid is True
    assert result.trace[0].array == [3, 1, 2]
    assert result.trace[-1].array == [1, 2, 3]


def test_reject_unsupported_algorithm():
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate({"algorithm": "quick_sort"})


def test_reject_large_animation():
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate({"input": {"size": 41}})


def test_large_run_without_animation_has_no_trace():
    config = ExperimentConfig.model_validate({
        "input": {"size": 41}, "visualization": {"enabled": False},
    })
    result = run(request("/api/v1/experiments/run"), config).data
    assert result.validation.valid
    assert result.trace == []
    assert not result.trace_truncated


def test_openapi_routes():
    paths = app.openapi()["paths"]
    assert all("/api/v1" + path in paths for path in [
        "/algorithms", "/chat", "/experiments/parse", "/experiments/run",
        "/experiments/compare", "/experiments/{run_id}", "/experiments/{run_id}/report",
    ])


def test_http_round_trip():
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/api/v1/experiments/run", json={"input": {"values": [3, 1, 2]}})
    assert response.status_code == 200
    assert response.json()["data"]["output"] == [1, 2, 3]
