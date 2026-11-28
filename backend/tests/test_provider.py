"""AV-M1-D02 Provider 测试（离线预案，不发起真实网络请求）。

当前未提供真实 Qwen 凭据：用 httpx.MockTransport 模拟 HTTP 层覆盖成功 / 超时 /
非 2xx / 无效 JSON / 空响应 / 缺凭据 / 脱敏。凭据到位后运行
scripts/provider_smoke.py 留存真实脱敏记录。
"""

import json

import httpx
import pytest

from app.ai import errors
from app.ai.provider import (
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_MODEL,
    ModelResponse,
    ProviderConfig,
    QwenProvider,
    extract_json_object,
    mask_secret,
    write_transcript,
)


def _response(status, text):
    return httpx.Response(
        status,
        text=text,
        request=httpx.Request("POST", "http://test/chat/completions"),
    )


def _ok_body(content='{"ok":true}'):
    return json.dumps({
        "choices": [{"message": {"content": content}}],
        "usage": {"total_tokens": 12},
    })


def _provider(handler):
    cfg = ProviderConfig.from_values("http://test", "qwen-test", "sk-SECRET123456", timeout=1.0)
    p = QwenProvider(cfg)
    p._client = httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0)
    return p


def test_mock_source_is_explicitly_marked():
    p = QwenProvider(ProviderConfig.from_values("http://test", "unused"))
    r = p.chat_json(
        [{"role": "user", "content": "hi"}],
        source="mock",
        mock_fn=lambda _: '{"algorithm":"bubble_sort"}',
    )
    assert r.source == "mock"
    assert r.model == "offline-mock-v1"
    assert "OFFLINE MOCK" in r.raw_snippet


def test_missing_credential_is_rejected():
    cfg = ProviderConfig.from_values("http://test", "qwen-test", None)
    with pytest.raises(errors.AIError) as ei:
        cfg.check_real_call()
    assert ei.value.code == errors.NO_CREDENTIAL
    assert ENV_API_KEY in ei.value.message


def test_success_and_masked_snippet():
    captured = {}

    def handler(req):
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = json.loads(req.content)
        return _response(200, _ok_body('{"algorithm":"bubble_sort"}'))

    p = _provider(handler)
    r = p.chat_json([{"role": "user", "content": "排序"}])
    assert r.content == '{"algorithm":"bubble_sort"}'
    assert captured["auth"].startswith("Bearer ")
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["temperature"] == 0.0
    assert "SECRET123456" not in r.raw_snippet
    assert r.source == "qwen"
    assert r.latency_ms >= 0


def test_timeout():
    def handler(_req):
        raise httpx.TimeoutException("simulated")

    with pytest.raises(errors.AIError) as ei:
        _provider(handler).chat_json([{"role": "user", "content": "hi"}])
    assert ei.value.code == errors.REQUEST_TIMEOUT
    assert ei.value.retryable is True


def test_non_2xx():
    with pytest.raises(errors.AIError) as ei:
        _provider(lambda _req: _response(429, '{"error":"rate limited"}')).chat_json(
            [{"role": "user", "content": "hi"}]
        )
    assert ei.value.code == errors.HTTP_ERROR
    assert ei.value.detail["status_code"] == 429
    assert ei.value.retryable is True


def test_invalid_json_body():
    with pytest.raises(errors.AIError) as ei:
        _provider(lambda _req: _response(200, "not-json")).chat_json(
            [{"role": "user", "content": "hi"}]
        )
    assert ei.value.code == errors.INVALID_JSON


def test_missing_choices():
    with pytest.raises(errors.AIError) as ei:
        _provider(lambda _req: _response(200, json.dumps({"choices": []}))).chat_json(
            [{"role": "user", "content": "hi"}]
        )
    assert ei.value.code == errors.INVALID_JSON


def test_empty_content():
    with pytest.raises(errors.AIError) as ei:
        _provider(lambda _req: _response(200, _ok_body("   "))).chat_json(
            [{"role": "user", "content": "hi"}]
        )
    assert ei.value.code == errors.EMPTY_RESPONSE


def test_extract_json_object_handles_fence():
    assert json.loads(extract_json_object('```json\n{"a":1}\n```')) == {"a": 1}
    assert json.loads(extract_json_object('思考：{"a": {"b": 2}} 完毕')) == {"a": {"b": 2}}
    with pytest.raises(errors.AIError):
        extract_json_object("没有 JSON")


def test_transcript_is_masked(tmp_path):
    p = _provider(lambda _req: _response(200, _ok_body()))
    r = p.chat_json([{"role": "user", "content": "key=sk-SECRET123456"}])
    out = write_transcript(
        tmp_path / "transcript.jsonl",
        request={"messages": [{"role": "user", "content": "key=sk-SECRET123456"}]},
        response=r,
    )
    text = out.read_text(encoding="utf-8")
    assert "SECRET123456" not in text
    assert "messages" not in text
    assert "content_preview" not in text
    assert r.request_id in text


def test_transcript_never_writes_prompts_model_text_or_error_details(tmp_path):
    marker = "DUMMY_API_KEY_VALUE_12345"
    personal = "姓名：测试同学；电话：000-0000-0000"
    special = "<private>&\"'\\\n"
    response = ModelResponse(
        content=marker + personal + special,
        request_id="test-request",
        model="qwen-flash",
        source="qwen",
        raw_snippet=marker + personal,
    )
    path = tmp_path / "transcript.jsonl"
    write_transcript(path, request={"messages": [personal, marker]}, response=response)
    write_transcript(
        path,
        request={"request_id": "test-request", "messages": [marker]},
        error=errors.AIError(errors.HTTP_ERROR, "failed", {"body": marker + personal + special}),
    )
    text = path.read_text(encoding="utf-8")
    for forbidden in (marker, personal, special, "messages", "raw_snippet", "content_preview"):
        assert forbidden not in text
    assert '"error_code": "E-QWEN-HTTP"' in text


def test_environment_variable_names():
    assert (ENV_BASE_URL, ENV_MODEL, ENV_API_KEY) == ("QWEN_BASE_URL", "QWEN_MODEL", "QWEN_API_KEY")


def test_load_dotenv_does_not_override_existing_env(monkeypatch, tmp_path):
    import os

    from app.ai import provider

    (tmp_path / ".env").write_text(
        "QWEN_TEST_A=from_file\nQWEN_TEST_B=file_b\n", encoding="utf-8"
    )
    monkeypatch.setenv("QWEN_TEST_A", "from_env")
    monkeypatch.delenv("QWEN_TEST_B", raising=False)
    monkeypatch.chdir(tmp_path)
    provider.load_dotenv(reload=True)
    assert os.environ["QWEN_TEST_A"] == "from_env"
    assert os.environ["QWEN_TEST_B"] == "file_b"


def test_mask_secret_variants():
    assert "abcdef123456" not in mask_secret("Bearer abcdef123456")
    assert "abcdef123456" not in mask_secret('{"api_key":"abcdef123456"}')
