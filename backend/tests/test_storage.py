import pytest
from sqlalchemy.exc import IntegrityError

from app.db.experiments import load_result, save_result
from app.schemas.models import ExperimentConfig
from app.services.experiment import run_experiment


def test_storage_without_http(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "direct.db"))
    result = run_experiment(ExperimentConfig(input={"values": [3, 1, 2]}))
    save_result(result)
    assert load_result(result.run_id).model_dump(mode="json") == result.model_dump(mode="json")
    assert load_result("missing") is None

def test_failed_insert_rolls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "rollback.db"))
    result = run_experiment(ExperimentConfig(input={"values": [2, 1]}))
    save_result(result)
    with pytest.raises(IntegrityError):
        save_result(result)
    assert load_result(result.run_id).output == [1, 2]


def test_processor_metadata_falls_back_to_machine(tmp_path, monkeypatch):
    import platform

    from sqlalchemy.orm import Session

    from app.db.experiments import ExperimentRecord, database_engine

    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "processor.db"))
    monkeypatch.setattr(platform, "processor", lambda: "")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    result = run_experiment(ExperimentConfig(input={"values": [2, 1]}))
    save_result(result)
    with Session(database_engine()) as session:
        row = session.get(ExperimentRecord, result.run_id)
        assert row.execution_environment["processor"] == "x86_64"
