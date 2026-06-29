from sqlalchemy import select

from app.models.subscription import Subscription
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get_by_user_id(
        self,
        user_id: int,
    ) -> list[Subscription]:
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
        )

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def get_all(
        self,
    ) -> list[Subscription]:
        stmt = select(Subscription)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())
