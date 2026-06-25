from decimal import Decimal

from app.repositories.price_history import (
    PriceHistoryRepository,
)


class PriceService:
    def __init__(
        self,
        price_history_repository: PriceHistoryRepository,
    ):
        self.price_history_repository = (
            price_history_repository
        )

    async def save_price(
        self,
        subscription_id: int,
        price: Decimal,
    ):
        return await self.price_history_repository.create(
            subscription_id=subscription_id,
            price=price,
        )
