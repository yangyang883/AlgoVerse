"""D03 实验配置解析器（AV-M1-D03）。

流程：自然语言 → 模型 JSON → StrictModel 校验（未知字段拒绝）→ 最多一次修复
→ ParseOutcome。算法名先只允许注册表 executable=True 的项。

边界：
- 输出必须是组员3 Pydantic 模型 ExperimentConfig；失败返回内部状态与错误码，
  由组员3映射到 HTTP 错误体（当前 ParseResult.config 必填，无法承载错误态）。
- 不执行算法、不访问工具；仅输出工具选择建议。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import ValidationError

from app.ai import errors
from app.ai.prompts import (
    PROMPT_VERSION,
    build_parse_messages,
    build_repair_messages,
)
from app.ai.provider import (
    QwenProvider,
    extract_json_object,
    new_request_id,
)
from app.engine.registry import CAPABILITIES
from app.schemas.models import ExperimentConfig

ToolFn = Callable[[list[dict[str, str]], str, str], Any]


@dataclass
class RepairInfo:
    attempted: bool = False
    reason: str = ""
    failed: bool = False
    attempts: int = 0


@dataclass
class ParseOutcome:
    """AI 模块内部结果；成功时可转为契约 ParseResult。"""

    status: str  # ok | needs_clarification | error
    config: ExperimentConfig | None = None
    source: str = "qwen"
    tool_suggestions: list[dict[str, Any]] = field(default_factory=list)
    clarification: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    repair: RepairInfo = field(default_factory=RepairInfo)
    request_id: str = ""
    prompt_version: str = PROMPT_VERSION
    raw_model_output: str = ""

    def to_contract_result(self):
        """成功态转组员3契约 ParseResult；失败态调用方应改用 APIError。"""
        from app.schemas.models import ParseResult

        if self.status != "ok" or self.config is None:
            raise ValueError("只有 status=ok 且 config 存在时才能转换")
        return ParseResult(config=self.config, source=self.source, requires_confirmation=True)


def _known_algorithms() -> dict[str, Any]:
    return {c.name: c for c in CAPABILITIES}


def _validate_model_json(parsed: dict[str, Any]) -> ParseOutcome:
    """校验模型输出；Unknown field 与非法枚举都在此拒绝。"""
    allowed_top = {"status", "config", "tool_suggestions", "clarification", "error_code"}
    extra = set(parsed.keys()) - allowed_top
    if extra:
        raise errors.AIError(
            errors.UNKNOWN_FIELD,
            "模型输出含未知字段：" + ", ".join(sorted(extra)),
            {"fields": sorted(extra)},
        )

    status = parsed.get("status")
    if status not in ("ok", "needs_clarification", "error"):
        raise errors.AIError(errors.PARSE_FAILED, "status 必须是 ok/needs_clarification/error", {})

    suggestions = parsed.get("tool_suggestions", [])
    if not isinstance(suggestions, list):
        raise errors.AIError(errors.TOOL_ARGUMENTS_INVALID, "tool_suggestions 必须是数组", {})
    whitelist = {
        "search_knowledge", "get_algorithm_capability", "generate_dataset",
        "run_registered_algorithm", "validate_result", "compare_runs",
        "summarize_experiment",
    }
    for item in suggestions:
        if not isinstance(item, dict) or item.get("tool") not in whitelist:
            raise errors.AIError(errors.UNKNOWN_TOOL, "建议了白名单外的工具", {"tool": str(item)})

    if status in ("needs_clarification", "error"):
        return ParseOutcome(
            status=status,
            clarification=parsed.get("clarification"),
            error_code=parsed.get("error_code")
            or (errors.AMBIGUOUS_INPUT if status == "needs_clarification" else errors.PARSE_FAILED),
            error_message=parsed.get("clarification"),
            tool_suggestions=suggestions,
        )

    config_obj = parsed.get("config")
    if not isinstance(config_obj, dict):
        raise errors.AIError(errors.PARSE_FAILED, "status=ok 但 config 缺失", {})
    try:
        config = ExperimentConfig.model_validate(config_obj)
    except ValidationError as exc:
        fields = [e.get("loc", ())[:1] for e in exc.errors()]
        code = errors.SCHEMA_INVALID
        if config_obj.get("algorithm") not in _known_algorithms():
            code = errors.UNKNOWN_ALGORITHM
        elif any("parameters" in str(f) for f in fields):
            code = errors.UNKNOWN_FIELD
        raise errors.AIError(
            code,
            "配置校验失败：" + str(exc.errors())[:400],
            {"errors": exc.errors()},
        ) from exc

    # 算法必须在注册表中可执行（防止绕过 schema 扩展）
    # ExperimentConfig.algorithm 是 Literal，Pydantic 校验后为 str。
    algorithm_name = str(config.algorithm)
    capability = _known_algorithms().get(algorithm_name)
    if capability is None or not capability.executable:
        raise errors.AIError(
            errors.UNKNOWN_ALGORITHM,
            f"算法 {algorithm_name} 当前不可执行",
            {"algorithm": algorithm_name},
        )

    return ParseOutcome(
        status="ok",
        config=config,
        tool_suggestions=suggestions,
    )


def _error_outcome(
    code: str,
    message: str,
    source: str,
    rid: str,
    repair: RepairInfo,
    raw: str,
) -> ParseOutcome:
    return ParseOutcome(
        status="error",
        source=source,
        error_code=code,
        error_message=message,
        repair=repair,
        request_id=rid,
        raw_model_output=raw[:1500],
    )


def parse(
    text: str,
    *,
    source: str = "qwen",
    session=None,
    provider: QwenProvider | None = None,
    tool_fn: ToolFn | None = None,
    request_id: str | None = None,
    max_repair: int = 1,
) -> ParseOutcome:
    """D03 主入口：一句话 → 受约束配置。

    Args:
        text: 用户自然语言。
        source: 'qwen' 真实调用 / 'mock' 离线预案。
        session: 会话切片（可选，D06 前仅占位）。
        provider: 可注入的 Provider；缺省时按环境变量创建。
        tool_fn: 测试用模型调用函数，签名 (messages, source, rid) -> content。
        request_id: 统一信封 request_id 透传。
        max_repair: 最多修复次数（计划要求最多 1 次）。
    """
    rid = request_id or new_request_id()
    repair = RepairInfo()
    own_provider = False
    if provider is None:
        provider = QwenProvider()
        own_provider = True

    def call(messages) -> str:
        if tool_fn is not None:
            return tool_fn(messages, source, rid)
        resp = provider.chat_json(messages, source=source, request_id=rid)
        return resp.content

    def finalize(outcome: ParseOutcome) -> ParseOutcome:
        outcome.source = source
        outcome.request_id = rid
        return outcome

    try:
        messages = build_parse_messages(text, session)
        raw = extract_json_object(call(messages))
        try:
            return finalize(_validate_model_json(json.loads(raw)))
        except (ValueError, errors.AIError) as exc:
            # 最多一次修复
            if max_repair < 1:
                raise
            repair.attempted = True
            repair.attempts = 1
            repair.reason = str(exc)[:500]
            repaired_raw = extract_json_object(
                call(build_repair_messages(text, raw, repair.reason, session))
            )
            outcome = _validate_model_json(json.loads(repaired_raw))
            outcome.repair = repair
            return finalize(outcome)
    except errors.AIError as exc:
        if repair.attempted:
            repair.failed = True
        return _error_outcome(exc.code, exc.message, source, rid, repair, "")
    except ValueError:
        if repair.attempted:
            repair.failed = True
        return _error_outcome(
            errors.INVALID_JSON,
            "模型输出 JSON 无法解析",
            source,
            rid,
            repair,
            "",
        )
    finally:
        if own_provider:
            provider.close()
