"""Tests for embeddings (BM25 sparse — no Ollama required)."""

from cacten.embeddings import BM25Encoder, embed_sparse


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


def test_sparse_uses_deterministic_token_indices() -> None:
    encoder = BM25Encoder()
    digest_index, _ = encoder.encode("2248669")

    assert digest_index == [2450039]


def test_sparse_tokenizer_normalizes_markdown_and_numbers() -> None:
    encoder = BM25Encoder()

    tokens = encoder.tokenize("**Cacten Test 48769** - Because Cactus' are cool!")

    assert "cacten" in tokens
    assert "test" in tokens
    assert "48769" in tokens
    assert "cactus" in tokens
