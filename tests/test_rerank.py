"""Tests for cross-encoder reranking helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from cacten.models import Chunk, ChunkMetadata, ScoredChunk
from cacten.rerank import _truncate, rerank, score_pairs


def _scored_chunk(text: str, score: float) -> ScoredChunk:
    chunk = Chunk(
        text=text,
        metadata=ChunkMetadata(
            chunk_id=str(uuid4()),
            kb_version_id="version",
            source_document_id="doc",
            source_filename="doc.md",
            chunk_index=0,
            char_offset_start=0,
            char_offset_end=len(text),
            ingested_at=datetime.now(tz=UTC),
            content_type="markdown",
        ),
    )
    return ScoredChunk(chunk=chunk, score=score)


def test_truncate_uses_configured_limit() -> None:
    with patch("cacten.rerank.config.RERANK_MAX_CHARS", 4):
        assert _truncate("abcdef") == "abcd"


def test_score_pairs_returns_empty_for_no_texts() -> None:
    assert score_pairs("query", []) == []


def test_score_pairs_raises_clear_error_without_dependency() -> None:
    with (
        patch("cacten.rerank._get_reranker", side_effect=RuntimeError("missing dependency")),
        pytest.raises(RuntimeError, match="missing dependency"),
    ):
        score_pairs("query", ["candidate"])


def test_rerank_sorts_by_model_scores_and_trims_top_k() -> None:
    candidates = [
        _scored_chunk("first", 0.1),
        _scored_chunk("second", 0.9),
        _scored_chunk("third", 0.3),
    ]

    with patch("cacten.rerank.score_pairs", return_value=[0.2, 0.95, 0.5]):
        results = rerank("query", candidates, top_k=2)

    assert [result.chunk.text for result in results] == ["second", "third"]
    assert [result.score for result in results] == [0.95, 0.5]
