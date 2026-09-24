# Research Document Extractor

A local web application for document classification, publication metadata extraction, DOI verification, human review, and Excel reporting.

This repository is currently at **Phase 9: PostgreSQL database foundation**. Application features are being added incrementally after explicit confirmation.

## Phase 1 Environment Check

Checked on Windows:

- Python: `C:\Python313\python.exe` is installed; Python 3.11 is also installed at `C:\Users\ASUS\AppData\Local\Programs\Python\Python311\python.exe`.
- pip: available through Python 3.13.
- Node.js: `v22.14.0`.
- npm: `10.9.2`.
- Git: `2.47.1.windows.2`.
- PostgreSQL: PostgreSQL 17 Windows service exists, but `psql` is not currently on `PATH`.
- Tesseract OCR: not found on `PATH` or in the usual Program Files locations.

Python 3.11 is the recommended project interpreter because the ML dependencies in `backend/requirements.txt` have broader compatibility with it than Python 3.13.

## Target Structure

```text
PDQA/
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |-- core/
|   |   |-- database/
|   |   |-- schemas/
|   |   |-- services/
|   |   `-- utils/
|   |-- tests/
|   |-- uploads/
|   |-- output/
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |-- pages/
|   |   |-- services/
|   |   |-- hooks/
|   |   `-- utils/
|   `-- package.json
|-- .env.example
|-- .gitignore
|-- docker-compose.yml
`-- README.md
```

The final backend will add `main.py`, Alembic files, database models, API routes, schemas, services, and tests inside this structure. The final frontend will add the Vite entry files and React screens/components.

## Phase 1 Setup

Open PowerShell in `D:\PDQA`.

### 1. Select Python 3.11 and create the backend virtual environment

```powershell
cd D:\PDQA
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python311\python.exe' -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
```

Expected Python output starts with `Python 3.11`.

If PowerShell blocks activation, run this once in a PowerShell window allowed by your organization:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

The virtual environment is not created automatically in Phase 1 validation because dependency installation is intentionally deferred.

### 2. Install backend dependencies

Run from `D:\PDQA` after activating the virtual environment:

```powershell
python -m pip install -r backend\requirements.txt
```

The dependency ranges include a compatible FastAPI, Starlette, pytest, and httpx combination for the FastAPI `TestClient`.

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Do not commit `.env`. It is ignored by Git.

### 4. Start PostgreSQL

The local PostgreSQL 17 service is present. To inspect or start it:

```powershell
Get-Service postgresql-x64-17
Start-Service postgresql-x64-17
```

The project can also use Docker Desktop instead:

```powershell
docker compose up -d postgres
```

Use one PostgreSQL option, not both on the same port. The default database settings are in `.env.example`.

### 5. Install Tesseract OCR

Install the Windows build from the UB Mannheim Tesseract distribution, then set the executable path in `.env`, for example:

