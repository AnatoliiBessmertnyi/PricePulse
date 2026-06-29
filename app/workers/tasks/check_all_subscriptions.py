import asyncio

from app.core.database import get_db
from app.workers.celery_app import celery_app
from app.workers.dependencies import get_subscription_service
from app.workers.settings import TASK_CHECK_ALL_SUBSCRIPTIONS
from app.workers.tasks.parse_price import parse_price


@celery_app.task(name=TASK_CHECK_ALL_SUBSCRIPTIONS)
def check_all_subscriptions() -> None:
    asyncio.run(_check_all_subscriptions())


async def _check_all_subscriptions() -> None:
    async for session in get_db():
        service = get_subscription_service(session)
        subscriptions = await service.get_all()

        for subscription in subscriptions:
            parse_price.delay(subscription.id)
