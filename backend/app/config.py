from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./attendtrend.db"
    environment: str = "development"
    cookie_secure: bool = False
    allowed_origins: str = (
        "http://localhost:5173,http://localhost:8080,http://127.0.0.1:5173,http://127.0.0.1:8080,http://localhost:4173,http://127.0.0.1:4173"
    )
    upload_dir: Path = Path("./uploads")
    session_hours: int = 24
    max_upload_bytes: int = 10 * 1024 * 1024


@lru_cache
def settings():
    config = Settings()
    if config.environment == "production":
        if not config.database_url.startswith("postgresql") or not config.cookie_secure:
            raise RuntimeError(
                "Production requires PostgreSQL and COOKIE_SECURE=true (HTTPS)."
            )
    return config
