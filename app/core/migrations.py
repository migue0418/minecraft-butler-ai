from alembic import command
from alembic.config import Config

from app.core.settings import BACKEND_DIR, get_settings


def build_alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def run_migrations() -> None:
    command.upgrade(build_alembic_config(), "head")
