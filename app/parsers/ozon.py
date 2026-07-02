# app/parsers/ozon.py
import json
import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.parsers.base import BaseParser
from app.parsers.http_client import MarketplaceHttpClient
from app.parsers.schemas import ProductData, VariantData

logger = get_logger(__name__)


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
        logger.info(
            "ozon_parse_start",
            url=product_url,
        )
        html, final_url = await self.http_client.get(
            product_url,
        )

        # ОТЛАДКА: Логируем полученный HTML
        logger.debug(
            "ozon_html_received",
            original_url=product_url,
            final_url=final_url,
            html_length=len(html),
        )

        # Проверяем наличие JSON-LD схемы
        soup = BeautifulSoup(html, "html.parser")
        ld_json_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

        if not ld_json_scripts:
            # Логируем все script теги для отладки
            all_scripts = soup.find_all("script")
            logger.warning(
                "ozon_no_ld_json_found",
                url=final_url,
                total_scripts=len(all_scripts),
                script_types=[s.get("type") for s in all_scripts if s.get("type")],
                html_preview=html[:500],
            )

        product_name = self._extract_product_name(
            html,
        )

        variant = self._extract_selected_variant(
            html,
            final_url,
        )

        if variant is None:
            logger.warning(
                "ozon_variant_not_found",
                url=final_url,
                product_name=product_name,
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

    def _extract_selected_variant(
        self,
        html: str,
        product_url: str,
    ) -> VariantData | None:
        sku = self._extract_sku_from_url(
            product_url,
        )

        if sku is None:
            logger.warning(
                "ozon_sku_not_extracted",
                url=product_url,
            )
            return None

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        blocks = soup.find_all(
            "div",
            attrs={
                "data-state": True,
            },
        )

        logger.debug(
            "ozon_data_state_blocks",
            url=product_url,
            sku=sku,
            blocks_found=len(blocks),
        )

        for block in blocks:
            state = block.get("data-state")

            if not state:
                continue

            sku_pattern = re.compile(rf'"sku"\s*:\s*"?{sku}"?')
            if not sku_pattern.search(state):
                continue

            result = self._extract_variant_from_state(
                state,
                sku,
            )

            if result is not None:
                return result

        logger.warning(
            "ozon_no_variant_with_sku",
            url=product_url,
            sku=sku,
        )
        return None

    def _extract_sku_from_url(
        self,
        product_url: str,
    ) -> str | None:
        """
        Извлекает SKU товара из URL Ozon.

        Например:
        https://www.ozon.ru/product/item-name-2751160853/
        → 2751160853
        """
        # Ищем число из 5-12 цифр в конце пути перед слэшем
        match = re.search(r"-(\d{5,12})/?", product_url)
        return match.group(1) if match else None

    def _extract_variant_from_state(
        self,
        state: str,
        sku: str,
    ) -> VariantData | None:
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
                        # Убираем пробелы, ₽, неразрывные пробелы
                        clean = re.sub(r"[^\d,\.]", "", raw_price).replace(",", ".")
                        if clean:
                            try:
                                price = Decimal(clean)
                            except InvalidOperation:
                                pass

                data = variant.get(
                    "data",
                    {},
                )
                value = data.get(
                    "searchableText",
                )

                if aspect_name and value:
                    selected_options[aspect_name] = value

                break

        if price is None:
            return None

        return VariantData(
            price=price,
            selected_options=selected_options,
        )
