from app.services.classifier import LocalPublicationClassifier


class FakeModel:
    def __call__(self, text, candidate_labels, multi_label):
        lowered = text.casefold()
        if "thesis" in lowered:
            label = "Thesis"
        elif "dissertation" in lowered:
            label = "Dissertation"
        elif "conference" in lowered:
            label = "Conference"
        else:
            label = "Other"
        return {"labels": [label], "scores": [0.91]}


def local_classifier(monkeypatch, threshold=0.70):
    classifier = LocalPublicationClassifier(threshold=threshold, model_name="local/model")
    monkeypatch.setattr(classifier, "_load_model", lambda: FakeModel())
    return classifier


def test_classifier_uses_local_nlp_model(monkeypatch) -> None:
    result = local_classifier(monkeypatch).classify(
        "Journal of Computational Methods\nVolume 12 Issue 3\nISSN 1234-5678"
    )

    assert result["publication_type"] == "Other"
    assert result["confidence"] >= 0.70
    assert result["provider"] == "local-transformer"
    assert result["status"] == "AUTO_APPROVED"


def test_classifier_identifies_thesis_and_dissertation_separately(monkeypatch) -> None:
    classifier = local_classifier(monkeypatch)
    thesis = classifier.classify("Master's thesis submitted to the Department of Biology")
    dissertation = classifier.classify("Doctoral dissertation submitted for the PhD degree")

    assert thesis["publication_type"] == "Thesis"
    assert dissertation["publication_type"] == "Dissertation"


def test_classifier_requires_a_local_nlp_model(monkeypatch) -> None:
    monkeypatch.delenv("LOCAL_CLASSIFIER_MODEL", raising=False)
    monkeypatch.setattr("app.services.classifier.settings.local_classifier_model", "")
    result = LocalPublicationClassifier(threshold=0.70)

    try:
        result.classify("A document about research")
    except RuntimeError as error:
        assert "LOCAL_CLASSIFIER_MODEL" in str(error)
    else:
        raise AssertionError("Classification must require a configured local NLP model")


def test_classifier_uses_configured_local_transformer(monkeypatch) -> None:
    classifier = local_classifier(monkeypatch)

    result = classifier.classify("Conference proceedings", {})

    assert result["publication_type"] == "Conference"
    assert result["provider"] == "local-transformer"
    assert result["status"] == "AUTO_APPROVED"