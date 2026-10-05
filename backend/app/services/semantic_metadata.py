import json
import re
import unicodedata
from collections.abc import Mapping

import requests
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.metadata import (
    AuthorMetadata,
    EvidenceSnippet,
    ISSNMetadata,
    MetadataConfidence,
    MetadataEvidence,
    PublicationDate,
    ResearchPaperMetadata,
)


REFERENCES_PATTERN = re.compile(r"^\s*(?:references|bibliography|works\s+cited)\s*:?\s*$", re.IGNORECASE)
DATE_EXCLUSION_PATTERN = re.compile(r"\b(received|revised|accepted|submitted)\b", re.IGNORECASE)
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
ISSN_PATTERN = re.compile(r"\b\d{4}-?\d{3}[\dX]\b", re.IGNORECASE)

SYSTEM_PROMPT = """You extract bibliographic metadata from research papers.
Use only the supplied page-one text blocks, which include PDF visual coordinates and have been truncated at the References section.
Use block positions to distinguish running headers from the article title and to associate author names with nearby same-column affiliations.
Return only the requested JSON object matching the supplied schema.
Do not guess. Use null for unavailable scalar fields and [] when no authors can be identified.
Extract only the current paper's title-page authors, not authors mentioned in the body.
Map numbered/superscript affiliations to the corresponding authors. Never infer a department from an institution.
Classify as journal only when the containing journal is identifiable; classify as conference only with proceedings/conference evidence; otherwise use unknown.
Publication date excludes received, revised, accepted, and submitted dates. Do not guess a month.
Use only ISSNs explicitly tied to the current journal. DOI must belong to this paper, not a citation.
UGC CARE is not verified by this local model. Always use not_verified for journal papers or not_applicable for conference papers, with a null link; never construct a URL.
For each non-null field, provide a short verbatim evidence snippet and page number when visible. Evidence must be copied from the supplied text.
Confidence must be conservative: high only for explicit, unambiguous evidence."""


def _paper_text(document: str | Mapping) -> str:
    if isinstance(document, Mapping):
        layout_blocks = document.get("cleaned_layout_blocks") or document.get("layout_blocks_by_page") or []
        if layout_blocks and layout_blocks[0]:
            page_texts = []
            in_references = False
            for page_number, blocks in enumerate(layout_blocks[:1], start=1):
                page_blocks = []
                for block in blocks:
                    text = str(block.get("text") or "").strip()
                    if REFERENCES_PATTERN.match(text):
                        in_references = True
                        break
                    if text:
                        page_blocks.append(
                            f"[BLOCK x={block.get('x0', 0):.0f} y={block.get('y0', 0):.0f}]\n{text}"
                        )
                page_texts.append(f"[PAGE {page_number}]\n" + "\n\n".join(page_blocks))
                if in_references:
                    break
            return "\n\n".join(page_texts)[:12000]
        pages = document.get("cleaned_layout_page_texts") or document.get("layout_page_texts") or document.get("cleaned_page_texts") or document.get("page_texts") or [
            document.get("cleaned_text") or document.get("raw_text", "")
        ]
    else:
        pages = [document or ""]
    accepted_pages = []
    in_references = False
    for page_number, page in enumerate(pages, start=1):
        if in_references:
            break
        lines = str(page).splitlines()
        reference_index = next(
            (index for index, line in enumerate(lines) if REFERENCES_PATTERN.match(line)),
            None,
        )
        if reference_index is not None:
            lines = lines[:reference_index]
            in_references = True
        accepted_pages.append(f"[PAGE {page_number}]\n" + "\n".join(lines))
    return "\n\n".join(accepted_pages[:1])[:7000]


def _normalized_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def _evidence_text(evidence) -> str | None:
    return evidence.text if evidence is not None else None


def _evidence_is_present(evidence, source_text: str) -> bool:
    snippet = _evidence_text(evidence)
    if not snippet or _normalized_text(snippet) not in _normalized_text(source_text):
        return False
    if evidence.page is None:
        return True
    page_match = re.search(
        rf"\[PAGE\s+{evidence.page}\](.*?)(?=\[PAGE\s+\d+\]|$)",
        source_text,
        re.IGNORECASE | re.DOTALL,
    )
    return bool(page_match and _normalized_text(snippet) in _normalized_text(page_match.group(1)))


def _evidence_is_on_page_one(evidence, source_text: str) -> bool:
    if evidence is None or evidence.page not in (None, 1):
        return False
    page_match = re.search(r"\[PAGE\s+1\](.*?)(?=\[PAGE\s+\d+\]|$)", source_text, re.IGNORECASE | re.DOTALL)
    page_text = page_match.group(1) if page_match else source_text
    return bool(evidence.text and _normalized_text(evidence.text) in _normalized_text(page_text))


