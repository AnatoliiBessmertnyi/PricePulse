from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.subscription import (
    SubscriptionRepository,
)
from app.repositories.user import UserRepository
from app.services.subscription import (
    SubscriptionService,
)
from app.services.user import UserService


async def get_session() -> AsyncGenerator[
    AsyncSession,
    None,
]:
    async for session in get_db():
        yield session


def get_user_repository(
    session: AsyncSession = Depends(
        get_session,
    ),
) -> UserRepository:
    return UserRepository(session)


def get_subscription_repository(
    session: AsyncSession = Depends(
        get_session,
    ),
) -> SubscriptionRepository:
    return SubscriptionRepository(session)


def get_user_service(
    repository: UserRepository = Depends(
        get_user_repository,
    ),
) -> UserService:
    return UserService(repository)


def get_subscription_service(
    repository: SubscriptionRepository = Depends(
        get_subscription_repository,
    ),
) -> SubscriptionService:
    return SubscriptionService(repository)
