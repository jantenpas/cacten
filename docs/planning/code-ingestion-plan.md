# Code Ingestion — Design & Implementation Plan

> Spike to add code file support and directory ingestion to the cacten pipeline.
> Prerequisite for meaningful evals against coding style use cases.

---

## Motivation

The current ingestion pipeline supports markdown, PDF, and URLs. To teach Cacten a developer's coding style, it needs to ingest actual source files. Two things are needed:

1. **Code-aware chunking** — split code by logical units (functions, classes) rather than by character count, so retrieved chunks are semantically coherent.
2. **Directory ingestion** — accept a directory path and ingest all relevant files in one command.

---

## What's Changing

### 1. Code-Aware Chunking (`splitter.py`)

Current behavior: all content uses `RecursiveCharacterTextSplitter` with character-based splits (512 chars, 64 overlap). This is fine for prose but breaks code at arbitrary points — splitting a function mid-body, losing the signature, etc.

New behavior: route to a code-aware splitter when `content_type` is `"python"`, `"typescript"`, or `"tsx"`.

**Approach:** Use LangChain's `Language`-aware splitter which knows language-specific separators (class/function definitions, decorators, etc.). For Python this uses `ast`-friendly separators. For TypeScript/TSX it uses function/arrow-function/component boundaries.

```python
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

LANGUAGE_MAP: dict[str, Language] = {
    "python": Language.PYTHON,
    "typescript": Language.TS,
    "tsx": Language.TS,
}

def split_code(text: str, language: Language) -> list[str]:
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=language,
        chunk_size=1024,   # larger than prose — code units are bigger
        chunk_overlap=128,
    )
    return splitter.split_text(text)
```

A dispatch function `split_by_content_type(text, content_type)` routes to `split_code` or the existing `split_text` based on content type.

**Chunk size rationale:** Code chunks are set to 1024/128 (vs 512/64 for prose) because a typical function body is larger than a paragraph and should stay intact.

---

### 2. File Extension → Content Type Mapping (`loaders.py`)

Add a new `load_code_file()` function and an extension map:

```python
EXTENSION_CONTENT_TYPE: dict[str, str] = {
    ".py":   "python",
    ".ts":   "typescript",
    ".tsx":  "tsx",
    ".md":   "markdown",
    ".html": "html",
    ".css":  "css",
    ".js":   "javascript",
}
```

`load_file()` already handles markdown and PDF. It needs to be extended to:
- Accept `.py`, `.ts`, `.tsx`, `.js`, `.css` as plain-text reads
- Return both the text and the detected `content_type`

Currently `load_file()` returns `tuple[str, str, str]` (text, source_url, source_filename). The `content_type` is determined inside `pipeline.py` with a simple `if/elif` block — that logic should move into `loaders.py` and be driven by extension.

---

### 3. Directory Ingestion (`pipeline.py` + `cli.py`)

**New function:** `ingest_directory(path: str, extensions: list[str] | None = None) -> list[KBVersion]`

Behavior:
- Walk the directory recursively using `pathlib.Path.rglob()`
- Skip hidden files/dirs (`.git`, `__pycache__`, `.venv`, `node_modules`)
- Filter to allowed extensions (default: `.py .ts .tsx .md .html .css .js`)
- Call `ingest(source)` per file, collecting results
- Return all `KBVersion` objects created

**CLI:** Extend `cacten ingest` to accept multiple paths:

```
cacten ingest ./src/cacten ./docs
cacten ingest ./src --ext .py .ts .tsx
```

`Typer` supports `argument: list[str]` for variadic positional args.

---

## What's NOT Changing

- The `Chunk` and `ChunkMetadata` models — `content_type` already supports arbitrary strings
- The vector store layer — no changes to Qdrant schema
- The MCP server — retrieval is content-type-agnostic
- The embedding pipeline — same dense + sparse path for all content types

---

## Files Affected

| File | Change |
|---|---|
| `src/cacten/splitter.py` | Add `split_code()` and `split_by_content_type()` dispatch |
| `src/cacten/loaders.py` | Add `load_code_file()`, extension → content_type map, update `load_file()` |
| `src/cacten/pipeline.py` | Update `ingest()` to use dispatch splitter; add `ingest_directory()` |
| `src/cacten/cli.py` | Extend `ingest` command to accept multiple paths + `--ext` flag |
| `tests/test_splitter.py` | Add tests for code chunking dispatch |
| `tests/test_pipeline.py` | Add test for directory ingestion |

---

## Tasks

| # | Task | Status |
|---|---|---|
| CI-1 | Add `LANGUAGE_MAP`, `split_code()`, `split_by_content_type()` to `splitter.py` | ✅ |
| CI-2 | Add `EXTENSION_CONTENT_TYPE` map and `load_code_file()` to `loaders.py` | ✅ |
| CI-3 | Move content_type detection from `pipeline.py` into `loaders.py` | ✅ |
| CI-4 | Update `ingest()` in `pipeline.py` to call `split_by_content_type()` | ✅ |
| CI-5 | Add `ingest_directory()` to `pipeline.py` | ✅ |
| CI-6 | Extend `cacten ingest` CLI to accept multiple paths and `--ext` flag | ✅ |
| CI-7 | Tests for code splitter dispatch and directory ingestion | ✅ |

---

## Open Questions

- **CSS/HTML chunking:** These don't have great LangChain language support. Use character splitter for now; revisit if retrieval quality is poor.
- **Large files:** No file size guard currently. Add a warning (not a hard limit) if a single file produces > 100 chunks.
- **`.js` files:** Low priority for the personal KB use case (prefer `.ts`). Include but don't optimize.
