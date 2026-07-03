from redis import Redis as SyncRedis
from redis.asyncio import Redis

from app.core.config import settings

_sync_redis: SyncRedis | None = None
_async_redis: Redis | None = None


async def get_redis() -> Redis:
    """Асинхронный Redis клиент для FastAPI"""
    global _async_redis
    if _async_redis is None:
        _async_redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    return _async_redis


def get_redis_sync() -> SyncRedis:
    """Синхронный Redis клиент для Celery worker"""
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = SyncRedis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

    return _sync_redis
