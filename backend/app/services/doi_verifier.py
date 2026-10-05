import os
import re
from html.parser import HTMLParser
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import quote

import requests

from app.services.metadata_extractor import normalize_doi


CROSSREF_API_URL = "https://api.crossref.org/works/"


def _normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def _last_name(value: str | None) -> str:
    words = re.findall(r"[a-z0-9]+", (value or "").casefold())
    return words[-1] if words else ""


def _title_similarity(first: str | None, second: str | None) -> float | None:
    if not first or not second:
        return None
    return SequenceMatcher(None, _normalized(first), _normalized(second)).ratio()


def _author_similarity(extracted: list[dict], crossref: list[dict]) -> float | None:
    if not extracted or not crossref:
        return None
    extracted_names = {_last_name(author.get("name")) for author in extracted}
    crossref_names = {
        _last_name(author.get("family"))
        for author in crossref
    }
    extracted_names.discard("")
    crossref_names.discard("")
    if not extracted_names or not crossref_names:
        return None
    return len(extracted_names & crossref_names) / max(len(extracted_names), len(crossref_names))


def _crossref_year(message: dict) -> int | None:
    for field in ("published-print", "published-online", "published", "issued"):
        parts = message.get(field, {}).get("date-parts", [])
        if parts and parts[0]:
            return parts[0][0]
    return None


def _crossref_month(message: dict) -> int | None:
    for field in ("published-print", "published-online", "published", "issued"):
        parts = message.get(field, {}).get("date-parts", [])
        if parts and parts[0] and len(parts[0]) > 1:
            return parts[0][1]
    return None


class _PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def _issn_media(issn: str) -> str | None:
    try:
        response = requests.get(
            f"https://portal.issn.org/resource/ISSN/{quote(issn, safe='')}",
            headers={"User-Agent": "ResearchDocumentExtractor/0.1"},
            timeout=8,
        )
        response.raise_for_status()
        parser = _PageTextParser()
        parser.feed(response.text)
        page_text = " ".join(parser.parts).casefold()
    except requests.RequestException:
        return None
    if re.search(r"medium\s*:?\s*print", page_text):
        return "print"
    if re.search(r"medium\s*:?\s*(?:online|electronic)", page_text):
        return "electronic"
    return None


def _crossref_authors(message: dict) -> list[dict]:
    authors = []
    for author in message.get("author", []):
        name = " ".join(part for part in (author.get("given"), author.get("family")) if part).strip()
        if not name:
            continue
        affiliations = [
            affiliation.get("name", "").strip()
            for affiliation in author.get("affiliation", [])
            if affiliation.get("name")
        ]
        authors.append({"name": name, "affiliations": affiliations})
    return authors


def verify_doi(doi: str | None, metadata: dict | None = None) -> dict:
    """Verify a DOI against Crossref metadata and report comparison evidence."""
    normalized_doi = normalize_doi(doi)
    result = {
        "doi": normalized_doi,
        "verified": False,
        "source": "Crossref",
        "verification_date": datetime.now(timezone.utc).isoformat(),
        "confidence": 0.0,
        "title_similarity": None,
        "author_similarity": None,
        "year_match": None,
        "container_match": None,
        "crossref_month": None,
        "crossref_issn": [],
        "crossref_issn_formats": {},
        "crossref_authors": [],
        "crossref_container": None,
        "crossref_type": None,
    }
    if not normalized_doi:
        result["remarks"] = "No DOI was extracted."
        return result

    try:
        response = requests.get(
            f"{CROSSREF_API_URL}{quote(normalized_doi, safe='')}",
            headers={"User-Agent": "ResearchDocumentExtractor/0.1"},
            params={"mailto": os.getenv("CROSSREF_MAILTO", "")} ,
            timeout=10,
        )
        response.raise_for_status()
        message = response.json().get("message", {})
    except (requests.RequestException, ConnectionError, ValueError) as error:
        result["remarks"] = f"Crossref verification unavailable: {error}"
        return result

    metadata = metadata or {}
    crossref_title = (message.get("title") or [None])[0]
    crossref_issn = message.get("ISSN") or []
    issn_formats = {issn: _issn_media(issn) for issn in crossref_issn}
    title_similarity = _title_similarity(metadata.get("title"), crossref_title)
    author_similarity = _author_similarity(metadata.get("authors", []), message.get("author", []))
    crossref_year = _crossref_year(message)
    year_match = (
        metadata.get("publication_year") is not None
        and crossref_year is not None
        and metadata["publication_year"] == crossref_year
    ) if metadata.get("publication_year") is not None and crossref_year is not None else None
    expected_container = metadata.get("journal") or metadata.get("conference")
    crossref_container = (message.get("container-title") or [None])[0]
    container_similarity = _title_similarity(expected_container, crossref_container)
    container_match = container_similarity >= 0.75 if container_similarity is not None else None

    comparisons = [value for value in (title_similarity, author_similarity, container_similarity) if value is not None]
    if year_match is not None:
        comparisons.append(1.0 if year_match else 0.0)
    confidence = sum(comparisons) / len(comparisons) if comparisons else 0.0
    verified = bool(title_similarity is not None and title_similarity >= 0.80)
    if author_similarity is not None:
        verified = verified and author_similarity >= 0.50
    if year_match is False:
        verified = False
    if container_match is False and expected_container:
        verified = False

    result.update(
        {
            "verified": verified,
            "confidence": round(confidence, 2),
            "title_similarity": round(title_similarity, 2) if title_similarity is not None else None,
            "author_similarity": round(author_similarity, 2) if author_similarity is not None else None,
            "year_match": year_match,
            "container_match": container_match,
            "crossref_title": crossref_title,
            "crossref_year": crossref_year,
            "crossref_month": _crossref_month(message),
            "crossref_issn": crossref_issn,
            "crossref_issn_formats": issn_formats,
            "crossref_authors": _crossref_authors(message),
            "crossref_container": crossref_container,
            "crossref_type": message.get("type"),
        }
    )
    return result