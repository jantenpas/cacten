"""Tests for the ingestion pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

import cacten.config as cfg_module
import cacten.versions as versions_module
from cacten.pipeline import ingest, ingest_directory, ingest_manifest

FAKE_DENSE = [0.1] * 768
FAKE_SPARSE = ([1, 2], [0.5, 0.5])


def _patch_embeddings() -> tuple[Any, Any]:
    # Returns patch context managers for both dense embedding paths and sparse embedding.
    dense = patch.multiple(
        "cacten.pipeline",
        embed_dense=MagicMock(return_value=FAKE_DENSE),
        embed_dense_many=MagicMock(side_effect=lambda texts: [FAKE_DENSE for _ in texts]),
    )
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
        patch("cacten.pipeline.split_by_content_type", return_value=[]),
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


def test_ingest_directory(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def foo():\n    pass\n")
    (tmp_path / "b.md").write_text("# Docs\n\nSome content.")

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
        result = ingest_directory(str(tmp_path))

    assert len(result) == 2
    assert mock_store.add.call_count == 2


def test_ingest_directory_ext_filter(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def foo():\n    pass\n")
    (tmp_path / "b.md").write_text("# Docs\n\nSome content.")

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
        result = ingest_directory(str(tmp_path), extensions=[".py"])

    assert len(result) == 1


def test_ingest_directory_skips_hidden(tmp_path: Path) -> None:
    (tmp_path / "visible.py").write_text("x = 1\n")
    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.py").write_text("y = 2\n")

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
        result = ingest_directory(str(tmp_path))

    assert len(result) == 1


def test_ingest_directory_not_a_directory(tmp_path: Path) -> None:
    f = tmp_path / "file.py"
    f.write_text("x = 1\n")
    with pytest.raises(ValueError, match="not a directory"):
        ingest_directory(str(f))


def test_ingest_directory_no_supported_files(tmp_path: Path) -> None:
    (tmp_path / "ignore.xyz").write_text("nothing")
    with pytest.raises(ValueError, match="No supported files"):
        ingest_directory(str(tmp_path))


def test_ingest_chunk_offset_fallback(tmp_path: Path) -> None:
    # Covers the start == -1 branch: triggered when a chunk text cannot be
    # located in the source string (e.g. the splitter modified whitespace).
    md = tmp_path / "doc.md"
    md.write_text("original content")

    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"
    mock_store = MagicMock()
    dense_patch, sparse_patch = _patch_embeddings()

    with (
        patch("cacten.config.ensure_dirs"),
        # Return a chunk that won't be found in the original text
        patch("cacten.pipeline.split_by_content_type", return_value=["chunk not in source"]),
        patch("cacten.pipeline.QdrantVectorStore", return_value=mock_store),
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        dense_patch,
        sparse_patch,
    ):
        version = ingest(str(md))

    assert version.chunk_count == 1
    mock_store.add.assert_called_once()


# ---------------------------------------------------------------------------
# ingest_manifest
# ---------------------------------------------------------------------------


def test_ingest_manifest_happy_path(tmp_path: Path) -> None:
    from cacten.manifest import ManifestConfig

    md = tmp_path / "doc.md"
    md.write_text("# Hello\n\nManifest ingestion test content.")

    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    manifest_toml = cacten_dir / "sources.toml"
    manifest_toml.write_text("version = 1\ninclude = ['*.md']\n")

    manifest = ManifestConfig(version=1, include=["*.md"])
    versions_file = tmp_path / "versions.json"
    version_files_dir = tmp_path / "version-files"
    config_file = tmp_path / "config.json"
    mock_store = MagicMock()
    dense_patch, sparse_patch = _patch_embeddings()

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.manifest.manifest_path", return_value=manifest_toml),
        patch("cacten.manifest.load_manifest", return_value=manifest),
        patch("cacten.manifest.resolve_files", return_value=[md]),
        patch("cacten.manifest.snapshot_manifest", return_value=(tmp_path / "snap.toml", "abc123")),
        patch("cacten.pipeline.QdrantVectorStore", return_value=mock_store),
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(versions_module, "VERSION_FILES_DIR", version_files_dir),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        dense_patch,
        sparse_patch,
    ):
        version = ingest_manifest(label="test run")

    assert version.chunk_count >= 1
    assert version.document_count == 1
    assert version.notes == "test run"
    assert version.manifest_hash == "abc123"
    mock_store.add.assert_called_once()


def test_ingest_manifest_bootstraps_when_missing(tmp_path: Path) -> None:
    from cacten.manifest import ManifestConfig

    md = tmp_path / "doc.md"
    md.write_text("Some content.")

    manifest = ManifestConfig(version=1, include=["*.md"])
    versions_file = tmp_path / "versions.json"
    version_files_dir = tmp_path / "version-files"
    config_file = tmp_path / "config.json"
    mock_store = MagicMock()
    dense_patch, sparse_patch = _patch_embeddings()

    # manifest_path returns a non-existent path → triggers bootstrap
    missing = tmp_path / ".cacten" / "sources.toml"

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.manifest.manifest_path", return_value=missing),
        patch("cacten.manifest.bootstrap_manifest", return_value=missing) as mock_bootstrap,
        patch("cacten.manifest.load_manifest", return_value=manifest),
        patch("cacten.manifest.resolve_files", return_value=[md]),
        patch("cacten.manifest.snapshot_manifest", return_value=(tmp_path / "snap.toml", "abc")),
        patch("cacten.pipeline.QdrantVectorStore", return_value=mock_store),
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(versions_module, "VERSION_FILES_DIR", version_files_dir),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        dense_patch,
        sparse_patch,
    ):
        ingest_manifest()

    mock_bootstrap.assert_called_once()


def test_ingest_manifest_no_files_raises(tmp_path: Path) -> None:
    from cacten.manifest import ManifestConfig

    manifest = ManifestConfig(version=1, include=["*.md"])
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    (cacten_dir / "sources.toml").write_text("version = 1\ninclude = ['*.md']\n")

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.manifest.manifest_path", return_value=cacten_dir / "sources.toml"),
        patch("cacten.manifest.load_manifest", return_value=manifest),
        patch("cacten.manifest.resolve_files", return_value=[]),
        pytest.raises(ValueError, match="resolved no files"),
    ):
        ingest_manifest()


def test_ingest_manifest_all_empty_chunks_raises(tmp_path: Path) -> None:
    from cacten.manifest import ManifestConfig

    md = tmp_path / "empty.md"
    md.write_text("")

    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    manifest_toml = cacten_dir / "sources.toml"
    manifest_toml.write_text("version = 1\ninclude = ['*.md']\n")

    manifest = ManifestConfig(version=1, include=["*.md"])
    version_files_dir = tmp_path / "version-files"

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.manifest.manifest_path", return_value=manifest_toml),
        patch("cacten.manifest.load_manifest", return_value=manifest),
        patch("cacten.manifest.resolve_files", return_value=[md]),
        patch("cacten.manifest.snapshot_manifest", return_value=(tmp_path / "snap.toml", "abc")),
        patch("cacten.pipeline.QdrantVectorStore"),
        patch.object(versions_module, "VERSION_FILES_DIR", version_files_dir),
        patch("cacten.pipeline.split_by_content_type", return_value=[]),
        pytest.raises(ValueError, match="No text could be extracted"),
    ):
        ingest_manifest()


def test_ingest_manifest_reuses_unchanged_files(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from cacten.manifest import ManifestConfig
    from cacten.models import Chunk, ChunkMetadata, VersionFileRecord

    md = tmp_path / "doc.md"
    md.write_text("# Hello\n\nManifest ingestion test content.")

    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    manifest_toml = cacten_dir / "sources.toml"
    manifest_toml.write_text("version = 1\ninclude = ['*.md']\n")

    manifest = ManifestConfig(version=1, include=["*.md"])
    versions_file = tmp_path / "versions.json"
    version_files_dir = tmp_path / "version-files"
    config_file = tmp_path / "config.json"
    mock_store = MagicMock()

    previous_chunk = Chunk(
        text="reused chunk",
        metadata=ChunkMetadata(
            chunk_id=str(uuid4()),
            kb_version_id="old-version",
            source_document_id=str(uuid4()),
            source_filename=md.name,
            source_path=str(md.resolve()),
            source_file_hash="oldhash",
            chunk_index=0,
            char_offset_start=0,
            char_offset_end=11,
            ingested_at=datetime.now(tz=UTC),
            content_type="markdown",
        ),
        dense_vector=FAKE_DENSE,
        sparse_indices=FAKE_SPARSE[0],
        sparse_values=FAKE_SPARSE[1],
    )
    previous_record = VersionFileRecord(
        path=str(md.resolve()),
        file_hash="sha256-match",
        file_size=md.stat().st_size,
        content_type="markdown",
        embedding_model=cfg_module.EMBEDDING_MODEL,
        sparse_encoder_version=cfg_module.SPARSE_ENCODER_VERSION,
        chunk_profile="default",
        chunk_count=1,
        chunk_ids=[previous_chunk.metadata.chunk_id],
    )

    with (
        patch("cacten.config.ensure_dirs"),
        patch("cacten.manifest.manifest_path", return_value=manifest_toml),
        patch("cacten.manifest.load_manifest", return_value=manifest),
        patch("cacten.manifest.resolve_files", return_value=[md.resolve()]),
        patch("cacten.manifest.snapshot_manifest", return_value=(tmp_path / "snap.toml", "abc123")),
        patch("cacten.pipeline._hash_file", return_value="sha256-match"),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(versions_module, "VERSION_FILES_DIR", version_files_dir),
        patch.object(cfg_module, "get_active_version_id", return_value="old-version"),
        patch("cacten.versions.load_version_files", return_value=[previous_record]),
        patch("cacten.pipeline.embed_dense_many") as mock_embed_many,
        patch("cacten.pipeline.embed_sparse") as mock_embed_sparse,
        patch("cacten.pipeline.QdrantVectorStore", return_value=mock_store),
    ):
        mock_store.get_chunks.return_value = [previous_chunk]
        version = ingest_manifest(label="incremental")

    assert version.document_count == 1
    assert version.chunk_count == 1
    mock_store.get_chunks.assert_called_once_with([previous_chunk.metadata.chunk_id])
    mock_embed_many.assert_not_called()
    mock_embed_sparse.assert_not_called()
