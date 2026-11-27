"""AV-M1-D05 检索测试（离线哈希向量，明确标记，不代表真实 BGE 质量）。"""

import json
from pathlib import Path

import pytest

from app.ai import errors
from app.ai.rag import (
    DEFAULT_TOP_K,
    EXPECTED_DIM,
    KNOWLEDGE_VERSION,
    MODEL_NAME,
    Index,
    OfflineHashEmbedder,
    load_index,
)

ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "knowledge" / "index" / "faiss_index.bin"


@pytest.fixture
def index():
    if not INDEX_PATH.exists():
        pytest.skip("索引未构建")
    return load_index(str(INDEX_PATH), use_real_bge=False)


def test_index_metadata():
    meta = json.loads(INDEX_PATH.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert meta["knowledge_version"] == KNOWLEDGE_VERSION
    assert meta["embedding_dim"] == EXPECTED_DIM
    assert meta["document_count"] == 40
    assert meta["embedding"] == "offline-hash"
    assert "离线" in meta["notice"]


def test_model_name_is_fixed():
    assert MODEL_NAME == "BAAI/bge-small-zh-v1.5"
    assert EXPECTED_DIM == 512


def test_search_returns_top_k(index):
    ans = index.search("快速排序最坏情况", top_k=4)
    assert ans.retrieved is True
    assert 1 <= len(ans.sources) <= 4
    assert all(s["source_id"] and s["title"] and s["version"] for s in ans.sources)
    assert ans.embedding == "offline-hash"
    assert ans.notice is not None  # 离线预案必须显式提示


def test_search_result_has_expected_fields(index):
    ans = index.search("冒泡排序复杂度")
    for s in ans.sources:
        expected = {"source_id", "title", "topic", "version", "source_url", "score", "excerpt"}
        assert expected.issubset(s.keys())
        assert 0.0 <= s["score"] <= 1.0


def test_empty_query_returns_empty_sources(index):
    ans = index.search("")
    assert ans.retrieved is False
    assert ans.sources == []
    assert "空" in ans.notice


def test_no_results_when_threshold_high():
    embedder = OfflineHashEmbedder()
    idx = Index(str(INDEX_PATH), embedder, score_threshold=1.0)
    ans = idx.search("完全无关的查询")
    assert ans.retrieved is False
    assert ans.sources == []
    assert "编造" in ans.notice


def test_missing_index_path_reports_error(tmp_path):
    with pytest.raises(errors.AIError) as ei:
        load_index(str(tmp_path / "not-exists.bin"))
    assert ei.value.code == errors.INDEX_MISSING


def test_hash_embedder_deterministic():
    e = OfflineHashEmbedder()
    a = e.encode(["冒泡排序复杂度"])
    b = e.encode(["冒泡排序复杂度"])
    assert (a == b).all()
    assert a.shape == (1, EXPECTED_DIM)


def test_default_top_k():
    assert DEFAULT_TOP_K == 4
