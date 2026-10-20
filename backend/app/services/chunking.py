import re
from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 150,
) -> List[str]:
    """
    Learning Note (Module 2 - Text Chunking):
    Splits a long document into smaller pieces (chunks) so they fit inside
    the embedding model and LLM context window.
    We use an 'overlap' (150 characters) so sentences at the edge of a chunk
    don't lose their meaning.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    # Try splitting by paragraph first, then line break, then sentence, then space
    separators = ["\n\n", "\n", ". ", "? ", "! ", " "]

    while start < text_len:
        end = start + chunk_size

        if end >= text_len:
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Look for a clean breakpoint near the end
        breakpoint = -1
        search_window = text[max(start, end - overlap) : min(text_len, end + 50)]

        for sep in separators:
            pos = search_window.rfind(sep)
            if pos != -1:
                breakpoint = max(start, end - overlap) + pos + len(sep)
                break

        if breakpoint == -1 or breakpoint <= start:
            breakpoint = end

        chunk = text[start:breakpoint].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward, stepping back by overlap
        start = max(breakpoint - overlap, start + 1)

    return chunks
