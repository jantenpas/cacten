"""Recursive character text splitter — 512 tokens, 64 overlap."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,
    separators=["\n\n", "\n", ".", " ", ""],
)


def split_text(text: str) -> list[str]:
    """Split text into chunks. Returns list of chunk strings."""
    return _splitter.split_text(text)
