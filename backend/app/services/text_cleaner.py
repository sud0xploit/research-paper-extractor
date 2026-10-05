import re
import unicodedata
from collections import Counter


PAGE_NUMBER_PATTERN = re.compile(r"^(?:page\s+)?\d+(?:\s+of\s+\d+)?$", re.IGNORECASE)


def clean_text(raw_text: str, remove_repeated_lines: bool = True) -> str:
    """Conservatively normalize extracted text without removing metadata content."""
    normalized = unicodedata.normalize("NFKC", raw_text or "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in normalized.split("\n"):
        safe_line = "".join(
            character
            for character in line
            if character in {"\t"} or unicodedata.category(character)[0] != "C"
        )
        safe_line = re.sub(r"[ \t]+", " ", safe_line).strip()
        if safe_line and not PAGE_NUMBER_PATTERN.fullmatch(safe_line):
            lines.append(safe_line)

    if not remove_repeated_lines:
        return "\n".join(lines).strip()
    repeated_lines = Counter(line.casefold() for line in lines)
    cleaned_lines = [line for line in lines if repeated_lines[line.casefold()] < 3]
    return "\n".join(cleaned_lines).strip()


def add_cleaned_text(extraction_result: dict) -> dict:
    """Add cleaned text while retaining the extractor's raw output unchanged."""
    cleaned_pages = [clean_text(page) for page in extraction_result.get("page_texts", [])]
    cleaned_layout_pages = [
        clean_text(page, remove_repeated_lines=False)
        for page in extraction_result.get("layout_page_texts", [])
    ]
    cleaned_layout_blocks = [
        [
            {**block, "text": clean_text(block.get("text", ""), remove_repeated_lines=False)}
            for block in page_blocks
        ]
        for page_blocks in extraction_result.get("layout_blocks_by_page", [])
    ]
    return {
        **extraction_result,
        "cleaned_text": clean_text(extraction_result.get("raw_text", "")),
        "cleaned_page_texts": cleaned_pages,
        "cleaned_layout_page_texts": cleaned_layout_pages,
        "cleaned_layout_blocks": cleaned_layout_blocks,
    }