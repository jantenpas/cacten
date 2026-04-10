"""Tests for retrieval edge cases."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from cacten import config
from cacten.models import Chunk, ChunkMetadata, KBVersion, ScoredChunk
from cacten.retrieval import retrieve


def _scored_chunk(text: str, score: float) -> ScoredChunk:
    chunk = Chunk(
        text=text,
        metadata=ChunkMetadata(
            chunk_id=str(uuid4()),
            kb_version_id="some-id",
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


def test_retrieve_no_active_version() -> None:
    with (
        patch.object(config, "get_active_version_id", return_value=None),
        pytest.raises(RuntimeError, match="No active KB version"),
    ):
        retrieve("anything")


def test_retrieve_model_mismatch() -> None:
    fake_version = KBVersion(
        version_id=str(uuid4()),
        version_number=1,
        created_at=datetime.now(tz=UTC),
        document_count=1,
        chunk_count=5,
        embedding_model="old-model",
    )

    with (
        patch.object(config, "get_active_version_id", return_value="some-id"),
        patch("cacten.retrieval.get_version", return_value=fake_version),
        patch("cacten.retrieval.config") as mock_cfg,
        pytest.raises(RuntimeError, match="Embedding model mismatch"),
    ):
        mock_cfg.get_active_version_id.return_value = "some-id"
        mock_cfg.EMBEDDING_MODEL = "new-model"
        retrieve("anything")


def test_retrieve_version_none_skips_mismatch_check() -> None:
    """If get_version returns None (version deleted), skip model check and proceed."""
    fake_dense = [0.1] * 768
    fake_sparse = ([1, 2], [0.5, 0.5])

    with (
        patch.object(config, "get_active_version_id", return_value="some-id"),
        patch("cacten.retrieval.get_version", return_value=None),
        patch("cacten.retrieval.embed_dense", return_value=fake_dense),
        patch("cacten.retrieval.embed_sparse", return_value=fake_sparse),
        patch("cacten.retrieval.QdrantVectorStore") as mock_store_cls,
    ):
        mock_store_cls.return_value.search.return_value = []
        results = retrieve("anything")
    assert results == []


def test_retrieve_reranks_wider_candidate_set() -> None:
    fake_dense = [0.1] * 768
    fake_sparse = ([1, 2], [0.5, 0.5])
    candidates = [
        _scored_chunk("lower-ranked exact answer", 0.2),
        _scored_chunk("higher-ranked broad answer", 0.9),
    ]
    reranked = [candidates[0]]

    with (
        patch.object(config, "get_active_version_id", return_value="some-id"),
        patch("cacten.retrieval.get_version", return_value=None),
        patch("cacten.retrieval.embed_dense", return_value=fake_dense),
        patch("cacten.retrieval.embed_sparse", return_value=fake_sparse),
        patch("cacten.retrieval.config.RERANK_ENABLED", True),
        patch("cacten.retrieval.config.RERANK_CANDIDATES", 50),
        patch("cacten.retrieval.QdrantVectorStore") as mock_store_cls,
        patch("cacten.retrieval.rerank", return_value=reranked) as mock_rerank,
    ):
        mock_store_cls.return_value.search.return_value = candidates
        results = retrieve("exact answer", top_k=1)

    assert results == reranked
    mock_store_cls.return_value.search.assert_called_once()
    assert mock_store_cls.return_value.search.call_args.kwargs["top_k"] == 50
    mock_rerank.assert_called_once_with(query="exact answer", candidates=candidates, top_k=1)


def test_retrieve_can_disable_reranking() -> None:
    fake_dense = [0.1] * 768
    fake_sparse = ([1, 2], [0.5, 0.5])
    candidates = [
        _scored_chunk("first", 0.9),
        _scored_chunk("second", 0.8),
    ]

    with (
        patch.object(config, "get_active_version_id", return_value="some-id"),
        patch("cacten.retrieval.get_version", return_value=None),
        patch("cacten.retrieval.embed_dense", return_value=fake_dense),
        patch("cacten.retrieval.embed_sparse", return_value=fake_sparse),
        patch("cacten.retrieval.config.RERANK_ENABLED", False),
        patch("cacten.retrieval.QdrantVectorStore") as mock_store_cls,
        patch("cacten.retrieval.rerank") as mock_rerank,
    ):
        mock_store_cls.return_value.search.return_value = candidates
        results = retrieve("anything", top_k=1)

    assert results == candidates[:1]
    assert mock_store_cls.return_value.search.call_args.kwargs["top_k"] == 1
    mock_rerank.assert_not_called()


def test_retrieve_falls_back_when_reranker_unavailable() -> None:
    fake_dense = [0.1] * 768
    fake_sparse = ([1, 2], [0.5, 0.5])
    candidates = [
        _scored_chunk("first", 0.9),
        _scored_chunk("second", 0.8),
    ]

    with (
        patch.object(config, "get_active_version_id", return_value="some-id"),
        patch("cacten.retrieval.get_version", return_value=None),
        patch("cacten.retrieval.embed_dense", return_value=fake_dense),
        patch("cacten.retrieval.embed_sparse", return_value=fake_sparse),
        patch("cacten.retrieval.config.RERANK_ENABLED", True),
        patch("cacten.retrieval.config.RERANK_CANDIDATES", 50),
        patch("cacten.retrieval.QdrantVectorStore") as mock_store_cls,
        patch("cacten.retrieval.rerank", side_effect=RuntimeError("missing dependency")),
    ):
        mock_store_cls.return_value.search.return_value = candidates
        results = retrieve("anything", top_k=1)

    assert results == candidates[:1]
