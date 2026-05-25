from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/fastapi_template"
)


class Settings(BaseSettings):
    app_name: str = "FastAPI Template"
    environment: Literal["development", "production", "test"] = "development"
    secret_key: str = "change-this-secret-key"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    database_url: str = DEFAULT_DATABASE_URL
    admin_username: str = "admin"
    admin_password: str = "ChangeMe123!"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def frontend_dist_dir(self) -> Path:
        return PROJECT_ROOT / "frontend" / "dist"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
