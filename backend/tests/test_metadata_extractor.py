from app.services.metadata_extractor import extract_doi, extract_metadata, normalize_doi


def test_metadata_extractor_returns_labeled_fields_and_dynamic_authors() -> None:
    text = """Title: Local Extraction for Research Papers
Authors: Ada Lovelace; Alan Turing; Grace Hopper; Katherine Johnson; Tim Berners-Lee
Journal: Computing Research
Publisher: Example Press
Volume: 12
Issue: 3
Pages: 44-58
Year: 2024
DOI: https://doi.org/10.1234/example.2024.
ISSN: 1234-5678
"""

    result = extract_metadata(text)

    assert result["title"] == "Local Extraction for Research Papers"
    assert len(result["authors"]) == 5
    assert result["authors"][4]["order"] == 5
    assert result["doi"] == "10.1234/example.2024"
    assert result["publication_year"] == 2024
    assert result["journal"] == "Computing Research"
    assert result["document_status"] == "RESEARCH_PAPER"
    assert result["metadata_confidence"] == 1.0


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

    assert result["title"] == (
        "A STUDY OF THE PERCEPTION OF DIFFERENT STAKEHOLDERS TOWARDS VIRTUAL "
        "TEACHING-LEARNING MODE DURING COVID-19 PANDEMIC AT THE UPPER PRIMARY STAGE"
    )


def test_doi_normalization_supports_common_forms() -> None:
    assert normalize_doi("doi:10.5555/ABC.") == "10.5555/ABC"
    assert normalize_doi("https://doi.org/10.5555/ABC") == "10.5555/ABC"
    assert extract_doi("Reference: 10.7777/example, accessed today") == "10.7777/example"


def test_metadata_extractor_marks_non_research_documents() -> None:
    result = extract_metadata("Abstract\nText only")

    assert result["doi"] is None
    assert result["title"] == "Document is not a research paper"
    assert result["authors"][0]["name"] == "No author"
    assert result["journal"] is None
    assert result["document_status"] == "NOT_RESEARCH_PAPER"


def test_metadata_extractor_marks_form_content_as_non_research_document() -> None:
    result = extract_metadata(
        "SESSION : - 2023-2024\nSUBJECT :-\nEXTERNAL SIGN\nINTERNAL SIGN\nPRINCIPAL SIGN"
    )

    assert result["title"] == "Document is not a research paper"
    assert result["authors"][0]["name"] == "No author"
    assert result["document_status"] == "NOT_RESEARCH_PAPER"