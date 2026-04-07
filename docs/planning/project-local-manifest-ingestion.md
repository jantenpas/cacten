# Project-Local Manifest Ingestion — Design & Implementation Plan

> Design doc for a simpler, project-first ingestion workflow.
> Goal: make `cacten ingest` feel effortless while preserving strong provenance for RAG and evals.

---

## Motivation

The current ingestion flow is functional, but it is still too close to the implementation:

- users have to think in terms of ad hoc file paths
- directory ingestion currently creates one KB version per file
- there is no first-class way to define "the corpus for this project"
- there is no durable history of the manifest used for a given ingest run

For Cacten to feel like a serious RAG system instead of a file loader, ingestion needs to be:

1. **Project-local** — configuration lives with the project
2. **Private by default** — real source lists stay out of public Git history
3. **Simple** — `cacten ingest` should work without extra flags
4. **Versioned** — every ingest run should preserve the exact manifest used
5. **Eval-friendly** — later we should be able to explain what source config produced a given KB version

Ad hoc path ingestion should remain supported for one-off tasks and testing, but the manifest flow becomes the primary project workflow.

---

## Core Decisions

### 1. Project-local manifest

The primary manifest lives at:

```text
.cacten/sources.toml
```

This is the file `cacten ingest` reads by default.

### 2. Project-local manifest history

Every ingest run snapshots the manifest into:

```text
.cacten/manifest-history/sources_<timestamp>.toml
```

This snapshot is immutable and is the source of truth for that ingest run.

### 3. Example manifest committed to Git

Projects should include:

```text
.cacten/sources-example.toml
```

This file is committed to the repo as documentation and a starter template.

### 4. Private local config stays out of Git

The real manifest and its history are ignored by Git:

```gitignore
.cacten/sources.toml
.cacten/manifest-history/
```

If needed, add an allowlist rule so the example stays committed:

```gitignore
.cacten/*
!.cacten/sources-example.toml
```

### 5. One ingest run = one KB version

This is the most important product rule.

If `cacten ingest` resolves 50 files from `.cacten/sources.toml`, that entire run produces one new KB version. A KB version represents a knowledge snapshot, not a single file event.

---

## User Experience

### Happy path

```bash
cacten init
cacten ingest --dry-run
cacten ingest
cacten ingest ./docs ./tests/test_pipeline.py
cacten ingest --label "post-refactor corpus refresh"
```

### Behavior

- `cacten init`
  creates `.cacten/sources.toml` from `.cacten/sources-example.toml` if needed
- `cacten ingest`
  automatically reads `.cacten/sources.toml`
  and bootstraps it from `.cacten/sources-example.toml` if the real manifest is missing
- `cacten ingest --dry-run`
  resolves files and shows what would be ingested without embedding or writing a KB version

### First-run experience

If `.cacten/sources.toml` does not exist:

1. if `.cacten/sources-example.toml` exists, Cacten generates `.cacten/sources.toml` from it
2. `cacten ingest` prints: `No sources.toml found. Generating from the sample file`
3. if `.cacten/sources-example.toml` also does not exist, Cacten raises a clear error

This keeps the workflow obvious and avoids hidden magic.

---

## Manifest Format

The v1 format should be intentionally simple and human-readable.

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

### Why this format

- flat structure is easier to understand than nested source objects
- `include` and `exclude` are familiar to developers
- glob patterns are expressive enough for the initial use case
- TOML is easy to edit and parse with Python standard library support

### Fields

| Field | Meaning |
|---|---|
| `version` | Required numbered version for the manifest |
| `include` | File paths or glob patterns to ingest |
| `exclude` | File paths or glob patterns to skip |

If `version` is missing, Cacten should raise a clear validation error.

### Explicitly deferred

The following are intentionally out of scope for the first version:

- named collections / groups
- per-path metadata tags
- per-source chunking policies
- change-only ingestion
- source priority weighting

These can be added later if the base workflow proves solid.

---

## Versioning Model

There are two separate histories:

### Manifest history

Tracks the configuration used to define the corpus.

Example:

```text
.cacten/manifest-history/sources_2026-04-07T10-14-32Z.toml
```

### KB history

Tracks the actual append-only knowledge base snapshots produced by ingestion.

Example:

- `v12` = snapshot produced from the manifest captured at `2026-04-07T10:14:32Z`

### Why both matter

- manifest history answers: "what did we try to ingest?"
- KB history answers: "what knowledge state did retrieval use?"

This separation is critical for debugging retrieval quality and for later eval export.

---

## Metadata Recorded Per KB Version

Each KB version created from a manifest-driven ingest should record:

- manifest path
- manifest snapshot path
- manifest hash
- manifest version
- ingest timestamp
- resolved file list
- file count
- chunk count
- optional notes / label

This gives Cacten strong provenance even when the live `sources.toml` changes later.

