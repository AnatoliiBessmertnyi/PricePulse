from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.models.price_history import PriceHistory
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.base import BaseRepository


class PriceHistoryRepository(BaseRepository[PriceHistory]):
    """Репозиторий для работы с историей цен с поддержкой агрегации."""

    model = PriceHistory

    async def get_by_subscription_id(self, subscription_id: int) -> list[PriceHistory]:
        """Получает все записи истории цен для указанной подписки."""
        stmt = (
            select(PriceHistory)
            .where(PriceHistory.subscription_id == subscription_id)
            .order_by(PriceHistory.created_at.desc())
        )

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def get_aggregated_price_history(
        self, subscription_id: int, period: str
    ) -> list[dict]:
        """Получает агрегированную историю цен с группировкой по периоду."""
        if period == "24h":
            stmt = (
                select(
                    PriceHistory.created_at.label("timestamp"),
                    PriceHistory.price.label("price"),
                    PriceHistory.price.label("min"),
                    PriceHistory.price.label("max"),
                    func.count(PriceHistory.id).label("count"),
                )
                .where(PriceHistory.subscription_id == subscription_id)
                .order_by(PriceHistory.created_at.desc())
                .limit(100)
            )
        else:
            if period == "7d":
                trunc_func = func.date_trunc("hour", PriceHistory.created_at)
            elif period == "30d":
                trunc_func = func.date_trunc("day", PriceHistory.created_at)
            else:  # all
                trunc_func = func.date_trunc("month", PriceHistory.created_at)

            stmt = (
                select(
                    trunc_func.label("timestamp"),
                    func.avg(PriceHistory.price).label("price"),
                    func.min(PriceHistory.price).label("min"),
                    func.max(PriceHistory.price).label("max"),
                    func.count(PriceHistory.id).label("count"),
                )
                .where(PriceHistory.subscription_id == subscription_id)
                .group_by(trunc_func)
                .order_by(trunc_func.desc())
            )

        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "timestamp": row.timestamp,
                "price": float(row.price),
                "min": float(row.min),
                "max": float(row.max),
                "count": row.count,
            }
            for row in rows
        ]

    async def cleanup_old_archived_history(self, days: int = 90) -> int:
        """Удаляет записи истории цен старых архивных подписок."""
        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        stmt = delete(PriceHistory).where(
            PriceHistory.subscription_id.in_(
                select(Subscription.id).where(
                    Subscription.status == SubscriptionStatus.ARCHIVED
                )
            ),
            PriceHistory.created_at < cutoff_date,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount
