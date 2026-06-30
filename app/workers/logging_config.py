from celery.signals import setup_logging as celery_setup_logging

from app.core.config import settings
from app.core.logging import setup_logging


@celery_setup_logging.connect
def configure_logging(**kwargs):
    """Настройка логирования для Celery worker и beat."""
    kwargs["loglevel"] = settings.log_level
    setup_logging(settings.log_level)
