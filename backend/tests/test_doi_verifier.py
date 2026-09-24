from app.services.doi_verifier import verify_doi


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_doi_verifier_requires_crossref_metadata_match(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.doi_verifier.requests.get",
        lambda *args, **kwargs: FakeResponse(
            {
                "message": {
                    "title": ["Local Extraction for Research Papers"],
                    "author": [{"family": "Lovelace", "given": "Ada"}],
                    "published": {"date-parts": [[2024]]},
                    "container-title": ["Computing Research"],
                }
            }
        ),
    )

    result = verify_doi(
        "https://doi.org/10.1234/example",
        {
            "title": "Local Extraction for Research Papers",
            "authors": [{"name": "Ada Lovelace"}],
            "publication_year": 2024,
            "journal": "Computing Research",
        },
    )

    assert result["doi"] == "10.1234/example"
    assert result["verified"] is True
    assert result["source"] == "Crossref"
    assert result["confidence"] == 1.0


def test_doi_verifier_rejects_title_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.doi_verifier.requests.get",
        lambda *args, **kwargs: FakeResponse({"message": {"title": ["Different paper"]}}),
    )

    result = verify_doi("10.1234/example", {"title": "Expected paper"})

    assert result["verified"] is False
    assert result["title_similarity"] < 0.80


def test_doi_verifier_does_not_confirm_missing_or_unavailable_doi(monkeypatch) -> None:
    missing = verify_doi(None, {})
    monkeypatch.setattr(
        "app.services.doi_verifier.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("offline")),
    )
    unavailable = verify_doi("10.1234/example", {})

    assert missing["verified"] is False
    assert unavailable["verified"] is False