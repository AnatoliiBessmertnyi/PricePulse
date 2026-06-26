from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
