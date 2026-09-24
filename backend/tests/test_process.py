from pathlib import Path

from fastapi.testclient import TestClient

from app.api import process
from app.main import app


def test_process_endpoint_returns_independent_file_results(tmp_path: Path, monkeypatch) -> None:
    job_directory = tmp_path / "job-123"
    job_directory.mkdir()
    (job_directory / "good.docx").write_bytes(b"good")
    (job_directory / "bad.pdf").write_bytes(b"bad")
    (job_directory / "notes.txt").write_bytes(b"ignored")
    monkeypatch.setattr(process, "UPLOAD_ROOT", tmp_path)

    monkeypatch.setattr(
        process,
        "process_batch",
        lambda paths: [
            {"filename": path.name, "status": "PROCESSED" if path.name == "good.docx" else "ERROR"}
            for path in paths
        ],
    )

    response = TestClient(app).post("/api/process/job-123")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "job-123",
        "count": 2,
        "files": [
            {"filename": "bad.pdf", "status": "ERROR"},
            {"filename": "good.docx", "status": "PROCESSED"},
        ],
    }