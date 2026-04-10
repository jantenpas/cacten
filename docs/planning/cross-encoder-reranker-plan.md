# Cross-Encoder Reranker — Design & Implementation Plan

> Plan for improving retrieval precision by adding a second-stage reranker after Qdrant hybrid search.
> Goal: keep Cacten's local-first hybrid retrieval architecture, but make final chunk ranking much better on exact technical matches and "needle in a haystack" queries.

---

## Motivation

Cacten's current retrieval flow is:

```text
query
→ dense embedding
→ sparse encoding
→ Qdrant hybrid search (DBSF fusion)
→ top-k chunks
```

This is a strong v1 architecture, but recent manual testing exposed an important weakness:

- the right chunk is sometimes in the KB
- hybrid retrieval can still fail to rank that chunk near the top
- short exact identifiers or small phrases inside larger chunks are especially weak cases

A reranker is the highest-ROI next step because it improves the **final ordering** of already-retrieved candidates without changing ingest, chunk storage, or KB versioning.

---

## Product Goal

Keep the current mental model:

- Qdrant hybrid search remains the first-stage retriever
- retrieval stays scoped to the active `kb_version_id`
- `cacten retrieve` and MCP both still return context chunks, not generated answers

Improve ranking quality by:

1. retrieving a wider candidate set from Qdrant
2. scoring each `(query, chunk)` pair with a cross-encoder
3. returning the reranked top results

---

## Recommended v1 Approach

### Two-stage retrieval

```text
query
→ Qdrant hybrid search (dense + sparse, prefetch 50, return 50)
→ cross-encoder reranker
→ final top 10 chunks
```

### Why this is the right first implementation

- no ingest changes required
- no Qdrant schema changes required
- improves precision where the current system is weakest
- preserves the existing local-first architecture
- can degrade gracefully back to hybrid-only retrieval if the reranker is unavailable

---

## Runtime And Model Recommendation

### Updated runtime decision

Use **FastEmbed's ONNX Runtime-based reranker** as the primary local path.

Initial model:

- `Xenova/ms-marco-MiniLM-L-6-v2`

Why:

- maintained by the Qdrant ecosystem, which already matches Cacten's vector store choice
- uses ONNX Runtime instead of PyTorch
- avoids the PyTorch / NumPy / macOS Intel compatibility issues encountered with `sentence-transformers`
- supports Python 3.12 and local CPU inference
- good enough to prove the reranking pipeline before investing in heavier model quality work

### Decision log

The original plan targeted:

- `sentence-transformers`
- `BAAI/bge-reranker-v2-m3`

That path was rejected for the first implementation because it introduced a fragile dependency stack on macOS Intel:

- newer PyTorch versions do not publish compatible macOS x86_64 wheels
- older compatible PyTorch versions conflict with newer `sentence-transformers` / `transformers` expectations
- older PyTorch also expects NumPy 1.x, while the environment resolved NumPy 2.x

This is too much setup friction for a local-first developer tool.

FastEmbed is a better product fit for Cacten's v1 reranker because it prioritizes simple local install and ONNX Runtime inference over maximum model choice.

### Future model upgrade

After the reranker pipeline works end to end, revisit stronger rerankers:

- `BAAI/bge-reranker-base` if supported cleanly through FastEmbed
- `BAAI/bge-reranker-v2-m3` if a Mac-friendly runtime path is available
- hosted rerankers as an optional non-local provider, not the default

### Fallback option

If local reranking is not available:

- skip reranking
- log or surface a clear message in verbose/debug modes
- continue with hybrid-only retrieval

### Non-goal for this phase

Do not add a hosted reranker provider yet. Keep v1 local-first.

---

## Mental Model

The reranker is not another retriever and not another embedding model.

It is a **judge** that runs after retrieval.

### Current mental model

```text
query
→ dense retrieval finds semantically related chunks
→ sparse retrieval finds exact-term chunks
→ DBSF fusion blends both signals
→ final top-k returned
```

