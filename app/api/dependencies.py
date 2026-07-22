from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheService
from app.core.database import get_db
from app.core.redis import get_redis
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.subscription import SubscriptionRepository
from app.repositories.user import UserRepository
from app.services.price import PriceCache, PriceService
from app.services.price_chart import PriceChartService
from app.services.subscription import SubscriptionService
from app.services.user import UserService


async def get_redis_client() -> Redis:
    """Возвращает асинхронный клиент Redis."""
    return await get_redis()


async def get_cache_service(redis_client: Redis = Depends(get_redis)) -> CacheService:
    """Возвращает сервис кэширования."""
    return CacheService(redis=redis_client)


def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    """Возвращает репозиторий пользователей."""
    return UserRepository(session)


def get_subscription_repository(
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRepository:
    """Возвращает репозиторий подписок."""
    return SubscriptionRepository(session)


def get_price_history_repository(
    session: AsyncSession = Depends(get_db),
) -> PriceHistoryRepository:
    """Возвращает репозиторий истории цен."""
    return PriceHistoryRepository(session)


def get_user_service(
    repository: UserRepository = Depends(get_user_repository),
) -> UserService:
    """Возвращает сервис пользователей."""
    return UserService(repository)


def get_subscription_service(
    repository: SubscriptionRepository = Depends(get_subscription_repository),
    cache: CacheService = Depends(get_cache_service),
) -> SubscriptionService:
    """Возвращает сервис подписок."""
    return SubscriptionService(subscription_repository=repository, cache=cache)


def get_price_service(
    repository: PriceHistoryRepository = Depends(get_price_history_repository),
    redis_client: Redis = Depends(get_redis_client),
) -> PriceService:
    """Возвращает сервис цен с настроенным кэшем."""
    price_cache = PriceCache(redis_async=redis_client)
    return PriceService(
        price_history_repository=repository,
        price_cache=price_cache,
    )


def get_price_chart_service(
    price_service: PriceService = Depends(get_price_service),
    cache: CacheService = Depends(get_cache_service),
) -> PriceChartService:
    """Возвращает сервис генерации графиков цен."""
    return PriceChartService(
        price_service=price_service,
        cache_service=cache,
    )
