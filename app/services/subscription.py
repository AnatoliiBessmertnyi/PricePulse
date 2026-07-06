from app.models.subscription import Subscription
from app.repositories.subscription import SubscriptionRepository


class SubscriptionService:
    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
    ):
        self.subscription_repository = subscription_repository

    async def create_subscription(
        self,
        user_id: int,
        marketplace: str,
        product_url: str,
        target_price: float | None = None,
    ) -> Subscription:
        subscription = await self.subscription_repository.create(
            user_id=user_id,
            marketplace=marketplace,
            product_url=product_url,
            target_price=target_price,
        )
        await self.subscription_repository.session.commit()
        return subscription

    async def get_user_subscriptions(
        self,
        user_id: int,
    ) -> list[Subscription]:
        return await self.subscription_repository.get_by_user_id(user_id)

    async def get_subscription(
        self,
        subscription_id: int,
    ) -> Subscription | None:
        return await self.subscription_repository.get(subscription_id)

    async def delete_subscription(
        self,
        subscription_id: int,
        user_id: int,
    ) -> bool:
        """Удалить подписку. Возвращает True если удалена, False если не найдена."""
        deleted = await self.subscription_repository.delete_by_user(
            subscription_id, user_id
        )
        if deleted:
            await self.subscription_repository.session.commit()
        return deleted
