"""Cacten CLI — ingest, retrieve, versions."""

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
    source: Annotated[str, typer.Argument(help="File path (.md, .pdf) or URL to ingest.")],
    notes: Annotated[str | None, typer.Option("--notes", "-n", help="Optional annotation.")] = None,
) -> None:
    """Ingest a document into the personal knowledge base."""
    from cacten.embeddings import check_ollama
    from cacten.pipeline import ingest as _ingest

    typer.echo("Checking Ollama...")
    try:
        check_ollama()
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e

    typer.echo(f"Ingesting: {source}")
    try:
        version = _ingest(source, notes=notes)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e

    typer.echo(
        f"Done. KB version v{version.version_number} created "
        f"({version.chunk_count} chunks). Now active."
    )


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
