import pytest

from app.services.conversation import conversations


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "experiments.db"))
    with conversations._lock:
        conversations._states.clear()
