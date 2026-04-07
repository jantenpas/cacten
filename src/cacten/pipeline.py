"""Ingestion pipeline: load → split → embed → upsert."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import typer

from cacten import config, versions
from cacten.embeddings import embed_dense, embed_sparse
from cacten.loaders import EXTENSION_CONTENT_TYPE, load_file, load_url
from cacten.models import Chunk, ChunkMetadata, KBVersion
from cacten.splitter import split_by_content_type
from cacten.store import QdrantVectorStore

# Directories that are never useful to ingest.
_SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}


def ingest(
    source: str,
    notes: str | None = None,
) -> KBVersion:
    """Ingest a local file path or URL into the knowledge base.

    Returns the new KBVersion created for this ingestion.
    """
    config.ensure_dirs()

    # Load document
    if source.startswith("http://"):
        raise ValueError("Insecure URLs are not allowed. Use https://")
    is_url = source.startswith("https://")
    if is_url:
        text, content_type = load_url(source)
        source_url: str | None = source
        source_filename: str | None = None
    else:
        path = Path(source).expanduser().resolve()
        text, content_type = load_file(path)
        source_url = None
        source_filename = path.name

    # Split
    raw_chunks = split_by_content_type(text, content_type)
    if not raw_chunks:
        raise ValueError(f"No text extracted from {source!r}")

    version_id = str(uuid4())
    source_doc_id = str(uuid4())
    ingested_at = datetime.now(tz=UTC)

    chunks: list[Chunk] = []
    char_pos = 0

    for i, chunk_text in enumerate(raw_chunks):
        dense = embed_dense(chunk_text)
        sparse_idx, sparse_val = embed_sparse(chunk_text)

        start = text.find(chunk_text, char_pos)
        if start == -1:
            start = char_pos
        end = start + len(chunk_text)
        char_pos = end

        metadata = ChunkMetadata(
            chunk_id=str(uuid4()),
            kb_version_id=version_id,
            source_document_id=source_doc_id,
            source_url=source_url,
            source_filename=source_filename,
            chunk_index=i,
            char_offset_start=start,
            char_offset_end=end,
            ingested_at=ingested_at,
            content_type=content_type,
        )
        chunks.append(
            Chunk(
                text=chunk_text,
                metadata=metadata,
                dense_vector=dense,
                sparse_indices=sparse_idx,
                sparse_values=sparse_val,
            )
        )

    store = QdrantVectorStore()
    store.add(chunks)

    version = versions.create_version(
        document_count=1,
        chunk_count=len(chunks),
        embedding_model=config.EMBEDDING_MODEL,
        notes=notes,
        version_id=version_id,
    )
    config.set_active_version_id(version.version_id)
    return version


def ingest_manifest(
    project_root: str | None = None,
    label: str | None = None,
) -> KBVersion:
    """Ingest all files resolved from .cacten/sources.toml as a single KB version.

    If sources.toml is missing but sources-example.toml exists, bootstraps it first
    and prints a notice. Raises FileNotFoundError if neither file exists.
    """
    from cacten.manifest import (
        ManifestConfig,
        bootstrap_manifest,
        load_manifest,
        manifest_path,
        resolve_files,
        snapshot_manifest,
    )

    config.ensure_dirs()

    root = Path(project_root).expanduser().resolve() if project_root else Path.cwd()
    mp = manifest_path(root)

    if not mp.exists():
        bootstrapped = bootstrap_manifest(root)
        typer.echo(f"No sources.toml found. Generating from the sample file: {bootstrapped}")

    manifest: ManifestConfig = load_manifest(root)
    files = resolve_files(manifest, root)
    if not files:
        raise ValueError("Manifest resolved no files — check include/exclude patterns.")

    snapshot_path, manifest_hash = snapshot_manifest(root)

    version_id = str(uuid4())
    ingested_at = datetime.now(tz=UTC)
    chunks: list[Chunk] = []

    for file_path in files:
        text, content_type = load_file(file_path)
        raw_chunks = split_by_content_type(text, content_type)
        if not raw_chunks:
            continue
        source_doc_id = str(uuid4())
        char_pos = 0
        for i, chunk_text in enumerate(raw_chunks):
            dense = embed_dense(chunk_text)
            sparse_idx, sparse_val = embed_sparse(chunk_text)
            start = text.find(chunk_text, char_pos)
            if start == -1:
                start = char_pos
            end = start + len(chunk_text)
            char_pos = end
            chunks.append(
                Chunk(
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        chunk_id=str(uuid4()),
                        kb_version_id=version_id,
                        source_document_id=source_doc_id,
                        source_url=None,
                        source_filename=file_path.name,
                        chunk_index=i,
                        char_offset_start=start,
                        char_offset_end=end,
                        ingested_at=ingested_at,
                        content_type=content_type,
                    ),
                    dense_vector=dense,
                    sparse_indices=sparse_idx,
                    sparse_values=sparse_val,
                )
            )

    if not chunks:
        raise ValueError("No text could be extracted from any resolved files.")

    store = QdrantVectorStore()
    store.add(chunks)

    version = versions.create_version(
        document_count=len(files),
        chunk_count=len(chunks),
        embedding_model=config.EMBEDDING_MODEL,
        notes=label,
        version_id=version_id,
        manifest_path=str(mp),
        manifest_snapshot_path=str(snapshot_path),
        manifest_hash=manifest_hash,
        manifest_version=manifest.version,
        resolved_files=[str(f) for f in files],
    )
    config.set_active_version_id(version.version_id)
    return version


def ingest_directory(
    directory: str,
    extensions: list[str] | None = None,
    notes: str | None = None,
) -> list[KBVersion]:
    """Ingest all supported files in a directory tree.

    Walks the directory recursively, skipping hidden dirs and common
    non-source dirs (node_modules, __pycache__, etc.). Each file is
    ingested as its own KB version.

    Args:
        directory: Path to the directory to walk.
        extensions: File extensions to include (e.g. [".py", ".ts"]).
                    Defaults to all extensions in EXTENSION_CONTENT_TYPE.
        notes: Optional annotation applied to every version created.

    Returns:
        List of KBVersion objects, one per ingested file.
    """
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"{directory!r} is not a directory")

    allowed = set(extensions or EXTENSION_CONTENT_TYPE.keys())
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in allowed
        and not any(part.startswith(".") or part in _SKIP_DIRS for part in path.parts)
    ]

    if not files:
        raise ValueError(f"No supported files found in {directory!r}")

    return [ingest(str(f), notes=notes) for f in sorted(files)]
