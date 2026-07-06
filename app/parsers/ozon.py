# app/parsers/ozon.py
import contextlib
import json
import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.parsers.base import BaseParser
from app.parsers.http_client import MarketplaceHttpClient
from app.parsers.schemas import ProductData, VariantData

logger = get_logger(__name__)


class _SoupProxy:
    """Прокси для BeautifulSoup с коротким __repr__ для логов."""

    __slots__ = ("_soup",)

    def __init__(self, soup: BeautifulSoup) -> None:
        self._soup = soup

    def __getattr__(self, name: str):
        return getattr(self._soup, name)

    def __repr__(self) -> str:
        return f"<BeautifulSoup: {len(str(self._soup))} chars>"


class OzonParser(BaseParser):
    def __init__(self, http_client: MarketplaceHttpClient) -> None:
        self.http_client = http_client

    async def parse(self, product_url: str) -> ProductData:
        logger.info("ozon_parse_start", url=product_url)
        html, final_url = await self.http_client.get(product_url)
        soup = _SoupProxy(BeautifulSoup(html, "html.parser"))
        product_name = self._extract_product_name(soup)
        variant = self._extract_selected_variant(soup, final_url)
        if variant is None:
            logger.warning(
                "ozon_variant_not_found", url=final_url, product_name=product_name
            )
            raise ValueError(
                f"Price not found for product: {product_name}. "
                f"Ozon may have changed the layout or blocked the request.",
            )

        logger.info(
            "ozon_parse_success",
            url=final_url,
            product_name=product_name,
            price=str(variant.price),
        )
        return ProductData(
            product_name=product_name,
            current_price=variant.price,
            selected_options=variant.selected_options,
        )

    def _extract_product_name(self, soup: BeautifulSoup) -> str:
        script = soup.find("script", attrs={"type": "application/ld+json"})
        if script is None:
            raise ValueError("Ozon product schema not found")

        if script.string is None:
            raise ValueError("Ozon product schema is empty")

        product_data = json.loads(script.string)
        product_name = product_data.get("name")
        if not isinstance(product_name, str):
            raise ValueError("Product name not found")

        return product_name

    def _extract_selected_variant(
        self, soup: BeautifulSoup, product_url: str
    ) -> VariantData | None:
        sku = self._extract_sku_from_url(product_url)
        if sku is None:
            logger.warning("ozon_sku_not_extracted", url=product_url)
            return None

        blocks = soup.find_all("div", attrs={"data-state": True})
        for block in blocks:
            state = block.get("data-state")
            if not state:
                continue

            sku_pattern = re.compile(rf'"sku"\s*:\s*"?{sku}"?')
            if not sku_pattern.search(state):
                continue

            result = self._extract_variant_from_state(state, sku)
            if result is not None:
                return result

        logger.warning("ozon_no_variant_with_sku", url=product_url, sku=sku)
        return None

    def _extract_sku_from_url(self, product_url: str) -> str | None:
        """
        Извлекает SKU товара из URL Ozon.

        Например:
        https://www.ozon.ru/product/item-name-2751160853/
        → 2751160853
        """
        match = re.search(r"-(\d{5,12})/?", product_url)
        return match.group(1) if match else None

    def _extract_variant_from_state(self, state: str, sku: str) -> VariantData | None:
        try:
            data = json.loads(state)
        except json.JSONDecodeError:
            return None

        price: Decimal | None = None
        selected_options: dict[str, str] = {}

        for aspect in data.get("aspects", []):
            aspect_name = aspect.get("aspectName")

            for variant in aspect.get("variants", []):
                if str(variant.get("sku")) != sku:
                    continue

                if not variant.get("active"):
                    continue

                if price is None and variant.get("price") is not None:
                    raw_price = variant["price"]
                    if isinstance(raw_price, (int, float)):
                        price = Decimal(str(raw_price))
                    elif isinstance(raw_price, str):
                        clean = re.sub(r"[^\d,\.]", "", raw_price).replace(",", ".")
                        if clean:
                            with contextlib.suppress(InvalidOperation):
                                price = Decimal(clean)

                data = variant.get("data", {})
                value = data.get("searchableText")

                if aspect_name and value:
                    selected_options[aspect_name] = value

                break

        if price is None:
            return None

        return VariantData(price=price, selected_options=selected_options)
