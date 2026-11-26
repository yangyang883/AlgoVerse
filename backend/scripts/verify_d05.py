"""D05 检索 Top-k 验证脚本（AV-M1-D05）。

用法（backend/ 下）：
    python scripts/verify_d05.py                          # 离线哈希索引
    python scripts/verify_d05.py --real-bge --index-name faiss_index_bge.bin

产物：backend/artifacts/d05-retrieval-samples.json（离线）
      backend/artifacts/d05-retrieval-samples-bge.json（真实 BGE）

真实 BGE 需要 sentence-transformers 与已下载的 BAAI/bge-small-zh-v1.5；
两种模式的结果分别标注 embedding，不得混用。
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.rag import KNOWLEDGE_VERSION, load_index

QUERIES = [
    "快速排序最坏情况是什么？",
    "冒泡排序的时间复杂度前提",
    "Dijkstra 能在平台上执行吗",
    "怎么保证同输入公平对比",
]


def to_json(ans):
    return {
        "question": ans.question,
        "answer": ans.answer,
        "retrieved": ans.retrieved,
        "notice": ans.notice,
        "embedding": ans.embedding,
        "knowledge_version": ans.knowledge_version,
        "top_k": ans.top_k,
        "sources": ans.sources,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-bge", action="store_true", help="用真实 BGE 嵌入查询")
    parser.add_argument("--index-name", default="faiss_index.bin")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    index_path = ROOT / "knowledge" / "index" / args.index_name
    idx = load_index(str(index_path), use_real_bge=args.real_bge)
    results = [to_json(idx.search(q, top_k=4)) for q in QUERIES]
    mode = idx.meta.get("embedding", "")
    out = Path(args.out) if args.out else (
        ROOT / "backend" / "artifacts" / (
            "d05-retrieval-samples-bge.json" if args.real_bge else "d05-retrieval-samples.json"
        )
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": ("REAL BGE EMBEDDING — BAAI/bge-small-zh-v1.5" if args.real_bge
                 else "OFFLINE HASH EMBEDDING — 不代表真实 BGE 语义检索质量"),
        "index": {
            "file": str(index_path),
            "embedding": mode,
            "embedding_model": idx.meta.get("embedding_model", ""),
            "dim": idx.meta.get("embedding_dim", idx.index.d),
            "knowledge_version": idx.meta.get("knowledge_version", KNOWLEDGE_VERSION),
            "document_count": idx.index.ntotal,
        },
        "api_for_member3": {
            "function": f"app.ai.rag.load_index(path, use_real_bge={args.real_bge!s}).search(query, top_k=4)",
            "input": {"query": "string", "top_k": "int, 默认 4"},
            "output_fields": [
                "question", "answer", "retrieved", "notice", "embedding",
                "knowledge_version", "top_k", "sources[]",
            ],
            "empty_result_contract": "retrieved=false, sources=[], notice 明确提示，不编造来源",
        },
        "results": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "queries": len(results), "embedding": mode, "out": str(out)},
                     ensure_ascii=False))
    for r in results:
        print("{} | {} | sources={}".format(
            r["question"][:20], r["retrieved"], len(r["sources"])
        ))


if __name__ == "__main__":
    main()
