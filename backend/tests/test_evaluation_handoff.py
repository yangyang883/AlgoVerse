from fastapi.testclient import TestClient

from app.main import app


def test_compare_saved_runs_with_identical_input():
    with TestClient(app) as client:
        config = {"input": {"values": [3, 1, 2]}}
        first = client.post("/api/v1/experiments/run", json=config).json()["data"]
        second = client.post("/api/v1/experiments/run", json=config).json()["data"]

        response = client.post("/api/v1/experiments/compare", json={
            "run_ids": [first["run_id"], second["run_id"]],
        })
        assert response.status_code == 200
        assert response.json()["data"] == {"runs": [first, second], "same_input": True}
        assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_compare_rejects_missing_or_different_runs():
    with TestClient(app) as client:
        first = client.post("/api/v1/experiments/run", json={
            "input": {"values": [3, 1, 2]},
        }).json()["data"]["run_id"]
        second = client.post("/api/v1/experiments/run", json={
            "input": {"values": [2, 1, 3]},
        }).json()["data"]["run_id"]

        different = client.post("/api/v1/experiments/compare", json={"run_ids": [first, second]})
        assert different.status_code == 409
        assert different.json()["error"]["code"] == "CONTEXT_CONFLICT"

        missing = client.post("/api/v1/experiments/compare", json={"run_ids": [first, "missing"]})
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "NOT_FOUND"

        invalid = client.post("/api/v1/experiments/compare", json={"run_ids": [first]})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["details"]["errors"][0]["loc"] == ["body", "run_ids"]


def test_invalid_provider_config_includes_field_path():
    with TestClient(app) as client:
        app.state.parse_provider = lambda request: {
            "config": {"algorithm": "quick_sort"}, "source": "mock",
        }
        try:
            response = client.post("/api/v1/experiments/parse", json={"text": "sort"})
        finally:
            del app.state.parse_provider

        assert response.status_code == 422
        body = response.json()
        assert body["request_id"] == response.headers["X-Request-ID"]
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert ["config", "algorithm"] in [
            error["loc"] for error in body["error"]["details"]["errors"]
        ]
