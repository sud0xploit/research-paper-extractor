import pytest

from app.core.config import settings
from app.services.metadata_extractor import extract_doi, extract_metadata, normalize_doi


@pytest.fixture(autouse=True)
def use_structural_provider(monkeypatch) -> None:
    monkeypatch.setattr(settings, "metadata_provider", "local")
    monkeypatch.setattr(settings, "crossref_metadata_verification", False)


def test_metadata_extractor_returns_labeled_fields_and_dynamic_authors() -> None:
    text = """Title: Local Extraction for Research Papers
Authors: Ada Lovelace; Alan Turing; Grace Hopper; Katherine Johnson; Tim Berners-Lee
Journal: Computing Research
Publisher: Example Press
Volume: 12
Issue: 3
Pages: 44-58
Publication date: March 2024
DOI: https://doi.org/10.1234/example.2024.
Print ISSN: 2049-3630
"""

    result = extract_metadata(text)

    assert result["paper_title"] == "Local Extraction for Research Papers"
    assert len(result["authors"]) == 5
    assert result["authors"][4]["name"] == "Tim Berners-Lee"
    assert result["doi"] == "10.1234/example.2024"
    assert result["publication_date"] == {"month": "March", "year": "2024"}
    assert result["journal_name"] == "Computing Research"
    assert result["issn"]["print"] == "2049-3630"
    assert result["document_type"] == "journal"
    assert result["evidence"]["doi"]["page"] == 1


def test_metadata_extractor_joins_wrapped_title_lines() -> None:
    text = """A STUDY OF THE PERCEPTION OF DIFFERENT
STAKEHOLDERS TOWARDS VIRTUAL
TEACHING-LEARNING MODE DURING COVID-19
PANDEMIC AT THE UPPER PRIMARY STAGE
Authors: Ada Lovelace
Journal: Education Research
Year: 2024
"""

    result = extract_metadata(text)

    assert result["paper_title"] == (
        "A STUDY OF THE PERCEPTION OF DIFFERENT STAKEHOLDERS TOWARDS VIRTUAL "
        "TEACHING-LEARNING MODE DURING COVID-19 PANDEMIC AT THE UPPER PRIMARY STAGE"
    )


def test_doi_normalization_supports_common_forms() -> None:
    assert normalize_doi("doi:10.5555/ABC.") == "10.5555/ABC"
    assert normalize_doi("https://doi.org/10.5555/ABC") == "10.5555/ABC"
    assert extract_doi("DOI: https://doi.org/10.7777/example, accessed today") == "10.7777/example"
    assert extract_doi("Title: Current paper\nReferences\nCited study DOI: 10.9999/reference") is None


def test_metadata_extractor_marks_non_research_documents() -> None:
    result = extract_metadata("Abstract\nText only")

    assert result["doi"] is None
    assert result["paper_title"] is None
    assert result["authors"] == []
    assert result["journal_name"] is None
    assert "paper_title" in result["missing_fields"]


def test_metadata_extractor_marks_form_content_as_non_research_document() -> None:
    result = extract_metadata(
        "SESSION : - 2023-2024\nSUBJECT :-\nEXTERNAL SIGN\nINTERNAL SIGN\nPRINCIPAL SIGN"
    )

    assert result["paper_title"] is None
    assert result["authors"] == []
    assert result["document_type"] == "unknown"


def test_metadata_extractor_excludes_reference_doi_and_received_date() -> None:
    result = extract_metadata(
        """Title: Current Study of Metadata
Authors: Ada Lovelace¹, Alan Turing²
¹Department of Computing, Example University, London
²Department of Information Systems, Other University, Oxford
Journal: Journal of Example Research
Received: 12 January 2023
Accepted: 4 March 2023
Published online: September 2024
DOI: https://doi.org/10.1000/current.paper
Abstract
This paper cites another study.
References
Unrelated title. DOI: 10.9999/reference.paper
"""
    )

    assert result["paper_title"] == "Current Study of Metadata"
    assert [author["name"] for author in result["authors"]] == ["Ada Lovelace", "Alan Turing"]
    assert result["authors"][0]["department"] == "Department of Computing"
    assert result["authors"][1]["institution"] == "Other University"
    assert result["publication_date"] == {"month": "September", "year": "2024"}
    assert result["doi"] == "10.1000/current.paper"


