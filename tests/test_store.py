"""Tests for QdrantVectorStore (uses a temp Qdrant path)."""

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

import cacten.store as store_module
from cacten.models import Chunk, ChunkMetadata
from cacten.store import QdrantVectorStore


def _make_chunk(version_id: str, idx: int = 0) -> Chunk:
    return Chunk(
        text=f"chunk text {idx}",
        metadata=ChunkMetadata(
            chunk_id=str(uuid4()),
            kb_version_id=version_id,
            source_document_id=str(uuid4()),
            source_filename="test.md",
            chunk_index=idx,
            char_offset_start=0,
            char_offset_end=10,
            ingested_at=datetime.now(tz=UTC),
            content_type="markdown",
        ),
        dense_vector=[0.1] * 768,
        sparse_indices=[0, 1],
        sparse_values=[0.5, 0.3],
    )


@pytest.fixture()
def store(tmp_path: Path) -> Generator[QdrantVectorStore, None, None]:
    with patch.object(store_module, "QDRANT_PATH", tmp_path / "qdrant"):
        yield QdrantVectorStore()


def test_add_and_search(store: QdrantVectorStore) -> None:
    version_id = str(uuid4())
    chunk = _make_chunk(version_id)
    store.add([chunk])

    results = store.search(
        dense_vector=[0.1] * 768,
        sparse_indices=[0, 1],
        sparse_values=[0.5, 0.3],
        kb_version_id=version_id,
        top_k=5,
    )
    assert len(results) == 1
    assert results[0].chunk.text == chunk.text


def test_delete_version(store: QdrantVectorStore) -> None:
    version_id = str(uuid4())
    store.add([_make_chunk(version_id, 0), _make_chunk(version_id, 1)])

    store.delete_version(version_id)

    results = store.search(
        dense_vector=[0.1] * 768,
        sparse_indices=[0],
        sparse_values=[0.5],
        kb_version_id=version_id,
        top_k=10,
    )
    assert results == []


def test_search_version_isolation(store: QdrantVectorStore) -> None:
    v1 = str(uuid4())
    v2 = str(uuid4())
    store.add([_make_chunk(v1)])
    store.add([_make_chunk(v2)])

    results_v1 = store.search([0.1] * 768, [0], [0.5], v1, top_k=10)
    results_v2 = store.search([0.1] * 768, [0], [0.5], v2, top_k=10)

    assert len(results_v1) == 1
    assert len(results_v2) == 1
    assert results_v1[0].chunk.metadata.kb_version_id == v1
    assert results_v2[0].chunk.metadata.kb_version_id == v2


def test_get_chunks_by_id(store: QdrantVectorStore) -> None:
    version_id = str(uuid4())
    chunk_a = _make_chunk(version_id, 0)
    chunk_b = _make_chunk(version_id, 1)
    store.add([chunk_a, chunk_b])

    results = store.get_chunks([chunk_b.metadata.chunk_id, chunk_a.metadata.chunk_id])

    assert [chunk.metadata.chunk_id for chunk in results] == [
        chunk_b.metadata.chunk_id,
        chunk_a.metadata.chunk_id,
    ]
    assert results[0].text == chunk_b.text
    assert results[1].text == chunk_a.text
