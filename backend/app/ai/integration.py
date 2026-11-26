"""AI → 后端 /parse 集成适配层（AV-M1 联调）。

职责：把 ``app.ai.planner.parse`` 包装成组员3路由期望的 callable：

    provider = getattr(app.state, "parse_provider", None)   # 组员3的路由
    parsed = ParseResult.model_validate(provider(body))      # body: ParseRequest

本模块**不修改** main.py / schemas/models.py / db / services，由组员3在启动时注入：

    from app.ai.integration import make_parse_provider
    app.state.parse_provider = make_parse_provider()

异常映射（对齐远程 main.py 的 parse 路由现有 catch）：
    TimeoutError    -> HTTP 504 MODEL_TIMEOUT
    ConnectionError -> HTTP 503 MODEL_UNAVAILABLE
    ValidationError -> HTTP 422 VALIDATION_ERROR
                       AI 细粒度错误码在 error.details.errors[].ctx.code

成功时返回 dict，字段严格限于契约 ParseResult：
    config / source / requires_confirmation
（session_id 由组员3路由用 conversations 状态回填，AI 不自行生成会话。）
"""

from typing import Any, Callable, Dict, Optional

from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from app.ai import errors
from app.ai.planner import ParseOutcome, parse
from app.ai.provider import (
    QwenProvider,
    new_request_id,
    write_transcript,
)

ModelFn = Callable[[Any, str, str], str]

TIMEOUT_CODES = frozenset({errors.REQUEST_TIMEOUT})
CONNECTION_CODES = frozenset({errors.HTTP_ERROR, errors.NO_CREDENTIAL})


def _as_validation_error(outcome: ParseOutcome) -> ValidationError:
    """把 AI 错误码塞进 Pydantic ValidationError，供组员3路由 422 透传。"""
    code = outcome.error_code or errors.PARSE_FAILED
    message = outcome.error_message or code
    ctx = {
        "code": code,
        "retryable": False,
        "request_id": outcome.request_id,
        "prompt_version": outcome.prompt_version,
    }
    if outcome.repair.attempted:
        ctx["repair"] = {
            "attempted": True,
            "failed": outcome.repair.failed,
            "attempts": outcome.repair.attempts,
        }
    return ValidationError.from_exception_data(
        "ParseProvider",
        [{
            "type": PydanticCustomError(code, message, ctx),
            "loc": ("ai", code),
            "input": None,
        }],
    )


def raise_for_outcome(outcome: ParseOutcome) -> None:
    """把 ParseOutcome 失败态映射成组员3路由已 catch 的标准异常。"""
    code = outcome.error_code or errors.PARSE_FAILED
    message = outcome.error_message or code
    if code in TIMEOUT_CODES:
        raise TimeoutError(message)
    if code in CONNECTION_CODES:
        raise ConnectionError(message)
    raise _as_validation_error(outcome)


def make_parse_provider(
    *,
    source: str = "qwen",
    call_model: Optional[ModelFn] = None,
    transcript_path: Optional[str] = None,
    max_repair: int = 1,
) -> Callable[[Any], Dict[str, Any]]:
    """生成可注入 ``app.state.parse_provider`` 的 callable。

    Args:
        source: 'qwen' 真实调用 / 'mock' 离线（需 call_model 提供 mock_fn）。
        call_model: 覆盖模型调用函数，签名 (messages, source, request_id) -> str。
                    缺省时用 QwenProvider.chat_json。
        transcript_path: 脱敏 JSONL 落盘路径；None 时不落盘。
        max_repair: 最多一次修复（计划硬要求）。

    Returns:
        callable(ParseRequest) -> dict，可被 ParseResult.model_validate 接受。
    """
    def provider(body: Any) -> Dict[str, Any]:
        rid = new_request_id()
        owned: Optional[QwenProvider] = None
        fn = call_model
        if fn is None:
            owned = QwenProvider()
            def fn(messages, src, request_id):  # noqa: F811
                resp = owned.chat_json(
                    messages,
                    source=src,
                    request_id=request_id,
                    response_format={"type": "json_object"},
                )
                if transcript_path:
                    write_transcript(
                        transcript_path,
                        request={"messages": messages, "request_id": request_id},
                        response=resp,
                    )
                return resp.content

        try:
            outcome = parse(
                body.text,
                source=source,
                tool_fn=fn,
                request_id=rid,
                max_repair=max_repair,
            )
        finally:
            if owned is not None:
                owned.close()

        if outcome.status == "ok" and outcome.config is not None:
            return {
                "config": outcome.config.model_dump(mode="json"),
                "source": outcome.source,
                "requires_confirmation": True,
            }
        raise_for_outcome(outcome)

    return provider
