from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.db.experiments import database_engine, load_result, save_result
from app.main import app
from app.schemas.models import ExperimentConfig
from app.services.conversation import (
    ConversationCapacity,
    ConversationService,
    ExpiredConversation,
)
from app.services.experiment import run_experiment


def test_provider_extra_fields_never_override_session():
    with TestClient(app) as client:
        session_id = client.post("/api/v1/conversations", json={"config": {
            "input": {"size": 20, "distribution": "random", "seed": 42}
        }}).json()["data"]["session_id"]
        app.state.parse_provider = lambda request: {
            "config": {"input": {"size": 30, "distribution": "reversed", "seed": 999}},
            "source": "mock", "session_id": "forged",
        }
        try:
            no_confirmation = client.post("/api/v1/experiments/parse", json={
                "text": "把规模改成 30", "session_id": session_id,
            })
            assert no_confirmation.status_code == 409
            confirmed = client.post("/api/v1/experiments/parse", json={
                "text": "把规模改成 30", "session_id": session_id,
                "confirmed_changes": {"input.size": 30},
            })
            assert confirmed.status_code == 200
            assert confirmed.json()["data"]["session_id"] == session_id
            state = client.get(f"/api/v1/conversations/{session_id}").json()["data"]
            assert state["last_config"]["input"] == {
                "size": 30, "distribution": "random", "seed": 42, "values": None,
            }
            assert state["modified_fields"] == ["input.size"]
            bad = client.post("/api/v1/experiments/parse", json={
                "text": "change", "session_id": session_id,
                "confirmed_changes": {"input.seed": 12},
            })
            assert bad.status_code == 422
            assert client.get(f"/api/v1/conversations/{session_id}").json()["data"] == state
        finally:
            del app.state.parse_provider


def test_run_conflict_does_not_change_state_or_save():
    with TestClient(app) as client:
        ids = [client.post("/api/v1/conversations", json={"config": {
            "input": {"size": 3, "seed": seed}
        }}).json()["data"]["session_id"] for seed in (1, 2)]
        before = client.get(f"/api/v1/conversations/{ids[0]}").json()["data"]
        conflict = client.post("/api/v1/experiments/run", json={
            "input": {"size": 4, "seed": 1}
        }, headers={"X-Session-ID": ids[0]})
        assert conflict.status_code == 409
        assert client.get(f"/api/v1/conversations/{ids[0]}").json()["data"] == before
        assert client.get(f"/api/v1/conversations/{ids[1]}").json()["data"][
            "last_config"]["input"]["seed"] == 2


def test_ttl_capacity_and_copy():
    now = [0.0]
    service = ConversationService(ttl_seconds=5, max_sessions=1, clock=lambda: now[0])
    config = ExperimentConfig()
    original = service.start(config)
    original.last_config.input.seed = 999
    assert service.get(original.session_id).last_config.input.seed == 42
    with pytest.raises(ConversationCapacity):
        service.start(config)
    now[0] = 5.0
    with pytest.raises(ExpiredConversation):
        service.get(original.session_id)
    assert service.start(config).session_id != original.session_id


def test_engine_reuse_isolation_and_parallel_reads(tmp_path, monkeypatch):
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(first))
    engine = database_engine()
    assert database_engine() is engine
    result = run_experiment(ExperimentConfig(input={"values": [3, 1, 2]}))
    save_result(result)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(lambda _: load_result(result.run_id).output == [1, 2, 3], range(8)))
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(second))
    assert database_engine() is not engine
    assert load_result(result.run_id) is None
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(first))
    assert load_result(result.run_id).output == [1, 2, 3]


def test_openapi_documents_error_envelope():
    route = app.openapi()["paths"]["/api/v1/experiments/run"]["post"]
    assert "409" in route["responses"]
    assert "422" in route["responses"]
    assert "500" in route["responses"]
    schema = route["responses"]["409"]["content"]["application/json"]["schema"]
    assert "$ref" in schema


def test_concurrent_sessions_remain_isolated():
    service = ConversationService(ttl_seconds=60, max_sessions=20)

    def create_and_revise(seed):
        state = service.start(ExperimentConfig(input={"size": 20, "seed": seed}))
        return service.revise(state.session_id, {"input.size": 10 + seed})

    with ThreadPoolExecutor(max_workers=4) as pool:
        states = list(pool.map(create_and_revise, range(8)))
    assert len({state.session_id for state in states}) == 8
    assert all(service.get(state.session_id).last_config.input.seed == seed
               for seed, state in enumerate(states))
