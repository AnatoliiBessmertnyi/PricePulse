from urllib.parse import urlparse, urlunparse

from app.core.logging import get_logger
from app.proxy.models import ProxyConfig

logger = get_logger(__name__)


class ProxyService:
    """Сервис для управления прокси: ротация, health check, fallback."""

    def __init__(self, proxy_urls: list[str] | None = None) -> None:
        self._proxies: list[ProxyConfig] = []
        self._index = 0
        if proxy_urls:
            self._proxies = [ProxyConfig(url=url) for url in proxy_urls]
            logger.info("proxy_service_initialized", proxy_count=len(self._proxies))

    def get_next_proxy(self) -> str | None:
        """
        Получить следующий прокси (round-robin).

        Returns:
            URL прокси или None (прямой запрос)
        """
        if not self._proxies:
            return None

        active_proxies = [p for p in self._proxies if p.is_active]
        if not active_proxies:
            logger.warning("all_proxies_failed", fallback="direct")
            return None

        proxy = active_proxies[self._index % len(active_proxies)]
        self._index += 1
        logger.debug("proxy_selected", proxy_url=self.get_masked_url(proxy.url))
        return proxy.url

    def mark_proxy_failed(self, proxy_url: str) -> None:
        """Пометить прокси как упавший."""
        for proxy in self._proxies:
            if proxy.url == proxy_url:
                proxy.mark_failed()
                logger.warning(
                    "proxy_failed",
                    proxy_url=self.get_masked_url(proxy_url),
                    failed_count=proxy.failed_count,
                    is_active=proxy.is_active,
                )
                return

    def mark_proxy_success(self, proxy_url: str) -> None:
        """Пометить прокси как успешный (сбросить счётчик ошибок)."""
        for proxy in self._proxies:
            if proxy.url == proxy_url:
                proxy.reset()
                return

    def get_stats(self) -> dict:
        """Получить статистику по прокси."""
        return {
            "total": len(self._proxies),
            "active": sum(1 for p in self._proxies if p.is_active),
            "failed": sum(1 for p in self._proxies if not p.is_active),
        }

    def get_masked_url(self, proxy_url: str) -> str:
        """Получить замаскированный URL прокси для логирования."""
        parsed = urlparse(proxy_url)
        if parsed.username or parsed.password:
            masked_netloc = "***:***@" + parsed.hostname
            if parsed.port:
                masked_netloc += f":{parsed.port}"
            return urlunparse((parsed.scheme, masked_netloc, parsed.path, "", "", ""))
        return proxy_url
