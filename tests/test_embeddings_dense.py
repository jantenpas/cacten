"""Tests for dense embedding + check_ollama error paths."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cacten import embeddings


def test_embed_dense_success() -> None:
    fake_embedding = [0.1] * 768
    with patch("cacten.embeddings.ollama.embeddings", return_value={"embedding": fake_embedding}):
        result = embeddings.embed_dense("hello")
    assert result == fake_embedding


def test_embed_dense_reraises_as_runtime_error() -> None:
    with (
        patch("cacten.embeddings.ollama.embeddings", side_effect=ConnectionError("refused")),
        pytest.raises(RuntimeError, match="Ollama unreachable"),
    ):
        embeddings.embed_dense("hello")


def test_check_ollama_success() -> None:
    with patch("cacten.embeddings.ollama.embeddings", return_value={"embedding": [0.0] * 768}):
        embeddings.check_ollama()  # should not raise


def test_check_ollama_raises_on_failure() -> None:
    with (
        patch("cacten.embeddings.ollama.embeddings", side_effect=ConnectionError("refused")),
        pytest.raises(RuntimeError, match="Ollama unreachable"),
    ):
        embeddings.check_ollama()
