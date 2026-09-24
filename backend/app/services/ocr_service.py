import os
from pathlib import Path

import fitz
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

from app.core.config import settings


def extract_image_text(file_path: Path) -> dict:
    """Extract text from an image using the locally installed Tesseract executable."""
    configure_tesseract()
    with Image.open(file_path) as image:
        prepared_image = _prepare_image_for_ocr(image)
        text = pytesseract.image_to_string(prepared_image).strip()
    return {
        "raw_text": text,
        "page_count": 1,
        "extraction_method": "tesseract",
        "needs_ocr": False,
    }


def _prepare_image_for_ocr(image: Image.Image) -> Image.Image:
    grayscale = ImageOps.grayscale(image)
    enlarged = grayscale.resize((grayscale.width * 2, grayscale.height * 2))
    enhanced = ImageEnhance.Contrast(enlarged).enhance(1.5)
    return ImageOps.autocontrast(enhanced)


def extract_scanned_pdf_text(file_path: Path) -> dict:
    """Render each scanned PDF page and extract its text with Tesseract."""
    configure_tesseract()
    page_text = []
    with fitz.open(file_path) as document:
        if document.is_encrypted and document.needs_pass:
            raise ValueError("Password-protected PDFs cannot be processed without a password.")

        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            page_text.append(pytesseract.image_to_string(_prepare_image_for_ocr(image)).strip())

    return {
        "raw_text": "\n\n".join(page_text).strip(),
        "page_count": len(page_text),
        "extraction_method": "tesseract-pdf",
        "needs_ocr": False,
    }


def configure_tesseract() -> None:
    configured_path = os.getenv("TESSERACT_PATH", "").strip() or settings.tesseract_path.strip()
    if configured_path:
        pytesseract.pytesseract.tesseract_cmd = configured_path