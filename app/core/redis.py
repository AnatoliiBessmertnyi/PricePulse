from redis import Redis as SyncRedis
from redis.asyncio import Redis

from app.core.config import settings


async def get_redis() -> Redis:
    """Асинхронный Redis клиент для FastAPI"""
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def get_redis_sync() -> SyncRedis:
    """Синхронный Redis клиент для Celery worker"""
    return SyncRedis(
        host=settings.redis_host,
        port=settings.redis_port,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
