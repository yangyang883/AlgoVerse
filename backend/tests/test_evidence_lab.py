import pytest

from app.db.experiments import dispose_database, load_result
from app.schemas.models import ExperimentPlanRequest
from app.services.evidence_lab import create_plan, execute_plan, load_report


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
