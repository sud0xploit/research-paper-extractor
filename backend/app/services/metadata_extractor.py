import re


DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
LABEL_PATTERN = re.compile(r"^(title|authors?|journal|conference|publisher|volume|issue|pages?|article\s+number|issn|isbn)\s*:\s*(.+)$", re.IGNORECASE)
NON_TITLE_PATTERN = re.compile(
    r"\b(session|subject|sign|signature|principal|class\s+teacher|internal|external)\b|:-?",
    re.IGNORECASE,
)
RESEARCH_PAPER_KEYWORDS = (
    "introduction",
    "method",
    "methods",
    "results",
    "discussion",
    "conclusion",
    "journal",
    "conference",
    "authors",
    "doi",
    "volume",
    "issue",
    "published",
    "submitted",
    "abstract",
)
TITLE_STOP_PATTERN = re.compile(
    r"^(abstract|keywords?|introduction|authors?|by\b|journal|conference|department|university)\b",
    re.IGNORECASE,
)


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip()
    doi = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi\s*:\s*", "", doi, flags=re.IGNORECASE)
    return doi.rstrip(".,;:)]}>") or None


def extract_doi(text: str) -> str | None:
    match = DOI_PATTERN.search(text or "")
    return normalize_doi(match.group(0)) if match else None


def _labeled_fields(lines: list[str]) -> dict[str, str]:
    fields = {}
    for line in lines:
        match = LABEL_PATTERN.match(line)
        if match:
            label = re.sub(r"\s+", "_", match.group(1).lower())
            fields[label] = match.group(2).strip()
    return fields


def _split_authors(value: str | None) -> list[dict]:
    if not value:
        return []
    names = re.split(r"\s*(?:;|\band\b|\&)\s*|\s*,\s*(?=[A-Z][^,]+(?:,|$))", value)
    return [
        {"name": name.strip(), "order": index, "orcid": None, "affiliation": None}
        for index, name in enumerate(names, start=1)
        if name.strip()
    ]


def _fallback_author() -> dict:
    return {"name": "No author", "order": 1, "orcid": None, "affiliation": None}


def _first_title(lines: list[str], fields: dict[str, str]) -> str | None:
    if fields.get("title"):
        return fields["title"]
    title_lines = []
    for line in lines[:8]:
        if TITLE_STOP_PATTERN.match(line) or LABEL_PATTERN.match(line):
            break
        if NON_TITLE_PATTERN.search(line) or len(line.split()) < 2:
            if title_lines:
                break
            continue
        if title_lines and ("," in line or "@" in line):
            break
        if not title_lines and len(line.split()) < 3:
            continue
        title_lines.append(line)
    if title_lines:
        return " ".join(title_lines)
    return None


def _looks_like_research_paper(
    text: str,
    title: str | None,
    authors: list[dict],
    journal: str | None,
    conference: str | None,
    year: int | None,
) -> bool:
    lowered = (text or "").lower()
    keyword_hits = sum(1 for keyword in RESEARCH_PAPER_KEYWORDS if keyword in lowered)
    valid_title = bool(title and title != "No title recognized" and len(title.split()) >= 2)
    valid_author = bool(authors and authors[0].get("name") not in {None, "No author"})
    valid_publisher = bool(journal or conference)
    valid_year = year is not None
    return valid_title and (valid_author or valid_publisher or valid_year or keyword_hits >= 2)


def extract_metadata(text: str) -> dict:
    """Extract research-paper metadata and return a clear status for non-paper files."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    fields = _labeled_fields(lines)
    authors = _split_authors(fields.get("author") or fields.get("authors"))
    if not authors:
        authors = [_fallback_author()]

    doi = normalize_doi(fields.get("doi")) or extract_doi(text)
    year_match = YEAR_PATTERN.search(fields.get("year", "")) or YEAR_PATTERN.search(text or "")
    year_value = int(year_match.group(1)) if year_match else None

    title_value = _first_title(lines, fields)
    journal_value = fields.get("journal")
    conference_value = fields.get("conference")
    paper_like = _looks_like_research_paper(
        text,
        title_value,
        authors,
        journal_value,
        conference_value,
        year_value,
    )

    known_fields = [
        title_value,
        authors[0]["name"] if authors and authors[0]["name"] != "No author" else None,
        doi,
        year_value,
        journal_value or conference_value,
    ]
    confidence = round(sum(bool(field) for field in known_fields) / len(known_fields), 2)

    result = {
        "title": title_value if title_value is not None else "No title recognized",
        "authors": authors,
        "publication_year": year_value,
        "journal": journal_value,
        "conference": conference_value,
        "publisher": fields.get("publisher"),
        "volume": fields.get("volume"),
        "issue": fields.get("issue"),
        "pages": fields.get("page") or fields.get("pages"),
        "article_number": fields.get("article_number"),
        "doi": doi,
        "issn": fields.get("issn"),
        "isbn": fields.get("isbn"),
        "metadata_confidence": confidence,
        "is_research_paper": paper_like,
        "document_status": "RESEARCH_PAPER" if paper_like else "NOT_RESEARCH_PAPER",
    }

    if not paper_like:
        result["title"] = "Document is not a research paper"
        result["authors"] = [_fallback_author()]
        result["journal"] = None
        result["conference"] = None
        result["publication_year"] = None
        result["message"] = "Document is not a research paper"

    return result