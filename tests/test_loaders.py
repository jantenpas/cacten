"""Tests for document loaders."""

from pathlib import Path

from cacten.loaders import _html_to_text, load_file


def test_load_markdown(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("# Hello\n\nThis is a test.")
    text, content_type = load_file(doc)
    assert "Hello" in text
    assert content_type == "markdown"


def test_load_pdf(tmp_path: Path) -> None:
    # Use pypdf to create a minimal valid PDF
    try:
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        pdf_path = tmp_path / "test.pdf"
        with open(pdf_path, "wb") as f:
            writer.write(f)
        text, content_type = load_file(pdf_path)
        assert content_type == "pdf"
    except ImportError:
        pass  # pypdf not available — skip


def test_html_to_text_strips_tags() -> None:
    html = "<html><body><h1>Hello</h1><p>World &amp; Friends</p></body></html>"
    text = _html_to_text(html)
    assert "Hello" in text
    assert "World & Friends" in text
    assert "<" not in text


def test_html_to_text_removes_scripts() -> None:
    html = "<html><script>alert('xss')</script><p>Safe</p></html>"
    text = _html_to_text(html)
    assert "alert" not in text
    assert "Safe" in text
