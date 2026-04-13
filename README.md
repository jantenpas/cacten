# Cacten

Local-first RAG middleware for MCP-compatible coding agents and assistants.

Cacten ingests your project documents into a versioned knowledge base, retrieves relevant context with hybrid search plus reranking, and serves that context over MCP. Your agent or client still does the reasoning and answer generation; Cacten focuses on retrieval quality, provenance, and local control.

[Architecture](docs/architecture.md) · [Systems Design](docs/systems-design.md) · [Requirements](docs/requirements.md)

---

## Why Cacten

- Local-first: knowledge-base data stays on your machine under `~/.cacten/`
- MCP-native: any compatible MCP client can request context on demand instead of relying on copy-paste workflows
- Versioned: every ingest creates a new KB snapshot you can inspect, switch, or delete
- Repeatable: a project-local manifest makes corpus refreshes one command instead of a manual ritual
- Practical quality stack: dense embeddings, sparse retrieval, DBSF fusion, and cross-encoder reranking

---

## What It Does Today

- Ingests markdown, PDFs, source code, text files, HTML, CSS, JSON, and HTTPS URLs
- Supports project-local manifest ingest and ad hoc ingest
- Reuses unchanged files during repeated manifest ingests
- Stores all chunks in a local Qdrant collection scoped by KB version
- Exposes retrieval through a FastMCP server for any MCP-compatible client
- Logs retrieval sessions for future eval export workflows

---

## How It Works

```text
files / URLs
  → load and split by content type
  → dense embed with Ollama
  → sparse encode with BM25
  → upsert into versioned local Qdrant storage

agent query
  → search_personal_kb
  → hybrid retrieval
  → rerank top candidates
  → return <cacten_context>
```

If you want the short architecture summary, start with [docs/architecture.md](docs/architecture.md). If you want the fuller design reference, use [docs/systems-design.md](docs/systems-design.md).

---

## Quickstart

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/)
- an MCP-compatible client such as Claude Code

### Install

```bash
git clone <repo-url>
cd cacten
uv tool install .
ollama pull nomic-embed-text
```

### Initialize And Ingest

```bash
cacten init
cacten ingest --dry-run
cacten ingest --label "initial ingest"
```

`cacten init` creates `.cacten/sources.toml` from the committed example manifest. `cacten ingest --dry-run` lets you inspect the resolved corpus before writing anything to the KB.

Manifest-based ingest is the recommended workflow because it is versioned, repeatable, and supports incremental reuse of unchanged files.

---

## MCP Setup

Configure any MCP-compatible client to launch:

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

If your client supports project-local MCP config, this is usually the cleanest option.

### Claude Code example

Project-scoped setup:

```bash
claude mcp add --scope project cacten cacten serve
```

Global setup:

```bash
claude mcp add cacten cacten serve
```

Verify:

```bash
claude mcp list
```

Once registered, your MCP client can call `search_personal_kb` automatically when a question would benefit from project context.

---

## Manifest Workflow

The manifest lives in `.cacten/sources.toml` and uses include/exclude glob patterns.

Example:

```toml
version = 1

include = [
  "./README.md",
  "./docs/**/*.md",
  "./src/**/*.py",
]

exclude = [
  "**/.git/**",
  "**/.venv/**",
  "**/node_modules/**",
  "**/__pycache__/**",
]
```

Recommended loop:

```bash
cacten ingest --dry-run
cacten ingest --label "post-refactor refresh"
cacten versions list
```

For manifest ingests, Cacten also:

- snapshots the live manifest into `.cacten/manifest-history/`
- records per-file metadata for incremental reuse
- creates one immutable KB version per run

---

## CLI

### `cacten init`

Create `.cacten/sources.toml` from `.cacten/sources-example.toml`.

```bash
cacten init
```

### `cacten ingest`

Manifest-based ingest:

```bash
cacten ingest
cacten ingest --dry-run
cacten ingest --label "my label"
```

Ad hoc ingest:

```bash
cacten ingest ./notes.md
cacten ingest ./paper.pdf
cacten ingest https://example.com/page
cacten ingest ./docs --ext .md,.py
```

### `cacten serve`

Start the local MCP server:

```bash
cacten serve
```

Passthrough mode for side-by-side comparison:

```bash
cacten serve --passthrough
```

### `cacten retrieve`

Smoke-test retrieval without starting an MCP client:

```bash
cacten retrieve "How does manifest ingest work?"
cacten retrieve "How does versioning work?" --top-k 5 --verbose
```

### `cacten versions`

```bash
cacten versions list
cacten versions set-active <version-id-prefix>
cacten versions delete <version-id-prefix> --yes
```

---

## Data Layout

User-level storage:

```text
~/.cacten/
├── config.json
├── kb/
│   ├── qdrant/
│   ├── versions.json
│   └── version-files/
└── logs/
    └── sessions/
```

Project-level files:

```text
.cacten/
├── sources.toml
├── sources-example.toml
└── manifest-history/
```

---

## Technical Notes

- Qdrant runs in local path mode; Docker is not required
- Dense embeddings use `nomic-embed-text` through Ollama
- Sparse retrieval uses a BM25-style encoder
- Hybrid results are fused with DBSF
- Final ranking uses a FastEmbed cross-encoder reranker
- Reranking falls back gracefully to hybrid results if the reranker is unavailable

---

## Development

```bash
uv run pytest
uv run ruff check src
uv run mypy src
```

The repository is configured for strict typing with mypy and is covered by tests across ingestion, retrieval, reranking, versions, and MCP behavior.
