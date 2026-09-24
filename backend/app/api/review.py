from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import Publication, Verification


ReviewStatus = Literal["APPROVED", "REJECTED", "NEEDS_REVIEW"]
router = APIRouter(prefix="/api/review", tags=["review"])


class ReviewDecision(BaseModel):
    status: ReviewStatus
    reviewer: str = Field(min_length=1, max_length=255)
    remarks: str | None = None


def _review_item(publication: Publication) -> dict:
    return {
        "id": publication.id,
        "document_id": publication.document_id,
        "title": publication.title,
        "publication_type": publication.publication_type,
        "review_status": publication.review_status,
        "authors": [author.name for author in publication.authors],
    }


@router.get("")
def list_reviews(
    status: ReviewStatus = "NEEDS_REVIEW",
    database: Session = Depends(get_db),
) -> dict:
    publications = database.scalars(
        select(Publication)
        .where(Publication.review_status == status)
        .order_by(Publication.id)
    ).all()
    items = [_review_item(publication) for publication in publications]
    return {"items": items, "count": len(items)}


@router.patch("/{publication_id}")
def submit_review(
    publication_id: int,
    decision: ReviewDecision,
    database: Session = Depends(get_db),
) -> dict:
    publication = database.get(Publication, publication_id)
    if publication is None:
        raise HTTPException(status_code=404, detail="Publication not found")

    publication.review_status = decision.status
    database.add(
        Verification(
            publication_id=publication.id,
            verification_type="HUMAN_REVIEW",
            status=decision.status,
            source=decision.reviewer,
            evidence=decision.remarks,
            verification_date=datetime.now(timezone.utc),
            remarks=decision.remarks,
        )
    )
    database.commit()
    database.refresh(publication)
    return _review_item(publication)