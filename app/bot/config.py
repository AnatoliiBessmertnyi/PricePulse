from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    telegram_bot_token: str
    fastapi_base_url: str = "http://localhost:8000"
    telegram_api_url: str | None = None
    request_timeout: int = 30
    connect_timeout: int = 10


@lru_cache
def get_bot_settings() -> BotSettings:
    return BotSettings()


bot_settings = get_bot_settings()
