from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    log_level: str = "INFO"
    service_token: SecretStr

    redis_url: str = "redis://redis:6379/0"
    redis_queue: str = "onboarding:index:queue"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "onboarding_documents"
    data_dir: Path = Path("/data/jobs")
    odoo_callback_url: str | None = None
    max_document_bytes: int = 10 * 1024 * 1024
    job_ttl: int = 86400
    index_lock_ttl: int = 600

    llm_provider: Literal["extractive", "ollama", "openai"] = "extractive"
    llm_api_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_chat_model: str | None = None
    embedding_model: str = "hashing-128"

    session_ttl: int = 3600
    cache_ttl: int = 900
    rate_limit_per_minute: int = 20
    rag_top_k: int = 2
    rag_min_score: float = 0.08

    @model_validator(mode="after")
    def validate_provider_configuration(self):
        if len(self.service_token.get_secret_value()) < 16:
            raise ValueError("SERVICE_TOKEN must contain at least 16 characters")
        if self.llm_provider in {"ollama", "openai"} and not self.llm_api_url:
            raise ValueError("LLM_API_URL is required for the selected provider")
        if self.llm_provider in {"ollama", "openai"} and not self.llm_chat_model:
            raise ValueError("LLM_CHAT_MODEL is required for the selected provider")
        if self.llm_provider == "openai" and (
            not self.llm_api_key or not self.llm_api_key.get_secret_value()
        ):
            raise ValueError("LLM_API_KEY is required for the OpenAI provider")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
