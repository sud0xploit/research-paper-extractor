import json as json_module

import requests

from app.core.config import settings
from app.schemas.metadata import ResearchPaperMetadata
from app.services.semantic_metadata import _parse_model_response, extract_with_ollama


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": {"content": self.content}}


def _fallback() -> dict:
    return ResearchPaperMetadata(
        warnings=["Local structural extraction is active; no metadata-generating LLM provider is configured."],
    ).model_dump(mode="json")


def _response_payload() -> dict:
    return {
        "paper_title": "A Semantic Paper on Metadata",
        "authors": [{
            "name": "Ada Lovelace",
            "department": "Department of Computing",
            "institution": "Example University",
            "location": "London",
        }],
        "journal_name": "Journal of Example Research",
        "publication_date": {"month": "March", "year": "2024"},
        "issn": {"print": "2049-3630", "electronic": None},
        "ugc_care": {"status": "not_verified", "link": None},
        "doi": "10.1234/current.paper",
        "document_type": "journal",
        "conference_name": None,
        "confidence": {
            "paper_title": 0.97,
            "authors": 0.94,
            "departments": 0.93,
            "journal_name": 0.95,
            "publication_date": 0.97,
            "issn": 0.96,
            "ugc_care": 0.0,
            "doi": 0.97,
        },
        "evidence": {
            "paper_title": {"text": "Title: A Semantic Paper on Metadata", "page": 1},
            "authors": {"text": "Authors: Ada Lovelace", "page": 1},
            "departments": {"text": "Department of Computing, Example University, London", "page": 1},
            "journal_name": {"text": "Journal: Journal of Example Research", "page": 1},
            "publication_date": {"text": "Published: March 2024", "page": 1},
            "issn": {"text": "Print ISSN: 2049-3630", "page": 1},
            "ugc_care": None,
            "doi": {"text": "DOI: 10.1234/current.paper", "page": 1},
        },
        "warnings": [],
        "missing_fields": [],
    }


def test_ollama_structured_output_accepts_only_evidenced_fields(monkeypatch) -> None:
    monkeypatch.setattr(settings, "metadata_provider", "ollama")
    payload = _response_payload()
    request_data = {}

    def fake_post(url, json, timeout):
        request_data.update(json)
        return FakeResponse(content=json_module.dumps(payload))

    monkeypatch.setattr("app.services.semantic_metadata.requests.post", fake_post)
    text = """Title: A Semantic Paper on Metadata
Authors: Ada Lovelace
Department of Computing, Example University, London
Journal: Journal of Example Research
Published: March 2024
Print ISSN: 2049-3630
DOI: 10.1234/current.paper
Abstract
References
Cited paper DOI: 10.9999/reference.paper
"""

    result = extract_with_ollama(text, _fallback())

    assert request_data["format"]["required"] == list(request_data["format"]["properties"])
    assert request_data["format"]["properties"]["paper_title"]
    assert "Cited paper DOI" not in request_data["messages"][1]["content"]
    assert result["paper_title"] == "A Semantic Paper on Metadata"
    assert result["authors"][0]["department"] == "Department of Computing"
    assert result["doi"] == "10.1234/current.paper"
    assert result["confidence"]["paper_title"] <= 0.94
    assert result["evidence"]["paper_title"]["source"] == "Ollama:qwen2:7b"
    assert result["ugc_care"] == {"status": "not_verified", "link": None}


def test_ollama_discards_metadata_whose_evidence_is_not_in_the_document(monkeypatch) -> None:
    monkeypatch.setattr(settings, "metadata_provider", "ollama")
    payload = _response_payload()
    payload["paper_title"] = "Invented Title"
    payload["evidence"]["paper_title"]["text"] = "Journal: Journal of Example Research"
    monkeypatch.setattr(
        "app.services.semantic_metadata.requests.post",
        lambda *args, **kwargs: FakeResponse(json_module.dumps(payload)),
    )

    result = extract_with_ollama("Title: Actual Paper Title", _fallback())

    assert result["paper_title"] is None
    assert any("title evidence did not match" in warning for warning in result["warnings"])


def test_ollama_failure_returns_structural_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "metadata_provider", "ollama")
    monkeypatch.setattr(
        "app.services.semantic_metadata.requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError("Ollama is offline")),
    )

    result = extract_with_ollama("Title: Actual Paper Title", _fallback())

    assert result["paper_title"] is None
    assert any("Ollama metadata extraction failed" in warning for warning in result["warnings"])


def test_invalid_model_issn_is_discarded_without_losing_other_fields() -> None:
    payload = _response_payload()
    payload["issn"]["print"] = "1331-2292"

    parsed = _parse_model_response(json_module.dumps(payload))

    assert parsed.issn.print is None
    assert parsed.paper_title == "A Semantic Paper on Metadata"
    assert any("invalid print ISSN" in warning for warning in parsed.warnings)


def test_model_enrichment_keeps_supported_journal_date_and_discards_other_fields(monkeypatch) -> None:
    monkeypatch.setattr(settings, "metadata_provider", "ollama")
    payload = _response_payload()
    payload["paper_title"] = "Unrelated Hallucinated Title"
    payload["authors"] = [{"name": "Unrelated Author"}]
    payload["journal_name"] = "The EUROCALL Review"
    payload["publication_date"] = {"month": "September", "year": "2017"}
    payload["evidence"]["paper_title"] = {"text": "The EUROCALL Review, Volume 25, No. 2, September 2017", "page": 1}
    payload["evidence"]["authors"] = {"text": "Krzysztof Kowalski", "page": 1}
    payload["evidence"]["journal_name"] = {"text": "The EUROCALL Review", "page": 1}
    payload["evidence"]["publication_date"] = {"text": "September 2017", "page": 1}
    monkeypatch.setattr(
        "app.services.semantic_metadata.requests.post",
        lambda *args, **kwargs: FakeResponse(json_module.dumps(payload)),
    )

    text = """The EUROCALL Review, Volume 25, No. 2, September 2017
True Paper Title
Jane Doe
Abstract
"""
    result = extract_with_ollama(text, _fallback())

    assert result["paper_title"] is None
    assert result["authors"] == []
    assert result["journal_name"] == "The EUROCALL Review"
    assert result["publication_date"] == {"month": "September", "year": "2017"}
    assert result["ugc_care"] == {"status": "not_verified", "link": None}
    assert result["evidence"]["journal_name"]["source"] == "Ollama:qwen2:7b"