"""有真实凭据时的最小请求脚本（AV-M1-D02）。

用法（在 backend/ 目录下）：
    python scripts/provider_smoke.py

要求：设置 QWEN_BASE_URL / QWEN_MODEL / QWEN_API_KEY 环境变量。
输出：backend/artifacts/provider_smoke.jsonl（自动脱敏，不记录 Key）。
无凭据时脚本直接退出并提示，不会把 Mock 结果冒充真实调用。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import errors
from app.ai.provider import ProviderConfig, QwenProvider, write_transcript

MESSAGES = [
    {"role": "system", "content": "请只输出 JSON，不要输出其他文字。"},
    {"role": "user", "content": '输出 {"ping":"pong"}'},
]


def main() -> int:
    out = Path(__file__).resolve().parents[1] / "artifacts" / "provider_smoke.jsonl"
    try:
        with QwenProvider(ProviderConfig.from_env()) as p:
            r = p.chat_json(MESSAGES)
            write_transcript(out, request={"model": r.model, "messages": MESSAGES}, response=r)
            print(json.dumps({
                "ok": True,
                "source": r.source,
                "model": r.model,
                "latency_ms": r.latency_ms,
                "content_preview": r.content[:120],
                "transcript": str(out),
            }, ensure_ascii=False))
            return 0
    except errors.AIError as exc:
        write_transcript(out, request={"model": "unknown", "messages": MESSAGES}, error=exc)
        print(json.dumps({"ok": False, "error": exc.public_dict(), "transcript": str(out)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
