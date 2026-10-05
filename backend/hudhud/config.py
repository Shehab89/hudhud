"""Runtime configuration, read from environment variables (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://hudhud:hudhud@localhost:5432/hudhud"
    seeds_dir: Path = REPO_ROOT / "database" / "seeds"

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        # Hosting dashboards (Supabase, Render, Neon) hand out postgres:// or postgresql:// URLs;
        # accept them as pasted and select the psycopg 3 driver.
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    # Fetching
    user_agent: str = "HudhudBot/0.1 (+https://github.com/; research crawler; respects robots.txt)"
    http_timeout_seconds: float = 20.0
    fetch_max_attempts: int = 3
    fetch_backoff_base_seconds: float = 2.0
    fetch_concurrency: int = 8
    # Only fetch article pages for sources whose access_policy allows it.
    fetch_article_pages: bool = False
    lookback_days: int = 3

    # NLP backends. "auto" uses transformer models when installed, otherwise the
    # deterministic fallback. The backend actually used is recorded with every result.
    nlp_backend: str = "auto"  # auto | transformers | fallback
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384
    sentiment_model: str = "cardiffnlp/twitter-xlm-roberta-base-sentiment-multilingual"
    sentiment_model_ar: str = "CAMeL-Lab/bert-base-arabic-camelbert-mix-sentiment"
    zero_shot_model: str = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
    ner_model: str = "Davlan/xlm-roberta-base-ner-hrl"
    use_transformer_ner: bool = False
    # The per-article analysis stops after this many seconds (0 = no limit); articles it did not
    # reach are analysed by the next run. Results are committed every ``analyse_commit_every``.
    analyse_max_seconds: float = 0
    analyse_commit_every: int = 8

    # Confidence routing thresholds
    accept_threshold: float = 0.85
    secondary_threshold: float = 0.60

    # Dedup thresholds
    title_near_dup_threshold: float = 0.88
    semantic_same_story_threshold: float = 0.92
    semantic_related_threshold: float = 0.80
    dedup_window_days: int = 4

    # Topic modelling
    topic_min_docs: int = 40
    topic_full_retrain_days: int = 7

    # LLM (optional; tier 2). Leave the key empty to run without any LLM.
    llm_provider: str = "none"  # none | anthropic
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5"
    llm_daily_budget_usd: float = 1.0
    llm_max_articles_per_run: int = 50

    # API
    api_cors_origins: str = "http://localhost:3000"
    api_rate_limit: str = "120/minute"
    admin_token: str = ""

    log_level: str = "INFO"
    log_json: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
