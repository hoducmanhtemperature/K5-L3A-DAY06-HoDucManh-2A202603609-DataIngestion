"""Split the Project Gutenberg Federalist Papers text into traceable essay units."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/source/federalist-papers.txt"
UNITS = ROOT / "starter/data/corpus"
MANIFEST = ROOT / "starter/data/manifest.json"

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(value: str) -> int:
    total = previous = 0
    for letter in reversed(value):
        current = ROMAN_VALUES[letter]
        total += -current if current < previous else current
        previous = current
    return total


def reflow(text: str) -> str:
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = " ".join(paragraph.split())
        if paragraph:
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def main() -> None:
    full_text = SOURCE.read_text(encoding="utf-8-sig")
    marker = "*** START OF THE PROJECT GUTENBERG EBOOK THE FEDERALIST PAPERS ***"
    start_offset = full_text.index(marker) + len(marker)
    text = full_text[start_offset:]
    text = text.split("*** END OF THE PROJECT GUTENBERG EBOOK THE FEDERALIST PAPERS ***", 1)[0]
    body_first_line = full_text[:start_offset].count("\n") + 1
    matches = list(re.finditer(r"(?m)^No\. ([IVXLCDM]+)\.\s*$", text))
    if not matches:
        raise RuntimeError("No Federalist essay headings found in source text")
    UNITS.mkdir(parents=True, exist_ok=True)
    seen: dict[str, int] = {}
    documents = []
    for index, match in enumerate(matches):
        roman = match.group(1)
        number = roman_to_int(roman)
        seen[roman] = seen.get(roman, 0) + 1
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw_body = text[match.start():end]
        body = reflow(raw_body)
        if len(body) < 1500:
            raise RuntimeError(f"Essay unit {index + 1} is too short ({len(body)} chars)")
        unit_name = f"federalist-unit-{index + 1:03d}.txt"
        (UNITS / unit_name).write_text(body + "\n", encoding="utf-8")
        line_start = body_first_line + text[:match.start()].count("\n")
        line_end = body_first_line + text[:end].count("\n") - 1
        category = (
            "union_and_factions" if number <= 14 else
            "confederation" if number <= 22 else
            "defense_and_taxation" if number <= 36 else
            "convention_and_republicanism" if number <= 43 else
            "federal_state_powers" if number <= 46 else
            "separation_and_checks" if number <= 51 else
            "legislature" if number <= 66 else
            "executive" if number <= 77 else
            "judiciary" if number <= 83 else "objections_and_conclusion"
        )
        documents.append({
            "document_id": f"federalist-{number:03d}-occurrence-{seen[roman]}",
            "path": f"data/corpus/{unit_name}",
            "source": f"Project Gutenberg eBook #18, Federalist No. {roman} (occurrence {seen[roman]})",
            "format": "text",
            "license_or_permission": "Original essays are public domain; Project Gutenberg eBook terms apply to its electronic edition. Source states users outside the U.S. must check local law; the authors died in 1804, 1804, and 1836.",
            "accessed_at": "2026-11-13",
            "content_pages": [index + 1],
            "content_chars": len(body),
            "source_line_start": line_start,
            "source_line_end": line_end,
            "metadata": {"paper_number": number, "heading_roman": roman,
                         "occurrence": seen[roman], "source_unit": index + 1,
                         "category": category},
        })
    manifest = {
        "title": "The Federalist Papers (Project Gutenberg eBook #18)",
        "source_url": "https://www.gutenberg.org/ebooks/18",
        "source_text_url": "https://www.gutenberg.org/cache/epub/18/pg18.txt",
        "license_or_permission": "The original essays are public domain. Project Gutenberg's eBook notice states the text may be reused under the Project Gutenberg License and asks users outside the U.S. to verify local law.",
        "accessed_at": "2026-11-13",
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "unit_rule": "One Federalist essay per source unit; text is Unicode-normalized, line-wrapped paragraphs reflowed, and paragraph boundaries retained. Each unit exceeds 1,500 characters. Unit sequence is preserved because the source has a duplicated No. LXX heading. The broad category field groups ranges by the essay titles in the source contents list and is intended only for coarse filtering.",
        "documents": documents,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(documents)} essay units; {sum(d['content_chars'] for d in documents):,} normalized characters.")
    print(f"Minimum unit length: {min(d['content_chars'] for d in documents):,} characters.")


if __name__ == "__main__":
    main()
