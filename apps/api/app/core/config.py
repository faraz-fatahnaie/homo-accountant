"""Application configuration via environment variables (prefix HOMO_)."""

from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOMO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    app_name: str = "Homo Accountant API"
    environment: str = "development"  # development | test | production
    debug: bool = False
    api_prefix: str = "/api/v1"

    # --- Database (PostgreSQL) ---
    database_url: str = "postgresql+psycopg://arya:arya_dev_pw@127.0.0.1:5432/arya_dev"

    # --- Security ---
    jwt_secret: str = Field(default="change-me-in-production-please", min_length=16)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    access_cookie_name: str = "homo_access"
    refresh_cookie_name: str = "homo_refresh"
    password_hash_iterations: int = 600_000
    # CORS allowlist (comma-separated origins)
    cors_origins: str = "http://localhost:3000"
    # Rate limiting on authentication endpoints (per IP)
    login_rate_limit_per_minute: int = 10
    lockout_after_failures: int = 5
    lockout_minutes: int = 15

    # --- Bootstrap (development) ---
    seed_demo_users: bool = False
    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""

    # --- Files / attachments ---
    media_dir: str = "media"  # local disk root for uploads (dev); S3 in prod slice
    max_upload_bytes: int = 5 * 1024 * 1024

    # --- Optional production monitoring ---
    sentry_dsn: str = ""
    sentry_release: str = ""
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Self:
        if not self.is_production:
            return self
        if self.jwt_secret == "change-me-in-production-please" or len(self.jwt_secret) < 32:
            raise ValueError(
                "production requires a unique HOMO_JWT_SECRET of at least 32 characters"
            )
        if "arya_dev_pw" in self.database_url:
            raise ValueError("production cannot use the development database password")
        if "*" in self.cors_origin_list:
            raise ValueError("production CORS origins cannot contain a wildcard")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
