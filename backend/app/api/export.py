from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Publication
from app.services.batch_processor import get_batch_results
from app.services.excel_exporter import build_batch_workbook, build_publications_workbook


ReviewFilter = Literal["APPROVED", "REJECTED", "NEEDS_REVIEW"]
router = APIRouter(prefix="/api/export", tags=["export"])


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