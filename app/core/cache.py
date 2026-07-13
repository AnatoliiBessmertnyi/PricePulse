import json
from typing import Any

from redis.asyncio import Redis

from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheService:
    """Универсальный сервис кэширования для FastAPI (JSON)."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_json(self, key: str) -> Any | None:
        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning("cache_get_error", key=key, error=str(e))
        return None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self._redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.warning("cache_set_error", key=key, error=str(e))

    async def delete(self, key: str) -> None:
        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
