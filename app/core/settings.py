from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/minecraftbutlerai"
)


class Settings(BaseSettings):
    app_name: str = "MinecraftButlerAI"
    environment: Literal["development", "production", "test"] = "development"
    secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    database_url: str = DEFAULT_DATABASE_URL
    admin_username: str = "admin"
    admin_password: str = "ChangeMe123!"
    anthropic_api_key: str = ""
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    classifier_model: str = "claude-haiku-4-5-20251001"
    responder_model: str = "claude-sonnet-4-6"
    embedding_provider: Literal["openai", "huggingface"] = "huggingface"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    openai_api_key: str = ""
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "minecraft_knowledge"
    qdrant_api_key: str = ""
    qdrant_top_k: int = 5
    qdrant_prefetch_limit: int = 20
    qdrant_score_threshold: float = 0.0
    redis_url: str = "redis://localhost:6379"
    redis_session_ttl_seconds: int = 86400
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    langsmith_api_key: str = ""
    langsmith_project: str = "minecraftbutlerai"
    langsmith_endpoint: str = ""
    langchain_tracing: bool = False
    ssl_verify: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.is_production and len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY debe tener al menos 32 caracteres en producción. "
                'Genera una con: python -c "import secrets; print(secrets.token_hex(32))"',
            )
        return self

    @model_validator(mode="after")
    def validate_llm_api_keys(self) -> "Settings":
        if self.environment == "test":
            return self
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY es obligatoria cuando LLM_PROVIDER=anthropic.",
            )
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY es obligatoria cuando LLM_PROVIDER=openai.",
            )
        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY es obligatoria cuando EMBEDDING_PROVIDER=openai.",
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
