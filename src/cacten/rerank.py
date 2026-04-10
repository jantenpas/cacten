"""Cross-encoder reranking helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol, cast

from cacten import config
from cacten.models import ScoredChunk


class _RerankerResult(Protocol):
    @property
    def score(self) -> float: ...


class _TextCrossEncoder(Protocol):
    def rerank(self, query: str, documents: list[str]) -> list[_RerankerResult]: ...


@lru_cache(maxsize=1)
def _get_reranker() -> _TextCrossEncoder:
    """Lazily construct the reranker model.

    The dependency is imported inside the function so the rest of Cacten can run
    without the reranker stack installed.
    """
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
    except ImportError as exc:
        raise RuntimeError(
            "Reranker dependency is not installed. Install `fastembed` "
            "to enable cross-encoder reranking."
        ) from exc

    try:
        return cast(_TextCrossEncoder, TextCrossEncoder(model_name=config.RERANK_MODEL))
    except Exception as exc:
        raise RuntimeError(
            f"Reranker model '{config.RERANK_MODEL}' is unavailable. "
            "Run retrieval with network access once to download the model, "
            "or disable reranking."
        ) from exc


def _truncate(text: str) -> str:
    """Clamp candidate text length so reranking latency stays bounded."""
    return text[: config.RERANK_MAX_CHARS]


def _coerce_score(result: float | _RerankerResult) -> float:
    if isinstance(result, int | float):
        return float(result)
    return float(result.score)


def score_pairs(query: str, texts: list[str]) -> list[float]:
    """Score query/text pairs with the configured reranker model."""
    if not texts:
        return []

    model = _get_reranker()
    documents = [_truncate(text) for text in texts]
    results = model.rerank(query=query, documents=documents)
    return [_coerce_score(result) for result in results]


def rerank(query: str, candidates: list[ScoredChunk], top_k: int) -> list[ScoredChunk]:
    """Return candidates sorted by cross-encoder relevance score."""
    if not candidates:
        return []

    scores = score_pairs(query, [candidate.chunk.text for candidate in candidates])
    reranked = [
        ScoredChunk(chunk=candidate.chunk, score=score)
        for candidate, score in zip(candidates, scores, strict=True)
    ]
    reranked.sort(key=lambda item: item.score, reverse=True)
    return reranked[:top_k]
