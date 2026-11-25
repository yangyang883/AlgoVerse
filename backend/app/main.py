from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


def request_id(request: Request) -> str:
    if not hasattr(request.state, "request_id"):
        request.state.request_id = str(uuid4())
    return request.state.request_id


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=APIResponse(
        error=APIError(code="VALIDATION_ERROR", message="Invalid request", details={"errors": jsonable_encoder(exc.errors())}),
        request_id=request_id(request),
    ).model_dump(mode="json"))


@app.get("/api/v1/health", response_model=APIResponse[dict])
def health(request: Request):
    return APIResponse(data={"status": "ok"}, request_id=request_id(request))


@app.get("/api/v1/algorithms", response_model=APIResponse[list])
def algorithms(request: Request):
    return APIResponse(data=CAPABILITIES, request_id=request_id(request))


@app.post("/api/v1/experiments/run", response_model=APIResponse[ExperimentResult])
def run(request: Request, config: ExperimentConfig):
    return APIResponse(data=run_experiment(config), request_id=request_id(request))


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
    return not_implemented(request)


@app.post("/api/v1/experiments/compare", response_model=APIResponse[CompareResult])
def compare(request: Request, body: CompareRequest):
    return not_implemented(request)


@app.get("/api/v1/experiments/{run_id}", response_model=APIResponse[ExperimentResult])
def get_experiment(request: Request, run_id: str):
    return not_implemented(request)


@app.get("/api/v1/experiments/{run_id}/report", response_model=APIResponse[ReportResult])
def get_report(request: Request, run_id: str):
    return not_implemented(request)
