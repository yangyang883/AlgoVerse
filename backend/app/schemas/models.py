from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExperimentInput(StrictModel):
    size: int = Field(default=20, ge=0, le=2000)
    distribution: Literal["random", "sorted", "reversed"] = "random"
    seed: int = 42
    values: Optional[List[int]] = None

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
    parameters: Dict[str, Any] = Field(default_factory=dict)
    visualization: Visualization = Field(default_factory=Visualization)
    metrics: List[Literal["comparisons", "swaps", "elapsed_ms"]] = Field(
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
    indices: List[int] = Field(default_factory=list)
    array: Optional[List[int]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationResult(StrictModel):
    valid: bool
    reason: Optional[str] = None


class ExperimentResult(StrictModel):
    run_id: str
    status: Literal["completed", "failed"]
    config: ExperimentConfig
    input: List[int]
    output: List[int]
    metrics: Dict[str, float]
    validation: ValidationResult
    trace: List[TraceEvent]
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


class APIError(StrictModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    data: Optional[T] = None
    error: Optional[APIError] = None
    request_id: str


class ParseRequest(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ParseResult(StrictModel):
    config: ExperimentConfig
    source: Literal["qwen", "manual", "mock"]
    requires_confirmation: bool = True


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResult(StrictModel):
    session_id: str
    answer: str
    sources: List[str] = Field(default_factory=list)
    state: ConversationState


class CompareRequest(StrictModel):
    run_ids: List[str] = Field(min_length=2)


class CompareResult(StrictModel):
    runs: List[ExperimentResult]
    same_input: bool


class ReportResult(StrictModel):
    run: ExperimentResult
    explanation: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
