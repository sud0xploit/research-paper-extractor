from pathlib import Path

from docx import Document


def extract_docx_text(file_path: Path) -> dict:
    """Extract DOCX paragraphs and table cells while preserving reading order."""
    document = Document(file_path)
    sections = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                sections.append(" | ".join(cells))

    return {
        "raw_text": "\n".join(sections),
        "page_count": None,
        "extraction_method": "python-docx",
        "needs_ocr": False,
    }