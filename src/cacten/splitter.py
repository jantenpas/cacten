"""Text splitting strategies — prose and code-aware variants.

Dispatch is content-type driven: prose uses a character-based recursive
splitter; code uses LangChain's language-aware splitter which respects
function/class boundaries for the given language.
"""

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

# Maps cacten content_type strings to LangChain Language enum values.
# Only languages with meaningful AST-aware separator sets are listed here.
LANGUAGE_MAP: dict[str, Language] = {
    "python": Language.PYTHON,
    "typescript": Language.TS,
    "tsx": Language.TS,
    "javascript": Language.JS,
    "json": Language.JS,
    "markdown": Language.MARKDOWN,
    "html": Language.HTML,
}

_prose_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,
    separators=["\n\n", "\n", ".", " ", ""],
)


def split_text(text: str) -> list[str]:
    """Split prose text into chunks."""
    return _prose_splitter.split_text(text)


def split_code(text: str, language: Language) -> list[str]:
    """Split source code into chunks using language-aware separators.

    Uses a larger chunk size than prose (1024 vs 512) because a typical
    function body is larger than a paragraph and should stay intact.
    """
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=language,
        chunk_size=1024,
        chunk_overlap=128,
    )
    return splitter.split_text(text)


def split_by_content_type(text: str, content_type: str) -> list[str]:
    """Dispatch to the appropriate splitter based on content type.

    Code content types route to the language-aware splitter; everything
    else falls back to the prose splitter.
    """
    language = LANGUAGE_MAP.get(content_type)
    if language is not None:
        return split_code(text, language)
    return split_text(text)
