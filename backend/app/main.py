import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.db.experiments import dispose_database, load_result, save_result
from app.engine.registry import CAPABILITIES
from app.schemas.models import (
    APIError,
    APIResponse,
    ChatRequest,
    ChatResult,
    CompareRequest,
    CompareResult,
    ConversationRevisionRequest,
    ConversationStartRequest,
    ConversationState,
    EvidencePlan,
    EvidenceReport,
    ExperimentConfig,
    ExperimentPlanRequest,
    ExperimentResult,
    ParseRequest,
    ParseResult,
    ReportResult,
)
from app.services.conversation import (
    ConversationCapacity,
    ExpiredConversation,
    InvalidRevision,
    MissingConversation,
    RunConfigConflict,
    conversations,
)
from app.services.evidence_lab import create_plan, execute_plan, load_report
from app.services.experiment import run_experiment


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    dispose_database()


app = FastAPI(title="AlgoVerse API", version="0.1.0", lifespan=lifespan)
logger = logging.getLogger(__name__)
ERROR_RESPONSES = {status: {"model": APIResponse[dict]} for status in (404, 409, 422, 500, 503, 504)}


def request_id(request: Request) -> str:
    if not hasattr(request.state, "request_id"):
        request.state.request_id = str(uuid4())
    return request.state.request_id


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id(request)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def error_response(request: Request, status: int, code: str, message: str, details=None):
    return JSONResponse(status_code=status, content=APIResponse(
        error=APIError(code=code, message=message, details=details),
        request_id=request_id(request),
    ).model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return error_response(request, 422, "VALIDATION_ERROR", "Invalid request",
                          {"errors": jsonable_encoder(exc.errors())})


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    codes = {404: "NOT_FOUND", 409: "CONTEXT_CONFLICT", 422: "VALIDATION_ERROR",
             503: "MODEL_UNAVAILABLE", 504: "MODEL_TIMEOUT"}
    return error_response(request, exc.status_code, codes.get(exc.status_code, "HTTP_ERROR"),
                          str(exc.detail))


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    logger.error("request %s failed: %s", request_id(request), type(exc).__name__)
    return error_response(request, 500, "INTERNAL_ERROR", "Internal server error")


@app.exception_handler(MissingConversation)
async def missing_conversation(request: Request, exc: MissingConversation):
    return error_response(request, 409, "CONTEXT_CONFLICT", "Conversation context is missing")


@app.exception_handler(ExpiredConversation)
async def expired_conversation(request: Request, exc: ExpiredConversation):
    return error_response(request, 409, "SESSION_EXPIRED", "Conversation has expired")


@app.exception_handler(ConversationCapacity)
async def session_capacity(request: Request, exc: ConversationCapacity):
    return error_response(request, 503, "SESSION_CAPACITY", "Conversation capacity reached")


@app.exception_handler(InvalidRevision)
async def invalid_revision(request: Request, exc: InvalidRevision):
    return error_response(request, 422, "VALIDATION_ERROR", str(exc))


@app.exception_handler(RunConfigConflict)
async def run_config_conflict(request: Request, exc: RunConfigConflict):
    return error_response(request, 409, "CONFIG_CONFLICT", str(exc))


@app.get("/api/v1/health", response_model=APIResponse[dict])
def health(request: Request):
    return APIResponse(data={"status": "ok"}, request_id=request_id(request))


@app.get("/api/v1/algorithms", response_model=APIResponse[list])
def algorithms(request: Request):
    return APIResponse(data=CAPABILITIES, request_id=request_id(request))


@app.post("/api/v1/evidence/plans", response_model=APIResponse[EvidencePlan], responses=ERROR_RESPONSES)
def post_evidence_plan(request: Request, body: ExperimentPlanRequest):
    try:
        plan = create_plan(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return APIResponse(data=plan, request_id=request_id(request))


@app.post("/api/v1/evidence/plans/{plan_id}/run", response_model=APIResponse[EvidenceReport], responses=ERROR_RESPONSES)
def run_evidence_plan(request: Request, plan_id: str):
    try:
        report = execute_plan(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="Evidence plan not found")
    return APIResponse(data=report, request_id=request_id(request))


@app.get("/api/v1/evidence/reports/{evidence_id}", response_model=APIResponse[EvidenceReport], responses=ERROR_RESPONSES)
def get_evidence_report(request: Request, evidence_id: str):
    report = load_report(evidence_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Evidence report not found")
    return APIResponse(data=report, request_id=request_id(request))


@app.post("/api/v1/experiments/run", response_model=APIResponse[ExperimentResult],
          responses=ERROR_RESPONSES)
def run(request: Request, config: ExperimentConfig):
    x_session_id = request.headers.get("X-Session-ID")

    def execute():
        result = run_experiment(config)
        save_result(result)
        return result

    result = conversations.execute_run(x_session_id, config, execute) if x_session_id else execute()
    return APIResponse(data=result, request_id=request_id(request))


@app.post("/api/v1/conversations", response_model=APIResponse[ConversationState],
          responses=ERROR_RESPONSES)
def start_conversation(request: Request, body: ConversationStartRequest):
    return APIResponse(data=conversations.start(body.config), request_id=request_id(request))


@app.get("/api/v1/conversations/{session_id}", response_model=APIResponse[ConversationState],
         responses=ERROR_RESPONSES)
def get_conversation(request: Request, session_id: str):
    return APIResponse(data=conversations.get(session_id), request_id=request_id(request))


@app.post("/api/v1/conversations/{session_id}/revise",
          response_model=APIResponse[ConversationState], responses=ERROR_RESPONSES)
def revise_conversation(request: Request, session_id: str, body: ConversationRevisionRequest):
    return APIResponse(data=conversations.revise(session_id, body.changes),
                       request_id=request_id(request))


def not_implemented(request: Request):
    return JSONResponse(status_code=501, content=APIResponse(
        error=APIError(code="NOT_IMPLEMENTED", message="Scheduled for D2-D12"),
        request_id=request_id(request),
    ).model_dump(mode="json"))


@app.post("/api/v1/chat", response_model=APIResponse[ChatResult])
def chat(request: Request, body: ChatRequest):
    return not_implemented(request)


@app.post("/api/v1/experiments/parse", response_model=APIResponse[ParseResult],
          responses=ERROR_RESPONSES)
def parse(request: Request, body: ParseRequest):
    provider = getattr(app.state, "parse_provider", None)
    if provider is None:
        return not_implemented(request)
    try:
        parsed = ParseResult.model_validate(provider(body))
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Model service timed out") from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail="Model service unavailable") from exc
    except ValidationError as exc:
        return error_response(request, 422, "VALIDATION_ERROR", "Model returned invalid configuration",
                              {"errors": jsonable_encoder(exc.errors())})
    state = (conversations.accept_parse(body.session_id, parsed.config, body.confirmed_changes)
             if body.session_id else conversations.start(parsed.config))
    parsed = parsed.model_copy(update={"session_id": state.session_id, "config": state.last_config})
    return APIResponse(data=parsed, request_id=request_id(request))


@app.post("/api/v1/experiments/compare", response_model=APIResponse[CompareResult],
          responses=ERROR_RESPONSES)
def compare(request: Request, body: CompareRequest):
    runs = [load_result(run_id) for run_id in body.run_ids]
    if any(run is None for run in runs):
        raise HTTPException(status_code=404, detail="Experiment not found")
    if any(run.input != runs[0].input for run in runs[1:]):
        raise HTTPException(status_code=409, detail="Experiments must use the same input")
    return APIResponse(data=CompareResult(runs=runs, same_input=True), request_id=request_id(request))


@app.get("/api/v1/experiments/{run_id}", response_model=APIResponse[ExperimentResult],
         responses=ERROR_RESPONSES)
def get_experiment(request: Request, run_id: str):
    result = load_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return APIResponse(data=result, request_id=request_id(request))


@app.get("/api/v1/experiments/{run_id}/report", response_model=APIResponse[ReportResult])
def get_report(request: Request, run_id: str):
    return not_implemented(request)