def _first_page_metadata(source_text: str) -> str:
    first_page = source_text.split("[PAGE 2]", 1)[0]
    header_end = re.search(
        r"^\s*(?:abstract|keywords?|introduction)\b",
        first_page,
        re.IGNORECASE | re.MULTILINE,
    )
    return first_page[:header_end.start()] if header_end else first_page


def _field_evidence(record: ResearchPaperMetadata, name: str) -> dict | None:
    evidence = getattr(record.evidence, name)
    return evidence.model_dump(mode="json") if evidence is not None else None


def _evidence_source(record: dict, field: str) -> str | None:
    evidence = record.get("evidence", {}).get(field)
    return evidence.get("source") if isinstance(evidence, dict) else None


def _strict_json_schema() -> dict:
    schema = ResearchPaperMetadata.model_json_schema()

    def require_properties(value: dict) -> None:
        if value.get("type") == "object" and isinstance(value.get("properties"), dict):
            value["required"] = list(value["properties"])
            value["additionalProperties"] = False
            for property_schema in value["properties"].values():
                if isinstance(property_schema, dict):
                    require_properties(property_schema)
        for definition in value.get("$defs", {}).values():
            require_properties(definition)

    require_properties(schema)
    return schema


def _score(value: float, fallback_score: float = 0.0) -> float:
    return round(min(max(float(value), 0.0), 0.94), 2) if value else fallback_score


