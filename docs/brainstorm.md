# Cacten — Brainstorm

---

## Open Questions

Questions are ordered by how much they block other decisions.

---

### Q7 — Eval Studio integration interface (BLOCKS session log design)

**Question:** What does Eval Studio expect as input? The session log format in `systems-design.md` is a placeholder — it needs to match Eval Studio's actual ingestion schema.

**Partially resolved:** RAGAS is the standard RAG evaluation framework. The `SessionLog` schema in `systems-design.md` is now designed to map to RAGAS metrics (faithfulness, answer_relevancy, context_precision, context_recall). Final validation against Eval Studio's actual ingestion contract required before Phase 3 begins.

**Action needed:** Review Eval Studio's input schema and confirm the `SessionLog` fields match exactly.

---

## Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-03-19 | RAG over fine-tuning | Faster iteration, no training pipeline, knowledge is versioned not baked in |
| 2026-03-19 | CLI first, VS Code v2 | Faster to build, easier to demo, aligns with portfolio timeline |
| 2026-03-19 | No GitHub integration in v1 | Scope control — user uploads what they want ingested |
| 2026-03-19 | Versioned KB (append-only) | Enables cross-version evals via Eval Studio; traceability is a first-class feature |
| 2026-03-19 | Python 3.12, Pydantic v2 | Inherits Jan's existing stack; consistency across portfolio projects |
| 2026-03-19 | claude-sonnet-4-6 as default model | Current best Claude model; matches Eval Studio's stack |
| 2026-03-19 | Cacten is an MCP server (agentic RAG) | Claude Code is the client, stays untouched; composable and portable; aligns with the MCP ecosystem. Exposes a **tool** for on-demand retrieval and a **resource** for session-start context injection. Naming of tool/resource is open (e.g., `cacten_search_kb`, `cacten_personal_context`) — keep flexible until implementation. |
| 2026-03-20 | Vector store: Qdrant (local) | Hybrid search (dense + sparse) is required — ChromaDB only supports dense. Qdrant has native hybrid search, local embedded mode, and is the modern OSS standard. `VectorStore` protocol retained for portability. |
| 2026-03-19 | Embeddings: `nomic-embed-text` via Ollama | Better quality than MiniLM on technical content; Ollama has strong MCP integrations with Claude Code; free, local, no API dependency. Model name stored in KB version metadata — cross-version comparisons invalid if model changes. |
| 2026-03-19 | Chunking: recursive character splitter | Good default for markdown-heavy content; respects document structure. Fixed-size chunking is the documented fallback; semantic chunking is a v2 quality improvement. |
| 2026-03-19 | KB versioning: auto-version per ingest | Every document ingestion creates a new version automatically. No staging/commit step in v1 — minimal friction, maximum traceability. |
| 2026-03-19 | Process model: MCP daemon + in-process CLI | `cacten serve` runs as the MCP daemon (retrieval). Ingestion and KB management commands (`ingest`, `versions`) run in-process via CLI — no separate server needed for those. FastAPI is not needed in v1. |
| 2026-03-20 | MCP tool returns chunks, not generated answers | `search_personal_kb` returns raw context chunks — Claude Code does all generation. Having Cacten call an LLM would double cost and strip Claude Code's ability to reason over raw context. |
| 2026-03-20 | Hybrid fusion: DBSF (Qdrant native) | Qdrant's DBSF (Distribution-Based Score Fusion) is score-aware normalization; better suited than RRF when retriever confidence varies. Default to DBSF; RRF is the documented fallback. |
| 2026-03-20 | MCP library: FastMCP | `mcp.server.fastmcp.FastMCP` is the standard Python library for MCP servers. Validated by research (08-build-rag-mcp-client.md). |
| 2026-03-20 | Session log aligned to RAGAS metrics | `SessionLog` schema maps to RAGAS: faithfulness, answer_relevancy, context_precision, context_recall. Final validation against Eval Studio schema required before Phase 3. |
