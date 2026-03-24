"""Tests for the ingestion pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import cacten.config as cfg_module
import cacten.versions as versions_module
from cacten.pipeline import ingest

FAKE_DENSE = [0.1] * 768
FAKE_SPARSE = ([1, 2], [0.5, 0.5])


def _patch_embeddings() -> tuple[Any, Any]:
    # Returns two patch context managers for embed_dense and embed_sparse
    dense = patch("cacten.pipeline.embed_dense", return_value=FAKE_DENSE)
    sparse = patch("cacten.pipeline.embed_sparse", return_value=FAKE_SPARSE)
    return dense, sparse


def test_ingest_markdown_file(tmp_path: Path) -> None:
    md = tmp_path / "notes.md"
    md.write_text("# Hello\n\nThis is a test document with enough content to chunk.")

    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"

    mock_store = MagicMock()
    dense_patch, sparse_patch = _patch_embeddings()

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.pipeline.QdrantVectorStore", return_value=mock_store),
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        dense_patch,
        sparse_patch,
    ):
        version = ingest(str(md))

    assert version.chunk_count >= 1
    mock_store.add.assert_called_once()


def test_ingest_url(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"

    mock_store = MagicMock()
    dense_patch, sparse_patch = _patch_embeddings()

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.pipeline.load_url", return_value=("Some web content here to split", "html")),
        patch("cacten.pipeline.QdrantVectorStore", return_value=mock_store),
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        dense_patch,
        sparse_patch,
    ):
        version = ingest("https://example.com")

    assert version.chunk_count >= 1


def test_ingest_rejects_http_url() -> None:
    with pytest.raises(ValueError, match="Insecure URLs"):
        ingest("http://example.com")


def test_ingest_empty_text_raises(tmp_path: Path) -> None:
    md = tmp_path / "empty.md"
    md.write_text("")

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.pipeline.split_text", return_value=[]),
        pytest.raises(ValueError, match="No text extracted"),
    ):
        ingest(str(md))


def test_ingest_with_notes(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text("Some content worth ingesting for the notes test.")

    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"
    mock_store = MagicMock()
    dense_patch, sparse_patch = _patch_embeddings()

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.pipeline.QdrantVectorStore", return_value=mock_store),
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        dense_patch,
        sparse_patch,
    ):
        version = ingest(str(md), notes="my notes")

    assert version.notes == "my notes"
