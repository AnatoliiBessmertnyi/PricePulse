from sqlalchemy import select

from app.models.price_history import PriceHistory
from app.repositories.base import BaseRepository


class PriceHistoryRepository(BaseRepository[PriceHistory]):
    model = PriceHistory

    async def get_by_subscription_id(
        self,
        subscription_id: int,
    ) -> list[PriceHistory]:
        stmt = (
            select(PriceHistory)
            .where(PriceHistory.subscription_id == subscription_id)
            .order_by(PriceHistory.created_at.desc())
        )

        result = await self.session.execute(stmt)

        return list(result.scalars().all())