def test_metadata_extractor_does_not_promote_reference_only_doi_or_issn() -> None:
    result = extract_metadata(
        """A Careful Study of Bibliographic Context
Authors: Ada Lovelace
Abstract
References
Journal cited in the references. ISSN: 2049-3630 DOI: 10.9999/cited.paper
"""
    )

    assert result["doi"] is None
    assert result["issn"] == {"print": None, "electronic": None}
    assert "doi" in result["missing_fields"]


def test_references_boundary_applies_to_all_following_pages() -> None:
    result = extract_metadata(
        {
            "page_texts": [
                "Title: A Current Paper\nAuthors: Ada Lovelace\nDOI: 10.1000/current.value\nReferences",
                "Cited paper. ISSN: 2049-3630 DOI: 10.9999/cited.value",
            ]
        }
    )

    assert result["doi"] == "10.1000/current.value"
    assert result["issn"] == {"print": None, "electronic": None}


def test_unlabeled_journal_first_page_layout_extracts_title_author_and_issue_date() -> None:
    result = extract_metadata(
        """The Journal of Example Studies, Volume 4, No. 1, September 2024
Research paper
A study of advanced learners' use of mobile devices for
language learning: Evidence from interview data
Mariusz Kruk
Example University, Oxford
Abstract
The paper discusses the results of a study.
"""
    )

    assert result["paper_title"] == (
        "A study of advanced learners' use of mobile devices for "
        "language learning: Evidence from interview data"
    )
    assert result["authors"] == [{
        "name": "Mariusz Kruk",
        "department": None,
        "institution": "Example University",
        "location": "Oxford",
    }]
    assert result["journal_name"] == "The Journal of Example Studies"
    assert result["publication_date"] == {"month": "September", "year": "2024"}
    assert result["document_type"] == "journal"


def test_institution_evidence_is_not_misreported_as_department_evidence() -> None:
    result = extract_metadata(
        """A Study of Institutional Context
Authors: Ada Lovelace
Example University, Oxford
Abstract
An abstract paragraph for the paper.
"""
    )

    assert result["authors"][0]["institution"] == "Example University"
    assert result["authors"][0]["department"] is None
    assert result["evidence"]["departments"] is None


def test_body_mention_of_conference_does_not_set_document_type() -> None:
    result = extract_metadata(
        """A Study of Document Classification
Authors: Ada Lovelace
Abstract
We compare conference and journal publications as examples.
"""
    )

    assert result["document_type"] == "unknown"
    assert result["conference_name"] is None


def test_ambiguous_dois_are_resolved_only_by_crossref_title_author_match(monkeypatch) -> None:
    def fake_verify(doi, metadata):
        return {"verified": doi == "10.1000/current", "confidence": 0.92}

    monkeypatch.setattr("app.services.doi_verifier.verify_doi", fake_verify)
    result = extract_metadata(
        """Title: A Current Paper
Authors: Ada Lovelace
DOI: 10.1000/unrelated
Publisher DOI: 10.1000/current
Abstract
The current work evaluates a paper.
"""
    )

    assert result["doi"] == "10.1000/current"
    assert result["evidence"]["doi"]["source"] == "Crossref"
    assert any("Crossref uniquely matched" in warning for warning in result["warnings"])


def test_body_doi_requires_crossref_verification(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.doi_verifier.verify_doi",
        lambda *args, **kwargs: {"verified": False, "confidence": 0.4},
    )
    result = extract_metadata(
        """Title: A Current Paper
Authors: Ada Lovelace
Abstract
The cited study has DOI 10.9999/unrelated.reference.
"""
    )

    assert result["doi"] is None
    assert "doi" in result["missing_fields"]


def test_conference_paper_is_not_marked_as_ugc_care_eligible() -> None:
    result = extract_metadata(
        """Title: Conference Research Paper
Authors: Ada Lovelace
Conference: International Conference on Document Analysis
"""
    )

    assert result["document_type"] == "conference"
    assert result["journal_name"] is None
    assert result["ugc_care"] == {"status": "not_applicable", "link": None}