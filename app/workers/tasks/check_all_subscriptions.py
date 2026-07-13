import asyncio
from datetime import UTC, datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.repositories.subscription import SubscriptionRepository
from app.workers.celery_app import celery_app
from app.workers.database import create_worker_engine, create_worker_session_factory
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
    engine = create_worker_engine()
    async_session_factory = create_worker_session_factory(engine)

    try:
        async with async_session_factory() as session:
            repo = SubscriptionRepository(session)
            check_time = datetime.now(UTC)
            subscriptions = await repo.get_subscriptions_for_check(
                price_check_interval=settings.price_check_interval,
                current_time=check_time,
            )
            if not subscriptions:
                logger.info("no_subscriptions_ready_for_check")
                return

            logger.info("subscriptions_ready_for_check", count=len(subscriptions))

            successful_ids: list[int] = []
            for subscription in subscriptions:
                try:
                    parse_price.delay(subscription.id)
                    successful_ids.append(subscription.id)
                except Exception as e:
                    logger.error(
                        "failed_to_create_task",
                        subscription_id=subscription.id,
                        error=str(e),
                    )

            for sub_id in successful_ids:
                await repo.mark_last_check_now(sub_id, check_time=check_time)

            await session.commit()
            logger.info(
                "check_tasks_dispatched",
                count=len(successful_ids),
                total=len(subscriptions),
            )
    finally:
        await engine.dispose()
