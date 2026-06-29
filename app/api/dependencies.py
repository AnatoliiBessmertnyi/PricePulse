from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.subscription import (
    SubscriptionRepository,
)
from app.repositories.user import UserRepository
from app.services.price import PriceService
from app.services.subscription import (
    SubscriptionService,
)
from app.services.user import UserService


async def get_redis_client() -> Redis:
    return await get_redis()


def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


def get_subscription_repository(
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRepository:
    return SubscriptionRepository(session)


def get_price_history_repository(
    session: AsyncSession = Depends(get_db),
) -> PriceHistoryRepository:
    return PriceHistoryRepository(session)


def get_user_service(
    repository: UserRepository = Depends(get_user_repository),
) -> UserService:
    return UserService(repository)


def get_subscription_service(
    repository: SubscriptionRepository = Depends(get_subscription_repository),
) -> SubscriptionService:
    return SubscriptionService(repository)


def get_price_service(
    repository: PriceHistoryRepository = Depends(get_price_history_repository),
    redis_client: Redis = Depends(get_redis_client),
) -> PriceService:
    return PriceService(repository, redis_client)
