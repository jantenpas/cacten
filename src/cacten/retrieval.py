"""Retrieval engine — hybrid search over the active KB version."""

from __future__ import annotations

from cacten import config
from cacten.embeddings import embed_dense, embed_sparse
from cacten.models import ScoredChunk
from cacten.store import QdrantVectorStore
from cacten.versions import get_version


def retrieve(
    query: str,
    top_k: int = 10,
    kb_version_id: str | None = None,
) -> list[ScoredChunk]:
    """Run hybrid search and return ranked chunks.

    Args:
        query: Developer's search query.
        top_k: Number of chunks to return.
        kb_version_id: Override active version. Defaults to config active version.

    Raises:
        RuntimeError: If no active KB version is set.
    """
    version_id = kb_version_id or config.get_active_version_id()
    if version_id is None:
        raise RuntimeError("No active KB version. Run `cacten ingest` first.")

    version = get_version(version_id)
    if version is not None and version.embedding_model != config.EMBEDDING_MODEL:
        raise RuntimeError(
            f"Embedding model mismatch: KB version was built with "
            f"'{version.embedding_model}' but current model is '{config.EMBEDDING_MODEL}'. "
            f"Re-ingest your documents to rebuild with the current model."
        )

    dense = embed_dense(query)
    sparse_idx, sparse_val = embed_sparse(query)

    store = QdrantVectorStore()
    return store.search(
        dense_vector=dense,
        sparse_indices=sparse_idx,
        sparse_values=sparse_val,
        kb_version_id=version_id,
        top_k=top_k,
    )


def format_context_block(chunks: list[ScoredChunk]) -> str:
    """Format scored chunks into the <cacten_context> block for MCP."""
    if not chunks:
        return "<cacten_context>\nNo relevant context found.\n</cacten_context>"

    version_id = chunks[0].chunk.metadata.kb_version_id
    lines = [
        "The following context was retrieved from your personal knowledge base.",
        "Use it to inform your response, but do not cite it directly unless asked.",
        f"KB version: {version_id}",
        "",
    ]
    for sc in chunks:
        source = sc.chunk.metadata.source_filename or sc.chunk.metadata.source_url or "unknown"
        lines.append(f"[Source: {source}] [Score: {sc.score:.2f}]")
        lines.append(sc.chunk.text)
        lines.append("")

    return "<cacten_context>\n" + "\n".join(lines) + "</cacten_context>"
