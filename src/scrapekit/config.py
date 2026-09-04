"""Configuration via environment variables and pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for AsyncScrapeClient.

    Environment variables are prefixed with ``SCRAPEKIT_``.
    Example: ``SCRAPEKIT_USER_AGENT=MyBot/1.0``.
    """

    model_config = SettingsConfigDict(
        env_prefix="SCRAPEKIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    user_agent: str = Field(
        default="async-scrapekit/0.1 (+https://github.com/muhammad-a-dev/async-scrapekit)",
        description="HTTP User-Agent sent with every request.",
    )
    max_concurrency_per_host: int = Field(
        default=2,
        ge=1,
        description="Maximum concurrent in-flight requests per host.",
    )
    requests_per_second: float = Field(
        default=1.0,
        gt=0,
        description="Steady-state request rate limit per host.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts for transient failures.",
    )
    backoff_base: float = Field(
        default=0.5,
        gt=0,
        description="Base delay (seconds) for exponential backoff.",
    )
    backoff_cap: float = Field(
        default=30.0,
        gt=0,
        description="Maximum backoff delay (seconds).",
    )
    timeout: float = Field(
        default=30.0,
        gt=0,
        description="Default request timeout in seconds.",
    )
    respect_robots: bool = Field(
        default=True,
        description="Whether to honor robots.txt by default.",
    )
    allow_disallowed: bool = Field(
        default=False,
        description=(
            "If True, permit fetching URLs disallowed by robots.txt. "
            "Must be set explicitly; defaults to False (respect robots)."
        ),
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )


def get_settings(**overrides: object) -> Settings:
    """Build settings, applying optional keyword overrides."""
    return Settings(**overrides)  # type: ignore[arg-type]
