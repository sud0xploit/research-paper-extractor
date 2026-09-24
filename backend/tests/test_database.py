from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.models import Author, Base, Document, Publication, ProcessingLog, Verification


def test_database_models_support_document_relationships() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        document = Document(filename="paper.pdf", storage_path="uploads/paper.pdf", file_type="pdf")
        publication = Publication(title="A database test", publication_type="Journal")
        publication.authors = [Author(name="First Author", author_order=1), Author(name="Second Author", author_order=2)]
        publication.verifications = [Verification(verification_type="DOI", status="Needs Verification")]
        document.publication = publication
        document.processing_logs = [ProcessingLog(stage="UPLOAD", status="SUCCESS", message="Stored")]
        session.add(document)
        session.commit()

        saved = session.query(Document).one()
        assert saved.publication.title == "A database test"
        assert [author.name for author in saved.publication.authors] == ["First Author", "Second Author"]
        assert saved.publication.verifications[0].status == "Needs Verification"
        assert saved.processing_logs[0].stage == "UPLOAD"