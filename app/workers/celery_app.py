from celery import Celery

from app.core.config import settings
from app.workers.settings import DEFAULT_QUEUE


celery_app = Celery(
    "pricepulse",
    broker=settings.rabbitmq_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_default_queue=DEFAULT_QUEUE,
)

celery_app.autodiscover_tasks(
    [
        "app.workers.tasks",
    ],
)
