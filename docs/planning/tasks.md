# Tasks — Cacten

> Track design and build tasks. Update status as work progresses.
> Status: ⬜ Not started | 🔄 In progress | ✅ Done | ❌ Blocked

---

## Phase 0 — Design (Week 1: Mar 19–21)

| # | Task | Status | Notes |
|---|---|---|---|
| D-1 | Bootstrap design project (CLAUDE.md, README, .gitignore) | ✅ Done | |
| D-2 | Scaffold all design docs (requirements, systems-design, project-plan, brainstorm, tasks) | ✅ Done | |
| D-3 | Resolve Q1: Claude Code wrapper pattern | ✅ Done | MCP server (agentic RAG) Mar 19 |
| D-4 | Resolve Q2: vector store selection | ✅ Done | Qdrant (local path mode) — hybrid search required Mar 20 |
| D-5 | Resolve Q3: embedding model selection | ✅ Done | nomic-embed-text via Ollama Mar 19 |
| D-6 | Resolve Q4: chunking strategy | ✅ Done | Recursive character splitter, 512/64 Mar 19 |
| D-7 | Resolve Q5: KB versioning granularity | ✅ Done | Auto-version per ingest Mar 19 |
| D-8 | Resolve Q6: process model | ✅ Done | MCP daemon + in-process CLI Mar 19 |
| D-9 | Review research docs, validate and update systems-design.md | ✅ Done | DBSF fusion, FastMCP, reranker v2, RAGAS alignment Mar 20 |
| D-10 | Add US-12 (end-to-end personalization + ACs) to requirements.md | ✅ Done | Mar 20 |
| D-11 | Finalize tasks.md | ✅ Done | Mar 20 |
| D-12 | Resolve Q7: Eval Studio schema alignment | ⬜ Not started | Partially resolved via RAGAS; needs Eval Studio schema review |

---

## Phase 1 — Foundation (Week 2: Mar 23–28)

| # | Task | Status | Notes |
|---|---|---|---|
| F-1 | Init project with uv, configure ruff + mypy strict | ✅ Done | |
| F-2 | Typer CLI scaffolding (`cacten` entrypoint, help text) | ✅ Done | |
| F-3 | Qdrant client setup + collection creation (768-dim dense + sparse) | ✅ Done | Local path mode, no Docker |
| F-4 | Ollama embedding client (`nomic-embed-text`, 768-dim) | ✅ Done | Fail fast if Ollama unreachable |
| F-5 | Sparse vector (BM25) generation for hybrid search | ✅ Done | |
| F-6 | Document loader: markdown + PDF | ✅ Done | pypdf for PDF |
| F-7 | URL fetcher + HTML-to-text parser | ✅ Done | httpx + html parser |
| F-8 | Recursive character splitter pipeline (512/64) | ✅ Done | langchain_text_splitters |
| F-9 | Chunk + embed + upsert pipeline (dense + sparse) | ✅ Done | |
| F-10 | KB version management (create, list, set-active, delete) | ✅ Done | versions.json registry |
| F-11 | `cacten ingest` command | ✅ Done | Accepts file path or URL |
| F-12 | `cacten versions` command (list, set-active, delete) | ✅ Done | |
| F-13 | `cacten retrieve` command (debug/test use) | ✅ Done | Raw chunk output, not generation |
| F-14 | VectorStore protocol + QdrantVectorStore implementation | ✅ Done | Swappable interface |
| F-15 | Tests for ingestion + retrieval core paths | ✅ Done | |

---

## Phase 2 — MCP Server (Week 3: Mar 30 – Apr 4)

