"""Document loaders: markdown, PDF, URL."""

from __future__ import annotations

from pathlib import Path

import httpx
from pypdf import PdfReader


def load_file(path: Path) -> tuple[str, str]:
    """Load a local file. Returns (text, content_type)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path), "pdf"
    # Default: treat as plain text / markdown
    return path.read_text(encoding="utf-8"), "markdown"


def _load_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def load_url(url: str) -> tuple[str, str]:
    """Fetch a URL and convert HTML to plain text. Returns (text, content_type)."""
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
