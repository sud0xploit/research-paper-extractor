from pathlib import Path

import fitz


MIN_MEANINGFUL_TEXT_CHARACTERS = 20


def extract_pdf_text(file_path: Path) -> dict:
    """Extract digital PDF text and identify PDFs that need OCR."""
    pages = []
    layout_pages = []
    layout_blocks_by_page = []
    with fitz.open(file_path) as document:
        for page in document:
            pages.append(page.get_text("text"))
            blocks = [
                block for block in page.get_text("blocks")
                if len(block) < 7 or block[6] == 0
            ]
            ordered_blocks = sorted(blocks, key=lambda block: (round(block[1] / 3), block[0]))
            layout_pages.append("\n".join(block[4].strip() for block in ordered_blocks if block[4].strip()))
            layout_blocks_by_page.append(
                [
                    {"x0": block[0], "y0": block[1], "text": block[4].strip()}
                    for block in ordered_blocks
                    if block[4].strip()
                ]
            )

    raw_text = "\n".join(pages).strip()
    meaningful_text = len("".join(raw_text.split())) >= MIN_MEANINGFUL_TEXT_CHARACTERS
    return {
        "raw_text": raw_text,
        "page_texts": pages,
        "layout_page_texts": layout_pages,
        "layout_blocks_by_page": layout_blocks_by_page,
        "page_count": len(pages),
        "extraction_method": "pymupdf" if meaningful_text else "none",
        "needs_ocr": not meaningful_text,
    }