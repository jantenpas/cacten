# Cacten

Local-first RAG middleware for Claude Code. Ingest your own documents into a versioned knowledge base; Cacten runs as an MCP server and returns relevant context chunks on demand — Claude does all generation.

**Stack:** Python 3.12 · Qdrant (local) · FastMCP · `nomic-embed-text` via Ollama · Pydantic v2 · Typer · uv

→ [Systems Design](docs/systems-design.md) · [Requirements](docs/requirements.md)

---

## Why

- **Local-first** — no cloud dependency, no API keys; KB data lives in `~/.cacten/`, project manifest files in `.cacten/`
- **Versioned KB** — every ingestion creates a new snapshot; roll back or compare across versions
- **MCP-native** — Claude Code calls `search_personal_kb` on demand; Cacten retrieves, Claude generates
- **Project-local manifest** — define your corpus once in `.cacten/sources.toml`, ingest with one command
- **Cacten Test 2248669** - Because it sounds like Cactus, and Cactus' are really cool! 

---

## Quickstart

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com/)

```bash
# 1. Install
git clone <repo> && cd cacten
uv tool install .

# 2. Pull the embedding model
ollama pull nomic-embed-text

# 3. Initialize a manifest for your project
cacten init

# 4. Preview what will be ingested
cacten ingest --dry-run

# 5. Ingest your corpus
cacten ingest --label "initial ingest"
```

See [MCP Setup](#mcp-setup) to wire Cacten into Claude Code.

---

## Ingestion workflow

### Manifest-based (recommended)

Define your corpus once, re-run with one command.

```bash
cacten init                                    # creates .cacten/sources.toml from the example
cacten ingest --dry-run                        # preview resolved files without ingesting
cacten ingest                                  # ingest all resolved files as one KB version
cacten ingest --label "post-refactor refresh"  # same, with a human-friendly label
```

`sources.toml` uses glob patterns:

```toml
version = 1

include = [
  "./README.md",
  "./docs/**/*.md",
  "./src/**/*.py",
]

exclude = [
  "**/.venv/**",
  "**/__pycache__/**",
]
```

**One ingest run = one KB version.** Every run snapshots the manifest to `.cacten/manifest-history/` for provenance.

`.cacten/sources.toml` is gitignored. Commit `.cacten/sources-example.toml` as the project template — `cacten init` copies it.

### Ad hoc (one-off files, URLs, directories)

```bash
cacten ingest ./my-notes.md
cacten ingest ./paper.pdf
cacten ingest https://example.com/some-page
cacten ingest ./docs/
```

---

## MCP Setup

Cacten runs as a local MCP server. Register it once and Claude Code calls it automatically on relevant queries.

### Option A — Project-scoped (recommended)

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

### Option C — Claude Code CLI

```bash
claude mcp add cacten cacten serve              # global
claude mcp add --scope project cacten cacten serve  # project-scoped
claude mcp list                                 # verify
```

Once registered, Claude Code starts the server automatically and calls `search_personal_kb` when your KB context is relevant.

---

## CLI reference

### `cacten init`

Initialize `.cacten/sources.toml` for this project from the example template.

```bash
cacten init
```

### `cacten ingest`

```bash
cacten ingest                                  # manifest-based: reads .cacten/sources.toml
cacten ingest --dry-run                        # preview resolved files, no KB write
cacten ingest --label "my label"               # manifest ingest with a version label
cacten ingest ./doc.md ./paper.pdf             # ad hoc: specific files
cacten ingest https://example.com/page         # ad hoc: URL
cacten ingest ./docs/ --ext .md,.py            # ad hoc: directory with extension filter
```

### `cacten serve`

```bash
cacten serve                    # start MCP server (stdio transport)
cacten serve --passthrough      # bypass RAG, return empty context for all queries
```

### `cacten retrieve`

Smoke-test retrieval without starting a full MCP session.

```bash
cacten retrieve "preferred error handling pattern"
cacten retrieve "deployment strategy" --top-k 5 --verbose
```

`--verbose` prints the full `<cacten_context>` block Claude would receive.

### `cacten versions`

```bash
cacten versions list
cacten versions set-active <version-id-prefix>
cacten versions delete <version-id-prefix> --yes
```

Every ingestion creates a new version and activates it automatically.

---

## Data storage

```
~/.cacten/
├── config.json             # active kb_version_id
├── kb/
│   ├── versions.json       # version registry with manifest provenance
│   └── qdrant/             # Qdrant local storage (no Docker needed)
└── logs/
    └── sessions/           # structured session logs for eval export

.cacten/                    # project-local (gitignored except the example)
├── sources.toml            # live manifest — gitignored
├── sources-example.toml    # committed template
└── manifest-history/       # immutable snapshots of each ingest run
```

---

## Development

```bash
uv run pytest                                        # run tests
uv run pytest --cov --cov-report=term-missing        # with coverage
uv run ruff check src/                               # lint
uv run mypy src/                                     # type check
```

---

## Roadmap

- `cacten evals export` — session log export for RAGAS eval pipelines
- Reranker (FastEmbed/ONNX cross-encoder), HyDE query expansion, contextual retrieval
- VS Code plugin, GitHub repo ingestion
