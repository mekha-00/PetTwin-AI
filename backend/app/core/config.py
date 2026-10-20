"""Application settings, loaded from environment variables.

Secrets are read from the environment (or a local git-ignored ``.env``) and are
never given working defaults. A missing or weak ``SECRET_KEY`` is a hard startup
failure rather than a silent fallback, because a default signing key would let
anyone forge access tokens.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "PetTwin AI API"
    app_version: str = "0.3.0"
    debug: bool = True
    api_prefix: str = "/api"

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    postgres_user: str = ""
    postgres_password: str = ""
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = ""
    #: TLS mode appended to the assembled connection string. Hosted Postgres
    #: (Render, Neon, Supabase) refuses non-TLS connections, so this defaults to
    #: "prefer" (use TLS if the server offers it) which is harmless locally and
    #: sufficient for hosts that require TLS. Set to "require" if a host insists.
    postgres_sslmode: str = "prefer"
    #: Full connection string override. When set, it wins over the POSTGRES_*
    #: parts, so a hosted provider's exact URL can be pasted verbatim.
    database_url_override: str = ""
    db_auto_create: bool = False

    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "pettwin-api"
    jwt_audience: str = "pettwin-frontend"
    access_token_expire_minutes: int = 60

    bcrypt_rounds: int = 12

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"

    #: Build the RAG index during application startup.
    #:
    #: The first build embeds every PDF chunk and takes a couple of minutes; the
    #: result is then cached in-process, so subsequent queries are fast. Warming
    #: at boot moves that cost to startup instead of the first request, which
    #: would otherwise appear to hang.
    #:
    #: Tests disable this. The ``client`` fixture enters the app's lifespan once
    #: per test, so an uncached build here would be paid repeatedly and dominate
    #: the run.
    rag_warmup_on_startup: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("jwt_algorithm")
    @classmethod
    def _only_hs256(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("only HS256 is supported for access tokens")
        return value

    @field_validator("secret_key")
    @classmethod
    def _secret_must_be_strong(cls, value: str) -> str:
        if not value:
            raise ValueError(
                "SECRET_KEY is not set. Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if len(value) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters long, "
                f"got {len(value)}"
            )
        return value

    @property
    def database_url(self) -> str:
        # A full override wins: hosted providers sometimes hand out a URL whose
        # shape does not map cleanly onto the POSTGRES_* parts.
        if self.database_url_override:
            url = self.database_url_override
            # Ensure the SQLAlchemy psycopg2 driver prefix is present.
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            return url
        if not self.postgres_user or not self.postgres_db:
            return ""
        password = self.postgres_password
        base = (
            f"postgresql+psycopg2://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.postgres_sslmode:
            separator = "&" if "?" in base else "?"
            base = f"{base}{separator}sslmode={self.postgres_sslmode}"
        return base

    @property
    def is_database_configured(self) -> bool:
        return bool(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
