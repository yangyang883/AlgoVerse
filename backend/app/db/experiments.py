"""SQLite storage for completed experiment runs."""
import os
import platform
from datetime import timezone
from pathlib import Path
from threading import RLock

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base

from app.schemas.models import ExperimentResult

Base = declarative_base()
_engine = None
_engine_path = None
_engine_lock = RLock()


class ExperimentRecord(Base):
    __tablename__ = "experiments"

    run_id = Column(String, primary_key=True)
    algorithm = Column(String, nullable=False)
    experiment_config = Column(JSON, nullable=False)
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=False)
    validation = Column(JSON, nullable=False)
    trace = Column(JSON, nullable=False)
    trace_truncated = Column(Boolean, nullable=False)
    seed = Column(Integer, nullable=False)
    algorithm_version = Column(String, nullable=False)
    model_version = Column(String)
    prompt_version = Column(String)
    knowledge_version = Column(String)
    execution_environment = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


def database_engine():
    global _engine, _engine_path
    path = Path(os.getenv("ALGOVERSE_DB_PATH", "algoverse.db")).expanduser().resolve()
    with _engine_lock:
        if _engine is None or _engine_path != path:
            if _engine is not None:
                _engine.dispose()
            path.parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(
                f"sqlite:///{path.as_posix()}", connect_args={"check_same_thread": False}
            )
            Base.metadata.create_all(_engine)
            _engine_path = path
        return _engine


def dispose_database():
    global _engine, _engine_path
    with _engine_lock:
        if _engine is not None:
            _engine.dispose()
        _engine = _engine_path = None


def save_result(result: ExperimentResult) -> None:
    record = ExperimentRecord(
        run_id=result.run_id, algorithm=result.config.algorithm,
        experiment_config=result.config.model_dump(mode="json"), input_data=result.input,
        output_data=result.output, metrics=result.metrics,
        validation=result.validation.model_dump(mode="json"),
        trace=[event.model_dump(mode="json") for event in result.trace],
        trace_truncated=result.trace_truncated, seed=result.config.input.seed,
        algorithm_version="bubble_sort:v1", model_version=None, prompt_version=None,
        knowledge_version=None,
        execution_environment={"python": platform.python_version(), "machine": platform.machine(),
                               "system": platform.system(),
                               "processor": platform.processor() or platform.machine(),
                               "timer": "time.perf_counter", "execution_mode": "in_process",
                               "metric_definitions": {"comparisons": "bubble_sort:v1 comparisons",
                                                      "swaps": "bubble_sort:v1 swaps",
                                                      "elapsed_ms": "time.perf_counter milliseconds"}},
        status=result.status, created_at=result.created_at,
    )
    with Session(database_engine()) as session, session.begin():
        session.add(record)


def load_result(run_id: str):
    with Session(database_engine()) as session:
        record = session.get(ExperimentRecord, run_id)
        if record is None:
            return None
        return ExperimentResult.model_validate({
            "run_id": record.run_id, "status": record.status,
            "config": record.experiment_config, "input": record.input_data,
            "output": record.output_data, "metrics": record.metrics,
            "validation": record.validation, "trace": record.trace,
            "trace_truncated": record.trace_truncated,
            "created_at": record.created_at.replace(tzinfo=timezone.utc),
        })
