import json
import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.parsers.base import BaseParser
from app.parsers.http_client import MarketplaceHttpClient
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
        html, final_url = await self.http_client.get(
            product_url,
        )

        product_name = self._extract_product_name(
            html,
        )

        current_price = self._extract_price(
            html,
            final_url,
        )

        if current_price is None:
            raise ValueError(
                f"Price not found for product: {product_name}. "
                f"Ozon may have changed the layout or blocked the request.",
            )

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

    def _extract_price(self, html: str, product_url: str) -> Decimal | None:
        """Извлекает цену товара, находя SKU из URL и ища цену рядом с ним в HTML."""
        sku = self._extract_sku_from_url(product_url)
        if not sku:
            return None

        # Ищем SKU, допуская любые пробелы вокруг двоеточия и опциональные кавычки
        sku_pattern = re.compile(rf'"sku"\s*:\s*"?{sku}"?')
        
        # Находим все вхождения SKU в HTML
        matches = list(sku_pattern.finditer(html))
        if not matches:
            return None

        # Перебираем все вхождения, пока не найдем то, где есть цена
        for match in matches:
            sku_pos = match.start()
            # Берем кусок HTML размером 3000 символов после найденного SKU
            chunk = html[sku_pos : sku_pos + 3000]

            # Проверяем, есть ли в этом чанке слово "price"
            if '"price"' not in chunk:
                continue

            # Пытаемся найти цену как число (например, "price": 3301)
            price_match = re.search(r'"price"\s*:\s*(\d+)', chunk)
            if price_match:
                return Decimal(price_match.group(1))

            # Fallback: ищем цену как строку (например, "price": "3 301 ₽")
            price_match = re.search(r'"price"\s*:\s*"([\d\s\u202f,\.]+)', chunk)
            if price_match:
                price_str = re.sub(r"[^\d,\.]", "", price_match.group(1)).replace(",", ".")
                if price_str:
                    try:
                        return Decimal(price_str)
                    except InvalidOperation:
                        pass

        return None

    def _extract_sku_from_url(
        self, 
        product_url: str,
    ) -> str | None:
        """Извлекает SKU товара из URL.
        URL формат: https://www.ozon.ru/product/krossovki-air-force-1-blood-2751160853/
        """
        # Ищем число из 5-12 цифр в конце пути перед слэшем
        match = re.search(r"-(\d{5,12})/?", product_url)
        return match.group(1) if match else None
