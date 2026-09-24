from pathlib import Path

from PIL import Image

from app.services import ocr_service


def test_image_ocr_preprocessing_enlarges_and_normalizes_image(tmp_path: Path) -> None:
    image = Image.new("RGB", (40, 20), "white")
    image_path = tmp_path / "scan.png"
    image.save(image_path)
    captured = {}

    def fake_image_to_string(processed_image):
        captured["size"] = processed_image.size
        captured["mode"] = processed_image.mode
        return "OCR text"

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(ocr_service.pytesseract, "image_to_string", fake_image_to_string)
    try:
        result = ocr_service.extract_image_text(image_path)
    finally:
        monkeypatch.undo()

    assert result["raw_text"] == "OCR text"
    assert captured == {"size": (80, 40), "mode": "L"}