"""Shared Pydantic data models."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    chunk_id: str
    kb_version_id: str
    source_document_id: str
    source_url: str | None = None
    source_filename: str | None = None
    chunk_index: int
    char_offset_start: int
    char_offset_end: int
    ingested_at: datetime
    content_type: str  # "markdown" | "pdf" | "html"


class Chunk(BaseModel):
    text: str
    metadata: ChunkMetadata
    dense_vector: list[float] = Field(default_factory=list)
    sparse_indices: list[int] = Field(default_factory=list)
    sparse_values: list[float] = Field(default_factory=list)


class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float


class KBVersion(BaseModel):
    version_id: str
    version_number: int
    created_at: datetime
    document_count: int
    chunk_count: int
    embedding_model: str
    notes: str | None = None
