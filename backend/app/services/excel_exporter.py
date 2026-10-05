import csv
from io import BytesIO, StringIO
from collections.abc import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.database.models import Publication
from app.schemas.metadata import ResearchPaperMetadata


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

METADATA_EXPORT_HEADERS = (
    "Paper Title",
    "Author Name",
    "Department",
    "Institution",
    "Location",
    "Journal Name",
    "Document Type",
    "Conference Name",
    "Publication Month",
    "Publication Year",
    "Print ISSN",
    "Electronic ISSN",
    "UGC CARE Status",
    "UGC CARE Link",
    "DOI",
    "Title Confidence",
    "Author Confidence",
    "Department Confidence",
    "Journal Confidence",
    "Publication Date Confidence",
    "ISSN Confidence",
    "UGC CARE Confidence",
    "DOI Confidence",
    "Missing Fields",
    "Warnings",
)


def metadata_export_rows(records: Iterable[dict]) -> list[list]:
    """Validate normalized records and map them once for both spreadsheet formats."""
    rows = []
    for record in records:
        metadata = ResearchPaperMetadata.model_validate(record)
        authors = [author for author in metadata.authors if author.name]
        rows.append(
            [
                metadata.paper_title,
                "; ".join(
                    f"{author.name} — {author.department}" if author.department else author.name
                    for author in authors
                ) or None,
                "; ".join(dict.fromkeys(author.department for author in authors if author.department)) or None,
                "; ".join(dict.fromkeys(author.institution for author in authors if author.institution)) or None,
                "; ".join(dict.fromkeys(author.location for author in authors if author.location)) or None,
                metadata.journal_name,
                metadata.document_type,
                metadata.conference_name,
                metadata.publication_date.month,
                metadata.publication_date.year,
                metadata.issn.print,
                metadata.issn.electronic,
                metadata.ugc_care.status,
                metadata.ugc_care.link,
                metadata.doi,
                metadata.confidence.paper_title,
                metadata.confidence.authors,
                metadata.confidence.departments,
                metadata.confidence.journal_name,
                metadata.confidence.publication_date,
                metadata.confidence.issn,
                metadata.confidence.ugc_care,
                metadata.confidence.doi,
                "; ".join(metadata.missing_fields) or None,
                "; ".join(metadata.warnings) or None,
            ]
        )
    return rows


def build_metadata_workbook(records: Iterable[dict]) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Research Paper Metadata"
    sheet.append(METADATA_EXPORT_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in metadata_export_rows(records):
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        values = [str(cell.value or "") for cell in column]
        width = min(max(max(map(len, values)) + 2, 12), 50)
        sheet.column_dimensions[column[0].column_letter].width = width
        for cell in column:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def build_metadata_csv(records: Iterable[dict]) -> BytesIO:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(METADATA_EXPORT_HEADERS)
    writer.writerows(metadata_export_rows(records))
    return BytesIO(output.getvalue().encode("utf-8-sig"))


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
                metadata.get("paper_title") or metadata.get("title"),
                "; ".join(author.get("name", "") for author in metadata.get("authors", [])),
                classification.get("publication_type") or "Not classified",
                classification.get("confidence"),
                classification.get("status") or result.get("status"),
                extraction.get("extraction_method"),
                metadata.get("doi"),
                metadata.get("confidence", {}).get("paper_title", metadata.get("metadata_confidence")),
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