# Cacten

Personalized RAG middleware for Claude Code. Builds a searchable knowledge base from your own documents and injects relevant context into Claude Code sessions via MCP.

---

## How it works

```
cacten ingest ./doc.md      # chunk → embed → store in Qdrant
cacten serve                # start MCP server (Phase 2)
```

Claude Code calls the `search_personal_kb` MCP tool when a query would benefit from your personal KB. Cacten returns raw context chunks — Claude does all generation.

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) running locally

```bash
ollama pull nomic-embed-text
```

---

## Setup

```bash
git clone <repo>
cd cacten
uv sync
```

To use `cacten` as a global command without activating the venv:

```bash
uv tool install .
```

To uninstall: `uv tool uninstall cacten`

---

## CLI

### Start the MCP server

```bash
cacten serve
cacten serve --passthrough   # bypass RAG, return empty context for all queries
```

Copy `.mcp.json` to your project root (or `~/.claude/`) and Claude Code will connect automatically on startup.

### Ingest a document

```bash
cacten ingest ./path/to/doc.md
cacten ingest ./paper.pdf
cacten ingest https://example.com/some-page
cacten ingest ./doc.md --notes "Q1 architecture decisions"
```

### Retrieve (debug / smoke test)

```bash
cacten retrieve "how do we handle auth?"
cacten retrieve "deployment strategy" --top-k 5 --verbose
```

`--verbose` prints the full `<cacten_context>` block as Claude Code would see it.

### Manage KB versions

```bash
cacten versions list
cacten versions set-active <version-id-prefix>
cacten versions delete <version-id-prefix>
```

Every ingestion creates a new version and activates it automatically.

---

## Data storage

All data lives in `~/.cacten/`:

```
~/.cacten/
├── config.json          # active kb_version_id
├── kb/
│   ├── versions.json    # version registry
│   └── qdrant/          # Qdrant local storage (no Docker needed)
└── logs/
    └── sessions/        # eval export logs (Phase 3)
```

---

## Development

```bash
uv run pytest            # run tests
uv run ruff check src/   # lint
uv run mypy src/         # type check
```

---

## Roadmap

- **Phase 3** — `cacten export` for RAGAS-compatible eval output
- **Backlog** — reranker, HyDE query expansion, contextual retrieval, VS Code plugin
