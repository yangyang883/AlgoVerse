"""Deterministic experiment planning and evidence validation."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.orm import Session

from app.db.experiments import Base, database_engine, load_result, save_result
from app.engine.registry import CAPABILITIES
from app.schemas.models import EvidencePlan, EvidenceReport, ExperimentPlanRequest
from app.services.experiment import run_experiment


class PlanRecord(Base):
    __tablename__ = "evidence_plans"
    plan_id = Column(String, primary_key=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ReportRecord(Base):
    __tablename__ = "evidence_reports"
    evidence_id = Column(String, primary_key=True)
    plan_id = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


def _session():
    engine = database_engine()
    Base.metadata.create_all(engine)
    return Session(engine)


def create_plan(body: ExperimentPlanRequest) -> EvidencePlan:
    if body.hypothesis.hypothesis_type != body.experiment_type:
        raise ValueError("hypothesis type and experiment type differ")
    available = {c.name for c in CAPABILITIES if c.executable}
    if any(c.algorithm not in available for c in body.configurations):
        raise ValueError("algorithm is not executable")
    configs = body.configurations
    if body.experiment_type == "distribution_effect":
        inputs = [c.input for c in configs]
        if any(i.values is not None for i in inputs) or len({i.distribution for i in inputs}) != len(inputs):
            raise ValueError("distribution experiment requires distinct generated distributions")
        if len({i.size for i in inputs}) != 1 or len({c.algorithm for c in configs}) != 1:
            raise ValueError("distribution experiment must control size and algorithm")
    else:
        if any(c.input.values is None for c in configs):
            raise ValueError("fair comparison requires explicit identical values")
        if len({tuple(c.input.values) for c in configs}) != 1:
            raise ValueError("fair comparison requires identical input")
        if len({tuple(c.metrics) for c in configs}) != 1:
            raise ValueError("metric definitions differ")
    plan = EvidencePlan(**body.model_dump(), plan_id=str(uuid4()), created_at=datetime.now(timezone.utc))
    with _session() as session, session.begin():
        session.add(PlanRecord(plan_id=plan.plan_id, payload=plan.model_dump(mode="json"), created_at=plan.created_at))
    return plan


def load_plan(plan_id: str):
    with _session() as session:
        row = session.get(PlanRecord, plan_id)
        return EvidencePlan.model_validate(row.payload) if row else None


def load_report(evidence_id: str):
    with _session() as session:
        row = session.get(ReportRecord, evidence_id)
        return EvidenceReport.model_validate(row.payload) if row else None


def execute_plan(plan_id: str) -> EvidenceReport | None:
    plan = load_plan(plan_id)
    if plan is None:
        return None
    if plan.status != "validated":
        raise ValueError("plan has already run")
    runs = []
    failure = None
    for config in plan.configurations:
        for _ in range(plan.repetitions):
            try:
                result = run_experiment(config)
                save_result(result)
                runs.append(result)
                if result.status != "completed":
                    failure = "algorithm execution failed"
                    break
            except Exception as exc:  # noqa: BLE001 - persist partial evidence and failed plan
                failure = f"execution failed: {type(exc).__name__}"
                break
        if failure:
            break
    persisted = [load_result(run.run_id) for run in runs]
    valid_runs = all(r is not None and r.status == "completed" and r.validation.valid and
                     r.output == sorted(r.input) for r in persisted)
    same_input = len({tuple(r.input) for r in persisted if r}) == 1
    fair = plan.experiment_type == "same_input_comparison" and same_input and valid_runs and not failure
    limitations = []
    if plan.experiment_type == "distribution_effect":
        limitations.append("条件变化实验；不同输入不能作为同输入公平对照。")
    if any(r.trace_truncated for r in persisted if r):
        limitations.append("部分轨迹已截断。")
    if failure or not valid_runs or len(persisted) != len(plan.configurations) * plan.repetitions:
        limitations.append(failure or "证据缺失或输出验证失败。")
    if any("elapsed_ms" in r.metrics for r in persisted if r):
        limitations.append("运行时间仅反映当前环境与输入；不构成渐近复杂度证明。")
    conclusion = ("证据不足，无法形成确定性结论。" if failure or not valid_runs or not persisted else
                  "当前输入和实现下的实际观测已记录；请按各 run_id 核对指标。")
    report = EvidenceReport(
        evidence_id=str(uuid4()), plan_id=plan_id, run_ids=[r.run_id for r in runs],
        input_fingerprints=[hashlib.sha256(json.dumps(r.input).encode()).hexdigest() for r in runs],
        observed_metrics=[r.metrics for r in runs], validation_results=[r.validation for r in runs],
        comparison_validity=fair,
        reproducibility_metadata={"algorithm_version": "bubble_sort:v1", "metric_definition": "registry executor v1",
                                  "python": platform.python_version(), "seeds": [r.config.input.seed for r in runs]},
        conclusion=conclusion, limitations=limitations, created_at=datetime.now(timezone.utc),
    )
    with _session() as session, session.begin():
        row = session.get(PlanRecord, plan_id)
        row.payload = plan.model_copy(update={"status": "failed" if failure or not valid_runs else "completed"}).model_dump(mode="json")
        session.add(ReportRecord(evidence_id=report.evidence_id, plan_id=plan_id,
                                 payload=report.model_dump(mode="json"), created_at=report.created_at))
    return report
