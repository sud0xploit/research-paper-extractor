import csv
from io import BytesIO, StringIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.database import get_db
from app.database.models import Author, Base, Document, Publication, Verification
from app.main import app
from app.services.excel_exporter import build_batch_workbook


def test_excel_export_contains_publication_metadata() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Document(
                filename="paper.pdf",
                storage_path="uploads/paper.pdf",
                file_type="pdf",
                publication=Publication(
                    title="Exportable paper",
                    publication_type="Journal",
                    doi="10.1234/example",
                    review_status="APPROVED",
                    authors=[Author(name="Ada Lovelace", author_order=1)],
                    verifications=[Verification(verification_type="HUMAN_REVIEW", status="APPROVED")],
                ),
            )
        )
        session.commit()

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/api/export/excel?status=APPROVED")
        assert response.status_code == 200
        assert response.headers["content-disposition"] == "attachment; filename=publications.xlsx"

        workbook = load_workbook(BytesIO(response.content))
        rows = list(workbook["Publications"].values)
        assert rows[0][0:3] == ("Document", "Title", "Authors")
        assert rows[1][0:3] == ("paper.pdf", "Exportable paper", "Ada Lovelace")
        assert rows[1][13:15] == ("APPROVED", "HUMAN_REVIEW: APPROVED")
        assert len(rows[0]) == len(rows[1]) == 15
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_batch_workbook_keeps_extracted_text_in_its_own_column() -> None:
    workbook = load_workbook(
        build_batch_workbook(
            [
                {
                    "filename": "scan.png",
                    "status": "PROCESSED",
                    "metadata": {"title": "Detected title", "metadata_confidence": 0.8},
                    "classification": {"publication_type": "Journal", "confidence": 0.9, "status": "AUTO_APPROVED"},
                    "extraction": {"extraction_method": "tesseract", "cleaned_text": "OCR source text"},
                }
            ]
        )
    )
    rows = list(workbook["Batch Results"].values)

    assert rows[0] == (
        "File", "Title", "Authors", "Publication Type", "Confidence", "Review Status",
        "Extraction Method", "DOI", "Metadata Confidence", "Extracted Text", "Error",
    )
    assert rows[1][1] == "Detected title"
    assert rows[1][3] == "Journal"
    assert rows[1][9] == "OCR source text"
    assert rows[1][10] is None


def test_normalized_exports_share_final_values_and_preserve_csv_content() -> None:
    record = {
        "paper_title": 'Edited, "Research" title',
        "authors": [{
            "name": "Zoë O'Neil",
            "department": "Department of Computing",
            "institution": "Example University",
            "location": "São Paulo",
        }],
        "journal_name": "Journal of Example Research",
        "publication_date": {"month": "March", "year": "2025"},
        "issn": {"print": "2049-3630", "electronic": None},
        "ugc_care": {"status": "not_verified", "link": None},
        "doi": "10.1234/final.value",
        "document_type": "journal",
        "conference_name": None,
        "confidence": {
            "paper_title": 0.98,
            "authors": 0.9,
            "departments": 0.85,
            "journal_name": 0.95,
            "publication_date": 0.9,
            "issn": 0.96,
            "ugc_care": 0.0,
            "doi": 0.96,
        },
        "evidence": {},
        "warnings": ["A quoted value, with a newline\nwas reviewed."],
        "missing_fields": ["ugc_care.link"],
    }
    client = TestClient(app)
    excel_response = client.post("/api/export/metadata/excel", json={"records": [record]})
    csv_response = client.post("/api/export/metadata/csv", json={"records": [record]})

    assert excel_response.status_code == csv_response.status_code == 200
    assert "Research_Paper_Metadata.xlsx" in excel_response.headers["content-disposition"]
    assert "Research_Paper_Metadata.csv" in csv_response.headers["content-disposition"]
    excel_rows = list(load_workbook(BytesIO(excel_response.content)).active.values)
    csv_rows = list(csv.reader(StringIO(csv_response.content.decode("utf-8-sig"), newline="")))

    assert excel_rows[0] == tuple(csv_rows[0])
    text_values = ["" if value is None else str(value) for value in excel_rows[1][:15]]
    assert text_values == csv_rows[1][:15]
    assert [float(value) for value in excel_rows[1][15:23]] == [float(value) for value in csv_rows[1][15:23]]
    assert (excel_rows[1][23] or "") == csv_rows[1][23]
    assert (excel_rows[1][24] or "") == csv_rows[1][24]
    assert excel_rows[1][0] == 'Edited, "Research" title'
    assert excel_rows[1][1] == "Zoë O'Neil — Department of Computing"
    assert excel_rows[1][4] == "São Paulo"
    assert "with a newline" in excel_rows[1][-1]


def test_normalized_export_rejects_invalid_confidence_values() -> None:
    response = TestClient(app).post(
        "/api/export/metadata/csv",
        json={"records": [{"confidence": {"paper_title": 2.0}}]},
    )

    assert response.status_code == 422