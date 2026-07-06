from celery import Celery
from rich.traceback import install as install_rich_traceback

from app.core.config import settings
from app.core.logging import setup_logging
from app.workers.beat_schedule import beat_schedule
from app.workers.settings import DEFAULT_QUEUE

install_rich_traceback(
    show_locals=True, locals_max_string=100, locals_max_length=10, max_frames=15
)
setup_logging(settings.log_level)
celery_app = Celery("pricepulse", broker=settings.rabbitmq_url)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_default_queue=DEFAULT_QUEUE,
    # === Concurrency & Resource Limits ===
    worker_concurrency=settings.worker_concurrency,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # === Time Limits ===
    task_soft_time_limit=120,
    task_time_limit=150,
    # === Worker Lifecycle ===
    worker_max_tasks_per_child=1,
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
    # === Logging ===
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format=(
        "[%(asctime)s: %(levelname)s/%(processName)s]"
        "[%(task_name)s(%(task_id)s)] %(message)s"
    ),
    # === Beat Schedule ===
    beat_schedule=beat_schedule,
)

celery_app.autodiscover_tasks(["app.workers.tasks"])
