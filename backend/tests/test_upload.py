from fastapi.testclient import TestClient

from app.api import upload
from app.main import app


client = TestClient(app)


def test_upload_accepts_supported_file_and_reports_invalid_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upload, "UPLOAD_ROOT", tmp_path)

    response = client.post(
        "/api/upload",
        files=[
            ("files", ("paper.pdf", b"PDF content", "application/pdf")),
            ("files", ("notes.txt", b"not supported", "text/plain")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"]
    assert [item["status"] for item in payload["files"]] == ["UPLOADED", "ERROR"]
    assert list(tmp_path.rglob("*paper.pdf"))


def test_upload_rejects_file_larger_than_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upload, "UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(upload, "MAX_FILE_SIZE_BYTES", 4)

    response = client.post(
        "/api/upload",
        files={"files": ("large.pdf", b"12345", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["files"][0]["status"] == "ERROR"
    assert "maximum size" in response.json()["files"][0]["message"]