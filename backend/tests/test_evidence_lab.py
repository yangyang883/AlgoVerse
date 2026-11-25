import pytest
from sqlalchemy.orm import Session

from app.db.experiments import ExperimentRecord, database_engine, dispose_database, load_result
from app.schemas.models import ExperimentPlanRequest
from app.services import evidence_lab
from app.services.evidence_lab import create_plan, execute_plan, load_plan, load_report
from app.services.experiment import run_experiment


def request(kind, inputs):
    return ExperimentPlanRequest.model_validate({
        "hypothesis": {"hypothesis_id": "h1", "hypothesis_type": kind,
                       "question": "What changes?", "expected_observation": "Compare measured counts"},
        "experiment_type": kind,
        "configurations": [{"algorithm": "bubble_sort", "input": value,
                            "visualization": {"enabled": False}} for value in inputs],
    })


def test_distribution_runs_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "evidence.db"))
    dispose_database()
    plan = create_plan(request("distribution_effect", [
        {"size": 5, "distribution": "sorted"}, {"size": 5, "distribution": "reversed"}]))
    report = execute_plan(plan.plan_id)
    assert len(report.run_ids) == 2
    assert not report.comparison_validity
    assert load_report(report.evidence_id) == report
    for run_id, metrics in zip(report.run_ids, report.observed_metrics):
        run = load_result(run_id)
        assert run.validation.valid and run.metrics == metrics
    dispose_database()


def test_fair_input_and_unsupported_algorithm():
    with pytest.raises(ValueError, match="identical input"):
        create_plan(request("same_input_comparison", [{"values": [2, 1]}, {"values": [1, 2]}]))
    body = request("same_input_comparison", [{"values": [2, 1]}, {"values": [2, 1]}])
    body.configurations[1].algorithm = "quick_sort"
    with pytest.raises(ValueError, match="not executable"):
        create_plan(body)


def test_same_input_comparable_and_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "fair.db"))
    dispose_database()
    plan = create_plan(request("same_input_comparison", [{"values": [3, 1, 2]}, {"values": [3, 1, 2]}]))
    report = execute_plan(plan.plan_id)
    assert report.comparison_status == "comparable"
    assert set(report.comparable_metrics) == {"comparisons", "swaps", "elapsed_ms"}
    assert load_plan(plan.plan_id).status == "completed"
    for run_id in report.run_ids:
        saved = load_result(run_id)
        assert saved.input == [3, 1, 2] and saved.output == [1, 2, 3]
        assert saved.metrics["comparisons"] == 3
        replay = run_experiment(saved.config)
        assert replay.input == saved.input and replay.output == saved.output
        assert replay.metrics["comparisons"] == saved.metrics["comparisons"]
        assert replay.metrics["swaps"] == saved.metrics["swaps"]
    with pytest.raises(ValueError, match="already run"):
        execute_plan(plan.plan_id)
    dispose_database()


def test_environment_and_missing_metadata_are_metric_specific(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "metadata.db"))
    dispose_database()
    plan = create_plan(request("same_input_comparison", [{"values": [2, 1]}, {"values": [2, 1]}]))
    report = execute_plan(plan.plan_id)
    with Session(database_engine()) as session, session.begin():
        row = session.get(ExperimentRecord, report.run_ids[1])
        env = dict(row.execution_environment)
        env["machine"] = "different-machine"
        row.execution_environment = env
    with Session(database_engine()) as session:
        rows = [session.get(ExperimentRecord, run_id) for run_id in report.run_ids]
        status, reasons, metrics = evidence_lab._compare(plan, rows, [load_result(i) for i in report.run_ids], [])
    assert status == "partially_comparable" and "elapsed_ms" not in metrics
    assert set(metrics) == {"comparisons", "swaps"}
    assert any("执行环境不一致" in reason for reason in reasons)
    with Session(database_engine()) as session, session.begin():
        row = session.get(ExperimentRecord, report.run_ids[1])
        row.execution_environment = {}
    with Session(database_engine()) as session:
        rows = [session.get(ExperimentRecord, run_id) for run_id in report.run_ids]
        status, reasons, metrics = evidence_lab._compare(plan, rows, [load_result(i) for i in report.run_ids], [])
    assert status == "not_comparable" and metrics == []
    assert any("统计口径缺失" in reason for reason in reasons)
    dispose_database()


def test_partial_failure_preserves_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "partial.db"))
    dispose_database()
    plan = create_plan(request("same_input_comparison", [{"values": [2, 1]}, {"values": [2, 1]}]))
    original = evidence_lab.run_experiment
    calls = 0

    def fail_second(config):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("deliberate failure")
        return original(config)

    monkeypatch.setattr(evidence_lab, "run_experiment", fail_second)
    report = execute_plan(plan.plan_id)
    assert load_plan(plan.plan_id).status == "failed"
    assert len(report.run_ids) == 1 and load_result(report.run_ids[0]) is not None
    assert report.conclusion.startswith("证据不足")
    assert report.errors[0]["kind"] == "execution_or_storage_failed"
    assert report.retryable
    dispose_database()


def test_missing_run_and_invalid_result_block_comparison(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "invalid.db"))
    dispose_database()
    plan = create_plan(request("same_input_comparison", [{"values": [2, 1]}, {"values": [2, 1]}]))
    report = execute_plan(plan.plan_id)
    with Session(database_engine()) as session:
        rows = [session.get(ExperimentRecord, report.run_ids[0]), None]
        status, reasons, _ = evidence_lab._compare(plan, rows, [load_result(i) for i in report.run_ids], [])
    assert status == "not_comparable" and "run_id 不存在" in reasons
    with Session(database_engine()) as session, session.begin():
        row = session.get(ExperimentRecord, report.run_ids[1])
        row.validation = {"valid": False, "reason": "bad output"}
    with Session(database_engine()) as session:
        rows = [session.get(ExperimentRecord, i) for i in report.run_ids]
        status, reasons, _ = evidence_lab._compare(plan, rows, [load_result(i) for i in report.run_ids], [])
    assert status == "not_comparable" and "执行失败或输出验证失败" in reasons
    dispose_database()


def test_run_storage_failure_never_marks_success(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGOVERSE_DB_PATH", str(tmp_path / "storage.db"))
    dispose_database()
    plan = create_plan(request("same_input_comparison", [{"values": [2, 1]}, {"values": [2, 1]}]))

    def fail_save(_result):
        raise OSError("disk full")

    monkeypatch.setattr(evidence_lab, "save_result", fail_save)
    report = execute_plan(plan.plan_id)
    assert load_plan(plan.plan_id).status == "failed"
    assert report.run_ids == [] and report.conclusion.startswith("证据不足")
    assert "disk full" in report.errors[0]["message"]
    dispose_database()
