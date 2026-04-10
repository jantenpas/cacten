# Incremental Ingest — Design & Implementation Plan

> Plan for speeding up repeated manifest ingests by reusing unchanged files across KB versions.
> Goal: preserve Cacten's append-only version model while avoiding unnecessary re-chunking and re-embedding.

---

## Motivation

The current manifest ingest flow creates a new KB version on every run and fully reprocesses every resolved file:

- re-read file contents
- re-split into chunks
- re-embed each chunk
- re-upsert the entire corpus

This is simple and correct, but expensive for large corpora. In the common case, most files do not change between runs, so repeated full ingest wastes the majority of the work.

Incremental ingest should make repeated runs fast by:

1. detecting unchanged files
2. reusing existing chunk/vector results for those files
3. only reprocessing files that are new or changed

---

## Product Goal

Keep the current user-facing mental model:

- one ingest run = one KB version
- every version is immutable
- retrieval remains scoped to a specific `kb_version_id`

But improve implementation efficiency:

- unchanged files should not hit Ollama again
- unchanged files should not be re-chunked again
- repeated corpus refreshes should be much cheaper than the first full ingest

---

## Recommended v1.5 Approach

### Reuse unchanged files, but keep version-scoped points

For the first implementation, do **file-level reuse** while preserving the current retrieval model.

That means:

- if a file is unchanged, skip chunking and embedding
- fetch its prior chunk/vector data from the previous version
- clone those chunks into the new version with the new `kb_version_id`
- retrieval still filters by `kb_version_id` exactly as it does today

### Why this approach

- much lower risk than a full chunk-deduplicated storage redesign
- preserves current retrieval semantics
- avoids touching MCP/retrieval architecture
- delivers most of the ingest-time savings where Ollama is currently the bottleneck

---

## What Counts As "Unchanged"

A file can be reused only if all of the following still match:

- file content hash
- embedding model
- chunking strategy / chunk profile
- content type detection result

If any of those change, the file must be reprocessed.

### Required file metadata

For every ingested file, Cacten should track:

- absolute path
- content hash
- file size
- content type
- embedding model
- chunk profile / chunking settings
- chunk count
- chunk ids belonging to that file for that version

---

## Storage Design

### Version registry stays where it is

High-level version metadata remains in:

```text
~/.cacten/kb/versions.json
```

### Add per-version file manifests

Store file-level ingest metadata in:

```text
~/.cacten/kb/version-files/
  <version-id>.json
```

Example shape:

```json
[
  {
    "path": "/Users/jtenpas/Documents/ai-projects/tentile/src/index.ts",
    "file_hash": "sha256:abc123...",
    "file_size": 1824,
    "content_type": "typescript",
    "embedding_model": "nomic-embed-text",
    "chunk_profile": "default",
    "chunk_count": 12,
    "chunk_ids": ["...", "...", "..."]
  }
]
```

### Optional chunk payload duplication

Qdrant chunk payloads may also include:

- `source_path`
- `source_file_hash`

This is useful for debugging, but the primary source of truth for change detection should live in the version metadata layer, not only in Qdrant.

---

## Ingest Flow

### Current flow

```text
resolve files
→ process every file
→ embed every chunk
→ upsert everything
→ create new KB version
```

### Incremental flow

```text
resolve files
→ load previous version file manifest
→ hash current files
→ partition into unchanged / changed / new / removed
→ reuse unchanged file chunks
→ reprocess changed + new files
→ create new KB version
→ write new per-version file manifest
```

### File states

#### Unchanged

- file still exists in the manifest
- content hash matches previous version
- chunking + embedding settings match
- reuse prior chunk/vector data

#### Changed

- file still exists, but hash or settings differ
- reprocess fully

#### New

- file exists now but was not present in prior version
- process fully

#### Removed

- file existed in prior version but is no longer resolved by the manifest
- do nothing for the new version
- old version remains intact

---

## Reuse Strategy

### v1.5 implementation

Reuse prior chunk data by cloning version-scoped points into the new version.

This means:

- read prior file metadata
- fetch prior chunks for that file
- copy payload/vector data into new chunks
- assign new chunk ids and new `kb_version_id`

### Tradeoff

This does **not** deduplicate Qdrant storage across versions.
It saves embedding time, not storage space.

That is acceptable for the first implementation because embedding is the current bottleneck.

### Future v2 possibility

Later, Cacten could move to a true deduplicated chunk store with a version-to-chunk mapping layer.
That would reduce storage duplication, but it is a much larger refactor and not necessary to unlock the first big ingest win.

---

## Required Data Model Changes

### New model: `VersionFileRecord`

