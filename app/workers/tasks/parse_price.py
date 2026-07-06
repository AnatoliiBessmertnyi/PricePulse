import asyncio

from celery.exceptions import SoftTimeLimitExceeded

from app.core.logging import get_logger
from app.parsers.exceptions import ParserError
from app.repositories.subscription import SubscriptionRepository
from app.workers.celery_app import celery_app
from app.workers.database import create_worker_engine, create_worker_session_factory
from app.workers.dependencies import get_price_parsing_service
from app.workers.settings import TASK_PARSE_PRICE

logger = get_logger(__name__)


@celery_app.task(
    name=TASK_PARSE_PRICE,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def parse_price(subscription_id: int) -> None:
    try:
        asyncio.run(_parse_price(subscription_id))
    except SoftTimeLimitExceeded:
        logger.warning("parse_price_timeout", subscription_id=subscription_id)
        asyncio.run(_mark_as_failed(subscription_id))
    except Exception as e:
        is_parse_error = isinstance(e, (ParserError, ValueError))
        logger.error(
            "parse_price_error" if not is_parse_error else "parse_price_parse_error",
            subscription_id=subscription_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        asyncio.run(_mark_as_failed(subscription_id))
        if not is_parse_error:
            raise


async def _mark_as_failed(subscription_id: int) -> None:
    """Пометить подписку как FAILED."""
    engine = create_worker_engine()
    async_session_factory = create_worker_session_factory(engine)
    try:
        async with async_session_factory() as session:
            repo = SubscriptionRepository(session)
            await repo.mark_as_failed(subscription_id)
            await session.commit()
    finally:
        await engine.dispose()


async def _parse_price(subscription_id: int) -> None:
    engine = create_worker_engine()
    async_session_factory = create_worker_session_factory(engine)

    try:
        async with async_session_factory() as session:
            repo = SubscriptionRepository(session)
            service = await get_price_parsing_service(session)
            await service.parse_subscription(subscription_id=subscription_id)
            await repo.mark_as_idle(subscription_id)
            await session.commit()

    except Exception as e:
        logger.exception(
            "parse_price_failed",
            subscription_id=subscription_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        await repo.mark_as_failed(subscription_id)
        await session.commit()
    finally:
        await engine.dispose()
