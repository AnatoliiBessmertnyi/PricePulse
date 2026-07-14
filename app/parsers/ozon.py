import contextlib
import html
import json
import re
import time
import urllib.parse
from decimal import Decimal, InvalidOperation

from app.core.logging import get_logger
from app.parsers.base import BaseParser
from app.parsers.exceptions import ProductDataNotFoundError
from app.parsers.http_client import MarketplaceHttpClient
from app.parsers.schemas import ProductData, VariantData

logger = get_logger(__name__)


class OzonParser(BaseParser):
    def __init__(self, http_client: MarketplaceHttpClient) -> None:
        self.http_client = http_client

    async def parse(self, product_url: str) -> ProductData:
        start_time = time.monotonic()
        logger.info("ozon_parse_start", url=product_url)
        html_content, final_url = await self.http_client.get(product_url)

        if "/search/" in final_url:
            logger.warning(
                "ozon_redirected_to_search",
                original_url=product_url,
                final_url=final_url,
            )
            fallback_name = "Товар не найден"
            match = re.search(r"text=([^&]+)", final_url)
            if match:
                fallback_name = urllib.parse.unquote(match.group(1)).replace("+", " ")

            raise ProductDataNotFoundError(
                f"Товар не найден или удален: {fallback_name}"
            )

        product_name = self._extract_product_name(html_content)
        variant = self._extract_selected_variant(html_content, final_url)

        if variant is None:
            fallback_price = self._extract_fallback_price(html_content)
            if fallback_price is not None:
                logger.info(
                    "ozon_using_fallback_price",
                    url=final_url,
                    price=str(fallback_price),
                )
                return ProductData(
                    product_name=product_name,
                    current_price=fallback_price,
                    selected_options={},
                )

            logger.warning(
                "ozon_variant_not_found", url=final_url, product_name=product_name
            )
            raise ValueError(
                f"Price not found for product: {product_name}. "
                f"Ozon may have changed the layout or blocked the request.",
            )

        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.info(
            "ozon_parse_success",
            url=final_url,
            product_name=product_name,
            price=str(variant.price),
            duration_ms=duration_ms,
        )
        return ProductData(
            product_name=product_name,
            current_price=variant.price,
            selected_options=variant.selected_options,
        )

    def _extract_product_name(self, html_content: str) -> str:
        match = re.search(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html_content,
            re.DOTALL | re.IGNORECASE,
        )

        if not match:
            title_match = re.search(
                r"<title>(.*?)</title>", html_content, re.IGNORECASE
            )
            if title_match:
                name = title_match.group(1).split("|")[0].split("OZON")[0].strip()
                if name:
                    return name
            raise ValueError("Ozon product schema not found")

        script_content = match.group(1).strip()
        if not script_content:
            raise ValueError("Ozon product schema is empty")

        try:
            product_data = json.loads(script_content)
        except json.JSONDecodeError as e:
            raise ValueError("Ozon product schema is not valid JSON") from e

        product_name = product_data.get("name")
        if not isinstance(product_name, str):
            raise ValueError("Product name not found")

        return product_name

    def _extract_selected_variant(
        self, html_content: str, product_url: str
    ) -> VariantData | None:
        sku = self._extract_sku_from_url(product_url)
        if sku is None:
            logger.warning("ozon_sku_not_extracted", url=product_url)
            return None

        pattern = re.compile(
            r'<div[^>]+data-state=(["\'])(.*?)\1[^>]*>', re.DOTALL | re.IGNORECASE
        )

        for match in pattern.finditer(html_content):
            state = match.group(2)
            if not state:
                continue

            decoded_state = html.unescape(state)
            sku_pattern = re.compile(rf'["\']sku["\']\s*:\s*["\']?{sku}["\']?')
            if not sku_pattern.search(decoded_state):
                continue

            result = self._extract_variant_from_state(decoded_state, sku)
            if result is not None:
                return result

        logger.warning("ozon_no_variant_with_sku", url=product_url, sku=sku)
        return None

    def _extract_sku_from_url(self, product_url: str) -> str | None:
        """
        Извлекает SKU товара из URL Ozon.
        Например: .../item-name-2751160853/ -> 2751160853
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
                        clean = re.sub(r"[^\d,.]", "", raw_price).replace(",", ".")
                        if clean:
                            with contextlib.suppress(InvalidOperation):
                                price = Decimal(clean)

                    variant_data = variant.get("data", {})
                    value = variant_data.get("searchableText")
                    if aspect_name and value:
                        selected_options[aspect_name] = value

                    break

        if price is None:
            return None

        return VariantData(price=price, selected_options=selected_options)

    def _extract_fallback_price(self, html_content: str) -> Decimal | None:
        """
        Запасной вариант извлечения цены, если data-state не найден или изменился.
        Ищет цену в мета-тегах OpenGraph и JSON-LD.
        """
        meta_patterns = [
            r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([\d,.]+)["\']',
            r'<meta[^>]+content=["\']([\d,.]+)["\'][^>]+property=["\']product:price:amount["\']',
        ]
        for pattern in meta_patterns:
            meta_match = re.search(pattern, html_content, re.IGNORECASE)
            if meta_match:
                with contextlib.suppress(InvalidOperation):
                    return Decimal(meta_match.group(1).replace(",", "."))

        try:
            ld_pattern = re.compile(
                r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                re.DOTALL | re.IGNORECASE,
            )
            for match in ld_pattern.finditer(html_content):
                data = json.loads(match.group(1).strip())
                if isinstance(data, dict) and "offers" in data:
                    offers = data["offers"]
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = offers.get("price")
                    if price:
                        with contextlib.suppress(InvalidOperation):
                            return Decimal(str(price).replace(",", "."))
        except Exception as e:
            logger.warning("ozon_fallback_price_parse_error", error=str(e))

        return None
