import asyncio

import httpx
from bs4 import BeautifulSoup

from app.parsers.http_client import MarketplaceHttpClient


PRODUCT_URL = (
    "https://ozon.ru/t/lwPpFFD"
)


async def main() -> None:
    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
    ) as http_client:
        client = MarketplaceHttpClient(
            http_client=http_client,
        )

        html = await client.get(
            PRODUCT_URL,
        )

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        scripts = soup.find_all(
            "script",
            attrs={
                "type": "application/ld+json",
            },
        )

        print(
            f"Found {len(scripts)} ld+json scripts",
        )

        for index, script in enumerate(
            scripts,
            start=1,
        ):
            print(
                f"\n=== SCRIPT {index} ===\n",
            )

            print(
                script.string,
            )

        with open(
            "ozon.html",
            "w",
            encoding="utf-8",
        ) as file:
            file.write(html)


if __name__ == "__main__":
    asyncio.run(main())