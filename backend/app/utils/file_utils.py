from pathlib import Path
from uuid import uuid4


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".jpg", ".jpeg", ".png"}


def get_safe_filename(filename: str) -> str:
    """Return a basename with a generated prefix to prevent collisions."""
    original_name = Path(filename or "unnamed").name
    safe_name = "".join(
        character
        for character in original_name
        if character.isalnum() or character in {".", "-", "_", " "}
    ).strip()
    return f"{uuid4().hex}_{safe_name or 'unnamed'}"


def get_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()