from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.database.models import Base, Document, Publication
from app.database.database import get_db
from app.main import app


def test_review_queue_and_submission_are_auditable() -> None:
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
                publication=Publication(title="A reviewable paper"),
            )
        )
        session.commit()

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        queue = client.get("/api/review")
        assert queue.status_code == 200
        assert queue.json()["count"] == 1

        publication_id = queue.json()["items"][0]["id"]
        response = client.patch(
            f"/api/review/{publication_id}",
            json={"status": "APPROVED", "reviewer": "reviewer@example.com", "remarks": "Confirmed"},
        )

        assert response.status_code == 200
        assert response.json()["review_status"] == "APPROVED"
        with Session(engine) as session:
            publication = session.get(Publication, publication_id)
            assert publication.review_status == "APPROVED"
            assert publication.verifications[0].verification_type == "HUMAN_REVIEW"
            assert publication.verifications[0].source == "reviewer@example.com"
    finally:
        app.dependency_overrides.pop(get_db, None)