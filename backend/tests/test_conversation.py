from fastapi.testclient import TestClient

from app.main import app


def test_manual_session_revision_and_run():
    with TestClient(app) as client:
        started = client.post("/api/v1/conversations", json={
            "config": {"input": {"size": 20, "seed": 7}}
        })
        assert started.status_code == 200
        session_id = started.json()["data"]["session_id"]
        revised = client.post(f"/api/v1/conversations/{session_id}/revise", json={
            "changes": {"input.size": 12}
        })
        assert revised.status_code == 200
        state = revised.json()["data"]
        assert state["modified_fields"] == ["input.size"]
        assert state["last_config"]["input"]["size"] == 12
        assert state["last_config"]["input"]["seed"] == 7
        run = client.post("/api/v1/experiments/run", json=state["last_config"],
                          headers={"X-Session-ID": session_id})
        assert run.status_code == 200
        fetched = client.get(f"/api/v1/conversations/{session_id}")
        assert fetched.json()["data"]["last_run_id"] == run.json()["data"]["run_id"]
        assert fetched.json()["data"]["modified_fields"] == ["input.size"]


def test_missing_context_and_invalid_change():
    with TestClient(app) as client:
        missing = client.post("/api/v1/conversations/missing/revise", json={
            "changes": {"input.size": 10}
        })
        assert missing.status_code == 409
        assert missing.json()["error"]["code"] == "CONTEXT_CONFLICT"
        started = client.post("/api/v1/conversations", json={"config": {}})
        session_id = started.json()["data"]["session_id"]
        bad = client.post(f"/api/v1/conversations/{session_id}/revise", json={
            "changes": {"algorithm": "quick_sort"}
        })
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "VALIDATION_ERROR"
        assert client.get(f"/api/v1/conversations/{session_id}").json()["data"][
            "current_algorithm"] == "bubble_sort"
        no_run = client.post("/api/v1/experiments/run", json={},
                             headers={"X-Session-ID": "missing"})
        assert no_run.status_code == 409


def test_mock_provider_cannot_set_session_state():
    app.state.parse_provider = lambda request: {
        "config": {"input": {"size": 20, "seed": 42}},
        "source": "mock", "session_id": "forged",
    }
    try:
        with TestClient(app) as client:
            parsed = client.post("/api/v1/experiments/parse", json={"text": "冒泡排序 20 个整数"})
            assert parsed.status_code == 200
            session_id = parsed.json()["data"]["session_id"]
            assert session_id != "forged"
            assert client.get(f"/api/v1/conversations/{session_id}").status_code == 200
    finally:
        del app.state.parse_provider


def test_revision_rejects_implicit_size_change_with_values():
    with TestClient(app) as client:
        started = client.post("/api/v1/conversations", json={
            "config": {"input": {"values": [3, 1, 2], "seed": 9}}
        })
        session_id = started.json()["data"]["session_id"]
        revised = client.post(f"/api/v1/conversations/{session_id}/revise", json={
            "changes": {"input.size": 10}
        })
        assert revised.status_code == 422
        assert client.get(f"/api/v1/conversations/{session_id}").json()["data"][
            "last_config"]["input"]["values"] == [3, 1, 2]
