"""Tests for PDF loading and URL-as-PDF path in loaders."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from cacten.loaders import load_file, load_url


def test_load_file_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"fake")  # PdfReader is mocked below

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "page one text"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("cacten.loaders.PdfReader", return_value=mock_reader):
        text, content_type = load_file(pdf_path)

    assert content_type == "pdf"
    assert "page one text" in text


def test_load_file_pdf_empty_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"fake")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = None  # pypdf can return None
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("cacten.loaders.PdfReader", return_value=mock_reader):
        text, content_type = load_file(pdf_path)

    assert content_type == "pdf"
    assert text == ""


def test_load_url_html() -> None:
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.text = "<html><body><p>Hello world</p></body></html>"
    mock_response.raise_for_status = MagicMock()

    with patch("cacten.loaders.httpx.get", return_value=mock_response):
        text, content_type = load_url("https://example.com")

    assert content_type == "html"
    assert "Hello world" in text


def test_load_url_pdf_content_type(tmp_path: Path) -> None:
    fake_pdf_bytes = b"%PDF-fake"
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.content = fake_pdf_bytes
    mock_response.raise_for_status = MagicMock()

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "pdf from url"
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with (
        patch("cacten.loaders.httpx.get", return_value=mock_response),
        patch("cacten.loaders.PdfReader", return_value=mock_reader),
    ):
        text, content_type = load_url("https://example.com/doc.pdf")

    assert content_type == "pdf"
    assert "pdf from url" in text
