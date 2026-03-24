"""Tests for retrieval edge cases."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest

from cacten import config
from cacten.models import KBVersion
from cacten.retrieval import retrieve
from cacten.store import QdrantVectorStore


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
        patch.object(QdrantVectorStore, "search", return_value=[]),
    ):
        results = retrieve("anything")
    assert results == []
