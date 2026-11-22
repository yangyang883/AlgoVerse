import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.db.experiments import load_result, save_result
from app.engine.registry import CAPABILITIES
from app.schemas.models import (
    APIError,
    APIResponse,
    ChatRequest,
    ChatResult,
    CompareRequest,
    CompareResult,
    ExperimentConfig,
    ExperimentResult,
    ParseRequest,
    ParseResult,
    ReportResult,
)
from app.services.experiment import run_experiment

app = FastAPI(title="AlgoVerse API", version="0.1.0")
logger = logging.getLogger(__name__)


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


@app.get("/api/v1/health", response_model=APIResponse[dict])
def health(request: Request):
    return APIResponse(data={"status": "ok"}, request_id=request_id(request))


@app.get("/api/v1/algorithms", response_model=APIResponse[list])
def algorithms(request: Request):
    return APIResponse(data=CAPABILITIES, request_id=request_id(request))


@app.post("/api/v1/experiments/run", response_model=APIResponse[ExperimentResult])
def run(request: Request, config: ExperimentConfig):
    result = run_experiment(config)
    save_result(result)
    return APIResponse(data=result, request_id=request_id(request))


def not_implemented(request: Request):
    return JSONResponse(status_code=501, content=APIResponse(
        error=APIError(code="NOT_IMPLEMENTED", message="Scheduled for D2-D12"),
        request_id=request_id(request),
    ).model_dump(mode="json"))


@app.post("/api/v1/chat", response_model=APIResponse[ChatResult])
def chat(request: Request, body: ChatRequest):
    return not_implemented(request)


@app.post("/api/v1/experiments/parse", response_model=APIResponse[ParseResult])
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
        raise HTTPException(status_code=422, detail="Model returned invalid configuration") from exc
    return APIResponse(data=parsed, request_id=request_id(request))


@app.post("/api/v1/experiments/compare", response_model=APIResponse[CompareResult])
def compare(request: Request, body: CompareRequest):
    return not_implemented(request)


@app.get("/api/v1/experiments/{run_id}", response_model=APIResponse[ExperimentResult])
def get_experiment(request: Request, run_id: str):
    result = load_result(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return APIResponse(data=result, request_id=request_id(request))


@app.get("/api/v1/experiments/{run_id}/report", response_model=APIResponse[ReportResult])
def get_report(request: Request, run_id: str):
    return not_implemented(request)
