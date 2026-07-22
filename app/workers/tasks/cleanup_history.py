import asyncio
from datetime import UTC, datetime, timedelta

from app.core.logging import get_logger
from app.repositories.price_history import PriceHistoryRepository
from app.workers.celery_app import celery_app
from app.workers.database import create_worker_engine, create_worker_session_factory
from app.workers.settings import TASK_CLEANUP_HISTORY

logger = get_logger(__name__)


@celery_app.task(name=TASK_CLEANUP_HISTORY)
def cleanup_old_price_history() -> None:
    """Запускает асинхронную задачу очистки старой истории цен."""
    asyncio.run(_cleanup_old_price_history())


async def _cleanup_old_price_history() -> None:
    """Выполняет очистку и планирует следующий запуск через 24 часа."""
    engine = create_worker_engine()
    async_session_factory = create_worker_session_factory(engine)

    try:
        async with async_session_factory() as session:
            repo = PriceHistoryRepository(session)
            deleted_count = await repo.cleanup_old_archived_history(days=90)
            logger.info("history_cleanup_completed", deleted_count=deleted_count)
    except Exception as e:
        logger.error("history_cleanup_failed", error=str(e), exc_info=True)
    finally:
        await engine.dispose()

    next_run = datetime.now(UTC) + timedelta(days=1)
    cleanup_old_price_history.apply_async(eta=next_run)
    logger.info("history_cleanup_next_scheduled", eta=next_run.isoformat())
