from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.services.batch_processor import process_batch, remember_batch_results
from app.utils.file_utils import ALLOWED_EXTENSIONS, get_extension


router = APIRouter(prefix="/api/process", tags=["process"])
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"


@router.post("/{job_id}")
def process_uploaded_batch(job_id: str) -> dict:
    job_directory = (UPLOAD_ROOT / job_id).resolve()
    if job_directory.parent != UPLOAD_ROOT.resolve() or not job_directory.is_dir():
        raise HTTPException(status_code=404, detail="Upload job not found")

    files = sorted(
        path for path in job_directory.iterdir()
        if path.is_file() and get_extension(path.name) in ALLOWED_EXTENSIONS
    )
    results = process_batch(files)
    remember_batch_results(job_id, results)
    return {"job_id": job_id, "count": len(results), "files": results}