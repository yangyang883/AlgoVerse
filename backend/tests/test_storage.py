from app.db.experiments import load_result, save_result
from app.schemas.models import ExperimentConfig
from app.services.experiment import run_experiment


def test_storage_without_http(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "direct.db"))
    result = run_experiment(ExperimentConfig(input={"values": [3, 1, 2]}))
    save_result(result)
    assert load_result(result.run_id).model_dump(mode="json") == result.model_dump(mode="json")
    assert load_result("missing") is None
import pytest
from sqlalchemy.exc import IntegrityError



def test_failed_insert_rolls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "rollback.db"))
    result = run_experiment(ExperimentConfig(input={"values": [2, 1]}))
    save_result(result)
    with pytest.raises(IntegrityError):
        save_result(result)
    assert load_result(result.run_id).output == [1, 2]