---

## CLI Design

### Commands

```bash
cacten init
cacten ingest
cacten ingest --dry-run
```

### Command semantics

#### `cacten init`

- creates `.cacten/` if missing
- writes `.cacten/sources.toml` from `.cacten/sources-example.toml`
- raises a clear error if `.cacten/sources-example.toml` does not exist
- does not overwrite an existing real manifest unless forced

#### `cacten ingest`

- if `.cacten/sources.toml` is missing and `.cacten/sources-example.toml` exists, generates the real manifest first
- prints `No sources.toml found. Generating from the sample file` when this bootstrap happens
- raises a clear error if neither file exists
- reads `.cacten/sources.toml`
- snapshots it to `.cacten/manifest-history/`
- resolves all matching files
- ingests them as one run
- creates one new KB version
- marks that version active
- supports `--label` for a human-friendly version note

Example:

```bash
cacten ingest --label "post-refactor corpus refresh"
```

#### `cacten ingest <paths...>`

- remains supported for ad hoc file, directory, or URL ingestion
- is especially useful for testing and one-off corpus experiments
- should continue to work without requiring a manifest

#### `cacten ingest --dry-run`

- reads `.cacten/sources.toml`
- resolves all matching files
- shows included files, skipped files, and summary counts
- does not snapshot the manifest
- does not create a KB version

---

## Output Design

The CLI should explain what happened in plain language.

Example:

```text
No sources.toml found. Generating from the sample file
Loaded manifest: .cacten/sources.toml
Saved snapshot: .cacten/manifest-history/sources_2026-04-07T10-14-32Z.toml
Resolved files: 47
Created KB version v14 (active)
Chunks created: 1382
```

This is much better DX than exposing internal ingestion mechanics.

---

## Implementation Notes

### Current behavior to change

Today, directory ingestion loops over files and creates one version per file. That behavior should be replaced for manifest-based ingest flows.

Desired behavior:

```text
many files resolved -> one ingest run -> one KB version
```

### Suggested implementation split

1. **Manifest loading**
   Parse `.cacten/sources.toml`, validate fields, normalize include/exclude patterns.
2. **File resolution**
   Expand glob patterns relative to project root, apply excludes, sort deterministically.
3. **Snapshotting**
   Save immutable manifest copy before ingestion begins.
4. **Batch ingestion**
   Build all chunks under a single `kb_version_id`.
5. **Version metadata**
   Persist manifest provenance alongside the KB version record.

---

## Files Affected

| File | Change |
|---|---|
| `src/cacten/cli.py` | Add `cacten init`; update `cacten ingest` to use project-local manifest |
| `src/cacten/pipeline.py` | Add manifest-driven batch ingest; change batch versioning semantics |
| `src/cacten/models.py` | Extend version metadata to store manifest provenance |
| `src/cacten/versions.py` | Persist manifest metadata with KB versions |
| `README.md` | Document project-local manifest workflow |
| `.gitignore` | Ignore live manifest and manifest-history, keep example committed |
| `.cacten/sources-example.toml` | Add committed template |
| `tests/test_cli.py` | Cover `init`, `dry-run`, and manifest ingest behavior |
| `tests/test_pipeline.py` | Cover batch ingest as one KB version |

---

## Tasks

| # | Task | Status |
|---|---|---|
| PM-1 | Add `.cacten/sources-example.toml` template | ✅ |
| PM-2 | Add `.gitignore` rules for `.cacten/sources.toml` and `.cacten/manifest-history/` | ✅ |
| PM-3 | Add manifest parser and validator | ✅ |
| PM-4 | Add deterministic glob resolution with exclude support | ✅ |
| PM-5 | Add `cacten init` command | ✅ |
| PM-6 | Add `cacten ingest --dry-run` manifest preview | ✅ |
| PM-7 | Refactor ingest pipeline so one manifest run creates one KB version | ✅ |
| PM-8 | Snapshot manifest into `.cacten/manifest-history/` before ingest | ✅ |
| PM-9 | Persist manifest provenance in KB version metadata | ✅ |
| PM-10 | Add `--label` support for human-friendly KB version notes | ✅ |
| PM-11 | Update README and help text | ✅ |
| PM-12 | Add tests for manifest workflow, label support, and version semantics | ✅ |

---

## Decisions From Review

- Ad hoc path ingestion remains supported alongside manifest-based ingest.
- `cacten init` should generate `.cacten/sources.toml` from `.cacten/sources-example.toml`, and raise an error only if the example file does not exist.
- `cacten ingest` should generate `.cacten/sources.toml` from `.cacten/sources-example.toml` when the real manifest is missing, and print `No sources.toml found. Generating from the sample file`.
- `cacten ingest` should support `--label` for human-friendly version notes.
- `version` is required in the manifest; if it is missing, Cacten should raise a validation error.