### New mental model

```text
query
→ dense retrieval finds semantically related chunks
→ sparse retrieval finds exact-term chunks
→ DBSF fusion produces a candidate set
→ cross-encoder judges each candidate against the query
→ reranked top-k returned
```

### Why this matters

Hybrid retrieval is good at **recall**:

- "what chunks might be relevant?"

The reranker is good at **precision**:

- "which of these candidates is actually the best answer?"

That distinction is especially important for:

- short exact identifiers
- filenames and symbols
- literal phrases buried inside broader chunks
- technical queries where multiple chunks are plausibly related

---

## Retrieval Flow Changes

### Current

In [retrieval.py](/Users/jtenpas/Documents/ai-projects/cacten/src/cacten/retrieval.py), `retrieve()`:

1. embeds the query densely
2. encodes the query sparsely
3. calls `QdrantVectorStore.search(...)`
4. returns the top `k`

### Proposed

Split retrieval into two stages:

1. first-stage hybrid retrieval
   - retrieve `prefetch_k` candidates from Qdrant
   - example default: `50`
2. second-stage reranking
   - score each `(query, chunk.text)` pair with the cross-encoder
   - sort by reranker score descending
   - return final `top_k`

### Important product rule

The reranker should only change the **order** of already-retrieved candidates.

It should not:

- fetch new chunks from outside the candidate set
- change version scoping
- mutate KB data

---

## Concrete Example

Suppose the query is:

```text
Cacten Test <unique-id>
```

And first-stage hybrid retrieval returns these candidates:

1. `README.md` chunk containing the exact phrase
2. `tasks.md` chunk mentioning Cacten generally
3. `systems-design.md` chunk about retrieval
4. `embeddings.py` chunk about sparse tokenization

Hybrid retrieval may still rank `tasks.md` or `systems-design.md` above the README chunk because they are semantically rich and broadly relevant to "Cacten."

The reranker then scores each pair directly:

```text
("Cacten Test <unique-id>", README chunk)         -> 0.98
("Cacten Test <unique-id>", tasks.md chunk)       -> 0.31
("Cacten Test <unique-id>", systems-design chunk) -> 0.22
("Cacten Test <unique-id>", embeddings.py chunk)  -> 0.18
```

The README chunk wins because the model can directly judge the query against the candidate text, not just rely on first-stage retrieval signals.

This is the exact class of failure the reranker is meant to improve.

---

## Implementation Shape

### New module

Add a dedicated reranker module:

```text
src/cacten/rerank.py
```

Responsibilities:

- load the reranker model lazily
- score `(query, text)` pairs
- return scored results in sorted order

Suggested interface:

```python
from cacten.models import ScoredChunk

def rerank(query: str, candidates: list[ScoredChunk], top_k: int) -> list[ScoredChunk]:
    ...
```

Suggested internal helper shape:

```python
def score_pairs(query: str, texts: list[str]) -> list[float]:
    ...
```

That split keeps the module easy to test:

- `score_pairs(...)` handles model inference
- `rerank(...)` handles sorting, truncation, and score replacement

### Proposed module sketch

```python
from __future__ import annotations

from functools import lru_cache

from cacten import config
from cacten.models import ScoredChunk


@lru_cache(maxsize=1)
def _get_reranker():
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model_name=config.RERANK_MODEL)


def _truncate(text: str) -> str:
    return text[: config.RERANK_MAX_CHARS]


def score_pairs(query: str, texts: list[str]) -> list[float]:
    model = _get_reranker()
    scores = model.rerank(query, [_truncate(text) for text in texts])
    return [float(score) for score in scores]


def rerank(query: str, candidates: list[ScoredChunk], top_k: int) -> list[ScoredChunk]:
    if not candidates:
        return []

    scores = score_pairs(query, [candidate.chunk.text for candidate in candidates])
    reranked = [
        ScoredChunk(chunk=candidate.chunk, score=score)
        for candidate, score in zip(candidates, scores, strict=True)
    ]
    reranked.sort(key=lambda item: item.score, reverse=True)
    return reranked[:top_k]
```