| # | Task | Status | Notes |
|---|---|---|---|
| M-1 | FastMCP server setup (`cacten serve` command) | ✅ Done | stdio transport, local |
| M-2 | Hybrid search retrieval (DBSF fusion, dense + sparse) | ✅ Done | Scoped to active KB version |
| M-3 | Context block formatter (ranked chunks → `<cacten_context>`) | ✅ Done | |
| M-4 | `search_personal_kb` MCP tool | ✅ Done | Returns chunks, not generated answer |
| M-5 | `personal_context` MCP resource | ✅ Done | Session-start identity injection |
| M-6 | `.mcp.json` config + setup documentation | ✅ Done | Project-scoped and user-scoped variants |
| M-7 | Session logging (`~/.cacten/logs/sessions/`) | ✅ Done | SessionLog schema from systems-design.md |
| M-8 | `--verbose` flag (show injected chunks on retrieve) | ✅ Done | |
| M-9 | Graceful degradation if Ollama unreachable at startup | ✅ Done | Clear error message |
| M-10 | Passthrough mode (bypass RAG augmentation) | ✅ Done | US-10 |
| M-11 | End-to-end test: ingest → serve → retrieve via MCP | ✅ Done | US-12 validation |

---

## Phase 3 — Polish (Apr 6–10)

| # | Task | Status | Notes |
|---|---|---|---|
| P-1 | End-to-end demo script (ingest → serve → ask → export) | ✅ Done | Removed from v1 scope; no longer tracked as a v1 deliverable. |
| P-2 | README polish (value prop, setup, prerequisites, demo) | ✅ Done | README rewritten and updated to match the current system. |
| P-3 | CLI help text audit (all commands) | ✅ Done | Current CLI surface and docs reviewed together during polish pass. |
| P-4 | Ingest performance pass | ✅ Done | Profiled large-corpus ingest; Ollama embedding is the main bottleneck. Batched embedding + streamed upserts landed, and follow-up optimizations are documented. |
| P-5 | Incremental ingest | ✅ Done | File hashes, per-version file manifests, unchanged-file reuse, and sparse encoder version invalidation implemented. |
| P-6 | Cross-encoder reranker | ✅ Done | FastEmbed/ONNX reranker integrated after hybrid retrieval with fallback behavior. |
| P-7 | mypy strict pass — clean across all modules | ✅ Done | `uv run mypy src` passes cleanly. |
| P-8 | Final test coverage pass | ✅ Done | `uv run pytest` passes; core ingestion, retrieval, rerank, versions, and store paths covered. |
| P-9 | Design docs final review | ✅ Done | Architecture and systems design docs refreshed and aligned with the implementation. |
| P-10 | Git repo init + initial push | ✅ Done | |

---

## Phase 4 — Eval Integration (Apr 13–17)

| # | Task | Status | Notes |
|---|---|---|---|
| E-1 | Resolve Q7: validate SessionLog schema against Eval Studio ingestion contract | ⬜ Not started | Must be done before E-2 |
| E-2 | `cacten evals export` command (session logs → JSON array for jt-eval-kit) | ⬜ Not started | `--output`, `--since`, `--kb-version`, `--limit` flags |
| E-3 | Eval Studio ingestion smoke test | ⬜ Not started | End-to-end validation |
| E-4 | Document eval workflow in README | ⬜ Not started | ingest → ask → export → eval |

---

## Backlog (Post-v1)

| # | Task | Notes |
|---|---|---|
| BL-1 | Reranker quality tuning | FastEmbed/ONNX reranker is implemented; tune candidate count/model choice with evals. |
| BL-2 | Contextual Retrieval (Anthropic, 2025) | LLM-prepended context summaries per chunk before embedding — one of the highest-ROI v2 upgrades |
| BL-3 | HyDE query expansion | Generate hypothetical answer, embed it, use for retrieval — strong fit for short/vague dev queries |
| BL-4 | Content-type chunking routing | PDFs → page-level, code → function-aware, markdown → structure-aware |
| BL-5 | HTTP MCP transport | Switch from stdio for shared/remote use or web UI |
| BL-6 | VS Code plugin | Wraps the CLI |
| BL-7 | GitHub repo ingestion | Direct repo ingest without manual file upload |
| BL-8 | Source-document-level erasure | `cacten ingest remove ./doc.md --rebuild-version` |
| BL-9 | Web UI for KB management | Ingestion history, version browser |
| BL-10 | Multi-developer support | Isolated KBs per developer |
| BL-11 | Medium article — Cacten | Write after v1 ships |
