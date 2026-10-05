from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Publication
from app.services.batch_processor import get_batch_results
from app.schemas.metadata import ResearchPaperMetadata
from app.services.excel_exporter import (
    build_batch_workbook,
    build_metadata_csv,
    build_metadata_workbook,
    build_publications_workbook,
)


ReviewFilter = Literal["APPROVED", "REJECTED", "NEEDS_REVIEW"]
router = APIRouter(prefix="/api/export", tags=["export"])


class MetadataExportRequest(BaseModel):
    records: list[ResearchPaperMetadata] = Field(min_length=1)


@router.post("/metadata/excel")
def export_metadata_excel(request: MetadataExportRequest) -> StreamingResponse:
    workbook = build_metadata_workbook([record.model_dump(mode="json") for record in request.records])
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Research_Paper_Metadata.xlsx"'},
    )


@router.post("/metadata/csv")
def export_metadata_csv(request: MetadataExportRequest) -> StreamingResponse:
    content = build_metadata_csv([record.model_dump(mode="json") for record in request.records])
    return StreamingResponse(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="Research_Paper_Metadata.csv"'},
    )


@router.get("/excel")
def export_excel(
    status: ReviewFilter | None = None,
    job_id: str | None = None,
    database: Session = Depends(get_db),
) -> StreamingResponse:
    if job_id is not None:
        results = get_batch_results(job_id)
        if results is not None:
            workbook = build_batch_workbook(results)
            return StreamingResponse(
                workbook,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={job_id}-results.xlsx"},
            )

    statement = select(Publication).order_by(Publication.id)
    if status is not None:
        statement = statement.where(Publication.review_status == status)
    publications = database.scalars(statement).all()
    workbook = build_publications_workbook(publications)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=publications.xlsx"},
    )