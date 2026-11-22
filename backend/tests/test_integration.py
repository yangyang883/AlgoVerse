import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.experiments import load_result
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "runs.db"))
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    if hasattr(app.state, "parse_provider"):
        del app.state.parse_provider


def test_persist_and_reload(client):
    response = client.post("/api/v1/experiments/run", json={"input": {"values": [3, 1, 2]}})
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["output"] == [1, 2, 3]
    assert result["metrics"]["comparisons"] == 3
    assert load_result(result["run_id"]).output == result["output"]
    fetched = client.get(f"/api/v1/experiments/{result['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"] == result


def test_missing_and_invalid(client):
    missing = client.get("/api/v1/experiments/missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    invalid = client.post("/api/v1/experiments/run", json={"algorithm": "quick_sort"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert invalid.json()["request_id"] == invalid.headers["X-Request-ID"]


def test_transaction_failure_has_no_record(client, monkeypatch):
    from app import main

    def fail(_result):
        raise SQLAlchemyError("test database error")

    monkeypatch.setattr(main, "save_result", fail)
    response = client.post("/api/v1/experiments/run", json={"input": {"values": [2, 1]}})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"


def test_mock_parse_to_real_execution(client):
    app.state.parse_provider = lambda request: {
        "config": {"algorithm": "bubble_sort", "input": {"size": 20, "seed": 42}},
        "source": "mock", "requires_confirmation": True,
    }
    parsed = client.post("/api/v1/experiments/parse", json={
        "text": "使用冒泡排序对 20 个随机整数进行排序。"
    })
    assert parsed.status_code == 200
    config = parsed.json()["data"]["config"]
    run = client.post("/api/v1/experiments/run", json=config)
    assert run.status_code == 200
    result = run.json()["data"]
    assert len(result["input"]) == 20
    assert result["output"] == sorted(result["input"])
    assert result["metrics"]["comparisons"] > 0
    assert result["validation"]["valid"]
    assert client.get(f"/api/v1/experiments/{result['run_id']}").json()["data"] == result


def test_model_timeout(client):
    app.state.parse_provider = lambda request: (_ for _ in ()).throw(TimeoutError())
    response = client.post("/api/v1/experiments/parse", json={"text": "sort"})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "MODEL_TIMEOUT"


