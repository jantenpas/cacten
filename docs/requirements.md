# Cacten — Requirements

## Product Vision

Cacten is a personalized RAG middleware layer that wraps Claude Code. It enriches every developer interaction with context from their own knowledge base — built from documents, repos, and decisions they have explicitly ingested.

The experience is: you talk to your AI agent, and it already knows who you are.

---

## User

**Primary user:** Jan (solo developer, portfolio context). The UX is designed for a single developer using Cacten as their personal co-pilot.

**Secondary consideration:** The architecture should be personal-scale but not single-user-hardcoded. A future v2 could serve multiple users.

---

## v1 Scope

### In Scope

- CLI interface for all developer interactions
- Ingestion pipeline: ingest documents (markdown, PDF) from local file path or URL
- Versioned knowledge base: each ingestion creates a new KB version
- RAG retrieval: query KB and retrieve relevant context chunks
- MCP server exposing retrieval as tools/resources; Claude Code is the client
- KB management: list versions, view ingestion history, set active version
- Basic eval hook: structured output format compatible with Eval Studio ingestion

### Explicitly Out of Scope (v1)

- GitHub integration (direct repo ingestion)
- VS Code plugin
- Web UI / dashboard
- Fine-tuning
- Multi-user support
- Streaming responses
- Agent plugins beyond Claude Code
- Automatic re-ingestion / sync
- Semantic deduplication across ingestion runs

---

## User Stories

### Ingestion

**US-01:** As a developer, I can ingest a local markdown or PDF file into my knowledge base, so that future Claude Code sessions have access to its content.

**US-02:** As a developer, I can ingest a document from a URL, so that I don't have to download files manually before ingesting them.

**US-03:** As a developer, each ingestion creates a new versioned snapshot of my KB, so that I can track how my co-pilot's knowledge has evolved.

**US-04:** As a developer, I can view my ingestion history (date, source, version number, document count), so that I understand what my KB contains.

### KB Management

**US-05:** As a developer, I can list all KB versions, so that I can choose which version is active.

**US-06:** As a developer, I can set a specific KB version as active, so that I control which knowledge state is used during retrieval.

**US-07:** As a developer, I can delete a KB version, so that I can remove stale or incorrect knowledge.

### Retrieval & Augmentation

**US-08:** As a developer, when Claude Code calls the `search_personal_kb` MCP tool, my query is automatically enriched with relevant context from my active KB.

**US-09:** As a developer, I can see which context chunks were injected into my last request (debug/verbose mode), so that I can understand why Cacten responded the way it did.

**US-10:** As a developer, I can make a request that bypasses RAG augmentation (passthrough mode), so that I can compare augmented vs. unaugmented responses.

### Eval Integration

**US-11:** As a developer, I can export a structured log of a Cacten session (input, retrieved context, augmented prompt, response), so that I can run quality evals in Eval Studio.

### End-to-End Personalization

**US-12:** As a developer, when I ask Claude Code to start a new project, it produces scaffolding, code style, and architectural decisions that match my existing work — without me having to describe my preferences — so that I spend less time correcting AI output and more time building.

**AC-1 — Style consistency:** Given a KB containing at least one of Jan's existing projects, Claude Code produces code that matches the observed formatting conventions (naming, structure, file layout) without explicit instruction.

**AC-2 — Architectural grounding:** Claude Code references or applies decisions documented in the KB (e.g., preferred stack choices, error handling patterns) when asked to design a new system.

**AC-3 — No hallucinated authority:** Cacten does not invent preferences or decisions not present in the KB. If relevant context is absent, Claude Code's response is indistinguishable from a passthrough (US-10) — it does not fabricate grounding.

**AC-4 — Measurable delta:** A side-by-side comparison of augmented vs. passthrough (US-10) responses shows a meaningful difference when the KB contains relevant content. This difference is the core eval signal fed to Eval Studio (US-11).

---

## Acceptance Criteria Notes

- All CLI commands must have `--help` output
- Ingestion must handle files up to 50MB without hanging
- Retrieval latency should be under 2 seconds for a local vector store at personal scale (<10k documents)
- KB versioning must be append-only — no in-place mutation of existing versions
- Eval export format must be documented and stable

---

## v2 Considerations

- VS Code plugin wrapping the CLI
- GitHub repo ingestion
- Web UI for KB management and ingestion history visualization
- Fine-tuning pipeline for style/tone consistency (documented tradeoff: cost vs. personalization depth)
- Multi-developer support with isolated KBs
- Automatic re-ingestion on document change
- Source-document-level erasure (`cacten ingest remove ./doc.md --rebuild-version`) — v1 only supports version-level deletion; source-level removal requires rebuilding the version without the target document
