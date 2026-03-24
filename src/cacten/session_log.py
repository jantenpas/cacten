"""Session logging — write retrieval events to ~/.cacten/logs/sessions/."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel

from cacten.config import LOGS_DIR
from cacten.models import ScoredChunk


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source: str
    score: float


class SessionLog(BaseModel):
    session_id: str
    timestamp: datetime
    kb_version_id: str
    embedding_model: str
    original_prompt: str
    retrieved_chunks: list[RetrievedChunk]
    latency_ms: int
    # Populated after Claude responds — not available at retrieval time
    response: str = ""
    model: str = ""


def write_session_log(
    query: str,
    kb_version_id: str,
    embedding_model: str,
    chunks: list[ScoredChunk],
    latency_ms: int,
    session_id: str | None = None,
) -> SessionLog:
    """Write a session log entry and return it."""
    log = SessionLog(
        session_id=session_id or str(uuid4()),
        timestamp=datetime.now(tz=UTC),
        kb_version_id=kb_version_id,
        embedding_model=embedding_model,
        original_prompt=query,
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id=sc.chunk.metadata.chunk_id,
                text=sc.chunk.text,
                source=sc.chunk.metadata.source_filename or sc.chunk.metadata.source_url or "",
                score=sc.score,
            )
            for sc in chunks
        ],
        latency_ms=latency_ms,
    )
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{log.session_id}.json"
    log_path.write_text(json.dumps(log.model_dump(mode="json"), indent=2))
    return log
