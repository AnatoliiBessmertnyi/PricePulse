import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.models.subscription import Subscription, SubscriptionStatus
from app.workers.celery_app import celery_app
from app.workers.database import create_worker_engine, create_worker_session_factory

logger = get_logger(__name__)


async def resync_queue() -> None:
    """
    Синхронизирует очередь Celery с текущим состоянием БД при старте системы.
    Стратегия: Полная очистка очереди и пересборка на основе БД (Single Source of Truth).
    Задачи сортируются по last_check_at, чтобы просроченные проверки выполнялись первыми.
    """
    setup_logging(settings.log_level)
    logger.info("starting_queue_resync")

    # 1. ОЧИСТКА ОЧЕРЕДИ: Не доверяем старым задачам, которые могли остаться после сбоя
    logger.info("purging_existing_tasks_from_queue")
    celery_app.control.purge()

    engine = create_worker_engine()
    async_session_factory = create_worker_session_factory(engine)
    now = datetime.now(UTC)
    scheduled_count = 0

    try:
        async with async_session_factory() as session:
            # 2. ПОЛУЧЕНИЕ И СОРТИРОВКА: nullsfirst() гарантирует, что новые подписки (без last_check_at) будут проверены первыми
            stmt = (
                select(Subscription.id, Subscription.last_check_at)
                .where(Subscription.is_active)
                .where(Subscription.status != SubscriptionStatus.ARCHIVED)
                .order_by(Subscription.last_check_at.asc().nullsfirst())
            )
            result = await session.execute(stmt)
            subscriptions = result.all()

            interval_seconds = settings.price_check_interval

            for sub_id, last_check_at in subscriptions:
                if last_check_at is None:
                    eta = now
                else:
                    expected_next = last_check_at + timedelta(seconds=interval_seconds)
                    # Если время уже пришло или прошло, ставим сейчас. Иначе - в будущее.
                    eta = now if expected_next <= now else expected_next

                celery_app.send_task("pricepulse.parse_price", args=[sub_id], eta=eta)
                scheduled_count += 1

        celery_app.send_task("pricepulse.cleanup_old_price_history")
        logger.info("history_cleanup_initial_scheduled")

        logger.info(
            "queue_resync_completed",
            total_subscriptions=len(subscriptions),
            scheduled_tasks=scheduled_count,
        )
    except Exception as e:
        logger.error("queue_resync_failed", error=str(e), exc_info=True)
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(resync_queue())