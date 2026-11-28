"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets must come from env / .env, never hardcoded."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GNI_",
        extra="ignore",
    )

    env: str = "dev"
    log_level: str = "INFO"
    timezone: str = "UTC"
    database_url: str = "postgresql+psycopg://gni:gni@localhost:5432/gni"

    llm_provider: str = "deepseek"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    daily_llm_budget_usd: float = 10.0
    daily_article_limit: int = 500
    per_article_token_limit: int = 8000

    report_timezone: str = "Asia/Shanghai"

    # Event lifecycle (writing-block §5.5): days since last linked article.
    # 14d is the spec's test default and must stay configurable (not a fixed fact).
    event_dormant_days: int = 14
    event_closed_days: int = 90

    # Meilisearch (optional; search falls back to Postgres ilike when unset/down)
    meili_url: str = "http://127.0.0.1:7700"
    meili_key: str = "gni_dev_meili_key"


@lru_cache
def get_settings() -> Settings:
    return Settings()
