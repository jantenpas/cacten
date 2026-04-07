# Cacten — Project Plan

> Target: End of March / early April 2026. Running alongside Eval Studio completion.

---

## Phases

### Phase 0 — Architecture & Design
**Goal:** Resolve all blocking open questions before writing code. Produce stable `systems-design.md`, `requirements.md`, and `tasks.md`.

**Milestone:** All blocking open questions resolved. Q7 (Eval Studio schema) is partially resolved and does not block Phase 1–2; it blocks Phase 3 only.

**Tasks:**
- [x] Resolve Q1: Claude Code wrapper pattern (CLI passthrough vs SDK vs MCP)
- [x] Resolve Q2: Vector store selection
- [x] Resolve Q3: Embedding model selection
- [x] Resolve Q4: Chunking strategy
- [x] Resolve Q5: KB versioning granularity
- [x] Resolve Q6: In-process vs FastAPI daemon
- [ ] Resolve Q7: Eval Studio session log schema
- [x] Finalize data storage layout (`~/.cacten/` structure)
- [x] Finalize `tasks.md` with Phase 1–4 breakdown

---

### Phase 1 — Foundation ✅
**Goal:** Project scaffolding, ingestion pipeline, and vector store working end-to-end. Can ingest a markdown file and retrieve relevant chunks.

**Milestone:** `cacten ingest ./my-doc.md` works. `cacten retrieve "what is my preferred Python style?"` returns relevant chunks.

**Tasks:**
- [x] Initialize project with uv, ruff, mypy strict
- [x] CLI scaffolding with Typer (`cacten` entrypoint)
- [x] Document loader: markdown + PDF
- [x] URL fetcher + HTML-to-text parser
- [x] Chunking pipeline
- [x] Embedding generation
- [x] Vector store setup (Qdrant — local path mode)
- [x] KB version management (create, list, set active)
- [x] `ingest` command
- [x] `versions` command (list, set-active, delete)
- [x] `retrieve` command (debug/test use)

---

### Phase 2 — MCP Server ✅
**Goal:** Cacten exposes retrieval as an MCP server. Claude Code calls it on-demand via the `search_personal_kb` tool and `personal_context` resource.

**Milestone:** `cacten serve` starts the MCP server. Claude Code retrieves personal KB context automatically on relevant queries.

**Tasks:**
- [x] FastMCP server setup (`cacten serve` command, stdio transport)
- [x] Hybrid search retrieval (DBSF fusion, dense + sparse)
- [x] Context block formatter (ranked chunks → `<cacten_context>`)
- [x] `search_personal_kb` MCP tool
- [x] `personal_context` MCP resource
- [x] `.mcp.json` config
- [x] Session logging to `~/.cacten/logs/sessions/`
- [x] `--passthrough` flag (bypass RAG augmentation)
- [x] `--verbose` flag showing injected context chunks
- [x] Graceful degradation if Ollama unreachable
- [x] End-to-end test: ingest → serve → retrieve via MCP

---

### Phase 3 — Eval Integration
**Goal:** Session logs are exportable in a format compatible with Eval Studio. Cross-version quality measurement is possible.

**Milestone:** A session log exported from Cacten can be ingested into Eval Studio and used to run evals.

**Tasks:**
- [ ] Finalize `SessionLog` schema against Eval Studio input format
- [ ] `cacten evals export` command: export session logs as jt-eval-kit JSON array
- [ ] `cacten evals` subcommand group (extensible for future `list`, `run`)
- [ ] Document eval workflow in README

---

### Phase 4 — Polish & Portfolio Prep
**Goal:** Project is demo-ready and portfolio-quality. README is compelling. Code is clean. CLI UX is polished.

**Milestone:** Cacten is publicly shareable as a portfolio artifact.

**Tasks:**
- [ ] End-to-end demo script (ingest → ask → eval)
- [ ] README polish: clear value prop, setup instructions, demo GIF or screenshot
- [ ] Error messages and help text audit
- [ ] Ingest performance pass: profile large-corpus ingest, identify embedding/upsert bottlenecks, and document follow-up optimizations
- [ ] Type coverage: mypy strict passes cleanly
- [ ] Test coverage: core ingestion and retrieval paths
- [ ] CLAUDE.md and design docs final review
- [ ] Git repo setup and initial push

---

## Planned Ingest UX

Project-local manifest workflow:

```bash
cacten init
cacten ingest --dry-run
cacten ingest --label "post-refactor corpus refresh"
```

If `.cacten/sources.toml` is missing, `cacten ingest` should generate it from `.cacten/sources-example.toml` and print `No sources.toml found. Generating from the sample file`.

Ad hoc testing workflow:

```bash
cacten ingest ./docs ./tests/test_pipeline.py
```

In the planned manifest flow, one ingest run produces one KB version, and `--label` gives that version a human-friendly note for later inspection.

---

## Timeline Estimate

| Phase | Target |
|---|---|
| Phase 0 | Week of 2026-03-19 |
| Phase 1 | Week of 2026-03-23 |
| Phase 2 | Week of 2026-03-30 |
| Phase 3 | Week of 2026-04-06 |
| Phase 4 | Week of 2026-04-06 (parallel with Phase 3) |

---

## Risks

| Risk | Mitigation |
|---|---|
| Claude Code wrapper pattern is complex or unsupported | Resolve Q1 first; fall back to SDK-direct if needed |
| Retrieval quality is poor on first implementation | Start simple, measure with Eval Studio, iterate |
| Scope creep from v2 features | Ruthlessly defer anything not in the v1 scope list |
| Eval Studio schema mismatch | Resolve Q7 before Phase 3 begins |