This is not final production code, but it is the shape I would build toward.

### Config additions

Add reranker configuration in [config.py](/Users/jtenpas/Documents/ai-projects/cacten/src/cacten/config.py):

- `RERANK_ENABLED = True`
- `RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"`
- `RERANK_CANDIDATES = 50`
- `RERANK_MAX_CHARS = 4000`

Why `RERANK_MAX_CHARS`:

- cross-encoders are slower than first-stage retrieval
- long chunk text should be truncated consistently to control latency

### Store changes

Keep [store.py](/Users/jtenpas/Documents/ai-projects/cacten/src/cacten/store.py) focused on first-stage retrieval.

Recommended change:

- let `QdrantVectorStore.search(...)` accept a larger `top_k`
- use that as the candidate set for reranking

No Qdrant payload or schema changes are required.

### Retrieval changes

Update [retrieval.py](/Users/jtenpas/Documents/ai-projects/cacten/src/cacten/retrieval.py):

1. retrieve `candidate_k = max(top_k, config.RERANK_CANDIDATES)` from Qdrant
2. if reranking is enabled:
   - pass candidates into `rerank(...)`
   - return the reranked top `top_k`
3. otherwise:
   - return the hybrid results directly

### Retrieval integration sketch

The likely retrieval shape is:

```python
from cacten import config
from cacten.rerank import rerank


def retrieve(query: str, top_k: int = 10, kb_version_id: str | None = None) -> list[ScoredChunk]:
    ...
    candidate_k = max(top_k, config.RERANK_CANDIDATES)
    candidates = store.search(
        dense_vector=dense,
        sparse_indices=sparse_idx,
        sparse_values=sparse_val,
        kb_version_id=version_id,
        top_k=candidate_k,
    )

    if not config.RERANK_ENABLED:
        return candidates[:top_k]

    try:
        return rerank(query=query, candidates=candidates, top_k=top_k)
    except Exception:
        return candidates[:top_k]
```

That fallback behavior preserves the current user experience even if the reranker dependency or local model is unavailable.

---

## Scoring Strategy

### Replace final score with reranker score

For v1, keep this simple:

- Qdrant hybrid search is just candidate generation
- the reranker owns final ordering
- final `ScoredChunk.score` becomes the reranker score

Why:

- easiest to reason about
- easiest to test
- standard second-stage retrieval pattern

### Preserve first-stage score for debugging

Add an optional metadata field or debug-only sidecar later if we want to compare:

- hybrid score
- reranker score

This is useful, but not required for the first implementation.

---

## Dependency Strategy

### Preferred library path

Use FastEmbed's reranker support:

- dependency: `fastembed`
- API: `fastembed.rerank.cross_encoder.TextCrossEncoder`
- runtime: ONNX Runtime

### Important constraint

Do not make reranking a mandatory dependency for the entire project if it can be avoided.

Recommended path:

- add the reranker dependency as an optional runtime dependency if possible
- or fail gracefully with a clear message when reranking is enabled but the dependency/model is unavailable

This keeps the base CLI and ingest path lightweight.

### What installation will likely look like

At implementation time, expect something like:

```bash
uv add fastembed
```

Then, on first reranker use, the model is downloaded and cached locally by FastEmbed.

This means reranker setup is still different from Ollama:

- dense embeddings today: `ollama pull ...`
- reranker: Python dependency + FastEmbed model download

If we want stricter local control later, we can document:

- how to pre-download the model
- how to point Cacten at a local cache path
- how to disable reranking entirely

---

## UX / CLI Behavior

### Default behavior

If reranking is enabled and available:

- `cacten retrieve` uses reranking automatically
- MCP `search_personal_kb` also benefits automatically

### Verbose mode

In verbose/debug contexts, show enough to explain what happened:

```text
Hybrid candidates: 50
Reranker enabled: Xenova/ms-marco-MiniLM-L-6-v2
Returned: 10
```

### Optional CLI flags

Not required for the first pass, but good follow-up additions:

- `--no-rerank`
- `--candidates 50`

These are helpful for debugging and A/B testing retrieval quality.

---

## Evaluation Plan

This feature needs explicit before/after evals.

### Manual eval set

Build a small retrieval-focused eval set with:

- exact identifiers
- filenames
- function/class names
- short quotes from docs
- semantic questions

### Success criteria

Reranking should improve:

- exact-match precision on technical queries
- ranking of the obviously correct chunk
- top-1 / top-3 quality on known test prompts

It should not significantly hurt:

- semantic retrieval on broader questions
- local-first usability via major latency regressions

---

## Latency Expectations

A reranker will make retrieval slower than hybrid-only retrieval.

That is acceptable if:

- candidate count is capped
- chunk text is truncated sensibly
- quality gains are obvious on real queries

Expected tradeoff:

- hybrid retrieval stays fast
- reranking adds a second-stage precision cost
- MCP responses should still feel interactive for normal use

If latency is too high, the first tuning knobs should be:

1. reduce candidate count
2. truncate chunk text more aggressively
3. allow `--no-rerank` fallback

---

## Risks

| Risk | Mitigation |
|---|---|
| Local reranker dependency is heavy or awkward to install | Prefer FastEmbed/ONNX Runtime over PyTorch; keep graceful fallback |
| Latency becomes too high for MCP usage | Cap candidate count and input length; keep hybrid-only fallback |
| Reranker improves exact matching but hurts broad semantic queries | Use a small eval set before making it the unquestioned default |
| Debugging gets harder because hybrid score and reranker score differ | Add verbose/debug output for both stages |

---

## Phased Task Breakdown

### RR-1 — Reranker design finalization

- ✅ confirm local model choice
- ✅ confirm dependency path
- ✅ confirm candidate count default

### RR-2 — Config + dependency wiring

- ✅ add reranker config knobs
- ✅ add dependency/runtime guardrails

### RR-3 — New reranker module

- ✅ implement lazy model loading
- ✅ implement `(query, chunk)` batch scoring
- ✅ implement top-k reranked return

### RR-4 — Retrieval pipeline integration

- ✅ retrieve wider hybrid candidate set
- ✅ rerank candidates before final return
- ✅ preserve hybrid-only fallback path

### RR-5 — CLI/MCP observability

- ⬜ add verbose output showing candidate count and reranker usage
- ⬜ optionally add `--no-rerank` later

### RR-6 — Tests

- ✅ unit test reranker wrapper
- ✅ retrieval tests proving reranker is called and truncates to final `top_k`
- ✅ fallback tests when reranker is unavailable
- ✅ regression test around an identifier-heavy query

### RR-7 — Evaluation + tuning

- ✅ run manual retrieval bakeoff
- ⬜ tune candidate count and truncation limits
- ⬜ document quality/latency tradeoffs

---

## Recommended Build Order

1. Add config knobs and the `rerank.py` module
2. Integrate reranking into `retrieve()`
3. Add graceful fallback behavior
4. Add tests
5. Run a targeted retrieval eval set
6. Tune candidate depth and truncation

---

## Definition of Done

This feature is done when:

- hybrid retrieval returns a wider candidate set
- a local cross-encoder reranks candidates before final return
- `cacten retrieve` and MCP both benefit automatically
- hybrid-only fallback still works cleanly
- tests cover the normal and fallback paths
- manual evals show a clear quality improvement on technical exact-match queries

Current status: implemented and manually validated on exact-token retrieval. Remaining follow-up work is tuning/observability, not core reranker integration.
