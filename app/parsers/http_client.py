import httpx


class MarketplaceHttpClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.http_client = http_client

    async def get(
        self,
        url: str,
    ) -> tuple[str, str]:
        """Делает GET-запрос и возвращает (HTML-контент, финальный URL после редиректов)."""
        response = await self.http_client.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                ),
            },
        )

        response.raise_for_status()

        return response.text, str(response.url)
