import httpx


class MarketplaceHttpClient:
    """HTTP клиент для работы с маркетплейсами."""

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def get(self, url: str) -> tuple[str, str]:
        """Делает GET-запрос и возвращает (HTML-контент, финальный URL)."""
        response = await self.http_client.get(
            url,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text, str(response.url)
