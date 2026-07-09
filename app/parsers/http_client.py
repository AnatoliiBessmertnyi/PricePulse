import asyncio
import random

from app.core.constants import PAGE_TIMEOUT_MS
from app.core.logging import get_logger
from app.proxy.service import ProxyService
from app.workers.http_client_manager import ProcessBrowser

logger = get_logger(__name__)


class MarketplaceHttpClient:
    """HTTP клиент для работы с маркетплейсами через headless браузер."""

    def __init__(
        self,
        browser_manager: ProcessBrowser,
        proxy_service: ProxyService | None = None,
    ) -> None:
        self._browser_manager = browser_manager
        self._proxy_service = proxy_service

    async def _human_delay(self, min_sec: float = 1.0, max_sec: float = 2.0) -> None:
        """Имитирует человеческую задержку."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    def _get_proxy_log(self, proxy_url: str | None) -> str:
        """Получить строку прокси для логирования (с маскированием credentials)."""
        if proxy_url is None:
            return "direct"

        if self._proxy_service:
            return self._proxy_service.get_masked_url(proxy_url)

        return proxy_url

    async def get(self, url: str) -> tuple[str, str]:
        """Получить HTML страницу."""
        proxy_url = None
        if self._proxy_service:
            proxy_url = self._proxy_service.get_next_proxy()

        logger.info(
            "http_client_get_start", url=url, proxy=self._get_proxy_log(proxy_url)
        )
        page = await self._browser_manager.get_page_with_proxy(proxy_url)
        page.set_default_timeout(PAGE_TIMEOUT_MS)
        page.set_default_navigation_timeout(PAGE_TIMEOUT_MS)

        try:
            await self._human_delay(0.5, 1.5)
            await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            await self._human_delay(1.0, 2.0)
            html = await page.content()
            final_url = page.url
            if proxy_url and self._proxy_service:
                self._proxy_service.mark_proxy_success(proxy_url)

            logger.info(
                "http_client_get_success",
                original_url=url,
                final_url=final_url,
                html_length=len(html),
                proxy=self._get_proxy_log(proxy_url),
            )
            return html, final_url
        except Exception as e:
            if proxy_url and self._proxy_service:
                self._proxy_service.mark_proxy_failed(proxy_url)

            logger.error(
                "http_client_get_error",
                url=url,
                error=str(e),
                error_type=type(e).__name__,
                proxy=self._get_proxy_log(proxy_url),
            )
            raise
        finally:
            if proxy_url is not None:
                await page.context.close()
