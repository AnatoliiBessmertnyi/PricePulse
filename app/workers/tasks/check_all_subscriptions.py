import asyncio

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.subscription import SubscriptionRepository
from app.workers.celery_app import celery_app
from app.workers.settings import TASK_CHECK_ALL_SUBSCRIPTIONS
from app.workers.tasks.parse_price import parse_price

logger = get_logger(__name__)


@celery_app.task(name=TASK_CHECK_ALL_SUBSCRIPTIONS)
def check_all_subscriptions() -> None:
    """Получить подписки, готовые к проверке, и создать задачи."""
    asyncio.run(_check_all_subscriptions())


async def _check_all_subscriptions() -> None:
    """
    Получить подписки, готовые к проверке,
    и создать задачи для их проверки.
    """
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
            repo = SubscriptionRepository(session)
            
            # Получаем подписки, готовые к проверке
            subscriptions = await repo.get_subscriptions_for_check(
                price_check_interval=settings.price_check_interval,
            )
            
            if not subscriptions:
                logger.info("no_subscriptions_ready_for_check")
                return
            
            logger.info(
                "subscriptions_ready_for_check",
                count=len(subscriptions),
            )

            # Создаём задачи и обновляем last_check_at СРАЗУ
            created_tasks = 0
            for subscription in subscriptions:
                try:
                    # Создаём задачу
                    parse_price.delay(subscription.id)
                    
                    # Обновляем last_check_at сразу (защита от дублирования)
                    await repo.mark_last_check_now(subscription.id)
                    
                    created_tasks += 1
                    
                except Exception as e:
                    logger.error(
                        "failed_to_create_task",
                        subscription_id=subscription.id,
                        error=str(e),
                    )

            # Фиксируем все изменения
            await session.commit()
            
            logger.info(
                "check_tasks_created",
                count=created_tasks,
                total=len(subscriptions),
            )
                
    finally:
        await engine.dispose()
