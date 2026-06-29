import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models.subscription import Subscription
from app.workers.celery_app import celery_app
from app.workers.settings import TASK_CHECK_ALL_SUBSCRIPTIONS
from app.workers.tasks.parse_price import parse_price


@celery_app.task(name=TASK_CHECK_ALL_SUBSCRIPTIONS)
def check_all_subscriptions() -> None:
    """Получить все активные подписки и поставить задачи на парсинг"""
    asyncio.run(_check_all_subscriptions())


async def _check_all_subscriptions() -> None:
    """Получить все активные подписки из БД и поставить задачи на парсинг"""
    # Создаем engine для этой задачи (не используем глобальный)
    engine = create_async_engine(
        settings.postgres_url,
        echo=False,
        pool_pre_ping=True,
    )

    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.is_active)
            )
            subscriptions = result.scalars().all()

            for subscription in subscriptions:
                parse_price.delay(subscription.id)
    finally:
        await engine.dispose()
