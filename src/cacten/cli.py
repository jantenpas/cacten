"""Cacten CLI — init, ingest, retrieve, versions."""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(
    name="cacten",
    help="Personalized RAG middleware for Claude Code.",
    no_args_is_help=True,
)

versions_app = typer.Typer(help="Manage KB versions.")
app.add_typer(versions_app, name="versions")


# ---------------------------------------------------------------------------
# cacten init
# ---------------------------------------------------------------------------


@app.command()
def init() -> None:
    """Initialize .cacten/sources.toml for this project from the example template."""
    from pathlib import Path

    from cacten.manifest import (
        bootstrap_manifest,
        example_manifest_path,
        manifest_path,
    )

    root = Path.cwd()
    dest = manifest_path(root)

    if dest.exists():
        typer.echo(f"Manifest already exists: {dest}")
        raise typer.Exit(0)

    try:
        created = bootstrap_manifest(root)
    except FileNotFoundError:
        example = example_manifest_path(root)
        typer.echo(
            f"Error: {example} not found. "
            "Add a .cacten/sources-example.toml to this project first.",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(f"Created {created}  — edit it, then run `cacten ingest`.")


# ---------------------------------------------------------------------------
# cacten serve
# ---------------------------------------------------------------------------


@app.command()
def serve(
    passthrough: Annotated[
        bool,
        typer.Option("--passthrough", help="Bypass RAG — return empty context for all queries."),
    ] = False,
) -> None:
    """Start the Cacten MCP server (stdio transport for Claude Code)."""
    import asyncio

    from cacten.server import serve as _serve

    asyncio.run(_serve(passthrough=passthrough))


# ---------------------------------------------------------------------------
# cacten ingest
# ---------------------------------------------------------------------------


@app.command()
def ingest(
    sources: Annotated[
        list[str] | None,
        typer.Argument(help="File paths, directories, or URLs. Omit to use .cacten/sources.toml."),
    ] = None,
    label: Annotated[
        str | None,
        typer.Option("--label", "-l", help="Human-friendly label for this KB version."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Resolve and preview files without ingesting."),
    ] = False,
    ext: Annotated[
        str | None,
        typer.Option("--ext", help="Comma-separated extensions to filter (e.g. --ext .py,.ts,.md)."),
    ] = None,
) -> None:
    """Ingest files into the personal knowledge base.

    With no arguments, reads .cacten/sources.toml and ingests all resolved files
    as a single KB version. Pass paths or URLs for ad hoc ingestion.
    """
    from pathlib import Path

    from cacten.embeddings import check_ollama
    from cacten.manifest import load_manifest, manifest_path, resolve_files
    from cacten.pipeline import ingest as _ingest
    from cacten.pipeline import ingest_directory, ingest_manifest

    # --dry-run is only supported for manifest-based ingest
    if dry_run:
        root = Path.cwd()
        try:
            manifest = load_manifest(root)
        except FileNotFoundError:
            typer.echo(f"No manifest found at {manifest_path(root)}", err=True)
            raise typer.Exit(1)
        files = resolve_files(manifest, root)
        typer.echo(f"Manifest: {manifest_path(root)}")
        typer.echo(f"Resolved files: {len(files)}")
        for f in files:
            display = f.relative_to(root) if f.is_relative_to(root) else f
            typer.echo(f"  {display}")
        return

    typer.echo("Checking Ollama...")
    try:
        check_ollama()
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e

    # Manifest-based ingest (no explicit sources provided)
    if not sources:
        try:
            version = ingest_manifest(label=label)
        except (FileNotFoundError, ValueError) as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1) from e
        typer.echo(f"Loaded manifest: {manifest_path(Path.cwd())}")
        typer.echo(f"Created KB version v{version.version_number} (active)")
        typer.echo(f"Files ingested: {version.document_count}")
        typer.echo(f"Chunks created: {version.chunk_count}")
        return

    # Ad hoc ingest (explicit paths or URLs)
    for source in sources:
        is_dir = not source.startswith("http") and Path(source).expanduser().is_dir()
        try:
            if is_dir:
                typer.echo(f"Ingesting directory: {source}")
                extensions = [e.strip() for e in ext.split(",")] if ext else None
                dir_versions = ingest_directory(source, extensions=extensions, notes=label)
                total_chunks = sum(v.chunk_count for v in dir_versions)
                typer.echo(
                    f"Done. {len(dir_versions)} files ingested "
                    f"({total_chunks} chunks total). Last version now active."
                )
            else:
                typer.echo(f"Ingesting: {source}")
                version = _ingest(source, notes=label)
                typer.echo(
                    f"Done. KB version v{version.version_number} created "
                    f"({version.chunk_count} chunks). Now active."
                )
        except (ValueError, RuntimeError) as e:
            typer.echo(f"Error ingesting {source!r}: {e}", err=True)
            raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# cacten retrieve
# ---------------------------------------------------------------------------


@app.command()
def retrieve(
    query: Annotated[str, typer.Argument(help="Search query.")],
    top_k: Annotated[int, typer.Option("--top-k", "-k", help="Chunks to return.")] = 10,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show context block.")] = False,
) -> None:
    """Retrieve context chunks from the knowledge base (debug/test)."""
    from cacten.retrieval import format_context_block
    from cacten.retrieval import retrieve as _retrieve

    try:
        results = _retrieve(query, top_k=top_k)
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e

    if verbose:
        typer.echo(format_context_block(results))
    else:
        typer.echo(f"Retrieved {len(results)} chunks:")
        for i, sc in enumerate(results, 1):
            source = sc.chunk.metadata.source_filename or sc.chunk.metadata.source_url or "unknown"
            preview = sc.chunk.text[:80].replace("\n", " ")
            typer.echo(f"  {i}. [{source}] score={sc.score:.3f}  {preview!r}")


# ---------------------------------------------------------------------------
# cacten versions list
# ---------------------------------------------------------------------------


@versions_app.command("list")
def versions_list() -> None:
    """List all KB versions."""
    from cacten import config
    from cacten.versions import list_versions

    active_id = config.get_active_version_id()
    all_versions = list_versions()
    if not all_versions:
        typer.echo("No versions found. Run `cacten ingest` to create one.")
        return

    for v in all_versions:
        active_marker = " (active)" if v.version_id == active_id else ""
        typer.echo(
            f"v{v.version_number}{active_marker}  {v.version_id[:8]}  "
            f"{v.created_at.strftime('%Y-%m-%d %H:%M')}  "
            f"{v.chunk_count} chunks  model={v.embedding_model}"
        )


# ---------------------------------------------------------------------------
# cacten versions set-active
# ---------------------------------------------------------------------------


@versions_app.command("set-active")
def versions_set_active(
    version_id: Annotated[str, typer.Argument(help="Version ID or prefix to activate.")],
) -> None:
    """Set the active KB version."""
    from cacten import config
    from cacten.versions import list_versions

    all_versions = list_versions()
    match = next(
        (v for v in all_versions if v.version_id.startswith(version_id)),
        None,
    )
    if match is None:
        typer.echo(f"Version not found: {version_id!r}", err=True)
        raise typer.Exit(1)

    config.set_active_version_id(match.version_id)
    typer.echo(f"Active version set to v{match.version_number} ({match.version_id[:8]})")


# ---------------------------------------------------------------------------
# cacten versions delete
# ---------------------------------------------------------------------------


@versions_app.command("delete")
def versions_delete(
    version_id: Annotated[str, typer.Argument(help="Version ID or prefix to delete.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Delete a KB version and its chunks from Qdrant."""
    from cacten import config
    from cacten.store import QdrantVectorStore
    from cacten.versions import delete_version, list_versions

    all_versions = list_versions()
    match = next(
        (v for v in all_versions if v.version_id.startswith(version_id)),
        None,
    )
    if match is None:
        typer.echo(f"Version not found: {version_id!r}", err=True)
        raise typer.Exit(1)

    if not yes:
        typer.confirm(
            f"Delete v{match.version_number} ({match.chunk_count} chunks)?",
            abort=True,
        )

    QdrantVectorStore().delete_version(match.version_id)
    delete_version(match.version_id)

    active_id = config.get_active_version_id()
    if active_id == match.version_id:
        remaining = [v for v in all_versions if v.version_id != match.version_id]
        if remaining:
            newest = max(remaining, key=lambda v: v.version_number)
            config.set_active_version_id(newest.version_id)
            typer.echo(f"Active version switched to v{newest.version_number}.")
        else:
            config.set_active_version_id("")
            typer.echo("No versions remain. KB is empty.")

    typer.echo(f"Deleted v{match.version_number}.")
