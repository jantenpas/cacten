"""Tests for the text splitter."""

from cacten.splitter import split_text


def test_split_basic() -> None:
    text = "Hello world. " * 100
    chunks = split_text(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 600  # some slack for splitter behavior


def test_split_empty() -> None:
    assert split_text("") == []


def test_split_short_text() -> None:
    text = "Short document."
    chunks = split_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text
