"""PDF text extraction and conservative Unicode/whitespace normalization."""
import unicodedata
from pathlib import Path
from .models import DocumentPage


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract all physical pages; blank pages remain visible for the audit.

    Detect and record pages with no text. OCR, when needed, is a separate step.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install requirements with `pip install -r requirements.txt` (pypdf missing)") from exc
    reader = PdfReader(str(path))
    pages = []
    for number, pdf_page in enumerate(reader.pages, start=1):
        raw = pdf_page.extract_text() or ""
        pages.append(DocumentPage(document_id, source, number, normalize_text(raw)))
    return pages


def normalize_text(text: str) -> str:
    """Normalize Unicode and line endings while preserving paragraph boundaries."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    # Collapse runs of blank lines but preserve a single paragraph separator.
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()
