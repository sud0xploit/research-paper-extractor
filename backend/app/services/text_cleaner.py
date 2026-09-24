import re
import unicodedata
from collections import Counter


PAGE_NUMBER_PATTERN = re.compile(r"^(?:page\s+)?\d+(?:\s+of\s+\d+)?$", re.IGNORECASE)


def clean_text(raw_text: str) -> str:
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

    repeated_lines = Counter(line.casefold() for line in lines)
    cleaned_lines = [line for line in lines if repeated_lines[line.casefold()] < 3]
    return "\n".join(cleaned_lines).strip()


def add_cleaned_text(extraction_result: dict) -> dict:
    """Add cleaned text while retaining the extractor's raw output unchanged."""
    return {**extraction_result, "cleaned_text": clean_text(extraction_result.get("raw_text", ""))}