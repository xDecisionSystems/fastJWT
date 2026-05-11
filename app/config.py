from typing import List

from pydantic.v1 import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Application configuration read from environment variables."""

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

    class Config:
        env_prefix = ""
        case_sensitive = False

        @classmethod
        def parse_env_var(cls, field_name, raw_val):
            if field_name == "cors_origins":
                return raw_val
            return super().parse_env_var(field_name, raw_val)

    @validator("cors_origins", pre=True)
    def _split_origins(cls, value):
        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",")]
            value = [origin for origin in origins if origin]
        return value or []
