import asyncio
import base64
import io
from datetime import datetime
from decimal import Decimal

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from app.core.cache import CacheService
from app.core.logging import get_logger
from app.services.price import PriceService

logger = get_logger(__name__)

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


class PriceChartService:
    """Сервис для генерации графиков цен с использованием агрегированных данных."""

    def __init__(
        self,
        price_service: PriceService,
        cache_service: CacheService,
    ) -> None:
        self._price_service = price_service
        self._cache = cache_service

    async def get_chart_image(
        self, subscription_id: int, period: str, target_price: Decimal | None
    ) -> bytes | None:
        """Генерирует изображение графика цен за указанный период."""
        cache_key = f"chart:{subscription_id}:{period}"

        cached = await self._cache.get_json(cache_key)
        if cached and "data" in cached:
            return base64.b64decode(cached["data"])

        history = await self._price_service.get_price_history(subscription_id, period)
        if not history:
            return None

        # Сортируем по timestamp (агрегированные данные приходят в обратном порядке)
        history.sort(key=lambda x: x["timestamp"])

        if len(history) < 2:
            return None

        dates = [item["timestamp"] for item in history]
        prices = [item["price"] for item in history]

        image_bytes = await asyncio.to_thread(
            self._render_chart, dates, prices, target_price
        )

        if image_bytes:
            b64_data = base64.b64encode(image_bytes).decode("utf-8")
            await self._cache.set_json(cache_key, {"data": b64_data}, ttl=300)

        return image_bytes

    def _render_chart(
        self, dates: list[datetime], prices: list[float], target_price: Decimal | None
    ) -> bytes:
        """Рендерит график в отдельном потоке и возвращает PNG-изображение."""
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)

        ax.plot(
            dates,
            prices,
            marker="o",
            linestyle="-",
            color="#1f77b4",
            linewidth=2,
            markersize=4,
        )

        if target_price is not None:
            target_val = float(target_price)
            ax.axhline(
                y=target_val,
                color="#ff7f0e",
                linestyle="--",
                linewidth=1.5,
                label=f"Цель: {target_val:,.0f} ₽",
            )
            ax.legend(loc="upper left")

        ax.set_ylabel("Цена (₽)", fontsize=10)
        ax.grid(True, linestyle=":", alpha=0.7)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        plt.xticks(rotation=45, fontsize=9)
        plt.yticks(fontsize=9)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)

        return buf.getvalue()
