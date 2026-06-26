from structlog import get_logger

from app.workers.settings import TASK_PARSE_PRICE
from app.workers.celery_app import celery_app


logger = get_logger()


@celery_app.task(
    name=TASK_PARSE_PRICE,
)
def parse_price(
    subscription_id: int,
) -> None:
    logger.info(
        "parse_price_started",
        subscription_id=subscription_id,
    )
