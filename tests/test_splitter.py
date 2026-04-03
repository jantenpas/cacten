"""Tests for the text splitter."""

from langchain_text_splitters import Language

from cacten.splitter import LANGUAGE_MAP, split_by_content_type, split_code, split_text


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


def test_split_code_python() -> None:
    code = "def foo():\n    return 1\n\n" * 50
    chunks = split_code(code, Language.PYTHON)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 1200  # slack for code chunk size


def test_split_code_typescript() -> None:
    code = "function foo(): number {\n    return 1;\n}\n\n" * 50
    chunks = split_code(code, Language.TS)
    assert len(chunks) > 1


def test_split_by_content_type_routes_code() -> None:
    code = "def foo():\n    pass\n\n" * 50
    chunks = split_by_content_type(code, "python")
    assert len(chunks) > 1


def test_split_by_content_type_routes_prose() -> None:
    text = "Hello world. " * 100
    chunks = split_by_content_type(text, "markdown")
    assert len(chunks) > 1


def test_split_by_content_type_unknown_falls_back_to_prose() -> None:
    text = "Hello world. " * 100
    chunks = split_by_content_type(text, "unknown_type")
    assert len(chunks) > 1


def test_language_map_covers_expected_types() -> None:
    expected = {"python", "typescript", "tsx", "javascript", "json", "markdown", "html"}
    assert expected.issubset(LANGUAGE_MAP.keys())
