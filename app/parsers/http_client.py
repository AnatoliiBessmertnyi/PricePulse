from playwright.async_api import Page


class MarketplaceHttpClient:
    """HTTP клиент для работы с маркетплейсами через headless браузер."""

    def __init__(self, page: Page):
        self.page = page

    async def get(self, url: str) -> tuple[str, str]:
        """Делает GET-запрос и возвращает (HTML-контент, финальный URL)."""
        await self.page.goto(url, wait_until="networkidle")
        html = await self.page.content()
        final_url = self.page.url
        return html, final_url
