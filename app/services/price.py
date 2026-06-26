from decimal import Decimal

from redis import Redis as SyncRedis
from redis.asyncio import Redis

from app.repositories.price_history import PriceHistoryRepository


class PriceService:
    def __init__(
        self,
        price_history_repository: PriceHistoryRepository,
        redis_client: Redis | None = None,
        redis_client_sync: SyncRedis | None = None,
    ) -> None:
        self._price_history_repository = price_history_repository
        self._redis = redis_client
        self._redis_sync = redis_client_sync

    async def save_price(
        self,
        subscription_id: int,
        price: Decimal,
    ) -> None:
        await self._price_history_repository.create(
            subscription_id=subscription_id,
            price=price,
        )

        if self._redis_sync:
            cache_key = f"price:latest:{subscription_id}"
            self._redis_sync.setex(
                cache_key,
                3600,
                str(price),
            )
        elif self._redis:
            cache_key = f"price:latest:{subscription_id}"
            await self._redis.setex(
                cache_key,
                3600,
                str(price),
            )

    async def get_price_history(
        self,
        subscription_id: int,
    ):
        return await self._price_history_repository.get_by_subscription_id(
            subscription_id,
        )

    async def get_latest_price(
        self,
        subscription_id: int,
    ) -> Decimal | None:
        """Получить последнюю цену из кэша или БД"""
        if self._redis:
            cache_key = f"price:latest:{subscription_id}"
            cached_price = await self._redis.get(cache_key)
            if cached_price:
                return Decimal(cached_price)
        
        if self._redis_sync:
            cache_key = f"price:latest:{subscription_id}"
            cached_price = self._redis_sync.get(cache_key)
            if cached_price:
                return Decimal(cached_price)

        history = await self._price_history_repository.get_by_subscription_id(
            subscription_id,
        )
        if history:
            return history[0].price
        return None