```python
class VersionFileRecord(BaseModel):
    path: str
    file_hash: str
    file_size: int
    content_type: str
    embedding_model: str
    chunk_profile: str
    chunk_count: int
    chunk_ids: list[str]
```

### Optional extensions to `ChunkMetadata`

Useful additions:

- `source_path: str | None`
- `source_file_hash: str | None`

These are not strictly required for the first implementation, but would improve debugging and traceability.

---

## Implementation Phases

### Phase 1 — File Hashing + Metadata Foundation

Goal: make ingest runs aware of per-file identity and preserve that data for future reuse.

Tasks:

1. Add a file hashing helper
2. Add `VersionFileRecord` model
3. Add `version-files/<version-id>.json` read/write helpers
4. Record per-file metadata for manifest ingests
5. Add tests for file-manifest persistence

Deliverable:
- every manifest ingest produces file-level metadata, even before reuse is implemented

### Phase 2 — Change Detection

Goal: classify manifest files by comparing current run to prior version metadata.

Tasks:

1. Load the previous active version's file manifest
2. Compare current resolved files against prior records
3. Partition into unchanged / changed / new / removed
4. Add CLI-visible ingest summary counts

Example output:

```text
Files resolved: 412
Unchanged: 398
Changed: 9
New: 5
Removed: 2
```

Deliverable:
- change detection works, but unchanged files may still be reprocessed for now

### Phase 3 — Reuse Unchanged Files

Goal: skip embedding for unchanged files.

Tasks:

1. Add a way to fetch all chunks for a file from a previous version
2. Clone those chunks into the new `kb_version_id`
3. Skip chunking + embedding for unchanged files
4. Preserve manifest/file provenance in the new version
5. Add tests covering mixed changed/unchanged runs

Deliverable:
- repeated ingest runs only embed changed/new files

### Phase 4 — UX + Observability

Goal: make incremental ingest understandable and trustworthy.

Tasks:

1. Print change summary during ingest
2. Print reused chunk counts vs newly embedded chunk counts
3. Update README and CLI help text
4. Add debug-friendly file-manifest inspection if needed

Deliverable:
- user can see what was reused and what was recomputed

---

## Files Likely Affected

| File | Change |
|---|---|
| `src/cacten/pipeline.py` | Add change detection and reuse path |
| `src/cacten/models.py` | Add file-level ingest metadata models |
| `src/cacten/versions.py` | Persist and load per-version file manifests |
| `src/cacten/store.py` | Add helper to fetch chunks by file/version if needed |
| `src/cacten/manifest.py` | Possibly expose resolved file details more explicitly |
| `src/cacten/cli.py` | Print incremental-ingest summaries |
| `README.md` | Document incremental ingest behavior |
| `tests/test_pipeline.py` | Mixed changed/unchanged ingest coverage |
| `tests/test_versions.py` | File-manifest persistence coverage |
| `tests/test_store.py` | Prior-file chunk fetch coverage |

---

## Task Breakdown

| # | Task | Status |
|---|---|---|
| II-1 | Add file hashing helper | ✅ |
| II-2 | Add `VersionFileRecord` model | ✅ |
| II-3 | Add `version-files/<version-id>.json` persistence layer | ✅ |
| II-4 | Record file-level metadata during manifest ingest | ✅ |
| II-5 | Load previous version file manifest for comparison | ✅ |
| II-6 | Partition files into unchanged/changed/new/removed | ✅ |
| II-7 | Add ingest summary output for change detection | ✅ |
| II-8 | Add store helper to fetch chunks for a file from a prior version | ✅ |
| II-9 | Clone unchanged file chunks into the new version | ✅ |
| II-10 | Skip chunking/embedding for unchanged files | ✅ |
| II-11 | Update README and help text | ✅ |
| II-12 | Add end-to-end tests for incremental ingest | ✅ |

---

## Risks

| Risk | Mitigation |
|---|---|
| Reuse logic silently becomes incorrect when settings change | Include embedding model, chunk profile, and content type in comparison logic |
| Qdrant storage still grows across versions | Accept as v1.5 tradeoff; prioritize compute savings first |
| File path moves are treated as "new" even when content is identical | Accept initially; content-based move detection can be a later improvement |
| Partial ingest failure leaves inconsistent new-version data | Reuse current cleanup-on-failure pattern and extend it to reused chunks |

---

## Recommendation

Build this in order:

1. file hash + per-version file manifests
2. change detection and user-visible summaries
3. reuse unchanged chunks

That sequence keeps the work incremental, testable, and easy to reason about while still moving directly toward the biggest ingest-time win.
