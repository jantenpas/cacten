"""Ingestion pipeline: load → split → embed → upsert."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import typer

from cacten import config, versions
from cacten.embeddings import embed_dense, embed_dense_many, embed_sparse
from cacten.loaders import EXTENSION_CONTENT_TYPE, load_file, load_url
from cacten.models import Chunk, ChunkMetadata, KBVersion, VersionFileRecord
from cacten.splitter import split_by_content_type
from cacten.store import QdrantVectorStore

# Directories that are never useful to ingest.
_SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}

_DENSE_EMBED_BATCH_SIZE = 32
_UPSERT_BATCH_SIZE = 256
_CHUNK_PROFILE = "default"


def _hash_file(path: Path) -> str:
    """Return a stable content hash for a source file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _detect_content_type(path: Path) -> str:
    """Best-effort content type detection from file extension."""
    return EXTENSION_CONTENT_TYPE.get(path.suffix.lower(), "unknown")


def _iter_chunk_batches(
    *,
    raw_chunks: list[str],
    text: str,
    version_id: str,
    source_doc_id: str,
    source_url: str | None,
    source_filename: str | None,
    content_type: str,
    ingested_at: datetime,
) -> Iterator[list[Chunk]]:
    """Yield fully-embedded chunk batches for a source document."""
    char_pos = 0

    for batch_start in range(0, len(raw_chunks), _DENSE_EMBED_BATCH_SIZE):
        chunk_batch = raw_chunks[batch_start : batch_start + _DENSE_EMBED_BATCH_SIZE]
        dense_vectors = embed_dense_many(chunk_batch)
        built_batch: list[Chunk] = []

        for batch_offset, (chunk_text, dense_vector) in enumerate(
            zip(chunk_batch, dense_vectors, strict=True)
        ):
            chunk_index = batch_start + batch_offset
            sparse_idx, sparse_val = embed_sparse(chunk_text)

            start = text.find(chunk_text, char_pos)
            if start == -1:
                start = char_pos
            end = start + len(chunk_text)
            char_pos = end

            built_batch.append(
                Chunk(
                    text=chunk_text,
                    metadata=ChunkMetadata(
                        chunk_id=str(uuid4()),
                        kb_version_id=version_id,
                        source_document_id=source_doc_id,
                        source_url=source_url,
                        source_filename=source_filename,
                        chunk_index=chunk_index,
                        char_offset_start=start,
                        char_offset_end=end,
                        ingested_at=ingested_at,
                        content_type=content_type,
                    ),
                    dense_vector=dense_vector,
                    sparse_indices=sparse_idx,
                    sparse_values=sparse_val,
                )
            )

        if built_batch:
            yield built_batch


def _clone_chunks_for_version(
    chunks: list[Chunk],
    *,
    version_id: str,
    source_doc_id: str,
    ingested_at: datetime,
) -> list[Chunk]:
    """Clone prior chunks into a new KB version without re-embedding."""
    cloned: list[Chunk] = []
    for chunk in chunks:
        cloned.append(
            Chunk(
                text=chunk.text,
                metadata=ChunkMetadata(
                    chunk_id=str(uuid4()),
                    kb_version_id=version_id,
                    source_document_id=source_doc_id,
                    source_url=chunk.metadata.source_url,
                    source_filename=chunk.metadata.source_filename,
                    source_path=chunk.metadata.source_path,
                    source_file_hash=chunk.metadata.source_file_hash,
                    chunk_index=chunk.metadata.chunk_index,
                    char_offset_start=chunk.metadata.char_offset_start,
                    char_offset_end=chunk.metadata.char_offset_end,
                    ingested_at=ingested_at,
                    content_type=chunk.metadata.content_type,
                ),
                dense_vector=chunk.dense_vector,
                sparse_indices=chunk.sparse_indices,
                sparse_values=chunk.sparse_values,
            )
        )
    return cloned


