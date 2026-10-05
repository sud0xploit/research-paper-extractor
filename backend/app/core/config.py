from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:password@localhost:5432/research_extractor"
    tesseract_path: str = ""
    metadata_provider: str = "ollama"
    crossref_metadata_verification: bool = True
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2:7b"
    ollama_timeout_seconds: int = 180
    crossref_mailto: str = ""
    llm_api_key: str = ""
    max_file_size_mb: int = 50
    classification_threshold: float = 0.70
    local_classifier_model: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()