from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal
from pydantic import SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="/workspace/.env", extra="ignore")
    database_url: SecretStr
    campus_timezone: str = "Asia/Kolkata"
    app_env: Literal["development", "test"] = "development"
    nlp_mode: Literal["baseline", "hybrid"] = "baseline"
    intent_model_path: str = "/workspace/.local/models/intent.json"

    allowed_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]
    now_interval_minutes: int = Field(default=30,ge=1,le=1440)
    nlp_horizon_days: int = Field(default=30,ge=1,le=30)
    cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=28800, ge=60, le=604800)
    preauth_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    login_limit_per_minute: int = Field(default=10, ge=1, le=1000)
    csrf_limit_per_minute: int = Field(default=30, ge=1, le=1000)

    @field_validator("allowed_origins")
    @classmethod
    def exact_origins(cls, origins):
        from urllib.parse import urlsplit
        if not origins:
            raise ValueError("At least one origin is required")
        for origin in origins:
            url = urlsplit(origin)
            if (url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password
                    or url.path or url.query or url.fragment or "*" in origin):
                raise ValueError("Origins must be exact HTTP(S) origins without paths")
        return origins

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value):
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("A PostgreSQL psycopg URL is required")
        return value

    @field_validator("campus_timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown campus timezone") from None
        return value
