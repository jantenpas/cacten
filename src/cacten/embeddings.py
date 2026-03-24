"""Embedding clients: dense (Ollama) and sparse (BM25)."""

from __future__ import annotations

import ollama

from cacten.config import EMBEDDING_MODEL


def embed_dense(text: str) -> list[float]:
    """Generate 768-dim dense embedding via Ollama nomic-embed-text."""
    try:
        response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)
    except Exception as exc:
        raise RuntimeError(
            f"Ollama unreachable — is `ollama serve` running? ({exc})"
        ) from exc
    embedding: list[float] = response["embedding"]
    return embedding


def check_ollama() -> None:
    """Fail fast if Ollama is unreachable or model is missing."""
    try:
        ollama.embeddings(model=EMBEDDING_MODEL, prompt="ping")
    except Exception as exc:
        raise RuntimeError(
            f"Ollama unreachable — run `ollama serve` and `ollama pull {EMBEDDING_MODEL}`. ({exc})"
        ) from exc


class BM25Encoder:
    """Sparse vector encoder using term-frequency weighting.

    Produces (indices, values) suitable for Qdrant sparse vectors.
    Indices are stable hash-based vocab IDs; values are normalized TF weights.
    This is a v1 approximation — SPLADE or proper BM25 with fixed vocab is a v2 upgrade.
    """

    def encode(self, text: str) -> tuple[list[int], list[float]]:
        tokens = text.lower().split()
        if not tokens:
            return [], []

        counts: dict[str, int] = {}
        for tok in tokens:
            counts[tok] = counts.get(tok, 0) + 1

        total = len(tokens)
        # Use abs(hash) as a stable, collision-tolerant vocabulary index
        term_scores: dict[int, float] = {}
        for tok, count in counts.items():
            idx = abs(hash(tok)) % (2**24)  # keep indices manageable
            tf = count / total
            term_scores[idx] = tf

        indices = sorted(term_scores.keys())
        values = [term_scores[i] for i in indices]
        return indices, values


_bm25_encoder = BM25Encoder()


def embed_sparse(text: str) -> tuple[list[int], list[float]]:
    """Return BM25 sparse vector as (indices, values)."""
    return _bm25_encoder.encode(text)
