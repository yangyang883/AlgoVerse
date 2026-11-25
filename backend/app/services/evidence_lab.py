"""Deterministic experiment planning and evidence validation."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.orm import Session

from app.db.experiments import Base, ExperimentRecord, database_engine, save_result
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


def _compare(plan, rows, runs, errors):
    reasons = []
    comparable = []
    if plan.experiment_type != "same_input_comparison":
        reasons.append("条件变化实验不属于同输入公平对照")
    if len(rows) != len(plan.configurations) * plan.repetitions or errors:
        reasons.append("运行记录缺失或部分执行失败")
    if any(row is None for row in rows):
        reasons.append("run_id 不存在")
    if len({tuple(row.input_data) for row in rows if row}) != 1:
        reasons.append("实际输入数组不一致")
    for index, row in enumerate(rows):
        if row is None:
            continue
        config = plan.configurations[index // plan.repetitions]
        run = runs[index]
        if row.experiment_config != config.model_dump(mode="json") or row.input_data != run.input:
            reasons.append("实验配置与实际执行不一致")
        if row.status != "completed" or not row.validation.get("valid") or row.output_data != sorted(row.input_data):
            reasons.append("执行失败或输出验证失败")
        if not row.algorithm_version:
            reasons.append("算法版本缺失")
        if row.seed is None or row.seed != config.input.seed:
            reasons.append("随机种子缺失或不一致")
        if row.trace_truncated:
            reasons.append("轨迹截断")
    if not reasons:
        for metric in plan.configurations[0].metrics:
            if any(row is None or metric not in row.metrics for row in rows):
                reasons.append(f"指标 {metric} 缺失")
                continue
            if len({row.algorithm_version for row in rows}) != 1:
                reasons.append(f"指标 {metric} 的算法实现版本不一致")
                continue
            definitions = [(row.execution_environment or {}).get("metric_definitions", {}).get(metric)
                           for row in rows]
            if not all(definitions) or len(set(definitions)) != 1:
                reasons.append(f"指标 {metric} 的统计口径缺失或不一致")
                continue
            if metric == "elapsed_ms":
                keys = ("python", "machine", "system", "processor", "timer", "execution_mode")
                if any(not row.execution_environment or any(not row.execution_environment.get(key) for key in keys)
                       for row in rows):
                    reasons.append("耗时指标的执行环境元数据缺失")
                    continue
                if len({tuple(row.execution_environment[key] for key in keys) for row in rows}) != 1:
                    reasons.append("耗时指标的执行环境不一致")
                    continue
            comparable.append(metric)
    status = ("comparable" if len(comparable) == len(plan.configurations[0].metrics) and not reasons else
              "partially_comparable" if comparable else "not_comparable")
    return status, sorted(set(reasons)), comparable


def execute_plan(plan_id: str) -> EvidenceReport | None:
    with _session() as session, session.begin():
        row = session.get(PlanRecord, plan_id)
        if row is None:
            return None
        plan = EvidencePlan.model_validate(row.payload)
        if plan.status != "validated":
            raise ValueError("plan has already run; retry requires a new plan")
        row.payload = plan.model_copy(update={"status": "running"}).model_dump(mode="json")
    runs = []
    errors = []
    for config in plan.configurations:
        for _ in range(plan.repetitions):
            try:
                result = run_experiment(config)
                save_result(result)
                runs.append(result)
                if result.status != "completed":
                    errors.append({"kind": "execution_failed", "message": result.validation.reason or "algorithm failed"})
                    break
            except Exception as exc:  # noqa: BLE001 - persist partial evidence and failed plan
                errors.append({"kind": "execution_or_storage_failed", "message": f"{type(exc).__name__}: {exc}"})
                break
        if errors:
            break
    try:
        with _session() as session:
            rows = [session.get(ExperimentRecord, run.run_id) for run in runs]
            status, reasons, comparable = _compare(plan, rows, runs, errors)
            metadata = [{"algorithm_version": row.algorithm_version, "execution_environment": row.execution_environment,
                         "seed": row.seed} for row in rows if row]
    except Exception as exc:  # noqa: BLE001 - report an evidence lookup failure
        errors.append({"kind": "evidence_query_failed", "message": f"{type(exc).__name__}: {exc}"})
        rows, metadata, comparable = [], [], []
        status, reasons = "not_comparable", ["证据查询失败"]
    complete = not errors and len(rows) == len(plan.configurations) * plan.repetitions and all(rows)
    valid = complete and all(row.status == "completed" and row.validation.get("valid") for row in rows)
    limitations = reasons + ["当前输入和实现下的观测不构成普遍规律或渐近复杂度证明。"]
    conclusion = ("证据不足，无法形成确定性结论。" if not valid else
                  "当前输入和实现下的观测已记录；仅可比较指标可用于对照。")
    report = EvidenceReport(
        evidence_id=str(uuid4()), plan_id=plan_id, run_ids=[r.run_id for r in runs],
        input_fingerprints=[hashlib.sha256(json.dumps(r.input).encode()).hexdigest() for r in runs],
        observed_metrics=[r.metrics for r in runs], validation_results=[r.validation for r in runs],
        comparison_validity=status == "comparable", comparison_status=status,
        comparison_reasons=reasons, comparable_metrics=comparable,
        errors=errors, retryable=bool(errors),
        reproducibility_metadata={"runs": metadata, "metric_definition": "bubble_sort:v1 comparisons/swaps; time.perf_counter elapsed_ms"},
        conclusion=conclusion, limitations=limitations, created_at=datetime.now(timezone.utc),
    )
    with _session() as session, session.begin():
        row = session.get(PlanRecord, plan_id)
        row.payload = plan.model_copy(update={"status": "completed" if valid else "failed"}).model_dump(mode="json")
        session.add(ReportRecord(evidence_id=report.evidence_id, plan_id=plan_id,
                                 payload=report.model_dump(mode="json"), created_at=report.created_at))
    return report
