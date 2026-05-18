"""Application settings — loaded once at import time via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    AGENT_MAX_ITERATIONS: int = 5
    AGENT_TIMEOUT_SECS: int = 30

    # Database (already set via env in containers; defaults for tests)
    DATABASE_URL: str = "postgresql+asyncpg://localhost/digidentity"


settings = Settings()
