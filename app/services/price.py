import json
from decimal import Decimal

from redis import Redis as SyncRedis
from redis.asyncio import Redis

from app.core.constants import REDIS_PRICE_TTL
from app.repositories.price_history import PriceHistoryRepository


class PriceCache:
    """Кэш для работы с Redis, инкапсулирующий синхронную и асинхронную логику."""

    def __init__(
        self, redis_sync: SyncRedis | None = None, redis_async: Redis | None = None
    ) -> None:
        self._redis_sync = redis_sync
        self._redis_async = redis_async

    async def set(self, key: str, value: str, ttl: int) -> None:
        """Сохраняет строковое значение в кэш с заданным временем жизни."""
        if self._redis_sync:
            self._redis_sync.setex(key, ttl, value)
        elif self._redis_async:
            await self._redis_async.setex(key, ttl, value)

    async def get(self, key: str) -> str | None:
        """Получает строковое значение из кэша по ключу."""
        if self._redis_async:
            cached_price = await self._redis_async.get(key)
            if cached_price:
                return cached_price

        if self._redis_sync:
            cached_price = self._redis_sync.get(key)
            if cached_price:
                return cached_price

        return None

    async def delete(self, key: str) -> None:
        """Удаляет ключ из кэша синхронно или асинхронно."""
        if self._redis_async:
            await self._redis_async.delete(key)
        elif self._redis_sync:
            self._redis_sync.delete(key)


class PriceService:
    """Сервис для управления ценами и историей цен с поддержкой кэширования."""

    def __init__(
        self,
        price_history_repository: PriceHistoryRepository,
        price_cache: PriceCache,
    ) -> None:
        self._price_history_repository = price_history_repository
        self._price_cache = price_cache

    async def save_price(self, subscription_id: int, price: Decimal) -> None:
        """Сохраняет новую цену в историю и инвалидирует кэш истории цен."""
        await self._price_history_repository.create(
            subscription_id=subscription_id, price=price
        )
        cache_key = f"price:latest:{subscription_id}"
        await self._price_cache.set(cache_key, str(price), REDIS_PRICE_TTL)
        await self._price_cache.delete(f"prices:history:{subscription_id}")

    async def get_price_history(self, subscription_id: int) -> list[dict]:
        """Получает историю цен из кэша или БД с последующим кэшированием результата."""
        cache_key = f"prices:history:{subscription_id}"
        cached_data = await self._price_cache.get(cache_key)
        if cached_data:
            return json.loads(cached_data)

        history = await self._price_history_repository.get_by_subscription_id(
            subscription_id
        )
        data_to_cache = [
            {
                "id": record.id,
                "subscription_id": record.subscription_id,
                "price": float(record.price),
                "created_at": record.created_at.isoformat(),
            }
            for record in history
        ]
        await self._price_cache.set(cache_key, json.dumps(data_to_cache), ttl=60)
        return data_to_cache

    async def get_latest_price(self, subscription_id: int) -> Decimal | None:
        """Получает последнюю известную цену из кэша или базы данных."""
        cache_key = f"price:latest:{subscription_id}"
        cached_price = await self._price_cache.get(cache_key)
        if cached_price:
            return Decimal(cached_price)

        history = await self._price_history_repository.get_by_subscription_id(
            subscription_id
        )
        if history:
            return history[0].price

        return None
