import asyncio
import base64
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import matplotlib

matplotlib.use("Agg")  # Обязательно для headless-окружения
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from app.core.cache import CacheService
from app.core.logging import get_logger
from app.repositories.price_history import PriceHistoryRepository

logger = get_logger(__name__)

# Настройка шрифтов для поддержки кириллицы
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


class PriceChartService:
    def __init__(
        self,
        price_history_repository: PriceHistoryRepository,
        cache_service: CacheService,
    ) -> None:
        self._repo = price_history_repository
        self._cache = cache_service

    async def get_chart_image(
        self, subscription_id: int, period: str, target_price: Decimal | None
    ) -> bytes | None:
        cache_key = f"chart:{subscription_id}:{period}"

        # 1. Проверяем кэш (используем JSON, так как он безопасно хранит Base64-строки)
        cached = await self._cache.get_json(cache_key)
        if cached and "data" in cached:
            return base64.b64decode(cached["data"])

        # 2. Получаем данные из БД
        history = await self._repo.get_by_subscription_id(subscription_id)
        if not history:
            return None

        now = datetime.now(UTC)
        if period == "7d":
            cutoff = now - timedelta(days=7)
        elif period == "30d":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = None

        filtered_data = [
            (h.created_at, float(h.price))
            for h in history
            if cutoff is None or h.created_at >= cutoff
        ]
        filtered_data.sort(key=lambda x: x[0])

        if len(filtered_data) < 2:
            return None

        dates = [item[0] for item in filtered_data]
        prices = [item[1] for item in filtered_data]

        # 3. Генерируем график в отдельном потоке
        image_bytes = await asyncio.to_thread(
            self._render_chart, dates, prices, target_price
        )

        # 4. Кэшируем как Base64-строку внутри JSON (спасает от decode_responses=True)
        if image_bytes:
            b64_data = base64.b64encode(image_bytes).decode("utf-8")
            await self._cache.set_json(cache_key, {"data": b64_data}, ttl=300)

        return image_bytes

    def _render_chart(
        self, dates: list[datetime], prices: list[float], target_price: Decimal | None
    ) -> bytes:
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