def ingest(
    source: str,
    notes: str | None = None,
) -> KBVersion:
    """Ingest a local file path or URL into the knowledge base.

    Returns the new KBVersion created for this ingestion.
    """
    # Load document
    if source.startswith("http://"):
        raise ValueError("Insecure URLs are not allowed. Use https://")

    config.ensure_dirs()

    is_url = source.startswith("https://")
    if is_url:
        text, content_type = load_url(source)
        source_url: str | None = source
        source_filename: str | None = None
        source_path: str | None = None
        source_file_hash: str | None = None
    else:
        path = Path(source).expanduser().resolve()
        file_hash = _hash_file(path)
        text, content_type = load_file(path)
        source_url = None
        source_filename = path.name
        source_path = str(path)
        source_file_hash = file_hash

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
            source_path=source_path,
            source_file_hash=source_file_hash,
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
    from cacten.versions import load_version_files, save_version_files

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

    previous_version_id = config.get_active_version_id()
    previous_records = {
        record.path: record
        for record in load_version_files(previous_version_id)
    } if previous_version_id else {}

    snapshot_path, manifest_hash = snapshot_manifest(root)

    version_id = str(uuid4())
    ingested_at = datetime.now(tz=UTC)
    store = QdrantVectorStore()
    pending_chunks: list[Chunk] = []
    document_count = 0
    chunk_count = 0
    wrote_chunks = False
    version_file_records: list[VersionFileRecord] = []
    unchanged_count = 0
    changed_count = 0
    new_count = 0

    try:
        for file_path in files:
            file_hash = _hash_file(file_path)
            file_size = file_path.stat().st_size
            content_type = _detect_content_type(file_path)
            previous_record = previous_records.get(str(file_path))

            can_reuse = (
                previous_version_id is not None
                and previous_record is not None
                and previous_record.file_hash == file_hash
                and previous_record.content_type == content_type
                and previous_record.embedding_model == config.EMBEDDING_MODEL
                and previous_record.sparse_encoder_version == config.SPARSE_ENCODER_VERSION
                and previous_record.chunk_profile == _CHUNK_PROFILE
            )

            if can_reuse and previous_record is not None:
                previous_chunks = store.get_chunks(previous_record.chunk_ids)
                if len(previous_chunks) == previous_record.chunk_count:
                    document_count += 1
                    unchanged_count += 1
                    source_doc_id = str(uuid4())
                    reused_chunks = _clone_chunks_for_version(
                        previous_chunks,
                        version_id=version_id,
                        source_doc_id=source_doc_id,
                        ingested_at=ingested_at,
                    )
                    pending_chunks.extend(reused_chunks)
                    chunk_count += len(reused_chunks)
                    version_file_records.append(
                        VersionFileRecord(
                            path=str(file_path),
                            file_hash=file_hash,
                            file_size=file_size,
                            content_type=content_type,
                            embedding_model=config.EMBEDDING_MODEL,
                            sparse_encoder_version=config.SPARSE_ENCODER_VERSION,
                            chunk_profile=_CHUNK_PROFILE,
                            chunk_count=len(reused_chunks),
                            chunk_ids=[chunk.metadata.chunk_id for chunk in reused_chunks],
                        )
                    )
                    if len(pending_chunks) >= _UPSERT_BATCH_SIZE:
                        store.add(pending_chunks)
                        pending_chunks = []
                        wrote_chunks = True
                    continue

            new_count += previous_record is None
            changed_count += previous_record is not None

            text, content_type = load_file(file_path)
            raw_chunks = split_by_content_type(text, content_type)
            if not raw_chunks:
                continue

            document_count += 1
            source_doc_id = str(uuid4())
            file_chunk_ids: list[str] = []
            for chunk_batch in _iter_chunk_batches(
                raw_chunks=raw_chunks,
                text=text,
                version_id=version_id,
                source_doc_id=source_doc_id,
                source_url=None,
                source_filename=file_path.name,
                content_type=content_type,
                ingested_at=ingested_at,
            ):
                for chunk in chunk_batch:
                    chunk.metadata.source_path = str(file_path)
                    chunk.metadata.source_file_hash = file_hash
                file_chunk_ids.extend(chunk.metadata.chunk_id for chunk in chunk_batch)
                pending_chunks.extend(chunk_batch)
                chunk_count += len(chunk_batch)
                if len(pending_chunks) >= _UPSERT_BATCH_SIZE:
                    store.add(pending_chunks)
                    pending_chunks = []
                    wrote_chunks = True

            version_file_records.append(
                VersionFileRecord(
                    path=str(file_path),
                    file_hash=file_hash,
                    file_size=file_size,
                    content_type=content_type,
                    embedding_model=config.EMBEDDING_MODEL,
                    sparse_encoder_version=config.SPARSE_ENCODER_VERSION,
                    chunk_profile=_CHUNK_PROFILE,
                    chunk_count=len(file_chunk_ids),
                    chunk_ids=file_chunk_ids,
                )
            )

        if pending_chunks:
            store.add(pending_chunks)
            wrote_chunks = True

        if chunk_count == 0:
            raise ValueError("No text could be extracted from any resolved files.")

        version = versions.create_version(
            document_count=document_count,
            chunk_count=chunk_count,
            embedding_model=config.EMBEDDING_MODEL,
            notes=label,
            version_id=version_id,
            manifest_path=str(mp),
            manifest_snapshot_path=str(snapshot_path),
            manifest_hash=manifest_hash,
            manifest_version=manifest.version,
            resolved_files=[str(f) for f in files],
        )
        save_version_files(version.version_id, version_file_records)
        config.set_active_version_id(version.version_id)
        typer.echo(
            f"Incremental ingest summary: unchanged={unchanged_count} "
            f"changed={changed_count} new={new_count}"
        )
        return version
    except Exception:
        versions.delete_version(version_id)
        if wrote_chunks:
            store.delete_version(version_id)
        raise


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
