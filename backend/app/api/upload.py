from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile

from app.utils.file_utils import ALLOWED_EXTENSIONS, get_extension, get_safe_filename


router = APIRouter(prefix="/api/upload", tags=["upload"])
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


@router.post("")
async def upload_documents(files: list[UploadFile] = File(...)) -> dict:
    """Store supported documents and return an independent result for each file."""
    job_id = uuid4().hex
    job_directory = UPLOAD_ROOT / job_id
    job_directory.mkdir(parents=True, exist_ok=True)
    results = []

    for uploaded_file in files:
        extension = get_extension(uploaded_file.filename or "")
        result = {"filename": uploaded_file.filename or "", "status": "ERROR"}

        if extension not in ALLOWED_EXTENSIONS:
            result["message"] = "Unsupported file type. Allowed: PDF, DOCX, JPG, JPEG, PNG."
            results.append(result)
            continue

        stored_path = job_directory / get_safe_filename(uploaded_file.filename or "")
        size = 0
        try:
            with stored_path.open("wb") as output_file:
                while chunk := await uploaded_file.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > MAX_FILE_SIZE_BYTES:
                        raise ValueError("File exceeds the 50 MB maximum size.")
                    output_file.write(chunk)
        except (OSError, ValueError) as error:
            stored_path.unlink(missing_ok=True)
            result["message"] = str(error)
        else:
            result.update(
                {
                    "status": "UPLOADED",
                    "size_bytes": size,
                    "stored_path": str(stored_path.relative_to(UPLOAD_ROOT.parent)),
                }
            )
        finally:
            await uploaded_file.close()

        results.append(result)

    return {"job_id": job_id, "files": results}