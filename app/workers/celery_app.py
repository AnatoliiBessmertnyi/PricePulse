from celery import Celery
from celery.signals import worker_shutdown

from app.core.config import settings
from app.workers.http_client_manager import close_http_client
from app.workers.settings import DEFAULT_QUEUE
from app.workers.beat_schedule import beat_schedule

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
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    beat_schedule=beat_schedule,
)

celery_app.autodiscover_tasks(
    [
        "app.workers.tasks",
    ],
)


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Закрываем http клиент при остановке воркера."""
    import asyncio

    asyncio.run(close_http_client())
