"""D05 RAG 检索：BGE Embedding + FAISS 索引查询（AV-M1-D05）。

固定配置：
- 模型名 BAAI/bge-small-zh-v1.5，向量维度 512（以模型实际输出为准并写入索引元数据）。
- 知识版本 kb-v1.0.0，与 knowledge/documents/ 中的 knowledge_version 一致。
- 检索 Top-k 默认 4（项目书建议 3-5）。

嵌入器可插拔：
- BgeEmbedder：真实模型，需安装 sentence-transformers 并下载模型。
- OfflineHashEmbedder：离线预案，确定性哈希向量，仅用于测试/无网环境，
  结果必须标注 embedding='offline-hash'，不得冒充真实 BGE。

无结果时返回空 sources 与明确提示（RagAnswer.retrieved=False）。
"""

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union

import numpy as np

from app.ai import errors

MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EXPECTED_DIM = 512
KNOWLEDGE_VERSION = "kb-v1.0.0"
DEFAULT_TOP_K = 4


class Embedder(Protocol):
    name: str
    dim: int

    def encode(self, texts: List[str]) -> np.ndarray:
        ...


@dataclass
class OfflineHashEmbedder:
    """离线预案嵌入器：确定性哈希桶向量。不可用于真实问答质量评估。"""

    dim: int = EXPECTED_DIM
    name: str = "offline-hash"

    def encode(self, texts: List[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), self.dim), dtype="float32")
        for i, text in enumerate(texts):
            # 字符级 bigram 哈希，保证中文短句有可区分性
            grams = [text[j:j + 2] for j in range(max(1, len(text) - 1))]
            for g in grams:
                h = int(hashlib.md5(g.encode("utf-8")).hexdigest()[:8], 16)
                vecs[i, h % self.dim] += 1.0
            norm = np.linalg.norm(vecs[i])
            if norm > 0:
                vecs[i] /= norm
        return vecs


class BgeEmbedder:
    """真实 BGE 嵌入器；sentence-transformers 缺失时抛明确错误。"""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise errors.AIError(
                errors.EMBEDDING_UNAVAILABLE,
                "未安装 sentence-transformers，无法使用真实 BGE 嵌入；请安装依赖或改用离线预案",
                {"model": model_name},
            ) from exc
        self.name = model_name
        self._model = SentenceTransformer(model_name)
        # sentence-transformers 6.x 将方法重命名为 get_embedding_dimension，兼容旧版
        dim_fn = getattr(self._model, "get_embedding_dimension", None) or getattr(
            self._model, "get_sentence_embedding_dimension", None
        )
        self.dim = int((dim_fn() if dim_fn else None) or EXPECTED_DIM)

    def encode(self, texts: List[str]) -> np.ndarray:
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype="float32")


@dataclass
class RagAnswer:
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    retrieved: bool
    notice: Optional[str]
    embedding: str
    knowledge_version: str
    top_k: int


class Index:
    """FAISS 索引封装：加载元数据后按 query 返回 Top-k 来源。"""

    def __init__(
        self,
        index_path: Union[str, Path],
        embedder: Embedder,
        *,
        score_threshold: float = 0.0,
    ) -> None:
        import faiss  # 延迟导入，便于未装依赖时仍可 import 模块

        self.index_path = Path(index_path)
        if not self.index_path.exists():
            raise errors.AIError(
                errors.INDEX_MISSING,
                "FAISS 索引不存在，请先运行 knowledge/scripts/build_index.py 构建",
                {"path": str(self.index_path)},
            )
        # faiss C++ 文件 IO 在 Windows 中文路径下失败：复制至 ASCII 临时路径读取
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp) / "index.bin"
            shutil.copyfile(str(self.index_path), str(tmp_path))
            self.index = faiss.read_index(str(tmp_path))
        meta_path = self.index_path.with_suffix(".meta.json")
        if not meta_path.exists():
            raise errors.AIError(errors.INDEX_MISSING, "索引元数据缺失", {"path": str(meta_path)})
        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.documents = self.meta["documents"]
        self.embedder = embedder
        self.score_threshold = score_threshold

        if self.index.d != embedder.dim:
            raise errors.AIError(
                errors.EMBEDDING_UNAVAILABLE,
                f"嵌入维度与索引不匹配：索引 {self.index.d}，嵌入器 {embedder.dim}",
                {"index_dim": self.index.d, "embedder_dim": embedder.dim,
                 "embedder": embedder.name},
            )

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> RagAnswer:
        if not query or not query.strip():
            return self._empty_answer(query, "查询为空", top_k)
        k = min(max(1, top_k), self.index.ntotal)
        vec = self.embedder.encode([query])
        scores, indices = self.index.search(vec, k)
        sources = []
        for score, idx in zip(scores[0].tolist(), indices[0].tolist()):
            if idx < 0 or score < self.score_threshold:
                continue
            doc = self.documents[idx]
            sources.append({
                "source_id": doc["source_id"],
                "title": doc["title"],
                "topic": doc["topic"],
                "version": doc["version"],
                "source_url": doc.get("source_url"),
                "score": round(float(score), 4),
                "excerpt": doc["content"][:160],
            })
        if not sources:
            return self._empty_answer(query, "检索无结果，请勿编造来源", top_k)
        answer = f"根据检索到的 {len(sources)} 条知识条目，相关信息如下：\n"
        answer += "\n".join(
            "[{0}] {1}：{2}".format(s["source_id"], s["title"], s["excerpt"]) for s in sources
        )
        notice = None
        if self.embedder.name == "offline-hash":
            notice = "离线预案：本次使用哈希向量检索，不代表真实 BGE 语义质量"
        return RagAnswer(
            question=query,
            answer=answer,
            sources=sources,
            retrieved=True,
            notice=notice,
            embedding=self.embedder.name,
            knowledge_version=self.meta.get("knowledge_version", ""),
            top_k=k,
        )

    def _empty_answer(self, query: str, notice: str, top_k: int) -> RagAnswer:
        return RagAnswer(
            question=query,
            answer="未检索到可核查的知识条目。",
            sources=[],
            retrieved=False,
            notice=notice,
            embedding=self.embedder.name,
            knowledge_version=self.meta.get("knowledge_version", ""),
            top_k=top_k,
        )


def load_index(index_path: Union[str, Path], use_real_bge: bool = False) -> Index:
    embedder: Embedder
    if use_real_bge:
        embedder = BgeEmbedder()
    else:
        embedder = OfflineHashEmbedder()
    return Index(index_path, embedder)
