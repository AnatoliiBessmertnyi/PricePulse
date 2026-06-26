from decimal import Decimal

from app.repositories.price_history import PriceHistoryRepository


class PriceService:
    def __init__(
        self,
        price_history_repository: PriceHistoryRepository,
    ) -> None:
        self._price_history_repository = price_history_repository

    async def save_price(
        self,
        subscription_id: int,
        price: Decimal,
    ) -> None:
        await self._price_history_repository.create(
            subscription_id=subscription_id,
            price=price,
        )

    async def get_price_history(
        self,
        subscription_id: int,
    ):
        return await self._price_history_repository.get_by_subscription_id(
            subscription_id,
        )
