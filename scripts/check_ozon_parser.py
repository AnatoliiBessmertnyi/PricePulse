import asyncio

import httpx

from app.parsers.http_client import MarketplaceHttpClient
from app.parsers.ozon import OzonParser

PRODUCT_URL = "https://ozon.ru/t/lwPpFFD"


async def main() -> None:
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
    ) as http_client:
        marketplace_http_client = MarketplaceHttpClient(
            http_client=http_client,
        )

        parser = OzonParser(
            http_client=marketplace_http_client,
        )

        product_data = await parser.parse(
            PRODUCT_URL,
        )

        print(
            product_data,
        )


if __name__ == "__main__":
    asyncio.run(main())
