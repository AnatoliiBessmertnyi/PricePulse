import asyncio
import time
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.logging import get_logger
from app.models.subscription import SubscriptionStatus
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.subscription import SubscriptionRepository
from app.services.notification import NotificationService
from app.services.subscription import SubscriptionService
from app.workers.celery_app import celery_app
from app.workers.database import create_worker_engine, create_worker_session_factory
from app.workers.dependencies import get_price_parsing_service
from app.workers.settings import TASK_PARSE_PRICE

logger = get_logger(__name__)


async def _schedule_if_not_archived(subscription_id: int) -> None:
    """Планирует следующую проверку, если подписка не находится в архиве."""
    engine = create_worker_engine()
    async_session_factory = create_worker_session_factory(engine)
    try:
        async with async_session_factory() as session:
            repo = SubscriptionRepository(session)
            sub = await repo.get(subscription_id)
            if sub and sub.status != SubscriptionStatus.ARCHIVED:
                next_check_at = datetime.now(UTC) + timedelta(
                    seconds=settings.price_check_interval
                )
                celery_app.send_task(
                    TASK_PARSE_PRICE, args=[subscription_id], eta=next_check_at
                )
                logger.info(
                    "parse_price_next_scheduled",
                    subscription_id=subscription_id,
                    eta=next_check_at.isoformat(),
                )
    finally:
        await engine.dispose()


async def _parse_price(subscription_id: int) -> None:
    """Выполняет основную логику парсинга."""
    engine = create_worker_engine()
    async_session_factory = create_worker_session_factory(engine)
    start_time = time.monotonic()
    logger.info("parse_price_started", subscription_id=subscription_id)

    try:
        async with async_session_factory() as session:
            repo = SubscriptionRepository(session)
            history_repo = PriceHistoryRepository(session)
            
            sub_before = await repo.get(subscription_id)
            old_price = sub_before.current_price if sub_before else None
            
            if old_price is None:
                old_price = await history_repo.get_latest_price(subscription_id)

            service = await get_price_parsing_service(session)
            is_active = await service.parse_subscription(subscription_id=subscription_id)
            
            if not is_active:
                logger.info("parse_price_skipped_archived", subscription_id=subscription_id)
                return

            subscription = await repo.get(subscription_id)
            
            if subscription and subscription.current_price and subscription.target_price:
                subscription_service = SubscriptionService(repo)
                notification_service = NotificationService(subscription_service)
                
                if notification_service.should_send_alert(subscription, subscription.current_price):
                    notification_service.notify_price_drop(subscription, old_price=old_price)
                    await subscription_service.mark_alert_sent(subscription_id)

            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "parse_price_completed",
                subscription_id=subscription_id,
                price=float(subscription.current_price) if subscription and subscription.current_price else None,
                duration_ms=duration_ms,
            )

            await repo.mark_as_idle(subscription_id)
            await session.commit()

    except Exception as e:
        logger.exception("parse_price_failed", subscription_id=subscription_id, error=str(e))
        async with async_session_factory() as session:
            repo = SubscriptionRepository(session)
            await repo.mark_as_failed(subscription_id)
            await session.commit()
    finally:
        await engine.dispose()

    await _schedule_if_not_archived(subscription_id)


@celery_app.task(name=TASK_PARSE_PRICE)
def parse_price(subscription_id: int) -> None:
    """
    Выполняет парсинг цены.
    Управление повторными попытками полностью делегировано механизму eta.
    Встроенные retry Celery отключены во избежание дублирования задач (Task Storm).
    """
    try:
        asyncio.run(_parse_price(subscription_id))
    except Exception as e:
        logger.critical(
            "parse_price_critical_error",
            subscription_id=subscription_id,
            error=str(e),
            exc_info=True,
        )
        asyncio.run(_schedule_if_not_archived(subscription_id))
