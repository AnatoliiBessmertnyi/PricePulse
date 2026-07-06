from functools import lru_cache

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    project_name: str = "PricePulse"
    project_version: str = "0.1.0"

    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int

    redis_host: str
    redis_port: int

    rabbitmq_host: str
    rabbitmq_port: int

    rabbitmq_default_user: str
    rabbitmq_default_pass: str

    telegram_bot_token: str | None = None
    fastapi_base_url: str = "http://api:8000"

    price_check_interval: int = 900
    browser_pool_size: int = 2
    worker_concurrency: int = 4

    proxy_list: str = ""
    proxy_rotation_enabled: bool = False

    log_level: str = "INFO"

    @field_validator("price_check_interval")
    @classmethod
    def validate_price_check_interval(cls, v: int) -> int:
        if v < 60:
            raise ValueError("price_check_interval must be at least 60 seconds")
        return v

    @field_validator("browser_pool_size")
    @classmethod
    def validate_browser_pool_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("browser_pool_size must be at least 1")
        if v > 20:
            raise ValueError("browser_pool_size must be at most 20")
        return v

    @field_validator("worker_concurrency")
    @classmethod
    def validate_worker_concurrency(cls, v: int) -> int:
        if v < 1:
            raise ValueError("worker_concurrency must be at least 1")
        if v > 16:
            raise ValueError("worker_concurrency must be at most 16")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper

    @computed_field
    @property
    def proxy_list_parsed(self) -> list[str]:
        """Parse proxy list from comma-separated string."""
        if not self.proxy_list:
            return []
        return [proxy.strip() for proxy in self.proxy_list.split(",") if proxy.strip()]

    @computed_field
    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:"
            f"{self.postgres_password}@"
            f"{self.postgres_host}:"
            f"{self.postgres_port}/"
            f"{self.postgres_db}"
        )

    @computed_field
    @property
    def sync_postgres_url(self) -> str:
        return (
            f"postgresql+psycopg://"
            f"{self.postgres_user}:"
            f"{self.postgres_password}@"
            f"{self.postgres_host}:"
            f"{self.postgres_port}/"
            f"{self.postgres_db}"
        )

    @computed_field
    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://"
            f"{self.rabbitmq_default_user}:"
            f"{self.rabbitmq_default_pass}@"
            f"{self.rabbitmq_host}:"
            f"{self.rabbitmq_port}//"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    cors_origins: str = "http://localhost:3000,http://localhost:8080"

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
