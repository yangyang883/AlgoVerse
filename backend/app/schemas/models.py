from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExperimentInput(StrictModel):
    size: int = Field(default=20, ge=0, le=2000)
    distribution: Literal["random", "sorted", "reversed"] = "random"
    seed: int = 42
    values: Optional[list[int]] = None

    @model_validator(mode="after")
    def check_values(self):
        if self.values is not None:
            if len(self.values) > 2000:
                raise ValueError("values may contain at most 2000 items")
            self.size = len(self.values)
        return self


class Visualization(StrictModel):
    enabled: bool = True


class ExperimentConfig(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    algorithm: Literal["bubble_sort"] = "bubble_sort"
    mode: Literal["experiment"] = "experiment"
    input: ExperimentInput = Field(default_factory=ExperimentInput)
    parameters: dict[str, Any] = Field(default_factory=dict)
    visualization: Visualization = Field(default_factory=Visualization)
    metrics: list[Literal["comparisons", "swaps", "elapsed_ms"]] = Field(
        default_factory=lambda: ["comparisons", "swaps", "elapsed_ms"]
    )

    @model_validator(mode="after")
    def no_parameters_yet(self):
        if self.parameters:
            raise ValueError("bubble_sort does not accept parameters")
        if self.visualization.enabled and self.input.size > 40:
            raise ValueError("visualization is limited to 40 items")
        return self


class TraceEvent(StrictModel):
    step: int = Field(ge=0)
    type: Literal["initial", "compare", "swap", "write", "pivot", "complete"]
    indices: list[int] = Field(default_factory=list)
    array: Optional[list[int]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(StrictModel):
    valid: bool
    reason: Optional[str] = None


class ExperimentResult(StrictModel):
    run_id: str
    status: Literal["completed", "failed"]
    config: ExperimentConfig
    input: list[int]
    output: list[int]
    metrics: dict[str, float]
    validation: ValidationResult
    trace: list[TraceEvent]
    trace_truncated: bool
    created_at: datetime


class AlgorithmCapability(StrictModel):
    name: str
    level: Literal["L1", "L2", "L3", "L4"]
    executable: bool
    visualizable: bool
    max_input_size: int


class ConversationState(StrictModel):
    session_id: str
    current_algorithm: Optional[str] = None
    last_config: Optional[ExperimentConfig] = None
    last_run_id: Optional[str] = None
    summary: str = ""
    modified_fields: list[str] = Field(default_factory=list)


class ConversationStartRequest(StrictModel):
    config: ExperimentConfig


class ConversationRevisionRequest(StrictModel):
    changes: dict[str, Any] = Field(min_length=1)


class APIError(StrictModel):
    code: str
    message: str
    details: Optional[dict[str, Any]] = None


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    error: Optional[APIError] = None
    request_id: str


class ParseRequest(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None
    confirmed_changes: Optional[dict[str, Any]] = None


class ParseResult(StrictModel):
    config: ExperimentConfig
    source: Literal["qwen", "manual", "mock"]
    requires_confirmation: bool = True
    session_id: Optional[str] = None


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResult(StrictModel):
    session_id: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    state: ConversationState


class CompareRequest(StrictModel):
    run_ids: list[str] = Field(min_length=2)


class CompareResult(StrictModel):
    runs: list[ExperimentResult]
    same_input: bool


class ReportResult(StrictModel):
    run: ExperimentResult
    explanation: Optional[str] = None
    limitations: list[str] = Field(default_factory=list)


class ExperimentHypothesis(StrictModel):
    hypothesis_id: str
    hypothesis_type: Literal["distribution_effect", "same_input_comparison"]
    question: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    expected_observation: str = Field(min_length=1)


class ExperimentPlanRequest(StrictModel):
    hypothesis: ExperimentHypothesis
    experiment_type: Literal["distribution_effect", "same_input_comparison"]
    configurations: list[ExperimentConfig] = Field(min_length=2, max_length=10)
    repetitions: int = Field(default=1, ge=1, le=10)


class EvidencePlan(ExperimentPlanRequest):
    plan_id: str
    status: Literal["validated", "running", "completed", "failed"] = "validated"
    created_at: datetime


class EvidenceReport(StrictModel):
    evidence_id: str
    plan_id: str
    run_ids: list[str]
    input_fingerprints: list[str]
    observed_metrics: list[dict[str, float]]
    validation_results: list[ValidationResult]
    comparison_validity: bool
    comparison_status: Literal["comparable", "partially_comparable", "not_comparable"] = "not_comparable"
    comparison_reasons: list[str] = Field(default_factory=list)
    comparable_metrics: list[str] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    retryable: bool = False
    reproducibility_metadata: dict[str, Any]
    conclusion: str
    limitations: list[str]
    created_at: datetime
