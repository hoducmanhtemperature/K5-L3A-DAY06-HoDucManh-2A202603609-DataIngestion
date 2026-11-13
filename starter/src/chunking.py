"""Fixed character windows and paragraph-aware chunks."""
import hashlib
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


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Pack whole paragraphs to the size limit; split only oversized paragraphs."""
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    paragraphs = [p.strip() for p in page.text.split("\n") if p.strip()]
    units: list[str] = []
    for para in paragraphs:
        if len(para) <= max_size:
            units.append(para)
        else:
            units.extend(para[i:i + max_size] for i in range(0, len(para), max_size))
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
