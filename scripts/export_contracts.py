"""Export the Pydantic source of truth into JSON Schema, OpenAPI and TypeScript."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app
from app.schemas.models import (
    AlgorithmCapability,
    APIError,
    APIResponse,
    ConversationRevisionRequest,
    ConversationStartRequest,
    ConversationState,
    EvidencePlan,
    EvidenceReport,
    ExperimentConfig,
    ExperimentHypothesis,
    ExperimentPlanRequest,
    ExperimentResult,
    ParseRequest,
    ParseResult,
    TraceEvent,
)

MODELS = [
    ExperimentConfig, ExperimentResult, TraceEvent, AlgorithmCapability, ConversationState,
    ConversationStartRequest, ConversationRevisionRequest, ParseRequest, ParseResult, APIError,
    ExperimentHypothesis, ExperimentPlanRequest, EvidencePlan, EvidenceReport,
]
NAMES = {"ExperimentConfig": "experiment", "ExperimentResult": "result", "TraceEvent": "trace"}


def ts_type(schema):
    if isinstance(schema, bool):
        return "unknown"
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    if "const" in schema:
        return json.dumps(schema["const"])
    if "anyOf" in schema:
        return " | ".join(ts_type(part) for part in schema["anyOf"])
    kind = schema.get("type")
    if kind == "array":
        return f"({ts_type(schema['items'])})[]"
    if kind == "object":
        if "properties" in schema:
            required = set(schema.get("required", []))
            fields = [f"{key}{'' if key in required else '?'}: {ts_type(value)}"
                      for key, value in schema["properties"].items()]
            return "{ " + "; ".join(fields) + " }"
        return f"Record<string, {ts_type(schema.get('additionalProperties', {}))}>"
    return {"string": "string", "integer": "number", "number": "number",
            "boolean": "boolean", "null": "null"}.get(kind, "unknown")


def outputs():
    files = {}
    definitions = {}
    for model in MODELS:
        schema = model.model_json_schema(ref_template="#/$defs/{model}")
        definitions.update(schema.pop("$defs", {}))
        files[ROOT / "contracts" / f"{NAMES.get(model.__name__, model.__name__.lower())}.schema.json"] = json.dumps(
            schema, ensure_ascii=False, indent=2) + "\n"
    files[ROOT / "contracts/apiresponse.schema.json"] = json.dumps(
        APIResponse[dict].model_json_schema(), ensure_ascii=False, indent=2
    ) + "\n"
    lines = ["// Generated from backend/app/schemas/models.py. Do not edit.\n"]
    model_names = {model.__name__ for model in MODELS}
    for name, schema in sorted(definitions.items()):
        if name in model_names:
            continue
        lines.append(f"export type {name} = {ts_type(schema)};\n")
    for model in MODELS:
        schema = model.model_json_schema(ref_template="#/$defs/{model}")
        schema.pop("$defs", None)
        lines.append(f"export type {model.__name__} = {ts_type(schema)};\n")
    lines.append("export type APIResponse<T> = { data: T | null; error: APIError | null; request_id: string };\n")
    files[ROOT / "frontend/src/types/contracts.ts"] = "".join(lines)
    files[ROOT / "contracts/openapi.json"] = json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, content in outputs().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if stale:
        parser.exit(1, "Stale contracts:\n" + "\n".join(stale) + "\n")
