"""Qwen 兼容 API Provider（AV-M1-D02）。

只做 HTTP 调用、超时/非 2xx/无效 JSON 处理与脱敏记录；
不做算法执行、不做工具调度、不做会话状态管理。

环境变量：QWEN_BASE_URL / QWEN_MODEL / QWEN_API_KEY / QWEN_TIMEOUT / QWEN_TEMPERATURE
接口格式：OpenAI 兼容 POST {base_url}/chat/completions
"""

import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

from app.ai import errors

PROVIDER_VERSION = "1.0.0"
ENV_BASE_URL = "QWEN_BASE_URL"
ENV_MODEL = "QWEN_MODEL"
ENV_API_KEY = "QWEN_API_KEY"
ENV_TIMEOUT = "QWEN_TIMEOUT"
ENV_TEMPERATURE = "QWEN_TEMPERATURE"
ENV_FILE_NAME = ".env"
_DOTENV_LOADED = False


def load_dotenv(reload: bool = False) -> Optional[Path]:
    """从当前目录向上、再从模块路径向上查找 .env，载入未设置的环境变量。

    系统环境变量优先，.env 不覆盖已显式设置的变量；找不到文件时不报错。
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED and not reload:
        return None
    _DOTENV_LOADED = True

    candidates: List[Path] = []
    starts = [Path.cwd().resolve(), Path(__file__).resolve().parent]
    for start in starts:
        for parent in [start] + list(start.parents)[:5]:
            candidates.append(parent / ENV_FILE_NAME)

    seen = set()
    for path in candidates:
        key = str(path)
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            if "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if name and value and name not in os.environ:
                os.environ[name] = value
        return path
    return None


def mask_secret(text: str) -> str:
    """对 Bearer Token 与常见 Key 形式做掩码。"""
    if not text:
        return text
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{6,}", r"\1***MASKED***", text)
    text = re.sub(
        r"(?i)(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9._\-]{6,}",
        r"\1***MASKED***",
        text,
    )
    # 内联 sk-xxxxxxxx 形式的 Key（如用户提示词里粘贴的凭据）
    text = re.sub(r"sk-[A-Za-z0-9._\-]{6,}", "sk-***MASKED***", text)
    return text


def new_request_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    model: str
    api_key: Optional[str] = None
    timeout: float = 30.0
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        load_dotenv()
        return cls(
            base_url=os.environ.get(ENV_BASE_URL, "").rstrip("/"),
            model=os.environ.get(ENV_MODEL, ""),
            api_key=os.environ.get(ENV_API_KEY) or None,
            timeout=float(os.environ.get(ENV_TIMEOUT, "30")),
            temperature=float(os.environ.get(ENV_TEMPERATURE, "0")),
        )

    @classmethod
    def from_values(
        cls,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        temperature: float = 0.0,
    ) -> "ProviderConfig":
        return cls(base_url.rstrip("/"), model, api_key, timeout, temperature)

    def check_real_call(self) -> None:
        missing = [
            name
            for name, value in (
                (ENV_BASE_URL, self.base_url),
                (ENV_MODEL, self.model),
                (ENV_API_KEY, self.api_key),
            )
            if not value
        ]
        if missing:
            raise errors.AIError(
                code=errors.NO_CREDENTIAL,
                message="未配置真实模型调用所需的环境变量：" + ", ".join(missing),
                detail={"missing": missing},
                retryable=False,
            )


@dataclass
class ModelResponse:
    content: str
    request_id: str
    model: str
    source: str  # qwen | mock
    raw_snippet: str  # 已脱敏
    usage: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0


class QwenProvider:
    """真实调用与离线 Mock 共用接口；Mock 结果必须显式标注 source='mock'。"""

    def __init__(self, config: Optional[ProviderConfig] = None) -> None:
        self.config = config or ProviderConfig.from_env()
        self._client = httpx.Client(timeout=httpx.Timeout(self.config.timeout))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "QwenProvider":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        *,
        source: str = "qwen",
        response_format: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        mock_fn: Optional[Callable[[List[Dict[str, str]]], str]] = None,
    ) -> ModelResponse:
        rid = request_id or new_request_id()
        if source == "mock":
            return self._mock_chat(messages, rid, mock_fn)
        if source != "qwen":
            raise errors.AIError(
                code=errors.NO_CREDENTIAL,
                message="source 只能是 qwen 或 mock",
                detail={"source": source},
                retryable=False,
            )

        self.config.check_real_call()
        body: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "response_format": response_format or {"type": "json_object"},
        }
        headers = {
            "Authorization": "Bearer " + str(self.config.api_key),
            "Content-Type": "application/json",
        }
        url = self.config.base_url + "/chat/completions"
        started = datetime.now(timezone.utc)

        try:
            resp = self._client.post(url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise errors.AIError(
                code=errors.REQUEST_TIMEOUT,
                message=f"模型请求超时（{self.config.timeout}s）",
                detail={"timeout": self.config.timeout},
                retryable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise errors.AIError(
                code=errors.HTTP_ERROR,
                message="模型服务不可达：" + type(exc).__name__,
                detail={"error": type(exc).__name__},
                retryable=True,
            ) from exc

        latency_ms = (datetime.now(timezone.utc) - started).total_seconds() * 1000
        if resp.status_code < 200 or resp.status_code >= 300:
            raise errors.AIError(
                code=errors.HTTP_ERROR,
                message=f"模型服务返回 HTTP {resp.status_code}",
                detail={
                    "status_code": resp.status_code,
                    "body": mask_secret(resp.text[:500]),
                    "latency_ms": round(latency_ms, 2),
                },
                retryable=resp.status_code in (408, 429, 500, 502, 503, 504),
            )

        try:
            payload = resp.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise errors.AIError(
                code=errors.INVALID_JSON,
                message="模型响应不是合法的 Chat Completions JSON",
                detail={"snippet": mask_secret(resp.text[:500])},
                retryable=False,
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise errors.AIError(
                code=errors.EMPTY_RESPONSE,
                message="模型响应正文为空",
                detail={},
                retryable=False,
            )

        return ModelResponse(
            content=content.strip(),
            request_id=rid,
            model=self.config.model,
            source="qwen",
            raw_snippet=mask_secret(json.dumps(payload, ensure_ascii=False)[:500]),
            usage=payload.get("usage"),
            latency_ms=round(latency_ms, 2),
        )

    def _mock_chat(
        self,
        messages: List[Dict[str, str]],
        rid: str,
        mock_fn: Optional[Callable[[List[Dict[str, str]]], str]],
    ) -> ModelResponse:
        if mock_fn is None:
            raise errors.AIError(
                code=errors.NO_CREDENTIAL,
                message="source='mock' 但未提供 mock_fn",
                detail={},
                retryable=False,
            )
        content = mock_fn(messages)
        if not isinstance(content, str):
            raise errors.AIError(
                code=errors.INVALID_JSON,
                message="mock_fn 必须返回字符串 JSON",
                detail={},
                retryable=False,
            )
        return ModelResponse(
            content=content,
            request_id=rid,
            model="offline-mock-v1",
            source="mock",
            raw_snippet="[OFFLINE MOCK] " + content[:500],
            usage=None,
            latency_ms=0.0,
        )


def write_transcript(
    path: Union[str, Path],
    *,
    request: Dict[str, Any],
    response: Optional[ModelResponse] = None,
    error: Optional[errors.AIError] = None,
) -> Path:
    """把一次请求/响应写入脱敏 JSONL；敏感字段先掩码。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": response.source if response else "qwen",
        "request_id": response.request_id if response else request.get("request_id", ""),
        "request": json.loads(mask_secret(json.dumps(request, ensure_ascii=False))),
        "response": None,
        "error": None,
    }
    if response is not None:
        record["response"] = {
            "content_preview": response.content[:800],
            "raw_snippet": response.raw_snippet,
            "model": response.model,
            "usage": response.usage,
            "latency_ms": response.latency_ms,
        }
    if error is not None:
        record["error"] = error.public_dict()
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p


def extract_json_object(text: str) -> str:
    """截取第一个完整 JSON 对象；只截取，不修补语法。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    if start < 0:
        raise errors.AIError(errors.INVALID_JSON, "模型输出中找不到 JSON 对象", {})
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start:i + 1]
    raise errors.AIError(errors.INVALID_JSON, "模型输出 JSON 对象未闭合", {})
