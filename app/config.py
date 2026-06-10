"""Application settings loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "sqlite+aiosqlite:///./data/monitor.db"

    tick_seconds: int = 60
    default_interval_minutes: int = 5
    request_timeout: int = 15

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    log_level: str = "INFO"

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
