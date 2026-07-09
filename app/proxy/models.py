from pydantic import BaseModel


class ProxyConfig(BaseModel):
    """Конфигурация прокси."""

    url: str
    is_active: bool = True
    failed_count: int = 0
    max_failures: int = 3

    def mark_failed(self) -> None:
        """Пометить прокси как упавший."""
        self.failed_count += 1
        if self.failed_count >= self.max_failures:
            self.is_active = False

    def reset(self) -> None:
        """Сбросить счётчик ошибок."""
        self.failed_count = 0
        self.is_active = True
