"""Tests for the Typer CLI commands."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from typer.testing import CliRunner

import cacten.config as cfg_module
import cacten.versions as versions_module
from cacten.cli import app
from cacten.models import KBVersion

runner = CliRunner()


def _make_version(
    version_number: int = 1,
    chunk_count: int = 5,
    version_id: str | None = None,
) -> KBVersion:
    return KBVersion(
        version_id=version_id or str(uuid4()),
        version_number=version_number,
        created_at=datetime.now(tz=UTC),
        document_count=1,
        chunk_count=chunk_count,
        embedding_model="nomic-embed-text",
    )


# ---------------------------------------------------------------------------
# cacten ingest
# ---------------------------------------------------------------------------


def test_ingest_success(tmp_path: Path) -> None:
    version = _make_version(version_number=1, chunk_count=3)
    with (
        patch("cacten.embeddings.check_ollama"),
        patch("cacten.pipeline.ingest", return_value=version) as mock_ingest,
    ):
        result = runner.invoke(app, ["ingest", "notes.md"])

    assert result.exit_code == 0
    assert "v1" in result.output
    assert "3 chunks" in result.output
    mock_ingest.assert_called_once_with("notes.md", notes=None)


def test_ingest_with_notes(tmp_path: Path) -> None:
    version = _make_version()
    with (
        patch("cacten.embeddings.check_ollama"),
        patch("cacten.pipeline.ingest", return_value=version) as mock_ingest,
    ):
        runner.invoke(app, ["ingest", "notes.md", "--notes", "my annotation"])

    mock_ingest.assert_called_once_with("notes.md", notes="my annotation")


def test_ingest_ollama_error() -> None:
    with patch("cacten.embeddings.check_ollama", side_effect=RuntimeError("Ollama down")):
        result = runner.invoke(app, ["ingest", "notes.md"])

    assert result.exit_code == 1
    assert "Ollama down" in result.output


def test_ingest_pipeline_error() -> None:
    with (
        patch("cacten.embeddings.check_ollama"),
        patch("cacten.pipeline.ingest", side_effect=ValueError("bad file")),
    ):
        result = runner.invoke(app, ["ingest", "notes.md"])

    assert result.exit_code == 1
    assert "bad file" in result.output


# ---------------------------------------------------------------------------
# cacten retrieve
# ---------------------------------------------------------------------------


def test_retrieve_success() -> None:
    from datetime import UTC, datetime

    from cacten.models import Chunk, ChunkMetadata, ScoredChunk

    version_id = str(uuid4())
    chunk = ScoredChunk(
        chunk=Chunk(
            text="Python is great for scripting",
            metadata=ChunkMetadata(
                chunk_id=str(uuid4()),
                kb_version_id=version_id,
                source_document_id=str(uuid4()),
                source_filename="prefs.md",
                chunk_index=0,
                char_offset_start=0,
                char_offset_end=29,
                ingested_at=datetime.now(tz=UTC),
                content_type="markdown",
            ),
        ),
        score=0.9,
    )

    with patch("cacten.retrieval.retrieve", return_value=[chunk]):
        result = runner.invoke(app, ["retrieve", "python tips"])

    assert result.exit_code == 0
    assert "1 chunks" in result.output
    assert "prefs.md" in result.output


def test_retrieve_verbose() -> None:
    from datetime import UTC, datetime

    from cacten.models import Chunk, ChunkMetadata, ScoredChunk

    version_id = str(uuid4())
    chunk = ScoredChunk(
        chunk=Chunk(
            text="verbose chunk content",
            metadata=ChunkMetadata(
                chunk_id=str(uuid4()),
                kb_version_id=version_id,
                source_document_id=str(uuid4()),
                source_url="https://example.com",
                chunk_index=0,
                char_offset_start=0,
                char_offset_end=21,
                ingested_at=datetime.now(tz=UTC),
                content_type="html",
            ),
        ),
        score=0.8,
    )

    with (
        patch("cacten.retrieval.retrieve", return_value=[chunk]),
        patch("cacten.retrieval.format_context_block", return_value="<cacten_context>ctx</cacten_context>"),  # noqa: E501
    ):
        result = runner.invoke(app, ["retrieve", "query", "--verbose"])

    assert result.exit_code == 0
    assert "<cacten_context>" in result.output


def test_retrieve_runtime_error() -> None:
    with patch("cacten.retrieval.retrieve", side_effect=RuntimeError("No active KB")):
        result = runner.invoke(app, ["retrieve", "query"])

    assert result.exit_code == 1
    assert "No active KB" in result.output


# ---------------------------------------------------------------------------
# cacten versions list
# ---------------------------------------------------------------------------


def test_versions_list_empty(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"

    with (
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
    ):
        result = runner.invoke(app, ["versions", "list"])

    assert result.exit_code == 0
    assert "No versions found" in result.output


def test_versions_list_with_versions(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"
    vid = str(uuid4())

    with (
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
    ):
        versions_module.create_version(1, 10, "nomic-embed-text", version_id=vid)
        cfg_module.set_active_version_id(vid)
        result = runner.invoke(app, ["versions", "list"])

    assert result.exit_code == 0
    assert "(active)" in result.output
    assert "v1" in result.output


# ---------------------------------------------------------------------------
# cacten versions set-active
# ---------------------------------------------------------------------------


def test_versions_set_active_success(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"
    vid = str(uuid4())

    with (
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
    ):
        versions_module.create_version(1, 5, "nomic-embed-text", version_id=vid)
        result = runner.invoke(app, ["versions", "set-active", vid[:8]])

    assert result.exit_code == 0
    assert "Active version set" in result.output


def test_versions_set_active_not_found(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"

    with patch.object(versions_module, "VERSIONS_FILE", versions_file):
        result = runner.invoke(app, ["versions", "set-active", "nonexistent"])

    assert result.exit_code == 1
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# cacten versions delete
# ---------------------------------------------------------------------------


def test_versions_delete_with_yes(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"
    vid = str(uuid4())

    with (
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        patch("cacten.store.QdrantVectorStore"),
    ):
        versions_module.create_version(1, 5, "nomic-embed-text", version_id=vid)
        result = runner.invoke(app, ["versions", "delete", vid[:8], "--yes"])

    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_versions_delete_switches_active(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"
    vid1 = str(uuid4())
    vid2 = str(uuid4())

    with (
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        patch("cacten.store.QdrantVectorStore"),
    ):
        versions_module.create_version(1, 5, "nomic-embed-text", version_id=vid1)
        versions_module.create_version(2, 5, "nomic-embed-text", version_id=vid2)
        cfg_module.set_active_version_id(vid1)
        result = runner.invoke(app, ["versions", "delete", vid1[:8], "--yes"])

    assert result.exit_code == 0
    assert "switched" in result.output


def test_versions_delete_last_version(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"
    config_file = tmp_path / "config.json"
    vid = str(uuid4())

    with (
        patch.object(versions_module, "VERSIONS_FILE", versions_file),
        patch.object(cfg_module, "CONFIG_FILE", config_file),
        patch("cacten.store.QdrantVectorStore"),
    ):
        versions_module.create_version(1, 5, "nomic-embed-text", version_id=vid)
        cfg_module.set_active_version_id(vid)
        result = runner.invoke(app, ["versions", "delete", vid[:8], "--yes"])

    assert result.exit_code == 0
    assert "No versions remain" in result.output


def test_versions_delete_not_found(tmp_path: Path) -> None:
    versions_file = tmp_path / "versions.json"

    with patch.object(versions_module, "VERSIONS_FILE", versions_file):
        result = runner.invoke(app, ["versions", "delete", "nonexistent", "--yes"])

    assert result.exit_code == 1
    assert "not found" in result.output
