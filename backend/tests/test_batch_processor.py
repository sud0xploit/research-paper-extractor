from pathlib import Path

from app.services import batch_processor


def test_batch_processor_continues_after_one_file_fails(tmp_path: Path, monkeypatch) -> None:
    good_file = tmp_path / "good.docx"
    bad_file = tmp_path / "bad.docx"
    good_file.write_bytes(b"good")
    bad_file.write_bytes(b"bad")

    def fake_process_file(file_path: Path) -> dict:
        if file_path.name == "bad.docx":
            raise ValueError("cannot process document")
        return {"filename": file_path.name, "status": "PROCESSED"}

    monkeypatch.setattr(batch_processor, "process_file", fake_process_file)

    results = batch_processor.process_batch([good_file, bad_file])

    assert [result["status"] for result in results] == ["PROCESSED", "ERROR"]
    assert results[1]["message"] == "cannot process document"


def test_batch_processor_sends_ocr_text_to_nlp_classifier(tmp_path: Path, monkeypatch) -> None:
    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"image")
    seen = {}

    monkeypatch.setattr(
        batch_processor,
        "extract_text",
        lambda path: {
            "raw_text": "OCR raw text",
            "cleaned_text": "OCR cleaned text",
            "extraction_method": "tesseract",
        },
    )
    monkeypatch.setattr(
        batch_processor,
        "extract_metadata",
        lambda text: {"title": text, "authors": []},
    )

    def fake_classifier(text, metadata):
        seen["text"] = text
        return {"publication_type": "Journal", "confidence": 0.91, "status": "AUTO_APPROVED"}

    monkeypatch.setattr(batch_processor, "classify_publication", fake_classifier)

    result = batch_processor.process_file(image_path)

    assert seen["text"] == "OCR cleaned text"
    assert result["classification"]["publication_type"] == "Journal"