from celery import Celery

from app.core.config import settings


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
)
