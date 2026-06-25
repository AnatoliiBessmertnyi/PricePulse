import json
from decimal import Decimal

from bs4 import BeautifulSoup

from app.parsers.base import BaseParser
from app.parsers.http_client import MarketplaceHttpClient
from app.parsers.schemas import ProductData
from app.parsers.exceptions import ProductDataNotFoundError

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

        # current_price = self._extract_price(
        #     html,
        # )
        current_price = Decimal("0")

        return ProductData(
            product_name=product_name,
            current_price=current_price,
        )

    def _extract_product_name(
        self,
        html: str,
    ) -> str:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        script = soup.find(
            "script",
            attrs={
                "type": "application/ld+json",
            },
        )

        if script is None:
            raise ValueError(
                "Ozon product schema not found",
            )

        if script.string is None:
            raise ValueError(
                "Ozon product schema is empty",
            )

        product_data = json.loads(
            script.string,
        )

        product_name = product_data.get(
            "name",
        )

        if not isinstance(
            product_name,
            str,
        ):
            raise ValueError(
                "Product name not found",
            )

        return product_name

    def _extract_price(
        self,
        html: str,
    ) -> Decimal:
        raise NotImplementedError
