import os
from collections.abc import Mapping

from app.core.config import settings

PUBLICATION_TYPES = (
    "Journal",
    "Conference",
    "Book",
    "Chapter",
    "Thesis",
    "Dissertation",
    "Preprint",
    "Report",
    "Other",
)

class PublicationClassifier:
    """Replaceable classifier contract used by the processing pipeline."""

    def classify(self, text: str, metadata: Mapping | None = None) -> dict:
        raise NotImplementedError


class LocalPublicationClassifier(PublicationClassifier):
    def __init__(self, threshold: float | None = None, model_name: str | None = None) -> None:
        self.threshold = threshold if threshold is not None else float(
            os.getenv("CLASSIFICATION_THRESHOLD", "0.70")
        )
        self.model_name = model_name or os.getenv("LOCAL_CLASSIFIER_MODEL", "") or settings.local_classifier_model
        self._model = None
        self._model_loaded = False

    def _load_model(self):
        if self._model_loaded:
            return self._model
        self._model_loaded = True
        if not self.model_name:
            raise RuntimeError("LOCAL_CLASSIFIER_MODEL must point to a local NLP model.")
        try:
            from transformers import pipeline

            self._model = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                local_files_only=True,
            )
        except ImportError as error:
            raise RuntimeError("The transformers package is required for NLP classification.") from error
        except (OSError, RuntimeError, ValueError) as error:
            raise RuntimeError(f"Unable to load local NLP model '{self.model_name}': {error}") from error
        return self._model

    def _classify_with_model(self, text: str, metadata: Mapping | None) -> dict | None:
        model = self._load_model()
        context = " ".join(
            [text or "", str((metadata or {}).get("journal") or ""), str((metadata or {}).get("conference") or "")]
        ).strip()
        if not context:
            raise ValueError("No extracted text is available for NLP classification.")
        try:
            result = model(context, candidate_labels=list(PUBLICATION_TYPES), multi_label=False)
            label = str(result["labels"][0])
            publication_type = next(
                (known_type for known_type in PUBLICATION_TYPES if known_type.casefold() == label.casefold()),
                "Other",
            )
            confidence = round(float(result["scores"][0]), 2)
            return {
                "publication_type": publication_type,
                "confidence": confidence,
                "status": "AUTO_APPROVED" if confidence >= self.threshold else "NEEDS_REVIEW",
                "provider": "local-transformer",
            }
        except (KeyError, IndexError, TypeError, ValueError, RuntimeError) as error:
            raise RuntimeError(f"Local NLP classification failed: {error}") from error

    def classify(self, text: str, metadata: Mapping | None = None) -> dict:
        return self._classify_with_model(text, metadata)


def classify_publication(text: str, metadata: Mapping | None = None) -> dict:
    """Classify with the default local provider."""
    return LocalPublicationClassifier().classify(text, metadata)