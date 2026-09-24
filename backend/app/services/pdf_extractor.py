from pathlib import Path

import fitz


MIN_MEANINGFUL_TEXT_CHARACTERS = 20


def extract_pdf_text(file_path: Path) -> dict:
    """Extract digital PDF text and identify PDFs that need OCR."""
    pages = []
    with fitz.open(file_path) as document:
        for page in document:
            pages.append(page.get_text("text"))

    raw_text = "\n".join(pages).strip()
    meaningful_text = len("".join(raw_text.split())) >= MIN_MEANINGFUL_TEXT_CHARACTERS
    return {
        "raw_text": raw_text,
        "page_count": len(pages),
        "extraction_method": "pymupdf" if meaningful_text else "none",
        "needs_ocr": not meaningful_text,
    }