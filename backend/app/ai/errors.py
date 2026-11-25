"""AI 模块错误码表（D01 草案，待组员3并入统一异常码表）。

边界：组员1只产出意图、工具建议与配置；白名单校验、状态流转与实际调用归组员3。
所有错误都带可展示给用户的 message；detail 中不得出现 API Key。
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class AIError(Exception):
    code: str
    message: str
    detail: Dict[str, Any] = field(default_factory=dict)
    retryable: bool = False

    def __str__(self) -> str:  # pragma: no cover
        return f"[{self.code}] {self.message}"

    def public_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "detail": self.detail,
        }


# 模型调用
NO_CREDENTIAL = "E-QWEN-NO-CREDENTIAL"
REQUEST_TIMEOUT = "E-QWEN-TIMEOUT"
HTTP_ERROR = "E-QWEN-HTTP"
INVALID_JSON = "E-QWEN-INVALID-JSON"
EMPTY_RESPONSE = "E-QWEN-EMPTY-RESPONSE"

# 解析与校验
SCHEMA_INVALID = "E-SCHEMA-INVALID"
UNKNOWN_FIELD = "E-SCHEMA-UNKNOWN-FIELD"
UNKNOWN_ALGORITHM = "E-UNKNOWN-ALGORITHM"
REPAIR_FAILED = "E-REPAIR-FAILED"
PARSE_FAILED = "E-PARSE-FAILED"
AMBIGUOUS_INPUT = "E-AMBIGUOUS-INPUT"

# 工具建议（不执行）
UNKNOWN_TOOL = "E-UNKNOWN-TOOL"
TOOL_ARGUMENTS_INVALID = "E-TOOL-ARGS-INVALID"

# 检索
INDEX_MISSING = "E-RAG-INDEX-MISSING"
EMBEDDING_UNAVAILABLE = "E-RAG-EMBEDDING-UNAVAILABLE"


def ai_error(code: str, message: str, **detail: Any) -> AIError:
    return AIError(code=code, message=message, detail=detail)
