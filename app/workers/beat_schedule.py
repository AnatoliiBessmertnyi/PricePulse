from celery.schedules import crontab

from app.workers.settings import TASK_CHECK_ALL_SUBSCRIPTIONS

beat_schedule = {
    "check-all-subscriptions": {
        "task": TASK_CHECK_ALL_SUBSCRIPTIONS,
        "schedule": crontab(minute="*"),
    }
}
