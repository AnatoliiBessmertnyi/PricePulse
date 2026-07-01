from playwright.async_api import Page

from app.core.logging import get_logger

logger = get_logger(__name__)


class MarketplaceHttpClient:
    """HTTP клиент для работы с маркетплейсами через headless браузер."""

    def __init__(self, page: Page):
        self.page = page
        self.page.set_default_timeout(60000)
        self.page.set_default_navigation_timeout(60000)

    async def get(self, url: str) -> tuple[str, str]:
        logger.info(
            "http_client_get_start",
            url=url,
        )
        
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = await self.page.content()
            final_url = self.page.url
            
            logger.info(
                "http_client_get_success",
                original_url=url,
                final_url=final_url,
                html_length=len(html),
            )
            
            return html, final_url
        except Exception as e:
            logger.error(
                "http_client_get_error",
                url=url,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
