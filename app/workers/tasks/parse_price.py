import asyncio

from app.core.database import get_db
from app.workers.celery_app import celery_app
from app.workers.dependencies import get_price_parsing_service
from app.workers.settings import TASK_PARSE_PRICE


@celery_app.task(
    name=TASK_PARSE_PRICE,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def parse_price(subscription_id: int) -> None:
    asyncio.run(_parse_price(subscription_id))


async def _parse_price(
    subscription_id: int,
) -> None:
    async for session in get_db():
        service = await get_price_parsing_service(session)
        await service.parse_subscription(subscription_id=subscription_id)
        await session.commit()