def _string_or_none(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _parse_model_response(content: str) -> ResearchPaperMetadata:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("The Ollama response must be a JSON object.")

    warnings = []
    confidence_values = {}
    raw_confidence = payload.get("confidence") if isinstance(payload.get("confidence"), dict) else {}
    for field in MetadataConfidence.model_fields:
        try:
            value = float(raw_confidence.get(field, 0.0))
            confidence_values[field] = min(max(value, 0.0), 1.0)
        except (TypeError, ValueError):
            confidence_values[field] = 0.0
            warnings.append(f"Invalid model confidence for {field} was reset to zero.")

    raw_evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    evidence_values = {}
    for field in MetadataEvidence.model_fields:
        value = raw_evidence.get(field)
        try:
            evidence_values[field] = EvidenceSnippet.model_validate(value) if value else None
        except ValidationError:
            evidence_values[field] = None
            warnings.append(f"Malformed model evidence for {field} was discarded.")

    authors = []
    for author_payload in payload.get("authors", []) if isinstance(payload.get("authors"), list) else []:
        try:
            authors.append(AuthorMetadata.model_validate(author_payload))
        except ValidationError:
            warnings.append("A malformed model author record was discarded.")

    raw_date = payload.get("publication_date") if isinstance(payload.get("publication_date"), dict) else {}
    try:
        publication_date = PublicationDate(
            month=_string_or_none(raw_date.get("month")),
            year=_string_or_none(raw_date.get("year")),
        )
    except ValidationError:
        try:
            publication_date = PublicationDate(year=_string_or_none(raw_date.get("year")))
        except ValidationError:
            publication_date = PublicationDate()
        warnings.append("An invalid model publication date was discarded.")

    raw_issn = payload.get("issn") if isinstance(payload.get("issn"), dict) else {}
    issn_values = {}
    for field in ("print", "electronic"):
        value = _string_or_none(raw_issn.get(field))
        try:
            issn_values[field] = ISSNMetadata(**{field: value}).model_dump()[field]
        except ValidationError:
            issn_values[field] = None
            warnings.append(f"The model's invalid {field} ISSN was discarded.")

    raw_doi = _string_or_none(payload.get("doi"))
    try:
        doi = ResearchPaperMetadata(doi=raw_doi).doi
    except ValidationError:
        doi = None
        warnings.append("The model's invalid DOI was discarded.")

    document_type = payload.get("document_type")
    if document_type not in {"journal", "conference", "unknown"}:
        document_type = "unknown"
        warnings.append("The model's invalid document type was changed to unknown.")

    return ResearchPaperMetadata(
        paper_title=_string_or_none(payload.get("paper_title")),
        authors=authors,
        journal_name=_string_or_none(payload.get("journal_name")),
        publication_date=publication_date,
        issn=ISSNMetadata(**issn_values),
        ugc_care={"status": "unknown", "link": None},
        doi=doi,
        document_type=document_type,
        conference_name=_string_or_none(payload.get("conference_name")),
        confidence=MetadataConfidence(**confidence_values),
        evidence=MetadataEvidence(**evidence_values),
        warnings=warnings,
    )


def _merge_evidenced_metadata(
    response: ResearchPaperMetadata,
    fallback: dict,
    source_text: str,
) -> dict:
    result = ResearchPaperMetadata.model_validate(fallback).model_dump(mode="json")
    warnings = list(result["warnings"])
    warnings = [warning for warning in warnings if "no metadata-generating LLM" not in warning]
    warnings.extend(response.warnings)
    warnings.append(f"Structured metadata extraction used local Ollama model {settings.ollama_model}.")

    if (
        response.paper_title
        and _evidence_source(fallback, "paper_title") != "PDF + Crossref"
        and _evidence_is_on_page_one(response.evidence.paper_title, source_text)
        and _normalized_text(response.paper_title) in _normalized_text(response.evidence.paper_title.text)
    ):
        result["paper_title"] = response.paper_title
        result["evidence"]["paper_title"] = _field_evidence(response, "paper_title")
        result["evidence"]["paper_title"]["source"] = f"Ollama:{settings.ollama_model}"
        result["confidence"]["paper_title"] = (
            fallback["confidence"]["paper_title"]
            if response.paper_title == fallback["paper_title"]
            else _score(response.confidence.paper_title)
        )
    elif response.paper_title:
        warnings.append("The model's title evidence did not match supplied paper text; its title was discarded.")

    author_evidence = response.evidence.authors
    if (
        response.authors
        and _evidence_source(fallback, "authors") != "Crossref"
        and _evidence_is_on_page_one(author_evidence, source_text)
        and all(
        author.name and _normalized_text(author.name) in _normalized_text(author_evidence.text)
        for author in response.authors
        )
    ):
        result["authors"] = [author.model_dump(mode="json") for author in response.authors]
        result["evidence"]["authors"] = _field_evidence(response, "authors")
        result["evidence"]["authors"]["source"] = f"Ollama:{settings.ollama_model}"
        result["confidence"]["authors"] = (
            fallback["confidence"]["authors"]
            if result["authors"] == fallback["authors"]
            else _score(response.confidence.authors)
        )
    elif response.authors:
        warnings.append("Model authors were discarded because the cited author evidence did not verify every name.")

    department_evidence = response.evidence.departments
    if _evidence_is_on_page_one(department_evidence, source_text):
        evidence_text = _normalized_text(department_evidence.text)
        verified_authors = []
        for author in response.authors:
            updates = {}
            for field in ("department", "institution", "location"):
                value = getattr(author, field)
                if value and _normalized_text(value) not in evidence_text:
                    updates[field] = None
                    warnings.append(f"The model's unsupported author {field} was discarded.")
            verified_authors.append(author.model_copy(update=updates))
        result_authors_by_name = {author["name"]: author for author in result["authors"]}
        for author in verified_authors:
            existing = result_authors_by_name.get(author.name)
            if existing:
                existing.update(
                    {field: getattr(author, field) for field in ("department", "institution", "location")}
                )
        if any(author.get("department") for author in result["authors"]):
            result["evidence"]["departments"] = _field_evidence(response, "departments")
            result["evidence"]["departments"]["source"] = f"Ollama:{settings.ollama_model}"
            result["confidence"]["departments"] = _score(response.confidence.departments)

    journal_evidence = response.evidence.journal_name
    if (
        response.journal_name
        and _evidence_source(fallback, "journal_name") != "Crossref"
        and _evidence_is_on_page_one(journal_evidence, source_text)
        and _normalized_text(response.journal_name) in _normalized_text(journal_evidence.text)
    ):
        result["journal_name"] = response.journal_name
        result["evidence"]["journal_name"] = _field_evidence(response, "journal_name")
        result["evidence"]["journal_name"]["source"] = f"Ollama:{settings.ollama_model}"
        result["confidence"]["journal_name"] = (
            fallback["confidence"]["journal_name"]
            if response.journal_name == fallback["journal_name"]
            else _score(response.confidence.journal_name)
        )

    date_evidence = response.evidence.publication_date
    if (
        _evidence_is_on_page_one(date_evidence, source_text)
        and _evidence_source(fallback, "publication_date") != "Crossref"
        and not DATE_EXCLUSION_PATTERN.search(date_evidence.text)
        and response.publication_date.year
        and response.publication_date.year in date_evidence.text
        and (
            not response.publication_date.month
            or response.publication_date.month.casefold() in date_evidence.text.casefold()
        )
    ):
        result["publication_date"] = response.publication_date.model_dump(mode="json")
        result["evidence"]["publication_date"] = _field_evidence(response, "publication_date")
        result["evidence"]["publication_date"]["source"] = f"Ollama:{settings.ollama_model}"
        result["confidence"]["publication_date"] = (
            fallback["confidence"]["publication_date"]
            if result["publication_date"] == fallback["publication_date"]
            else _score(response.confidence.publication_date)
        )

    issn_evidence = response.evidence.issn
    if (
        _evidence_is_on_page_one(issn_evidence, source_text)
        and _evidence_source(fallback, "issn") != "Crossref + ISSN International Centre"
        and re.search(
            r"\b(?:print\s+issn|electronic\s+issn|online\s+issn|e-?issn|issn)\b",
            issn_evidence.text,
            re.IGNORECASE,
        )
    ):
        evidenced_values = {value.replace("-", "").casefold() for value in ISSN_PATTERN.findall(issn_evidence.text)}
        candidate_values = {
            value.replace("-", "").casefold()
            for value in (response.issn.print, response.issn.electronic)
            if value
        }
        if candidate_values and candidate_values.issubset(evidenced_values):
            result["issn"] = response.issn.model_dump(mode="json")
            result["evidence"]["issn"] = _field_evidence(response, "issn")
            result["evidence"]["issn"]["source"] = f"Ollama:{settings.ollama_model}"
            result["confidence"]["issn"] = (
                fallback["confidence"]["issn"]
                if result["issn"] == fallback["issn"]
                else _score(response.confidence.issn)
            )

    doi_evidence = response.evidence.doi
    if (
        response.doi
        and _evidence_source(fallback, "doi") != "PDF + Crossref"
        and _evidence_is_present(doi_evidence, source_text)
        and response.doi.casefold() in doi_evidence.text.casefold()
        and re.search(r"\bdoi\b|doi\.org", doi_evidence.text, re.IGNORECASE)
    ):
        metadata_block = _first_page_metadata(source_text)
        block_dois = {value.casefold() for value in DOI_PATTERN.findall(metadata_block)}
        explicitly_labeled = bool(re.search(r"\bdoi\b|doi\.org", doi_evidence.text, re.IGNORECASE))
        crossref_verified = response.doi.casefold() == (fallback.get("doi") or "").casefold()
        if (response.doi.casefold() in block_dois and explicitly_labeled) or crossref_verified:
            result["doi"] = response.doi
            result["evidence"]["doi"] = _field_evidence(response, "doi")
            result["evidence"]["doi"]["source"] = f"Ollama:{settings.ollama_model}"
            result["confidence"]["doi"] = (
                fallback["confidence"]["doi"]
                if response.doi == fallback["doi"]
                else _score(response.confidence.doi)
            )
        elif response.doi != fallback.get("doi"):
            warnings.append("The model DOI was discarded because current-paper ownership was ambiguous.")

    if response.document_type == "conference" and response.conference_name:
        conference_evidence = response.evidence.journal_name
        if _evidence_is_present(conference_evidence, source_text) and re.search(
            r"proceedings|conference", conference_evidence.text, re.IGNORECASE
        ):
            result["document_type"] = "conference"
            result["journal_name"] = None
            result["conference_name"] = response.conference_name
            result["ugc_care"] = {"status": "not_applicable", "link": None}
    elif response.document_type == "journal" and result["journal_name"]:
        result["document_type"] = "journal"
        result["conference_name"] = None

    if result["document_type"] == "conference":
        result["ugc_care"] = {"status": "not_applicable", "link": None}
    elif result["document_type"] == "journal":
        result["ugc_care"] = {"status": "not_verified", "link": None}
        if not any("UGC CARE" in warning for warning in warnings):
            warnings.append("UGC CARE status was not verified because no authoritative UGC CARE source is configured.")
    else:
        result["ugc_care"] = fallback["ugc_care"]
    result["warnings"] = list(dict.fromkeys(warnings))
    return ResearchPaperMetadata.model_validate(result).model_dump(mode="json")


def extract_with_ollama(document: str | Mapping, fallback: dict) -> dict:
    if settings.metadata_provider.casefold() not in {"ollama", "local-llm"}:
        return fallback

    source_text = _paper_text(document)
    if not source_text.strip():
        return fallback
    try:
        response = requests.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": source_text},
                ],
                "format": _strict_json_schema(),
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        content = response.json()["message"]["content"]
        parsed = _parse_model_response(content)
        return _merge_evidenced_metadata(parsed, fallback, source_text)
    except (requests.RequestException, KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as error:
        result = ResearchPaperMetadata.model_validate(fallback).model_dump(mode="json")
        result["warnings"].append(
            f"Ollama metadata extraction failed; structural extraction was retained ({type(error).__name__})."
        )
        return result