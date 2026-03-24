"""Tests for embeddings (BM25 sparse — no Ollama required)."""

from cacten.embeddings import embed_sparse


def test_sparse_basic() -> None:
    indices, values = embed_sparse("the quick brown fox")
    assert len(indices) == len(values)
    assert len(indices) > 0
    assert all(v > 0 for v in values)


def test_sparse_empty() -> None:
    indices, values = embed_sparse("")
    assert indices == []
    assert values == []


def test_sparse_reproducible() -> None:
    a = embed_sparse("hello world")
    b = embed_sparse("hello world")
    assert a == b
