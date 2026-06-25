from decimal import Decimal

from app.parsers.http_client import MarketplaceHttpClient
from app.parsers.base import BaseParser
from app.parsers.schemas import ProductData


class OzonParser(BaseParser):
    def __init__(
        self,
        http_client: MarketplaceHttpClient,
    ) -> None:
        self.http_client = http_client

    async def parse(
        self,
        product_url: str,
    ) -> ProductData:
        html = await self.http_client.get(
            product_url,
        )

        product_name = self._extract_product_name(
            html,
        )

        current_price = self._extract_price(
            html,
        )

        return ProductData(
            product_name=product_name,
            current_price=current_price,
        )

    def _extract_product_name(
        self,
        html: str,
    ) -> str:
        raise NotImplementedError

    def _extract_price(
        self,
        html: str,
    ) -> Decimal:
        raise NotImplementedError
