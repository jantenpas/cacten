"""Document loaders: local files (code, markdown, PDF) and URLs."""

from __future__ import annotations

from pathlib import Path

import httpx
from pypdf import PdfReader

# Authoritative map of supported file extensions to cacten content types.
EXTENSION_CONTENT_TYPE: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".txt": "text",
    ".pdf": "pdf",
}


def load_file(path: Path) -> tuple[str, str]:
    """Load a local file and return (text, content_type).

    Raises ValueError for unsupported file extensions.
    """
    suffix = path.suffix.lower()
    content_type = EXTENSION_CONTENT_TYPE.get(suffix)
    if content_type is None:
        supported = ", ".join(sorted(EXTENSION_CONTENT_TYPE))
        raise ValueError(
            f"Unsupported file type {suffix!r}. Supported extensions: {supported}"
        )
    if content_type == "pdf":
        return _load_pdf(path), "pdf"
    return path.read_text(encoding="utf-8"), content_type


def _load_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def load_url(url: str) -> tuple[str, str]:
    """Fetch a URL and return (text, content_type)."""
    response = httpx.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "pdf" in content_type:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(response.content)
            tmp = Path(f.name)
        text = _load_pdf(tmp)
        tmp.unlink(missing_ok=True)
        return text, "pdf"
    return _html_to_text(response.text), "html"


def _html_to_text(html: str) -> str:
    """Strip HTML tags to extract plain text."""
    import html as html_lib
    import re

    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode HTML entities
    text = html_lib.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text
