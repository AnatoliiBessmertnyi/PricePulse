import asyncio

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.workers.celery_app import celery_app
from app.workers.dependencies import get_price_parsing_service
from app.workers.settings import TASK_PARSE_PRICE

logger = get_logger(__name__)


@celery_app.task(
    name=TASK_PARSE_PRICE,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def parse_price(subscription_id: int) -> None:
    try:
        asyncio.run(_parse_price(subscription_id))
    except SoftTimeLimitExceeded:
        logger.warning(
            "parse_price_timeout",
            subscription_id=subscription_id,
            message="Task exceeded soft time limit",
        )
        raise
    except Exception as e:
        logger.error(
            "parse_price_error",
            subscription_id=subscription_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


async def _parse_price(
    subscription_id: int,
) -> None:
    # Создаём свой engine для этой задачи (не используем глобальный)
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
            service = await get_price_parsing_service(session)
            await service.parse_subscription(subscription_id=subscription_id)
            await session.commit()
    finally:
        await engine.dispose()
