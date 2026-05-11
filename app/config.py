from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration read from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    secret_key: str = Field(..., min_length=32, description="JWT signing key")
    jwt_expiration_minutes: int = Field(
        20,
        gt=0,
        description="Number of minutes before a generated token expires",
    )
    jwt_issuer: str = Field(
        "fastjwt-api",
        min_length=1,
        description="Expected JWT issuer claim",
    )
    jwt_audience: str = Field(
        "fastjwt-clients",
        min_length=1,
        description="Expected JWT audience claim",
    )
    cors_origins: List[str] = Field(
        default_factory=list,
        description="Origins allowed by CORS (comma-delimited string accepted)",
    )
    rate_limit_requests: int = Field(
        60,
        ge=0,
        description="Maximum accepted requests per client within rate_limit_window_seconds",
    )
    rate_limit_window_seconds: int = Field(
        60,
        gt=0,
        description="Duration of the rate-limit window in seconds",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",")]
            value = [origin for origin in origins if origin]
        return value or []
