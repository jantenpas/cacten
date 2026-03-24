"""Tests for session logging."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from cacten import config
from cacten.models import Chunk, ChunkMetadata, ScoredChunk
from cacten.session_log import write_session_log


def _make_scored_chunk(version_id: str) -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(
            text="test chunk",
            metadata=ChunkMetadata(
                chunk_id=str(uuid4()),
                kb_version_id=version_id,
                source_document_id=str(uuid4()),
                source_filename="test.md",
                chunk_index=0,
                char_offset_start=0,
                char_offset_end=10,
                ingested_at=datetime.now(tz=UTC),
                content_type="markdown",
            ),
        ),
        score=0.9,
    )


def test_write_creates_file(tmp_path: Path) -> None:
    version_id = str(uuid4())
    with patch.object(config, "LOGS_DIR", tmp_path / "sessions"):
        from cacten import session_log as sl_module
        with patch.object(sl_module, "LOGS_DIR", tmp_path / "sessions"):
            log = write_session_log(
                query="test query",
                kb_version_id=version_id,
                embedding_model="nomic-embed-text",
                chunks=[_make_scored_chunk(version_id)],
                latency_ms=42,
            )

    log_files = list((tmp_path / "sessions").glob("*.json"))
    assert len(log_files) == 1
    assert log.session_id in log_files[0].name


def test_log_content(tmp_path: Path) -> None:
    import json

    version_id = str(uuid4())
    chunk = _make_scored_chunk(version_id)

    from cacten import session_log as sl_module
    with patch.object(sl_module, "LOGS_DIR", tmp_path / "sessions"):
        log = write_session_log(
            query="how do I deploy?",
            kb_version_id=version_id,
            embedding_model="nomic-embed-text",
            chunks=[chunk],
            latency_ms=100,
        )

    log_path = tmp_path / "sessions" / f"{log.session_id}.json"
    data = json.loads(log_path.read_text())

    assert data["original_prompt"] == "how do I deploy?"
    assert data["kb_version_id"] == version_id
    assert data["latency_ms"] == 100
    assert len(data["retrieved_chunks"]) == 1
    assert data["retrieved_chunks"][0]["text"] == "test chunk"
    assert data["retrieved_chunks"][0]["score"] == 0.9
