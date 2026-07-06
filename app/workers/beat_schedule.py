from datetime import timedelta

from app.core.config import settings
from app.workers.settings import TASK_CHECK_ALL_SUBSCRIPTIONS

interval_seconds = settings.price_check_interval

if interval_seconds % 60 == 0:
    from celery.schedules import crontab

    interval_minutes = interval_seconds // 60
    if interval_minutes == 1:
        schedule = crontab(minute="*")
    elif interval_minutes < 60:
        schedule = crontab(minute=f"*/{interval_minutes}")
    else:
        schedule = crontab(minute=0, hour=f"*/{interval_minutes // 60}")
else:
    schedule = timedelta(seconds=interval_seconds)

beat_schedule = {
    "check-all-subscriptions": {
        "task": TASK_CHECK_ALL_SUBSCRIPTIONS,
        "schedule": schedule,
    },
}
