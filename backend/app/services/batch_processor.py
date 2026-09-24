from collections.abc import Iterable
from pathlib import Path

from app.services.classifier import classify_publication
from app.services.file_processor import extract_text
from app.services.metadata_extractor import extract_metadata


BATCH_RESULTS: dict[str, list[dict]] = {}


def get_batch_results(job_id: str) -> list[dict] | None:
    return BATCH_RESULTS.get(job_id)


def remember_batch_results(job_id: str, results: list[dict]) -> None:
    BATCH_RESULTS[job_id] = results


def process_file(file_path: Path) -> dict:
    """Process one document while keeping extraction details for downstream use."""
    extracted = extract_text(file_path)
    metadata = extract_metadata(extracted.get("cleaned_text") or extracted.get("raw_text", ""))
    classification = classify_publication(extracted.get("cleaned_text") or "", metadata)
    return {
        "filename": file_path.name,
        "status": "PROCESSED",
        "extraction": extracted,
        "metadata": metadata,
        "classification": classification,
    }


def process_batch(file_paths: Iterable[Path]) -> list[dict]:
    """Process every file independently so one failure does not stop the batch."""
    results = []
    for file_path in file_paths:
        try:
            results.append(process_file(file_path))
        except Exception as error:
            results.append(
                {
                    "filename": file_path.name,
                    "status": "ERROR",
                    "message": str(error),
                }
            )
    return results