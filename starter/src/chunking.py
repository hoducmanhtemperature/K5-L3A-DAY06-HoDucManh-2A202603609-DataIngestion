"""Fixed character windows and paragraph-aware chunks."""
import hashlib
import re
from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, text: str, strategy: str, ordinal: int) -> Chunk:
    identity = f"{strategy}:{page.document_id}:{page.page}:{ordinal}:{text}"
    chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return Chunk(chunk_id, page.document_id, page.source, page.page, text,
                 {**page.metadata, "document_id": page.document_id, "source": page.source, "page": page.page})


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Split into overlapping character windows without crossing page boundaries."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")
    text = page.text
    step = size - overlap
    chunks = []
    for start in range(0, len(text), step):
        part = text[start:start + size].strip()
        if part:
            chunks.append(_chunk(page, part, "fixed", len(chunks)))
        if start + size >= len(text):
            break
    return chunks


def _sentence_units(paragraph: str, max_size: int) -> list[str]:
    """Split an oversized paragraph at sentence ends, with balanced word-boundary fallback."""
    raw = [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z\"“'])", paragraph) if part.strip()]
    sentences: list[str] = []
    for part in raw:
        if sentences and len(sentences[-1]) < 80 and len(sentences[-1]) + len(part) + 1 <= max_size:
            sentences[-1] += " " + part
        else:
            sentences.append(part)

    result: list[str] = []
    for sentence in sentences:
        remaining = sentence
        while len(remaining) > max_size:
            boundary = remaining.rfind(" ", 1, max_size + 1)
            if boundary < max_size // 2:
                boundary = max_size
            # Avoid leaving a tiny trailing fragment when a sentence barely exceeds the limit.
            if len(remaining) - boundary < 100:
                earlier = remaining.rfind(" ", 1, len(remaining) - 100)
                if earlier >= max_size // 2:
                    boundary = earlier
            result.append(remaining[:boundary].strip())
            remaining = remaining[boundary:].strip()
        if remaining:
            if result and len(remaining) < 40 and len(result[-1]) + len(remaining) + 1 <= max_size:
                result[-1] += " " + remaining
            else:
                result.append(remaining)
    return result


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Pack paragraphs to the size limit; split oversized paragraphs at sentence ends."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    paragraphs = [p.strip() for p in page.text.split("\n") if p.strip()]
    units: list[str] = []
    for para in paragraphs:
        if len(para) <= max_size:
            units.append(para)
        else:
            units.extend(_sentence_units(para, max_size))
    packed: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) > max_size and current:
            packed.append(current)
            current = unit
        else:
            current = candidate
    if current:
        packed.append(current)
    return [_chunk(page, text, "paragraph", i) for i, text in enumerate(packed)]
