from app.repositories.subscription import (
    SubscriptionRepository,
)


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
    ):
        return await self.subscription_repository.create(
            user_id=user_id,
            marketplace=marketplace,
            product_url=product_url,
            target_price=target_price,
        )

    async def get_user_subscriptions(
        self,
        user_id: int,
    ):
        return await self.subscription_repository.get_by_user_id(
            user_id,
        )
