# Cacten

Local-first RAG middleware for Claude Code. Ingest your own documents into a versioned knowledge base; Cacten runs as an MCP server and returns relevant context chunks on demand — Claude does all generation.

**Stack:** Python 3.12 · Qdrant (local) · FastMCP · `nomic-embed-text` via Ollama · Pydantic v2 · Typer · uv

→ [Systems Design](docs/systems-design.md) · [Requirements](docs/requirements.md)

---

## Why

- **Local-first** — no cloud dependency, no API keys, all data in `~/.cacten/`
- **Versioned KB** — every ingestion creates a new snapshot; roll back or compare across versions
- **MCP-native** — Claude Code calls `search_personal_kb` on demand; Cacten retrieves, Claude generates

---

## Quickstart

```bash
# 1. Install
git clone <repo> && cd cacten
uv tool install .

# 2. Pull the embedding model
ollama pull nomic-embed-text

# 3. Ingest a document
cacten ingest ./my-notes.md

# 4. In one terminal: start Ollama
ollama serve

# 5. In a second terminal: start the MCP server
cacten serve
```

See [MCP Setup](#mcp-setup) below for how to wire this into Claude Code.

---

## Example workflow

```bash
# Ingest your architecture decisions and coding notes
cacten ingest ./docs/architecture.md --notes "system design v2"
cacten ingest ./docs/style-guide.md

# Smoke test retrieval before starting a session
cacten retrieve "preferred error handling pattern" --verbose

# Start the server — Claude Code picks it up via .mcp.json
cacten serve
```

Ask Claude Code something that touches your ingested content. The `--verbose` flag on `cacten retrieve` shows the exact `<cacten_context>` block Claude receives.

---

## MCP Setup

Cacten runs as a local MCP server. You register it once and Claude Code calls it automatically on relevant queries — no manual prompting needed.

### Option A — Project-scoped (recommended for per-project KBs)

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "cacten": {
      "command": "cacten",
      "args": ["serve"],
      "transport": "stdio"
    }
  }
}
```

### Option B — Global (works across all projects)

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "cacten": {
      "command": "cacten",
      "args": ["serve"],
      "transport": "stdio"
    }
  }
}
```

### Claude Code CLI

You can also register it directly from the terminal without editing JSON:

```bash
# Add globally
claude mcp add cacten cacten serve

# Or scoped to the current project
claude mcp add --scope project cacten cacten serve

# Verify it's registered
claude mcp list
```

Once registered, Claude Code starts the server automatically and calls `search_personal_kb` when your KB context is relevant. No `cacten serve` needed in a separate terminal.

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) running locally (`ollama serve`)

---

## CLI reference

### Ingest

```bash
cacten ingest ./path/to/doc.md
cacten ingest ./paper.pdf
cacten ingest https://example.com/some-page
cacten ingest ./doc.md --notes "Q1 architecture decisions"
```

### Serve

```bash
cacten serve
cacten serve --passthrough   # bypass RAG, return empty context for all queries
```

### Retrieve (debug / smoke test)

```bash
cacten retrieve "how do we handle auth?"
cacten retrieve "deployment strategy" --top-k 5 --verbose
```

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
    └── sessions/        # structured session logs for later eval export
```

---

## Development

```bash
uv run pytest                                        # run tests
uv run pytest --cov --cov-report=term-missing        # run tests with coverage
uv run ruff check src/                               # lint
uv run mypy src/                                     # type check
```

---

## Roadmap

- `cacten export` — session log export for RAGAS eval pipelines
- Reranker (cross-encoder), HyDE query expansion, contextual retrieval
- VS Code plugin, GitHub repo ingestion
