import pytest

from app.db.experiments import dispose_database
from app.services.conversation import conversations


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "experiments.db"))
    with conversations._lock:
        conversations._states.clear()
    yield
    dispose_database()
