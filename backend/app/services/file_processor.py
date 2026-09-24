from pathlib import Path

from app.services.docx_extractor import extract_docx_text
from app.services.ocr_service import extract_image_text, extract_scanned_pdf_text
from app.services.pdf_extractor import extract_pdf_text
from app.services.text_cleaner import add_cleaned_text
from app.utils.file_utils import get_extension


def extract_text(file_path: Path) -> dict:
    """Select the format-specific text extractor for a stored document."""
    extension = get_extension(file_path.name)
    if extension == ".pdf":
        pdf_result = extract_pdf_text(file_path)
        result = extract_scanned_pdf_text(file_path) if pdf_result["needs_ocr"] else pdf_result
        return add_cleaned_text(result)
    if extension == ".docx":
        return add_cleaned_text(extract_docx_text(file_path))
    if extension in {".jpg", ".jpeg", ".png"}:
        return add_cleaned_text(extract_image_text(file_path))
    raise ValueError(f"Unsupported file type: {extension or 'unknown'}")