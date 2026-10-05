import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AuthorMetadata(BaseModel):
    name: str | None = None
    department: str | None = None
    institution: str | None = None
    location: str | None = None


class PublicationDate(BaseModel):
    month: str | None = None
    year: str | None = None

    @field_validator("month")
    @classmethod
    def normalize_month(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        months = {
            month.casefold(): month
            for month in (
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            )
        }
        normalized = months.get(value.strip().casefold())
        if normalized is None:
            raise ValueError("Publication month must be a month name or null.")
        return normalized

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not re.fullmatch(r"(?:19|20)\d{2}", normalized):
            raise ValueError("Publication year must be a four-digit year or null.")
        return normalized


class ISSNMetadata(BaseModel):
    print: str | None = None
    electronic: str | None = None

    @field_validator("print", "electronic")
    @classmethod
    def validate_issn(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        digits = value.replace("-", "").replace(" ", "").upper()
        if not re.fullmatch(r"\d{7}[\dX]", digits):
            raise ValueError("ISSN must use the NNNN-NNNN format.")
        checksum = sum(int(digit) * weight for digit, weight in zip(digits[:7], range(8, 1, -1)))
        check_digit = (11 - checksum % 11) % 11
        expected = "X" if check_digit == 10 else str(check_digit)
        if digits[-1] != expected:
            raise ValueError("ISSN checksum is invalid.")
        return f"{digits[:4]}-{digits[4:]}"


class UGCCareMetadata(BaseModel):
    status: Literal["verified", "not_verified", "not_applicable", "unknown"] = "unknown"
    link: str | None = None


class MetadataConfidence(BaseModel):
    paper_title: float = Field(default=0.0, ge=0.0, le=1.0)
    authors: float = Field(default=0.0, ge=0.0, le=1.0)
    departments: float = Field(default=0.0, ge=0.0, le=1.0)
    journal_name: float = Field(default=0.0, ge=0.0, le=1.0)
    publication_date: float = Field(default=0.0, ge=0.0, le=1.0)
    issn: float = Field(default=0.0, ge=0.0, le=1.0)
    ugc_care: float = Field(default=0.0, ge=0.0, le=1.0)
    doi: float = Field(default=0.0, ge=0.0, le=1.0)


class EvidenceSnippet(BaseModel):
    text: str
    page: int | None = None
    source: str | None = None


class MetadataEvidence(BaseModel):
    paper_title: EvidenceSnippet | None = None
    authors: EvidenceSnippet | None = None
    departments: EvidenceSnippet | None = None
    journal_name: EvidenceSnippet | None = None
    publication_date: EvidenceSnippet | None = None
    issn: EvidenceSnippet | None = None
    ugc_care: EvidenceSnippet | None = None
    doi: EvidenceSnippet | None = None


class ResearchPaperMetadata(BaseModel):
    paper_title: str | None = None
    authors: list[AuthorMetadata] = Field(default_factory=list)
    journal_name: str | None = None
    publication_date: PublicationDate = Field(default_factory=PublicationDate)
    issn: ISSNMetadata = Field(default_factory=ISSNMetadata)
    ugc_care: UGCCareMetadata = Field(default_factory=UGCCareMetadata)
    doi: str | None = None
    document_type: Literal["journal", "conference", "unknown"] = "unknown"
    conference_name: str | None = None
    confidence: MetadataConfidence = Field(default_factory=MetadataConfidence)
    evidence: MetadataEvidence = Field(default_factory=MetadataEvidence)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("doi")
    @classmethod
    def normalize_doi(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        normalized = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"^doi\s*:\s*", "", normalized, flags=re.IGNORECASE)
        normalized = normalized.rstrip(".,;:)]}>")
        if not re.fullmatch(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", normalized, re.IGNORECASE):
            raise ValueError("DOI must be a normalized DOI identifier or null.")
        return normalized

    @model_validator(mode="after")
    def normalize_document_specific_fields(self):
        if self.document_type == "conference":
            self.journal_name = None
            self.ugc_care = UGCCareMetadata(status="not_applicable", link=None)
        if self.ugc_care.status == "verified" and not self.ugc_care.link:
            raise ValueError("A verified UGC CARE status requires its source link.")
        if self.ugc_care.link and not re.match(r"^https?://", self.ugc_care.link, re.IGNORECASE):
            raise ValueError("UGC CARE link must be an HTTP(S) URL.")

        missing = []
        if not self.paper_title:
            missing.append("paper_title")
        named_authors = [author for author in self.authors if author.name]
        if not named_authors:
            missing.append("authors")
        if named_authors and any(author.department is None for author in named_authors):
            missing.append("author_departments")
        if self.document_type == "journal" and not self.journal_name:
            missing.append("journal_name")
        if not self.publication_date.year:
            missing.append("publication_date")
        if not self.issn.print and not self.issn.electronic:
            missing.append("issn")
        if self.document_type == "journal" and not self.ugc_care.link:
            missing.append("ugc_care.link")
        if self.document_type == "conference" and not self.conference_name:
            missing.append("conference_name")
        if not self.doi:
            missing.append("doi")
        self.missing_fields = missing
        return self