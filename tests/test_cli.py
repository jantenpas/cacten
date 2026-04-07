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


def test_ingest_with_label(tmp_path: Path) -> None:
    version = _make_version()
    with (
        patch("cacten.embeddings.check_ollama"),
        patch("cacten.pipeline.ingest", return_value=version) as mock_ingest,
    ):
        runner.invoke(app, ["ingest", "notes.md", "--label", "my annotation"])

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


# ---------------------------------------------------------------------------
# cacten init
# ---------------------------------------------------------------------------


def test_init_creates_manifest(tmp_path: Path) -> None:
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    (cacten_dir / "sources-example.toml").write_text('version = 1\ninclude = ["*.md"]\n')

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert (cacten_dir / "sources.toml").exists()
    assert "Created" in result.output


def test_init_does_not_overwrite_existing(tmp_path: Path) -> None:
    cacten_dir = tmp_path / ".cacten"
    cacten_dir.mkdir()
    existing = cacten_dir / "sources.toml"
    existing.write_text("original")

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert existing.read_text() == "original"
    assert "already exists" in result.output


def test_init_fails_without_example(tmp_path: Path) -> None:
    (tmp_path / ".cacten").mkdir()

    with patch("pathlib.Path.cwd", return_value=tmp_path):
        result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# cacten ingest (manifest path)
# ---------------------------------------------------------------------------


def test_ingest_manifest_no_args(tmp_path: Path) -> None:
    version = _make_version(version_number=2, chunk_count=42)
    version = version.model_copy(update={"document_count": 5})

    with (
        patch("cacten.embeddings.check_ollama"),
        patch("cacten.pipeline.ingest_manifest", return_value=version) as mock_manifest,
        patch("cacten.manifest.manifest_path", return_value=tmp_path / ".cacten" / "sources.toml"),
        patch("pathlib.Path.cwd", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["ingest"])

    assert result.exit_code == 0
    assert "v2" in result.output
    assert "42" in result.output
    mock_manifest.assert_called_once_with(label=None)


def test_ingest_manifest_with_label(tmp_path: Path) -> None:
    version = _make_version()

    with (
        patch("cacten.embeddings.check_ollama"),
        patch("cacten.pipeline.ingest_manifest", return_value=version) as mock_manifest,
        patch("cacten.manifest.manifest_path", return_value=tmp_path / ".cacten" / "sources.toml"),
        patch("pathlib.Path.cwd", return_value=tmp_path),
    ):
        runner.invoke(app, ["ingest", "--label", "post-refactor"])

    mock_manifest.assert_called_once_with(label="post-refactor")


def test_ingest_manifest_error(tmp_path: Path) -> None:
    with (
        patch("cacten.embeddings.check_ollama"),
        patch("cacten.pipeline.ingest_manifest", side_effect=FileNotFoundError("no manifest")),
        patch("pathlib.Path.cwd", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["ingest"])

    assert result.exit_code == 1
    assert "no manifest" in result.output


# ---------------------------------------------------------------------------
# cacten ingest --dry-run
# ---------------------------------------------------------------------------


def test_ingest_dry_run(tmp_path: Path) -> None:
    from cacten.manifest import ManifestConfig

    manifest = ManifestConfig(version=1, include=["*.md"])
    files = [tmp_path / "a.md", tmp_path / "b.md"]

    with (
        patch("cacten.manifest.load_manifest", return_value=manifest),
        patch("cacten.manifest.resolve_files", return_value=files),
        patch("cacten.manifest.manifest_path", return_value=tmp_path / ".cacten" / "sources.toml"),
        patch("pathlib.Path.cwd", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["ingest", "--dry-run"])

    assert result.exit_code == 0
    assert "Resolved files: 2" in result.output


def test_ingest_dry_run_missing_manifest(tmp_path: Path) -> None:
    with (
        patch("cacten.manifest.load_manifest", side_effect=FileNotFoundError),
        patch("cacten.manifest.manifest_path", return_value=tmp_path / ".cacten" / "sources.toml"),
        patch("pathlib.Path.cwd", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["ingest", "--dry-run"])

    assert result.exit_code == 1