```text
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Verify the installation in a new PowerShell window:

```powershell
tesseract --version
```

Tesseract is required for scanned PDFs and image files, but it is not needed for the Phase 1 scaffold.

### 6. Prepare the frontend

From `D:\PDQA\frontend`:

```powershell
npm install
```

Frontend source files are intentionally deferred until the React phase.

## Phase Workflow

The implementation will proceed in this order:

1. Environment and project structure
2. FastAPI backend and health endpoint
3. File upload
4. PDF, DOCX, and image extraction
5. OCR
6. Metadata extraction
7. Publication classification
8. Database and migrations
9. Crossref verification
10. Human review
11. Excel export
12. Batch processing
13. React frontend
14. Frontend/backend integration
15. Testing
16. Final cleanup and documentation

## Important Design Decisions

- Local extraction is the default; no paid LLM API is required.
- PostgreSQL is the target database. Docker Compose is supplied as a reproducible local option.
- Tesseract is an external Windows prerequisite and is configured through `TESSERACT_PATH`.
- Extracted metadata and externally verified metadata remain separate.
- Each document will be processed independently so one failure does not stop a batch.

## Current Status

Phase 1 files and directories are created and validated. Phase 2 adds `backend/app/main.py` with the FastAPI application and `GET /api/health`, plus a focused test in `backend/tests/test_health.py`. Phase 3 adds `POST /api/upload`, safe filename handling, supported file validation, maximum-size enforcement, and per-file results in `backend/app/api/upload.py` and `backend/app/utils/file_utils.py`. Phase 4 adds format-specific extraction services in `backend/app/services/` and tests in `backend/tests/test_extractors.py`. Phase 5 renders scanned PDFs page by page and sends them through Tesseract via `backend/app/services/ocr_service.py`. Phase 6 adds conservative normalization through `backend/app/services/text_cleaner.py`. Phase 7 adds local metadata extraction through `backend/app/services/metadata_extractor.py`. Phase 8 adds a local Hugging Face publication classifier through `backend/app/services/classifier.py`. Phase 9 adds SQLAlchemy models, PostgreSQL settings, sessions, and Alembic configuration. Phase 10 adds Crossref DOI verification and the human-review API in `backend/app/services/doi_verifier.py` and `backend/app/api/review.py`. Phase 11 adds filtered Excel export through `backend/app/services/excel_exporter.py` and `backend/app/api/export.py`. Phase 12 adds independent batch processing through `backend/app/services/batch_processor.py` and `backend/app/api/process.py`. Phase 13 adds the React intake workspace in `frontend/src/`, wired to upload, processing, and Excel export. Phase 14 enables browser integration with local CORS support for the Vite frontend. Phase 15 validates the backend suite, frontend production build, and real local NLP model inference.

Run the Phase 2 test from `D:\PDQA` with the virtual environment activated:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
python -m pytest backend\tests\test_health.py -q
```

Expected result for the current full test suite: `25 passed`.

The database foundation is in `backend/app/database/`. It defines `Document`, `Publication`, `Author`, `Verification`, and `ProcessingLog` with foreign keys, indexes, ordered authors, and cascading relationships. Alembic is configured in `backend/alembic.ini` and `backend/alembic/`.

From `D:\PDQA`, after activating `backend\.venv` and configuring `.env`:

```powershell
alembic -c backend\alembic.ini revision --autogenerate -m "initial tables"
alembic -c backend\alembic.ini upgrade head
```

The model test uses an isolated SQLite database so the test suite does not require PostgreSQL to be running. The application target remains PostgreSQL through `DATABASE_URL`.

Text extraction can be exercised directly from `D:\PDQA`:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
python -c "from pathlib import Path; from app.services.file_processor import extract_text; print(extract_text(Path('backend/uploads/<job_id>/<stored_file>')))"
```

Digital PDFs use PyMuPDF. DOCX files include paragraphs and table rows. Images and scanned PDFs use Tesseract through `TESSERACT_PATH`. PDFs with insufficient embedded text are rendered at 2x scale and OCR'd page by page. Password-protected PDFs return a clear processing error rather than being silently accepted. Processed results retain `raw_text` and add conservative `cleaned_text` with Unicode normalization, whitespace cleanup, obvious page-number removal, and repeated-line filtering.

Metadata extraction is local and rule-based. It returns title, dynamic ordered authors, publication fields, year, normalized DOI, ISSN, ISBN, and `metadata_confidence`. Missing or uncertain values remain `None` or empty rather than being guessed. Classification and external DOI verification are separate later phases.

Publication classification uses the bundled local Hugging Face zero-shot NLP model in `backend/models/publication-classifier`, configured with `LOCAL_CLASSIFIER_MODEL`. It returns `publication_type`, `confidence`, `status`, and `provider`. The model is loaded from the local filesystem with no hosted inference. It supports Journal, Conference, Book, Chapter, Thesis, Dissertation, Preprint, Report, and Other. Results below `CLASSIFICATION_THRESHOLD` are marked `NEEDS_REVIEW`.

The local model is based on `typeform/distilbert-base-uncased-mnli` and uses CPU inference by default. Tesseract remains the local OCR engine for scanned PDFs and images; DOCX and digital PDF text continue to use `python-docx` and PyMuPDF.

Upload documents with a multipart request using the `files` field:

```powershell
curl.exe -X POST http://localhost:8000/api/upload -F "files=@C:\path\to\paper.pdf"
```

Supported extensions are `.pdf`, `.docx`, `.jpg`, `.jpeg`, and `.png`. Files are stored under `backend\uploads\<job_id>` with a generated filename prefix. Invalid files are reported independently and do not prevent other files in the same request from being stored.
