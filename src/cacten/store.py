"""VectorStore protocol and QdrantVectorStore implementation."""

from __future__ import annotations

from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from cacten.config import COLLECTION_NAME, EMBEDDING_DIM, QDRANT_PATH
from cacten.models import Chunk, ScoredChunk


class VectorStore(Protocol):
    def add(self, chunks: list[Chunk]) -> None: ...

    def search(
        self,
        dense_vector: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        kb_version_id: str,
        top_k: int,
    ) -> list[ScoredChunk]: ...

    def delete_version(self, kb_version_id: str) -> None: ...


class QdrantVectorStore:
    def __init__(self) -> None:
        self._client = QdrantClient(path=str(QDRANT_PATH))
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if COLLECTION_NAME not in existing:
            self._client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={
                    "dense": VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
                },
                sparse_vectors_config={"sparse": SparseVectorParams()},
            )

    def add(self, chunks: list[Chunk]) -> None:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=chunk.metadata.chunk_id,
                vector={
                    "dense": chunk.dense_vector,
                    "sparse": SparseVector(
                        indices=chunk.sparse_indices,
                        values=chunk.sparse_values,
                    ),
                },
                payload={
                    "text": chunk.text,
                    **chunk.metadata.model_dump(mode="json"),
                },
            )
            for chunk in chunks
        ]
        self._client.upsert(collection_name=COLLECTION_NAME, points=points)

    def search(
        self,
        dense_vector: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        kb_version_id: str,
        top_k: int = 10,
    ) -> list[ScoredChunk]:
        from cacten.models import ChunkMetadata

        version_filter = Filter(
            must=[FieldCondition(key="kb_version_id", match=MatchValue(value=kb_version_id))]
        )
        results = self._client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                Prefetch(
                    query=SparseVector(indices=sparse_indices, values=sparse_values),
                    using="sparse",
                    filter=version_filter,
                    limit=50,
                ),
                Prefetch(
                    query=dense_vector,
                    using="dense",
                    filter=version_filter,
                    limit=50,
                ),
            ],
            query=FusionQuery(fusion=Fusion.DBSF),
            query_filter=version_filter,
            limit=top_k,
        )
        scored: list[ScoredChunk] = []
        for point in results.points:
            payload = dict(point.payload or {})
            text = str(payload.pop("text", ""))
            metadata = ChunkMetadata.model_validate(payload)
            chunk = Chunk(text=text, metadata=metadata)
            scored.append(ScoredChunk(chunk=chunk, score=point.score))
        return scored

    def delete_version(self, kb_version_id: str) -> None:
        from qdrant_client.models import FilterSelector

        self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="kb_version_id", match=MatchValue(value=kb_version_id)
                        )
                    ]
                )
            ),
        )
