"""Tests for MCP server tools/resources.

End-to-end coverage: exercises search_personal_kb and personal_context
by patching storage and embeddings — no live Ollama or Qdrant required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import cacten.store as store_module
from cacten import config
from cacten.models import Chunk, ChunkMetadata, ScoredChunk
from cacten.server import personal_context, search_personal_kb, set_passthrough


def _scored_chunk(text: str, version_id: str, filename: str = "doc.md") -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(
            text=text,
            metadata=ChunkMetadata(
                chunk_id=str(uuid4()),
                kb_version_id=version_id,
                source_document_id=str(uuid4()),
                source_filename=filename,
                chunk_index=0,
                char_offset_start=0,
                char_offset_end=len(text),
                ingested_at=datetime.now(tz=UTC),
                content_type="markdown",
            ),
        ),
        score=0.85,
    )


# ---------------------------------------------------------------------------
# search_personal_kb
# ---------------------------------------------------------------------------


def test_search_no_active_version() -> None:
    with patch.object(config, "get_active_version_id", return_value=None):
        result = search_personal_kb("anything")
    assert "No active KB version" in result


def test_search_passthrough() -> None:
    set_passthrough(True)
    try:
        result = search_personal_kb("anything")
    finally:
        set_passthrough(False)
    assert "Passthrough mode" in result


def test_search_returns_context_block(tmp_path: Path) -> None:
    version_id = str(uuid4())
    chunks = [_scored_chunk("Python is great.", version_id)]

    with (
        patch.object(config, "get_active_version_id", return_value=version_id),
        patch("cacten.server.retrieve", return_value=chunks),
        patch("cacten.server.write_session_log"),
    ):
        result = search_personal_kb("python tips")

    assert "<cacten_context>" in result
    assert "Python is great." in result
    assert "doc.md" in result


def test_search_writes_session_log(tmp_path: Path) -> None:
    version_id = str(uuid4())
    chunks = [_scored_chunk("Some content.", version_id)]
    captured: list[dict[str, object]] = []

    def fake_write(**kwargs: object) -> None:
        captured.append(dict(kwargs))

    with (
        patch.object(config, "get_active_version_id", return_value=version_id),
        patch("cacten.server.retrieve", return_value=chunks),
        patch("cacten.server.write_session_log", side_effect=fake_write),
    ):
        search_personal_kb("my query", top_k=3)

    assert len(captured) == 1
    assert captured[0]["query"] == "my query"
    assert captured[0]["kb_version_id"] == version_id


def test_search_retrieval_error() -> None:
    version_id = str(uuid4())
    with (
        patch.object(config, "get_active_version_id", return_value=version_id),
        patch("cacten.server.retrieve", side_effect=RuntimeError("boom")),
    ):
        result = search_personal_kb("anything")
    assert "Retrieval error" in result


# ---------------------------------------------------------------------------
# personal_context
# ---------------------------------------------------------------------------


def test_personal_context_no_version() -> None:
    with patch.object(config, "get_active_version_id", return_value=None):
        result = personal_context()
    assert "No personal context" in result


def test_personal_context_returns_chunks() -> None:
    version_id = str(uuid4())
    chunks = [_scored_chunk("I prefer functional patterns.", version_id, "prefs.md")]

    with (
        patch.object(config, "get_active_version_id", return_value=version_id),
        patch("cacten.server.retrieve", return_value=chunks),
    ):
        result = personal_context()

    assert "I prefer functional patterns." in result
    assert "prefs.md" in result


# ---------------------------------------------------------------------------
# M-11: end-to-end smoke test (ingest pipeline → retrieval → context block)
# ---------------------------------------------------------------------------


def test_end_to_end_ingest_retrieve(tmp_path: Path) -> None:
    """Smoke test: pipeline → store → retrieve → format_context_block."""
    import cacten.config as cfg_module
    from cacten.embeddings import embed_sparse
    from cacten.retrieval import format_context_block
    from cacten.retrieval import retrieve as _retrieve
    from cacten.store import QdrantVectorStore

    version_id = str(uuid4())
    qdrant_path = tmp_path / "qdrant"

    fake_dense = [0.1] * 768
    sparse_idx, sparse_val = embed_sparse("hello world test chunk")

    # Build and insert a chunk directly (no Ollama needed)
    with patch.object(store_module, "QDRANT_PATH", qdrant_path):
        store = QdrantVectorStore()
        from cacten.models import Chunk, ChunkMetadata

        chunk = Chunk(
            text="hello world test chunk",
            metadata=ChunkMetadata(
                chunk_id=str(uuid4()),
                kb_version_id=version_id,
                source_document_id=str(uuid4()),
                source_filename="e2e.md",
                chunk_index=0,
                char_offset_start=0,
                char_offset_end=22,
                ingested_at=datetime.now(tz=UTC),
                content_type="markdown",
            ),
            dense_vector=fake_dense,
            sparse_indices=sparse_idx,
            sparse_values=sparse_val,
        )
        store.add([chunk])

        with (
            patch.object(cfg_module, "get_active_version_id", return_value=version_id),
            patch("cacten.retrieval.embed_dense", return_value=fake_dense),
            patch("cacten.retrieval.embed_sparse", return_value=(sparse_idx, sparse_val)),
            patch("cacten.retrieval.QdrantVectorStore", return_value=store),
        ):
            results = _retrieve("hello world", top_k=5)

    assert len(results) >= 1
    assert results[0].chunk.text == "hello world test chunk"

    context = format_context_block(results)
    assert "<cacten_context>" in context
    assert "e2e.md" in context


def test_personal_context_retrieval_error() -> None:
    version_id = str(uuid4())
    with (
        patch.object(config, "get_active_version_id", return_value=version_id),
        patch("cacten.server.retrieve", side_effect=RuntimeError("boom")),
    ):
        result = personal_context()
    assert "unavailable" in result


def test_personal_context_empty_chunks() -> None:
    version_id = str(uuid4())
    with (
        patch.object(config, "get_active_version_id", return_value=version_id),
        patch("cacten.server.retrieve", return_value=[]),
    ):
        result = personal_context()
    assert "No personal context found" in result


async def test_serve_passthrough_skips_ollama() -> None:
    from unittest.mock import AsyncMock

    from cacten.server import serve

    with (
        patch("cacten.server.check_ollama") as mock_check,
        patch("cacten.server.mcp") as mock_mcp,
    ):
        mock_mcp.run_stdio_async = AsyncMock()
        await serve(passthrough=True)
        mock_check.assert_not_called()


async def test_serve_ollama_warning_on_failure() -> None:
    import sys
    from io import StringIO
    from unittest.mock import AsyncMock

    from cacten.server import serve

    with (
        patch("cacten.server.check_ollama", side_effect=RuntimeError("offline")),
        patch("cacten.server.mcp") as mock_mcp,
    ):
        mock_mcp.run_stdio_async = AsyncMock()
        buf = StringIO()
        with patch.object(sys, "stderr", buf):
            await serve(passthrough=False)

    stderr_output = buf.getvalue()
    assert "Warning" in stderr_output, f"Expected warning on stderr, got: {stderr_output!r}"
    assert "offline" in stderr_output, f"Expected error message in warning, got: {stderr_output!r}"
