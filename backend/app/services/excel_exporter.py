from io import BytesIO
from collections.abc import Iterable

from openpyxl import Workbook
from openpyxl.styles import Font

from app.database.models import Publication


EXPORT_HEADERS = (
    "Document",
    "Title",
    "Authors",
    "Publication Type",
    "Journal",
    "Conference",
    "Publisher",
    "Year",
    "DOI",
    "ISSN",
    "ISBN",
    "Extraction Confidence",
    "Classification Confidence",
    "Review Status",
    "Verification Status",
)

BATCH_EXPORT_HEADERS = (
    "File",
    "Title",
    "Authors",
    "Publication Type",
    "Confidence",
    "Review Status",
    "Extraction Method",
    "DOI",
    "Metadata Confidence",
    "Extracted Text",
    "Error",
)


def build_publications_workbook(publications: Iterable[Publication]) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Publications"
    sheet.append(EXPORT_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for publication in publications:
        verification_status = "; ".join(
            f"{verification.verification_type}: {verification.status}"
            for verification in publication.verifications
        )
        sheet.append(
            [
                publication.document.filename if publication.document else None,
                publication.title,
                "; ".join(author.name for author in publication.authors),
                publication.publication_type,
                publication.journal,
                publication.conference,
                publication.publisher,
                publication.publication_year,
                publication.doi,
                publication.issn,
                publication.isbn,
                publication.extraction_confidence,
                publication.classification_confidence,
                publication.review_status,
                verification_status,
            ]
        )

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column) + 2
        sheet.column_dimensions[column[0].column_letter].width = min(width, 45)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def build_batch_workbook(results: Iterable[dict]) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Batch Results"
    sheet.append(BATCH_EXPORT_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for result in results:
        metadata = result.get("metadata", {})
        classification = result.get("classification", {})
        extraction = result.get("extraction", {})
        sheet.append(
            [
                result.get("filename"),
                metadata.get("title"),
                "; ".join(author.get("name", "") for author in metadata.get("authors", [])),
                classification.get("publication_type") or "Not classified",
                classification.get("confidence"),
                classification.get("status") or result.get("status"),
                extraction.get("extraction_method"),
                metadata.get("doi"),
                metadata.get("metadata_confidence"),
                extraction.get("cleaned_text") or extraction.get("raw_text"),
                result.get("message"),
            ]
        )

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column) + 2
        sheet.column_dimensions[column[0].column_letter].width = min(width, 45)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output