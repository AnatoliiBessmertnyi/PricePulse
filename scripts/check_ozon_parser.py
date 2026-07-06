import asyncio

from app.parsers.http_client import MarketplaceHttpClient
from app.parsers.ozon import OzonParser
from app.workers.http_client_manager import close_browser, get_page

PRODUCT_URL = "https://ozon.ru/t/lwPpFFD"


async def main() -> None:
    page = await get_page()
    parser = OzonParser(http_client=MarketplaceHttpClient(page=page))

    try:
        product_data = await parser.parse(PRODUCT_URL)
        print(product_data)
    finally:
        await close_browser()


if __name__ == "__main__":
    asyncio.run(main())
