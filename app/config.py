"""Application settings loaded from environment variables / .env."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-4o-mini",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    database_url: str = "sqlite:///./ilanuyum.db"
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # CV <-> job posting match analysis (LLM). The feature is disabled (503)
    # until the API key of the selected provider is set.
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    llm_model: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    llm_timeout_seconds: float = 30.0

    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model or DEFAULT_MODELS[self.llm_provider]


settings = Settings()
