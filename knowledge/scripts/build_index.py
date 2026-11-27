"""D05 离线索引构建脚本（AV-M1-D05）。

用法（仓库根目录）：
    python knowledge/scripts/build_index.py --embedder offline-hash
    python knowledge/scripts/build_index.py --embedder bge --index-name faiss_index_bge.bin  # 需 sentence-transformers

产物：
    knowledge/index/faiss_index.bin
    knowledge/index/faiss_index.meta.json

注意：离线哈希索引仅用于验证流程与 Top-k 形状，不代表真实 BGE 语义质量。
真实部署应使用 --embedder bge 并将模型名/维度写入元数据。
"""

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai import errors  # noqa: E402
from app.ai.rag import (  # noqa: E402
    BgeEmbedder,
    DEFAULT_TOP_K,
    EXPECTED_DIM,
    KNOWLEDGE_VERSION,
    MODEL_NAME,
    OfflineHashEmbedder,
)

DOC_DIR = ROOT / "knowledge" / "documents"
INDEX_DIR = ROOT / "knowledge" / "index"
INDEX_PATH = INDEX_DIR / "faiss_index.bin"
META_PATH = INDEX_DIR / "faiss_index.meta.json"


def load_documents() -> list:
    docs = []
    versions = set()
    for path in sorted(DOC_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        versions.add(payload.get("knowledge_version", ""))
        for doc in payload["documents"]:
            # 把标题与主题拼进嵌入文本，提升检索命中
            doc["_embed_text"] = "{0} {1} {2}".format(
                doc["title"], doc.get("topic", ""), doc["content"]
            )
            docs.append(doc)
    if len(versions) != 1 or KNOWLEDGE_VERSION not in versions:
        raise ValueError("知识版本不一致：{0}，期望 {1}".format(versions, KNOWLEDGE_VERSION))
    if not docs:
        raise ValueError("没有可索引的知识条目")
    ids = [d["source_id"] for d in docs]
    if len(set(ids)) != len(ids):
        raise ValueError("source_id 重复")
    return docs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedder", choices=["offline-hash", "bge"], default="offline-hash")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--index-name", default="faiss_index.bin", help="索引文件名，元数据后缀自动改为 .meta.json")
    args = parser.parse_args()

    import numpy as np
    import faiss

    index_path = INDEX_DIR / args.index_name
    meta_path = index_path.with_suffix(".meta.json")
    docs = load_documents()
    if args.embedder == "bge":
        try:
            embedder = BgeEmbedder()
        except errors.AIError as exc:
            print(json.dumps({"ok": False, "error": exc.public_dict()}, ensure_ascii=False))
            return 2
        model_name, embedding_mode = embedder.name, "bge-real"
    else:
        embedder = OfflineHashEmbedder()
        model_name, embedding_mode = "offline-hash-v1", "offline-hash"

    vectors = embedder.encode([d["_embed_text"] for d in docs])
    vectors = np.asarray(vectors, dtype="float32")
    if vectors.shape[1] != embedder.dim:
        raise ValueError("向量维度不匹配：{0} vs {1}".format(vectors.shape[1], embedder.dim))

    index = faiss.IndexFlatIP(embedder.dim)
    index.add(vectors)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    # faiss 的 C++ 文件 IO 在 Windows 中文路径下会失败，先写 ASCII 临时路径再复制
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "index.bin"
        faiss.write_index(index, str(tmp_path))
        shutil.copyfile(str(tmp_path), str(index_path))

    meta = {
        "knowledge_version": KNOWLEDGE_VERSION,
        "embedding": embedding_mode,
        "embedding_model": model_name,
        "embedding_dim": int(embedder.dim),
        "index_type": "IndexFlatIP",
        "top_k": args.top_k,
        "document_count": len(docs),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "notice": ("离线哈希向量，不代表真实 BGE 语义质量" if embedding_mode == "offline-hash" else None),
        "documents": [
            {k: v for k, v in d.items() if k != "_embed_text"} for d in docs
        ],
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "embedding": embedding_mode,
        "model": model_name,
        "dim": embedder.dim,
        "documents": len(docs),
        "index": str(index_path),
        "meta": str(meta_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
